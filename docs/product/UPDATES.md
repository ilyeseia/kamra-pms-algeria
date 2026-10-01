# ZIRI PMS — Update design

> **Status: DESIGN. Nothing in this document is implemented.**
>
> No update runner, release manifest, signature, channel selector, pre-flight gate,
> `Update Run` record or admin screen described below exists in this repository. Where
> the text says "the installation does X", read "the installation will do X once built".
> What *does* exist today is listed in §1, with file references, so the gap is visible.
>
> Companion document: [`ROLLBACK.md`](ROLLBACK.md). Baseline: the Phase 0 audit,
> [`PRODUCTIZATION_AUDIT.md`](PRODUCTIZATION_AUDIT.md). Nothing here contradicts it;
> this document is the design for the audit's "Update has no rollback" and
> "Every release is a patch release" findings.

Product `ZIRI PMS`, internal app name `kamra`. Version at time of writing: `2.6.5`
(`.release-please-manifest.json`). Database: **MariaDB 11.8**, not PostgreSQL.

Conventions used below:

- `<COMPOSE>` is the compose invocation from `docs/algeria/BACKUP.md` §1 and
  `deploy/install.sh:178-184` — project `kamra`, env file `/opt/kamra/kamra.env`, the four
  `-f` files — run from `/opt/kamra/frappe_docker`.
- `$SITE` is the Frappe site name. `$RUN` is an update run id. `$UPD=/opt/kamra/updates/$RUN`.
- Service names are the real ones: `backend`, `frontend`, `db`, `redis-cache`,
  `redis-queue`, `queue-short`, `queue-long`, `scheduler`, `websocket`, `configurator`.
- A command marked **(VERIFY)** has a flag or behaviour that belongs to the Frappe or Docker
  version inside the built image and was not confirmed from this repository. Confirm it on the
  target before it is written into a script.
- The design assumes **one production site per installation**. `install.sh update` runs
  `migrate` on `--site all`; this design does not (see §8, step 9).

---

## 1. Starting point — what exists, measured

| Capability | State today | Where |
| --- | --- | --- |
| Version number, single source | Works. `2.6.5`. | `.release-please-manifest.json`, `kamra/__init__.py` |
| Release automation | Works. Draft Release PR on push to `main`; merging tags and publishes a GitHub Release. | `.github/workflows/release-please.yml` |
| Bump policy | `always-bump-patch`: `feat` and `fix` both bump the third digit. | `release-please-config.json:7` |
| Image publication | Works. `ghcr.io/kamra-pms/kamra:<tag>` **and** `:latest` (a moving tag). | `.github/workflows/release.yml:97-99` |
| Nightly | Works. Rolling prerelease named `nightly`, image `:nightly`, redeploys `nightly.kamrapms.com`. Gated on green CI for that SHA. | `.github/workflows/nightly.yml` |
| Update **discovery** | Works, read-only. Queries `GET /repos/Kamra-PMS/kamra-pms/releases/latest`, caches 1 h, compares installed vs latest semver, shows it at `/kamra/health`. | `kamra/health.py:24-28, 51-88, 389-434` |
| Update **application** | `install.sh update`: rebuild, `compose up -d --force-recreate`, `migrate --site all`, `clear-cache`. No pre-flight, no backup, no health gate, no rollback. | `deploy/install.sh:217-240` |
| Release artifacts a customer could verify | **None.** No checksum file, no signature, no SBOM attached to any release. | `release.yml`, `release-please.yml` |
| Backup | Documented manual procedure only; nothing automated, nothing verified. | `docs/algeria/BACKUP.md` |
| Licence validity | **Does not exist.** Zero hits in the repository (audit, Gaps). | — |

Facts about the current update path that shape this design, each read from the files above:

1. **The installation tracks a moving branch, not a release.** `KAMRA_BRANCH` defaults to
   `main` (`install.sh:42`). `install.sh update` re-reads `apps.json` and rebuilds whatever
   that branch is *now* (`install.sh:228-230`). An administrator who never touched
   anything is still on "whatever `main` was at the last update".
2. **The image tag is overwritten, not versioned.** The build is always tagged
   `${KAMRA_IMAGE}:${KAMRA_TAG}` = `kamra:local` (`install.sh:38-39, 168-169`). After an
   update the previous image is an untagged layer set; it is not a rollback target, and the
   `docker system prune -af` that `nightly.yml:164` and `release.yml:138` run on the VPS
   would delete it. See `ROLLBACK.md` §2.
3. **A rebuild is not reproducible.** `FRAPPE_BRANCH=version-16` and the `payments`
   `develop` branch both move (`install.sh:43, 156`). `ci.yml:81-82` records that the
   `version-16` tip "currently ships an UnboundLocalError" and pins CI to `v16.25.0` for
   that reason — **CI tests one Frappe, the customer's rebuild gets another.**
4. **`--force-recreate` with no service names recreates every service**, including `db`
   and both Redis instances (`install.sh:232`). `nightly.yml:181-182` already lists only the
   app services when it recreates them; the customer path does not.
5. **There is a window with new code on the old schema.** Containers are recreated on the
   new image (`install.sh:232`) and only afterwards is `migrate` run (`:235`). There is no
   maintenance mode in between.
