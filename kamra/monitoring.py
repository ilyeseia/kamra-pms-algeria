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
