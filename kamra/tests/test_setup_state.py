# Copyright (c) 2026 Ilyes Keskas (Algeria)
# Part of the ZIRI PMS Algeria distribution of Kamra PMS.
# SPDX-License-Identifier: AGPL-3.0-or-later
# See NOTICE for the upstream authorship this builds on.
"""The first-run wizard's saved progress.

Two things are under test and the second matters more than the first.

The first is that a sitting survives a closed tab, which is the feature.

The second is that nothing secret is ever written to site_config.json on the
way. A resumable form that remembers a password is a password in a config
file, and the wizard is run by whoever is setting up the hotel - which is
exactly when somebody types a credential into a field that was not meant for
one.
"""

import frappe
from frappe.tests import IntegrationTestCase

from kamra import setup_state as S


class TestSetupState(IntegrationTestCase):
	def tearDown(self):
		try:
			S.clear_state()
		except Exception:
			pass
		frappe.db.rollback()

	# ── it remembers ─────────────────────────────────────────────────────
	def test_nothing_saved_starts_at_the_beginning(self):
		S.clear_state()
		out = S.get_state()
		self.assertEqual(out["step"], 0)
		self.assertFalse(out["resumed"])
		self.assertEqual(out["answers"], {})

	def test_a_saved_sitting_comes_back(self):
		S.save_state(step=2, answers={"property_name": "Hotel El Karma",
		                              "city": "Algiers"})
		out = S.get_state()
		self.assertTrue(out["resumed"])
		self.assertEqual(out["step"], 2)
		self.assertEqual(out["answers"]["property_name"], "Hotel El Karma")

	def test_saving_twice_keeps_the_later_one(self):
		S.save_state(step=1, answers={"city": "Oran"})
		S.save_state(step=3, answers={"city": "Constantine"})
		out = S.get_state()
		self.assertEqual(out["step"], 3)
		self.assertEqual(out["answers"]["city"], "Constantine")

	def test_clearing_forgets(self):
		S.save_state(step=2, answers={"city": "Annaba"})
		S.clear_state()
		self.assertFalse(S.get_state()["resumed"])

	def test_a_created_property_is_remembered_once(self):
		"""The point of no return. Once setup_property has run, a resume must
		know a property exists so nothing is tempted to create a second."""
		S.save_state(step=3, answers={}, property="PROP-0001")
		S.save_state(step=4, answers={})          # a later save with no property
		self.assertEqual(S.get_state()["property"], "PROP-0001")

	# ── it never remembers a secret ──────────────────────────────────────
	def test_password_like_answers_are_dropped(self):
		out = S.save_state(step=1, answers={
			"property_name": "Hotel El Karma",
			"admin_password": "hunter2",
			"api_key": "sk-live-whatever",
			"smtp_secret": "x",
			"cashier_pin": "1234",
		})
		self.assertEqual(set(out["dropped"]),
		                 {"admin_password", "api_key", "smtp_secret",
		                  "cashier_pin"})
		answers = S.get_state()["answers"]
		self.assertEqual(answers, {"property_name": "Hotel El Karma"})

	def test_the_dropped_value_never_reaches_site_config(self):
		"""The assertion the module exists for. Checked against the stored
		blob, not against what save_state returned - a filter that reports a
		drop while still writing the value would pass the test above."""
		S.save_state(step=1, answers={"admin_password": "hunter2",
		                              "city": "Setif"})
		raw = str(frappe.conf.get("kamra_setup_state") or "")
		self.assertNotIn("hunter2", raw)
		self.assertIn("Setif", raw)

	def test_the_filter_is_case_insensitive(self):
		out = S.save_state(step=1, answers={"ADMIN_PASSWORD": "x",
		                                    "ApiKey": "y"})
		self.assertEqual(set(out["dropped"]), {"ADMIN_PASSWORD", "ApiKey"})

	def test_a_huge_paste_is_bounded(self):
		"""site_config.json holds the encryption key and the database
		password. A wizard field is not a reason to grow it by a megabyte."""
		S.save_state(step=1, answers={"city": "x" * 50000})
		self.assertLessEqual(len(S.get_state()["answers"]["city"]), 2000)

	# ── it fails softly, between two screens of a form ───────────────────
	def test_a_nonsense_step_does_not_raise(self):
		for bad in ("abc", None, -5, 9999):
			out = S.save_state(step=bad, answers={})
			self.assertTrue(out["ok"])
			self.assertGreaterEqual(out["step"], 0)
			self.assertLessEqual(out["step"], S.MAX_STEP)

	def test_nonsense_answers_do_not_raise(self):
		for bad in (None, "not json", 42, ["a"]):
			self.assertTrue(S.save_state(step=1, answers=bad)["ok"])

	def test_answers_as_a_json_string_are_accepted(self):
		"""The frontend sends JSON.stringify(prop) through frappe.call."""
		S.save_state(step=1, answers='{"city": "Blida"}')
		self.assertEqual(S.get_state()["answers"]["city"], "Blida")

	def test_a_corrupt_stored_state_starts_fresh_rather_than_failing(self):
		"""A hand-edited site_config must not wedge the wizard shut."""
		frappe.conf["kamra_setup_state"] = "{not json at all"
		out = S.get_state()
		self.assertFalse(out["resumed"])
		self.assertEqual(out["step"], 0)

	# ── stale state is offered, not applied ──────────────────────────────
	def test_an_old_sitting_is_flagged_and_not_restored(self):
		S.save_state(step=3, answers={"city": "Tlemcen"})
		stored = frappe.parse_json(frappe.conf["kamra_setup_state"])
		stored["saved_at"] = frappe.utils.add_to_date(
			frappe.utils.now(), days=-(S.STALE_DAYS + 1))
		frappe.conf["kamra_setup_state"] = frappe.as_json(stored)
		out = S.get_state()
		self.assertTrue(out.get("stale"))
		self.assertFalse(out["resumed"])
		self.assertEqual(out["answers"], {})
