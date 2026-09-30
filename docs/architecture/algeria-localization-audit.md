# Algeria localization — Phase 0 architecture audit

Audit of the existing Kamra PMS codebase, performed before any Algeria change,
to establish where an Algerian country pack plugs in and — just as important —
where it must **not** touch. Every claim below was read out of the source, not
assumed.

- Branch: `feature/algeria-hospitality-platform`
- Cut from: `develop` @ `7b4b65b`
- Upstream: `https://github.com/Kamra-PMS/kamra-pms.git` (remote `upstream`)
- Origin: `https://github.com/ilyeseia/kamra-pms-algeria.git` (remote `origin`)

## 1. What this codebase actually is

A mature, shipping hotel PMS — not a skeleton. Size, measured over tracked files:

| Surface | Measure |
| --- | --- |
| Python (Frappe app `kamra/`) | 39,589 LOC |
| TypeScript / TSX (`frontend/src/`) | 44,736 LOC |
| DocTypes | 96 |
| React screens | 64 |
| Shared React components | 30 |
| Migration patch sets | `v23` … `v35` (13 versions, tracked in `kamra/patches.txt`) |
| Backend test modules | 11 (`kamra/tests/`) |
| CI workflows | 7 (`.github/workflows/`) |

Stack, from the manifests:

- **Frappe framework `>=16.0.0-dev,<17.0.0`** — declared in `pyproject.toml`
  under `[tool.bench.frappe-dependencies]`. Bench and the Frappe Cloud
  marketplace read that to gate installs.
- **Python `>=3.10`**, linted with **ruff**, line length 110,
  `indent-style = "tab"`, `quote-style = "double"`. Tabs, not spaces — new
  Python must match.
- **React 19.1 + TypeScript 5.8 + Vite 6.3 + Tailwind 4.1**, in `frontend/`.
- Built SPA assets are **committed** to `kamra/public/frontend` so a plain
  `bench get-app` serves the UI with no Node build (see root `package.json`).

## 2. Correction to the program brief: the database is MariaDB

The brief specifies PostgreSQL as the primary database. **This project runs on
MariaDB throughout**, and nothing in it targets Postgres:

- `.github/workflows/ci.yml:43` — service image `mariadb:11.8`
- `.github/workflows/ci.yml:97` — `--mariadb-user-host-login-scope='%'`
- `deploy/install.sh:181` — `-f overrides/compose.mariadb.yaml`
- `deploy/install.sh:305` — `--install-app kamra --no-mariadb-socket`
- `.github/workflows/nightly.yml:179,205` and `release.yml:152` — same override
- `deploy/README.md:59` — "upstream compose files (MariaDB + Redis + noproxy)"

Frappe's PostgreSQL support is second-class relative to MariaDB, and converting
96 DocTypes plus 13 patch sets would invalidate the CI matrix,
`deploy/install.sh`, all three release workflows and every documented install
path — for no Algeria-specific gain.

**Decision: stay on MariaDB.** Database work for this programme is therefore
MariaDB index, query and concurrency work. If a Postgres migration is genuinely
wanted it is a separate programme with its own risk budget, not a line item
inside localization.

## 3. Correction to the program brief: Arabic and RTL already exist

The brief treats Arabic and RTL as work to be built. They are already shipped.

`frontend/src/lib/dir.ts` holds a **language registry**, and its own comment
states the extension contract: *"Add a row + a `locales/<code>.json` to ship
another."* It currently registers `en` (ltr) and `ar` (rtl).

Direction is resolved from that registry — the file explicitly notes it is not
a hard-coded comparison against `"ar"` — and `applyLang()` sets `lang` and
`dir` on `document.documentElement`, so the whole tree flips together.
`setLang()` persists the choice per device and dispatches a `kamra:lang` event
that `useT()` in `frontend/src/lib/i18n.ts` subscribes to.

`frontend/src/i18n/locales/ar.json` is **~81 KB of existing Arabic**, keyed by
English source string. `frontend/src/lib/i18n.ts` falls back to the English key
when a translation is missing, so partial coverage degrades gracefully and
never blanks the UI.

**Therefore the real i18n gap for Algeria is French, not Arabic.** Arabic needs
a coverage review, not construction.

Tooling already present: `frontend/scripts/i18n-extract.mjs` (extracts English
from `t()` / `translate()` call sites into `src/i18n/catalog.csv`, merging
existing Arabic) and `i18n-import.mjs`. Note it skips `PublicBooking.tsx`,
`PublicListing.tsx` and `QrMenu.tsx`.

## 4. The insertion point: the localization seam

This is the single most important finding. `kamra/localization/__init__.py` is
a documented, purpose-built country-pack seam. Its docstring states the design
intent plainly: *"The core PMS never knows about GST, VAT or fiscal printers -
it asks the country pack."*

Existing packs: `generic.py`, `india.py`, `indonesia.py`, `malaysia.py`,
`saudi.py`, `thailand.py`, `uae.py`.