6. **`install_self` fetches and installs a script from `main` unverified**
   (`install.sh:202-203`) when the script was piped. That is an existing path that executes
   unverified code. §6 closes it for the update path.
7. **The release is published before its image exists.** `release-please` creates the
   GitHub Release, then calls `release.yml`, whose `docker` job builds for many minutes
   (`release-please.yml:41-50`). In that window `releases/latest` — which `health.py`
   trusts — names a version whose image is not yet pushed.

---

## 2. Principles

1. **Fail closed.** A check that cannot be evaluated is a failed check. Any critical failure
   means *do not update* (§7).
2. **Nothing unverified is ever executed.** Not the manifest's contents, not a downloaded
   script, not a runner replacement (§6).
3. **A human starts every update; discovery never applies one.** Discovery tells, the
   administrator decides, the runner executes. This also preserves the existing contract in
   `health.py`'s docstring: "we never mutate the install from this screen."
4. **The thing that updates the stack cannot live inside the stack it updates.** The runner
   is a host-side program (it needs `docker`), not a Frappe request handler, and the
   `backend` container is not given the Docker socket (that would turn any web-app
   compromise into host root).
5. **Every step leaves the system in a state the administrator can name**, with an explicit
   statement of whether going back is possible and what it would cost (§9).
6. **Say what rollback costs before the update starts, not after it fails.**
7. **The version number is not trusted to carry meaning it cannot carry** (§5).

---

## 3. Release channels

| Channel | For | What it is | Source of truth | Offered? |
| --- | --- | --- | --- | --- |
| **STABLE** (default) | Every hotel | Latest non-prerelease, non-draft GitHub Release **that has a signed manifest attached** | `GET /releases/latest` (what `health.py` already calls), then the manifest | Offered, never applied automatically |
| **BETA** (opt-in) | A hotel that asked, or a pilot | A `vX.Y.Z-beta.N` GitHub **prerelease** that has passed CI and run on a non-production host | `GET /releases` filtered to prereleases matching the beta pattern | Offered to opted-in installs only, never applied automatically |
| **NIGHTLY** | Developers, the demo hosts | The rolling `nightly` prerelease / `:nightly` image | `nightly.yml` | **Never offered to a production hotel** |

Rules:

