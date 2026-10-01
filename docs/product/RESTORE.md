# Restore and backup verification - design

**Status: design. Nothing in this document has been executed against a running
stack by its author.** Every command is written against the real service names
(`backend`, `db`, `redis-cache`, `redis-queue`, `configurator`, `scheduler`,
`queue-short`, `queue-long`, `websocket`, `frontend`) and volumes (`sites`,
`db-data`, `redis-queue-data`) but is unrun. **[confirm]** marks a Frappe flag
or behaviour this repository cannot show - read it off `--help` on the installed
image first, as [`../algeria/BACKUP.md`](../algeria/BACKUP.md) section 4 demands.
The verification described in section 2 does not exist as a tool yet; until it
has been built **and seen to fail on bad input** (section 2.5) it must not be
reported as a passing check.

**The governing rule, from the audit
([`PRODUCTIZATION_AUDIT.md`](PRODUCTIZATION_AUDIT.md), "No backup verification
anywhere"): a backup whose restoration has never been exercised is not a
backup.** A file that exists, is the right size and has a recent timestamp is
evidence of nothing. This document defines a test that restores the data into a
disposable MariaDB and interrogates what came back.

Companions: what is backed up and where -
[`BACKUP.md`](BACKUP.md); what breaks and how fast you recover -
[`DISASTER_RECOVERY.md`](DISASTER_RECOVERY.md). The mechanics of reaching
`bench` through compose and the manual post-restore checklist are in
`algeria/BACKUP.md` sections 1 and 4; they are referenced, not repeated.
`DC` means the compose invocation of your install (`algeria/BACKUP.md` section 1,
or `docker compose` in `deploy/linux/`).

Database is **MariaDB 11.8**. Tools: `bench`, `mariadb`, `zcat`. No `psql`.

---

## 1. Rules before any restore - real or test

1. **A restored copy can talk to the real world.** `kamra/hooks.py` schedules,
   among others, `push_all_ari` hourly (channel manager availability push),
   `run_prearrival_outreach` daily at 09:00 (messages to upcoming arrivals) and
   `run_banquet_reminders`. A restored site that holds decryptable gateway,
   SMTP and channel credentials, with the `scheduler` and workers running, will
   push stale availability to real OTAs and contact real guests. This is not
   hypothetical; it is the consequence of restoring the key correctly.
   **Therefore:** in any test or any second copy, do not start `scheduler`,
   `queue-short`, `queue-long` or `websocket`, and cut off egress (section 2.4).
   In a real restore onto a new host, the old host must be confirmed off before
   the new `scheduler` starts.
2. **A restore overwrites the target.** Take a safety copy of the current state
   first, even if broken (section 4.1).
3. **Never test on the live site.** Test sites are separate and destroyed.
4. **`down -v` is destructive and a typo is enough.** Anything that tears down
   a test stack must be given an explicit project name different from the
   production one, and must print the volumes it will delete first (section
   2.6). `docker compose down -v` in the wrong project directory destroys the
   hotel (`deploy/linux/README.md`).
5. **A test restore is a second copy of guest personal data** (Law 18-07). Run
   it on a machine at least as well protected as the server, and destroy it.
6. **Project name matters.** `install.sh` uses `--project-name kamra`; a plain
   `docker compose` in `deploy/linux/` uses the directory name. Volume names
   follow. Run `docker volume ls` and write down the real names before relying
   on any of them.

---

## 2. Backup verification

Two levels. They answer different questions and cost different amounts, so they
run at different frequencies (section 5).

| | Level 1 - SQL | Level 2 - Stack |
| --- | --- | --- |
| Needs | Docker and the set. Not the app image | The app image, a second compose project |
| Disposable MariaDB | A bare `mariadb:11.8` container | The `db` service of a `kamra-verify` project |
| Proves | The dump is complete, imports cleanly and contains what the manifest says | Everything in Level 1, plus: files restored, the encryption key works, `migrate` succeeds on current code |
| Does not prove | Files, the key, application compatibility | That a human can operate it at 2am; load; the host-loss path |
| Run on | Every full set; newest intra-day set daily | Monthly; before an update; before handover |

Both levels consume a **manifest** written at backup time (`BACKUP.md` section
3): table count, exact per-table row counts taken just before the dump,
watermarks, `bench version`, image ID, canary ciphertext, checksums. Without it
the checks below degrade to "it imported", which is the weak claim this
document exists to avoid; a set without a manifest is reported **UNVERIFIABLE**,
never PASS.

### 2.1 Level 1 - SQL-only restore into a throwaway MariaDB

Use the same character-set flags as production's `db` service
(`deploy/linux/docker-compose.yml`) or the import may behave differently from
the real thing, which would make the test lie.

```bash
set -euo pipefail
V_PW=$(openssl rand -hex 16)

docker run -d --name kamra-verify-db --network none \
  -e MARIADB_ROOT_PASSWORD="$V_PW" -e MARIADB_DATABASE=verify \
  mariadb:11.8 \
  --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci \
  --skip-character-set-client-handshake

# wait for the FINAL server, not the init-time one (the entrypoint starts two)
until [ "$(docker logs kamra-verify-db 2>&1 | grep -c 'ready for connections')" -ge 2 ]; do sleep 2; done

zcat "$DUMP" | docker exec -i -e MYSQL_PWD="$V_PW" kamra-verify-db mariadb -uroot verify
```

(`--network none`: the container needs no network to import; `docker exec`
still works. The tag `mariadb:11.8` floats; prefer the exact version recorded
in the manifest.)

`set -o pipefail` is load-bearing: without it a truncated dump makes `zcat`
fail while the pipeline's last command reports success.

**Checks**, run against schema `verify`. Each is binary. "Reported" means the
number is printed, never that it passed:

| # | Check | FAIL when | Catches |
| --- | --- | --- | --- |
| 1 | `sha256sum -c SHA256SUMS` on the set as fetched from the destination | any mismatch | Corruption or truncation in storage or transit. Not a restore |
| 2 | `gzip -t` on the dump | non-zero | Truncated/corrupt archive |
| 3 | The import pipeline exit codes | any non-zero, or any `ERROR` on stderr | Syntax-level damage, partial dump |
| 4 | Table count equals the manifest | different | Missing tables from a partial dump |
| 5 | Per-table exact `COUNT(*)` against the manifest | a table is missing; or manifest > 0 and restored = 0; or restored < manifest for any table not on the churn allowlist | An import that stopped halfway, an emptied table, the wrong dump |
| 6 | Watermark: `MAX(modified)` on each designated table is `>=` the manifest's | older | A stale set, the wrong file picked up |

Generating the counts (same query on the live DB for the manifest, and on the
restored one for the check - production's schema name is the site's `db_name`
from `site_config.json`, not `verify`):

```sql
SELECT GROUP_CONCAT(
  CONCAT('SELECT ''', table_name, ''' AS t, COUNT(*) AS n FROM `', table_name, '`')
  SEPARATOR ' UNION ALL ')
FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE';
```

Run its output as a second query. Exact counts, not `information_schema`
estimates: `TABLE_ROWS` is approximate for InnoDB and would pass a lossy
import.

Notes on what the rules mean in practice:

- Counts are taken before the dump, and the site stays live, so a table may
  legitimately shrink between manifest and dump (expired sessions, a deleted
  draft). The **churn allowlist** names those tables. It is built from the first
  few runs, which **will** throw false alarms; that tuning is expected and is
  not a reason to loosen rule 5 for everything.
- The watermark tables are chosen at setup: tables that receive writes on
  every normal day. Which ones those are on a real property has not been
  determined.
- Check 5 can pass on a dump that is structurally complete but semantically
  wrong in a way no count shows. Level 1 cannot see that. Level 2 and a human
  can, to a degree (section 2.3).

**Deliberately omitted: `mariadb-check` / `CHECK TABLE`.** After a logical
import the tables were just written by the verifier's own server; checking
them validates the verifier's tablespace, not the backup. Including it would
add a green line that cannot detect a bad backup.

Teardown, always, including on failure (`trap` it): `docker rm -fv kamra-verify-db`.

### 2.2 Level 1 against the encrypted repository

If the destination is a restic repository (`BACKUP.md` section 6), Level 1 starts
by restoring a snapshot into a temporary directory and checking that directory
- so the encryption path with the host's password file is exercised by the same
run:

```bash
restic -r <repo> restore latest --tag full --target "$TMP"
restic -r <repo> check --read-data-subset=10%
```

`check --read-data-subset` samples repository blocks, so a different slice is
read each time you vary the subset; it is repository integrity, not a restore.
It does not replace checks 1-6. The temporary directory holds decrypted guest
data: mode 0700, removed in the same `trap`.

### 2.3 Level 2 - a disposable stack

A second compose project with the same file and the production **image**
(or, to test restore-onto-new-code, the candidate new image), its own volumes
and its own `DB_PASSWORD`. Prefer a different machine; the minimum spec in
`deploy/linux/README.md` is 4 GB RAM, and a second MariaDB plus backend on the
production host competes with the hotel.

Start only what `bench` needs. **Not** the scheduler, workers, websocket or
frontend (rule 1):

```bash
VDC="docker compose -p kamra-verify --env-file verify.env \
  -f docker-compose.yml -f verify.override.yml"     # verify.override.yml: section 2.4

$VDC up -d db redis-cache redis-queue configurator backend
$VDC ps        # configurator must be Exited (0), db healthy - same gate as production
```

Create a throwaway site with the flags `install.sh` itself uses
(`algeria/BACKUP.md` section 5), then restore into it:

```bash
$VDC exec -T backend bench new-site verify.localhost \
  --mariadb-user-host-login-scope='%' --no-mariadb-socket \
  --db-root-password "$V_PW" --admin-password "$(openssl rand -hex 12)" \
  --install-app payments --install-app kamra

$VDC cp ./set/. backend:/home/frappe/frappe-bench/sites/verify.localhost/private/backups/
$VDC exec -T backend bench --site verify.localhost set-config pause_scheduler 1   # [confirm key]

$VDC exec -T backend bench --site verify.localhost restore \
  sites/verify.localhost/private/backups/<ts>-<slug>-database.sql.gz \
  --with-public-files  sites/verify.localhost/private/backups/<ts>-<slug>-files.tar \
  --with-private-files sites/verify.localhost/private/backups/<ts>-<slug>-private-files.tar \
  --db-root-password "$V_PW" --force                       # all flags [confirm]
```

The container path `/home/frappe/frappe-bench/sites` is read from
`deploy/linux/docker-compose.yml`. The file names are Frappe's, to be listed on
the install, not assumed (`algeria/BACKUP.md` section 2).

Then, in this order, each a recorded check:

| # | Step | FAIL when |
| --- | --- | --- |
| 7 | Canary **before** fixing the key: decrypt must fail (section 3.2) | it *succeeds* - the control is broken |
| 8 | Set the original key from the set's `site_config.json`, then canary must succeed (section 3.1) | decryption fails or returns the wrong text |
| 9 | Checks 4-6 against the restored schema | as above |
| 10 | Files: every private file the DB references exists (below) | missing share exceeds `FILE_MISS_PCT` (start at 1%), or any table row refers to files and **none** exist |
| 11 | `bench --site verify.localhost migrate` | non-zero. Record its duration |
| 12 | Repeat 8 after `migrate` | fails (migrate must not disturb secrets) |

Check 10, the DB-to-files consistency test that catches "files archive never
restored", which is the failure `algeria/BACKUP.md` section 4 can only check by
a human looking at one image:

```bash
$VDC exec -T -e MYSQL_PWD="$V_PW" db mariadb -uroot -N -B <verify db_name> \
  -e "SELECT file_url FROM tabFile WHERE is_private=1 AND is_folder=0
        AND file_url LIKE '/private/files/%'" > urls.txt

$VDC exec -T backend bash -c '
  tot=0; miss=0
  while IFS= read -r u; do
    tot=$((tot+1)); [ -f "sites/verify.localhost${u}" ] || miss=$((miss+1))
  done
  echo "$tot referenced, $miss missing"' < urls.txt
```

URL-encoded names can produce false misses, and a file uploaded between the
dump and the archive is a true but harmless miss (`BACKUP.md` section 3);
the percentage threshold absorbs the second and the first is why the figure is
a starting value. A set with `tot = 0` reports the check **N/A** and says why;
N/A is not PASS.

Steps 7-12 are the part Level 1 cannot do. **Record the wall-clock time of the
restore and of `migrate`.** They are the first real inputs to RTO
(`DISASTER_RECOVERY.md` section 2); no such number exists in this repository today.

Finally a human, once, at handover and then occasionally: sign in to the test
stack's backend and work the manual list in `algeria/BACKUP.md` section 4 (today's
arrivals, a folio total, one guest ID that actually renders, one invoice footer).
Counts cannot tell you a folio adds up.

