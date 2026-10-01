# ZIRI PMS — Rollback design

> **Status: DESIGN. Nothing in this document is implemented.**
>
> There is no rollback in this repository today. `deploy/install.sh update` rebuilds,
> recreates, migrates and stops there (`deploy/install.sh:217-240`); the Phase 0 audit
> records "Update has no rollback". Every procedure below is what the installation *will*
> do once the update runner in [`UPDATES.md`](UPDATES.md) exists. Nothing here has been
> run, timed or rehearsed. Where this document says an image or a backup "exists", it
> means "will exist if the sequence in `UPDATES.md` §8 has run", and §2 states plainly
> that today it does not.

Read with [`UPDATES.md`](UPDATES.md) (the forward path, step numbers referenced below) and
[`PRODUCTIZATION_AUDIT.md`](PRODUCTIZATION_AUDIT.md). Same conventions as `UPDATES.md`:
`<COMPOSE>` is the compose invocation from `docs/algeria/BACKUP.md` §1, run from
`/opt/kamra/frappe_docker`; `$SITE`, `$RUN`, `$UPD=/opt/kamra/updates/$RUN`; service names
are `backend`, `frontend`, `db`, `redis-cache`, `redis-queue`, `queue-short`, `queue-long`,
`scheduler`, `websocket`, `configurator`; **(VERIFY)** marks a command or flag not confirmed
from this repository. Database: **MariaDB 11.8**.

---

## 1. The one thing to understand first

There are two completely different operations that both get called "rollback".

| | Roll back the **application** | Roll back the **database** |
| --- | --- | --- |
| What changes | Which image the containers run | The contents of MariaDB (and the files volume) |
| Mechanism | Point `CUSTOM_TAG` at the previous image, recreate the app containers | Restore a backup taken before the update |
| Difficulty | **Easy**, if the previous image still exists | **Hard** |
| Data cost | **None.** No data is touched | **Everything written after the backup point is lost** |
| Time | Seconds to a couple of minutes | Proportional to database and files size; **unmeasured** |
| Reversible itself? | Yes | No: it overwrites the current database |
| When it is the right tool | Failure happened before the database was changed, or the change is additive and old code tolerates it | The database was changed in a way old code cannot live with, or its state is unknown |

Application rollback is a decision about code. Database rollback is a decision about
**data**, and the hotel's data is the only thing in this system that cannot be rebuilt.
Frappe gives no way to undo a migration (§3), so "roll back the update" on a database that
has migrated means restoring a backup, which discards real work unless the backup is
recent enough. That cost is the reason this design takes a second, quiesced backup
(`UPDATES.md` step 7) and structures the sequence so the decision to restore is made
**before the hotel resumes work**, when it costs nothing.

---

## 2. Rolling back the application image

### What it is

The application *is* the image: `backend`, `frontend`, `websocket`, `queue-short`,
`queue-long`, `scheduler` and `configurator` all run `${CUSTOM_IMAGE}:${CUSTOM_TAG}`
(`deploy/linux/docker-compose.yml`, `x-customizable-image`). Rolling back means making
those services run the previous one. `db`, `redis-cache` and `redis-queue` are separate
upstream images and are not part of it.

### Does the previous image exist today? No.

This must be stated, because the easy case is only easy if the image is there:

- `install.sh` tags every build `kamra:local` (`install.sh:38-39, 168-169`). Building again
  **moves that tag**. The previous image keeps its layers but loses its name, and
  `docker image ls` shows it as `<none>`.
- A host that runs `docker system prune -af` (as `nightly.yml:164` and `release.yml:138`
  do on the demo VPS) deletes every image not used by a running container. That includes any
  previous image. That command is correct for a CI-managed demo host and **must never be
  copied onto a customer host.**
- The fallback, rebuilding the old version from source, is **not** a rollback: Frappe
  `version-16` and `payments` `develop` move (`UPDATES.md` §1 item 3), so a rebuild yields a
  different image from the one that ran. `ci.yml:81-82` documents a Frappe tip that shipped a
  bug.