- **STABLE is the default and the only channel a fresh installation starts on.**
- **BETA is a per-installation setting written by the administrator**, shown on the update
  screen as a plain warning ("this install receives releases before they are declared
  stable"). Leaving BETA does not downgrade: the install waits for a STABLE version higher
  than the one it runs.
- **NIGHTLY is not a selectable channel on a production installation.** An installation
  has a `deployment_kind` recorded at install time (`production` by default; the demo and
  nightly hosts are marked otherwise). The runner refuses channel `nightly` when
  `deployment_kind=production`, and there is no override in the UI. A rolling tag that is
  deleted and recreated every night (`nightly.yml:120-121`) has no stable identity a
  signature could attach to and no "previous version" to roll back to.
- **The existing escape hatch must be closed when the runner exists.** Today
  `KAMRA_BRANCH=develop install.sh update` rebuilds a hotel from `develop`
  (`install.sh:224-227`). "Never auto-deployed" is a convention until `install.sh update`
  itself refuses a non-tag ref on a production install.
- **Soak before promotion (proposal):** a version reaches STABLE only after a minimum
  period as a BETA prerelease with no open regression. The period is a release-policy
  decision; this document does not pick a number.

**What must change for these channels to exist** (none of it done):

- BETA does not exist. `release-please-config.json` has no prerelease configuration, so no
  `-beta.N` tag is ever produced. Producing them is pipeline work.
- `health.py`'s `_parse_semver` (`:31-36`) discards the prerelease suffix:
  `2.6.6-beta.1` and `2.6.6` compare **equal**. Channel-aware comparison needs a
  prerelease-aware ordering (`2.6.6-beta.1 < 2.6.6`). Without it a BETA install is told it
  is up to date on the stable release it should be offered.
- `/releases/latest` excludes prereleases by design, which is correct for STABLE and
  means BETA needs a second query (`/releases`), with the same 1-hour cache and the same
  unauthenticated rate limit (shared by every install behind one NAT).

---

## 4. How an installation discovers an update

Build on `health.py`; do not add a second discovery mechanism.

**Today:** `system_health()` calls `_fetch_github_latest()`, which hits `releases/latest`,
caches for `CACHE_TTL = 3600`, and `_version_check()` turns the semver comparison into
`passed / attention / info`. That is the discovery.

**Design:**

1. **`_fetch_github_latest()` gains a `channel` argument** and, for BETA, the second query
   above. The cache key includes the channel. The 1-hour TTL stays.
2. **An advertised release is not an available update until its signed manifest is
   found.** After reading the tag, discovery requests `release-manifest.json` and its
   signature from that release's assets. No manifest means the release is reported as
   "published, not yet installable", not as an update. This closes the publication race in
   §1 item 7: the manifest is the **last** artifact uploaded, after the image push
   succeeds, so its existence means the image exists.
3. **The GitHub API response is advisory and untrusted.** It is used to find the manifest
   and nothing else. Whether an update exists, what it contains and what it requires is
   decided from the **verified** manifest only (§6). A tampered API response can at worst
   hide an update or point at a manifest that then fails verification.
4. **The in-app check stays read-only.** `/kamra/health` shows "Update available" with the
   verified facts (to-version, severity, migration class, whether rollback is
   application-only or needs a restore) and tells the administrator to run the host-side
   command. It executes nothing. `system_health()["upgrade"]` currently hands out a bare
   `bench` command line (`health.py:484-488`); that block should be replaced by the runner
   command, because the bench one-liner skips every gate in this document.
5. **Offline tolerance.** If GitHub is unreachable (`ok: False`, already handled at
   `health.py:67-75`), discovery reports "could not check" as `info`, never as "up to
   date", and shows how stale the last successful check is.
6. **Which feed an installation follows is not settled.** `health.py:24` hard-codes
   `Kamra-PMS/kamra-pms`. `docs/algeria/VERSIONING.md` describes a downstream `ziri-v*`
   tag line and a distribution version independent of the core version. If ZIRI
   installations follow ZIRI releases, `GITHUB_REPO` and the tag pattern become
   per-distribution configuration and the manifest carries **both** version numbers.
   Decision D1, §11.

---

## 5. Release metadata the version number cannot carry

`release-please-config.json:7` sets `always-bump-patch`. `2.6.4 → 2.6.5` may be a security
fix, a typo, or the whole banquet module; the audit records that the number cannot tell the
administrator which. `release-please.yml:6-7` notes that a `Release-As:` commit footer can
force a minor or major, so a workaround exists, but it is manual and unenforced.

This design does **not** change the bump policy (a release-policy decision for the owner,
recorded in the audit). It puts the meaning *beside* the number, in the manifest:

| Field | Values | Set by |
| --- | --- | --- |
| `severity` | `security` · `fix` · `feature` · `breaking` | A human, in the release PR |
| `migration.class` | `M0` · `M1` · `M2` · `M3` (below) | A human, checked by CI |
| `migration.patches_added` | Ordered list of new entries in `kamra/patches.txt` | **Derived by CI** by diffing `patches.txt` between the previous tag and this one |
| `migration.rollback_mode` | `app-only` · `restore-required` | Derived from `class` |
| `requires_operator_action` | free text, may be empty | A human |

Migration classes (the unit the rollback design turns on; reasoning in `ROLLBACK.md` §3-4):

| Class | Meaning | Example from `kamra/patches/` |
| --- | --- | --- |
| **M0** | No new patch, no DocType/schema change | — |
| **M1** | Additive: new columns/DocTypes, plus backfills that write **only blank values** | `v28`, `v29`, `v36`, `v37` |
| **M2** | Rewrites or deletes existing rows, or overwrites values unconditionally | `v24`, `v34.keep_existing_privacy_settings`, `v35` |
| **M3** | Destroys information that exists nowhere else (drops a column or table, narrows a type, merges records) or changes the DB engine / Frappe major | none in the current patches |

Two safeguards, because a human label is the weak point:

- CI computes `patches_added` mechanically and **fails the release** if it differs from the
  manifest. A human cannot silently under-declare the patch list.
- **An unclassified or missing `migration.class` is treated as `M3`.** The default is the
  most cautious reading.

---

## 6. Update package integrity

### What "the package" is

There is no package today. The design defines three things that travel together:

1. **`release-manifest.json`** — the signed statement of what this release is.
2. **`release-manifest.json.sig`** — detached signature over the manifest's exact bytes,
   plus a published SHA-256 of the manifest.
3. **The image**, referenced **by digest** in the manifest, never by tag.

Proposed manifest (the schema is a proposal; nothing produces it):

```json
{
  "schema": 1,
  "product": "ziri-pms",
  "version": "2.6.6",
  "distribution_version": null,
  "channel": "stable",
  "released_at": "2026-10-01T00:00:00Z",
  "severity": "fix",
  "min_from_version": "2.6.0",
  "required_stops": [],
  "source": { "repo": "Kamra-PMS/kamra-pms", "tag": "v2.6.6", "commit": "<40-hex>" },
  "image":  { "ref": "ghcr.io/kamra-pms/kamra", "digest": "sha256:<64-hex>" },
  "runner": { "sha256": "<64-hex>" },
  "frappe": { "version": "16.25.0" },
  "db_engine": { "mariadb": "11.8" },
  "migration": {
    "class": "M1",
    "rollback_mode": "app-only",
    "patches_added": ["kamra.patches.v38.example"]
  },
  "requires_operator_action": ""
}
```

### Checksum and signature do different jobs

- **Checksum (SHA-256)** detects corruption and truncation: a half-downloaded manifest, a
  flipped bit. It proves nothing about *who* made the file. A checksum served from the same
  place as the file is replaced together with the file.
- **Signature** authenticates origin. Only this shows the manifest came from the release
  owner.

The installation requires **both**, in this order, and refuses on the first failure:

1. SHA-256 of the downloaded manifest matches the published checksum.
2. The detached signature verifies against a **public key pinned on the installation**.
3. The manifest is internally consistent and its fields are checked against the
   installation (§7).
4. The image pulled by digest has exactly the digest the manifest names. A different digest
   is a refusal.

### Proposed signing scheme, and its trade-off

- **Detached Ed25519 signature (minisign-style), public key pinned at install time** under
  `/opt/kamra/trust/`. It verifies offline, which matters for hotels with intermittent
  connectivity.
- Alternative considered: **Sigstore/cosign keyless**, which binds a signature to the
  GitHub Actions workflow identity and needs no key custody. It needs network access to
  transparency-log infrastructure to verify, and its trust root is "our CI": a CI
  compromise signs malicious releases with a perfectly valid identity.
- **Key custody decides the real security level.** If the private key is a GitHub Actions
  secret, building and signing share one trust domain and the signature adds little beyond
  tamper-evidence in transit. If STABLE manifests are signed by a person on a separate
  machine after the draft release PR is reviewed (the repository already has
  `draft-pull-request: true`), a CI compromise cannot ship to hotels without that second
  step. **Recommended: offline human signing for STABLE; a CI-held key is acceptable for
  BETA.** Decision D2.
- **Key rotation:** the pinned file is a *set* of trusted keys with validity ranges. A
  rotation manifest signed by a currently trusted key adds the next key. Losing the only
  signing key with no pre-distributed successor strands every installation; accept that only
  with a published manual re-pin procedure.
- **First-install trust is trust-on-first-use.** The pinned key arrives with the installer,
  and the installer is fetched with `curl … | bash` from `raw.githubusercontent.com`
  (`install.sh:4`). Signing releases does not make the *first* install verified. That link
  cannot be closed without a separately distributed fingerprint (on the vendor site, on
  paper at handover).

### The unverified path that exists today, and what replaces it

- `install_self` (`install.sh:197-205`) downloads `install.sh` from `main` and installs it
  executable, unverified. In the new update path the runner is **a file referenced from the
  verified manifest by SHA-256**. The running, previously trusted runner verifies the new
  one and only then replaces itself, atomically. A runner never executes a runner it has not
  verified.
- Downloaded content is staged in `$UPD/staging/`, directory mode 700, files mode 600 (no
  executable bit), until the Verify step passes. The manifest is parsed as data by a strict
  JSON parser and is never passed through a shell or `eval`.

### Image: pull by digest, or rebuild?

`install.sh` builds the image on the customer's machine (`install.sh:164-176`; the
comment at `install.sh:9` says ghcr is kept private for ZIRI's own hosts). A signature
over the `kamra` source commit does **not** cover a locally built image, because Frappe
(`version-16`) and `payments` (`develop`) are fetched fresh and unpinned (§1 item 3).

- **Preferred:** STABLE installs `docker pull ghcr.io/kamra-pms/kamra@sha256:<digest>`.
  What was tested in CI and BETA is byte-identical to what runs in the hotel, and a
  per-version image exists locally for rollback. **This requires the ghcr package to be
  readable by customers (or a credential distributed to them): decision D3.**
- **Fallback, reduced assurance:** local build from the signed `source.commit`. The runner
  checks that the fetched tag resolves to `source.commit`, labels the run
  "source-verified, build-unverified", and shows that label to the administrator. The
  build is not reproducible and can differ from what was tested.

---

## 7. The pre-flight gate

**Rule: any critical failure means DO NOT UPDATE.** Not "update with a warning", not
"update if the administrator insists". A critical check that errors, times out, or returns
something unparsable counts as failed. Warnings do not block, but are shown and must be
acknowledged by name before the run continues.

The gate runs in two stages because one check (backup validity) needs the backup the
sequence takes, and taking a backup on a full disk can itself take the site down:

- **Gate A**, before the backup: *can a backup safely be taken at all?*
- **Gate B**, after the backup, before anything is downloaded or changed.

Gate A is re-run in abbreviated form immediately before maintenance mode (§8, step 7): a
gap of hours between the administrator confirming and the quiesce is exactly when a disk
fills or a container dies.

### Gate A

| Check | How (host runner) | Critical when | In `health.py` today |
| --- | --- | --- | --- |
| Disk space | `df -P` on the Docker data root **and** the backup destination | free < required (below) | Partly: `_disk_check` measures the *site path* only; `failed` below 2 GB or 5 % free (`:103-122`) |
| Database health | `<COMPOSE> exec -T db healthcheck.sh --connect --innodb_initialized` **and** `<COMPOSE> exec -T backend bench --site $SITE mariadb -e "SELECT 1"` **(VERIFY** the `mariadb` subcommand) | either fails | Partly: `_database_check` runs `select 1` (`:317-322`); it does not run the container healthcheck |
| Container health | `<COMPOSE> ps` plus `docker inspect -f '{{.State.Status}} {{.State.Health.Status}}'` per service: `db`, `redis-cache`, `redis-queue`, `backend`, `frontend`, `websocket`, `queue-short`, `queue-long`, `scheduler` running; `configurator` exited 0 | any expected service not running, `db` not healthy, `configurator` not exit 0 | **No.** The audit lists container state as absent |
| Redis | `<COMPOSE> exec -T redis-cache redis-cli ping` and `<COMPOSE> exec -T redis-queue redis-cli ping` | either is not `PONG` | Partly: `_redis_check` round-trips the cache only (`:222-235`); `redis-queue` is not checked |
| Not mid-work | no night-audit run in progress; queue depth recorded as the baseline | night audit running (critical); queue depth above a threshold (warning) | Partly: queue depth in `_workers_check` (`:238-275`); night-audit state not checked |

**Disk requirement (proposed starting rule, not measured):**
`free >= image_size_from_manifest + 2 x size_of_last_successful_backup + 20 % headroom` on
the filesystem holding Docker's data root, and `free >= 2 x size_of_last_successful_backup`
on the backup destination. The factor 2 and the 20 % are placeholders (two full backups,
B1 and B2, plus the new image are held at once) and must be tuned on real installations.
The existing `failed` floor (2 GB / 5 %) remains a hard minimum underneath.

### Gate B

| Check | How | Critical when | In `health.py` today |
| --- | --- | --- | --- |
| Backup validity | The run's B1 (§8, step 2): `gzip -t` on the SQL dump; `tar -tzf` on each files archive; non-zero size; size within a sane ratio of the previous backup (warning if under 50 %); sha256 recorded; a copy present **off the `sites` volume** | any structural test fails or the off-volume copy is missing | **No.** `_backup_check` reports age only and says so: "this does not prove it can be restored" (`:278-314`) |
| Backup freshness | B1 was taken within this run, not "some backup from last night" | B1 absent | Age only; never `failed`, by design |
| Restore ever proven | A recorded successful restore test for this installation (`BACKUP.md` §5) | never critical; **warning** with explicit acknowledgment if none is recorded | **No** |
| Version compatibility | `installed >= min_from_version`; `to > installed` (no downgrade); no `required_stops` entry skipped; channel allowed for this `deployment_kind`; manifest Frappe version compatible with the running Frappe; `db_engine.mariadb` equals the running `db` image's major.minor | any fails | Partly: `_version_check`, `_frappe_check`, informational only |
| Migration compatibility | (a) every `patches_added` entry is absent from `tabPatch Log`; (b) **every patch already in `tabPatch Log` appears in the target release's `patches.txt`**, because a patch the target does not know means the site ran newer or forked code; (c) `migration.class` present | (b) fails; (c) missing is not a refusal but forces class `M3` and `restore-required` | **No** |
| Licence validity | Entitlement check against a licence record | see below | **Cannot exist**: no licence system (audit, Gaps) |
| Manifest verified | §6 steps 1-4 passed | any fails | **No** |

**Licence validity, stated honestly.** No licence system exists, so this check returns
`skipped: not implemented`, and the admin screen shows exactly that. It is never rendered as
passed. When a licence system is designed, the recommended gate rule is: an expired licence
may block **feature** updates; it must never block a `severity: security` update, and it
must never block a rollback. Whether to gate at all is a commercial decision outside this
document. `docs/algeria/LICENSING.md` documents AGPL-3.0 §13 obligations, not an entitlement
system, and must not be mistaken for one.

**Why (b) in migration compatibility matters:** `tabPatch Log` is keyed by the dotted path
of the patch. `v36` and `v37` exist in this distribution; if an upstream release ever ships
a *different* `kamra.patches.v36.*` with the same name, the log would claim it already ran.
The path-based key is a known sharp edge for a downstream line, and (b) is where a lineage
mismatch becomes visible before any data is touched.

---

## 8. The update sequence

Each step names what the administrator sees and whether rollback is available
(definitions in §9).

> **Deviations from the order in the brief, and why.** The brief lists *migrate* before
> *update app*. In this stack the patches ship **inside the image**, so migrating before the
> new image runs would execute the **old** release's patches. The image is applied first,
> then migrated, which is also what `install.sh` does today (`:232`, then `:235`). Two more
> deliberate changes: a disk/DB/container gate runs **before** the backup (a backup on a full
> disk can crash the site), and a **second, quiesced backup** is the authoritative rollback
> point (a backup taken while the hotel is live loses whatever is written after it). Neither
> contradicts the intent of the brief; both fix a flaw in a literal reading of its order.

### Step 0 — Discover (read-only)
`/kamra/health` and `kamra-update check` show installed version, available version, channel,
`severity`, `migration.class`, and "rollback would be: application image / database restore
required". *Rollback:* n/a, nothing has changed.

### Step 1 — Gate A (can a backup be taken?)
Disk, database, containers, Redis, not-mid-work (§7). A critical failure stops the run
here. *Rollback:* n/a.

### Step 2 — Backup B1 (online)
```bash
<COMPOSE> exec -T backend bench --site "$SITE" backup --with-files
# copy OFF the sites volume; container name and paths per BACKUP.md §2 (VERIFY)
docker cp kamra-backend-1:/home/frappe/frappe-bench/sites/$SITE/private/backups/. "$UPD/backup-b1/"
sha256sum "$UPD"/backup-b1/* > "$UPD/backup-b1.sha256"
```
Also copy `site_config.json`, `kamra.env`, `apps.json` and the compose files into
`$UPD/config/` (mode 600): the encryption key and the DB password are *not* guaranteed to be
in Frappe's backup (`BACKUP.md` §3). B1 is taken **while the hotel is live**, so restoring it
alone would lose whatever was written after it. It proves the backup machinery works before
anything is disturbed, and is a fallback. It is not the rollback point.
*Admin sees:* "Backup B1 taken, `<id>`, `<size>`, `<duration>`". *Rollback:* n/a.

### Step 3 — Gate B
Backup validity, version and migration compatibility, licence, restore-ever-proven (§7).
Critical failure stops the run. Warnings are listed and acknowledged individually.
*Admin sees:* the full pre-flight table, each row `passed / warning / FAILED /
skipped-not-implemented`, and one line: **"Update permitted"** or **"DO NOT UPDATE: n
critical failure(s)"**.

### Step 4 — Download
Fetch manifest, signature, checksum and (if changed) the runner into `$UPD/staging/`; then
`docker pull ghcr.io/kamra-pms/kamra@sha256:<digest>` (or the fallback source fetch).
Nothing is executed. The **current** image is retagged immutably now:
```bash
docker tag kamra:<current-tag> kamra:rollback-<from_version>
```
*Admin sees:* "Downloaded 2.6.6 (`<size>`). Previous image kept as `kamra:rollback-2.6.5`."
*Rollback:* n/a.

### Step 5 — Verify
§6 steps 1-4. Failure deletes `$UPD/staging/`, records the reason, stops. A failed
verification is **not retried automatically against a different mirror or fallback**:
silent fallback is how a downgrade attack succeeds.
*Admin sees:* "Checksum OK · Signature OK (key `<fingerprint>`) · Image digest OK".

### Step 6 — Administrator confirmation (the human gate)
One summary, **before any disruption**: from → to, severity, migration class, patches that
will run, the rollback statement (§9), estimated downtime **derived from B1's measured
duration** (not a guess), and what stops working during maintenance. For classes `M2`/`M3`
the confirmation text includes: *"Reverting this update after the hotel resumes work means
restoring a backup and losing everything entered since."*

### Step 7 — Quiesce, then Backup B2 (the rollback point)
```bash
# re-run Gate A abbreviated; a critical failure aborts here with nothing changed
<COMPOSE> exec -T backend bench --site "$SITE" set-maintenance-mode on     # (VERIFY)
<COMPOSE> stop scheduler queue-short queue-long
# drain in-flight jobs; record redis-queue depth and the row-count baseline for step 11
<COMPOSE> exec -T backend bench --site "$SITE" backup --with-files
# copy off-volume; sha256; gzip -t; tar -tzf   -> B2
```
B2 is taken with writes blocked and the schedulers stopped, so restoring it later loses
**no data**. B2 is the "backup ID" the administrator is shown. If B2 fails validation the
run **aborts here**: maintenance off, workers restarted, nothing was modified, nothing to
roll back.
*Admin sees:* "Maintenance mode ON. Backup B2 `<id>` validated (gzip OK, archives OK, copy
off-volume OK, sha256 `<…>`)." *Rollback:* **available, full** (restoring B2 loses nothing;
the previous image is retained).

