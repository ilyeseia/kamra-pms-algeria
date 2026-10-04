"""Watch the health checks so nobody has to.

WHY THIS EXISTS
health.py can tell you the scheduler has not run, the disk is nearly full or
the database is unreachable. It tells whoever opens the panel. On this very
installation the scheduler was stalled from the moment the site was created -
the night audit never ran once - and nothing said so, because nobody opens a
health panel on a system that appears to be working. A check that waits to be
read is a check that reports a fire the morning after.

WHAT IT DOES NOT DO
It does not replace Prometheus, and it is not a monitoring product. It is the
smallest thing that closes the gap between "the product knows" and "a human
knows", on a single-server hotel install that will never have an observability
stack. A site that does have one should scrape kamra.health.system_health and
turn this off.

THE TWO WAYS THIS GOES WRONG, AND WHAT STOPS THEM
  1. Alert fatigue. An hourly mail saying "still broken" gets filtered within a
     week, and the filter catches the next real failure too. So this alerts on
     a CHANGE of state, not on a state: one mail when a check starts failing,
     one when it recovers, nothing in between. A daily reminder is deliberately
     not implemented - if an operator has ignored the first mail for a day,
     a second identical one is not the missing piece.
  2. The monitor breaking the thing it monitors. This runs inside the
     scheduler. An exception here kills the job that also posts the night
     audit, so every failure path returns quietly and logs.
"""

from __future__ import annotations

import json

import frappe

from kamra.authz import require_roles

_STATE_KEY = "kamra_health_alert_state"
# Advisories are not pages. "No backup yet" and "a newer release exists" are
# real and neither is worth waking anyone; they are visible on the panel and in
# ziri-doctor. Only a failed check alerts.
_ALERT_ON = ("failed",)


def _recipients() -> list[str]:
	"""Who hears about it.

	`kamra_alert_email` in site config first, because an operator who set it
	meant it. Otherwise every enabled System Manager, which is who would be
	called anyway.
	"""
	configured = frappe.conf.get("kamra_alert_email")
	if configured:
		return [e.strip() for e in str(configured).split(",") if e.strip()]
	rows = frappe.get_all(
		"Has Role",
		filters={"role": "System Manager", "parenttype": "User"},
		pluck="parent",
	)
	return [
		u for u in rows
		if u not in ("Administrator", "Guest")
		and frappe.db.get_value("User", u, "enabled")
	]


def _load_state() -> dict:
	try:
		raw = frappe.db.get_global(_STATE_KEY)
		return json.loads(raw) if raw else {}
	except Exception:
		return {}


def _save_state(state: dict) -> None:
	try:
		frappe.db.set_global(_STATE_KEY, json.dumps(state))
	except Exception:
		frappe.log_error(title="health monitor: could not persist state")


def _post_webhook(url: str, payload: dict) -> None:
	"""Vendor-neutral by construction: one POST of JSON to whatever the site
	configured. No client library, no account, nothing to keep up to date."""
	import urllib.request

	req = urllib.request.Request(
		url,
		data=json.dumps(payload).encode("utf-8"),
		headers={"Content-Type": "application/json"},
		method="POST",
	)
	with urllib.request.urlopen(req, timeout=10):  # nosemgrep: python.lang.security - operator-configured endpoint
		pass


def _notify(subject: str, lines: list[str], payload: dict) -> None:
	body = "\n".join(lines)
	to = _recipients()
	if to:
		try:
			frappe.sendmail(recipients=to, subject=subject, message=body.replace("\n", "<br>"))
		except Exception:
			frappe.log_error(title="health monitor: email failed")
	url = frappe.conf.get("kamra_alert_webhook")
	if url:
		try:
			_post_webhook(str(url), payload)
		except Exception:
			frappe.log_error(title="health monitor: webhook failed")
	if not to and not url:
		# Not silent: an installation with nowhere to send an alert should say
		# so in a place an engineer will find, rather than appear healthy.
		frappe.log_error(
			title="health monitor: no recipients",
			message=f"{subject}\n\n{body}\n\nSet kamra_alert_email or "
			        "kamra_alert_webhook in site config, or enable a System "
			        "Manager user.",
		)