So the claim "the previous image tag still exists" is a **requirement the update sequence
must create**, not a property the system has:

1. **Per-version immutable tags.** `CUSTOM_TAG` in `kamra.env` is the release version
   (`2.6.6`), not `local`.
2. **Retag before replacing** (`UPDATES.md` step 4): `docker tag kamra:<current> kamra:rollback-<from_version>`.
3. **Record the previous image digest** in the `Update Run` record.
4. **Verify presence before offering rollback:** `docker image inspect kamra:rollback-<from_version>`
   must succeed, and the run is shown "application rollback: available" only if it did.
5. **Second line of defence:** the previous release's signed manifest is kept in `$UPD/`.
   If the local image is gone, `docker pull ghcr.io/kamra-pms/kamra@sha256:<previous digest>`
   restores the *identical* image, if that package is still published and readable
   (decision D3 in `UPDATES.md`).

### The procedure

```bash
cd /opt/kamra/frappe_docker
# maintenance mode stays ON; workers stay stopped
<COMPOSE> stop scheduler queue-short queue-long
cp -p /opt/kamra/kamra.env "$UPD/config/kamra.env.failed"
sed -i "s/^CUSTOM_TAG=.*/CUSTOM_TAG=<previous-tag>/; s/^ERPNEXT_VERSION=.*/ERPNEXT_VERSION=<previous-tag>/" /opt/kamra/kamra.env
<COMPOSE> up -d --force-recreate configurator backend frontend websocket
<COMPOSE> restart frontend      # nginx caches backend's address; see the 502 row in deploy/linux/README.md
<COMPOSE> exec -T backend bench --site "$SITE" clear-cache
```

`db`, `redis-cache` and `redis-queue` are left alone. **Do not run `bench migrate` after an
application rollback**: the old release's DocType definitions would be synced over the new
ones already in the database, and a schema sync that tries to narrow a column or drop a
field is exactly the unsafe direction (§3).

### What it does not roll back

- **The database.** Columns, tables and rows that the new release added or rewrote are
  still there.
- **DocType metadata, which lives in the database.** `tabDocType`, Custom Fields,
  Property Setters, permissions and workspace records were updated by `migrate`. After an
  application rollback the old code runs against the **new release's metadata**. For an
  additive change (§4, M1) that is usually tolerable; it is not guaranteed, and nothing in
  this repository has tested it.
- **Static assets in the `sites` volume.** The VPS deploy script syncs assets from the new
  image into the volume (`nightly.yml:188-194`, `release.yml:139-142`); `install.sh update`
  does not, and whether the customer path needs it was not determined (§10). A rollback
  has the mirror-image question. The smoke test's asset fetch (`UPDATES.md` step 11) is the
  check that catches it.
- **Anything the new version already did to the outside world** (§6).

### When it is the right and the wrong tool

**Right:** failure before `migrate` ran (new image will not start, `configurator` did not
exit 0, `backend` crash-loops): the database has not been touched, so this loses nothing and
restores the old behaviour exactly. This is *Case B* in §5.

**Wrong after the database changed in a way old code cannot read** (class M2/M3, §4).
Starting old code on rewritten or removed data looks like a successful rollback until
someone opens the screen that reads the rewritten column. Treat "the containers came up"
as proving nothing; only the health and smoke steps do.

---

## 3. Why database rollback is hard here

### Frappe patches are forward-only

`kamra/patches.txt` lists patches in two sections, `[pre_model_sync]` and
`[post_model_sync]`; `bench migrate` runs them in order and records each in `tabPatch Log`.
Each patch is a Python module with one function, `execute()` (see `kamra/patches/v37/`).
There is **no `down`, no `revert`, no inverse** in the format. A rollback design that
assumes reversible migrations is wrong for this stack and this document does not assume it.

What follows from that:

1. **There is no "undo the last migration" command to build a rollback on.** The only
   restoration of previous *data* is a backup.
