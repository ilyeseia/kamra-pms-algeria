# Backup - design

**Status: design. Nothing in this document has been executed against a running
stack by its author.** No script implementing it exists in the repository; the
audit ([`PRODUCTIZATION_AUDIT.md`](PRODUCTIZATION_AUDIT.md), "Gaps": scheduled
automatic backup) found none and this phase adds none. Commands are written
against the real service names (`backend`, `db`, `sites`, ...) but every one is
unrun. A command marked **[confirm]** uses a Frappe flag or behaviour that this
repository cannot show; read it off `--help` on the installed image before
trusting it, as [`../algeria/BACKUP.md`](../algeria/BACKUP.md) section 4 already requires.

This document extends [`../algeria/BACKUP.md`](../algeria/BACKUP.md). That file
owns the mechanics of getting a `bench backup` out of the `backend` container,
the `<COMPOSE>` prefix, and the Windows Task Scheduler wiring. It is not
repeated here. What this file adds: the encryption-key problem stated first,
a tiered schedule with configurable retention, destinations, encryption of the
backups themselves and who holds that key, and what must never sit beside a
backup. Restoring and proving a restore works is in [`RESTORE.md`](RESTORE.md);
failure scenarios and RPO/RTO are in [`DISASTER_RECOVERY.md`](DISASTER_RECOVERY.md).

Database is **MariaDB 11.8**. The tool is `bench`. Nothing here uses `pg_dump`.

`DC` below means whichever compose invocation your install uses: the
`<COMPOSE>` prefix of `algeria/BACKUP.md` section 1 for an `install.sh` install, or
plain `docker compose` inside `deploy/linux/` for a hand-built one.

---

## 1. The trap: a database backup without the encryption key is half a backup

Read this before anything else.

Frappe encrypts stored secrets (every `Password`-type field: SMTP credentials,
payment-gateway secrets, API keys, anything an integration keeps) with an
`encryption_key` that lives in `sites/<site>/site_config.json`. The key is not
in the database. The database holds only ciphertext.

That file lives in the **`sites` volume**, not in `db-data`. So:

- A dump of MariaDB alone contains secrets nobody can read.
- Restore that dump onto a rebuilt or new site and the new site has its own,
  freshly generated key. Sign-in works. Reservations are there. Folios add up.
  Everything looks fine, and every integration credential fails the first time
  something tries to use it - typically a scheduled job at night.
- Nothing warns you at restore time. The failure is deferred and silent.

This is the one failure that survives every "the restore completed" check.
(The existing `algeria/BACKUP.md` section 3 flags the key but leaves open whether
`bench backup` captures it. This document does not rely on the answer.)

**Design rules that follow from it:**

1. **A backup set is not complete without `site_config.json`.** The backup job
   copies it explicitly into every set. It does not depend on Frappe doing so.
   (Some Frappe versions write a `*-site_config_backup.json` next to the dump
   **[confirm: list the real directory on the install]**. If yours does, that
   file contains the key in plaintext beside the database dump - see section 7.)
2. **The key is also held in escrow, outside the backups** (section 6), so a
   backup set that is somehow missing its config file is still recoverable.
3. **Every restore proves the key** with a decryption canary (`RESTORE.md`
   section 3.1). "Restore exited 0" is not evidence about the key.
4. The key does not change in normal operation; it is created with the site.
   A copy taken once at install and re-taken after any `set-config` is enough.
   Anyone who rotates it by hand invalidates every older backup's ciphertext
   unless the old key is kept. Do not rotate without writing the old one down.

---

## 2. What holds what

Three named volumes hold everything. Names below are the compose names;
Docker prefixes them with the project name. `install.sh` uses
`--project-name kamra` (so `kamra_sites`); plain `docker compose` in
`deploy/linux/` defaults the project to the directory name (so `linux_sites`).
**Read the real names off the install** - `docker volume ls` - before writing
anything that references one.

