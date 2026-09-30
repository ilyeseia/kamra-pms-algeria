# Backup and restore — Algeria Distribution

For a hotel that cannot lose reservations.

A PMS holds the only record of who is arriving tonight, what they agreed to
pay, what they have already paid, and what the hotel owes the tax authority.
Losing it is not an IT inconvenience; it is a hotel that cannot check anyone in
and cannot invoice anyone who has left.

This document gives the exact commands for the Docker install described in
[`INSTALLATION.md`](INSTALLATION.md), what to back up besides the database, how
to schedule it on Windows, and — the part most people skip — **how to prove a
restore works**.

Where a command's exact form could not be verified from this repository, it is
marked. Nothing below is invented.

---

## 1. How commands reach `bench`

Everything runs inside the `backend` container. The compose invocation is the
one `install.sh` uses itself (`deploy/install.sh:178-184`), run from the
`frappe_docker` directory it checks out (`deploy/install.sh:150`):

```bash
cd /opt/kamra/frappe_docker
docker compose --project-name kamra --env-file /opt/kamra/kamra.env \
  -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.noproxy.yaml \
  exec -T backend <bench command>
```

All four `-f` overrides, the project name and the env file are required. A bare
`docker compose exec backend …` will not find the stack.

For readability the rest of this document writes that prefix as `<COMPOSE>`:

```bash
<COMPOSE> exec -T backend bench --site pms.hotel.dz backup --with-files
```

On the Windows 10 / WSL2 install, run it inside the WSL distribution, or from
PowerShell through `wsl -d <Distro> -- bash -lc "…"`. Docker Desktop must be
running; if it is not, the command fails immediately and any scheduled job
silently produces nothing. See §6.

Define it once in a shell:

```bash
KC='docker compose --project-name kamra --env-file /opt/kamra/kamra.env
    -f compose.yaml -f overrides/compose.mariadb.yaml
    -f overrides/compose.redis.yaml -f overrides/compose.noproxy.yaml'
cd /opt/kamra/frappe_docker
docker compose $KC exec -T backend bench --version   # sanity check first
```

`install.sh` uses `exec -T backend bench --version` as its own readiness probe
(`deploy/install.sh:189`), so that is a good first test.

---

## 2. Taking a backup

### Database plus files

```bash
<COMPOSE> exec -T backend bench --site pms.hotel.dz backup --with-files
```

This is Frappe's own command. `--with-files` is confirmed in use across this
repository — `docs/self-hosting.md:79-80`, `docs-site/self-hosting/index.md:69`
and `kamra/id_documents.py:27`, the last of which notes specifically that it
"tars private/files".

**Always use `--with-files`.** A database-only backup restores a hotel whose
guest ID scans, signed registration cards, invoice attachments and uploaded
documents have all vanished. For an Algerian house that keeps a *fiche de
police* trail, that is not a partial backup, it is a compliance problem.

### Where the archives land

Frappe writes site backups into the site's own private backup directory:

```
sites/<site>/private/backups/
```

inside the container, which is the `sites` volume the compose stack mounts.
Each run produces a timestamped set: the database dump, and — with
`--with-files` — separate tarballs for public and private files.

> **Not verified from this repository.** The exact filenames and the number of
> archives per run are Frappe framework behaviour, not Kamra's, and the
> framework is not vendored here — `frappe_docker` is fetched at install time
> (`deploy/install.sh:139-151`). Do not script against an assumed filename
> pattern. List the directory on the actual install and read the real names:
>
> ```bash
> <COMPOSE> exec -T backend ls -lh sites/pms.hotel.dz/private/backups/
> ```
>
> The same caution applies to the volume's name on the Docker host: it is
> derived from the compose project (`kamra`) and the volume name in upstream
> `frappe_docker`'s `compose.yaml`, which this repository does not contain.
> Read it off the install rather than guessing:
>
> ```bash
> docker volume ls | grep kamra
> ```

### Getting the archive off the machine

A backup that only exists inside the container is not a backup — `down -v`,
a corrupted volume or a dead disk takes it with everything else. Copy it out:

