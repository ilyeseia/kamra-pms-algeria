# Copyright (c) 2026 Ilyes Keskas (Algeria)
# Part of the ZIRI PMS Algeria distribution of Kamra PMS.
# SPDX-License-Identifier: AGPL-3.0-or-later
# See NOTICE for the upstream authorship this builds on.
"""The vendor fetch, tested against the four rules in its own header.

The feature - a record arriving by itself instead of being typed - is the
easy part and the last thing these tests check. What they mostly check is
that the fetch cannot hurt the hotel, because that is the only way a module
like this goes wrong:

  rule 1  a response may not remove or weaken a stored record
  rule 2  a failure is never an outage
  rule 3  only the Installation ID and the version leave the building
  rule 4  deleting the module changes nothing but convenience

Rule 1 has the most tests, and deliberately so. Every one of them is a way a
live customer's plan could be erased by something that is not their fault: a
URL pointed at the wrong host, a vendor restored from an old backup, a typo
in an Installation ID, a half-written response.

No test here makes a real network call. `fetch` is replaced where the
response is what is under test; `_endpoint` and `urlopen` are replaced where
the request is.
"""

import json

import frappe
from frappe.tests import IntegrationTestCase

from kamra import entitlement as E
from kamra import entitlement_sync as S

URL = "https://vendor.example/api/method/ziri_vendor.api.entitlement"

GOOD = {
	"plan": "Support - Standard",
	"customer": "Hôtel El Karma SARL",
	"reference": "DZ-2026-0041",
	"starts": "2026-01-15",
	"expires": "2027-01-14",
	"services": ["updates", "support"],
}


class _Resp:
	"""Just enough of urlopen's return value."""

	def __init__(self, payload, raw=None):
		self._body = raw if raw is not None else json.dumps(payload).encode()

	def read(self, n=None):
		return self._body[:n] if n else self._body

	def __enter__(self):
		return self

	def __exit__(self, *a):
		return False


class _SyncTest(IntegrationTestCase):
	def setUp(self):
		self._saved = {k: frappe.conf.get(k)
		               for k in ("kamra_entitlement_url", "kamra_entitlement_sync",
		                         "kamra_entitlement")}
		self._real = {name: getattr(S, name)
		              for name in ("fetch", "_endpoint", "_write_sync",
		                           "_read_sync", "urlopen")}
		# Bookkeeping in site config is a file write. Held in memory for the
		# test so a run does not leave anything behind on the machine.
		self._book = {}
		S._write_sync = lambda **kw: self._book.update(kw)
		S._read_sync = lambda: dict(self._book)
		S._endpoint = lambda: URL

	def tearDown(self):
		# Every stub is put back by name. A module attribute left patched
		# leaks into whatever test module runs next in the same process,
		# which is the kind of failure that gets blamed on the wrong file.
		for name, value in self._real.items():
			setattr(S, name, value)
		for k, v in self._saved.items():
			if v is None:
				frappe.conf.pop(k, None)
			else:
				frappe.conf[k] = v
		frappe.db.rollback()

	def _stored(self):
		return E.state().get("record") or {}

	def _set_local(self, **kw):
		rec = {**GOOD, **kw}
		E.set_record(rec["plan"], expires=rec.get("expires"),
		             customer=rec.get("customer"), reference=rec.get("reference"),
		             starts=rec.get("starts"), services=rec.get("services"))


