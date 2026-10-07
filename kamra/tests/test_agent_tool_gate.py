"""Which tools ZIRI Agent may see and call, and why some of them disappear.

The agent describes its tools to the model on every round of a conversation.
Two things decide which: the signed-in user's roles, which was always checked,
and the property's own module configuration, which was not - so a guesthouse
that switched Events off in Settings still had all fifteen banquet tools
offered, and the hotelier paid for schema describing a module their own UI
hides.

WHY EVERY ASSERTION HERE IS A DIFFERENCE

These tests are about the MODULE gate, and the role gate runs beside it. An
earlier version compared tool counts against len(TOOLS) and failed in CI,
because whichever roles the test user holds legitimately remove some tools
before the module gate is even consulted. Comparing against a baseline taken
in the same session isolates the one dimension under test and is correct
whatever roles the runner happens to have.

The direction the gate fails in matters more than the saving. A gate that
hides a tool a hotel needs is worse than one that leaves an extra tool
visible, so every uncertain case must resolve to "allowed".
"""

import frappe
from frappe.tests import IntegrationTestCase

from kamra import assistant as A
from kamra.api import ALL_MODULES
from kamra.tests.fixtures import PROPERTY, build


class TestAgentToolGate(IntegrationTestCase):
	def setUp(self):
		# Per test, not setUpClass: tearDown rolls back, and a rollback that
		# removed the fixture property would leave every later test in the
		# class running against nothing while still passing some of its
		# assertions. fixtures._upsert is built to be called repeatedly -
		# "restoring matters more than creating" - so this is what it is for.
		build()

	def _names(self, property=None):
		return {d["function"]["name"] for d in A._tool_defs(property)}

	def _set_modules(self, modules):
		frappe.db.set_value("Property", PROPERTY, "enabled_modules",
		                    ",".join(modules), update_modified=False)
		frappe.clear_cache()

	def _baseline(self):
		"""Every tool this user may see when no module is switched off."""
		self._set_modules(ALL_MODULES)
		return self._names(PROPERTY)

	def _roles_for(self, tool):
		"""Roles that satisfy this tool's own gate, so a module assertion is
		never decided by the role one."""
		fn = A._resolve(A.TOOLS[tool][0])
		allowed = getattr(fn, "_kamra_roles", None)
		return set(allowed) if allowed else set(frappe.get_roles())

	def tearDown(self):
		frappe.db.rollback()
		frappe.clear_cache()

	# ── the gate does something ──────────────────────────────────────────
	def test_every_module_on_changes_nothing(self):
		"""The common case must be a no-op: a property running everything sees
		exactly what it sees with no module filtering at all."""
		unfiltered = self._names(None)
		self._set_modules(ALL_MODULES)
		self.assertEqual(self._names(PROPERTY), unfiltered)

	def test_events_off_removes_exactly_the_banquet_tools(self):
		baseline = self._baseline()
		self._set_modules([m for m in ALL_MODULES if m != "events"])
		removed = baseline - self._names(PROPERTY)
		self.assertTrue(removed, "events off removed no tools at all")
		self.assertEqual(
			removed, {n for n in baseline if n.startswith("banquet_")},
			"events off removed something other than the banquet tools")

	def test_housekeeping_off_removes_only_its_own(self):
		baseline = self._baseline()
		self._set_modules([m for m in ALL_MODULES if m != "housekeeping"])
		removed = baseline - self._names(PROPERTY)
		self.assertEqual(
			removed,
			baseline & set(A._TOOL_MODULE["housekeeping"]),
			"housekeeping off removed something other than its own tools")

	# ── the direction it fails in ────────────────────────────────────────
	def test_empty_setting_means_every_module(self):
		"""An empty enabled_modules means "all of them" everywhere else in the
		product (kamra.api.enabled_modules), and it has to mean that here too -
		otherwise upgrading a property that never opened Settings would
		silently strip its agent down."""
		baseline = self._baseline()
		self._set_modules([])
		self.assertEqual(self._names(PROPERTY), baseline)

	def test_unknown_property_hides_nothing(self):
		"""The question this gate answers is "may I HIDE this tool". When the
		configuration cannot be read the answer must be no."""
		self.assertEqual(self._names("NO-SUCH-PROPERTY"), self._names(None))

	def test_no_property_hides_nothing(self):
		baseline = self._baseline()
		self.assertEqual(self._names(None), baseline)

	# ── hiding is not enforcing ──────────────────────────────────────────
	def test_disabled_module_is_refused_by_the_gate_itself(self):
		"""Checked on _tool_allowed with roles that satisfy the tool, so this
		cannot pass because of the role gate."""
		roles = self._roles_for("banquet_sheet")
		on = set(ALL_MODULES)
		off = on - {"events"}
		self.assertTrue(A._tool_allowed("banquet_sheet", roles, on),
		                "the gate refused a tool whose module is enabled")
		self.assertFalse(A._tool_allowed("banquet_sheet", roles, off),
		                 "the gate allowed a tool whose module is off")

	def test_run_tool_refuses_a_disabled_module(self):
		"""Leaving a tool out of the schema is presentation. A model that
		invents a tool name, or a conversation replayed with an older tool
		list, still reaches _run_tool - so the gate is checked there too."""
		self._set_modules([m for m in ALL_MODULES if m != "events"])
		with self.assertRaises(frappe.PermissionError):
			A._run_tool("banquet_sheet", {}, PROPERTY)

	# ── the mapping itself ───────────────────────────────────────────────
	def test_every_mapped_tool_exists(self):
		"""_TOOL_MODULE is written by hand. A typo there would silently stop
		gating a tool, and nothing else would notice."""
		for module, names in A._TOOL_MODULE.items():
			self.assertIn(module, ALL_MODULES,
			              f"{module} is not a real module")
			for n in names:
				self.assertIn(n, A.TOOLS, f"{n} is mapped but is not a tool")

	def test_mapping_is_not_silently_empty(self):
		"""Events is the mapping that pays for itself. If the banquet tools
		were ever renamed out from under the startswith() that collects them,
		every assertion above would still pass against an empty set."""
		self.assertGreaterEqual(len(A._TOOL_MODULE["events"]), 10)