2. **MariaDB DDL is not transactional.** `ALTER TABLE` and `CREATE TABLE` commit
   implicitly. `migrate` first syncs DocType definitions to the schema (adding columns and
   tables), then runs `[post_model_sync]` patches. If a patch fails, the schema changes
   already made **stay made**; there is no transaction to abort. (This is the general
   MariaDB/Frappe behaviour as understood here; it was not exercised against this image.)
3. **A failed `migrate` leaves a partly-migrated database in an indeterminate state.**
   Patches that completed are in `tabPatch Log`; the one that failed is not; some patches
   issue an explicit `frappe.db.commit()` midway (`v23`, `v31`), so a failure inside such a
   patch can leave it half-applied. Re-running `migrate` is therefore not a safe default; it
   works only if every pending patch is idempotent, and the repository says so for some
   (`v36`, `v37`) and shows the opposite for others (§4).
4. **Metadata is data.** The "schema" old code needs is not only tables. It includes
   DocType records, custom fields, permissions and settings stored in rows. Reverting the
   image reverts none of it.
5. **After the update commits, new rows exist.** A restore does not "undo the migration"; it
   replaces the whole database with an older one. Reservations, folio charges, payments, ID
   scans created after the backup point are not carried forward by anything. There is no
   merge.
6. **Some patches destroy information outright** (§4: `v35` deletes permission rows;
   `v24` rewrites `agent_name`). The inverse is not derivable from the result.

### The three honest options when a migration has gone wrong

| Option | What it is | Data cost | When it is real |
| --- | --- | --- | --- |
| **Restore from backup** | Replace the database and files with a backup, and run the old image | Everything since the backup point | Always available if a valid backup exists. **Free** if taken in the quiesced window and nothing has been written since (before the commit point); progressively expensive after |
| **Forward-fix** | Ship a corrected release; the failed patch runs again or is superseded | None | Only when the cause is understood, the failed patch is safe to re-run, and a signed fixed release exists. **Not a field action** for an administrator at 2 a.m. |
| **Application-only rollback** | Old code, new schema (§2) | None | Only when the migration was additive and old code is known to tolerate it |

There is no fourth option. A claim that the database "can be rolled back" without one of
these three is a claim this stack cannot support.

### Specific to this repository

- **MariaDB engine upgrades are one-way.** `MARIADB_AUTO_UPGRADE: 1` is set on `db`
  (`deploy/linux/docker-compose.yml`), so a changed `mariadb` image rewrites the data
  directory on start. Booting the old image on that directory is not supported. The update
  gate refuses an update that changes the `db` image (`UPDATES.md` §7); this is why it is
  refused and not merely warned about.
- **Restoring reverts security fixes in the data.** `v35` deletes permission rows so that
  Hosting Enquiry (sales PII) is System-Manager-only. Restoring a backup from before `v35`
  puts the broader permissions back. Rolling back a `severity: security` release by restore
  **re-opens the vulnerability it closed**, which is why §5 prefers forward-fix there.
- **Restoring revives deleted personal data.** `backup --with-files` tars `private/files`,
  so guest ID scans deleted at checkout under the retention policy return with any restore
  (`kamra/id_documents.py:18-31`, `BACKUP.md` §4). A rollback restore is subject to the same
  privacy consequence.
- **The files volume and the encryption key** are not necessarily inside Frappe's backup
  (`BACKUP.md` §3). The update sequence copies `site_config.json`, `kamra.env` and
  `apps.json` into `$UPD/config/` precisely so a restore can reproduce them; without the
  encryption key, stored gateway/SMTP credentials are unreadable after restore.

---

## 4. Migration classes and the patches that exist

`UPDATES.md` §5 defines the class a release declares. The class is not decoration; it is the
input to the decision rules in §5.

| Class | Meaning | Application-only rollback | Database restore |
| --- | --- | --- | --- |
| **M0** | No new patch, no schema change | Safe in principle | Not needed |
| **M1** | Additive columns/DocTypes; backfills write only blank values | Plausible; **must be rehearsed per release** | Available |
| **M2** | Rewrites/deletes existing rows or overwrites values unconditionally | **Unsafe** | Only route to the old version |
| **M3** | Destroys information not held elsewhere, or changes DB engine / Frappe major | **Unsafe** | Only route; and after the commit point the lost information is gone with the restore |