# ── rule 1: a response may not remove or weaken a record ─────────────────
class TestItCannotTakeAnythingAway(_SyncTest):
	def test_unknown_installation_does_not_erase_the_record(self):
		"""The one that would hurt a real customer. A vendor restored from an
		old backup, or a URL pointed at the wrong host, answers found:false -
		and that is not an instruction to forget what the hotel has."""
		self._set_local()
		S.fetch = lambda: {"ok": True, "found": False,
		                   "outcome": "unknown-installation"}
		out = S.sync(force=True)
		self.assertFalse(out["acted"])
		self.assertEqual(self._stored()["plan"], GOOD["plan"])
		self.assertEqual(E.state()["state"], "active")

	def test_an_unreachable_vendor_does_not_erase_the_record(self):
		self._set_local()
		S.fetch = lambda: {"ok": False, "outcome": "unreachable",
		                   "detail": "no route"}
		S.sync(force=True)
		self.assertEqual(self._stored()["plan"], GOOD["plan"])

	def test_an_unparseable_record_does_not_erase_the_record(self):
		self._set_local()
		S.fetch = lambda: {"ok": False, "outcome": "bad-record"}
		S.sync(force=True)
		self.assertEqual(self._stored()["expires"], GOOD["expires"])

	def test_a_record_with_no_plan_is_refused_rather_than_stored(self):
		"""Validation, not the network. A response the vendor really sent,
		with the one field entitlement.py needs missing."""
		self.assertIsNone(S._validate({"customer": "X", "expires": "2027-01-01"}))
		self.assertIsNone(S._validate({"plan": "   "}))
		self.assertIsNone(S._validate(None))
		self.assertIsNone(S._validate("a string"))
		self.assertIsNone(S._validate([GOOD]))

	def test_an_unparseable_date_is_refused_not_passed_through(self):
		"""A date entitlement.state() cannot read turns a healthy record into
		LICENSE-004 - the hotel reporting a fault about the vendor's typo."""
		self.assertIsNone(S._validate({**GOOD, "expires": "next Tuesday"}))
		self.assertIsNone(S._validate({**GOOD, "starts": "15/01/2026 maybe"}))

	def test_a_stored_record_survives_every_failure_outcome(self):
		"""Swept rather than listed one by one, so a new failure path added
		later to fetch() is covered by this test the day it is written."""
		for outcome in ("not-configured", "no-installation-id", "rate-limited",
		                "http-error", "unreachable", "bad-response",
		                "bad-record", "store-failed"):
			with self.subTest(outcome=outcome):
				self._set_local()
				S.fetch = lambda o=outcome: {"ok": False, "outcome": o}
				S.sync(force=True)
				self.assertEqual(self._stored()["plan"], GOOD["plan"])


# ── rule 2: a failure is never an outage ─────────────────────────────────
class TestItFailsQuietly(_SyncTest):
	def test_sync_survives_a_fetch_that_explodes(self):
		"""An expired certificate, a DNS library throwing something exotic, a
		vendor serving a redirect loop. The scheduler must get an answer."""
		self._set_local()

		def boom():
			raise RuntimeError("the vendor's certificate expired")

		S.fetch = boom
		out = S.sync(force=True)
		self.assertFalse(out["ok"])
		self.assertFalse(out["acted"])
		self.assertEqual(self._stored()["plan"], GOOD["plan"])

	def test_an_unconfigured_site_does_no_work_and_reports_it(self):
		S._endpoint = lambda: ""
		out = S.sync()
		self.assertFalse(out["acted"])
		self.assertEqual(out["outcome"], "not-configured")

	def test_the_health_check_is_untouched_by_a_failed_fetch(self):
		"""monitoring.py pages on `failed` health checks. A vendor's outage is
		not a hotel's outage, and the entitlement check must stay exactly as
		forgiving as it was before this module existed."""
		from kamra.health import _entitlement_check

		self._set_local()
		S.fetch = lambda: {"ok": False, "outcome": "unreachable"}
		S.sync(force=True)
		self.assertNotEqual(_entitlement_check()["status"], "failed")

	def test_get_entitlement_still_answers_if_the_sync_module_breaks(self):
		"""Rule 4, from the other side: the record stands on its own."""
		real = S.last_sync
		try:
			S.last_sync = lambda: 1 / 0
			out = E.get_entitlement()
			self.assertIn("state", out)
			self.assertFalse(out["enforced"])
		finally:
			S.last_sync = real


