# Copyright (c) 2026 Ilyes Keskas (Algeria)
# Part of the ZIRI PMS Algeria distribution of Kamra PMS.
# SPDX-License-Identifier: AGPL-3.0-or-later
# See NOTICE for the upstream authorship this builds on.
"""Algeria localization pack.

Algerian supplies carry TVA - Taxe sur la valeur ajoutée - and the bill a
hotel hands a guest is a French-facing document in most houses, so this
pack labels the tax "TVA" and the operator's tax registration "NIF".

On the rates, read this carefully: THIS PACK ASSERTS NO LEGAL POSITION.
The numbers below are configurable defaults, not advice. 19 is carried as
DEFAULT_TVA because it is Algeria's standard TVA rate and 9 appears in
tax_rate_options because it is the known reduced rate - but whether a
given house's accommodation and its F&B outlets fall on the standard rate,
the reduced rate, or a mix of the two is a question for the operator's own
accountant, and it changes with the finance law, the outlet and the
classification of the hotel. So nothing here is hard-coded as fact:

  - the TVA rate comes from the Room Type's tax percent, exactly as the
    Saudi and UAE packs read theirs; DEFAULT_TVA is only the fallback for
    a room type nobody has typed a number on yet
  - F&B follows the property's own room-type rates for the same reason - a
    restaurant on a different rate is set on the room types, or the number
    is overridden where the POS asks for it
  - confirm all of it with the accountant before the first live invoice

What sits beside TVA is not TVA. Algerian municipalities levy a taxe de
séjour per person per night, the amount varying with the classification of
the hotel - so ROOM_LEVY_LABEL names it correctly for the front desk and
the invoice.

A percent cannot model that, so the Property doctype carries two bases and
the operator picks one: set `room_levy_mode` to "Fixed per person per
night" and fill `room_levy_amount`, which is what an Algerian house wants.
The older `room_levy_percent` is still there and still the default, so no
existing property changed behaviour when the fixed basis landed. Both
bases are computed in two places that must agree to the cent - the quote
in kamra/pricing.py and the per-night posting in kamra/folio.py - because
a guest who accepted one number must not be handed another.

Children are not counted: the levy bills adults only. Whether a child owes
it is an operator policy call, and several Algerian municipalities do treat
them differently, so it is left as an explicit decision rather than a
guessed default.

Legal identifiers are the other place this pack is deliberately
incomplete. An Algerian invoice is expected to carry the RC (Registre de
Commerce), the NIF (Numéro d'Identification Fiscale), the NIS (Numéro
d'Identification Statistique) and the AI (Article d'Imposition). The
Property doctype today has exactly one tax-identifier field, `gstin`, so
the NIF rides on it via tax_id_label = "NIF" and the rest have nowhere to
live. RC, NIS and AI need dedicated Property fields in a follow-up
migration; invoice_context reads them defensively so that the day those
fields land they simply start printing, and until then their absence is
silent rather than an error.

No e-invoicing hooks. Algeria has no clearance regime equivalent to
Saudi ZATCA for this seam to call, and a stub that pretended to report an
invoice somewhere would be worse than nothing - it would read like a
working integration to the next person. Amounts in words also stay on the
default accessor in localization/__init__.py: words.py now knows DZD, so a
bill reads "Dinars Three Thousand Five Hundred Only" with centimes where
there are any. No reason for this pack to override the hook.
"""

from decimal import Decimal

import frappe

# Algeria's standard TVA rate, used only where nobody has set a rate yet.
# Configurable, not asserted - see the module docstring.
DEFAULT_TVA = Decimal("19")

DEFAULT_CURRENCY = "DZD"
DEFAULT_TIMEZONE = "Africa/Algiers"
# the municipal taxe de séjour - bill it on Property.room_levy_mode
# "Fixed per person per night" with room_levy_amount, not on the percent
ROOM_LEVY_LABEL = "Taxe de séjour"
DEFAULT_NATIONALITY = "Algerian"
# named in the guest privacy notice (Law 18-07 on the protection of natural
# persons in the processing of personal data)
PRIVACY_AUTHORITY = "the Autorité nationale de protection des données à caractère personnel (ANPDP)"
GUEST_REPORT = "guest registration with the police (the hotel guest register / fiche de police)"
# what the front desk records at check-in: the Carte Nationale d'Identité,
# a passport for visitors, a residence permit for foreign residents
ID_TYPES = ["National ID", "Passport", "Driving License", "Residence Permit", "Other"]
# CIB and Edahabia are card schemes, not payment modes - they book as Card
# so the till, the ledger and the night audit still balance
PAYMENT_MODES = ["Cash", "Card", "Bank Transfer"]

