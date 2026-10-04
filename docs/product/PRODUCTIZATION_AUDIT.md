# Productization audit — Phase 0

**Scope**: what this repository already has, measured, before any product-lifecycle
work is designed on top of it.

**Why this document exists first**: the brief that commissioned this work describes a
platform covering install → licence → update → backup → recovery → support. A
substantial part of that already exists here and has done for some time. Designing it
again would produce a second, worse copy of working machinery. Everything below was
read out of the repository, not assumed.

**Version at audit**: `2.6.5` (`.release-please-manifest.json`).
**Branch**: `feature/productization`, cut from `55b0aa0`.

---

## Correction to the brief, before anything is built on it

The brief names **PostgreSQL** in six places — as the database to monitor, to back up,
to health-check, and to put in the deployment diagram.

**This product does not run on PostgreSQL and cannot.** It is a Frappe v16 application.
Frappe's PostgreSQL support is experimental and is not used for production hotels; this
stack runs **MariaDB 11.8**, which is what `deploy/linux/docker-compose.yml` starts, what
CI provisions, and what the live install uses.

Every PostgreSQL reference in the brief is read as MariaDB in this plan. This is not a
preference — a backup procedure written for `pg_dump` would produce files that cannot be
restored, and a "database healthy" check written against PostgreSQL would be a green
tick that verifies nothing. Flagged here because it is the kind of error that is cheap
now and expensive after it has been implemented.

Two smaller ones, noted and then set aside:

- The brief asks for `curl … | bash` as the installation command and then says not to
  implement it blindly. Agreed, and `deploy/install.sh` already exists; §8 below.
- The brief says customers should not need to understand Docker. True as a goal, but the
  Windows path already drives Docker Desktop through WSL2 and that leaks; §8.

---

## What already exists

### Versioning and release — largely built

| | Where | State |
| --- | --- | --- |
| Semantic version, single source | `.release-please-manifest.json` → `2.6.5` | Working |
| Automated version bump from commits | `.github/workflows/release-please.yml` | Working |
| Release config | `release-please-config.json` | Working |
| GitHub Release publication | `.github/workflows/release.yml` → `softprops/action-gh-release`, actions pinned by SHA | Working |
| Docker image publication | same workflow → `ghcr.io/kamra-pms/kamra` | Working |
| Demo deployment on release | same workflow, `deploy-demo` job | Working |
| Version visible to the customer | `kamra/health.py` imports `kamra.__version__` | Working |
| Update availability | `_fetch_github_latest()` + `_version_check()` compare the installed semver against the newest GitHub release | Working |

