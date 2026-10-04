"""What the customer bought, and when it runs out. Nothing more.

READ THIS BEFORE CHANGING ANYTHING HERE

This module records a commercial relationship and reports its state. It does
not gate a single function of this software, and it must never be made to.
That is not caution, it is the licence:

  - ZIRI PMS is distributed under the GNU Affero General Public License v3
    (`license.txt`, and `docs/algeria/LICENSING.md` for the obligations).
    AGPL-3.0 section 7 does not permit imposing further restrictions on the
    rights it grants, and running the program is one of those rights. A key
    that switches off the front desk is such a restriction.
  - AGPL-3.0 section 13 requires the complete source to be offered to every
    user who interacts with the program over a network. Any gate written here
    therefore ships, by obligation, together with the instructions for
    removing it. It would be a lock with its own key taped to the door.
  - The product already tells the hotelier, in the marketplace screen
    (`kamra/marketplace.py`): "The rooms of your PMS - every app is open and
    included." Code that contradicts the UI is a defect whichever one is
    right.

What legitimately stops when a customer does not renew is the vendor's own
services, because they run on the vendor's machines: the update feed, the
managed WhatsApp gateway, remote support, an SLA. None of that is enforced
from inside the hotel's installation, and none of it belongs in this file.
This is the model Frappe and ERPNext themselves run on.

So: this is a record and a reminder. If a future requirement is "stop the
hotel from using X until they pay", the answer is not here - it is either a
separate, separately-licensed application the vendor owns, or a conversation
with a lawyer about relicensing, which needs the agreement of the upstream
Kamra authors and not just this distribution's.

WHY IT IS NEVER A FAILED CHECK

An expired invoice is not an outage. health.py reports this as `attention` or
`info` and never as `failed`, and monitoring.py only alerts on `failed` - so an
unpaid renewal will never page anyone at 03:00. A red cross for a billing
matter teaches an operator that red crosses are noise, and the next one is a
database that has stopped answering.

WHERE IT IS STORED

Site config, like the Installation ID and for the same reasons: it must be
readable before app logic runs, by support tooling that cannot assume the
schema is intact, and it should not be something the hotelier edits in the
Desk by accident. It rides in site_config.json, which means a restore brings
it back - and also means it is NOT evidence of anything. Anyone with shell
access can write it. It is a note of what was agreed, for the people who
agreed it.
"""

from __future__ import annotations

import json

import frappe

_KEY = "kamra_entitlement"

# The window after `expires` in which the reminder stays gentle. The brief
# asked for a grace period; this is what a grace period means when nothing is
# being switched off - how long before "renewing soon" becomes "this lapsed".
GRACE_DAYS = 30
# How long before expiry the reminder starts. One month is enough for a hotel
# to raise a purchase order and short enough that the notice still means
# something when it appears.
NOTICE_DAYS = 30

# Service names are free text on purpose: what a vendor sells changes faster
# than this file does, and an enum here would only ever be out of date. These
# are the ones the product currently has a vendor-side service for, offered as
# a hint to whoever writes the record.
KNOWN_SERVICES = ("updates", "support", "remote-support", "managed-whatsapp", "sla")


def _raw() -> dict | None:
	try:
		value = frappe.conf.get(_KEY)
	except Exception:
		return None
	if not value:
		return None
	if isinstance(value, dict):
		return value
	try:
		parsed = json.loads(str(value))
		return parsed if isinstance(parsed, dict) else None
	except (ValueError, TypeError):
		# Deliberately distinguished from "absent" by the caller: a record
		# that exists and cannot be read is a different problem from no
		# record, and reporting it as no record would hide a typo for ever.
		return {"_malformed": True}


