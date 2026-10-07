"""Which tools ZIRI Agent may see and call, and why some of them disappear.

The agent describes its tools to the model on every round of a conversation.
Two things decide which: the signed-in user's roles, which was always checked,
and the property's own module configuration, which was not - so a guesthouse
that switched Events off in Settings still had all fifteen banquet tools
offered, and the hotelier paid for schema describing a module their own UI
hides.

These tests defend the gate's two halves and, more importantly, the direction
it fails in. A gate that hides a tool a hotel needs is worse than one that
leaves an extra tool visible, so every uncertain case must resolve to
"allowed".
"""

import frappe
from frappe.tests import IntegrationTestCase

from kamra import assistant as A
from kamra.api import ALL_MODULES
from kamra.tests.fixtures import PROPERTY, build


class TestAgentToolGate(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		build()
		cls.banquet = [n for n in A.TOOLS if n.startswith("banquet_")]

	def _names(self, property=None):
		return {d["function"]["name"] for d in A._tool_defs(property)}

	def _set_modules(self, modules):
		frappe.db.set_value("Property", PROPERTY, "enabled_modules",
		                    ",".join(modules), update_modified=False)
		frappe.clear_cache()

	def tearDown(self):
		frappe.db.rollback()
		frappe.clear_cache()

	# ── the gate does something ──────────────────────────────────────────
	def test_every_module_on_hides_nothing(self):
		"""The common case must be a no-op. A property that runs everything
		sees exactly what it saw before this gate existed."""
		self._set_modules(ALL_MODULES)
		self.assertEqual(len(self._names(PROPERTY)), len(A.TOOLS))

	def test_events_off_removes_exactly_the_banquet_tools(self):
		self._set_modules([m for m in ALL_MODULES if m != "events"])
		names = self._names(PROPERTY)
		self.assertFalse([n for n in names if n.startswith("banquet_")])
		self.assertEqual(len(names), len(A.TOOLS) - len(self.banquet))
		# and nothing else went with them
		self.assertIn("front_desk_today", names)
		self.assertIn("check_in", names)

	def test_housekeeping_off_removes_only_its_own(self):
		self._set_modules([m for m in ALL_MODULES if m != "housekeeping"])
		names = self._names(PROPERTY)
		self.assertNotIn("hk_queue", names)
		self.assertIn("banquet_sheet", names)
		self.assertEqual(len(names), len(A.TOOLS) - 3)

	# ── the direction it fails in ────────────────────────────────────────
	def test_empty_setting_means_every_module(self):
		"""An empty enabled_modules means "all of them" everywhere else in the
		product (kamra.api.enabled_modules), and it has to mean that here too -
		otherwise upgrading a property that never opened Settings would silently
		strip its agent down to nothing."""
		self._set_modules([])
		self.assertEqual(len(self._names(PROPERTY)), len(A.TOOLS))

	def test_unknown_property_hides_nothing(self):
		"""The question this gate answers is "may I HIDE this tool". When the
		configuration cannot be read the answer must be no."""
		self.assertEqual(len(self._names("NO-SUCH-PROPERTY")), len(A.TOOLS))

	def test_no_property_hides_nothing(self):
		self.assertEqual(len(self._names(None)), len(A.TOOLS))

	# ── hiding is not enforcing ──────────────────────────────────────────
	def test_disabled_module_tool_is_refused_not_merely_hidden(self):
		"""Leaving a tool out of the schema is presentation. A model that
		invents a tool name, or a conversation replayed with an older tool
		list, still reaches _run_tool - so the gate is checked there too."""
		self._set_modules([m for m in ALL_MODULES if m != "events"])
		with self.assertRaises(frappe.PermissionError):
			A._run_tool("banquet_sheet", {}, PROPERTY)

	def test_enabled_module_tool_is_not_refused_by_the_gate(self):
		"""The negative control. If this raised PermissionError too, the test
		above would pass for the wrong reason."""
		self._set_modules(ALL_MODULES)
		try:
			A._run_tool("banquet_sheet", {}, PROPERTY)
		except frappe.PermissionError:
			self.fail("the module gate refused a tool whose module is enabled")
		except Exception:
			# Any other failure is the tool's own business - wrong arguments,
			# missing data. This test is only about the gate.
			pass

	# ── the mapping itself ───────────────────────────────────────────────
	def test_every_mapped_tool_exists(self):
		"""_TOOL_MODULE is written by hand. A typo there would silently stop
		gating a tool, and nothing else would notice."""
		for module, names in A._TOOL_MODULE.items():
			self.assertIn(module, ALL_MODULES,
			              f"{module} is not a real module")
			for n in names:
				self.assertIn(n, A.TOOLS, f"{n} is mapped but is not a tool")