### Step 8 — Apply the new image
Only the application services are recreated; `db`, `redis-cache` and `redis-queue` are not
touched (unlike `install.sh:232`):
```bash
cp -p /opt/kamra/kamra.env "$UPD/config/kamra.env.before"
sed -i "s/^CUSTOM_TAG=.*/CUSTOM_TAG=<new-tag>/; s/^ERPNEXT_VERSION=.*/ERPNEXT_VERSION=<new-tag>/" /opt/kamra/kamra.env
<COMPOSE> up -d --force-recreate configurator backend frontend websocket
<COMPOSE> restart frontend     # nginx caches backend's IP; see the 502 row in deploy/linux/README.md
```
`queue-short`, `queue-long` and `scheduler` stay **stopped**. New-code workers must not
start sending emails or calling payment gateways before the migration and the checks are
known good; those effects cannot be restored away (`ROLLBACK.md` §6).
*Trigger if this fails:* application fails to start → `ROLLBACK.md` Case B.
*Admin sees:* "New image running. Previous image `kamra:rollback-2.6.5` retained."
*Rollback:* **available, full.**

### Step 9 — Migrate
```bash
<COMPOSE> exec -T backend bench --site "$SITE" migrate        # one named site, never --site all
<COMPOSE> exec -T backend bench --site "$SITE" clear-cache
```
Capture the exit status, the full output, and the `tabPatch Log` delta (the patches that
ran). Frappe patches are forward-only and MariaDB DDL does not roll back, so a failure leaves
the schema **partly changed** (`ROLLBACK.md` §3). The response to a failed migrate is
decided by `ROLLBACK.md` §5, not retried here.
*Admin sees:* "Migration: OK, 1 patch applied (`kamra.patches.v38.example`)" or "Migration
FAILED at `<patch>`: see rollback". *Rollback:* **available, full** until the commit point
(step 13), provided B2 is intact.