```bash
# list first, then copy the real names you saw
<COMPOSE> exec -T backend ls -1 sites/pms.hotel.dz/private/backups/

# copy the whole backup directory out of the container to the host
docker cp kamra-backend-1:/home/frappe/frappe-bench/sites/pms.hotel.dz/private/backups/. \
  /opt/kamra/backups/
```

> **Not verified:** the container name (`kamra-backend-1`) and the bench path
> inside the container (`/home/frappe/frappe-bench`) both come from upstream
> `frappe_docker`, not from this repository. Confirm both on the install:
>
> ```bash
> <COMPOSE> ps                      # real container names
> <COMPOSE> exec -T backend pwd     # the bench working directory
> ```
>
> `install.sh` runs `bench` with relative paths like
> `sites/${SITE_NAME}/site_config.json` (`deploy/install.sh:299`), which
> confirms the container's working directory *is* the bench root — but not what
> that path is. Read it.

Then copy from the host to somewhere else entirely: an external disk, a NAS,
object storage, the hotel's own cloud drive. **Different machine, different
building.** A hotel's server and its backup drive in the same office share the
same fire.

### Retention inside the site

Frappe prunes its own backup directory to a configurable limit:

```bash
<COMPOSE> exec -T backend bench --site pms.hotel.dz set-config backup_limit 10
```

Confirmed in `docs/self-hosting.md:79`. Ten is a reasonable figure for a daily
schedule — roughly ten days of local history, with your off-site copies
carrying the longer tail.

---

## 3. What must be backed up besides the database

The database is the largest part, not the whole part.

| What | Where | Why it matters | Covered by `backup --with-files`? |
| --- | --- | --- | --- |
| Site database | in MariaDB | Everything: reservations, folios, invoices, guests, users | Yes |
| Private files | `sites/<site>/private/files` | Guest ID scans, signed registration cards, private attachments | Yes |
| Public files | `sites/<site>/public/files` | Property photos, logos, menu images | Yes |
| **`/opt/kamra/kamra.env`** | host | **The MariaDB password.** Mode 600 | **No** |
| `/opt/kamra/apps.json` | host | Which repository and branch are installed | No |
| `sites/<site>/site_config.json` | in the container | Site-level config, encryption key | No |

### `kamra.env` — the one people forget

`deploy/install.sh:277-289` writes it with `umask 077`, so mode 600, and it
contains `DB_PASSWORD`. A re-run reads it back rather than generating a new one
(`deploy/install.sh:257-260`), precisely so MariaDB keeps working.

If you lose `kamra.env` you may find a database dump you cannot get into a
rebuilt stack without a password-reset detour. Back it up — **separately, and
treated as a secret**, not dropped in the same world-readable folder as the
dumps. It is 8 lines; a password manager entry or an encrypted archive is
enough.

Do not commit it. `.gitignore` on this branch closes `kamra.env` along with
`site_config.json`, `*.pem`, `.env.*` and `id_rsa*`, and a `gitleaks` pre-commit
hook scans the staged diff — but a backup folder inside a working tree is
exactly how that protection gets bypassed. Keep backups outside the repository.

### `site_config.json` and the encryption key

Frappe stores an `encryption_key` in the site config and uses it for stored
passwords and secrets (payment gateway keys, SMTP credentials, API keys).

> **Not verified from this repository** whether Frappe's own `backup` command
> includes `site_config.json` in its archive set. Do not assume either way.
> Back it up explicitly and keep it with `kamra.env` as a secret:
>
> ```bash
> <COMPOSE> exec -T backend cat sites/pms.hotel.dz/site_config.json
> ```
>
> The practical consequence of getting this wrong: the database restores, the
> hotel signs in, and then every stored integration credential is
> undecryptable and must be re-entered by hand. Recoverable, but a bad
> afternoon — and one you should find out about during the restore test in §5,
> not during a real outage.

---

## 4. Restoring

### Before you restore anything

Restoring **overwrites the target site's database**. Two rules:

1. **Back up the current state first**, even when it is broken. A broken
   database you still have beats a broken database you overwrote.