### 2.4 Keeping the test stack from reaching the world

`verify.override.yml` (design; not a file in the repository):

```yaml
networks:
  default:
    internal: true        # no route out of the project network   [confirm]
```

with no published ports. Combined with not starting `scheduler`, the workers,
`websocket` and `frontend`, and `pause_scheduler`, a restored site holding real
credentials has no way to send anything. After the first run, test it: from
inside `backend`, an outbound connection must fail. A control that is assumed
and never exercised is the thing this document is about.

### 2.5 The verifier must be seen to fail

A check that has never failed has not been shown to be able to. Every time the
verifier is built or changed, and at least on every Level 2 run, run these
**negative controls** and require the result FAIL:

| Control | How | Must FAIL at |
| --- | --- | --- |
| N1 truncated dump | `head -c $(( $(stat -c%s "$DUMP") / 2 )) "$DUMP" > bad.sql.gz` and verify that | check 2, and 3 |
| N2 empty database | skip the import, run 4-6 | check 4 and 5 |
| N3 wrong key | step 7 above | built in: step 7 *requires* failure |
| N4 stale set | verify a week-old set against today's manifest | check 6 |

If a control comes back PASS, the verifier is wrong and every earlier "pass"
is void. **Until N1-N4 have been run and seen to fail, the deployment's
verification status is UNPROVEN, whatever the checks printed.**

