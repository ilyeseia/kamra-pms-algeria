# Copyright (c) 2026 Ilyes Keskas (Algeria)
# Part of the ZIRI PMS Algeria distribution of Kamra PMS.
# SPDX-License-Identifier: AGPL-3.0-or-later
# See NOTICE for the upstream authorship this builds on.
"""Where the first-run wizard is up to, kept somewhere a closed tab cannot lose.

THE PROBLEM THIS SOLVES

frontend/src/screens/Setup.tsx is a five-step wizard holding its progress in
`useState(0)`. That lives in one browser tab. Close it, lose the connection,
have the laptop sleep, hit a validation error you need to go and ask the owner
about - and the hotelier starts again from the first screen, re-typing what
they already typed.

The brief asks for a resumable wizard and says why in one line: do not assume
installation will always complete on the first attempt. On a hotel's own
server, over Algerian connectivity, that is not a hypothetical.

WHAT RESUMABLE MEANS HERE, AND WHAT IT DOES NOT

It means the wizard's ANSWERS and its position survive the tab. It does not
mean the wizard replays actions: `setup_property` has already created a
Property by the time step three is reached, and this module never calls it
again. Resume returns a hotelier to where they were, with what they had
typed; the records already created stay created.

That distinction is the whole safety of it. A wizard that "resumed" by
re-running its steps would create a second property on a flaky connection,
which is worse than losing a form.

WHERE IT IS STORED, AND WHY NOT IN A DOCTYPE

Site config, like the Installation ID and the entitlement record. The wizard
runs before a hotel has anything - possibly before Property exists at all -
and a setup state that needs the schema to be complete cannot help with a
setup that failed halfway through building it.

WHAT MUST NEVER GO IN HERE

No passwords, no API keys. The administrator's password is set through
Frappe's own user flow and is not a wizard answer this module keeps. A
resumable form that remembers a password is a password written to a config
file, and this module refuses the keys rather than trusting callers.
"""

from __future__ import annotations

import json

import frappe

from kamra.authz import require_roles

_KEY = "kamra_setup_state"

# The wizard's own step count is in the frontend; this is a sanity bound, not
# a schema. A step number outside it means the two have drifted and the state
# is more likely to confuse than to help.
MAX_STEP = 20

# Answers whose names say they are secret are dropped on the way in. Matched
# by substring because the frontend names its own fields and will add more.
_FORBIDDEN = ("password", "passwd", "secret", "token", "api_key", "apikey",
              "private_key", "credential", "pin")

# One wizard, one hotel, one sitting. A state older than this is a setup
# somebody walked away from, and resuming into half-remembered answers from
# last month is worse than starting fresh.
STALE_DAYS = 30


def _sanitise(answers: dict) -> tuple[dict, list[str]]:
	"""Strip anything that looks like a credential. Returns (kept, dropped)."""
	kept, dropped = {}, []
	for k, v in (answers or {}).items():
		key = str(k)
		if any(bad in key.lower() for bad in _FORBIDDEN):
			dropped.append(key)
			continue
		# Values are the hotelier's own typing; bound them so a paste cannot
		# turn the site config into a megabyte of JSON.
		if isinstance(v, str) and len(v) > 2000:
			v = v[:2000]
		kept[key] = v
	return kept, dropped


def _read() -> dict:
	try:
		raw = frappe.conf.get(_KEY)
	except Exception:
		return {}
	if not raw:
		return {}
	if isinstance(raw, dict):
		return raw
	try:
		out = json.loads(str(raw))
		return out if isinstance(out, dict) else {}
	except (ValueError, TypeError):
		# A hand-edited site_config should not wedge the wizard. Treated as
		# "nothing saved", which starts the hotelier at step one rather than
		# refusing to open.
		return {}


def _write(state: dict) -> None:
	from frappe.installer import update_site_config

	blob = json.dumps(state)
	update_site_config(_KEY, blob, validate=False)
	# frappe.conf in this process is a snapshot; set it too or a read in the
	# same request returns the old value. Same reason as kamra/installation.py.
	frappe.conf[_KEY] = blob


def _is_stale(state: dict) -> bool:
	saved = state.get("saved_at")
	if not saved:
		return False
	try:
		age = frappe.utils.date_diff(frappe.utils.nowdate(), saved[:10])
	except Exception:
		return False
	return age > STALE_DAYS


@frappe.whitelist()
@require_roles("Hotel Admin", "System Manager")
def get_state() -> dict:
	"""Where the wizard was, or an empty start.

	Role-gated: setup answers are the hotel's own commercial details - its
	name, its address, how many rooms it has - and are nobody else's business
	even on a site that has no data yet.
	"""
	state = _read()
	if not state:
		return {"step": 0, "answers": {}, "resumed": False}
	if _is_stale(state):
		# Not deleted. The hotelier is told it is old and offered a fresh
		# start; throwing away what they typed without asking is the thing
		# this module exists to prevent.
		return {"step": 0, "answers": {}, "resumed": False,
		        "stale": True, "saved_at": state.get("saved_at")}
	return {
		"step": int(state.get("step") or 0),
		"answers": state.get("answers") or {},
		"resumed": True,
		"saved_at": state.get("saved_at"),
		"property": state.get("property"),
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def save_state(step: int | str = 0, answers=None, property: str | None = None) -> dict:
	"""Record progress. Called after each step, and safe to call repeatedly.

	Never raises for a bad step or an odd answer: this runs between two
	screens of a form, and a hotelier who loses their place because the
	save call was strict is exactly the person this was written for.
	"""
	try:
		step = int(step)
	except (TypeError, ValueError):
		step = 0
	step = max(0, min(step, MAX_STEP))

	if isinstance(answers, str):
		try:
			answers = frappe.parse_json(answers)
		except Exception:
			answers = {}
	if not isinstance(answers, dict):
		answers = {}

	kept, dropped = _sanitise(answers)
	state = {
		"step": step,
		"answers": kept,
		"saved_at": frappe.utils.now(),
		"by": frappe.session.user,
	}
	# Once a property exists the wizard has passed the point of no return.
	# Recorded so a resume can say "this one", and so nothing downstream is
	# tempted to create a second.
	existing = _read().get("property")
	if property or existing:
		state["property"] = property or existing

	try:
		_write(state)
	except Exception:
		# A read-only config or a permissions problem costs the hotelier a
		# resume, not their session. Logged where an engineer will find it.
		frappe.log_error(title="setup state: could not persist")
		return {"ok": False, "dropped": dropped}
	return {"ok": True, "step": step, "dropped": dropped}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def clear_state() -> dict:
	"""Forget the saved answers.

	Called when setup finishes, and available to a hotelier who wants to
	start over. Sets the key to null rather than deleting it - Frappe's
	update_site_config has no delete across the versions this runs on, and
	rewriting site_config.json by hand to remove one line would risk the file
	that holds the encryption key and the database password. _read() treats
	null and absent identically.
	"""
	try:
		from frappe.installer import update_site_config

		update_site_config(_KEY, None, validate=False)
		frappe.conf.pop(_KEY, None)
	except Exception:
		frappe.log_error(title="setup state: could not clear")
		return {"ok": False}
	return {"ok": True}
