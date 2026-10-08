# Kamra PMS Algeria — commercial transformation audit

**Phase 1 of 10. Audit only. Nothing in this document has been implemented by
the change that added it, and no file outside this one was modified.**

Every number here was measured against the working tree on 2026-10-08, at
commit `1c5a6df`. Where a thing does not exist, this document says so in those
words rather than describing what it would look like.

---

## 1. What this repository actually is

| | |
| --- | --- |
| Product | ZIRI PMS 1.0.0 — the Algeria distribution of Kamra PMS 2.6.5 |
| Licence | AGPL-3.0 (`license.txt`, 661 lines) |
| Backend | Frappe v16.25.0, one app: `kamra` |
| Frontend | React 19 + TypeScript + Vite 6 + Tailwind 4, one SPA at `/ziri` |
| Database | **MariaDB 11.8**, not PostgreSQL |
| Python | 389 modules, 43,949 lines |
| Frontend | 58 screens, 45,335 lines |
| DocTypes | 97 |
| Schema patches | 22 |
| Test modules | 51 |
| Documentation | 72 markdown files |

Docker Compose runs ten services: `configurator`, `backend`, `frontend`,
`websocket`, `queue-short`, `queue-long`, `scheduler`, `db`, `redis-cache`,
`redis-queue`.

**It is single-tenant by design.** `kamra/public_api.py:265` states it
outright: "Each ZIRI deploy is single-tenant: one site = one hotel/villa."
Isolation between customers is the deployment boundary, not a tenant column.
Multi-property exists *within* one customer, through the `Property` DocType
and the property-scoping in `kamra/authz.py`.

---

## 2. The commercial vocabulary search (brief §1)

Raw file counts mislead here, so each term was read rather than counted.

| Term searched | Files | What it actually is |
| --- | --- | --- |
| `licens*` | 179 | **Boilerplate only.** 111 × "For license information, please see license.txt", 38 × "See license.txt", 20 × SPDX. There is no licensing system |
| `quotation` / `contract` | 12 / 17 | **Banquet**, not commercial. `banquet.py`, `venue_booking` — selling an event to a guest, not selling software to a hotel |
| `sla` | 46 | The hotel's own service-ticket and channel-manager SLAs. Nothing about vendor support response times |
| `tenant` | 6 | Comments stating the product is single-tenant |
| `trial` | 5 | The trial *install*, in docs and deploy scripts |
| `demo` | 23 | Demo seed data and `kamra_demo_mode` |
| `activation` | 1 | A passing mention |
| `subscription` | 0 | Does not exist |
| `feature_flag` | 0 | Does not exist **under that name** — see §4 |
| `telemetry` | 0 | Does not exist |
| `analytics` | 0 | Does not exist as a product-analytics concept |
| `remote_support` | 0 | Does not exist |
| `entitlement` | 4 | Exists — see §4 |
| `installation_id` | 4 | Exists — see §4 |

---

## 3. Security and authorization, as built

`kamra/authz.py` (292 lines) is the real authorization layer and it is better
than the brief assumes:

- `require_roles(*roles, scope=...)` — the decorator every endpoint carries
- `restricted_properties()` / `assert_property_access()` — **server-side**
  property scoping, not frontend filtering
- `assert_record_access()`, `assert_guest_access()`, `guest_scope_sql()` —
  row-level scoping down to individual guests
- `require_cashier_pin()` with lockout — a second factor for till operations

Roles shipped: Hotel Admin, Front Desk, Housekeeping, Finance, Revenue
Manager, Kamra Agent. The brief's proposed set (§28) maps onto these with two
genuine gaps: there is no `SUPPORT` role and no `READ_ONLY` role.

Audit logging exists through Frappe's `Activity Log` (logins, logouts, failed
attempts), `Version` with `track_changes` on every money DocType, and
`Permission Log`. Backup and restore operations were added to that trail this
cycle (`kamra/monitoring.py`).

---

## 4. What already exists of the brief's commercial ecosystem

This is the part most likely to be misjudged. Several items the brief asks
for are built, and building them again would be the expensive mistake.

