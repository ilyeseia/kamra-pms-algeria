# Copyright (c) 2026 Ilyes Keskas (Algeria)
# Part of the ZIRI PMS Algeria distribution of Kamra PMS.
# SPDX-License-Identifier: AGPL-3.0-or-later
# See NOTICE for the upstream authorship this builds on.
"""Asking the vendor what this installation bought. Never asking permission.

READ kamra/entitlement.py FIRST. Its header is the law here: that module is a
record and a reminder, it gates nothing, and nothing in this file may change
that. This only saves somebody retyping the record by hand.

WHAT THIS IS

One daily HTTPS GET to the vendor's endpoint, carrying the Installation ID and
nothing else, writing the six fields entitlement.py already understands. The
contract is docs/ENTITLEMENT_API.md in the vendor's own repository.

OFF UNLESS SOMEBODY TURNS IT ON

No URL configured, no request - and no URL is configured by default:

    bench --site <site> set-config kamra_entitlement_url \\
        "https://vendor.example/api/method/ziri_vendor.api.entitlement"

That default is not timidity. This software is AGPL-3.0 and may be run by
anyone with no commercial relationship at all; an install that phones a
vendor nobody told it about would be a surprise at best, and most ZIRI
installations will legitimately never have an entitlement to fetch. The same
reasoning already governs `kamra_update_repo` in kamra/distribution.py, which
can be emptied to switch update checking off and says so when it is off.

THE FOUR THINGS A FETCH MAY NOT DO

These are the vendor contract's own rules, enforced on this side, where it
matters - the hotel is the party that would be harmed:

  1. It may not remove or weaken a record. A response that says "I have never
     heard of this installation" is NOT an instruction to forget what the
     hotel already has. A pointed-at-the-wrong-host URL, a vendor's database
     restored from an old backup, or a typo in the Installation ID would
     otherwise erase a live customer's plan. Only `found: true` with a record
     that passes validation writes anything.
  2. It may not fail loudly. A fetch that cannot reach the vendor leaves the
     stored record exactly as it was and reports `info`. There is no state of
     this network call that is an outage for a hotel, because the record
     itself gates nothing.
  3. It may not send anything but the Installation ID and, optionally, the
     version. No guest data, no occupancy, no revenue, no room count. The
     payload is two query parameters and it stays that way.
  4. It may not be the thing that makes the software run. Delete this file and
     ZIRI PMS is unchanged except that somebody types the record by hand.

WHY HTTPS ONLY

The Installation ID is not a secret (kamra/installation.py says so), so the
risk is not eavesdropping - it is the answer. Over plain HTTP anything on the
path could hand this installation a record, and while a false record cannot
switch anything off, a hotelier reading somebody else's plan on their own
dashboard is a defect. `_endpoint()` refuses anything but https.

WHERE THE BOOKKEEPING LIVES

A separate site config key from the record itself. The record is the six
fields and must stay exactly that; when the last attempt happened and how it
went is this module's business, and mixing the two would mean a sync failure
could corrupt the thing it was trying to refresh.
"""

from __future__ import annotations

import hashlib
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import frappe

from kamra.authz import require_roles

_URL_KEY = "kamra_entitlement_url"
_SYNC_KEY = "kamra_entitlement_sync"

# Matches health.py's outbound check. Short on purpose: this runs in a
# background job on a hotel's own server, often on a domestic connection, and
# a job that hangs for a minute on a vendor's outage is worse than one that
# gives up and tries tomorrow.
TIMEOUT = 8

# A vendor's answer is six short strings. Anything larger is not that answer,
# and reading it into memory on a hotel's server is not this module's job.
MAX_BYTES = 64 * 1024

# How stale an attempt has to be before another one is due. Not 24h: a run
# missed because the server was off overnight should be picked up by the next
# hourly pass rather than waiting a further day.
MIN_HOURS_BETWEEN = 23

# Both sides treat this as the whole record. entitlement.py reads exactly
# these; the vendor's contract promises exactly these.
_FIELDS = ("plan", "customer", "reference", "starts", "expires", "services")