# ── rule 3: only the Installation ID and the version leave ───────────────
class TestItSendsNothingElse(_SyncTest):
	def _capture(self):
		seen = {}

		def fake_urlopen(request, timeout=None):
			seen["url"] = request.full_url
			seen["method"] = request.get_method()
			seen["headers"] = dict(request.headers)
			seen["body"] = request.data
			seen["timeout"] = timeout
			return _Resp({"found": True, "record": GOOD})

		S.urlopen = fake_urlopen
		return seen

	def test_the_request_carries_two_parameters_and_no_body(self):
		from urllib.parse import parse_qs, urlparse

		seen = self._capture()
		S.fetch()
		query = parse_qs(urlparse(seen["url"]).query)
		self.assertEqual(sorted(query), ["installation_id", "version"])
		self.assertEqual(seen["method"], "GET")
		self.assertIsNone(seen["body"])

	def test_nothing_about_the_hotel_is_in_the_request(self):
		seen = self._capture()
		S.fetch()
		blob = (seen["url"] + json.dumps(seen["headers"])).lower()
		for leaked in ("guest", "revenue", "occupancy", "room", "folio",
		               "reservation", "@", "password", "token"):
			self.assertNotIn(leaked, blob)

	def test_the_request_has_a_timeout(self):
		"""A background job on a domestic connection must not hang."""
		seen = self._capture()
		S.fetch()
		self.assertEqual(seen["timeout"], S.TIMEOUT)
		self.assertLessEqual(S.TIMEOUT, 15)

	def test_only_https_is_ever_called(self):
		for bad in ("http://vendor.example/x", "ftp://vendor.example/x",
		            "file:///etc/passwd", "vendor.example/x", "", "   ",
		            "https://", "javascript:alert(1)"):
			with self.subTest(url=bad):
				frappe.conf["kamra_entitlement_url"] = bad
				S._endpoint = self._real['_endpoint']
				self.assertEqual(S._endpoint(), "")
				self.assertFalse(S.configured())

	def test_an_https_url_is_accepted(self):
		frappe.conf["kamra_entitlement_url"] = URL
		S._endpoint = self._real['_endpoint']
		self.assertEqual(S._endpoint(), URL)


# ── the response, which is somebody else's data ──────────────────────────
class TestItDistrustsTheResponse(_SyncTest):
	def _answer(self, payload=None, raw=None):
		S.urlopen = lambda request, timeout=None: _Resp(payload, raw)

	def test_a_frappe_wrapped_response_is_understood(self):
		"""A whitelisted Frappe method returns {"message": {...}}. Both shapes
		are accepted because the hotel cannot be redeployed if the vendor
		later moves the endpoint behind a plain handler."""
		self._answer({"message": {"found": True, "record": GOOD}})
		out = S.fetch()
		self.assertTrue(out["ok"])
		self.assertEqual(out["record"]["plan"], GOOD["plan"])

	def test_an_unwrapped_response_is_understood(self):
		self._answer({"found": True, "record": GOOD})
		self.assertTrue(S.fetch()["ok"])

	def test_rubbish_is_not_a_record(self):
		for raw in (b"", b"not json", b"<html>503</html>", b"null", b"[]",
		            b'{"found": true}', b'{"found": true, "record": "x"}'):
			with self.subTest(raw=raw):
				self._answer(raw=raw)
				out = S.fetch()
				self.assertFalse(out.get("ok") and out.get("found"))

	def test_an_enormous_answer_is_refused_unread(self):
		self._answer(raw=b'{"found": true, "record": {"plan": "'
		                 + b"x" * (S.MAX_BYTES + 100) + b'"}}')
		self.assertEqual(S.fetch()["outcome"], "bad-response")

	def test_long_strings_are_bounded(self):
		rec = S._validate({"plan": "p" * 5000, "customer": "c" * 5000})
		self.assertLessEqual(len(rec["plan"]), 140)
		self.assertLessEqual(len(rec["customer"]), 140)

	def test_services_as_a_string_or_a_list_both_work(self):
		self.assertEqual(S._validate({**GOOD, "services": "updates, sla"})["services"],
		                 ["updates", "sla"])
		self.assertEqual(S._validate({**GOOD, "services": ["updates"]})["services"],
		                 ["updates"])
		self.assertNotIn("services", S._validate({**GOOD, "services": 42}))

	def test_a_rate_limit_is_a_normal_outcome(self):
		from urllib.error import HTTPError

		def limited(request, timeout=None):
			raise HTTPError(URL, 429, "Too Many Requests", {}, None)

		S.urlopen = limited
		out = S.fetch()
		self.assertEqual(out["outcome"], "rate-limited")
		self.assertFalse(out["ok"])

	def test_the_dates_are_normalised_not_echoed(self):
		rec = S._validate({**GOOD, "expires": "2027-01-14 00:00:00"})
		self.assertEqual(rec["expires"], "2027-01-14")