| Brief section | Status | Where |
| --- | --- | --- |
| §7 Installation identity | **Built** | `kamra/installation.py` (119 lines). Generated and stored, deliberately *not* derived from hardware, site name or the encryption key — the module documents why each of those is wrong |
| §37 Health monitoring | **Built** | `kamra/health.py` (714 lines), 11 checks, `bench ziri-doctor` |
| §41 Observability | **Partly** | 27 error codes emitted, taxonomy in `docs/product/ERROR_CODES.md`, CI guard against drift |
| §25 Backup / DR | **Built** | `deploy/backup-verify.sh` with level-1 restore verification and negative controls that prove the verifier can fail; `deploy/verify-restore.sh` for level 2; systemd timers |
| §23 Update system | **Partly** | `kamra/distribution.py`, GitHub release feed, `deploy/install.sh` gates, `docs/product/UPDATES.md`, `ROLLBACK.md` |
| §52 Feature flags | **Built, under another name** | `Property.enabled_modules` + `kamra.api.ALL_MODULES` (9 modules) + `visibleApps()` in the frontend. The AI agent now respects it too |
| §30 AI assistant | **Built** | `kamra/assistant.py` — 55 governed tools, role-gated, module-gated, audit-logged, Arabic/French/English, local Ollama supported. `kamra/agent_guest.py` for unauthenticated callers, 4 read-only tools |
| §34 Demo | **Partly** | `kamra_demo_mode`, demo seed scripts |
| §44 Migrations | **Built** | 22 versioned patches in `patches.txt` |
| §43 CI/CD | **Partly** | 15-step CI: error-code guard, eval harness, 4 test suites, fresh-install correctness. **No dependency, container or secret scanning** |
| §12–14 Commercial licence | **Record only** | `kamra/entitlement.py` (223 lines) — states and dates, surfaced in health and the support bundle, **enforces nothing**. See §6 below |

---

## 5. What does not exist at all

Measured, not assumed:

- No licensing server, no signed licence, no Ed25519, no public-key
  verification, no activation protocol, no revocation, no grace period
- No customer, hotel-as-customer, quotation, contract, payment or renewal
  record **for selling the software** (the ones that exist sell banquets)
