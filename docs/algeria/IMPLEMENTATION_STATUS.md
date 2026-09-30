# Algeria — implementation status

Single source of truth for what is delivered, what is not, and what was
verified versus merely written. Updated at the end of each phase.

## Position

| | |
| --- | --- |
| Branch | `feature/algeria-hospitality-platform` |
| Cut from | `upstream/develop` @ `7b4b65b` |
| Upstream remote | `upstream` → `https://github.com/Kamra-PMS/kamra-pms.git` |
| Origin remote | `origin` → `https://github.com/ilyeseia/kamra-pms-algeria.git` |
| Commits ahead of `upstream/develop` | 5 |
| Last upstream sync | `7b4b65b` (branch point; no merge performed) |
| Published to `origin` | **Yes** — `feature/algeria-hospitality-platform` @ `ff1d9fe` |
| Pull request | Not opened — see Blockers |

## Phase 0 — Audit · COMPLETE

`docs/architecture/algeria-localization-audit.md`. Measured, not estimated:
39,589 LOC Python, 44,736 LOC TS/TSX, 96 DocTypes, 64 screens, 13 patch sets.

Two premises in the original programme brief were corrected against the
source:

- **PostgreSQL → MariaDB.** `.github/workflows/ci.yml:43` runs `mariadb:11.8`;
  `deploy/install.sh:305` passes `--no-mariadb-socket`; all three release
  workflows use `overrides/compose.mariadb.yaml`. Staying on MariaDB.
- **Arabic/RTL is not new work.** `frontend/src/lib/dir.ts` already carries a
  registry-driven direction system and `ar.json` already held 1240 keys. The
  actual gap was French.

## Phase 1 — Foundation · COMPLETE

### Delivered

| Item | Files |
| --- | --- |
| Algeria country pack | `kamra/localization/algeria.py` (new) |
| Pack registration | `kamra/hooks.py` (+1 line in `kamra_localization`) |
| French UI language | `frontend/src/lib/dir.ts`, `frontend/src/lib/i18n.ts`, `frontend/src/i18n/locales/fr.json` (new) |
| Fixed per-person levy | `kamra/kamra/doctype/property/property.json`, `kamra/pricing.py`, `kamra/folio.py`, `frontend/src/screens/Settings.tsx` |
| Levy migration | `kamra/patches/v36/backfill_room_levy_mode.py` (new), `kamra/patches.txt` |
| Secret hygiene | `.gitignore` (closed `site_config.json`, `*.pem`, `.env.*`, `kamra.env`, `id_rsa*` gaps) |
| Documentation | `docs/architecture/algeria-localization-audit.md`, `docs/algeria/TAXES.md`, this file |

Registering the pack in `hooks.py` is what makes Algeria appear in the setup
wizard and drives the frontend's currency and tax formatting, via
`kamra/api.py:4624-4627` and `:4668-4673` — **no frontend change was needed
for that**.

Pack contents: DZD, `Africa/Algiers`, TVA/NIF labelling, ANPDP as the privacy
authority (Law 18-07), guest registration with the police (fiche de police),
Algerian ID types, `Taxe de séjour` levy label, and CIB/Edahabia mapped onto
`Card` because `payment_modes()` silently drops anything outside
`CANONICAL_PAYMENT_MODES`.

French coverage: **1187 of 1240 keys = 95.73%**. The 53 omissions are
deliberate — acronyms and product names that must not be translated (ADR,
RevPAR, OTA, VIP, KOT, GSTIN…), plus two keys whose placeholders interpolate
an English morpheme (`{ord}` → "st/nd/rd/th", `{ies}` → "y/ies") and so cannot
be translated without rendering broken French. No English-to-English filler
was added; an omitted key falls back to English by design.

### Verification — what was actually run

| Gate | Result |
| --- | --- |
| `ruff check kamra/localization/algeria.py` | **All checks passed** |
| `ruff check kamra/pricing.py kamra/folio.py kamra/patches/v36/` | 2 findings, **both pre-existing at HEAD** (RUF001/RUF002 on `×` and `−` glyphs); zero new |
| `marketplace_install_check.py` | **6/6 PASS** (needs `PYTHONUTF8=1` on Windows) |
| `tsc --noEmit` (frontend) | **exit 0** |
| `property.json` integrity | JSON valid; `field_order` 84 = definitions 84; no orphans, no duplicates |
| `fr.json` integrity | valid JSON; 0 keys absent from `ar.json`; 0 empty values; placeholder sets match on all 1187 keys |
| Quote vs folio levy parity | 13 cases agree to the cent (e.g. 3 nights × 2 adults × 200 DZD → 1200.00 both paths, tax 228.00 both) |
| Secret scan | **0 real secrets** across all 5932 blobs in local object DB (exhaustive, not sampled) |
| `git diff --check` | clean |

### NOT verified — stated plainly

- **No Frappe / bench test was run.** There is no `bench` and no configured
  site on the development machine. The backend test suite (`kamra/tests/`,
  11 modules), `bench migrate`, and patch `v36`'s SQL have **not** been
  executed. Business-logic verification above came from exercising the real
  modules against a stubbed `frappe`, which is weaker than a site test.
- Patch `v36` has been reviewed for syntax, structure and idempotency only.
  **It has never run against a database.**
- No RTL/LTR visual verification of the French or Arabic UI in a browser.
- No semgrep run (`linters.yml` equivalent); semgrep is installed but the
  Frappe rule set was not cloned.
- French legal/privacy paragraphs and two terminology calls (`Housekeeping` →
  "Ménage", `Walk-in` → "Sans réservation") want a native Algerian reviewer.