| Volume | Mounted by | Holds | Loss means |
| --- | --- | --- | --- |
| `sites` | configurator, backend, frontend, websocket, queue-short, queue-long, scheduler | `common_site_config.json`; per site: **`site_config.json` (the encryption key, the site DB user and password)**, `public/files`, `private/files` (**guest ID scans**, signed cards), and `private/backups/` | Secrets undecryptable; every uploaded file gone; Frappe's own backups gone with it |
| `db-data` | db | `/var/lib/mysql`: every site's database, plus MariaDB's own users | Every reservation, folio, guest, invoice |
| `redis-queue-data` | redis-queue | Pending background jobs | Queued jobs (e.g. outbound email) not yet run. Not backed up - see below |

`redis-cache` has no volume and is disposable by design.

Three consequences that are easy to miss:

- **Frappe's own backups live inside the `sites` volume** (`sites/<site>/private/backups/`).
  `docker compose down -v` deletes the data **and the backups made to protect
  it**. That directory is a staging area, never a destination.
- **`redis-queue-data` is deliberately not backed up.** Jobs in flight at the
  moment of a disaster are lost. The scheduler re-enqueues its cron entries on
  start, which is how the nightly jobs (`kamra/hooks.py`) come back **[not
  exercised]**; a one-off job - say a queued email - does not. Accepted loss.
- **The image is not in any backup.** It is built on the host as
  `kamra:local` (`CUSTOM_TAG=local`, `PULL_POLICY=never`), a mutable tag with
  no registry behind it. See section 4.4.

Host files outside the volumes, backed up separately and as secrets:
`/opt/kamra/kamra.env` (`DB_PASSWORD`; or `deploy/linux/.env`) and
`/opt/kamra/apps.json`. Per `algeria/BACKUP.md` section 3. A nuance to that
file: `kamra.env` is needed to reach a database whose `db-data` volume
survives. A rebuilt host with an empty `db-data` can probably choose a new
`DB_PASSWORD` **[not exercised]**. Keep the old one anyway; it costs nothing.

---

## 3. What one backup set contains

One set per run, assembled in a staging directory **on the host, outside the
volumes** (`/opt/kamra/backups/staging/<site>/<UTC timestamp>/`):

| File | Source | Present in |
| --- | --- | --- |
| database dump (`*-database.sql.gz`) | `bench --site <site> backup` | every set |
| public and private file archives | `bench --site <site> backup --with-files` | full sets only |
| `site_config.json` | `DC exec -T backend cat sites/<site>/site_config.json` | every set |
| `manifest.json` (proposed; nothing writes it today) | the job | every set |
| `SHA256SUMS` | the job | every set |

The manifest is what makes a later verification a test rather than a
formality (`RESTORE.md` section 2). It records, **at backup time**:

- site name, UTC timestamp, set kind (`full` / `db-only`)
- the output of `DC exec -T backend bench version` (Frappe and `kamra`
  versions), the image ID (`docker image inspect <image> --format '{{.Id}}'`)
  and `DC exec -T db mariadb --version`
- the count of tables in the site schema, and exact `COUNT(*)` per table,
  taken immediately **before** the dump
- the decryption canary ciphertext (`RESTORE.md` section 3.1) and the dump's size

Backup commands, run inside the job:

```bash
DC exec -T backend bench --site "$SITE" backup                # db-only set
DC exec -T backend bench --site "$SITE" backup --with-files   # full set
```

`--with-files` is verified in use in this repo (`algeria/BACKUP.md` section 2).
The dump is a logical dump, taken while the site is live; Frappe's dump should
use a single consistent InnoDB snapshot **[confirm; it is framework
behaviour]**. The database and the file archives are **not** captured
atomically: a scan uploaded between the two can be in one and not the other.
Verification tolerates a small mismatch for that reason (`RESTORE.md` section 2).

A set is "good" only when `gzip -t` passes on the dump, `tar -tf` passes on
each archive, the config file is non-empty and `SHA256SUMS` was written
**after** those checks. These catch truncation and disk-full, nothing more.
They are not a restore and the job must not report them as one.

---

## 4. Schedule and retention

### 4.1 Cadence