- No customer portal, no internal admin portal
- No support ticket system **for the vendor** (the Service Ticket DocType is
  the hotel's own guest-facing queue)
- No maintenance contract
- No remote-support authorization workflow
- No telemetry, no product analytics
- No `SUPPORT` or `READ_ONLY` role
- No first-run wizard that is resumable (`first_boot.py` is a script, not a
  wizard)
- No dependency / container / secret scanning in CI

---

## 6. The licensing problem — read this before approving Phase 3

The brief's §5–§10 and §33 describe a signed-licence system with activation,
revocation and feature entitlement. **Most of it cannot be made effective on
this codebase, and the reason is structural rather than a matter of effort.**

ZIRI PMS is AGPL-3.0. Section 7 of that licence does not permit imposing
further restrictions on the rights it grants, and running the program is one
of them. Section 13 requires the complete Corresponding Source to be offered
to every user who interacts with it over a network — which means any
enforcement code ships, by obligation, together with the instructions for
removing it. The product's own marketplace screen also tells the hotelier
"every app is open and included", and `docs/algeria/LICENSING.md` §3.2 — part
of this distribution — commits in writing to not presenting the software as
though it originated with the distributor.

This was raised earlier in this project and the decision taken was: an
entitlement **record** with informational state, no functional gating. That is
what `kamra/entitlement.py` implements, and it is why no state it reports is
ever `failed`.

Three paths remain open, and the choice is commercial rather than technical:

1. **Entitlement as record** (what exists). What actually stops on
   non-renewal is the vendor's own services — the update feed, a managed
   gateway, remote support, an SLA — because those run on the vendor's
   machines. This is the Frappe/ERPNext model.
2. **Open core.** ZIRI stays AGPL; paid modules are a separate Frappe app in
   a repository the vendor owns and does not publish. This is the only path
   that supports genuine, enforceable restriction, and it means a paid
   feature is never written in this repository.
3. **Relicensing.** Requires agreement from the upstream Kamra authors —
   Mohammed Azzan holds roughly 396 of the ~510 commits — not only from this
   distribution.

**Phases 2, 3 and 5 of the brief's plan should not start until this is
decided**, because the licence model determines whether `Plan`, `Feature` and
`License` are records on the hotel's own site or records on a vendor server
the hotel never sees.

---

## 7. Security findings

Nothing here is a live incident; these are audit findings ranked by what they
would cost.

**High — confirmation is not enforced.** `kamra/assistant.py:171` instructs
the model to confirm irreversible actions. It is a sentence in a prompt, not
a gate. 30 of the 55 staff tools change state, including `cancel_booking` and
`void_charge`. A model that skips the question is not prevented from acting.

**High — prompt injection on the staff agent.** Tool results return to the
model unfenced. A guest name or reservation note containing "ignore previous
instructions" is read as text. The guest agent (`agent_guest.py`) fences its
results; the staff agent does not.

**Medium — no SUPPORT or READ_ONLY role.** Support work is done today as
Hotel Admin or System Manager, which is more authority than the task needs
and leaves a weaker audit trail.

**Medium — CI has no security scanning.** No dependency advisories, no
container scan, no secret scan. `semgrep` rules exist for two Frappe-specific
patterns and are enforced, which is good but narrow.

**Medium — unrotated credentials.** A GitHub PAT and a server SSH password
were pasted into a working session earlier in this project and have not been
confirmed rotated. This belongs in the audit because it is the kind of finding
that is embarrassing to discover later rather than now.

**Low — the demo-account check is documentation, not code.** SECURITY-003
("demo accounts exist on a production site") has basis `doc`: a query a human
is told to run. It is not a health check.

---

## 8. Technical debt worth naming

- **Two-level versioning is correct but leaks.** `kamra/__init__.py` is
  2.6.5 (upstream Kamra), `distribution.py` is 1.0.0 (ZIRI). Every surface
  that shows a version must pick deliberately; one of them showed the wrong
  one until this cycle.
- **`/assets/kamra/` and `/api/method/kamra.*` are permanent.** The public
  route moved to `/ziri`, but the app package cannot be renamed without a
  migration that touches every stored reference. Treat `kamra` as an internal
  identifier for ever.
- **Build artifacts are committed.** `kamra/public/frontend/` holds the built
  SPA, ~76 hashed files replaced on every frontend change. Necessary for
  marketplace installs that cannot run npm; noisy in every diff.
- **41 of 67 error codes have no machine signal.** Documented as such, not
  hidden, but it means the taxonomy is ahead of the instrumentation.

---

## 9. Recommended target architecture

Modular, inside the existing app, not microservices.

```
                    Vendor side (new, separate repo)
                    ┌──────────────────────────────┐
                    │  Licensing / customer server │
                    │  customers, hotels, licences │
                    │  quotations, contracts       │
                    │  support tickets, SLA        │
                    │  update feed                 │
                    └──────────────┬───────────────┘
                                   │ HTTPS, signed
  ───────────────────────────────── │ ───────────────────────────────
                    Hotel side (this repository)
                                   │
   kamra/entitlement.py ◀──────────┘   record + state, no gating
   kamra/installation.py               identity, already built
   kamra/health.py                     11 checks, already built
   kamra/monitoring.py                 alerting, already built
   kamra/api.py ALL_MODULES            feature flags, already built
```

The vendor-side system is a **separate application**. Nothing about customers,
quotations or contracts belongs on a hotel's own site: it is the vendor's
commercial data, it must survive a hotel's database being restored, and a
hotelier must never be able to read another customer's record because both
happen to run ZIRI.

That single decision answers brief sections 11, 12, 15, 16, 17, 18, 19, 20,
22, 36 and 38 at once — all of them are the vendor application, none of them
is a change to this repository.

---

## 10. Phased plan, re-ordered by what unblocks what

The brief's phase order starts with licensing. That is the wrong first move
here, because §6 above is undecided and because two security findings should
not wait behind a commercial decision.

| Phase | Work | Depends on |
| --- | --- | --- |
| **0** | **Decide the licence model** (§6). One commercial decision | You |
| **1** | Enforce confirmation on the 30 mutating agent tools; fence tool output on the staff agent | Nothing |
| **2** | Add `SUPPORT` and `READ_ONLY` roles; remote-support authorization with expiry, scope and audit | Nothing |
| **3** | CI security scanning — dependencies, containers, secrets | Nothing |
| **4** | Resumable first-run wizard over the existing `first_boot.py` | Nothing |
| **5** | Vendor application: customers, hotels, licences, quotations, contracts, tickets | Phase 0 |
| **6** | Licence client: fetch, verify, cache, grace period, state surface | Phase 5 |
| **7** | Customer portal | Phase 5 |
| **8** | Telemetry, opt-in and documented | Phase 5 |

Phases 1 to 4 are work in this repository that is worth doing whatever is
decided in Phase 0, and three of the four are security.

---

## 11. What this audit did not examine

Stated so the gaps are visible rather than implied.

- **No running system was inspected.** Docker Desktop has been off for
  several working sessions, so every finding here is from source and from CI
  runs, not from a live site.
- **Dependency vulnerabilities were not scanned.** There is no tooling for it
  in this repository yet, which is itself finding §7.
- **The frontend was measured, not reviewed.** 45,335 lines across 58
  screens; this audit read the routing, i18n and agent surfaces only.
- **Algerian tax and legal correctness was not verified.** `localization/
  algeria.py` declares TVA, the taxe de séjour and the NIF/RC/NIS/AI
  identifiers. Whether those match current Algerian law is a question for an
  accountant, and the brief's own §2 warns against hardcoding assumptions.
- **No load or concurrency testing.**

---

## 12. Decisions taken

Recorded here because an audit that collects decisions and then loses them is
a document nobody can act from six months later.

### D1 — The licence model is an entitlement record, not enforcement

**Decided.** Section 6 set out three paths; the one chosen is the first.
`kamra/entitlement.py` records what a customer bought and reports its state,
and gates nothing. What stops on non-renewal is the vendor's own services —
the update feed, a managed gateway, remote support, an SLA — because those run
on the vendor's machines rather than inside a hotel's installation.

Consequences that follow from this and should not be re-argued per feature:

- No state the entitlement reports is ever `failed`, so an unpaid renewal can
  never page anyone at 03:00 and can never read as an outage.
- `Plan` and `Feature` are **vendor-side records**. The hotel's installation
  learns what it is entitled to; it does not decide it, and it does not
  enforce it.
- Brief sections 5, 8, 9, 10 and 33 — signed licences, activation, offline
  grace, expiry behaviour, anti-piracy layers — reduce to one thing on the
  hotel side: fetch a record, cache it, show its state honestly. Everything
  else in those sections is vendor-side or does not apply.

### D2 — The vendor application lives in its own repository

**Decided.** Not a second Frappe app in this bench, and nothing about
customers, quotations, contracts or tickets on a hotel's own site.

The reasons, so the boundary holds when it is inconvenient:

- It is the **vendor's** commercial data. A hotelier restoring their own
  database must not restore the vendor's customer list with it, and must never
  be able to read another customer's record because both happen to run ZIRI.
- Its lifecycle is different. The vendor system is updated when the business
  changes; a hotel's installation is updated when the product does, on the
  hotel's own maintenance window.
- It keeps this repository AGPL-clean. Under D1 the vendor system holds no
  enforcement, but it does hold commercial data, and separating it means no
  future commercial feature arrives in a repository whose source must be
  offered to every guest who opens the booking page.
- **It is what makes D1 workable at all.** The services that stop on
  non-renewal only stop because they run somewhere the hotel does not control.

This settles brief sections 11, 12, 15, 16, 17, 18, 19, 20, 22, 36 and 38 in
one move: all of them are the vendor application, none of them is a change to
this repository.

### Still open

- Approval to begin Phase 1. Phases 1 to 4 modify this repository and are
  worth doing under either licence model; three of the four are security.

---

## 13. What is needed from you before Phase 1

1. **The licence-model decision** (§6). It blocks phases 5 to 8.
2. **Confirmation that Phases 1–4 may proceed**, since they modify this
   repository.
3. Whether the vendor application should live in a new repository — the
   recommendation — or as a second Frappe app in this bench.