An unclassified release is treated as **M3**.

### What the existing patches look like (classified by reading, not by running)

The author of this document read the patch bodies and assigned classes. **No patch was
executed.** `docs/algeria/VERSIONING.md` and `BACKUP.md` §4 both state that `v36` and `v37`
have never run against a real database. `v26` and `v27` delegate to helpers
(`kamra.install.set_site_favicon`, `kamra.siu.units.backfill_property`) that were not read
in full; their class is provisional.

| Patch | What it does | Class | Why |
| --- | --- | --- | --- |
| `v23.backfill_action_log_approval_status` | Sets `approval_status='Executed'`, `executed_at=creation` on rows where blank | M1 | Writes blank values only; explicit `db.commit()` |
| `v24.split_actor_from_agent_name` | Moves values between `agent_name` and `actor`, then nulls `agent_name` | **M2** | Rewrites existing values; which rows were changed is not recorded |
| `v25.backfill_property_country` | Sets country/currency/locale where blank | M1 | Blank-only |
| `v26.set_site_favicon` | Calls `set_site_favicon()` | M1 (provisional) | Helper not read |
| `v27.backfill_sellable_units` | Creates Sellable Units for rooms | M1 (provisional) | Additive rows; helper not read |
| `v28.backfill_property_kind` | `property_kind='Hotel'` where blank | M1 | Blank-only |
| `v29.backfill_booking_mode` | `booking_mode`, `hold_minutes` where blank/zero | M1 | Blank-only |
| `v30.ensure_turnover_profiles` | Creates default profile per property | M1 | Additive |
| `v31.backfill_listing_slugs` | Fills blank slugs; explicit `db.commit()` | M1 | Blank-only |
| `v32.seed_cashier_ledger` | Seeds codes; backfills blank `transaction_code`; sets `business_date` where unset | M1 | Blank-only |
| `v33.seed_banquet_checklists` | Seeds templates | M1 | Additive |
| `v34.keep_access_logs_a_year` | Raises Log Settings retention to at least 365 days | **M2** | Overwrites existing setting values |
| `v34.keep_existing_privacy_settings` | `UPDATE tabProperty SET guest_retention_months = 0` for **every** row | **M2** | Unconditional overwrite; re-running after an operator set a period would erase it. This is the one patch here that is **not** idempotent |
| `v35.hosting_enquiry_system_manager_only` | Deletes Custom DocPerm and DocPerm rows | **M2** | Destroys permission rows; reverting re-opens PII access |
| `v36.backfill_room_levy_mode` | `room_levy_mode='Percent'`, `room_levy_amount=0` where blank/NULL | M1 | Blank-only, idempotent by its own docstring |
| `v37.normalize_legal_id_columns` | NULL to `''` on three new columns | M1 | Idempotent; the NULL-versus-empty distinction is lost, which is trivial |

Reading this table: of 16 patch modules, 12 are M1 and 4 are M2 (`v24`, both `v34`
patches, `v35`), none M3. That distribution is the argument for application-only rollback
being a *real option most of the time* and for refusing to promise it *every* time. It is a
small sample from one project's history, classified by one reader, and says nothing about
the next release.

---

## 5. Failure triggers and the decision rules

### Triggers (any one starts this procedure)