## Known limitations

1. **Tax-exempt rooms cannot be expressed.** `Room Type.tax_percent` is a
   Frappe `Percent`, blank stores as `0`, and its own description says blank
   means "use your country's standard rate" — so `0` and "unconfigured" are
   the same value. Every pack therefore reads `0` as the national default.
   Algeria's `tax_rate_options` was reduced to `[9, 19]` so the dropdown stops
   offering a choice the arithmetic discards. **Upstream-wide**: the same
   collapse exists in `indonesia.py:41`, `malaysia.py:37`, `saudi.py:42`,
   `thailand.py:38`, `uae.py:40`, and those packs still offer `0`. Proper fix
   is a `tax_exempt` flag on Room Type. Changing `if v else` to
   `if v is not None` would be **worse** — it would zero tax on every
   unconfigured room type in six countries.
2. **Pre-existing Percent-mode discount split.** With a voucher, the quote
   levies on the discount-reduced room net while the folio levies on the full
   night rate (1350 vs 1500 on a worked example). Reproduced against pristine
   `HEAD`, so it predates this branch. Fixed mode is unaffected. Needs an owner
   decision — is a percentage levy discountable? — and both sites must change
   together.
3. **RC / NIS / AI have no Property fields.** Only NIF prints, riding on
   `gstin` via `tax_id_label`. `LEGAL_ID_FIELDS` in the pack already maps
   `rc_number` / `nis_number` / `ai_number`, so they start printing the day a
   migration adds them. Needs `v37` — `v36` is taken by the levy.
4. **Children are not counted in the levy.** Adults only, commented at both
   calculation sites. Several Algerian municipalities exempt or halve
   children; this is an operator policy decision left explicit.
5. **Levy tax rate basis differs subtly between paths**: the quote uses the
   stay's blended room tax rate, the folio uses that night's. Identical unless
   a stay crosses a rate boundary. Pre-existing.
6. **Amounts in words print `"DZD Three Thousand Only"`** — `words.py` has no
   DZD entry. One-line upstream fix (`"DZD": ("Dinars", "Centimes")`).
7. **Fixed levy is treated as tax-exclusive** even on a `rates_include_tax`
   property, because `_post_room_levy` has no notion of inclusivity and adding
   one would split the two paths.
8. **`i18n.ts` statically imports every dictionary**, so `fr.json` adds ~70 KB
   uncompressed to the main bundle for all users. Pre-existing pattern.
9. **`i18n-extract.mjs` only merges `ar.json`** — a future extraction run will
   drop French from `catalog.csv`.
10. **Demo credentials ship in the built bundle.** `Login.tsx` defines
    `DEMO_ACCOUNTS` and `seed_users.py` sets them. Already public upstream and
    gated server-side by `kamra_demo_mode`, so not a new leak — but any
    production site that runs `seed_users.py` hands out known admin passwords.
11. **`gstin` now carries five different countries' tax IDs.** Display label is
    overridden per pack; the fieldname is not.
12. **`marketplace_install_check.py` crashes on Windows** with
    `UnicodeDecodeError` (cp1252) unless `PYTHONUTF8=1` is set. Environment
    bug, works in CI. Worth an upstream fix.

## Technical debt / upstream candidates

- `tax_exempt` on Room Type (limitation 1) — affects six packs.
- Percent-levy discount basis (limitation 2).
- `{ord}` / `{ies}` / `{s}` English-morphology leaks in i18n keys — these block
  every non-English language, not just French. A `plural(n, one, many)` helper
  would retire them.
- `i18n-extract.mjs` should glob `src/i18n/locales/` instead of hard-coding
  `ar.json`.
- Lazy-load locale dictionaries.
- `words.py` DZD entry.
- `marketplace_install_check.py` Windows encoding.
- Rename `gstin` → `tax_id`.
- No secret-scanning pre-commit hook (`gitleaks` / `detect-secrets`).

## Blockers

1. **No pull request could be opened.** `git push` works — git authenticates
   through the OS credential manager — but the `gh` CLI token is invalid
   (`gh auth status` → *"The token in default is invalid."*), so no PR can be
   created from the command line. Either run `gh auth login -h github.com -w`
   or open it in the browser at
   `https://github.com/ilyeseia/kamra-pms-algeria/pull/new/feature/algeria-hospitality-platform`.
2. **Cannot run the backend test suite.** No `bench`, no site. This caps the
   quality gate at static analysis plus stubbed-module arithmetic.
3. **Fork CI will fail until secrets are set.** `nightly.yml`, `release.yml`
   and `vps-doctor.yml` reference `DEPLOY_HOST`, `DEPLOY_USER`,
   `DEPLOY_SSH_KEY` and `GITHUB_TOKEN`, which the new remote will not have.
   Either configure them or disable those workflows on the fork.

## Not started

Phases 2–8 of the original brief. The audit (§9) found that most of what they
describe already exists in this PMS — POS, housekeeping, laundry, banquet,
inventory, channel manager, booking engine, WhatsApp, deposits, GRC, group
bookings, multi-property RBAC and the MCP/AI layer are all shipped upstream.
The remaining genuine Algeria work is:

- `v37`: Property fields for RC / NIS / AI (limitation 3)
- Trilingual GRC / invoice print verification (ar / fr / en layout, RTL)
- Arabic coverage review against a fresh `catalog.csv`
- FR/AR strings for the two new levy settings fields
- Children policy for the levy (limitation 4)
- A native-speaker pass on the French legal/privacy copy
