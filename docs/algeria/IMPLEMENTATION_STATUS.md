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
| Commits ahead of `upstream/develop` | 9 |
| Last upstream sync | `7b4b65b` (branch point; no merge performed) |
| Published to `origin` | **Yes** — `feature/algeria-hospitality-platform` |
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
| RC / NIS / AI fields | `kamra/kamra/doctype/property/property.json`, `frontend/src/screens/Settings.tsx` |
| Legal-id migration | `kamra/patches/v37/normalize_legal_id_columns.py` (new), `kamra/patches.txt` |
| Secret hygiene | `.gitignore` (closed `site_config.json`, `*.pem`, `.env.*`, `kamra.env`, `id_rsa*` gaps) |
| Secret scanning | `.pre-commit-config.yaml` — gitleaks `v8.30.1` on the staged diff |
| DZD in words | `kamra/localization/words.py` — `("Dinars", "Centimes")` |
| Guest-facing i18n | `PublicBooking.tsx`, `PublicListing.tsx`, `QrMenu.tsx` + both locales |
| Algiers time zone | `frontend/src/screens/Settings.tsx` — `Africa/Algiers` was absent |
| Catalog tooling | `frontend/scripts/i18n-extract.mjs`, `i18n-import.mjs` |
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

### Localization coverage — measured three times, honestly each time

This number has been corrected twice, and the direction of travel is worth
recording because each revision was less flattering and more true.

1. **"95.73%"** — wrong metric entirely. That was the French/Arabic key-count
   ratio (1187/1240), which says nothing about how much of the UI is translated.
2. **"ar 100%, fr 96.90%"** — right metric, broken instrument. Measured against
   the extractor's 1031 keys, but the extractor only saw static `t("literal")`
   calls. It was blind to every string reaching `t()` through a spec table —
   `t(spec.label)`, `t(spec.hint)`, `t(o)` — which is where all of this
   branch's Algeria strings live.
3. **The current figure, with the extractor fixed:**

| | catalog keys | translated | coverage | dictionary keys |
| --- | --- | --- | --- | --- |
| Arabic | 1593 | 1245 | **78.2%** | 1363 |
| French | 1593 | 1202 | **75.5%** | 1310 |

The catalog grew 1031 → 1593 (1126 from `t()` calls, 467 from spec tables).
**Coverage did not get worse — the measurement got honest.** Both dictionaries
gained keys throughout; the denominator simply stopped lying by 562 strings.

Of the remaining gap, a large share is deliberate: acronyms and product names
that must not be translated (ADR, RevPAR, OTA, VIP, UPI, KOT, Pax…), strings
already identical in the target language, and keys whose placeholders carry an
English morpheme and so cannot be translated at all (limitation 12). The rest is
genuine backlog. ~118 Arabic and ~108 French keys are reported unused; most are
still reachable through `t(variable)` call sites the extractor cannot see, or
are server-supplied country-pack strings that no frontend analysis can ever
find — the truly dead count is around 49.

Arabic was also quietly behind the UI before this branch: 22 live strings — the
AI-provider block in Settings, the marketplace block in Setup, several
housekeeping and POS strings — had never reached it. Those are translated.

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
3. ~~**RC / NIS / AI have no Property fields.**~~ **Resolved.** `rc_number`,
   `nis_number` and `ai_number` now exist on Property (patch `v37`), and the
   footer prints `RC · NIF · NIS · AI`, verified by calling `invoice_context()`
   against the real module. The three fields are **not** country-gated: `gstin`
   itself is ungated, nothing in this app gates on `country` (zero hits for
   `doc.country` across every DocType), and `Property.country` is free-text
   `Data` — so an `eval:` on it would break on "algerie" or a trailing space by
   silently *hiding* a legal identifier off a printed invoice. Cost: three rows
   every country sees, the same cost already paid for the five `gst_*` fields.
   The clean fix is making `country` a Link and grouping country fields behind
   a section `depends_on`, which is a much larger change.
4. **Children are not counted in the levy.** Adults only, commented at both
   calculation sites. Several Algerian municipalities exempt or halve
   children; this is an operator policy decision left explicit.
5. **Levy tax rate basis differs subtly between paths**: the quote uses the
   stay's blended room tax rate, the folio uses that night's. Identical unless
   a stay crosses a rate boundary. Pre-existing.