### Step 10 — Health check, phase 1 (application up, workers still stopped)
Reuse `system_health()` (`health.py:437`) plus the §7 checks it lacks. Phase 1 covers:
`backend` answers; DB responds; both Redis; installed apps (`frappe`, `kamra`); version reads
the new `kamra.__version__`; container states. A short bounded retry (for example three
tries 20 s apart, proposed) absorbs warm-up; it is not a loop until green.
Any `failed` is a rollback trigger. `attention` is shown, not blocking.

### Step 11 — Smoke test
Read-only and run on the server, so it needs no credentials:
```bash
curl -fsS http://localhost:${HTTP_PUBLISH_PORT}/api/method/ping                       # expects pong (VERIFY)
curl -fsS -o /dev/null -w '%{http_code}' http://localhost:${HTTP_PUBLISH_PORT}/kamra  # expects 200
# data invariants: counts must equal the step-7 baseline (writes were blocked)
<COMPOSE> exec -T backend bench --site "$SITE" mariadb -e \
  "SELECT 'reservation',COUNT(*) FROM \`tabReservation\` UNION ALL SELECT 'property',COUNT(*) FROM \`tabProperty\` UNION ALL SELECT 'folio_charge',COUNT(*) FROM \`tabFolio Charge\`"    # (VERIFY)
```
The smoke test also fetches one built asset URL taken from the served `/kamra` page
(`ci.yml:31-34` asserts the SPA references `/assets/kamra/frontend/assets/`). The VPS deploy
script syncs assets from the new image into the `sites` volume (`nightly.yml:188-194`);
`install.sh update` does not, and whether the customer path needs it was not determined, so
this probe is the check that would catch stale assets.

