# Copyright (c) 2026 Ilyes Keskas (Algeria)
# Part of the ZIRI PMS Algeria distribution of Kamra PMS.
# SPDX-License-Identifier: AGPL-3.0-or-later
# See NOTICE for the upstream authorship this builds on.
"""Letting a technician in, for a while, with the hotel's permission.

WHY THIS EXISTS AND WHAT IT REPLACES

Support on this product is done today as Hotel Admin or System Manager -
whoever is on the phone hands over an administrator password. That is more
authority than any diagnosis needs, it leaves no record of who looked at what,
and the password usually outlives the call.

The brief this implements is explicit about what must NOT be built: no hidden
backdoors, no permanent hidden accounts, no undocumented SSH credentials, no
secret remote-control. This is the opposite shape. The hotel opens the door,
for a stated reason, for a stated time, to a named person, and the door shuts
by itself.

THE ONE DESIGN DECISION EVERYTHING ELSE FOLLOWS FROM

A granted role is a cached convenience. **The grant is the gate.**

The obvious implementation is to add the Support role to a user and have a
scheduled job remove it when the grant expires. That makes a failed scheduler
indistinguishable from permanent access - the exact backdoor the brief
forbids, arrived at by accident rather than by design. A hotel would never
know, because nothing would look wrong.

So `active_grant()` re-reads the record and re-checks the clock on every call.
The role is attached for the Desk's benefit and removed when convenient; if it
is ever left behind, it authorises nothing. kamra/mcp_oauth.py takes the same
position with its tokens, and for the same reason.

WHO MAY OPEN THE DOOR

The hotel. `request_access` is role-gated to Hotel Admin and System Manager -
the customer's own administrators - and the technician is named in the
request, never the requester. A technician cannot grant themselves access,
which is the property that makes this an authorisation rather than a login.

WHAT A SESSION CAN REACH

Scope, not seniority. The default is `diagnostics`: health, versions, logs,
the support bundle - what a fault is usually found in. `read_only` adds the
hotel's own operational data. `full` exists because some faults cannot be
fixed without writing, and it is the one that must be asked for explicitly,
recorded, and justified.

Nothing here grants System Manager. A support session is never an
administrator.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_to_date, now_datetime

from kamra.authz import require_roles

SUPPORT_ROLE = "Support"
READ_ONLY_ROLE = "Read Only"

# What a session may reach, narrowest first. Ordered, so a check can ask
# "at least this much" without a table of comparisons.
SCOPES = ("diagnostics", "read_only", "full")

# A support call is an hour, not a tenancy. Longer is possible and must be
# asked for; this is what you get by not saying.
DEFAULT_HOURS = 4
MAX_HOURS = 72


def _now():
	return now_datetime()


def active_grant(user: str | None = None):
	"""The live grant for this user, or None.

	Re-read and re-checked on every call. See the module docstring: the role
	is a convenience, this is the gate.
	"""
	user = user or frappe.session.user
	if not user or user in ("Guest", "Administrator"):
		# Administrator is excluded deliberately. It already has every
		# permission; letting it hold a support grant would make the audit
		# trail say a technician was authorised when what really happened is
		# somebody used the admin account.
		return None
	try:
		name = frappe.db.get_value(
			"Support Access Grant",
			{"user": user, "revoked": 0, "expires_after": (">", _now())},
			"name")
	except Exception:
		# A missing table during a migration must not become open access.
		return None
	return frappe.get_doc("Support Access Grant", name) if name else None


def has_scope(minimum: str, user: str | None = None) -> bool:
	"""Does this user hold a live grant of at least `minimum` scope?"""
	if minimum not in SCOPES:
		raise ValueError(f"unknown scope {minimum!r}")
	grant = active_grant(user)
	if not grant:
		return False
	try:
		return SCOPES.index(grant.scope) >= SCOPES.index(minimum)
	except ValueError:
		# A scope that is not in the list is not a scope. Fail closed.
		return False


def require_support_scope(minimum: str = "diagnostics"):
	"""Decorator for endpoints a support session may use."""
	def outer(fn):
		import functools

		@functools.wraps(fn)
		def guarded(*args, **kwargs):
			if not has_scope(minimum):
				frappe.throw(
					"This needs an authorised support session. Ask the hotel "
					"to approve one from Settings.",
					frappe.PermissionError)
			_record(frappe.session.user, "used", fn.__name__)
			return fn(*args, **kwargs)

		guarded._kamra_support_scope = minimum
		return guarded
	return outer


def _record(user: str, event: str, detail: str = "") -> None:
	"""One audit line per support event.

	Into Activity Log, where logins and the data-operation trail already live,
	so an auditor asking "what happened to this site" still reads one list.
	Never raises: a logging failure must not be the thing that stops a
	technician diagnosing an outage, and must not be the thing that stops a
	revocation either.
	"""
	try:
		frappe.get_doc({
			"doctype": "Activity Log",
			"subject": f"[support] {event}: {detail}"[:140],
			"status": "Success" if event != "denied" else "Failed",
			"user": user,
			"full_name": f"support {user}",
		}).insert(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- an access record must survive a failing caller
	except Exception:
		try:
			frappe.log_error(title=f"[SECURITY-006] support audit failed: {event}")
		except Exception:
			pass


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def request_access(technician: str, reason: str, hours: int = DEFAULT_HOURS,
                   scope: str = "diagnostics") -> dict:
	"""The hotel authorises one technician, for a while, for a reason.

	Role-gated to the customer's own administrators, and `technician` is a
	separate argument from the caller - a technician cannot grant themselves
	access, which is what makes this an authorisation and not a login.
	"""
	if scope not in SCOPES:
		frappe.throw(f"Scope must be one of: {', '.join(SCOPES)}.")
	reason = (reason or "").strip()
	if len(reason) < 10:
		# Not bureaucracy. "fixing it" tells the next auditor nothing, and the
		# reason is the only part of this record a human writes.
		frappe.throw("Give a reason a reader will understand in six months.")
	try:
		hours = int(hours)
	except (TypeError, ValueError):
		frappe.throw("Hours must be a number.")
	if not 1 <= hours <= MAX_HOURS:
		frappe.throw(f"Access can last between 1 and {MAX_HOURS} hours.")
	if not frappe.db.exists("User", technician):
		frappe.throw("No such user to authorise.")
	if technician == frappe.session.user:
		frappe.throw("Authorise the technician, not yourself.",
		             frappe.PermissionError)

	doc = frappe.get_doc({
		"doctype": "Support Access Grant",
		"user": technician,
		"scope": scope,
		"reason": reason,
		"approved_by": frappe.session.user,
		"granted_at": _now(),
		"expires_after": add_to_date(_now(), hours=hours),
		"revoked": 0,
	}).insert(ignore_permissions=True)

	_attach_role(technician)
	_record(technician, "granted",
	        f"{scope} for {hours}h by {frappe.session.user}: {reason}")
	return {"grant": doc.name, "expires_after": str(doc.expires_after),
	        "scope": scope}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def revoke_access(grant: str) -> dict:
	"""Shut the door now rather than waiting for the clock."""
	doc = frappe.get_doc("Support Access Grant", grant)
	doc.revoked = 1
	doc.save(ignore_permissions=True)
	_detach_role(doc.user)
	_record(doc.user, "revoked", f"by {frappe.session.user}")
	return {"ok": True}


@frappe.whitelist()
@require_roles("Hotel Admin", "System Manager")
def list_access() -> list[dict]:
	"""Every grant, live or not. The hotel's own record of who was let in."""
	rows = frappe.get_all(
		"Support Access Grant",
		fields=["name", "user", "scope", "reason", "approved_by",
		        "granted_at", "expires_after", "revoked"],
		order_by="granted_at desc", limit=100)
	now = _now()
	for r in rows:
		r["live"] = bool(not r["revoked"] and r["expires_after"]
		                 and r["expires_after"] > now)
	return rows