Packs are resolved through the `kamra_localization` hook in `kamra/hooks.py:72`,
ERPNext `regional_overrides` style — a country claims itself by declaring the
hook, and an unknown country falls back to the flat-tax `generic` pack.

### Required pack interface

| Function | Returns |
| --- | --- |
| `calculate_room_tax(property, room_type_doc, nightly_rate)` | `Decimal` |
| `fnb_tax_rate(property)` | `float` |
| `tax_rate_options(property)` | `list[float]` |
| `invoice_context(prop_doc)` | `dict` — labels, service code, place of supply, split, footer |
| `locale(prop_doc)` | `dict` — `currency_symbol`, `locale`, `currency`, `tax_label`, `tax_id_label`, `tax_rates` |

### Optional, each with a safe default in `__init__.py`

`service_code_for` (per-line tax code), `tax_split`, `amount_in_words`, and the
statutory e-invoicing hooks `on_invoice_issued`, `on_invoice_cancelled`,
`on_pos_bill_paid`, `invoice_print_block`.

The e-invoicing hooks are wrapped by `_hook()`, which takes a savepoint and
rolls back on failure so a half-written fiscal record cannot fork the invoice
chain — and deliberately never blocks a checkout: *"the record can be
regenerated, a guest kept waiting at checkout cannot."*

### Module constants a pack declares

`DEFAULT_CURRENCY`, `DEFAULT_TIMEZONE`, `DEFAULT_NATIONALITY`, `ID_TYPES`,
`PAYMENT_MODES`, `PRIVACY_AUTHORITY`, `GUEST_REPORT`, `ROOM_LEVY_LABEL`.

**Constraint that matters for Algeria:** `payment_modes()` filters a pack's
`PAYMENT_MODES` against `CANONICAL_PAYMENT_MODES = ("Cash", "Card", "UPI",
"Bank Transfer")` — anything else is silently dropped. Algerian card schemes
(CIB, Edahabia) must therefore map onto `Card`, exactly as `saudi.py` maps
mada, so the till, ledger and night audit still balance. A pack "chooses what
the desk is offered - never invents a mode the till, ledger and night audit do
not know."

`validate_id_type()` enforces that an ID type is one the property's country
recognises, on new writes only — values already on file are never re-checked.

### Consumers of the seam

`kamra/api.py` calls into localization at roughly a dozen sites, notably:

- `api.py:4624-4627` — merges `pack.locale(prop)` with
  `front_desk_vocabulary(pack)` into one payload that drives the frontend's
  money formatting and tax dropdowns
- `api.py:4668-4673` — `localization_countries()` exposes
  `supported_countries()`, which the setup wizard and Settings render

Consequence: **registering an Algeria pack makes Algeria appear in the setup
wizard and drives frontend currency/tax formatting with no frontend change.**

## 5. Property model — what exists, what Algeria still needs

`kamra/kamra/doctype/property/property.json` carries 82 fields. Relevant ones:

- Identity: `property_name`, `legal_name`, `property_kind`, `country`, `state`,
  `city`, `timezone`, `locale`, `currency` (Link → Currency)
- Tax: `gstin`, `gst_mode`, `gst_slab_threshold`, `gst_rate_low`,
  `gst_rate_high`, `rates_include_tax`
- Levy beside tax: `room_levy_label`, `room_levy_percent`, `room_levy_taxable`
- Privacy: `id_retention`, `guest_retention_months`, `privacy_contact`
- Classification: `star_category`

Two concrete gaps for Algeria:

1. **Legal identifiers.** An Algerian invoice carries RC (Registre de
   Commerce), NIF (Numéro d'Identification Fiscale), NIS (Numéro
   d'Identification Statistique) and AI (Article d'Imposition). The only tax-id
   field is `gstin`, which is India-shaped. NIF can ride on `gstin` via
   `tax_id_label = "NIF"` as an interim measure; **RC / NIS / AI need dedicated
   Property fields**, which is a DocType change plus a patch under
   `kamra/patches/v36/` — coordinated, not done inside the pack.
2. **Taxe de séjour is a fixed amount, not a percent.** Algerian
   municipalities levy tourist tax per person per night, varying by hotel
   classification. `room_levy_percent` is a **Percent** field and cannot model
   that faithfully.

   **Resolved on this branch** (this paragraph originally recorded it as an
   open decision): Property now carries `room_levy_mode` — a Select whose
   default is `Percent`, so no existing property changed behaviour — plus
   `room_levy_amount` (Currency, per person per night). Both calculation
   sites honour it: `kamra/pricing.py` (the quote) and
   `kamra/folio.py:_post_room_levy` (the per-night posting). Patch
   `kamra/patches/v36/backfill_room_levy_mode.py` pins existing rows to
   `Percent`. The levy bills **adults only**; a children policy is an
   explicit open operator decision, not a guessed default.

## 6. Authorization and multi-property — already in place