# Written only when the record actually changes. A distinct prefix from
# monitoring.py's `[data]` so the backup-and-restore trail stays one list -
# see _AUDIT_PREFIX there for why the marker lives in the subject at all.
_AUDIT_PREFIX = "[entitlement]"


# ── configuration ────────────────────────────────────────────────────────
def _endpoint() -> str:
	"""The configured URL, or "" meaning off.

	Refuses anything that is not https for the reason in the header. A
	misconfigured URL reads as "off" rather than raising: this is called from a
	scheduled job, and a typo in site_config must not become a traceback every
	hour.
	"""
	try:
		raw = str(frappe.conf.get(_URL_KEY) or "").strip()
	except Exception:
		return ""
	if not raw:
		return ""
	try:
		parsed = urlparse(raw)
	except Exception:
		return ""
	if parsed.scheme != "https" or not parsed.netloc:
		return ""
	return raw


def configured() -> bool:
	return bool(_endpoint())


# ── the response, which is somebody else's data ──────────────────────────
def _clean_services(value) -> list[str]:
	if isinstance(value, str):
		return [s.strip() for s in value.split(",") if s.strip()][:20]
	if isinstance(value, (list, tuple)):
		return [str(s).strip() for s in value if str(s).strip()][:20]
	return []


def _validate(record) -> dict | None:
	"""The vendor's record as something safe to store, or None.

	Everything here arrives from off this machine, so nothing is trusted: not
	the field set, not the types, not the lengths, not that a date is a date.
	Returning None means "keep what we have", which is rule 1.
	"""
	if not isinstance(record, dict):
		return None

	plan = str(record.get("plan") or "").strip()
	if not plan:
		# A record with no plan says nothing that entitlement.py can report,
		# and overwriting a good record with it would lose information.
		return None

	out: dict = {"plan": plan[:140]}
	for field in ("customer", "reference"):
		value = str(record.get(field) or "").strip()
		if value:
			out[field] = value[:140]

	for field in ("starts", "expires"):
		value = str(record.get(field) or "").strip()
		if not value:
			continue
		try:
			# Normalised rather than passed through. entitlement.state() does
			# date_diff on `expires`, and a value it cannot parse turns a
			# healthy record into LICENSE-004 - a self-inflicted fault
			# reported to the hotelier about the vendor's typo.
			out[field] = frappe.utils.getdate(value).isoformat()
		except Exception:
			return None

	services = _clean_services(record.get("services"))
	if services:
		out["services"] = services
	return out


# ── bookkeeping, kept away from the record ───────────────────────────────
def _read_sync() -> dict:
	try:
		raw = frappe.conf.get(_SYNC_KEY)
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
		return {}


def _write_sync(**fields) -> None:
	state = _read_sync()
	state.update(fields)
	try:
		from frappe.installer import update_site_config

		blob = json.dumps(state)
		update_site_config(_SYNC_KEY, blob, validate=False)
		# frappe.conf in this process is a snapshot; same reason as
		# kamra/installation.py and kamra/setup_state.py.
		frappe.conf[_SYNC_KEY] = blob
	except Exception:
		# Losing the bookkeeping costs the next run its timing, not the
		# hotel's record. Never the thing that fails a sync.
		frappe.log_error(title="entitlement sync: could not record the attempt")


def last_sync() -> dict:
	"""When this last ran and how it went. For the CLI and the UI."""
	state = _read_sync()
	return {
		"configured": configured(),
		"last_attempt": state.get("last_attempt"),
		"last_success": state.get("last_success"),
		"outcome": state.get("outcome"),
		"detail": state.get("detail"),
	}