### 2.6 Teardown, with a guard

```bash
# list first; abort unless EVERY volume starts with the verify project name
docker volume ls --format '{{.Name}}' | grep '^kamra-verify_'
# only then:
docker compose -p kamra-verify -f docker-compose.yml -f verify.override.yml down -v
```

Never run a bare `down -v` in this directory. Delete the extracted set and
`urls.txt` too: they hold guest data.

### 2.7 What a result is

A verification writes one record per run: set id, level, each check with its
value and PASS / FAIL / N/A, durations, verifier version, and the negative
controls' outcome. The set's status is **VERIFIED-L1**, **VERIFIED-L2** with a
date, or **UNVERIFIED**. A single FAIL, a missing manifest or an unrun control
makes it not-verified; "skipped" is never reported as passed. The timestamp of
the last passing run, and its level, is the number `BACKUP.md` section 8 says to
watch.

---

## 3. The encryption key

`BACKUP.md` section 1 explains why. This section is the test.

### 3.1 The canary

At install - and after any change to the key - record a value encrypted with
the site's real key:

```bash
DC exec -T backend bench --site "$SITE" execute frappe.utils.password.encrypt \
  --args "['ziri-key-canary']"                                    # [confirm name and --args syntax]
```

Store the printed ciphertext in the manifest, and the plaintext with it. After
a restore, decrypt it with the restored site's key:

