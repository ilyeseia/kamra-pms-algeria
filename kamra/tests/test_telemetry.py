# Copyright (c) 2026 Ilyes Keskas (Algeria)
# Part of the ZIRI PMS Algeria distribution of Kamra PMS.
# SPDX-License-Identifier: AGPL-3.0-or-later
# See NOTICE for the upstream authorship this builds on.
"""Opt-in telemetry: that it is off, and that it cannot carry a person.

Two claims are under test and the second is the one the module exists to
make good on.

The first is that nothing is sent unless two separate things are true. A
default install must send nothing, and must keep sending nothing if only one
switch is thrown.

The second is that the payload cannot contain a string anybody typed. The
module's defence is not care, it is intersection: module names are filtered
against ALL_MODULES, error codes against the ERROR_CODES.md pattern, versions
against a version shape, the property count is replaced by a bucket. So the
test for it is adversarial - a guest's name is typed into the fields the
builder reads, and the payload is then searched for it.

A test that only checked the happy payload would pass against a module that
forwarded whatever it found.
"""

import json

import frappe
from frappe.tests import IntegrationTestCase

from kamra import telemetry as T

URL = "https://vendor.example/api/method/ziri_vendor.api.telemetry"

# Typed into every field the builder reads, so a leak is unmistakable rather
# than a judgement call about whether some value was sensitive.
POISON = "Fatima Benali +213 555 0199 fatima@example.com"


class _TelemetryTest(IntegrationTestCase):
	def setUp(self):
		self._saved = {k: frappe.conf.get(k) for k in
		               ("kamra_telemetry_url", "kamra_telemetry_consent",
		                "kamra_telemetry_state")}
		self._real = {name: getattr(T, name) for name in
		              ("_write", "_read_state", "_write_state", "urlopen")}
		# Site config is a file on disk. Held in memory for the test so a run
		# leaves nothing behind on the machine.
		self._conf: dict = {}
		self._state: dict = {}
		T._write = lambda key, value: self._conf.__setitem__(key, value)
		T._read_state = lambda: dict(self._state)
		T._write_state = lambda **kw: self._state.update(kw)

	def tearDown(self):
		for name, value in self._real.items():
			setattr(T, name, value)
		for k, v in self._saved.items():
			if v is None:
				frappe.conf.pop(k, None)
			else:
				frappe.conf[k] = v
		frappe.db.rollback()

	def _switch_on(self):
		frappe.conf["kamra_telemetry_url"] = URL
		frappe.conf["kamra_telemetry_consent"] = json.dumps(
			{"by": "owner@example.com", "at": frappe.utils.now()})

	def _capture(self):
		"""Replace the transport and keep what it was handed."""
		seen = {}

		class _Resp:
			def read(self, n=None):
				return b'{"ok": true}'

			def __enter__(self):
				return self

			def __exit__(self, *a):
				return False

		def fake(request, timeout=None):
			seen.update(url=request.full_url, method=request.get_method(),
			            body=request.data, timeout=timeout,
			            headers=dict(request.headers))
			return _Resp()

		T.urlopen = fake
		return seen