A lower count than the baseline is data loss. A higher count under maintenance mode is
unexplained. Both are rollback triggers. The CI checks (`kamra.scripts.eval_harness`,
`kamra.scripts.frontdesk_eval`) are **not** run here: they create records and were written
for a throwaway CI site (`ci.yml:102-122`); running them on a hotel's production site would
be a change, not a test.

### Step 12 — Start workers, health check phase 2
```bash
<COMPOSE> up -d queue-short queue-long scheduler
```
Phase 2 re-runs the full health set including `_workers_check` and `_scheduler_check`. This
is the first moment new-code background jobs can run.

### Step 13 — Commit (the point of no return for restore-based rollback)
The administrator confirms and maintenance mode is lifted:
```bash
<COMPOSE> exec -T backend bench --site "$SITE" set-maintenance-mode off     # (VERIFY)
```
The **commit point** is the earlier of: first start of `scheduler`/`queue-*` on the new
version, or lifting maintenance mode. From then on new data exists that B2 does not contain.
The run record is finalised; B2 and the rollback image are retained (`ROLLBACK.md` §7).
*Rollback:* **changes character**, see §9.

---

## 9. What the administrator sees

### The `Update Run` record (proposed)

The host runner writes a status file at every step (`$UPD/status.json`) and imports it into
the application after step 13 (or after a rollback, once the site is back). **The Frappe UI
is not a reliable progress display during steps 7-12**: `backend` and `frontend` are being
recreated and the site is in maintenance mode. Live progress is on the terminal that started
the run and in `$UPD/run.log`; the in-app record is the history afterwards.

