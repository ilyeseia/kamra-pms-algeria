# Copyright (c) 2026 Ilyes Keskas (Algeria)
# Part of the ZIRI PMS Algeria distribution of Kamra PMS.
# SPDX-License-Identifier: AGPL-3.0-or-later
# See NOTICE for the upstream authorship this builds on.
import frappe
from frappe.model.document import Document


class SupportAccessGrant(Document):
	def validate(self):
		# Enforced on the document, not only in the API that creates it, so a
		# grant written from the Desk or a script obeys the same rule.
		if self.user == self.approved_by:
			frappe.throw("A technician cannot authorise their own access.",
			             frappe.PermissionError)
		if self.expires_after and self.granted_at \
				and self.expires_after <= self.granted_at:
			frappe.throw("A grant that expires before it starts is not a grant.")