# Invoice identifiers and the Property field each reads from today. NIF
# shares `gstin` with the rest of the world's tax-id field; the other three
# have no field yet, and .get() on a missing fieldname is simply None.
LEGAL_ID_FIELDS = (
	("RC", "rc_number"),
	("NIF", "gstin"),
	("NIS", "nis_number"),
	("AI", "ai_number"),
)


def calculate_room_tax(property, room_type_doc, nightly_rate) -> Decimal:
	"""Flat TVA - the room type's tax percent IS the rate that applies to
	this room. Unset falls back to the standard 19%."""
	v = room_type_doc.get("tax_percent") if room_type_doc else None
	return Decimal(str(v)) if v else DEFAULT_TVA


def fnb_tax_rate(property) -> float:
	"""Hotel F&B follows the property's own configured rate. Whether the
	restaurant genuinely sits on the same rate as the rooms is the
	operator's call - this only reads what they set."""
	rates = frappe.get_all(
		"Room Type", filters={"property": property, "disabled": 0},
		pluck="tax_percent", limit=5)
	first = next((r for r in rates if r), None)
	return float(first) if first else float(DEFAULT_TVA)


def tax_rate_options(property) -> list:
	"""The rates an Algerian operator picks between - the reduced rate and
	the standard rate. Offered, not prescribed.

	Zero is deliberately absent, and that is not an oversight: Room Type's
	tax_percent cannot express it. The field's own description reads "Leave
	blank to use your country's standard rate", and Frappe stores a blank
	Percent as 0 - so 0 and "not configured" are the same value in the
	database, and calculate_room_tax below reads 0 as "fall back to
	DEFAULT_TVA". Offering 0 in this list would put a choice in the dropdown
	that the arithmetic silently turns into 19%. Better an honest short list
	than an exempt option that does not hold. A genuinely exempt room needs a
	tax_exempt flag on Room Type - see docs/algeria/TAXES.md."""
	return [9, 19]


def _legal_ids(prop_doc) -> str:
	"""The legal identifiers actually on file, as an invoice footer reads
	them. Fields that do not exist yet drop out rather than print blank."""
	parts = [f"{label}: {prop_doc.get(field)}"
	         for label, field in LEGAL_ID_FIELDS if prop_doc.get(field)]
	return " · ".join(parts)


def invoice_context(prop_doc) -> dict:
	footer = ("Facture - la taxe de séjour figure sur une ligne distincte le "
	          "cas échéant. / Tourist tax appears as a separate line where "
	          "applicable. This is a computer-generated invoice.")
	ids = _legal_ids(prop_doc)
	if ids:
		footer = f"{ids}. {footer}"
	return {
		"tax_label": "TVA",
		"tax_id_label": "NIF",
		"service_code": None,
		"sac": None,
		"place_of_supply": prop_doc.get("city") or prop_doc.get("state"),
		# national TVA, single line - no centre/region split
		"split": [("tva", Decimal("1"))],
		"footer": footer,
	}


def locale(prop_doc) -> dict:
	currency = prop_doc.get("currency") or DEFAULT_CURRENCY
	# An Algerian bill is written in DA, so that is what the desk sees.
	#
	# For DZD the pack decides and does NOT defer to the Currency master.
	# That reads backwards until you check a real site: Frappe ships DZD with
	# the symbol already set to د.ج, so deferring meant the master always won
	# and DA never appeared once. The master's value there is stock framework
	# data, not something an operator chose, and this product standardises on
	# DA - so the pack overrides it. An operator who genuinely wants د.ج
	# changes it here, which is a visible decision rather than a silent one.
	#
	# Every other currency still prefers the master: those symbols ARE the
	# right answer, and a pack has no business second-guessing them.
	#
	# The trailing space is deliberate - fmtMoney prefixes the symbol, so
	# "DA 1 500" needs it.
	if currency == "DZD":
		symbol = "DA "
	else:
		symbol = frappe.db.get_value("Currency", currency, "symbol") or f"{currency} "
	return {
		"currency_symbol": symbol,
		# the invoice and the front desk speak French in most houses
		"locale": "fr-DZ",
		"currency": currency,
		"tax_label": "TVA",
		"tax_id_label": "NIF",
		"tax_rates": tax_rate_options(prop_doc.name),
	}