| Field | Content |
| --- | --- |
| `run_id` | e.g. `20261001T0300Z-2.6.5-to-2.6.6` |
| `state` | `gated` · `refused` · `backed-up` · `verified` · `maintenance` · `applied` · `migrated` · `health-1-ok` · `smoke-ok` · `committed` · `failed` · `rolled-back-app` · `rolled-back-restore` · `rollback-failed` |
| `previous_version`, `new_version` | `2.6.5`, `2.6.6` |
| `channel`, `severity`, `migration_class` | `stable`, `fix`, `M1` |
| `backup_id` | B2 file-set name, sha256, and the validation methods that passed |
| `previous_image`, `new_image` | digest of each |
| `migration_result` | `not-run` · `ok` · `failed`, with patches applied and, on failure, the failing patch and the first error line |
| `health_result` | per-check status for phase 1 and phase 2 |
| `smoke_result` | each probe and baseline-versus-after counts |
| `rollback_available` | `application-only` · `database-restore` · `both` · `none`, **with the reason as a sentence** |
| `data_at_risk` | After the commit point: rows created since B2 that a restore would lose |
| `log_path` | `$UPD/run.log` |

### "Rollback available" over the lifetime of a run

| Phase | Application image rollback | Database restore | Cost of using it |
| --- | --- | --- | --- |
| Steps 0-6 | n/a, nothing changed | n/a | none; abort is free |
| Step 7 (B2 validated) to step 12 | yes | yes, to B2 | **no data lost** (writes blocked, workers stopped); costs downtime proportional to DB size, **unmeasured** |
| After step 13, class M0/M1 | yes, plausible; must be rehearsed per release | yes | a restore loses everything since B2 |
| After step 13, class M2/M3 | **not safe** (old code on rewritten data) | yes, the only route to the old version | a restore loses everything since B2; forward-fix is the alternative |
| B2 missing or invalid | n/a | no | the run must have aborted at step 7; it never reaches apply in this state |

"Available" is displayed only when the thing it names was checked present and validated *in
this run*: the image exists in the local image store, B2's validation passed. It is not a
default.

### What each step prints (illustrative mock-up, not real output)