6. ~~**Amounts in words print `"DZD Three Thousand Only"`**~~ **Resolved.**
   `words.py` now carries `"DZD": ("Dinars", "Centimes")`. Still open for the
   Saudi pack, whose `SAR` has no entry either — not this branch's to fix.
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
12. **Plural and ordinal morphology — visible damage stopped, real support
    still absent.** Call sites compute an *English* morpheme themselves
    (`s: n === 1 ? "" : "s"`, `ies`, `ord` for st/nd/rd/th) and pass it in, so
    Arabic rendered `3 ليلةs`, `3 عقارy` and `الطابق 3rd` — on staff screens and,
    after the public-screens work, on the guest booking page.

    **Fixed as far as it can be cheaply fixed:** `LangDef` now declares
    `suffixPlural` and `ordinalSuffix`, and `interpolate()` drops those
    placeholders where they do not apply. Arabic renders `3 ليلة` and
    `الطابق 3`; English and French are unchanged. Two flags rather than one
    because the properties differ — French pluralises with `-s` so it keeps
    `{s}`, but writes ordinals `1er` / `3e`, so `3rd étage` would be as wrong as
    the Arabic was. A side benefit: with `{ord}` dropped, that key is
    translatable into French for the first time.

    **This is not plural support and is labelled a stopgap in the code.** It
    declines to append an English suffix; it does not select a plural form.
    Arabic has six plural categories and this expresses none of them, and
    `{n}e étage` is still wrong for `n = 1` (French wants `1er`). Real support
    means per-category forms driven by `Intl.PluralRules`, which changes the
    dictionary format and every affected key — roughly 40 call sites across 15
    screens.
13. ~~**The three public guest-facing screens are not internationalised.**~~
    **Resolved.** All three now use `t()` (88 / 52 / 13 calls where there were
    zero), carry a language picker a guest can reach without an account, and
    pick Arabic from `navigator.language` on a cold visit. Every physical
    directional class on text in those files is now logical, and price and phone
    runs are bidi-isolated. **But the hotel's own content is still
    monolingual** — property and room descriptions, house rules, FAQ, amenities,
    meal-plan and menu item names are backend data, so an Arabic guest gets an
    Arabic interface wrapped around whatever language the operator typed. Fixing
    that means per-language fields on the Property / Room Type / Menu Item
    DocTypes, or saying so plainly in the operator-facing settings copy.
14. ~~**The booking drawer is not RTL-correct.**~~ **Resolved.** `Sheet`,
    `BookingDialog` and the Kitchen display panel now anchor `end-0` instead of
    `right-0`, the Kitchen panel's `border-l` became `border-s`, and
    `index.css` gained a mirrored `sheet-in-rtl` keyframe selected by
    `[dir="rtl"]` — a logical anchor with a physical animation would have been
    worse than neither, landing correctly after starting from off the wrong
    edge. `aria-label="Close"` is now `t("Close")`, which was already
    translated (`إغلاق` / `Fermer`) and simply never used. `Sheet`'s
    `description` widened from `string` to `ReactNode` so a caller can
    bidi-isolate the date range inside it.
15. **`LangPicker` now exists in six places** — the three public screens,
    `PublicCheckin`, and `<select>` variants in `Login` and `Settings`. Pure
    duplication; wants one component in `components/ui/` with a `tone` prop for
    the hero-glass variant `PublicBooking` needs.

    The cold `navigator.language` sniff is duplicated four times alongside it,
    and moving it into `initLang()` would fix every entry point at once — but
    that is **not** a pure refactor and is deliberately left undone. `initLang`
    runs for the whole app, so the sniff would start choosing the initial
    language for *staff* screens too, not just guest pages. Defensible, and
    arguably right, but it changes default behaviour for every existing user
    and is the operator's call, not a cleanup.
16. **The frontend is type-checked but not lint-checked.** `eslint` is not in
    the local `node_modules` and `npx` refused to install it, so
    `react-hooks/exhaustive-deps` has never run over the new effects. CI's
    pre-commit eslint hook will be the first to see them.
17. **`rtl:rotate-180` is the first use of the `rtl:` variant in this repo.**
    Tailwind 4 drives it off `<html dir>`, which `applyLang()` sets, and it
    type-checks — but nobody has confirmed it visually.
18. **`marketplace_install_check.py` crashes on Windows** with
    `UnicodeDecodeError` (cp1252) unless `PYTHONUTF8=1` is set. Environment
    bug, works in CI. Worth an upstream fix.