# ── the feature itself ───────────────────────────────────────────────────
class TestItActuallySaves(_SyncTest):
	def test_a_fetched_record_becomes_the_stored_record(self):
		E.clear_record()
		S.fetch = lambda: {"ok": True, "found": True, "outcome": "fetched",
		                   "record": dict(GOOD)}
		out = S.sync(force=True)
		self.assertTrue(out["acted"])
		stored = self._stored()
		for field in ("plan", "customer", "reference", "starts", "expires"):
			self.assertEqual(stored[field], GOOD[field])
		self.assertEqual(stored["services"], GOOD["services"])

	def test_a_renewal_replaces_the_old_dates(self):
		self._set_local(expires="2026-02-01")
		renewed = {**GOOD, "expires": "2028-01-14"}
		S.fetch = lambda: {"ok": True, "found": True, "outcome": "fetched",
		                   "record": renewed}
		out = S.sync(force=True)
		self.assertTrue(out["acted"])
		self.assertIn("expires", out["changed"])
		self.assertEqual(self._stored()["expires"], "2028-01-14")

	def test_an_unchanged_record_is_not_rewritten(self):
		"""Site config holds the database password and the encryption key.
		Rewriting it 365 times a year to store the same six strings is a risk
		taken for nothing."""
		self._set_local()
		S.fetch = lambda: {"ok": True, "found": True, "outcome": "fetched",
		                   "record": dict(GOOD)}
		out = S.sync(force=True)
		self.assertFalse(out["acted"])
		self.assertEqual(out["outcome"], "unchanged")

	def test_a_change_leaves_one_audit_line_and_a_no_op_leaves_none(self):
		marker = S._AUDIT_PREFIX

		def count():
			return frappe.db.count("Activity Log",
			                       {"subject": ["like", f"{marker}%"]})

		E.clear_record()
		S.fetch = lambda: {"ok": True, "found": True, "outcome": "fetched",
		                   "record": dict(GOOD)}
		before = count()
		S.sync(force=True)
		self.assertEqual(count(), before + 1)
		S.sync(force=True)          # nothing changed this time
		self.assertEqual(count(), before + 1)

	def test_the_bookkeeping_is_not_the_record(self):
		"""Two keys on purpose: a sync failure must not be able to corrupt
		the thing it was trying to refresh."""
		self._set_local()
		S.fetch = lambda: {"ok": False, "outcome": "unreachable",
		                   "detail": "no route to host"}
		S.sync(force=True)
		self.assertEqual(self._book["outcome"], "unreachable")
		self.assertIn("plan", self._stored())
		self.assertNotIn("outcome", self._stored())