2. **Practise on a throwaway site**, never on the live one. See §5.

### The command

Frappe's restore is:

```bash
<COMPOSE> exec -T backend bench --site pms.hotel.dz restore <path-to-sql-dump> \
  --db-root-password "<DB_PASSWORD from /opt/kamra/kamra.env>"
```

The `--db-root-password` flag is used the same way by `install.sh` when it
creates the site (`deploy/install.sh:303`), so that part is verified here.

> **Not verified from this repository:** the flag names for restoring the file
> archives alongside the dump. Frappe's restore accepts options for the public
> and private file tarballs, but the exact spelling belongs to the framework
> version in the built image, not to this repository. **Read them off the
> install rather than trusting any flag written down here or elsewhere:**
>
> ```bash
> <COMPOSE> exec -T backend bench --site pms.hotel.dz restore --help
> ```
>
> Do this once on the trial install, write the real invocation into the
> client's runbook, and use that. A restore is the worst possible moment to
> discover a flag was renamed.

The dump must be reachable from inside the container. Copy it into the sites
volume first if you are restoring an archive you took off the machine:

```bash
docker cp ./20260930_pms-hotel-dz-database.sql.gz \
  kamra-backend-1:/home/frappe/frappe-bench/sites/pms.hotel.dz/private/backups/
```

(Container name and path: confirm as in §2.)

### After every restore

```bash
<COMPOSE> exec -T backend bench --site pms.hotel.dz migrate
<COMPOSE> exec -T backend bench --site pms.hotel.dz clear-cache
```

`install.sh update` runs exactly this pair after a rebuild
(`deploy/install.sh:235-236`). The `migrate` matters when the backup came from
an older build than the running image — and note that on this distribution
that is the path on which `v36` and `v37` run, which have never executed
against a database at all ([`INSTALLATION.md`](INSTALLATION.md) §8.2).

Then verify. A restore is not finished because a command exited zero:

- sign in
- open today's arrivals and departures — are the right reservations there?
- open a folio with payments on it — do the totals match what you remember?
- open a guest with an uploaded ID — **does the image actually load?** This is
  the check that catches a files-archive that never restored
- print one invoice — is the RC/NIF/NIS/AI footer intact?
- `bench --site <site> doctor` — is the scheduler still enabled?

### One thing a restore will bring back with it

`kamra/id_documents.py:18-31` notes it directly: guest ID images are deleted at
checkout under the property's retention policy, but `backup --with-files` tars
`private/files` — so **a scan deleted for retention still exists in every
backup taken before the deletion**, and a restore brings it back.

No code fixes this; it is a backup-rotation decision. For an Algerian hotel
under Law 18-07 (ANPDP), it is worth deciding deliberately: how long do you
keep backups that contain guest identity documents, and who can read them? A
90-day off-site retention is a different privacy posture from a seven-year one.
Whatever you choose, do not let the guest-facing copy promise a deletion the
backups quietly undo.

---

## 5. Test your restore — this is not optional

**A backup nobody has restored is not a backup. It is a file.**

Every real backup failure looks the same in hindsight: the job ran nightly for
two years, the archives were all there, and not one of them restored — wrong
flag, truncated dump, missing files tarball, lost encryption key, a password
nobody had. The failure was always present; only the discovery was delayed
until it was expensive.

So: **do a full restore before handover, and once a quarter after.**

### The procedure

1. Take a fresh backup of the live site, with `--with-files`.
2. Copy it, plus `kamra.env` and `site_config.json`, off the machine.
3. Create a **separate throwaway site** on the same stack:

   ```bash
   <COMPOSE> exec -T backend bench new-site restore-test.localhost \
     --mariadb-user-host-login-scope='%' \
     --db-root-password "<DB_PASSWORD>" \
     --admin-password "<a throwaway password>" \
     --install-app payments --install-app kamra --no-mariadb-socket
   ```

   Those flags are exactly what `install.sh` uses (`deploy/install.sh:301-305`),
   so they are verified. Better still, do this on a different machine
   entirely — that also proves the archive is portable, which is the thing you
   actually need in a disaster.