```bash
$VDC exec -T backend bench --site verify.localhost execute frappe.utils.password.decrypt \
  --args "['<ciphertext>']"                                       # [confirm]
```

It must print `ziri-key-canary`. A wrong key raises an error. This tests the
key in the restored `site_config.json` directly, and does not depend on the
hotel having stored any real secret yet - which is why it is the primary check.
A canary cannot be created after the key is lost; it is an install-time step.

### 3.2 It must fail first

In Level 2, run the decrypt **before** installing the original key (the
new site has its own, different key). It must fail. This is the proof that
the check is able to detect the problem it exists for. If it succeeds, the
canary is not testing what you think.

### 3.3 Fallbacks, and the honest empty case

- No canary recorded: find a real encrypted value -
  `SELECT doctype, name, fieldname FROM __Auth WHERE encrypted = 1 LIMIT 1`
  (**[confirm columns]**) - and call `frappe.utils.password.get_decrypted_password`
  on it.
- No canary and no encrypted rows: the key **cannot be verified**. Report
  **NOT VERIFIED**. Never PASS, never skipped-and-green.

### 3.4 Setting the key after a restore

If the restored site's key differs from the set's:

```bash
# compare WITHOUT printing the secret
jq -j .encryption_key set/site_config.json | sha256sum
DC exec -T backend python -c "import json,hashlib;print(hashlib.sha256(json.load(open('sites/$SITE/site_config.json'))['encryption_key'].encode()).hexdigest())"

# if they differ, set only this one key, then clear-cache
DC exec -T backend bench --site "$SITE" set-config encryption_key '<value>'
DC exec -T backend bench --site "$SITE" clear-cache
```