Times are host local time, which must equal the site timezone
(`Africa/Algiers`) - check both. The cron schedule in `kamra/hooks.py` puts
writers on the clock: night audit 03:00, guest-retention erasure 03:30, demo
reset 04:15, enquiry purge 04:45. **`algeria/BACKUP.md` sections 6-7 schedule
the backup at 03:30, on top of the retention job and 30 minutes into the night
audit.** A dump taken mid-audit is consistent but captures a half-closed day.
This design puts the full backup after the last writer. (How long the night
audit actually takes on a real property has not been measured.)

| Set | Contents | When | Why |
| --- | --- | --- | --- |
| **Full** | database + files + config | 05:30 daily | After the last scheduled writer; one quiet, complete set a day |
| **Intra-day** | database + config only | 01:00, 09:00, 13:00, 17:00, 21:00 | Caps the longest unprotected stretch at 4.5 h (01:00 to 05:30). Database only: cheap enough to run while the desk works |

Single-hotel profiles that cannot afford the intra-day sets can run the full
backup alone; the resulting RPO is stated in `DISASTER_RECOVERY.md` section 2.
That is a legitimate choice. It is just a 24-hour one.

Do not run a set while another is running (`flock`). Do not run during an
update. Back up immediately before any update or migration regardless of
schedule (`algeria/BACKUP.md` section 9); `install.sh update` does not do this
for you (audit, "Update has no rollback").

### 4.2 Promotion and retention - configurable

Weekly and monthly copies are not extra backups; they are the daily full set
kept longer. The job promotes: the first full set of an ISO week is the
weekly, the first of a calendar month is the monthly. Retention is a
per-destination setting, never a constant in a script.

Proposed settings (a config file the future job reads; **nothing reads it
today**):

| Key | Suggested default | Meaning |
| --- | --- | --- |
| `KEEP_INTRADAY` | 3 days | Database-only sets |
| `KEEP_DAILY` | 7 | Daily full sets |
| `KEEP_WEEKLY` | 4 | |
| `KEEP_MONTHLY` | 12 | |
| `KEEP_BEFORE_UPDATE` | until next successful update, plus one | Pre-update sets, never auto-pruned inside that window |
| `MIN_FREE_GB` | 2x the latest full set | Job refuses to start below it |

**7 / 4 / 12 is a starting point, not a requirement.** Two things override it
and neither is IT's to decide:

- **Accounting and tax retention.** The hotel's accountant sets how long
  invoice history must be recoverable. It is usually far longer than 7 days,
  and may mean a monthly kept for years.
- **Guest identity documents.** Backups contain ID scans and guest personal
  data - personal data under Algerian Law 18-07. The live system erases a
  scan at checkout (`kamra/id_documents.py`) and `apply_retention` erases idle
  guests nightly (`kamra/hooks.py`, 03:30). **Every backup older than that
  erasure still holds the data**, and a restore brings it back. Long backup
  retention and short live retention are in direct tension. Set `KEEP_*` for
  every destination deliberately, write it down, and make sure the privacy
  notice a guest reads is true. A 12-month monthly keeps a scan roughly a
  year past the day the guest was told it was deleted.

Inside the `sites` volume, set Frappe's own limit high enough to cover the
intra-day sets so it does not prune a set before it has been copied out
(`bench --site <site> set-config backup_limit <n>`, `algeria/BACKUP.md`
section 2). What `backup_limit` counts when sets of different kinds mix is
**[confirm]**.

### 4.3 Where it is scheduled

**Implemented** for Linux hosts: `deploy/systemd/install-timers.sh` installs

| Unit | When | What |
| --- | --- | --- |
| `ziri-backup.timer` | daily 05:30 local | one set, then pruning to `KEEP_SETS` (default 14) |
| `ziri-verify.timer` | Sunday 06:30 local | level 1 verification of the newest set |

Both carry `Persistent=true`, which is the reason this is a systemd timer and
not a `cron` entry: a hotel server that was off, asleep or mid-update at 05:30
backs up as soon as it is back instead of silently skipping the night. The two
units take the same `flock`, so a verification and a dump never run at once -
the daily backup waits up to 30 minutes for the weekly verify, and the weekly
verify skips rather than queue behind a backup.

The installer runs one backup immediately and fails if it does not work, since
an enabled timer only proves systemd accepted the file.

