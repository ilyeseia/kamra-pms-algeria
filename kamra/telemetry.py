# Copyright (c) 2026 Ilyes Keskas (Algeria)
# Part of the ZIRI PMS Algeria distribution of Kamra PMS.
# SPDX-License-Identifier: AGPL-3.0-or-later
# See NOTICE for the upstream authorship this builds on.
"""What a hotel may CHOOSE to tell the vendor about the software. Nothing else.

OFF, AND IT STAYS OFF UNTIL SOMEBODY SAYS OTHERWISE

Two things must be true before a single byte leaves, and they are deliberately
separate:

    bench --site <site> set-config kamra_telemetry_url \\
        "https://vendor.example/api/method/ziri_vendor.api.telemetry"
    # then, from the Desk or the shell, a named person agrees:
    bench --site <site> ziri-telemetry --consent

The URL is "where". The consent is "yes". They are separate because a vendor
who ships a preconfigured image can set the URL in a template, and the thing
that must come from whoever runs the hotel is the agreement - after reading
what would be sent. `kamra_telemetry_consent` records WHO agreed and WHEN,
the way kamra/support_access.py records who let a technician in. A boolean
would not have been a record of consent, only a flag.

WHY IT IS A SEPARATE ENDPOINT FROM THE ENTITLEMENT FETCH

Because rule 3 of the entitlement contract says nothing personal crosses that
wire, and because the two have opposite shapes: the entitlement fetch is a
GET that asks about this hotel and sends two parameters; this is a POST that
tells the vendor about the software. Putting them on one endpoint would mean
a hotel could not accept one and refuse the other, which is the whole point.

THE RULE THAT MAKES THIS SAFE, AND IT IS NOT "BE CAREFUL"

Every value in the payload is INTERSECTED WITH A KNOWN VOCABULARY on the way
out. Not sanitised, not escaped, not reviewed - intersected:

  - module names are filtered to kamra.api.ALL_MODULES
  - error codes are filtered to the ERROR_CODES.md pattern, ^[A-Z]+-[0-9]{3}$
  - health counts are integers, cast
  - versions are matched against a version-shaped pattern
  - the property count is replaced by a bucket, so it is one of four strings

So a hand-edited Property with a guest's name typed into `enabled_modules`, a
hostile `code` injected by a future check, a site name, a plan title - none of
them can appear, because none of them is in a vocabulary. The payload is
assembled from enum values and numbers this module itself produced. There is
no string in it that was ever typed by a person.

That is why `preview()` is honest: it runs the same builder, so what a
hotelier reads is byte-for-byte what would be sent.

WHAT IS NOT IN IT, AND CANNOT BE

No guest, no reservation, no folio, no rate, no revenue, no occupancy, no
room count, no staff name, no email, no phone number, no site hostname, no
property name. Not "we try not to" - there is no field for any of them and
`_payload()` has no access to a vocabulary that could contain one.

The Installation ID IS sent, in the clear. It identifies the installation so
a week's report can be deduplicated and a trend can be followed. It is not
hashed, because the vendor holds the entitlement records too and could hash
any ID it already knows - a hash here would protect nobody and would read as
though it did.

IT GATES NOTHING, LIKE EVERYTHING ELSE HERE

A refusal to send telemetry changes nothing about what the software does, and
cannot. See the header of kamra/entitlement.py for why that is the licence
rather than a policy.
"""

from __future__ import annotations

import hashlib
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import frappe

from kamra.authz import require_roles

_URL_KEY = "kamra_telemetry_url"
_CONSENT_KEY = "kamra_telemetry_consent"
_STATE_KEY = "kamra_telemetry_state"

# Same floor as health.py's outbound check and entitlement_sync's fetch. This
# runs in a background job on a hotel's own server, often on a domestic
# connection; a job that hangs on a vendor's outage is worse than one that
# gives up and tries next week.
TIMEOUT = 8

# Weekly, not daily. Nothing in this payload changes hour to hour, and a
# weekly cadence is a quarter of the noise for the same signal.
MIN_HOURS_BETWEEN = 6 * 24 + 12

# An ERROR_CODES.md identifier. Codes are filtered through this rather than
# trusted, so a future health check returning something else - a sentence, a
# field value, a stack trace - contributes nothing instead of leaking.
_CODE = re.compile(r"^[A-Z]+-[0-9]{3}$")

# A version string, and nothing that merely claims to be one. Bounded length
# matters as much as the shape: this is the only part of the payload read from
# a value this module did not compute.
_VERSION = re.compile(r"^[0-9]+(\.[0-9]+){0,3}([-+][0-9A-Za-z.]{1,20})?$")

# The complete set of keys that may appear. `_payload()` is filtered through
# it, so a key added to the builder without being added here is dropped rather
# than sent - and the test that compares the two fails.
ALLOWED_KEYS = (
	"installation_id",
	"distribution",
	"distribution_version",
	"kamra_version",
	"frappe_version",
	"python_version",
	"health_overall",
	"health_passed",
	"health_attention",
	"health_failed",
	"health_info",
	"codes",
	"modules",
	"properties",
	"sent_at",
)