# ── it is off ────────────────────────────────────────────────────────────
class TestItIsOffByDefault(_TelemetryTest):
	def test_a_default_install_sends_nothing(self):
		frappe.conf.pop("kamra_telemetry_url", None)
		frappe.conf.pop("kamra_telemetry_consent", None)
		self.assertFalse(T.enabled())
		out = T.send(force=True)
		self.assertFalse(out["sent"])
		self.assertEqual(out["outcome"], "not-enabled")

	def test_a_url_alone_is_not_consent(self):
		"""A vendor shipping a preconfigured image can set a URL. The
		agreement has to come from whoever runs the hotel."""
		frappe.conf["kamra_telemetry_url"] = URL
		frappe.conf.pop("kamra_telemetry_consent", None)
		self.assertFalse(T.enabled())
		self.assertFalse(T.send(force=True)["sent"])

	def test_consent_alone_sends_nothing(self):
		frappe.conf.pop("kamra_telemetry_url", None)
		frappe.conf["kamra_telemetry_consent"] = json.dumps(
			{"by": "owner@example.com", "at": frappe.utils.now()})
		self.assertFalse(T.enabled())
		self.assertFalse(T.send(force=True)["sent"])

	def test_only_https_is_ever_sent_to(self):
		"""This endpoint SENDS. A plain-http URL would put the report on the
		wire for anything on the path to read."""
		frappe.conf["kamra_telemetry_consent"] = json.dumps(
			{"by": "x", "at": "2026-01-01 00:00:00"})
		for bad in ("http://vendor.example/x", "ftp://vendor.example/x",
		            "file:///etc/passwd", "vendor.example/x", "", "   ",
		            "https://", "javascript:alert(1)"):
			with self.subTest(url=bad):
				frappe.conf["kamra_telemetry_url"] = bad
				self.assertEqual(T._endpoint(), "")
				self.assertFalse(T.enabled())

	def test_an_unreadable_consent_record_is_not_consent(self):
		"""The one value in this module that fails closed."""
		frappe.conf["kamra_telemetry_url"] = URL
		for bad in ("{not json", "[]", "null", '{"at": "now"}', "", "true"):
			with self.subTest(value=bad):
				frappe.conf["kamra_telemetry_consent"] = bad
				self.assertFalse(T.enabled())

	def test_withdrawing_stops_it(self):
		self._switch_on()
		self.assertTrue(T.enabled())
		T.withdraw_consent()
		# _write is captured, so assert on what it was asked to write.
		self.assertIsNone(self._conf["kamra_telemetry_consent"])

	def test_consent_records_who_and_when_not_a_boolean(self):
		"""Months later, "who turned this on" needs an answer."""
		out = T.give_consent()
		self.assertTrue(out["ok"])
		self.assertEqual(out["consent"]["by"], frappe.session.user)
		self.assertTrue(out["consent"]["at"])
		stored = self._conf["kamra_telemetry_consent"]
		self.assertIn("by", stored)