| # | Trigger | Detected by |
| --- | --- | --- |
| T1 | **Migration fails**: `bench migrate` exits non-zero, raises, or exceeds the administrator-visible limit (limit proposed, unmeasured) | `UPDATES.md` step 9 exit status and output |
| T2 | **Application fails to start**: `configurator` does not exit 0; `backend` not running or restarting; `/api/method/ping` not answered after the bounded retry | Steps 8, 10, 11; `<COMPOSE> ps` |
| T3 | **Health check fails**: any check `failed` in phase 1 or phase 2 | `system_health()` plus the §7 checks |
| T4 | **Critical service down** at any point after step 8: `db` unhealthy, `redis-cache` or `redis-queue` not answering, `scheduler` or both queue workers absent in phase 2 | Container state; `_workers_check` ("No worker is running" is `failed`); `_scheduler_check` |
| T5 | **Smoke test fails**: `/kamra` not 200, a built asset not served, or row counts differ from the step-7 baseline | `UPDATES.md` step 11 |
| T6 | **Administrator requests rollback** after the commit point | Manual |

**Not triggers:** an `attention` status (for example the time-zone or scheduler
"no job yet" notes). Rolling back a database for a warning is how a recoverable
inconvenience becomes data loss.

### The cases

The rules key on **where in the sequence the failure happened** and **whether the commit
point has passed** (`UPDATES.md` step 13: first start of `scheduler`/`queue-*` on the new
version, or maintenance lifted).

| Case | Situation | Action | Data lost |
| --- | --- | --- | --- |
| **A** | Failure before step 8 (gate, B1, verify, quiesce, B2) | **Abort.** Maintenance off, workers restarted. Nothing was changed. | None |
| **B** | Step 8: new image will not start; `migrate` has **not** run | **Application rollback only** (§2). Database untouched; verify by an empty `tabPatch Log` delta. | None |
| **C** | Step 9: **migrate failed or timed out**; commit point not passed | **Restore B2 with the previous image** (§8). The database is in an unknown state; restoring is the only way back to a *known* one, and it costs nothing because B2 was quiesced. Forward-fix only if a fixed signed release exists, which is a vendor action, not a field one. | None |
| **D** | Steps 10-11: migrate succeeded, health or smoke failed; commit point not passed | **Restore B2 with the previous image** is the default. Application-only rollback is permitted if the class is M0/M1 **and** the administrator chooses it to avoid restore time; its safety is unproven and the health and smoke steps are re-run to find out. | None (restore) |
| **E** | Commit point passed (workers started or maintenance lifted); a trigger fires, or the administrator reports a defect later | See below | Depends |

**Case E in detail.** From the commit point, new data exists that B2 does not contain, so
restore stops being free:

1. **`severity: security` release:** prefer forward-fix. Restoring reverts the fix (§3).
2. **Class M0/M1:** application-only rollback is the first choice. If health and smoke pass
   afterwards, stop there. If they do not, the next option is a restore.
3. **Class M2/M3:** application-only rollback is unsafe. The choices are forward-fix or
   restore.
4. **Restore after the commit point** requires an explicit administrator decision showing
   `data_at_risk` (rows created since B2, by table), and a typed confirmation. **Before**
   restoring, take a backup of the current state (B3, §8 step R6) so what would be lost is
   preserved and can be consulted or re-keyed by hand. B3 is not a rollback; it is the
   record of what the rollback discarded.
5. **If B2 is missing or invalid:** there is no database rollback. Application-only
   rollback (if the class allows) or forward-fix are the only options. The sequence is built
   so a run never reaches apply in this state (`UPDATES.md` step 7 aborts), so reaching this
   row means something outside the sequence went wrong.

---

## 6. What cannot be undone, whatever is done

Say this to the administrator before the update, not after. Some effects of running a
release are permanent:

1. **Information a migration destroys** (M3), and the *prior value* of anything a patch
   overwrote (M2). Only a backup holds it, and only up to the backup point.
2. **Everything entered after the backup point** if a restore is performed. No tool merges
   it back.
3. **External side effects of new-code background jobs.** Emails sent, SMS/WhatsApp
   messages delivered, payment-gateway calls made, tax or e-invoice submissions filed by
   `queue-short`, `queue-long` or `scheduler` are not undone by restoring a database. This
   is why the sequence keeps those services stopped until migrate, health and smoke pass
   (`UPDATES.md` step 8, 12), and why the commit point is defined as their first start.
4. **A restore revives deleted personal data** (§3) and **reverts security fixes held in
   data** (§3).