19. **The currency symbol prefixes the amount; Algerian convention suffixes
    it.** Money renders `DA 1 500`. An Algerian bill is conventionally written
    `1 500,00 DA`. The amount, the separators and the symbol are all correct —
    only the position is not, so nothing is ambiguous or wrong, it simply is
    not how a local accountant writes it.

    **Deliberately deferred, with the cost measured rather than guessed.** The
    position is not a setting: it is baked into every money display in the app.

    | | count |
    | --- | --- |
    | `cur()` sitting directly before a number (mechanically convertible) | 149 |
    | `cur()` standalone — a bare symbol in a column header, `{cur()}0`, `${cur()}/night` — each needing its own judgement | 84 |
    | files defining their own local number formatter (`const inr = …`) | 34 |
    | files touching `cur()` | 40 |
    | uses of the one shared formatter, `fmtMoney` | 2 |

    So the fix is not a flag. It is: add one shared formatter that honours a
    per-pack position, migrate 149 adjacency sites to it, review 84 standalone
    uses individually, and collapse 34 duplicated local formatters. Every money
    surface in the product, including printed invoices.

    **Why it waits:** there is no bench, no site and no browser here, so not one
    of those 233 sites could be seen rendered. The failure mode is a wrong
    price on a guest's invoice that nobody notices before the guest does. And a
    partial migration is worse than none — one screen reading `DA 1 500` while
    another reads `1 500 DA` is a defect in a way that consistent
    non-convention is not.

    **Do it right after the first trial install**, when screens can actually be
    looked at. The order that keeps it verifiable:
    1. Add `symbol_position` to the pack contract in
       `kamra/localization/__init__.py`, defaulting to prefix so every existing
       country is unaffected; Algeria returns suffix.
    2. Add `money(n)` to `frontend/src/lib/money.ts` as the single formatter,
       honouring position, and keep `cur()` for the genuine bare-symbol cases.
    3. Convert the 149 adjacency sites by script — the patterns are regular
       (`{cur()}{inr(x)}`, `${cur()}${inr(x)}`) — then assert the count went to
       zero and `tsc` still passes.
    4. Walk the 84 standalone uses by hand.
    5. Delete the 34 local formatters.
    6. **Look at a rendered invoice, folio, thermal receipt and booking page**
       before believing any of it.

## Technical debt / upstream candidates

- `tax_exempt` on Room Type (limitation 1) — affects six packs.
- Percent-levy discount basis (limitation 2).
- **Real plural support via `Intl.PluralRules`** (limitation 12). The visible
  garbage is gone, but the scheme still cannot *select* a form: Arabic's six
  plural categories are unexpressed, and French `1er` vs `3e` needs the caller
  to stop passing a suffix. ~40 call sites across 15 screens, plus a dictionary
  format that can hold per-category forms.
- ~~`i18n-extract.mjs` hard-codes `ar.json` and cannot see `t(variable)`~~ —
  **done**: it globs `src/i18n/locales/*.json`, names columns by locale code,
  harvests spec-table literals, and its per-file SKIP list was replaced with
  structural exclusions that cannot rot. `i18n-import.mjs` was fixed in the same
  commit to default its column to the language code. Remaining gap: string
  arrays consumed as `.map(o => t(o))` (e.g. `ORDER_TYPES` in POS, `id_types` in
  `lib/money.ts`) and backend-supplied country-pack strings are still invisible.
- Lazy-load locale dictionaries.
- `words.py` `SAR` entry, for the Saudi pack (DZD is done).
- One shared money formatter, and the symbol position with it
  (limitation 19) — 233 sites, sequenced there.
- `marketplace_install_check.py` Windows encoding.
- Rename `gstin` → `tax_id`.
- ~~Internationalise the three public screens~~ — **done**. What remains is
  the hotel's own content (limitation 13) and the `Sheet` component's RTL
  anchoring (limitation 14).
- Extract a shared `LangPicker` and move the `navigator.language` sniff into
  `initLang()` (limitation 15).
- Prune the 49 genuinely dead `ar.json` keys / 45 in `fr.json`.

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

- Trilingual GRC / invoice print verification (ar / fr / en layout, RTL) —
  nobody has looked at a rendered page in any language, including the newly
  localised guest-facing screens
- Per-language fields for hotel-authored content, or an explicit decision to
  accept mixed-language guest pages and say so in the operator settings copy
- Children policy for the levy (limitation 4) — an operator decision
- Whether a percentage levy is discountable (limitation 2) — an owner decision
- A native-speaker pass on the French legal/privacy copy, and on the Arabic
  levy harmonisation (`الرسم على الغرفة` → `رسم الإقامة`), which edited three
  translations someone else shipped
- `bench migrate` on a real site — the first genuine test of `v36` and `v37`