# ── the request ──────────────────────────────────────────────────────────
def _audit(detail: str) -> None:
	"""One Activity Log line, and only when the record really changed.

	A line per fetch would be 365 rows a year saying nothing happened, and an
	audit trail nobody reads is not one. A line when a hotelier's plan changed
	under them is the one somebody will go looking for.
	"""
	try:
		frappe.get_doc({
			"doctype": "Activity Log",
			"subject": f"{_AUDIT_PREFIX} record updated from the vendor - {detail}"[:500],
			"status": "Success",
			"user": "Administrator",
			"full_name": "ZIRI entitlement sync",
		}).insert(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit -- the audit line must survive a failing caller
	except Exception as e:
		frappe.log_error(
			title=f"entitlement sync: could not record the change: {type(e).__name__}",
			message=str(e),
		)


def fetch() -> dict:
	"""Ask, once. Returns what happened; writes nothing and never raises.

	Separated from sync() so the decision to store is testable apart from the
	network, and so a technician can see the vendor's answer without it
	landing in site config.
	"""
	url = _endpoint()
	if not url:
		return {"ok": False, "outcome": "not-configured",
		        "detail": "No kamra_entitlement_url is set for this site."}

	try:
		from kamra.installation import installation_id

		iid = installation_id(create=False)
	except Exception:
		iid = None
	if not iid:
		# Before first run, or a site whose config cannot be read. Nothing to
		# look up, and generating an ID as a side effect of a background job
		# is not this module's decision to make.
		return {"ok": False, "outcome": "no-installation-id",
		        "detail": "This site has no Installation ID yet."}

	try:
		from kamra.distribution import DISTRIBUTION_VERSION

		version = DISTRIBUTION_VERSION
	except Exception:
		version = None

	# Two parameters. Rule 3, and the only place it could be broken.
	query = {"installation_id": iid}
	if version:
		query["version"] = version
	sep = "&" if "?" in url else "?"
	request = Request(
		f"{url}{sep}{urlencode(query)}",
		headers={"Accept": "application/json",
		         "User-Agent": f"ZIRI-PMS/{version or 'unknown'}"},
		method="GET",
	)

	try:
		with urlopen(request, timeout=TIMEOUT) as resp:  # nosemgrep: python.lang.security - https enforced in _endpoint()
			body = resp.read(MAX_BYTES + 1)
	except HTTPError as e:
		if e.code == 429:
			# The contract's own answer to a client asking too often. Not a
			# problem to report: the stored record is still good.
			return {"ok": False, "outcome": "rate-limited",
			        "detail": "The vendor is rate limiting; will try again."}
		return {"ok": False, "outcome": "http-error",
		        "detail": f"The vendor answered HTTP {e.code}."}
	except (URLError, TimeoutError, OSError) as e:
		return {"ok": False, "outcome": "unreachable",
		        "detail": f"Could not reach the vendor ({type(e).__name__})."}

	if len(body) > MAX_BYTES:
		return {"ok": False, "outcome": "bad-response",
		        "detail": "The vendor's answer was too large to be an entitlement."}

	try:
		payload = json.loads(body.decode("utf-8", "replace"))
	except (ValueError, TypeError):
		return {"ok": False, "outcome": "bad-response",
		        "detail": "The vendor's answer was not JSON."}

	# Frappe wraps a whitelisted method's return value in `message`. Both
	# shapes are accepted because a vendor may well put this behind a plain
	# handler later, and the hotel cannot be redeployed to follow.
	if isinstance(payload, dict) and "message" in payload and "found" not in payload:
		payload = payload.get("message")
	if not isinstance(payload, dict):
		return {"ok": False, "outcome": "bad-response",
		        "detail": "The vendor's answer was not an entitlement."}

	if not payload.get("found"):
		# Rule 1. This vendor has no record of this installation - which is
		# the normal answer for most installs, and never a reason to discard
		# what the hotel already has.
		return {"ok": True, "found": False, "outcome": "unknown-installation",
		        "detail": "The vendor has no record for this installation; "
		                  "anything already stored was left alone."}

	record = _validate(payload.get("record"))
	if record is None:
		return {"ok": False, "outcome": "bad-record",
		        "detail": "The vendor's record could not be read; "
		                  "anything already stored was left alone."}
	return {"ok": True, "found": True, "outcome": "fetched", "record": record}


# ── the scheduled entry point ────────────────────────────────────────────
def _due(state: dict, now=None) -> bool:
	"""Is an attempt due in this hour?

	Runs hourly and acts roughly daily, in an hour derived from the
	Installation ID. That spreads a fleet of hotels across the 24 hours
	instead of every one of them arriving at the vendor on the stroke of
	03:00, and it is derived rather than random so a given hotel asks at the
	same time every day - which makes "it stopped asking on Tuesday"
	a readable fact rather than noise.
	"""
	last = state.get("last_attempt")
	if last:
		try:
			hours = frappe.utils.time_diff_in_hours(
				now or frappe.utils.now(), last)
			if hours < MIN_HOURS_BETWEEN:
				return False
		except Exception:
			# An unreadable timestamp should not wedge the sync shut for
			# ever; treat it as "never ran".
			pass
	else:
		# Never run. Go now rather than waiting up to 24 hours to find out
		# whether the URL somebody just configured even works.
		return True

	try:
		from kamra.installation import installation_id

		iid = installation_id(create=False) or ""
	except Exception:
		iid = ""
	digest = hashlib.sha256(iid.encode("utf-8")).digest()
	try:
		hour_now = frappe.utils.get_datetime(now or frappe.utils.now()).hour
	except Exception:
		return True
	return hour_now == digest[0] % 24


def sync(force: bool = False) -> dict:
	"""The hourly job. Acts about once a day, and never raises.

	Called from hooks.py. Everything it can return is a normal outcome: a
	hotel with no vendor, a vendor that is down, a vendor that has never heard
	of this installation. None of them changes what the software does.
	"""
	if not configured():
		return {"ok": False, "outcome": "not-configured", "acted": False}

	state = _read_sync()
	if not force and not _due(state):
		return {"ok": True, "outcome": "not-due", "acted": False}

	try:
		result = fetch()
	except Exception as e:
		# fetch() is written not to raise, and this is here anyway. It runs
		# from the scheduler, where an unhandled exception is noise in a log
		# about somebody else's server being down - and rule 2 says a vendor's
		# problem is never the hotel's.
		frappe.log_error(title=f"entitlement sync: fetch raised "
		                       f"{type(e).__name__}", message=str(e))
		result = {"ok": False, "outcome": "unreachable",
		          "detail": f"{type(e).__name__} while asking the vendor."}

	now = frappe.utils.now()
	_write_sync(last_attempt=now, outcome=result["outcome"],
	            detail=result.get("detail"),
	            **({"last_success": now} if result.get("ok") else {}))

	if not result.get("ok"):
		# Deliberately log_error rather than an alert. monitoring.py pages on
		# `failed` health checks, and a vendor's outage is not a hotel's
		# outage - see the header of kamra/entitlement.py on why a billing
		# matter must never wake anybody at 03:00.
		frappe.log_error(
			title=f"entitlement sync: {result['outcome']}",
			message=result.get("detail") or "",
		)
		return {**result, "acted": False}

	if not result.get("found"):
		return {**result, "acted": False}

	from kamra.entitlement import set_record
	from kamra.entitlement import state as current_state

	before = (current_state().get("record") or {})
	record = result["record"]
	changed = [f for f in _FIELDS
	           if (before.get(f) or ([] if f == "services" else None))
	           != (record.get(f) or ([] if f == "services" else None))]
	if not changed:
		return {**result, "acted": False, "outcome": "unchanged"}

	try:
		set_record(
			record["plan"], expires=record.get("expires"),
			customer=record.get("customer"), reference=record.get("reference"),
			starts=record.get("starts"), services=record.get("services"),
		)
	except Exception as e:
		frappe.log_error(title=f"entitlement sync: could not store the record: "
		                       f"{type(e).__name__}", message=str(e))
		return {"ok": False, "outcome": "store-failed", "acted": False,
		        "detail": str(e)[:200]}

	_audit(f"{record['plan']}; fields changed: {', '.join(changed)}")
	return {**result, "acted": True, "changed": changed}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def sync_now() -> dict:
	"""Check with the vendor now, for a hotelier who has just renewed.

	Role-gated and POST-only. Not because the fetch is dangerous - it reads
	one record about this hotel - but because it is the one function here that
	makes the server reach out on demand, and that belongs to whoever runs the
	hotel rather than to every logged-in user.
	"""
	result = sync(force=True)
	from kamra.entitlement import get_entitlement

	return {"sync": {k: v for k, v in result.items() if k != "record"},
	        "entitlement": get_entitlement()}