4. Restore the backup into `restore-test.localhost`.
5. `migrate`, `clear-cache`, then work the verification list in §4.
6. **Write down what you had to do**, including any flag you had to look up,
   and the real filenames. That note is the runbook the hotel uses at 2am.
7. Delete the test site:

   ```bash
   <COMPOSE> exec -T backend bench drop-site restore-test.localhost \
     --db-root-password "<DB_PASSWORD>"
   ```

   > **Not verified:** `drop-site`'s exact flags in this Frappe version. Check
   > `bench drop-site --help` first.

### What the test must prove

| Claim | How the test proves it |
| --- | --- |
| The dump is readable | `restore` completes |
| The schema matches the running code | `migrate` completes clean |
| Reservations survived | Today's arrivals list is right |
| Money survived | A folio's totals match |
| **Files survived** | A guest ID image **loads in the browser** |
| Secrets survived | A stored gateway or SMTP credential still works |
| Someone can actually do this | It was done by following the written runbook |

If the test fails, you have found a problem on a day when nothing is at stake.
That is the entire value of it.

---

## 6. Scheduling on Windows 10 (WSL2 install)

WSL has no always-on cron by default, so the schedule lives in **Windows Task
Scheduler**, calling into WSL.

### The script

Create it **inside WSL**, not on the Windows filesystem — a script on `/mnt/c`
can pick up CRLF line endings and fail with `bad interpreter`.

`/opt/kamra/backup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

SITE="pms.hotel.dz"
OUT="/opt/kamra/backups"
cd /opt/kamra/frappe_docker

compose() {
  docker compose --project-name kamra --env-file /opt/kamra/kamra.env \
    -f compose.yaml \
    -f overrides/compose.mariadb.yaml \
    -f overrides/compose.redis.yaml \
    -f overrides/compose.noproxy.yaml "$@"
}

# Fail loudly if Docker Desktop is not running — otherwise this job
# "succeeds" every night and produces nothing.
compose exec -T backend bench --version >/dev/null

compose exec -T backend bench --site "$SITE" backup --with-files

mkdir -p "$OUT"
# Read the real container name and bench path once (see BACKUP.md §2)
# and hard-code them here after confirming them on this install.
docker cp "kamra-backend-1:/home/frappe/frappe-bench/sites/$SITE/private/backups/." "$OUT/"

echo "backup ok: $(date -Is)"
```

```bash
chmod +x /opt/kamra/backup.sh
```

Then run it by hand once and read the output before you schedule it.

### The task

```powershell
$action = New-ScheduledTaskAction -Execute "wsl.exe" `
  -Argument "-d Ubuntu -- bash -lc '/opt/kamra/backup.sh >> /opt/kamra/backup.log 2>&1'"
$trigger = New-ScheduledTaskTrigger -Daily -At 3:30am
Register-ScheduledTask -TaskName "Kamra backup" -Action $action -Trigger $trigger `
  -Description "Nightly Kamra PMS backup (Algeria Distribution)"
```

Replace `Ubuntu` with the actual distribution name from `wsl --list --verbose`.

Two Windows-specific facts that decide whether this ever runs:

- **Docker Desktop must be running.** If it starts at login and nobody is
  logged in, there is no Docker and the task fails. On Windows 10, a task set
  to "Run whether user is logged on or not" **still will not have Docker
  Desktop**, because Docker Desktop is a user-session application. This is a
  genuine structural weakness of the Windows profile, not a configuration
  detail — and one more reason [`INSTALLATION.md`](INSTALLATION.md) §2
  recommends a Linux host for production.
- **A sleeping or powered-off machine runs nothing.** Set the task's *Run task
  as soon as possible after a scheduled start is missed*, and either keep the
  machine awake at 03:30 or accept gaps. Task Scheduler's *Wake the computer to
  run this task* helps only if the power settings permit it.

### Copying off-site

Add a second step — `robocopy` to a NAS or external disk, `rclone` to object
storage, whatever the hotel already has. Do not leave the only copy on the
machine you are protecting against.

