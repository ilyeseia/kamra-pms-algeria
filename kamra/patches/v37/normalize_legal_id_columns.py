import frappe


def execute():
	"""Property grew three more legal-identifier columns - rc_number,
	nis_number and ai_number - so an Algerian invoice can print the RC, the
	NIS and the AI beside the NIF that already rides on `gstin`.

	Nothing here can be backfilled: an operator's Registre de Commerce number
	is not derivable from anything already on file, and guessing one would put
	a wrong identifier on a legal document. So this patch only normalises the
	columns Frappe just added, which arrive NULL on every pre-existing row.

	That matters for raw SQL and reports, not for the Python path:
	localization/algeria.py drops a falsy identifier either way, so the footer
	is already correct. But `WHERE rc_number = ''` and CONCAT over a NULL both
	behave surprisingly in MariaDB, and "" says "not configured" as plainly in
	a report as it does in code. Same reasoning as v36 did for
	room_levy_amount.

	Idempotent: it writes only rows that are still NULL, so re-running migrate
	cannot overwrite an identifier an operator has since typed. Guarded by
	has_column so it is a no-op on a site whose schema has not synced yet."""
	for column in ("rc_number", "nis_number", "ai_number"):
		if frappe.db.has_column("Property", column):
			frappe.db.sql(  # nosemgrep: frappe-sql-format-injection -- the column name is a constant from the tuple above, not user input
				f"""
				UPDATE `tabProperty`
				SET `{column}` = ''
				WHERE `{column}` IS NULL
				"""
			)
	frappe.clear_cache(doctype="Property")