Until this existed the schedule was documented here and nowhere else:
`backup-verify.sh` ran when a human ran it, which is the same protection as no
script at all (`PRODUCTIZATION_AUDIT.md`, gap section 22).

Other hosts: `cron` or a timer by hand, as `algeria/BACKUP.md` section 7.
Windows: Task Scheduler as `algeria/BACKUP.md` section 6, with the structural
weakness stated there - Docker Desktop is a user-session app, so a Windows
hotel server that is asleep, locked out or not logged in backs up nothing. This
design does not fix that; it only refuses to hide it (section 8).

### 4.4 The image is a dependency of the backup

A backup restores into *some* version of the application. Rebuilding the image
is documented as a **20 to 45 minute build** (`deploy/linux/README.md`) that
needs the internet for base images and for `git clone`, and it builds from
branches (`FRAPPE_BRANCH=version-16`, the `apps.json` branch) that move. A
rebuild on a bad day can produce a different version from the one that wrote
the backup, over a link that is down. So:

- Record the image ID and `bench version` in every manifest (section 3).
- Before any update, tag what is running so it survives the rebuild:
  `docker tag kamra:local kamra:pre-<version>`.
- Where connectivity is poor, keep an archive of the image off-host
  (`docker save kamra:local | gzip`). Its size has not been measured; do not
  assume it is small.

The image archive is optional for a site with reliable internet and
effectively required for one without. Its effect on RTO is in
`DISASTER_RECOVERY.md` section 2.

---

## 5. Destinations

Every set is written to the host staging area first, then copied. A set that
exists only in staging, or only in the `sites` volume, is not protected.