# ── it cannot carry a person ─────────────────────────────────────────────
class TestThePayloadCannotCarryAPerson(_TelemetryTest):
	def test_the_keys_are_exactly_the_allowlist(self):
		payload = T._payload()
		self.assertTrue(set(payload) <= set(T.ALLOWED_KEYS),
		                f"undeclared keys: {set(payload) - set(T.ALLOWED_KEYS)}")

	def test_a_name_typed_into_enabled_modules_does_not_travel(self):
		"""The adversarial case. Property.enabled_modules is comma-separated
		text a human edits, and _modules() intersects it with ALL_MODULES
		rather than reading it."""
		properties = frappe.get_all("Property", pluck="name", limit=1)
		if not properties:
			self.skipTest("no Property on this site to poison")
		frappe.db.set_value("Property", properties[0], "enabled_modules",
		                    f"front-desk,{POISON},housekeeping")
		payload = frappe.as_json(T._payload())
		# Distinctive tokens, not fragments. "213" would have been matched by
		# chance inside a timestamp's microseconds, which is a flaky test
		# rather than a real assertion.
		for token in ("Fatima", "Benali", "5550199", "@example.com"):
			self.assertNotIn(token, payload, f"{token!r} travelled")
		# And the real module names still came through, so this is not
		# passing by producing nothing.
		self.assertIn("front-desk", payload)

	def test_every_module_name_is_in_the_vocabulary(self):
		from kamra.api import ALL_MODULES

		for module in T._payload().get("modules") or []:
			self.assertIn(module, ALL_MODULES)

	def test_every_code_looks_like_an_error_code(self):
		for code in T._payload().get("codes") or []:
			self.assertRegex(code, r"^[A-Z]+-[0-9]{3}$")

	def test_a_rubbish_health_code_is_dropped(self):
		"""A future check returning a sentence, a field value or a stack
		trace must contribute nothing rather than leak."""
		import kamra.health as H

		original = H.system_health
		try:
			H.system_health = lambda *a, **kw: {
				"overall": "passed",
				"summary": {"passed": 1, "attention": 0, "failed": 0, "info": 0},
				"checks": [{"code": POISON}, {"code": "BACKUP-002"},
				           {"code": "not a code"}, {"code": None}],
			}
			out = T._health()
			self.assertEqual(out["codes"], ["BACKUP-002"])
		finally:
			H.system_health = original

	def test_the_site_hostname_never_appears(self):
		"""health.system_health() returns `site`; this payload must not
		forward it, which is why _payload builds its own dict."""
		payload = frappe.as_json(T._payload())
		self.assertNotIn(frappe.local.site, payload)

	def test_the_property_count_is_a_bucket_not_a_number(self):
		self.assertEqual(T._bucket(0), "1")
		self.assertEqual(T._bucket(1), "1")
		self.assertEqual(T._bucket(4), "2-5")
		self.assertEqual(T._bucket(19), "6-20")
		self.assertEqual(T._bucket(500), "20+")
		self.assertIn(T._payload()["properties"], ("1", "2-5", "6-20", "20+"))

	def test_a_version_that_is_not_a_version_is_dropped(self):
		self.assertIsNone(T._version("Hôtel El Karma"))
		self.assertIsNone(T._version("x" * 200))
		self.assertIsNone(T._version(None))
		self.assertEqual(T._version("1.0.0"), "1.0.0")
		self.assertEqual(T._version("16.25.0"), "16.25.0")

	def test_no_value_in_the_payload_looks_like_contact_details(self):
		"""A sweep rather than a list, so a field added later is covered.

		`sent_at` is excluded before the phone sweep, not after: a timestamp
		is digits, spaces and hyphens, so "2026-10-11 14" matches any honest
		phone-number pattern. Keeping it in would have failed this test
		against a correct payload, which is worse than not having it.
		"""
		payload = T._payload()
		timestamp = payload.pop("sent_at", None)
		self.assertTrue(timestamp, "sent_at should exist to be excluded")
		blob = frappe.as_json(payload)
		self.assertNotRegex(blob, r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")
		self.assertNotRegex(blob, r"\+?[0-9][0-9 ()-]{8,}")

	def test_preview_runs_the_same_builder_as_send(self):
		"""Otherwise a hotelier agrees to a description rather than the
		thing. Compared with sent_at removed, which is a clock."""
		self._switch_on()
		seen = self._capture()
		shown = dict(T.preview()["payload"])
		T.send(force=True)
		sent = json.loads(seen["body"].decode())
		shown.pop("sent_at", None)
		sent.pop("sent_at", None)
		self.assertEqual(shown, sent)


# ── the request ──────────────────────────────────────────────────────────
class TestTheRequest(_TelemetryTest):
	def test_it_posts_json_to_the_configured_url_with_a_timeout(self):
		self._switch_on()
		seen = self._capture()
		out = T.send(force=True)
		self.assertTrue(out["sent"])
		self.assertEqual(seen["url"], URL)
		self.assertEqual(seen["method"], "POST")
		self.assertEqual(seen["timeout"], T.TIMEOUT)
		self.assertLessEqual(T.TIMEOUT, 15)
		json.loads(seen["body"].decode())  # it is JSON

	def test_a_failure_is_recorded_and_nothing_else_happens(self):
		from urllib.error import URLError

		self._switch_on()

		def boom(request, timeout=None):
			raise URLError("no route to host")

		T.urlopen = boom
		out = T.send(force=True)
		self.assertFalse(out["sent"])
		self.assertIn("unreachable", out["outcome"])
		self.assertIn("last_attempt", self._state)
		self.assertNotIn("last_success", self._state)

	def test_an_exotic_exception_does_not_escape(self):
		self._switch_on()

		def boom(request, timeout=None):
			raise RuntimeError("the vendor's certificate expired")

		T.urlopen = boom
		out = T.send(force=True)
		self.assertFalse(out["sent"])
		self.assertTrue(out["outcome"].startswith("error-"))

	def test_a_rate_limit_is_a_normal_outcome(self):
		from urllib.error import HTTPError

		self._switch_on()
		T.urlopen = lambda r, timeout=None: (_ for _ in ()).throw(
			HTTPError(URL, 429, "Too Many", {}, None))
		self.assertEqual(T.send(force=True)["outcome"], "rate-limited")


# ── when it runs ─────────────────────────────────────────────────────────
class TestWhenItRuns(_TelemetryTest):
	def test_a_site_that_has_never_sent_is_due(self):
		self.assertTrue(T._due({}))

	def test_a_recent_attempt_is_not_repeated(self):
		recent = frappe.utils.add_to_date(frappe.utils.now(), hours=-2)
		self.assertFalse(T._due({"last_attempt": recent}))

	def test_weekly_means_one_hour_of_one_weekday(self):
		"""Derived from the Installation ID so a fleet spreads across 168
		hours, and so one install reports at the same time each week."""
		old = frappe.utils.add_to_date(frappe.utils.now(), days=-20)
		hits = []
		start = frappe.utils.get_datetime(frappe.utils.nowdate())
		for hour in range(168):
			when = frappe.utils.add_to_date(start, hours=hour)
			if T._due({"last_attempt": old}, now=when):
				hits.append(hour)
		self.assertEqual(len(hits), 1, f"due in hours {hits}, expected one")

	def test_an_unreadable_timestamp_does_not_wedge_it_shut(self):
		for bad in ("not a date", "", 0, None, []):
			with self.subTest(value=bad):
				self.assertTrue(
					T._due({"last_attempt": bad})
					or any(T._due({"last_attempt": bad},
					              now=frappe.utils.add_to_date(
						              frappe.utils.nowdate(), hours=h))
					       for h in range(168)))


# ── it gates nothing ─────────────────────────────────────────────────────
class TestItGatesNothing(_TelemetryTest):
	def test_the_module_contains_no_enforcement(self):
		import inspect

		src = inspect.getsource(T).lower()
		for forbidden in ("frappe.throw", "permissionerror", "disable",
		                  "deactivate", "suspend", "lockout", "raise frappe"):
			self.assertNotIn(forbidden, src,
			                 f"{forbidden!r} appears in telemetry.py - read "
			                 "the header of kamra/entitlement.py")

	def test_nothing_in_the_app_branches_on_telemetry(self):
		"""Telemetry may be configured. It may not be a condition anywhere."""
		import pathlib
		import re

		root = pathlib.Path(T.__file__).parent
		pattern = re.compile(
			r"\b(if|elif|while|assert|and|or|not)\b\s+[^\n]*"
			r"(telemetry\.|T\.enabled|last_sent)\s*\(")
		offenders = []
		for path in root.rglob("*.py"):
			if path.name == "telemetry.py" or "tests" in path.parts:
				continue
			if pattern.search(path.read_text(encoding="utf-8", errors="replace")):
				offenders.append(str(path.relative_to(root)))
		self.assertEqual(offenders, [])

	def test_the_whitelisted_surface_is_three_functions(self):
		"""A new whitelisted function here is a new way for data to leave."""
		import ast
		import inspect

		found = []
		for node in ast.walk(ast.parse(inspect.getsource(T))):
			if not isinstance(node, ast.FunctionDef):
				continue
			if any(isinstance(d, ast.Call)
			       and getattr(d.func, "attr", None) == "whitelist"
			       for d in node.decorator_list):
				found.append(node.name)
		self.assertEqual(sorted(found),
		                 ["give_consent", "preview", "withdraw_consent"])

	def test_nothing_here_is_guest_facing(self):
		import ast
		import inspect

		for node in ast.walk(ast.parse(inspect.getsource(T))):
			if not isinstance(node, ast.FunctionDef):
				continue
			for dec in node.decorator_list:
				if not isinstance(dec, ast.Call):
					continue
				for kw in dec.keywords:
					if kw.arg == "allow_guest":
						self.fail(f"{node.name} is guest-facing")