`kamra/authz.py` is a purpose-built endpoint authorization layer, and its
docstring names the exact threat it exists for: *"Frappe checks doctype
permissions on ORM paths, but raw-SQL reads and `db.set_value` writes sail past
them."* Every whitelisted endpoint declares who may call it and which
properties it may touch.

- `ADMIN = ("System Manager", "Administrator", "Hotel Admin")`
- `IT_ADMIN = ("System Manager", "Administrator")` — deliberately **excludes**
  the Hotel Admin business role, for user management, developer settings and
  API keys
- `SCOPED_ARGS` maps an endpoint argument name to the DocType(s) it names, each
  carrying a `property` link, so the guard can tell which hotel a call reaches
- Cashier PIN brute-force controls: `PIN_MAX_ATTEMPTS = 5`,
  `PIN_LOCK_MINUTES = 15`

**Multi-property is therefore not new work** — property-scoped permissions
already exist. The brief's §28 hotel-group requirement should be validated
against this layer before anything is added.

## 7. MCP / AI surface — already exists, and is already gated

- `kamra/mcp_http.py`, `kamra/mcp_oauth.py`, `kamra/mcp_tools.py`,
  `mcp/kamra_mcp.py`
- DocTypes `MCP OAuth Client`, `MCP OAuth Grant`, `Agent Action Log`,
  `AI Assistant Settings`, `Copilot Conversation`
- `kamra/agents_api.py`, `kamra/assistant.py`, `kamra/llm_compat.py`
- Tests: `kamra/tests/test_mcp.py`, `test_mcp_registry.py`, `test_llm_compat.py`

The brief's §20 requirement that AI never reach the database directly appears
to be satisfied by construction — tools go through whitelisted endpoints and
`authz.py`, and `Agent Action Log` exists for audit. **This needs verification,
not reconstruction.**

## 8. Finance surface already present

`Folio`, `Folio Charge`, `Folio Ledger Entry`, `Folio Payment`,
`Proforma Folio`, `Folio Reprint`, `Credit Note`, `Cancelled Invoice`,
`City Ledger Account`, `City Ledger Entry`, `Cashier`, `Cashier Session`,
`Cashier Transaction`, `Cashier PIN`, `Petty Cash Voucher`, `Exchange Rate`,
`Exchange Transaction`, `Night Audit Run`, `Security Deposit`,
`Discount Voucher`, `Revenue Budget`, `Hurdle Rate`, `Rate Plan`,
`Rate Guardrail`, `Season`, `Company Billing Rule`.

Multi-currency (`Exchange Rate`, `Exchange Transaction`) and night audit
(`Night Audit Run`, `kamra/business_date.py`) already exist. DZD support is a
currency + pack concern, **not** a finance-module rewrite.

## 9. Scope reassessment

Measured against the code, large parts of the brief's 19-agent / 8-phase plan
describe features this PMS already has: POS (`pos_*` DocTypes, `kamra/pos.py`),
housekeeping (`Housekeeping Task`, `kamra/housekeeping.py`), laundry, banquet
(15 DocTypes), inventory (`Ingredient`, `Ingredient Stock`,
`kamra/inventory.py`), channel manager (`Channel Manager Connection`,
`kamra/channel_manager.py`), booking engine (`kamra/public_api.py`,
`booking_slugs.py`, public screens), WhatsApp (`kamra/whatsapp.py`), deposits,
GRC and group bookings.

**The genuine Algeria delta is narrower and sharper than the brief implies:**

| # | Work | Depends on |
| --- | --- | --- |
| A1 | `kamra/localization/algeria.py` + `hooks.py` registration | — |
| A2 | French locale (`fr`) in the language registry + `fr.json` | — |
| A3 | DZD currency record + seeding | A1 |
| A4 | Property fields for RC / NIS / AI + patch `v37` (`v36` is now the levy) | A1, schema coordination |
| A5 | ~~Taxe de séjour amount model decision~~ — **done**, see §5 | A4 |
| A6 | Backend tests for the Algeria pack | A1 |
| A7 | Trilingual GRC / invoice print (ar / fr / en) layout verification | A1, A2 |
| A8 | Arabic coverage review against the current `catalog.csv` | A2 |
| A9 | `docs/algeria/` | all |

Everything else in the brief is either already built, or is generic PMS
hardening unrelated to Algerian localization. Treating it as Algeria work would
add risk to a shipping product without adding Algerian capability.

## 10. Standing constraints for every agent on this branch

- **Tabs** in Python; ruff line length 110; double quotes. Match the existing
  prose-style docstrings — this codebase explains *why*, not *what*.
- **Never assert an Algerian tax rate as legal fact.** Rates are configurable,
  defaults are documented as defaults, and assumptions are written down where a
  reader will find them.
- Do not edit `kamra/public/frontend` by hand — it is build output.
- Schema changes require a patch under `kamra/patches/vNN/` and a line in
  `kamra/patches.txt`. Never an undocumented migration.
- Preserve AGPL-3.0 and upstream Kamra PMS attribution (`license.txt`,
  `README.md`).
- `upstream` is never blind-merged; divergence is documented.