5. **MariaDB engine or Frappe-major upgrades.** The data directory cannot be downgraded
   (§3). Not an application update; refused by the gate.
6. **Time.** The business date and night-audit state live in the database
   (`v32` sets `business_date`). Restoring B2 returns them to B2's values; a night audit that
   ran after B2 is gone from the database even though its consequences may exist outside it.
7. **A migration that was never classified.** Treated as M3, which means: assume it cannot
   be undone.

---

## 7. Retention — what must still exist when rollback is needed

| Artefact | Kept for | Why | Protected from |
| --- | --- | --- | --- |
| `kamra:rollback-<from_version>` image | Until the next update commits, plus the previous one (keep two) | Application rollback | `docker system prune -af`, `docker image prune -a`: label images `kamra.keep=true` and only ever prune with `--filter "label!=kamra.keep=true"`, or do not prune on a customer host |
| B2 (quiesced backup) and its sha256 | At least until the next successful update's B2 exists | The rollback point | Sits in `$UPD/`, **off the `sites` volume**, on the host |
| B1 | Same | Fallback if B2 is damaged, at the cost of data written between B1 and the quiesce | Same |
| `$UPD/config/` (`kamra.env`, `site_config.json`, `apps.json`, compose files) | With B2 | Encryption key and DB password needed to use a restore | Mode 600; **never included in any bundle sent off the machine** |
| Previous release manifest + signature | With the image | Second-line image recovery by digest | Same |
| `run.log`, collected logs | Long enough to be useful for support; retention is a privacy decision | Diagnosis | Logs may contain personal data and secrets; redact before sharing |

Disk used by two backups and two images is already inside the pre-flight disk rule
(`UPDATES.md` §7). Retention is **not** a substitute for the off-machine copy that
`BACKUP.md` §2 calls for: B2 on the same disk as the database shares its fate.

**Never, during a rollback:** `docker compose down -v`, `docker volume rm`,
`docker volume prune`, or any command that removes `sites` or `db-data`. Those two volumes
are the hotel (`deploy/linux/docker-compose.yml`, `volumes:`). A rollback that deletes them
has converted an update failure into a total loss.

---

## 8. The ordered response

Run in this order. Steps R1-R3 happen on **every** trigger; R4-R6 are chosen by §5.

### R1 — Stop
- Halt the runner. **Do not retry the failed step**, and in particular do not re-run
  `migrate` hoping it passes (§3, point 3).
- Keep maintenance mode **on**. Keep `scheduler`, `queue-short`, `queue-long` stopped (if
  the commit point has not passed they already are):
```bash
<COMPOSE> stop scheduler queue-short queue-long
```
- Do not touch volumes (§7).

### R2 — Collect logs (before anything is restarted, because restarts rotate them)
```bash
mkdir -p "$UPD/logs" && chmod 700 "$UPD/logs"
<COMPOSE> logs --no-color --since "<run start time>" backend configurator frontend websocket \
  queue-short queue-long scheduler db > "$UPD/logs/compose.log" 2>&1
<COMPOSE> ps > "$UPD/logs/ps.txt"
docker image ls --digests > "$UPD/logs/images.txt"
df -h > "$UPD/logs/df.txt"
<COMPOSE> exec -T backend bench --site "$SITE" mariadb -e \
  "SELECT patch FROM \`tabPatch Log\` ORDER BY creation DESC LIMIT 50" > "$UPD/logs/patch-log-tail.txt"   # (VERIFY)
# plus the migrate output captured at step 9 (already in run.log)
```
These logs can contain personal data and secrets. They stay in `$UPD/logs/` on the host.
There is no support-bundle mechanism yet (audit, Gaps: 0 hits); until one exists, nothing
leaves the machine without a person reading it.

### R3 — Mark the update failed
- Write `state: failed` and the trigger (T1-T6) to `$UPD/status.json`.
- Record the failing step, the first error line, the failing patch if any.
- **Record the version as known-bad on this installation.** Discovery
  (`UPDATES.md` §4) must not re-offer the same version as a one-click update until an
  administrator acknowledges it or a newer version exists; otherwise the next
  `/kamra/health` visit invites a repeat.