def _attach_role(user: str) -> None:
	try:
		doc = frappe.get_doc("User", user)
		if not any(r.role == SUPPORT_ROLE for r in doc.roles):
			doc.append("roles", {"role": SUPPORT_ROLE})
			doc.save(ignore_permissions=True)
	except Exception:
		# The role is a convenience for the Desk. active_grant() is what
		# actually authorises, so failing to attach it costs a technician a
		# Desk menu, not the session.
		frappe.log_error(title="support access: could not attach role")


def _detach_role(user: str) -> None:
	try:
		doc = frappe.get_doc("User", user)
		keep = [r for r in doc.roles if r.role != SUPPORT_ROLE]
		if len(keep) != len(doc.roles):
			doc.set("roles", [])
			for r in keep:
				doc.append("roles", {"role": r.role})
			doc.save(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="support access: could not detach role")


def expire_grants() -> dict:
	"""Scheduled tidy-up: take the role off users whose grant has lapsed.

	This is housekeeping, NOT enforcement. Every check goes through
	active_grant(), which reads the clock itself - so a run of this that never
	happens leaves a stale role that authorises nothing. Said plainly because
	the opposite assumption is how a support door becomes a permanent one.
	"""
	closed = 0
	try:
		stale = frappe.get_all(
			"Support Access Grant",
			filters={"revoked": 0, "expires_after": ("<=", _now())},
			pluck="user")
	except Exception:
		return {"ok": False}
	for user in set(stale):
		if not active_grant(user):
			_detach_role(user)
			_record(user, "expired")
			closed += 1
	return {"ok": True, "closed": closed}