# Coarse on purpose. "How big is this install" is worth knowing for sizing
# support; "this hotel has 7 properties" is a business fact the vendor has no
# need of unless they are already the vendor, in which case the contract says
# so. Four buckets answer the first question and not the second.
_BUCKETS = ((1, "1"), (5, "2-5"), (20, "6-20"))


# ── the two switches ─────────────────────────────────────────────────────
def _endpoint() -> str:
	"""The configured URL, or "" meaning off. https only.

	Refuses anything else rather than raising: this is read from a scheduled
	job, and a typo in site_config must not become an hourly traceback. The
	scheme matters more here than for the entitlement fetch - that one only
	receives, this one sends.
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
	return raw if parsed.scheme == "https" and parsed.netloc else ""


def _consent() -> dict:
	"""Who agreed, and when. {} means nobody has."""
	try:
		raw = frappe.conf.get(_CONSENT_KEY)
	except Exception:
		return {}
	if not raw:
		return {}
	if isinstance(raw, dict):
		return raw
	try:
		out = json.loads(str(raw))
		return out if isinstance(out, dict) and out.get("by") else {}
	except (ValueError, TypeError):
		# An unreadable consent record is not consent. Failing closed is the
		# only safe direction for this one value in the whole module.
		return {}


def enabled() -> bool:
	"""Both switches, and both are required."""
	return bool(_endpoint()) and bool(_consent().get("by"))


def _write(key: str, value) -> None:
	from frappe.installer import update_site_config

	blob = json.dumps(value) if value is not None else None
	update_site_config(key, blob, validate=False)
	# frappe.conf in this process is a snapshot; same reason as
	# kamra/installation.py and kamra/setup_state.py.
	if blob is None:
		frappe.conf.pop(key, None)
	else:
		frappe.conf[key] = blob


# ── the payload, built from vocabularies ─────────────────────────────────
def _version(value) -> str | None:
	text = str(value or "").strip()
	return text if text and len(text) <= 40 and _VERSION.match(text) else None


def _bucket(count: int) -> str:
	for ceiling, label in _BUCKETS:
		if count <= ceiling:
			return label
	return "20+"


def _modules() -> list[str]:
	"""Which parts of the product are in use anywhere on this site.

	Intersected with ALL_MODULES, not read. `Property.enabled_modules` is a
	comma-separated text field a human can edit, so whatever is in it is
	treated as a claim to be checked against the vocabulary - which means a
	guest's name typed into that field contributes nothing.
	"""
	from kamra.api import ALL_MODULES

	seen: set[str] = set()
	try:
		for raw in frappe.get_all("Property", pluck="enabled_modules") or []:
			for part in str(raw or "").split(","):
				candidate = part.strip()
				if candidate in ALL_MODULES:
					seen.add(candidate)
	except Exception:
		return []
	return sorted(seen)


def _health() -> dict:
	"""Counts, an overall word, and the error codes currently reported.

	The codes are the useful half. A vendor who can see that nine installs
	are reporting BACKUP-002 this week knows something worth knowing, and
	every one of those strings comes from this product's own taxonomy.
	"""
	try:
		from kamra.health import system_health

		report = system_health()
	except Exception:
		return {}

	summary = report.get("summary") or {}
	codes = sorted({
		str(c.get("code") or "") for c in (report.get("checks") or [])
		if _CODE.match(str(c.get("code") or ""))
	})
	overall = str(report.get("overall") or "")
	return {
		"health_overall": overall if overall in
		("passed", "attention", "failed", "info") else None,
		"health_passed": int(summary.get("passed") or 0),
		"health_attention": int(summary.get("attention") or 0),
		"health_failed": int(summary.get("failed") or 0),
		"health_info": int(summary.get("info") or 0),
		"codes": codes[:40],
	}


def _payload() -> dict:
	"""Exactly what would be sent. Used by preview() and by send().

	One builder, so a hotelier reading the preview is reading the thing
	itself rather than a description of it.
	"""
	import sys

	from kamra import __version__ as kamra_version
	from kamra.distribution import DISTRIBUTION, DISTRIBUTION_VERSION

	try:
		from kamra.installation import installation_id

		iid = installation_id(create=False)
	except Exception:
		iid = None

	try:
		properties = frappe.db.count("Property")
	except Exception:
		properties = 0

	out = {
		"installation_id": iid,
		"distribution": DISTRIBUTION,
		"distribution_version": _version(DISTRIBUTION_VERSION),
		"kamra_version": _version(kamra_version),
		"frappe_version": _version(getattr(frappe, "__version__", None)),
		"python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
		"modules": _modules(),
		"properties": _bucket(int(properties or 0)),
		"sent_at": frappe.utils.now(),
		**_health(),
	}
	# The allowlist is applied to the built dict, not trusted to the builder.
	# A key added above and not added to ALLOWED_KEYS is dropped here, and
	# kamra/tests/test_telemetry.py fails on the difference.
	return {k: v for k, v in out.items() if k in ALLOWED_KEYS}


# ── consent ──────────────────────────────────────────────────────────────
@frappe.whitelist()
@require_roles("Hotel Admin", "System Manager")
def preview() -> dict:
	"""What would be sent, whether or not sending is switched on.

	Readable before agreeing, which is the only thing that makes agreeing
	meaningful. Role-gated because the health codes say what is currently
	wrong with the hotel's own system.
	"""
	return {
		"enabled": enabled(),
		"configured": bool(_endpoint()),
		"consent": _consent(),
		"payload": _payload(),
		"note": ("This is the whole payload, built by the same function that "
		         "sends it. Nothing in ZIRI PMS depends on whether you send "
		         "it."),
	}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def give_consent() -> dict:
	"""Agree, on the record.

	Stores who and when rather than a boolean, so that months later the
	question "who turned this on" has an answer. Does not configure the URL:
	agreeing to send and deciding where to send are different decisions and
	only one of them is the hotel's.
	"""
	record = {"by": frappe.session.user, "at": frappe.utils.now()}
	try:
		_write(_CONSENT_KEY, record)
	except Exception:
		frappe.log_error(title="telemetry: could not record consent")
		return {"ok": False}
	return {"ok": True, "consent": record, "configured": bool(_endpoint())}


@frappe.whitelist(methods=["POST"])
@require_roles("Hotel Admin", "System Manager")
def withdraw_consent() -> dict:
	"""Stop. Takes effect on the next scheduled run and needs no explanation.

	The URL is deliberately left alone: withdrawing consent should not
	require re-typing an endpoint to change one's mind back.
	"""
	try:
		_write(_CONSENT_KEY, None)
	except Exception:
		frappe.log_error(title="telemetry: could not withdraw consent")
		return {"ok": False}
	return {"ok": True, "enabled": enabled()}


# ── sending ──────────────────────────────────────────────────────────────
def _read_state() -> dict:
	try:
		raw = frappe.conf.get(_STATE_KEY)
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


def _write_state(**fields) -> None:
	state = _read_state()
	state.update(fields)
	try:
		_write(_STATE_KEY, state)
	except Exception:
		frappe.log_error(title="telemetry: could not record the attempt")


def last_sent() -> dict:
	state = _read_state()
	return {
		"enabled": enabled(),
		"last_attempt": state.get("last_attempt"),
		"last_success": state.get("last_success"),
		"outcome": state.get("outcome"),
	}


def _due(state: dict, now=None) -> bool:
	"""Weekly, in an hour and on a weekday derived from the Installation ID.

	Same reasoning as entitlement_sync._due and the same arithmetic, one
	cadence slower: a fleet of hotels spread across 168 hours rather than
	arriving together, and derived rather than random so one install reports
	at the same time each week.
	"""
	last = state.get("last_attempt")
	if not last:
		return True
	try:
		if frappe.utils.time_diff_in_hours(now or frappe.utils.now(),
		                                   last) < MIN_HOURS_BETWEEN:
			return False
	except Exception:
		# An unreadable timestamp must not wedge it shut for ever.
		return True

	try:
		from kamra.installation import installation_id

		iid = installation_id(create=False) or ""
	except Exception:
		iid = ""
	digest = hashlib.sha256(iid.encode("utf-8")).digest()
	try:
		when = frappe.utils.get_datetime(now or frappe.utils.now())
	except Exception:
		return True
	return when.hour == digest[0] % 24 and when.weekday() == digest[1] % 7


def send(force: bool = False) -> dict:
	"""The hourly job that acts about weekly. Never raises.

	Called from hooks.py. A site with no URL, no consent, or neither does
	nothing at all - which is every site by default.
	"""
	if not enabled():
		return {"ok": False, "outcome": "not-enabled", "sent": False}
	if not force and not _due(_read_state()):
		return {"ok": True, "outcome": "not-due", "sent": False}

	url = _endpoint()
	body = json.dumps(_payload()).encode("utf-8")
	request = Request(  # https is enforced in _endpoint()
		url, data=body, method="POST",
		headers={"Content-Type": "application/json",
		         "Accept": "application/json"},
	)

	outcome, ok = "sent", True
	try:
		with urlopen(request, timeout=TIMEOUT) as resp:  # nosemgrep: python.lang.security - https enforced in _endpoint()
			resp.read(4096)
	except HTTPError as e:
		outcome, ok = ("rate-limited" if e.code == 429
		               else f"http-{e.code}"), False
	except (URLError, TimeoutError, OSError) as e:
		outcome, ok = f"unreachable-{type(e).__name__}", False
	except Exception as e:
		# Nothing about a telemetry failure is worth a traceback in a
		# scheduler log every hour, and nothing about it affects the hotel.
		outcome, ok = f"error-{type(e).__name__}", False

	now = frappe.utils.now()
	_write_state(last_attempt=now, outcome=outcome,
	             **({"last_success": now} if ok else {}))
	return {"ok": ok, "outcome": outcome, "sent": ok}