Do not copy the whole old `site_config.json` over the new one: it carries the
old `db_name` and `db_password`, which belong to a database that no longer
exists on a rebuilt host. The key will be visible in the process list and shell
history for the duration of the command; run it from a shell with history
disabled, or edit the file instead. Both are weaker than a script that does not
exist yet; the exposure is real and short.

---

## 4. Restore procedures

### 4.1 Common start

1. **Choose the set.** Read the manifests. The newest set is usually right; if
   the damage (corruption, a bad import, a deletion) may predate it, work back
   until a set verifies as clean.
2. **Safety copy of what is there now**, even if broken:
   - database alive: `DC exec -T backend bench --site "$SITE" backup --with-files`, copied off-volume.
   - database not trustworthy: stop everything and archive the volumes cold:
     ```bash
     DC stop
     docker run --rm -v <project>_db-data:/v:ro -v /opt/kamra/backups/pre-restore:/b alpine \
       tar czf /b/db-data.tgz -C /v .
     docker run --rm -v <project>_sites:/v:ro   -v /opt/kamra/backups/pre-restore:/b alpine \
       tar czf /b/sites.tgz   -C /v .
     ```
     Volume names from `docker volume ls`. The archive is consistent because
     the stack is stopped. (Not run; size unmeasured.)
3. **Stop writers and egress:** `DC stop frontend scheduler queue-short queue-long websocket`.
   Leave `db`, `redis-*` and `backend`.
4. **Fetch, decrypt, verify** the chosen set on the host: `SHA256SUMS`, `gzip -t`.
   Copy it into the `backend` container's `sites/<site>/private/backups/`.

### 4.2 Database plus files - same host (the default)

```bash
set -a; . /opt/kamra/kamra.env; set +a        # DB_PASSWORD, from the host, not typed
DC exec -T backend bench --site "$SITE" restore \
  "sites/$SITE/private/backups/<ts>-<slug>-database.sql.gz" \
  --with-public-files  "sites/$SITE/private/backups/<ts>-<slug>-files.tar" \
  --with-private-files "sites/$SITE/private/backups/<ts>-<slug>-private-files.tar" \
  --db-root-password "$DB_PASSWORD" --force                    # flags [confirm] via --help
```

Then, in order: **key** (section 3.4) -> `migrate` -> `clear-cache` -> canary
(section 3.1) -> start `frontend` -> the manual checklist in `algeria/BACKUP.md`
section 4 -> **last**, `scheduler`, `queue-short`, `queue-long`, `websocket`.
Starting the scheduler last matters: it is the part that acts on the world.