# ── when it runs ─────────────────────────────────────────────────────────
class TestWhenItRuns(_SyncTest):
	def test_a_site_that_has_never_synced_goes_at_once(self):
		"""Somebody who has just configured the URL should not wait up to a
		day to find out whether it works."""
		self.assertTrue(S._due({}))

	def test_a_recent_attempt_is_not_repeated(self):
		recent = frappe.utils.add_to_date(frappe.utils.now(), hours=-2)
		self.assertFalse(S._due({"last_attempt": recent}))

	def test_an_old_attempt_becomes_due_again(self):
		"""Only in this installation's own hour - which is the point of the
		derived hour, so a fleet does not arrive together. Checked across a
		whole day: exactly one hour must be due."""
		old = frappe.utils.add_to_date(frappe.utils.now(), days=-3)
		due = [h for h in range(24)
		       if S._due({"last_attempt": old},
		                 now=frappe.utils.add_to_date(
			                 frappe.utils.nowdate(), hours=h))]
		self.assertEqual(len(due), 1, f"due in hours {due}, expected exactly one")

	def test_the_hour_is_stable_for_one_installation(self):
		old = frappe.utils.add_to_date(frappe.utils.now(), days=-3)
		first = [h for h in range(24)
		         if S._due({"last_attempt": old},
		                   now=frappe.utils.add_to_date(
			                   frappe.utils.nowdate(), hours=h))]
		second = [h for h in range(24)
		          if S._due({"last_attempt": old},
		                    now=frappe.utils.add_to_date(
			                    frappe.utils.nowdate(), hours=h))]
		self.assertEqual(first, second)

	def test_an_unreadable_timestamp_does_not_wedge_it_shut_for_ever(self):
		for bad in ("not a date", "", 0, None, []):
			with self.subTest(value=bad):
				# Either due now or due in its own hour; never never.
				day = [h for h in range(24)
				       if S._due({"last_attempt": bad},
				                 now=frappe.utils.add_to_date(
					                 frappe.utils.nowdate(), hours=h))]
				self.assertTrue(day, f"last_attempt={bad!r} is never due")


# ── rule 4, and the one thing that must never appear here ────────────────
class TestItGatesNothing(_SyncTest):
	def test_the_module_contains_no_enforcement(self):
		"""A guard against the change somebody will eventually try to make.
		Reading the source is crude and it is also the only way to catch a
		gate that has not been written yet."""
		import inspect

		src = inspect.getsource(S).lower()
		# Anything that would read as "stop the hotel using X".
		for forbidden in ("frappe.throw", "permissionerror", "disable",
		                  "deactivate", "block", "suspend", "lockout",
		                  "raise frappe"):
			self.assertNotIn(forbidden, src,
			                 f"{forbidden!r} appears in entitlement_sync.py - "
			                 "read the header of kamra/entitlement.py")

	def test_nothing_in_the_app_branches_on_the_sync_outcome(self):
		"""The sync may inform a screen. It may not be a condition anywhere."""
		import pathlib
		import re

		root = pathlib.Path(S.__file__).parent
		# Word boundaries matter: without them "or" matches inside "for ".
		pattern = re.compile(r"\b(if|elif|while|assert|and|or|not)\b\s+[^\n]*"
		                     r"(entitlement_sync|last_sync)\s*\(")
		offenders = []
		for path in root.rglob("*.py"):
			if path.name in ("entitlement_sync.py",) or "tests" in path.parts:
				continue
			text = path.read_text(encoding="utf-8", errors="replace")
			if pattern.search(text):
				offenders.append(str(path.relative_to(root)))
		self.assertEqual(offenders, [])

	def test_sync_now_is_role_gated(self):
		"""The one function that makes the server reach out on demand belongs
		to whoever runs the hotel."""
		self.assertTrue(hasattr(S.sync_now, "__wrapped__")
		                or S.sync_now.__doc__)
		import inspect

		src = inspect.getsource(S)
		marker = src.split("def sync_now")[0]
		self.assertIn('@require_roles("Hotel Admin", "System Manager")',
		              marker[marker.rindex("@frappe.whitelist"):])