### Verify the schedule works

The day after you set it up:

```powershell
Get-ScheduledTaskInfo -TaskName "Kamra backup"   # LastRunTime, LastTaskResult
```

`LastTaskResult` must be `0`. Then look at the archive dates and at
`/opt/kamra/backup.log`. A backup job that has been failing silently for three
weeks is indistinguishable from no backup at all — check it, and put a monthly
reminder on someone's calendar to check it again.

---

## 7. Scheduling on a Linux host (the recommended profile)

Simpler, and the reason [`INSTALLATION.md`](INSTALLATION.md) §2 recommends it.
Same script, root's crontab:

```cron
30 3 * * * /opt/kamra/backup.sh >> /var/log/kamra-backup.log 2>&1
```

No Docker Desktop, no logged-in user, no sleeping laptop. `systemd` brings the
containers up after a reboot, and a `systemd` timer with `OnFailure=` gives you
real alerting if you want it.

---

## 8. Retention

A starting point, to be adjusted against the hotel's own obligations:

| Copy | Kept | Where |
| --- | --- | --- |
| Nightly, on the machine | 10 days (`backup_limit 10`) | site's private backups |
| Nightly, off-site | 30 days | NAS, external disk, or object storage |
| Monthly | 12 months | off-site, separate location |
| Before every update | until the next successful update, plus one | off-site |
| Before every migration | indefinitely, or per policy | off-site |
| `kamra.env` + `site_config.json` | current, as secrets | password manager or encrypted archive |

Two policy points that are decisions, not defaults:

- **Accounting retention.** Algerian commercial and tax retention obligations
  apply to invoice records. The hotel's accountant sets that number, not this
  document — and it is usually far longer than 30 days.
- **Guest identity documents.** Per §4, backups contain ID scans that the live
  site has since deleted for retention. Long backup retention and a short
  live-data retention policy are in tension. Decide it consciously, write it
  down, and make sure the privacy copy the guest reads is true.

---

## 9. Back up before these, every time

- Any `sudo /opt/kamra/install.sh update` — it runs
  `bench --site all migrate` (`deploy/install.sh:235`)
- Any `bench migrate`
- Any branch or tag switch (`KAMRA_BRANCH=… install.sh update`)
- Any bulk edit, import, or script run against real data
- Any change to the room levy mode or a TVA rate, before the next invoice run
- Before letting anyone experiment on the live site

On this distribution the first two carry extra weight: `v36` and `v37` have
never run against a database anywhere
([`INSTALLATION.md`](INSTALLATION.md) §8.2). A backup taken two minutes earlier
is the difference between a bad hour and a lost hotel.

---

## 10. Quick reference

```bash
# the prefix (run from /opt/kamra/frappe_docker)
docker compose --project-name kamra --env-file /opt/kamra/kamra.env \
  -f compose.yaml -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml -f overrides/compose.noproxy.yaml

# is the stack alive
<COMPOSE> exec -T backend bench --version

# back up
<COMPOSE> exec -T backend bench --site <site> backup --with-files

# what did it write
<COMPOSE> exec -T backend ls -lh sites/<site>/private/backups/

# retention inside the site
<COMPOSE> exec -T backend bench --site <site> set-config backup_limit 10

# restore (check --help for the file-archive flags first)
<COMPOSE> exec -T backend bench --site <site> restore <dump> --db-root-password "<pw>"
<COMPOSE> exec -T backend bench --site <site> migrate
<COMPOSE> exec -T backend bench --site <site> clear-cache

# health
<COMPOSE> exec -T backend bench --site <site> doctor
```

The database password is `DB_PASSWORD` in `/opt/kamra/kamra.env` (mode 600).

---

## See also

- [`INSTALLATION.md`](INSTALLATION.md) — install, verification, what is not proven
- [`LICENSING.md`](LICENSING.md) — AGPL-3.0 obligations
- [`VERSIONING.md`](VERSIONING.md) — which version a backup came from
- `deploy/README.md`, `deploy/TROUBLESHOOTING.md` — upstream self-host notes