After the scheduler is up, look in `/kamra/activity` for a `Night Audit Run`
gap covering the downtime. The night audit (03:00 site time) does not run while
the stack is down, and this repository does not document a safe manual
re-run; that must be established, not guessed.

### 4.3 Database only

Use when the `sites` volume is intact and only the database is damaged or must
be rolled back. Same command without `--with-public-files` /
`--with-private-files`. Consequence: the database and the files are now from
different moments. A guest ID scan erased after the backup (checkout, or the
03:30 retention job) is still gone from disk while the restored database again
points at it - a broken link rather than a leak - and the reverse, a file kept
that the old database does not know, is harmless. Run check 10 (section 2.3)
against the live site afterwards to see how far they diverge.

### 4.4 Files only

Use when `private/files` or `public/files` were wiped and the database is
fine. The tarball's internal layout is Frappe's: list it first
(`tar -tf <archive> | head`) and extract so the paths land under
`sites/<site>/`. Prefer `bench restore --with-*-files` semantics where they
can be run without the dump **[confirm]**. Not written down further because the
safe form cannot be known without the real archive.

### 4.5 A different host

The case that matters in a real disaster: the server is gone.

1. **Provision** with `deploy/install.sh` or the `deploy/linux` route
   (`deploy/linux/README.md`). Without an off-host image archive this means the
   20-45 minute build and a working internet link (`BACKUP.md` section 4.4);
   with one, `docker load`.
2. **Escrow.** Retrieve the repository password, `site_config.json` and
   `kamra.env` (`BACKUP.md` section 6.2). Using an empty `db-data`, a fresh
   `DB_PASSWORD` should suffice; reuse the old one if you have it.
3. **Create the site with the same name** as before - the domain. The
   `FRAPPE_SITE_NAME_HEADER` in `.env` must equal it exactly or every request
   404s (`deploy/linux/README.md`). `install.sh` or `bench new-site` as the
   README shows.
4. **Fetch and verify the set** from the off-site copy: section 4.1 step 4.
   If you can, run a Level 1 on it before spending an hour on the rest.
5. **Restore** (section 4.2) with `scheduler`, workers, `websocket` and
   `frontend` stopped, then the **key** (section 3.4). `kamra` gets a new
   `db_name` and DB password from `new-site`; only `encryption_key` is carried
   over.
6. **Compare** the old `site_config.json` with the new one, key by key, and
   re-apply the non-database settings by `set-config` (for example
   `backup_limit`, host name, anything the hotel set) - not db credentials.
7. TLS: the reverse proxy's certificate and DNS must point at the new host.
   Neither is in any backup this design defines; they are separate recovery
   items.
8. **Old host fenced** (powered off or network-isolated) **before** the new
   `scheduler` starts. Two live copies of one hotel is a worse outcome than
   downtime: duplicate guest messages, conflicting OTA availability.
9. Verify, then start the services in the order given in section 4.2.

### 4.6 Restoring an older backup onto a newer application

Compare the manifest's `bench version` with the running one and decide:

| Backup is... | Action |
| --- | --- |
| Same app version | Restore, `migrate` (a no-op in the normal case) |
| Older, same Frappe major | Restore, then `migrate`. The patch log decides which patches run; those the old database has not seen run now |
| Older, **different Frappe major** | Do not skip. Restore on an image of the backup's own major, `migrate`, then upgrade stepwise. Not exercised; this distribution is on `version-16` |
| **Newer** than the running app | Unsupported. `migrate` does not run patches backwards. Use an image at or above the backup's version |
| Unknown (no manifest) | Treat as unverifiable (section 2); restore to a disposable site first |

Two specifics from this repository:

- `algeria/BACKUP.md` section 4 notes the Algeria patches `v36` and `v37` "have
  never run against a database". Restoring a pre-`v36` backup onto current code
  is therefore the first time they touch real data. **Run it as a Level 2
  against the target image first**, so that is where they fail, not on the live
  site.
- The image tag is `kamra:local`, mutable, with no registry. The image that
  matches an old backup exists only if it was tagged before the rebuild
  (`BACKUP.md` section 4.4). Without it, "restore onto the version that wrote
  the backup" may be impossible, and the answer is the older-onto-newer path
  above.