### R4 — Decide (§5)
Pick the case. State it, with the data cost, on the terminal and in `run.log`. For Case E
restore, stop and wait for the typed administrator confirmation.

### R5 — Roll back the application
The §2 procedure. Always done first, in every case that ends with the old version running,
because a restore should be performed with the old code in place.

### R6 — Restore the database **only if the case requires it** (C, D by default, E by choice)
```bash
# R6.0 Preserve the current state (B3). Best effort: if the database is too damaged to back
#      up, record that and continue; do not let a failed B3 block a restore that is needed.
<COMPOSE> exec -T backend bench --site "$SITE" backup --with-files
docker cp kamra-backend-1:/home/frappe/frappe-bench/sites/$SITE/private/backups/. "$UPD/backup-b3/"

# R6.1 Validate B2 again (gzip -t, tar -tzf, sha256 against $UPD/backup-b2.sha256).
#      A mismatch means STOP: use B1 only with an explicit data-loss decision, see §9.

# R6.2 Put B2 where the container can read it
docker cp "$UPD/backup-b2/." kamra-backend-1:/home/frappe/frappe-bench/sites/$SITE/private/backups/restore-$RUN/

# R6.3 Restore. Flag names are the framework's, not this repository's: read them off the
#      image first.
<COMPOSE> exec -T backend bench --site "$SITE" restore --help                          # (VERIFY)
<COMPOSE> exec -T backend bench --site "$SITE" restore \
  sites/$SITE/private/backups/restore-$RUN/<B2-database>.sql.gz \
  --with-public-files <B2-public-files>.tar --with-private-files <B2-private-files>.tar \
  --db-root-password "$DB_PASSWORD"                                                     # (VERIFY every flag)

# R6.4 Put back the secrets the backup may not contain
#      compare $UPD/config/site_config.json with the live one; restore the encryption key if it differs

# R6.5 State after restore is not assumed
<COMPOSE> exec -T backend bench --site "$SITE" set-maintenance-mode on                 # (VERIFY) re-assert, do not trust
<COMPOSE> exec -T backend bench --site "$SITE" clear-cache
<COMPOSE> exec -T redis-queue redis-cli DBSIZE                                          # log the count
<COMPOSE> exec -T redis-queue redis-cli FLUSHALL                                        # (VERIFY) jobs enqueued by the new version
                                                                                        # refer to rows the restored database no longer has
```
**Do not run `migrate` after restoring B2 under the old image.** B2 and the old image agree
on schema and on `tabPatch Log`; `migrate` would add risk without a purpose. (`BACKUP.md`
§4 recommends `migrate` after a restore when the backup is older than the *running* image;
here they match by construction.) The flushed queue loses jobs that were queued before the
update; most are re-derivable from database state by the scheduler, but that was not
verified.

### R7 — Health check
Run exactly the checks the forward path runs, against the restored or rolled-back system:
phase 1 (`UPDATES.md` step 10), then the smoke test (step 11) with the row counts compared
against the **step-7 baseline** (which B2 should reproduce exactly), then start
`scheduler queue-short queue-long`, then phase 2.

Success means **every** critical check `passed` and the counts equal the baseline. Anything
less is `rollback-failed` (§9), not "mostly rolled back".

### R8 — Close out
- With the administrator's confirmation, lift maintenance mode.
- State: `rolled-back-app` or `rolled-back-restore`.
- Tell the administrator in plain words: the version now running, the backup used and its
  timestamp, what data (if any) was discarded and where B3 is, and that the failed version is
  marked known-bad.

---

## 9. When the rollback itself fails