| Destination | Survives | Does not survive | Notes |
| --- | --- | --- | --- |
| **Local disk** (second physical disk, or a directory on the same disk) | Corruption, deletion, bad update, `down -v` (if not in the volume) | Disk failure (same disk), fire, theft, ransomware on the host | A directory on the system disk guards against software mistakes only. Say that out loud when presenting it as "a backup" |
| **External USB disk** | Host failure, host ransomware **if unplugged** | Fire/theft if kept beside the server | Two disks, swapped weekly, one kept in another building. Guard the mount: a job writing to an unmounted mountpoint fills the system disk and "succeeds". Check `mountpoint -q <path>` first and fail otherwise |
| **NAS** | Host failure | Ransomware that can reach the share; fire if in the same room | Mounted read-write on the host means it is only as safe as the host. Prefer NAS-side snapshots the host cannot delete, or have the NAS pull |
| **S3-compatible object storage** | Site loss | Credentials stolen from the host if they can delete; provider loss | Use credentials that can write but not delete, and bucket versioning or object lock. Needs internet and a payment route that works in Algeria. **Cross-border transfer of personal data is regulated under Law 18-07; this has not been analysed here - get advice before pointing backups containing ID scans at a provider abroad.** Client-side encryption (section 6) reduces exposure; it does not by itself answer the legal question |
| **Remote server** (the owner's other site, a second property, a VPS) | Site loss | Same-credential compromise | SFTP/SSH. Best done as a pull from the remote end, or to an append-only target, so the hotel host cannot rewrite history |

**Local-only is fully supported.** Many Algerian properties will have an
unreliable or slow link, and a design that needs a cloud to be safe is a design
for somewhere else. The local-only profile is: full and intra-day sets to a
second disk, plus the weekly full set to an external disk that **leaves the
building**. It is weaker (no automatic off-site copy; RPO for site loss is the
age of the last disk swap, up to a week) and `DISASTER_RECOVERY.md` quotes it
that way. It is a valid configuration with known limits, not a degraded mode
to apologise for.

**Requirement for any profile: at least one copy that the production host
cannot modify or delete.** An unplugged disk, a pull from another machine, an
append-only or object-locked target - any of these. Without it, the first host
compromise (`DISASTER_RECOVERY.md`, ransomware) deletes the backups too.

Network loss is normal operation, not an error: sets queue in staging and ship
when the link returns. The staleness of the last *shipped* set, not the last
*taken* set, is the number that matters (section 8).

---

## 6. Encrypting the backups, and the key to that

Backups contain guest ID scans, the site encryption key and the site database
password. An unencrypted backup on a USB disk is a data breach waiting for a
bag to be left on a train. **Every copy that leaves the host is encrypted.**

### 6.1 Reference design

One tool for encryption, deduplication, retention and multiple destinations:
**restic** (local path, SFTP, S3-compatible and a mounted NAS are all
repository types). It is a design choice, not something installed or tested
here; the version is unspecified and every command below is unrun.

```bash
restic -r <repo> backup --tag full    /opt/kamra/backups/staging/<site>/<ts>
restic -r <repo> backup --tag db-only /opt/kamra/backups/staging/<site>/<ts>

restic -r <repo> forget --tag db-only --keep-within 3d
restic -r <repo> forget --tag full --keep-daily 7 --keep-weekly 4 --keep-monthly 12
```

(Retention values come from the section 4.2 config, not literals. `forget
--prune` needs delete rights; per section 5, run that step from a different
machine or credential than the one that backs up.)

Without restic, `age` encryption of a tarball plus `rsync` and a `find -mtime`
pruning script does the same job with less. Not detailed here.

### 6.2 Where the backup key lives

An unattended job must be able to encrypt, so the repository password is
readable by the job: `/etc/kamra/restic.pass`, root-only, mode 0400. State
plainly what that buys. Backups are protected **at rest at the destination**
(stolen disk, NAS, bucket, provider). They are **not** protected against
someone who owns the host, who can read the password file. Public-key
encryption (`age` with a recipient key, private key never on the host) would
close that gap for the encrypt side, at the cost of a clumsier restore. The
design accepts the trade-off; it does not pretend it away.

**The escrow record** - three items, the only things needed to turn a bare
disk of backups plus a new machine back into a hotel:

1. the backup repository password (or the age private key)
2. a copy of `site_config.json` (carrying the encryption key)
3. a copy of `kamra.env` / `.env` (`DB_PASSWORD`)

Where: a password-manager entry **and** a sealed printed copy, in different
places - for example the hotel safe, and the owner's home or the accountant's
safe. Not on the server. Not in an email thread. Not only in the integrator's
laptop.

**Who holds it.** Named people, written down:

| Role | Who | Holds |
| --- | --- | --- |
| Primary custodian | the owner or general manager | the escrow record |
| Secondary custodian | one other person who is not the integrator | a second sealed copy |
| Operator | whoever runs the backups (may be the integrator) | **does not** need the escrow record day-to-day |

An integrator may hold the secondary copy under a written agreement. Hotel
ownership must never depend on a single outside party being reachable.

### 6.3 If the key is lost

State it without softening: **if the repository password is lost, every
encrypted backup under it is unrecoverable.** There is no reset, no vendor
bypass and no support route; that is the point of encryption. What remains:

- If the live system is still running, take a fresh backup under a new
  password immediately, escrow it properly, and treat the old backups as gone.
- If the live system is also gone, the data is gone.

If only the Frappe `encryption_key` is lost while the backups still decrypt
(for example the set had no config file and escrow is empty), the hotel's
operational data is intact and the stored integration credentials are not:
re-enter every gateway, SMTP and API secret by hand. Recoverable, and a bad
afternoon.

### 6.4 Prove the key works

The automated checks in `RESTORE.md` run on the host that holds the password
file. They prove the *server's* copy works. They do not prove the **escrow**
copy works - which is the copy that matters in a disaster. So, at least
quarterly, the primary custodian, with the operator absent, retrieves the
escrow record and decrypts one real backup with it. A custodian who cannot do
that has found out on a day with nothing at stake.

---

## 7. What must never be stored beside a backup

"Beside" means: the same directory, the same disk, the same bucket, the same
person's custody, or the same unencrypted archive.

| Never beside the backup | Because |
| --- | --- |
| The backup repository password / age private key | It is the lock and the key in one place |
| `kamra.env` / `.env` in plaintext | `DB_PASSWORD` is the MariaDB root password |
| A plaintext `site_config.json` outside the encrypted set | Holds the encryption key and the site DB password. With the dump beside it, every stored secret decrypts |
| Frappe's plaintext `*-site_config_backup.json` **[confirm it exists]** left in an unencrypted staging or local directory | Same reason, placed there by the tool. Treat the local `private/backups/` and the staging area as sensitive: mode 0700, on an encrypted host disk where practicable |
| Cloud or NAS credentials with delete rights | A compromised host then deletes every copy |
| The verification stack's data after a test | A restore test makes a second copy of real guest data on a possibly less-protected machine. Destroy it (`RESTORE.md` section 2) |
| Anything inside the git working tree | `algeria/BACKUP.md` section 3 makes the same point; the `.gitignore` and `gitleaks` protections are bypassed by a backup folder in a clone |

The set inside the encrypted repository *does* contain `site_config.json`
(section 3) - that is deliberate: the encryption protects it at rest, and a set
missing its config is incomplete. The rule is about the **escrow** and the
**unencrypted** copies.

---

## 8. Seeing that it is working

The application already reports on backups. `kamra/health.py` has
`_backup_check()`, surfaced on `/kamra/health`. Read what it actually does:

- it globs `*.sql.gz` in the site's own `private/backups/` and reports the age
  of the newest;
- it goes to "attention" past **48 hours** (a constant in the code);
- it is deliberately never "failed", and its own text says it does not prove
  restorability.

So it cannot see the host staging area, any off-site copy, a failed copy, an
intra-day cadence (48 h is far too loose for 4.5 h) or the last verification.
A passing `_backup_check` means "Frappe wrote a dump recently". It does not
mean "the hotel is protected". (The audit's gap list records backup freshness
as unchecked; this check exists in the file as read, and the audit's wider
point stands: it is age only.)

The numbers the operator should actually watch, once a job exists to produce
them:

| Signal | Healthy | Why this one |
| --- | --- | --- |
| Age of the newest set **taken** | below one cadence interval plus slack | The job is running |
| Age of the newest set **shipped** to each destination | same | The thing that bounds RPO off-site |
| Age of the last **verification** that passed, and whether it ran Level 1 or 2 | within `RESTORE.md` section 5 cadence | A copy never tested is not evidence |
| Free disk against `MIN_FREE_GB` | above | A full disk is the commonest silent failure |

A job that cannot reach Docker, or the disk, or the destination, must exit
non-zero and leave a status file saying so. A scheduler that "ran" is not a
backup that happened (`algeria/BACKUP.md` section 6).

---

## What this does not cover / has not been tested

- **Nothing here has been run.** The job, the config file, the manifest, the
  staging layout, the `restic` commands and the retention behaviour are a
  design. No script exists. No backup produced by this design exists.
- **The compose stack has only ever run on Docker Desktop over WSL2**, on one
  machine, never on the Linux server it is written for (audit, "What this
  document does not establish"). Nothing about volume names, mount behaviour
  or scheduling has been seen on Linux.
- **Frappe behaviours assumed and not checkable from this repository:** whether
  `bench backup` writes a `site_config_backup.json`; whether its dump is a
  single-snapshot dump; what `backup_limit` counts; the exact file names; the
  restore flags. All must be read off the installed image.
- **No measured sizes or durations**: dump size, files-archive size, time to
  back up, time to ship, image-archive size, night-audit duration, free-space
  need. The `MIN_FREE_GB` default is a placeholder rule, not a measurement.
- **Which fields are encrypted** in this application has not been enumerated.
  "Every `Password`-type field" is Frappe's rule; the app's own fields were not
  audited.
- **Cross-border transfer, retention periods and breach duties under Law
  18-07** were not analysed. They are flagged as decisions for the hotel and
  its legal adviser, not answered.
- **Multi-site hosts** (several Frappe sites in one bench): the unit of backup
  is the site. A loop over sites is the intent; `bench --site all backup`
  semantics are not verified.
- **Windows hosts**: the Docker Desktop session limitation in
  `algeria/BACKUP.md` section 6 is unresolved by this design.
- The whole-volume cold copy (stop the stack, archive `sites` and `db-data`)
  is mentioned in `DISASTER_RECOVERY.md` as a pre-update option; it is not
  specified here and has not been tried.
