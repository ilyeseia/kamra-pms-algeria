# Copyright (c) 2026 Ilyes Keskas (Algeria)
# Part of the ZIRI PMS Algeria distribution of Kamra PMS.
# SPDX-License-Identifier: AGPL-3.0-or-later
# See NOTICE for the upstream authorship this builds on.
"""Temporary support access: who can open the door, and that it shuts itself.

The assertion this file exists for is the last one: a grant that has expired
authorises nothing EVEN IF the Support role is still attached to the user.
That is the difference between a support door and a backdoor, and it is the
reason enforcement reads the grant rather than trusting the role.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from kamra import support_access as S

TECH = "ziri-support-test@example.com"
BOSS = "ziri-admin-test@example.com"


def _user(email: str, roles: list[str]) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc({
			"doctype": "User", "email": email, "first_name": email.split("@")[0],
			"enabled": 1, "user_type": "System User", "send_welcome_email": 0,
			"roles": [{"role": r} for r in roles],
		}).insert(ignore_permissions=True)
	return email


class TestSupportAccess(IntegrationTestCase):
	def setUp(self):
		for role in (S.SUPPORT_ROLE, S.READ_ONLY_ROLE, "Hotel Admin"):
			if not frappe.db.exists("Role", role):
				frappe.get_doc({"doctype": "Role", "role_name": role,
				                "desk_access": 0}).insert(ignore_permissions=True)
		_user(TECH, [])
		_user(BOSS, ["Hotel Admin"])

	def tearDown(self):
		frappe.db.rollback()

	def _grant(self, hours=4, scope="diagnostics", revoked=0, user=TECH):
		"""Create a grant. `hours` may be negative, meaning already expired.

		An expired one is created VALID and then aged with db.set_value,
		because SupportAccessGrant.validate refuses a grant that expires
		before it starts - correctly, and that rule has its own test. The
		state being set up here is not "somebody created a bad grant", it is
		"time passed", and time passing does not re-run validation.
		"""
		doc = frappe.get_doc({
			"doctype": "Support Access Grant", "user": user, "scope": scope,
			"reason": "a reason long enough to mean something later",
			"approved_by": BOSS, "granted_at": now_datetime(),
			"expires_after": add_to_date(now_datetime(), hours=max(hours, 1)),
			"revoked": revoked,
		}).insert(ignore_permissions=True)
		if hours < 0:
			frappe.db.set_value(
				"Support Access Grant", doc.name, "expires_after",
				add_to_date(now_datetime(), hours=hours),
				update_modified=False)
			doc.reload()
		return doc

	# ── the gate is the grant, not the role ──────────────────────────────
	def test_an_expired_grant_authorises_nothing(self):
		"""THE test. A scheduled revoke that never runs leaves the Support
		role attached; if the role were the gate, that would be permanent
		access nobody can see. It is not the gate."""
		self._grant(hours=-1)
		S._attach_role(TECH)          # exactly what a failed tidy-up leaves
		self.assertIsNone(S.active_grant(TECH))
		self.assertFalse(S.has_scope("diagnostics", TECH))

	def test_a_revoked_grant_authorises_nothing_immediately(self):
		g = self._grant()
		self.assertTrue(S.has_scope("diagnostics", TECH))
		g.revoked = 1
		g.save(ignore_permissions=True)
		self.assertFalse(S.has_scope("diagnostics", TECH))

	def test_a_live_grant_does_authorise(self):
		"""The positive control, without which the two above could pass
		because access never works at all."""
		self._grant()
		self.assertIsNotNone(S.active_grant(TECH))
		self.assertTrue(S.has_scope("diagnostics", TECH))

	def test_a_user_with_no_grant_has_nothing(self):
		self.assertIsNone(S.active_grant(TECH))
		self.assertFalse(S.has_scope("diagnostics", TECH))

	# ── scope is ordered, and narrow by default ──────────────────────────
	def test_scope_is_a_floor_not_an_equality(self):
		self._grant(scope="full")
		self.assertTrue(S.has_scope("diagnostics", TECH))
		self.assertTrue(S.has_scope("read_only", TECH))
		self.assertTrue(S.has_scope("full", TECH))

	def test_a_narrow_scope_does_not_reach_a_wide_one(self):
		self._grant(scope="diagnostics")
		self.assertTrue(S.has_scope("diagnostics", TECH))
		self.assertFalse(S.has_scope("read_only", TECH))
		self.assertFalse(S.has_scope("full", TECH))

	def test_an_unknown_scope_on_a_grant_fails_closed(self):
		"""A row edited by hand, or written by an older version."""
		g = self._grant()
		frappe.db.set_value("Support Access Grant", g.name, "scope",
		                    "superuser", update_modified=False)
		self.assertFalse(S.has_scope("diagnostics", TECH))

	def test_asking_for_an_unknown_scope_is_a_programming_error(self):
		self._grant(scope="full")
		with self.assertRaises(ValueError):
			S.has_scope("root", TECH)

	# ── who may open the door ────────────────────────────────────────────
	def test_a_technician_cannot_authorise_themselves(self):
		"""The property that makes this an authorisation and not a login."""
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({
				"doctype": "Support Access Grant", "user": TECH,
				"scope": "full", "reason": "I would like full access please",
				"approved_by": TECH, "granted_at": now_datetime(),
				"expires_after": add_to_date(now_datetime(), hours=4),
			}).insert(ignore_permissions=True)

	def test_a_grant_that_expires_before_it_starts_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({
				"doctype": "Support Access Grant", "user": TECH,
				"scope": "diagnostics", "reason": "a reason long enough here",
				"approved_by": BOSS, "granted_at": now_datetime(),
				"expires_after": add_to_date(now_datetime(), hours=-1),
			}).insert(ignore_permissions=True)

	# ── Administrator is not a support session ───────────────────────────
	def test_administrator_never_holds_a_support_grant(self):
		"""It already has every permission. A grant on it would make the
		audit trail claim a technician was authorised when what happened is
		somebody used the admin account."""
		self.assertIsNone(S.active_grant("Administrator"))
		self.assertIsNone(S.active_grant("Guest"))

	# ── the roles exist and are not handed out ───────────────────────────
	def test_both_roles_are_shipped(self):
		from kamra.scripts.provision import ROLES

		self.assertIn(S.SUPPORT_ROLE, ROLES)
		self.assertIn(S.READ_ONLY_ROLE, ROLES)

	def test_neither_role_is_provisioned_to_a_module(self):
		"""They are granted, never assigned. A property that gets Support
		automatically would be a standing open door."""
		from kamra.scripts.provision import MODULE_ROLES

		for roles in MODULE_ROLES.values():
			self.assertNotIn(S.SUPPORT_ROLE, roles)
			self.assertNotIn(S.READ_ONLY_ROLE, roles)

	def test_a_support_session_is_never_system_manager(self):
		import io
		import pathlib

		src = pathlib.Path(frappe.get_app_path("kamra", "support_access.py"))
		body = io.open(src, encoding="utf-8").read()
		attach = body.split("def _attach_role", 1)[1].split("def ", 1)[0]
		self.assertNotIn("System Manager", attach)

	# ── the tidy-up is housekeeping, not the gate ────────────────────────
	def test_expire_grants_detaches_but_is_not_what_protects(self):
		self._grant(hours=-1)
		S._attach_role(TECH)
		out = S.expire_grants()
		self.assertTrue(out.get("ok"))
		# and the thing that actually mattered was already true
		self.assertFalse(S.has_scope("diagnostics", TECH))

	def test_expire_grants_leaves_a_live_session_alone(self):
		self._grant(hours=4)
		S._attach_role(TECH)
		S.expire_grants()
		self.assertTrue(S.has_scope("diagnostics", TECH))