def check_and_alert() -> dict:
	"""Scheduled hourly. Alerts on a change of state, never on a state."""
	try:
		from kamra.health import system_health
		from kamra.installation import installation_id

		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- scheduled job; system_health is read-only and role-gated
		result = system_health(refresh=1)
	except Exception as e:
		frappe.log_error(title=f"health monitor: could not run checks: {type(e).__name__}")
		return {"ok": False, "error": str(e)[:200]}

	now = {c["id"]: c["status"] for c in result.get("checks", [])}
	was = _load_state()
	iid = None
	try:
		iid = installation_id()
	except Exception:
		pass

	broke = [i for i, s in now.items()
	         if s in _ALERT_ON and was.get(i) not in _ALERT_ON]
	fixed = [i for i, s in now.items()
	         if s not in _ALERT_ON and was.get(i) in _ALERT_ON]

	detail = {c["id"]: c for c in result.get("checks", [])}
	site = frappe.local.site

	if broke:
		titles = [f"{detail[i]['title']}: {detail[i]['detail']}" for i in broke]
		_notify(
			f"[ZIRI] {site}: {len(broke)} check(s) failing",
			[f"Installation: {iid or 'unknown'}", f"Site: {site}", ""]
			+ titles
			+ ["", "Run `bench --site <site> ziri-doctor` for the full picture."],
			{"event": "health_failed", "installation_id": iid, "site": site,
			 "checks": broke, "detail": {i: detail[i] for i in broke}},
		)
	if fixed:
		_notify(
			f"[ZIRI] {site}: recovered",
			[f"Installation: {iid or 'unknown'}", f"Site: {site}", "",
			 "Recovered: " + ", ".join(detail[i]["title"] for i in fixed)],
			{"event": "health_recovered", "installation_id": iid, "site": site,
			 "checks": fixed},
		)

	_save_state(now)
	return {"ok": True, "overall": result.get("overall"),
	        "newly_failing": broke, "recovered": fixed}


# ── audit: the operations Frappe does not already record ────────────────
# Frappe covers more than a first look suggests, and checking that before
# building anything saved a parallel audit system that would have duplicated
# it: Activity Log carries logins, logouts and failed attempts; Version carries
# document changes on every money doctype in this app; Permission Log carries
# permission edits. What none of them sees is an operator taking a backup or
# restoring one - which is the single most consequential thing anyone does to a
# hotel's data, and until now left no trace at all.

# The marker that makes these rows findable. Both `operation` and `status` on
# Activity Log are Select fields with a vocabulary Frappe owns - operation
# allows only Login, Logout, Impersonate, and status only Success, Failed,
# Linked, Closed. The first version of this wrote operation="Data Operation"
# and status="ok", and Frappe rejected every row; the rows were missing for a
# full backup-and-verify cycle before anyone looked.
#
# The fix is NOT to widen those options with a Property Setter. Appending to a
# core field's option list means owning that list forever: the moment Frappe
# adds an operation of its own, our override silently drops it. Instead the
# operation is left blank - which is valid, and is what Frappe itself writes
# for generic activity rows - and the marker lives in the subject, where no
# framework vocabulary applies.
_AUDIT_PREFIX = "[data]"
# ok -> Success is not cosmetic: Frappe's own list views and reports colour and
# filter on these four values, so a data operation reads like every other row.
_STATUS_MAP = {"ok": "Success", "success": "Success",
               "failed": "Failed", "error": "Failed"}


def record_data_operation(operation: str, detail: str = "", status: str = "ok") -> None:
	"""Write one audit line for a backup, restore or verification.

	Deliberately an Activity Log row rather than a new doctype: an auditor
	looking for "what happened to this site" should find one list, not two, and
	Frappe already applies its retention and permission rules to that one.

	Never raises. This is called from scripts that are themselves recovering a
	site; a logging failure must not be the thing that stops a restore.
	"""
	try:
		from kamra.installation import installation_id
		iid = installation_id(create=False) or "unknown"
	except Exception:
		iid = "unknown"
	try:
		frappe.get_doc({
			"doctype": "Activity Log",
			"subject": f"{_AUDIT_PREFIX} {operation}: {status}"
			           + (f" - {detail}" if detail else ""),
			# operation deliberately unset - see _AUDIT_PREFIX above.
			"status": _STATUS_MAP.get(str(status).lower(), "Failed"),
			"user": frappe.session.user if getattr(frappe, "session", None) else "Administrator",
			"full_name": f"ZIRI {iid}",
		}).insert(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- audit line must survive a failing caller
	except Exception as e:
		# The reason goes in the title. The previous version logged only
		# "could not record backup", which said that the audit trail was
		# broken but not why, and the why was a one-line schema constraint.
		try:
			frappe.log_error(
				title=f"audit: could not record {operation}: {type(e).__name__}",
				message=f"{e}\n\noperation={operation!r} status={status!r} detail={detail!r}",
			)
		except Exception:
			pass


def recent_data_operations(limit: int = 20) -> list[dict]:
	"""The data-operation trail, for ziri-doctor and the support bundle.

	Matching on the subject prefix rather than a dedicated field is the cost of
	not owning Activity Log's Select vocabulary - see _AUDIT_PREFIX. It is an
	indexed-prefix LIKE on a table Frappe already keeps small by retention.
	"""
	try:
		return frappe.get_all(
			"Activity Log",
			filters={"subject": ["like", f"{_AUDIT_PREFIX}%"]},
			fields=["subject", "status", "user", "creation"],
			order_by="creation desc",
			limit=limit,
		)
	except Exception:
		return []


@frappe.whitelist()
@require_roles("Hotel Admin", "System Manager", "Administrator")
def log_data_operation(operation: str, detail: str = "", status: str = "ok") -> dict:
	"""Called by deploy/backup-verify.sh and deploy/verify-restore.sh so an
	operation run from a shell still lands in the site's own audit trail.

	Role-gated even though it only appends: an audit trail any logged-in user
	can write to is an audit trail an attacker can bury their own entry in.
	"""
	record_data_operation(operation, detail, status)
	return {"ok": True}