```
ZIRI PMS update            2.6.5  ->  2.6.6      channel: stable    severity: fix
 [1/13] Gate A ............ OK   disk 41 GB free, db healthy, 9/9 services up, redis OK
 [2/13] Backup B1 ......... OK   id 20261001_0300  1.4 GB  gzip OK
 [3/13] Gate B ............ OK   2 warnings acknowledged: no restore test recorded; licence check skipped (not implemented)
 [5/13] Verify ............ OK   checksum, signature (key 3F2A..91), image digest
 [6/13] Confirm ........... migration class M1; rollback: application image, or database restore (no data lost before commit)
 [7/13] Quiesce + B2 ...... OK   maintenance ON, backup B2 validated and copied off-volume
 [9/13] Migrate ........... OK   1 patch: kamra.patches.v38.example
[10/13] Health (1) ........ OK
[11/13] Smoke ............. OK   counts identical to baseline
[12/13] Health (2) ........ OK   workers up, scheduler running
[13/13] Commit ............ maintenance OFF. Rollback now: image only, or restore (loses data entered after 03:14).
```

---

## 10. Changes this design requires (none are done)

1. **Host-side runner** (`kamra-update`, name provisional) replacing `install.sh update`.
   `install.sh update` should delegate to it, or refuse on a production install.
2. **Release pipeline:** generate `release-manifest.json` (with CI-derived `patches_added`)
   and a checksum, attach them to the GitHub Release as the **last** step after the image
   push, and sign. Today `release.yml` attaches nothing.
3. **Stop treating `:latest` as an update target.** The runner never uses a tag; `:latest`
   may remain for humans.
4. **Per-version image tags** in `kamra.env` (`CUSTOM_TAG=2.6.6`) instead of the constant
   `local`.
5. **`health.py`:** channel-aware, prerelease-aware discovery; manifest fetch; replace the
   `upgrade.bench` hint (`:484-488`); add `redis-queue`, backup *validity*, and (when it
   exists) licence. Container state cannot be read from inside `backend` without the Docker
   socket, so those checks belong to the host runner and are reported *to* the app, not
   collected by it.
6. **`Update Run` DocType** and a whitelisted receiver for the runner's final report.
7. **Guard `install.sh`:** refuse a non-tag `KAMRA_BRANCH` on `deployment_kind=production`;
   remove the unverified `install_self` download from the update path.
8. **Prune policy:** never `docker system prune -af` on a customer host; protect the
   `kamra:rollback-*` images (`ROLLBACK.md` §7).

---

## 11. Open decisions

| # | Decision | Why it is open |
| --- | --- | --- |
| D1 | Which release feed and tag line do ZIRI installations follow, upstream `v*` or ZIRI `ziri-v*`? Does the manifest carry the distribution version? | `health.py:24` hard-codes upstream; `VERSIONING.md` says the two lines differ |
| D2 | Who holds the signing key, and where? Offline human for STABLE versus CI-held | Decides whether the signature defends against a CI compromise |
| D3 | Is the ghcr image readable by customers, or does the local build remain the customer path? | Decides whether images can be pinned by digest and retained per version |
| D4 | Change `always-bump-patch`? | The manifest compensates; it does not give the number meaning |
| D5 | Soak period between BETA and STABLE | Release policy |
| D6 | Licence gating policy once a licence system exists | §7 |

---

## 12. What this does not cover / has not been tested

**Nothing in this document has been run.** It is a design written by reading the
repository.

- **No update was performed, simulated or timed.** Downtime, backup duration, backup size,
  restore duration and the proposed disk factors are unmeasured; every threshold marked
  "proposed" is a placeholder.
- **Commands marked (VERIFY) were not run.** That includes `bench set-maintenance-mode`,
  `bench --site … mariadb`, the `/api/method/ping` probe, `healthcheck.sh` invoked through
  `compose exec`, and the container name `kamra-backend-1`. The compose stack has only run on
  Docker Desktop over WSL2 on one machine, never on the Linux server it is written for
  (audit, "What this document does not establish").
- **Whether maintenance mode blocks the Administrator, API tokens or the websocket** was not
  determined, so "writes are blocked" in step 7 is the intent, not an established fact. The
  step 11 row-count baseline is the check that would catch the assumption being wrong.
- **The manifest, signature scheme and `Update Run` schema are proposals.** No key exists,
  nothing is signed, and no CI step produces a manifest.
- **Licence validity** cannot be designed further until a licence or entitlement system
  exists. The check is specified only as "skipped, not implemented".
- **Multi-site benches** are out of scope. `install.sh` assumes `--site all`; this design
  assumes one production site.
- **Windows (Docker Desktop over WSL2) specifics** are not designed here: the runner under
  WSL, Task Scheduler, Docker Desktop being stopped. `BACKUP.md` §6 shows the shape of the
  problem.
- **Frappe, MariaDB and Redis image upgrades** are not an application update. A changed `db`
  image (`MARIADB_AUTO_UPGRADE: 1` can rewrite the data directory) is refused by the gate and
  needs its own procedure, which does not exist.
- **Installations on a custom fork or with local patches** are not handled. The
  migration-compatibility check (b) will refuse some of them; others will pass it.
- **Offline or air-gapped update** (delivering manifest, signature and an image archive by
  removable media) is a natural extension of the same verification and is not designed.
- **No security review of the signing and trust design has been done.**
