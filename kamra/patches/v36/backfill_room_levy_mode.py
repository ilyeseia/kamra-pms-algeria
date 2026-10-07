# Copyright (c) 2026 Ilyes Keskas (Algeria)
# Part of the ZIRI PMS Algeria distribution of Kamra PMS.
# SPDX-License-Identifier: AGPL-3.0-or-later
# See NOTICE for the upstream authorship this builds on.
import frappe


def execute():
	"""Property grew a levy basis switch (Percent vs a flat amount per person
	per night, for Algeria's taxe de sejour). Every property that existed
	before the switch was charging a percent, so pin them all to Percent -
	an upgrade must not quietly change anyone's money.

	Idempotent: it only writes rows whose basis is still blank, so re-running
	migrate cannot overwrite an operator who has since switched to Fixed."""
	if frappe.db.has_column("Property", "room_levy_mode"):
		frappe.db.sql(
			"""
			UPDATE `tabProperty`
			SET room_levy_mode = 'Percent'
			WHERE IFNULL(room_levy_mode, '') = ''
			"""
		)
	# the new amount column starts life as NULL on existing rows; 0 says
	# "no fixed levy configured" in reports as plainly as it does in code
	if frappe.db.has_column("Property", "room_levy_amount"):
		frappe.db.sql(
			"""
			UPDATE `tabProperty`
			SET room_levy_amount = 0
			WHERE room_levy_amount IS NULL
			"""
		)
	frappe.clear_cache(doctype="Property")
