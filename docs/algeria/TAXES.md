# Taxes — Algeria

How the Algeria country pack (`kamra/localization/algeria.py`) treats tax, what
it deliberately does not decide, and the two places the current data model
cannot express what Algerian practice needs.

> **This pack asserts no legal position.** Every rate below is a configurable
> default, not advice. Whether a given house's accommodation and its F&B
> outlets fall on the standard rate, the reduced rate, or a mix, changes with
> the finance law, the outlet and the classification of the hotel. **Confirm all
> of it with the operator's own accountant before the first live invoice.**

## TVA

The tax is TVA — *Taxe sur la valeur ajoutée*. The pack labels it `TVA` and
labels the operator's tax registration `NIF`.

| Where | Value |
| --- | --- |
| Standard rate carried as `DEFAULT_TVA` | 19 |
| Reduced rate offered in the dropdown | 9 |
| Rates offered (`tax_rate_options`) | `[9, 19]` |

**No rate is hard-coded into logic.** `calculate_room_tax` reads the Room
Type's `tax_percent`, exactly as the Saudi and UAE packs read theirs;
`DEFAULT_TVA` is only the fallback for a room type nobody has typed a number
on yet. `fnb_tax_rate` reads the property's own room-type rates for the same
reason — the pack only reports what the operator configured.

To change a rate you change data on the Room Type, not code.

## Known limitation 1 — a tax-exempt room cannot be expressed

`tax_rate_options` deliberately does **not** offer `0`, and that is not an
oversight.

`Room Type.tax_percent` is a Frappe `Percent` field whose own description reads
*"Leave blank to use your country's standard rate"*. Frappe stores a blank
`Percent` as `0`, so **`0` and "not configured" are the same value in the
database**. Every country pack therefore reads `0` as "fall back to the
national default":

```python
v = room_type_doc.get("tax_percent") if room_type_doc else None
return Decimal(str(v)) if v else DEFAULT_TVA
```

Offering `0` in the dropdown would put a choice in front of the operator that
the arithmetic silently converts to 19%. An honest short list beats an exempt
option that does not hold.

This is **not an Algeria-specific defect**. The same collapse exists upstream
in `indonesia.py:41`, `malaysia.py:37`, `saudi.py:42`, `thailand.py:38` and
`uae.py:40` — and all of those *do* still offer `0` in their dropdowns.

Fixing it properly means making exemption representable, not changing the
fallback: a `tax_exempt` Check on Room Type, plus a patch, plus teaching the
six packs to honour it. Changing `if v else` to `if v is not None` would be
strictly worse — it would make every unconfigured room type charge 0% instead
of the national rate, across all six countries. **Do not do that.**

Status: documented, not changed. Worth reporting upstream.

## Known limitation 2 — taxe de séjour is a fixed amount, not a percent

What sits beside TVA is not TVA. Algerian municipalities levy a *taxe de
séjour* **per person, per night**, with the amount varying by the
classification of the hotel.

`ROOM_LEVY_LABEL = "Taxe de séjour"` names it correctly for the front desk and
the invoice. The amount model is the problem: `Property.room_levy_percent` is a
**percent of the nightly rate**, computed in two places —
`kamra/pricing.py:299` (the quote) and `kamra/folio.py:349` (the per-night
posting).

A percent does not model a fixed per-person charge. Back-solving a percentage
from a typical rate drifts the moment the rate moves or the occupancy changes.

**Decision taken:** add a fixed per-person-per-night amount to Property
alongside the percent, with a mode switch defaulting to `Percent` so existing
properties are untouched, and teach both calculation sites to honour it. See
`kamra/patches/v36/` and `docs/algeria/IMPLEMENTATION_STATUS.md` for the
delivered state.

The alternative — posting the taxe de séjour as an ordinary folio charge line,
the way `saudi.py` and `uae.py` describe municipality fees — prices it exactly
and needs no schema change, but is manual work at the desk every night.

## Legal identifiers on the invoice

An Algerian invoice is expected to carry four identifiers. Only one has a field
today:

| Identifier | Meaning | Property field |
| --- | --- | --- |
| RC | Registre de Commerce | *none yet* |
| NIF | Numéro d'Identification Fiscale | `gstin` (via `tax_id_label = "NIF"`) |
| NIS | Numéro d'Identification Statistique | *none yet* |
| AI | Article d'Imposition | *none yet* |

`invoice_context` builds the footer from `LEGAL_ID_FIELDS`, reading each field
defensively — a fieldname that does not exist returns `None` and drops out
silently rather than printing blank or raising. **The day a migration adds
`rc_number`, `nis_number` and `ai_number`, they start printing with no further
code change.**

Note that `gstin` now carries a GSTIN, a VAT No., a TRN, an NPWP and a NIF
across six packs. Every pack overrides the *display* label via `tax_id_label`,
but the underlying fieldname still says GSTIN. A rename to something neutral
like `tax_id` would be an upstream improvement.

## No e-invoicing

Algeria has no clearance regime equivalent to Saudi ZATCA for the
`on_invoice_issued` / `on_invoice_cancelled` / `on_pos_bill_paid` seam to call.
The pack implements none of those hooks deliberately: a stub that pretended to
report an invoice somewhere would read like a working integration to the next
person, which is worse than nothing.

## Amounts in words

`kamra/localization/words.py` does not know DZD, so a bill reads
`"DZD Three Thousand Five Hundred Only"` rather than spelling dinars and
centimes. The pack does **not** override the `amount_in_words` hook for this —
the default accessor is plain but correct. Teaching `CURRENCY_WORDS` about
`"DZD": ("Dinars", "Centimes")` is a one-line upstream improvement.

## Payment modes

`payment_modes()` in `kamra/localization/__init__.py` filters a pack's
`PAYMENT_MODES` against `CANONICAL_PAYMENT_MODES = ("Cash", "Card", "UPI",
"Bank Transfer")` — anything else is **silently dropped**.

So the pack declares `["Cash", "Card", "Bank Transfer"]`. **CIB and Edahabia
are card schemes, not payment modes** — they book as `Card`, exactly as
`saudi.py` maps mada, so the till, the ledger and the night audit still
balance. Adding them as their own modes would make them vanish at runtime.