`--force` on `restore` exists to override Frappe's own version check
**[confirm]**. Read the refusal message before using it. It silences a safety
check; it does not make the mismatch safe.

MariaDB itself: a logical dump loads into the same or a newer 11.x; the
`db` service sets `MARIADB_AUTO_UPGRADE: 1` for data-directory upgrades.
Restoring into an older server than made the dump is not covered.

### 4.7 One record, not the whole site

An accidentally deleted reservation does not justify rolling back everyone's
work. Try Frappe's own recovery first (the Deleted Document list and its
Restore action - core Frappe **[confirm that the ZIRI doctypes keep deletion
history]**). Failing that: restore the set into a disposable Level 2 stack
(section 2.3, with all of rule 1 in force), read the record there and re-enter
it, or export it with `bench export-json` **[confirm]** and import it live.
A site restores as a whole; there is no per-property or per-record restore
inside one site, so in a multi-property site this is the only way to recover
one property's data without touching the others.

---

## 5. Cadence

Derived from cost, not from ritual. The costs are unmeasured, so these are
starting points to adjust after the first runs report durations.

| What | When | Why |
| --- | --- | --- |
| Level 1 | Every full set (daily); newest intra-day set once a day | Cheap: one container, no app. Catches truncation and empty dumps within a day, while the previous night's set still exists |
| Level 2 | Monthly; before every update/migration, against the target image; once before handover, from an off-site copy only | Dearer: a second stack. The update-time run is the only place `v36`/`v37`-class patch problems appear safely |
| Custodian key drill | Quarterly | `BACKUP.md` section 6.4: proves the escrow copy, not the server's |
| Host-loss drill | Before handover and yearly | Provision a spare machine from escrow plus an off-site set only. The only exercise that tests `DISASTER_RECOVERY.md` for real, and the only source of an honest RTO |

**Status words for a deployment**, used verbatim: `UNVERIFIED` (no
passing Level 2 from an off-site copy), `L1 <date>`, `L2 <date>`,
`DRILLED <date>`. A deployment that is `UNVERIFIED` is described as exactly
that, not as backed up.

---

## What this does not cover / has not been tested

- **The verifier does not exist.** No script, no manifest writer, no result
  record, no `verify.override.yml`. This is the specification of one. Until it
  is built and N1-N4 (section 2.5) have been seen to fail, no deployment can
  claim a verified backup.
- **No restore has been performed with these commands.** The `bench restore`
  flags, `--force`, `pause_scheduler`, the `execute --args` syntax for the
  canary, the `__Auth` columns, `export-json` and the layout of the Frappe
  archives are all **[confirm]** items from framework knowledge, not from this
  repository. The compose volume path and the `install.sh` site-creation flags
  are the only parts read from it.
- **Whether `internal: true` actually blocks all egress** on the Linux host,
  and whether the restored site makes outbound calls at `migrate` time, has not
  been tested.
- **No timings.** Restore duration, `migrate` duration, verification duration
  and resource use are unmeasured; RTO inherits that (`DISASTER_RECOVERY.md`).
- **Which tables churn and which are good watermarks** on a real property is
  unknown; the allowlist and watermark set are empty until the first runs.
- **Semantic correctness** (folio arithmetic, tax lines, an invoice footer)
  is not machine-checked; it is a human step.
- **Downgrade, cross-major upgrade and restoring onto an older MariaDB** are
  declared unsupported or unexercised, not solved.
- **Only Docker Desktop over WSL2 has run this stack**; nothing here has been
  seen on the Linux server it targets.
- **Re-erasure after restore.** A restored backup resurrects guest data the
  live system had erased under retention. The nightly `apply_retention`
  (03:30) will probably erase idle guests again on its next run, but whether it
  re-erases scans already purged at checkout, and exactly what it covers, has
  not been tested. Treat the window between restore and the next run as one in
  which erased data is present.
- **Law 18-07** duties around a restored or leaked copy are not analysed.