| Failure | Response |
| --- | --- |
| **Previous image absent** | `docker pull` by the digest recorded in the previous manifest (§2). If that is unavailable, the only remaining route is a source rebuild: label it "build-unverified", expect it to differ from what ran, and re-run health and smoke before trusting it. Say so to the administrator. |
| **B2 fails validation or restore errors** | Use **B1**, but only with an explicit decision: everything written between B1 and the quiesce (potentially hours) is lost, and the amount is stated before the administrator agrees. |
| **B1 also unusable, or no backup exists** | **There is no database rollback.** The hotel stays in maintenance mode. Application-only rollback (if the class permits) or forward-fix are all that remain. Do not delete anything. Take a cold copy of the `db-data` volume (stop `db`, archive the volume, volume name per `docker volume ls`, **VERIFY**) before any further experiment, and escalate. |
| **Restore succeeds, health fails** | The restored system is not trusted. Re-check the encryption key, `kamra.env`'s `DB_PASSWORD`, then the container list; this is the case `BACKUP.md` §5 exists to find in advance. |
| **Disk fills during rollback** | The pre-flight disk rule reserves for B1, B2 and the image, not for B3 plus a restore working copy. Stop, free space from non-data sources only (old images, logs), and resume. |

The honest statement for the last row of that table is worth repeating at install time: **a
hotel without a valid backup has no database rollback, and an update gate that allows an
update without one is not a gate.** That is why a missing or invalid B2 aborts the run
before anything is modified (`UPDATES.md` step 7).

---

## 10. What this does not cover / has not been tested

**Nothing in this document has been run.** It is a design written by reading the
repository.

- **No rollback has ever been performed on this stack.** Not application rollback, not
  restore. Restore time for a realistic hotel database, backup size, and the duration of a
  full rollback are all **unmeasured**.
- **The compose stack has only run on Docker Desktop over WSL2 on one machine** and never on
  the Linux server it targets (audit, "What this document does not establish").
- **Frappe behaviours asserted from general knowledge, not confirmed in the built image:**
  that MariaDB DDL commits implicitly and is not undone by a failed patch; that `tabPatch
  Log` records only completed patches; how `bench restore` treats an existing site, and its
  flag names; whether it preserves or resets maintenance mode; whether it restores
  `site_config.json`. Each must be confirmed on the real image (the `(VERIFY)` markers) and
  the restore procedure rehearsed using `BACKUP.md` §5.
- **Whether old code tolerates a new schema was not tested for any release.** "Plausible"
  for M1 is a hypothesis, not a result. Each M1 release needs an actual rehearsal (new
  schema, old image, run health and smoke) before the manifest may declare `rollback_mode:
  app-only`.
- **Patch classifications are by reading.** `v26` and `v27` helpers were not read; no patch
  was executed; `v36`/`v37` have never run against a real database. The class table is a
  starting point for review, not an audit.
- **Static-asset behaviour across image changes.** The VPS deploy script syncs assets into
  the `sites` volume; `install.sh update` does not. Whether the customer path needs it, and
  whether an application rollback leaves stale assets, was not determined. The smoke test is
  designed to detect it but was never run.
- **Maintenance mode semantics** (who it blocks, whether the websocket and API tokens are
  covered) were not determined; the "restoring B2 loses nothing" claim rests on writes being
  blocked from the quiesce step onward, and the row-count baseline is the safeguard if it
  does not.
- **Redis queue flushing** (R6.5) trades away pre-update queued jobs; the claim that the
  scheduler re-derives them from database state is unverified.
- **No second site, no cold standby, no replication.** Rollback here is single-node. There is
  no point-in-time recovery: MariaDB binary logs are not enabled in `deploy/linux/docker-compose.yml`
  and are not designed here, so the recovery granularity is "the last backup", not "five
  minutes ago".
- **Windows installs** (Docker Desktop over WSL2): Docker Desktop being stopped mid-rollback
  and WSL path handling are not designed here.
- **Support escalation** depends on a support bundle and error-code taxonomy that do not
  exist yet (audit, Gaps).
- **No rehearsal, drill or failure-injection plan** is included. One is required before this
  design is trusted: a deliberately failing patch, a deliberately full disk and a deleted
  rollback image, each run against a throwaway site.