The brief's §15 (versioning), §16 (release channels, partly — `nightly.yml` exists), §38
(release pipeline) and §62 (changelog, via release-please's generated notes) are
therefore **mostly already satisfied**. What is missing from them is listed under Gaps.

### Continuous integration — real, not decorative

Seven workflows: `ci.yml`, `linters.yml`, `nightly.yml`, `release.yml`,
`release-please.yml`, `deploy-smoke.yml`, `vps-doctor.yml`.

`ci.yml` is the substantive one and it does more than lint:

- frontend typecheck and production build, then **asserts the built `index.html`
  references the production asset base** — a real check, not a green tick
- provisions MariaDB, initialises a bench, installs the app and creates a site
- runs the backend eval harness, the banquet unit tests, and a front-desk persona
  journey against that live site

`linters.yml` runs semgrep with `frappe-sql-format-injection` at ERROR severity; the repo
has an established `# nosemgrep` convention for the audited exceptions.

Secret scanning exists at commit time: gitleaks `v8.30.1` in `.pre-commit-config.yaml`.

49 files match `test_*.py`. **Most are Frappe's generated per-doctype stubs** and assert
nothing; the tests that carry weight are the banquet suite, the eval harness and the
persona journey named above. Counting 49 as "49 tests" would be the kind of number this
document exists to avoid.

### Health checking — built, and already in the UI

`kamra/health.py` (316 lines) exposes `system_health()`, surfaced at `/kamra/health` by
`frontend/src/screens/SystemHealth.tsx`. It returns per-check `passed / attention /
failed / info` plus an overall rollup, and already checks:

version-vs-latest · Frappe · installed apps · database · scheduler · disk · timezone

So the brief's §26 (`kamra-doctor`) and a good part of §31 (admin dashboard) exist. The
checks it does **not** perform are listed under Gaps, and they are the ones that matter
most in production.

### Installation — three paths, all real

| Path | File | Target |
| --- | --- | --- |
| Linux, scripted | `deploy/install.sh` | Fresh Ubuntu/Debian server; fetches frappe_docker, builds, creates site, first boot |
| Linux, compose | `deploy/linux/docker-compose.yml` + `.env.example` + `README.md` | Day-to-day operation of an existing image |
| Linode | `deploy/linode/stackscript.sh` | One-click provisioning |
| Windows | `deploy/windows/Install-Kamra.ps1` + `ZiriPms-Setup.nsi` | Docker Desktop over WSL2, NSIS installer |

The compose stack has been run end to end: ten services up, site created, migrations
`v36`/`v37` applied, app served, and a `down`/`up` cycle survived (which is how the
MariaDB `start_period` and the nginx stale-IP traps in `deploy/linux/README.md` were
found).

### Documentation — 22 files, three languages

`docs/algeria/` carries `INSTALLATION.md`, `BACKUP.md`, `VERSIONING.md`, `LICENSING.md`,
`TAXES.md`, `IMPLEMENTATION_STATUS.md`, plus `guides/{INSTALL,USER,DOCKER}-{ar,fr,en}.md`.
`docs/` adds `self-hosting.md`, `user-guide.md`, `ai-and-api.md`, `email-setup.md`.

### Activity recording — partial

`Agent Action Log` and `Night Audit Run` doctypes exist, with `/kamra/activity` in the
UI. This is **not** the audit log §29 asks for — see Gaps.

---

## Gaps — measured, not guessed

Each line below is a repository-wide search that returned **zero** non-documentation hits.

| Brief | Capability | Hits |
| --- | --- | --- |
| §27 | Support bundle | 0 |
| §35 | Installation ID | 0 |
| §59 | Feature flags | 0 |
| §12–14 | Commercial licence: enforcement, grace period, activation | 0 |
| §45 | Error-code taxonomy (`DB-001`, `UPDATE-003`…) | 0 |
| §30, §55 | Monitoring, metrics endpoint, alerting | 0 |
| §22 | Scheduled automatic backup | 0 |

### Since this audit (2026-10-04)

The Hits column above is a dated measurement and is left as it was found; a
record that gets edited to match today is not a record. What has changed since:

| Brief | Then | Now |
| --- | --- | --- |
| §27 Support bundle | 0 | **Closed.** `kamra/support_bundle.py`, `bench ziri-support-bundle`, 10 sections, 3-layer redaction with a fail-closed canary |
| §35 Installation ID | 0 | **Closed.** `kamra/installation.py`, generated and stored rather than derived |
| §30, §55 Monitoring, alerting | 0 | **Alerting closed**, `kamra/monitoring.py`, hourly, on state change not state. **Metrics endpoint still open**: `system_health` is JSON over HTTP, not a Prometheus exposition |
| §45 Error-code taxonomy | 0 | **22 of 63 allocated codes emitted** by `health.py`, `ziri-doctor`, the bundle and four `Error Log` titles; `kamra/scripts/error_code_check.py` fails CI on drift. The other 41 have no machine signal and say so |
| §22 Scheduled automatic backup | 0 | **Closed.** `deploy/systemd/` - daily backup 05:30, weekly verification Sunday 06:30, both `Persistent=true`, installed by `install-timers.sh`. Retention added at the same time (`KEEP_SETS`, default 14): automating an unbounded writer is how a disk fills |
| §59 Feature flags | 0 | **Still open.** No hit anywhere |
| §12–14 Commercial licence | 0 | **Still open.** No hit anywhere |

Audit trail was not in the table and turned out to be largely already present:
Frappe's `Activity Log` carries logins and failed attempts, and `Version` with
`track_changes` carries document history on every money doctype but one. The
real gaps were `Cancelled Invoice` and backup/restore, both now closed
(`kamra/monitoring.py`).

`docs/algeria/LICENSING.md` exists but documents **AGPL-3.0 §13 obligations** — the
licence this software is distributed *under*. It is not a commercial entitlement system
and must not be confused with one.

### Gaps inside things that do exist

**`health.py` did not check what breaks.** *(Partly addressed after this audit was
written — see the note below.)* Its seven checks omitted: Redis (two instances), the
queue workers, the scheduler *process* as opposed to its setting, container state, TLS
certificate expiry, backup freshness, and licence validity. On the live install the
single most common failure in this session was a service being reachable by DNS but not
by cached IP — nothing in `health.py` would have reported it.

> **Superseded in part.** Redis (write-and-read-back), background workers (RQ worker
> count and queue depth) and backup age were added in `75ee9eb`, and the scheduler check
> was rewritten to require a recent execution rather than a enabled setting. Doing so
> exposed a real stall on the trial install: all 51 `Scheduled Job Type` rows were
> stamped in the future after the site's time zone moved to a lower UTC offset, so
> nothing was ever due and the night audit had never run — while the process was alive
> and `bench doctor` reported workers online. That detection is now in the check.
>
> Still missing from `health.py`: container state, TLS certificate expiry, licence
> validity, and any notion of an *off-host* backup. `_backup_check` is age-only against
> a hard-coded 48-hour constant and can see only `*.sql.gz` inside the `sites` volume —
> it cannot see a shipped copy, and it cannot tell whether anything restores. There is
> still no monitoring or alerting of any kind: the panel must be looked at to be read.

**No backup verification anywhere.** `docs/algeria/BACKUP.md` documents
`bench backup --with-files` and says to test a restore. Nothing automates or verifies it.
Per §18 and §49, a backup whose restoration has never been exercised is not a backup, and
this product currently cannot claim one.

**Update has no rollback.** `install.sh update` rebuilds and runs `bench --site all
migrate`. There is no pre-flight gate, no backup-before-update, no health gate after, and
no rollback path. §17–20 are unbuilt.

**Every release is a patch release.** `release-please-config.json` sets
`"versioning": "always-bump-patch"`. Conventional-commit types are therefore ignored for
the purpose of choosing the next number: a `feat:` commit bumps the patch digit exactly
like a `fix:` does, and a breaking change does not reach the major digit on its own.

The number still rises monotonically, so nothing is broken today — but §15 and §61 of the
brief ask for bug fix, minor feature, major feature and breaking change to be released
*differently*, and this setting makes the version incapable of expressing that
difference. A hotel administrator reading `2.6.4 → 2.6.5` cannot tell a security fix from
a new banquet module. Changing it is a deliberate release-policy decision, not a bug fix,
so it is recorded here rather than changed.

**Not a gap, recorded because it looks like one:** `frontend/package.json` carries
`"version": "2.0.0"` while the manifest says `2.6.5`. This was initially written up here
as version drift. It is not. `release-please-config.json` declares
`extra-files: ["kamra/__init__.py"]`, that file reads `2.6.5`, and `health.py` reports it
to the customer from there — so the customer-visible version is consistent across its
whole path. The `frontend/package.json` field is required by npm, is read by nothing in
this repository (searched), and is inert. Wiring it into the release process would add a
moving part to fix a problem that does not exist.

**Audit log does not cover §29.** `Agent Action Log` records what the AI agent did. Login,
role change, refund, discount, configuration change, restore — none are recorded as
protected audit events.

---

## Honest position

What exists is the **developer-facing half** of the lifecycle: build, test, version,
release, install, and a basic health read-out. It is real and it works.

What is missing is the **operator-facing half**: knowing an installation is healthy in
ways that matter, proving a backup can be restored, updating without risking the hotel,
getting out of a failure, and supporting a customer you cannot SSH into.

That is the actual delta, and it is what the subsequent phases address.

## What this document does not establish

- The compose stack has only ever run on Docker Desktop over WSL2 on one machine. It has
  **never run on the Linux server it is written for**.
- `deploy/linode/stackscript.sh` and the Windows NSIS installer were read, not executed,
  during this audit.
- No capacity figure appears anywhere in this document, because none has been measured.
  §56–57 remain entirely unaddressed and will stay that way until a load test exists.