def state() -> dict:
	"""The entitlement and its state. Never raises.

	Returned `state` is one of:
	  unregistered - no record. A legitimate, supported state: this software
	                 may be run by anyone under the AGPL with no commercial
	                 relationship at all, and that must not look like a fault.
	  active       - in force, more than NOTICE_DAYS left
	  expiring     - in force, NOTICE_DAYS or less left
	  grace        - past `expires`, within GRACE_DAYS
	  expired      - past `expires` by more than GRACE_DAYS
	  perpetual    - a record with no `expires`. A one-off licence or a
	                 relationship with no renewal date; not an error.
	  malformed    - a record is present and could not be parsed
	"""
	rec = _raw()
	if rec is None:
		return {"state": "unregistered", "record": None, "days": None}
	if rec.get("_malformed"):
		return {"state": "malformed", "record": None, "days": None}

	plan = str(rec.get("plan") or "").strip() or None
	expires = str(rec.get("expires") or "").strip() or None
	services = rec.get("services") or []
	if isinstance(services, str):
		services = [s.strip() for s in services.split(",") if s.strip()]
	out = {
		"plan": plan,
		"customer": str(rec.get("customer") or "").strip() or None,
		"reference": str(rec.get("reference") or "").strip() or None,
		"starts": str(rec.get("starts") or "").strip() or None,
		"expires": expires,
		"services": list(services),
	}

	if not expires:
		return {"state": "perpetual", "record": out, "days": None}

	try:
		days = frappe.utils.date_diff(expires, frappe.utils.nowdate())
	except Exception:
		# A date that will not parse is a malformed record, not an expiry.
		return {"state": "malformed", "record": out, "days": None}

	if days > NOTICE_DAYS:
		st = "active"
	elif days >= 0:
		st = "expiring"
	elif days >= -GRACE_DAYS:
		st = "grace"
	else:
		st = "expired"
	return {"state": st, "record": out, "days": days}


def set_record(plan: str, expires: str | None = None, customer: str | None = None,
               reference: str | None = None, starts: str | None = None,
               services: str | list | None = None) -> dict:
	"""Write the record into site config. Called by `bench ziri-entitlement`.

	Not whitelisted, and deliberately not reachable over HTTP: the record says
	what a customer agreed to buy, and the customer should not be the one
	typing it. Whoever installs or supports the system writes it from a shell.
	"""
	if isinstance(services, str):
		services = [s.strip() for s in services.split(",") if s.strip()]
	rec = {
		"plan": plan,
		"customer": customer,
		"reference": reference,
		"starts": starts,
		"expires": expires,
		"services": list(services or []),
	}
	rec = {k: v for k, v in rec.items() if v not in (None, "", [])}

	from frappe.installer import update_site_config

	update_site_config(_KEY, json.dumps(rec), validate=False)
	# update_site_config rewrites the file; frappe.conf in this process is a
	# snapshot, so set it too or a read in this same request returns the old
	# value. Same reason as kamra/installation.py.
	frappe.conf[_KEY] = json.dumps(rec)
	return state()


def clear_record() -> dict:
	"""Forget the record. An install with no commercial relationship is a
	supported state, so this is a normal operation and not a reset.

	This sets the key to null rather than deleting it: Frappe's
	update_site_config writes `"kamra_entitlement": null` when handed None and
	offers no delete across the versions this runs on. Rewriting
	site_config.json by hand to remove one key would risk the file that holds
	the encryption key and the database password, to tidy a line nothing reads.
	`_raw()` treats null and absent identically, which is checked by the
	`unregistered` path in the tests.
	"""
	from frappe.installer import update_site_config

	update_site_config(_KEY, None, validate=False)
	frappe.conf.pop(_KEY, None)
	return state()


@frappe.whitelist()
def get_entitlement() -> dict:
	"""Readable by any logged-in user.

	Not role-gated, for the same reason the Installation ID is not: it
	authorises nothing, and a hotelier who cannot see when their own support
	contract lapses has a worse experience for no gain. `enforced: False` is
	in the payload so a UI author reading it cannot mistake what it is for.
	"""
	s = state()
	return {
		**s,
		"enforced": False,
		"note": ("Informational. ZIRI PMS is AGPL-3.0 and no feature of it "
		         "depends on this record. See kamra/entitlement.py."),
		"grace_days": GRACE_DAYS,
		"notice_days": NOTICE_DAYS,
	}
