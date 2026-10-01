# ZIRI PMS — Technician Manual

For a technician who has never seen this install and is standing at (or SSH'd
into) the server. The product is called ZIRI PMS; the application inside it is
named `kamra` and that is the name you will see in container images, Python
modules and `bench` output.

This manual is written against what is actually in this repository. Where a
capability does not exist, it says so in those words and does not supply a
command. Read [Section 2](#2-what-exists-and-what-does-not) before you promise
a customer anything.

Companion documents:

- [`PRODUCTION_RUNBOOK.md`](PRODUCTION_RUNBOOK.md) — what to do when something is broken, ordered by how often it happens.
- [`../product/ERROR_CODES.md`](../product/ERROR_CODES.md) — the error taxonomy (a specification; nothing emits it yet).
- [`../../deploy/linux/README.md`](../../deploy/linux/README.md) — the compose stack and its troubleshooting table. This manual extends it and does not repeat it.
- [`../algeria/BACKUP.md`](../algeria/BACKUP.md) — backup and restore in depth. This manual gives the short form and points there.
- [`../algeria/INSTALLATION.md`](../algeria/INSTALLATION.md) — installation in depth.

---

## Contents

1. [Conventions, and how commands are labelled](#1-conventions-and-how-commands-are-labelled)
2. [What exists and what does not](#2-what-exists-and-what-does-not)
3. [The stack in one page](#3-the-stack-in-one-page)
4. [Install](#4-install)
5. [Diagnose: the first five minutes](#5-diagnose-the-first-five-minutes)
6. [Component checks](#6-component-checks)
7. [Collect logs](#7-collect-logs)
8. [Create a support bundle (does not exist yet)](#8-create-a-support-bundle-does-not-exist-yet)
9. [Specification: the support bundle that must be built](#9-specification-the-support-bundle-that-must-be-built)
10. [Back up](#10-back-up)
11. [Restore](#11-restore)
12. [Update](#12-update)
13. [Roll back](#13-roll-back)
14. [Migrate](#14-migrate)
15. [Recover a lost server](#15-recover-a-lost-server)
16. [Verify the licence (does not exist)](#16-verify-the-licence-does-not-exist)
17. [What this does not cover / has not been tested](#17-what-this-does-not-cover--has-not-been-tested)

---

## 1. Conventions, and how commands are labelled

### Two layouts exist. Know which one you are on.

| | Layout A — installed by `deploy/install.sh` | Layout B — `deploy/linux/` compose, run by hand |
| --- | --- | --- |
| Stack directory | `/opt/kamra/frappe_docker` | wherever `deploy/linux/` was copied |
| Secrets file | `/opt/kamra/kamra.env` (mode 600) | `.env` next to `docker-compose.yml` |
| Compose files | upstream `compose.yaml` + three overrides, project name `kamra` | the single flattened `docker-compose.yml` |
| MariaDB `start_period` | **upstream's 5 s** (see [R04](PRODUCTION_RUNBOOK.md#r04-docker-compose-up-fails-with-db-unhealthy)) | 180 s |
| Windows (WSL2) install | this layout, inside the WSL distribution | not used by the Windows installer |

Everything in this manual is written with a shell function, `dc`, so the same
command works on both. Define it once per shell, **as root** (shell functions
do not survive `sudo`):

```bash
# Layout A
cd /opt/kamra/frappe_docker
dc() { docker compose --project-name kamra --env-file /opt/kamra/kamra.env \
  -f compose.yaml -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml -f overrides/compose.noproxy.yaml "$@"; }
```

```bash
# Layout B
cd /path/to/deploy/linux
dc() { docker compose "$@"; }
```

Then name the site. It must equal `FRAPPE_SITE_NAME_HEADER` in the env file:

```bash
export SITE=pms.yourhotel.dz
```

Rules used throughout:

- Commands address **service names** (`backend`, `db`, ...), never container
  names. Container names depend on the compose project name and differ between
  layouts.
- `dc exec -T` is used wherever the command is piped or has a here-document.
  `-T` disables the pseudo-terminal; without it, piped input fails.
- On the Windows install, run everything inside the WSL distribution:
  `wsl -d <Distro> -- bash -lc "..."`. **Docker Desktop must be running**, and
  it is a user-session application: nothing works while nobody is logged in
  ([`BACKUP.md` §6](../algeria/BACKUP.md)).

### Provenance labels

This author could not run these commands against a live stack while writing.
Each section therefore says where its commands come from:

| Label | Meaning |
| --- | --- |
| **[live]** | Used on the live install, per the incident record. Still re-check the output on your own site. |
| **[repo]** | Taken from a file in this repository (`install.sh`, `BACKUP.md`, `INSTALLATION.md`, the compose file, `health.py`). |
| **[standard]** | Standard Docker / Frappe `bench` / MariaDB / Redis / OpenSSL usage that is expected to work against this stack but has **not been executed against it by the author**. Run it on a trial site first. |

If a **[standard]** command behaves differently on your install, trust the
install and correct this document.

### Two safety rules that apply to every section

1. **`docker compose down -v` destroys the hotel.** It deletes the `sites`,
   `db-data` and `redis-queue-data` volumes. `docker compose down` (no `-v`)
   keeps them. Never type the `-v` form on a customer machine.
2. **Never paste a secret into a ticket, chat or email.** `DB_PASSWORD`,
   `site_config.json` (which holds the database password and the encryption
   key) and anything printed by `docker inspect` on the `db` container
   (`MYSQL_ROOT_PASSWORD` is in its environment) are secrets. See
   [Section 9](#9-specification-the-support-bundle-that-must-be-built).

---

## 2. What exists and what does not

Measured against the repository (see
[`../product/PRODUCTIZATION_AUDIT.md`](../product/PRODUCTIZATION_AUDIT.md)).
"Does not exist" means a repository-wide search found no code.

| Capability | State | Where / what is true |
| --- | --- | --- |
| Install | Exists | `deploy/install.sh`, or `deploy/linux/` by hand, or the Windows installer driving `install.sh` in WSL2. The compose stack has been run end to end **only on Docker Desktop over WSL2, never on a Linux server**. |
| Health read-out | Partial | `kamra/health.py`, shown at `/kamra/health`. Ten checks (version, Frappe, apps, database, Redis, workers, scheduler, backup age, disk, time zone). **No** container-state, TLS, migration-status or licence check. |
| Log access | Manual only | `docker compose logs`; the `Error Log` doctype. The compose file configures **no log rotation** ([R09](PRODUCTION_RUNBOOK.md#r09-disk-full)). |
| **Support bundle** | **Does not exist** | Zero code. [Section 8](#8-create-a-support-bundle-does-not-exist-yet) is a by-hand stand-in; [Section 9](#9-specification-the-support-bundle-that-must-be-built) specifies the real one. |
| Backup (manual) | Exists | `bench --site <site> backup --with-files`. |
| Backup (scheduled) | Does not exist in the product | No scheduler job takes backups. The documented approach is host cron / Windows Task Scheduler running a script that is *itself written by hand* (`BACKUP.md` §6–7). |
| Backup verification | Does not exist | `health.py` reports backup **age only** and says so. Nothing proves a backup restores. |
| Restore | Manual | `bench --site <site> restore`. Flags for the file archives must be read from `--help` on the install. |
| Update | Exists, unguarded | `install.sh update`: rebuild, recreate, `bench --site all migrate`. No pre-flight, no backup-before, no health gate afterward. |
| **Rollback** | **Does not exist** | No tool, no script. [Section 13](#13-roll-back) is a manual procedure built from Docker and Frappe primitives and has **never been exercised**. |
| Migrate | Exists | `bench migrate`. Patches `v36` and `v37` have been applied on the live install. |
| Disaster recovery | Manual | [Section 15](#15-recover-a-lost-server). Never exercised end to end. |
| TLS | Outside the stack | The compose file publishes plain HTTP on `HTTP_PUBLISH_PORT`. TLS is whatever proxy the technician puts in front. No check in the product. |
| **Licence verification** | **Does not exist** | Zero code for a commercial licence, activation, grace period or enforcement. `docs/algeria/LICENSING.md` documents AGPL-3.0 obligations, which is a different thing. [Section 16](#16-verify-the-licence-does-not-exist). |
| Installation ID | Does not exist | Zero code. A support bundle cannot yet carry a stable identifier for the installation. |
| Monitoring, metrics, alerting | Does not exist | Zero code. A dead scheduler tells nobody. |
| Error-code taxonomy | Does not exist | Specified in [`ERROR_CODES.md`](../product/ERROR_CODES.md); emitted by nothing. |

---

## 3. The stack in one page

Ten services (`deploy/linux/docker-compose.yml`). Memorise the right-hand
column; it is how you triage.

| Service | Image | Does | If it is down |
| --- | --- | --- | --- |
| `configurator` | app image | **One-shot.** Writes db/redis hosts into the shared `sites` volume, then exits. Must read `Exited (0)`. | Nothing else starts. |
| `backend` | app image | gunicorn serving the Frappe app on :8000 | Pages and API fail (nginx answers 502). |
| `frontend` | app image | **nginx**, published on the host as `HTTP_PUBLISH_PORT` (default 8080). Proxies to `backend:8000` and `websocket:9000`. | Nothing is reachable. |
| `websocket` | app image | Socket.IO on :9000 | Live updates stop; pages still work. |
| `queue-short` | app image | `bench worker --queue short,default` | Short background jobs (emails, notifications) never run. |
| `queue-long` | app image | `bench worker --queue long,default,short` | Long jobs never run. |
| `scheduler` | app image | `bench schedule` | **Silent.** Night audit, hold expiry, retention, reminders, hourly channel push stop. |
| `db` | `mariadb:11.8` | The database | Everything fails. |
| `redis-cache` | `redis:8.6-alpine` | Cache, sessions | Logins and cached pages fail. |
| `redis-queue` | `redis:8.6-alpine` | Job queue, volume `redis-queue-data` | Background work stops. |

Three volumes hold the hotel: `sites` (site config, the **encryption key**,
every uploaded file including guest ID scans), `db-data` (the database),
`redis-queue-data` (queued jobs).

The database is **MariaDB 11.8**. It is not PostgreSQL. There is no `psql`, no
`pg_dump`, no `pg_isready` anywhere in this product.

What the scheduler runs (from `kamra/hooks.py`; times are site time):

| Cron | Job | Why you care |
| --- | --- | --- |
| `0 3 * * *` | `kamra.folio.nightly_audit_all_properties` | **The night audit.** Posts room charges, flags no-shows, advances the business date by one day. |
| `*/15 * * * *` | `housekeeping.escalate_overdue_tasks`, `reservation_state.expire_holds` | Releases expired holds. |
| `0 * * * *` | `channel_manager.push_all_ari` | Pushes availability and rates to OTAs. |
| `0 9 * * *` | `prearrival.run_prearrival_outreach` | Self check-in links. |
| `30 3 * * *` | `privacy.apply_retention` | Erases guests idle past retention. |
| `30 8 * * *` | `banquet.run_banquet_reminders` | Banquet follow-ups. |

---

## 4. Install

**Status: exists. Proven only on Docker Desktop over WSL2.** The authoritative
text is [`INSTALLATION.md`](../algeria/INSTALLATION.md) and
[`deploy/linux/README.md`](../../deploy/linux/README.md). What follows is the
technician's shortened path and the traps that bit people.

### 4.1 Linux server (recommended for a hotel taking live bookings)

Requirements: x86-64, Docker Engine with Compose v2 and `buildx`, 2 vCPU / 4 GB
RAM / 40 GB disk minimum, 8 GB RAM for a comfortable build. The services declare
`platform: linux/amd64`; on ARM everything runs emulated.

**[repo]**

```bash
export KAMRA_GIT_URL=https://github.com/ilyeseia/kamra-pms-algeria
export KAMRA_BRANCH=feature/algeria-hospitality-platform
curl -fsSL https://raw.githubusercontent.com/ilyeseia/kamra-pms-algeria/feature/algeria-hospitality-platform/deploy/install.sh -o install.sh
```

Read `install.sh`, then:

```bash
sudo bash install.sh
```

Do not skip the two `export` lines: without them the build produces upstream
Kamra with no Algerian localisation, after 20–45 minutes. The installer asks
for the site domain, an admin email and an admin password (10 characters
minimum, no default). The repository named in `KAMRA_GIT_URL` must be publicly
readable; it is cloned from inside the build with no credentials.

`install.sh` is safe to re-run: it reuses the existing `DB_PASSWORD` and skips
`new-site` if the site exists.

### 4.2 Windows 10 (WSL2 + Docker Desktop)

Run `deploy/windows/Install-Kamra.ps1 -Preflight` first; it changes nothing.
Production install: `-Mode Production -SiteName <fqdn> -AdminEmail <email>`.
This path runs `install.sh` inside WSL2, so it is Layout A. See
[`deploy/windows/README.md`](../../deploy/windows/README.md). It is a pilot or
demo profile, not a production recommendation (`INSTALLATION.md` §2).

### 4.3 Compose by hand (Layout B)

Build the image once (commands in `deploy/linux/README.md`, "Building the image
by hand"), then:

```bash
cp .env.example .env     # set DB_PASSWORD and FRAPPE_SITE_NAME_HEADER
docker compose up -d
docker compose ps        # configurator must read "Exited (0)"
```

If you clone `frappe_docker` on Windows to build, use
`git -c core.autocrlf=false clone ...`. CRLF line endings baked into the image
make **every container** die with `exec ...entrypoint.sh: no such file or
directory`, while `configurator` still succeeds (it overrides the entrypoint),
which makes the image look fine.

### 4.4 TLS

The stack serves **plain HTTP**. Production requires a proxy in front
(nginx/Caddy, or `certbot --nginx -d <site>` as `install.sh` suggests). The
proxy is outside this repository; its certificate is checked in
[Section 6.7](#67-tls).

### 4.5 Verify the install — do not hand over on "the login page loaded"

Work through `INSTALLATION.md` §7 (stack up, `list-apps` shows `frappe`,
`payments`, `kamra`, migrations clean, Algeria registered, demo accounts
absent, scheduler). Then add the checks that document predates:

```bash
dc ps                                   # configurator Exited (0); everything else Up; db (healthy)
```

Open `https://<site>/kamra/health` as an administrator. **Every row must be
`passed`, or you must be able to explain each `attention`.** A fresh site
legitimately shows `attention` on Backup (none yet) and on Scheduler for the
first minutes.

Then prove the scheduler runs — this is the check that was missing, and the
reason is in [R03](PRODUCTION_RUNBOOK.md#r03-scheduler-not-running). Wait at
least 15 minutes after first boot, then:

```bash
dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
SELECT COUNT(*) AS job_types,
       SUM(last_execution IS NOT NULL) AS have_run,
       MAX(last_execution) AS last_run
FROM `tabScheduled Job Type`;
SQL
```

`have_run` must be greater than zero and `last_run` recent. **[standard]**

For a production site, set the time zone (System Settings and the Property)
**before** the first night, not after. Changing it afterwards is exactly what
caused R03.

Finally, take a backup and **restore it onto a throwaway site**
([Section 11](#11-restore)). Until you have, the customer has no backup.

---

## 5. Diagnose: the first five minutes

Do these in order. Stop at the first one that is wrong.

**1. Is every container up?** **[standard]**

```bash
dc ps
```

`configurator` should be `Exited (0)`. Every other service `Up`, and `db`
`(healthy)`. Anything `Restarting` or `Exited` is the problem; read its log
(Section 7).

**2. Does the application answer, and does it answer all the way through?**
**[standard]**

```bash
HTTP_PORT=8080   # your HTTP_PUBLISH_PORT
curl -sS -o /dev/null -w 'page  %{http_code}\n' "http://localhost:${HTTP_PORT}/api/method/ping"
curl -sS -o /dev/null -w 'asset %{http_code}\n' "http://localhost:${HTTP_PORT}/assets/kamra/ziri-mark.png"
```

| `page` | `asset` | Meaning |
| --- | --- | --- |
| 200 | 200 | Application path is up. |
| **502** | **200** | nginx is alive but cannot reach `backend`. Go to [R02](PRODUCTION_RUNBOOK.md#r02-pages-and-api-return-502-after-a-restart). |
| 404 | 404 | `FRAPPE_SITE_NAME_HEADER` does not match `$SITE`. |
| timeout | timeout | `frontend` is down, or the host port is blocked. [R01](PRODUCTION_RUNBOOK.md#r01-application-down). |

**3. Read the application's own health report.** In the browser,
`/kamra/health`. From the command line, without a browser: **[standard]**

```bash
dc exec -T backend bench --site "$SITE" execute kamra.health.system_health
```

This prints the same JSON the screen renders (`overall`, `summary`, `checks`).
It needs an image built from a tree that contains the extended `health.py`
(Redis, workers, backup). On an older image, the Redis / workers / backup rows
simply will not exist; that is not a fault in the site.

Map failing check ids to runbook sections:

| `checks[].id` | Section |
| --- | --- |
| `database` | [R12](PRODUCTION_RUNBOOK.md#r12-database-down) |
| `redis` | [R13](PRODUCTION_RUNBOOK.md#r13-redis-down) |
| `workers` | [R10](PRODUCTION_RUNBOOK.md#r10-background-worker-down-or-queue-backing-up) |
| `scheduler` | [R03](PRODUCTION_RUNBOOK.md#r03-scheduler-not-running) |
| `backup` | [R08](PRODUCTION_RUNBOOK.md#r08-backup-failed-or-missing) |
| `disk` | [R09](PRODUCTION_RUNBOOK.md#r09-disk-full) |
| `timezone` | [R03](PRODUCTION_RUNBOOK.md#r03-scheduler-not-running) (read the cause) |
| `version`, `frappe`, `apps` | [R16](PRODUCTION_RUNBOOK.md#r16-update-failed) |

**The health page cannot report its own outage.** If the application is down,
this screen is down with it. And it cannot see container state, TLS, or the
host. A green page means "the checks it performs passed", nothing more.

**4. Recent errors the application logged about itself.** **[standard]**

```bash
dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
SELECT creation, method AS title
FROM `tabError Log`
ORDER BY creation DESC
LIMIT 20;
SQL
```

`method` holds the title passed to `frappe.log_error`. This query deliberately
returns **titles only**, not the `error` column, which holds tracebacks and can
contain personal data. Titles that exist in the code, and what they mean, are
in [`ERROR_CODES.md`](../product/ERROR_CODES.md).

**5. The last 100 lines of whatever is failing.**

```bash
dc logs --tail=100 --timestamps <service>
```

---

## 6. Component checks

### 6.1 Docker

**[standard]**

```bash
docker version
docker compose version                       # must be v2 ("docker compose", not "docker-compose")
systemctl is-active docker                   # active
systemctl is-enabled docker                  # enabled - otherwise a reboot leaves the hotel down
docker info --format '{{.DockerRootDir}} {{.Driver}}'
dc ps -a
docker stats --no-stream                     # CPU and memory per container
```

The app services use `restart: ${RESTART_POLICY:-unless-stopped}`, so they come
back after a reboot only if the Docker daemon itself starts at boot.

Image present, and which build is running:

```bash
docker image ls kamra
dc images
```

### 6.2 MariaDB

**[repo]** for the healthcheck, **[standard]** for the rest.

```bash
dc ps db                                                                    # (healthy)
dc exec db healthcheck.sh --connect --innodb_initialized; echo "exit=$?"    # 0 = healthy
dc logs --tail=100 --timestamps db
```

Inspect through the `db` container's own root password variable so the password
never appears on your command line or in shell history:

```bash
dc exec -T db sh -c 'mariadb -uroot -p"$MYSQL_ROOT_PASSWORD"' <<'SQL'
SELECT VERSION();
SHOW GLOBAL STATUS WHERE Variable_name IN ('Uptime','Threads_connected','Max_used_connections','Aborted_connects');
SHOW VARIABLES LIKE 'max_connections';
SELECT table_schema, ROUND(SUM(data_length+index_length)/1024/1024) AS mb
FROM information_schema.tables GROUP BY table_schema;
SQL
```

Do **not** run `SHOW PROCESSLIST` or `SHOW ENGINE INNODB STATUS` for a support
case: both can print live query text containing guest data.

To connect as the site rather than root, using the credentials Frappe already
holds (no password typed): `dc exec -T backend bench --site "$SITE" mariadb`.

There is no `psql`. If someone hands you a PostgreSQL command, it is wrong for
this product.

### 6.3 Redis

Two instances. **[standard]**

```bash
dc exec redis-cache redis-cli ping                   # PONG
dc exec redis-queue redis-cli ping                   # PONG
dc exec redis-cache redis-cli info memory | grep -E 'used_memory_human|maxmemory_human'
dc exec redis-queue redis-cli info persistence | grep -E 'rdb_last_save_time|aof_enabled'
dc exec redis-queue redis-cli --scan --pattern 'rq:*' | head -20     # queue and worker keys
```

`health.py` does a write-and-read-back through Frappe's cache, which proves the
application can use Redis, not merely that Redis answers `PING`.

### 6.4 Background workers

**[standard]**

```bash
dc ps queue-short queue-long
dc exec -T backend bench --site "$SITE" doctor
```

`doctor` prints the number of workers online and pending jobs. **A worker
count above zero proves nothing about the scheduler** — see 6.5.

### 6.5 Scheduler

Three different questions, and only the last matters:

| Question | How | What it proves |
| --- | --- | --- |
| Is the container up? | `dc ps scheduler` | The process exists. |
| Is the setting on? | `dc exec -T backend bench --site "$SITE" scheduler status` | A flag in System Settings. |
| **Has it executed anything?** | the SQL below, and the `scheduler` row of `/kamra/health` | **The only thing that counts.** |

**[live]** for the comparison, **[standard]** for the exact invocation:

```bash
dc exec -T backend bench --site "$SITE" execute frappe.utils.now_datetime
dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
SELECT COUNT(*)                         AS job_types,
       SUM(last_execution IS NULL)      AS never_run,
       MIN(creation)                    AS oldest_creation,
       MAX(creation)                    AS newest_creation,
       MAX(last_execution)              AS last_run
FROM `tabScheduled Job Type`;
SQL
```

If `MIN(creation)` (or any `last_execution`) is **later than the site clock**
printed by the first command, nothing will ever come due. That is the silent
failure in [R03](PRODUCTION_RUNBOOK.md#r03-scheduler-not-running). `health.py`
reports it as `failed` with the count.

### 6.6 Disk

**[standard]**

```bash
df -h /                                   # the host
df -h "$(docker info --format '{{.DockerRootDir}}')"
docker system df                          # images, containers, volumes, build cache
docker system df -v | head -60            # per-volume size
```

`health.py` measures free space on the filesystem holding the **site path**
only: `attention` below 5 GB or 10% free, `failed` below 2 GB or 5%. It does not
see the Docker log files, which are the usual thing that fills a disk
([R09](PRODUCTION_RUNBOOK.md#r09-disk-full)).

On Docker Desktop (Windows) the WSL2 virtual disk grows and does not shrink on
its own; deleting data inside it does not give the space back to Windows.

### 6.7 TLS

TLS is not part of this stack, so the product cannot check it. Check from
**outside** the server, against the public name, because that is what the
guest's browser sees. **[standard]**

```bash
SITE_FQDN=pms.yourhotel.dz
echo | openssl s_client -connect "$SITE_FQDN:443" -servername "$SITE_FQDN" 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates
echo | openssl s_client -connect "$SITE_FQDN:443" -servername "$SITE_FQDN" 2>/dev/null \
  | openssl x509 -noout -checkend 1209600; echo "exit=$?"     # exit 1 = expires within 14 days
```

If the proxy is certbot-managed on the same host:

```bash
sudo certbot certificates
sudo certbot renew --dry-run
systemctl list-timers | grep -i certbot
```

If the proxy is Caddy, it renews itself; check `journalctl -u caddy`. A site
reached by IP, or on `localhost` (the Trial profile), has no certificate and
this section does not apply.

### 6.8 Time zone and clocks

**[standard]**

```bash
dc exec -T backend bench --site "$SITE" execute frappe.db.get_single_value --args "['System Settings','time_zone']"
date -u; dc exec -T backend date -u; dc exec -T db date -u
```

All three `date -u` lines should agree to the second. If they do, the clocks
are not the problem. A site whose **time zone was changed after the site was
built** is a different problem from clock drift and produces R03.

### 6.9 Application version

**[standard]**

```bash
dc exec -T backend bench --site "$SITE" version
dc exec -T backend bench --site "$SITE" list-apps       # frappe, payments, kamra
docker image inspect kamra:local --format '{{.Id}} {{.Created}}'
```

---

## 7. Collect logs

**What produces logs here**

| Source | How to read | Notes |
| --- | --- | --- |
| Every container's stdout/stderr | `dc logs [--tail N] [--since 2h] --timestamps <service>` | **[standard]** Docker's default `json-file` driver. The compose file sets no rotation. |
| Application faults | the `Error Log` doctype (Section 5, step 4) | Titles are safe to share; the `error` column is not. |
| Scheduled job results | table `` `tabScheduled Job Log` `` | Proof the scheduler is executing. |
| Frappe log files | `dc exec backend ls -lh logs sites/$SITE/logs` | **Not verified** to persist: only the `sites` volume is mounted, so anything under the bench `logs/` directory lives in the container's writable layer and is **lost when the container is recreated** (every `install.sh update` recreates them). Prefer `docker compose logs`. |

**Examples**

```bash
dc logs --no-color --timestamps --since 2h backend frontend > /tmp/app-2h.log
dc logs --no-color --timestamps --tail=300 scheduler queue-short queue-long > /tmp/jobs.log
dc logs --no-color --timestamps --tail=200 db > /tmp/db.log
```

**Personal-data warning.** The `frontend` logs are nginx access logs: client IP
addresses, URLs and query strings. Query strings and `/api/resource/<Doctype>/<name>`
paths can carry guest names and reservation identifiers. Worker logs can print
job arguments. **Treat every raw log as containing personal data under Law
18-07** until it has been redacted and read by a human. Do not attach a raw log
to an email.

---

## 8. Create a support bundle (does not exist yet)

**There is no support bundle in this product.** A repository-wide search returns
zero hits. There is no `kamra-doctor`, no `support-bundle` command, no button.
Section 9 specifies what one must do. Until it exists, a technician collects by
hand. The steps below use only commands that exist, collect an allow-list (not
"everything"), and filter with `sed`. **This is a stand-in, not a substitute:
the filter is best-effort and a human must read the result before it leaves the
machine.**

```bash
OUT=~/ziri-support-$(date +%Y%m%d-%H%M%S); mkdir -m 700 "$OUT"; cd "$OUT"

# 1. Version and host
{ date -Is; uname -a; cat /etc/os-release; nproc; free -m; df -h /; docker version --format '{{.Server.Version}}'; docker compose version; } > host.txt 2>&1
dc exec -T backend bench --site "$SITE" version > versions.txt 2>&1

# 2. Container state - FORMATTED, never raw 'docker inspect' and never 'docker compose config'
dc ps -a --format 'table {{.Service}}\t{{.State}}\t{{.Status}}\t{{.Image}}' > containers.txt
docker inspect --format '{{.Name}} restarts={{.RestartCount}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} started={{.State.StartedAt}}' $(dc ps -q) > restarts.txt

# 3. Application health
dc exec -T backend bench --site "$SITE" execute kamra.health.system_health > health.json 2>&1

# 4. Logs, then redact
dc logs --no-color --timestamps --tail=300 > logs.raw 2>&1
```

Redact. GNU `sed -E`; each expression is one rule from Section 9.4 in ERE form:

```bash
redact() {
  sed -E -z 's/-----BEGIN [A-Z ]*PRIVATE KEY-----[^-]*-----END [A-Z ]*PRIVATE KEY-----/<redacted:private-key>/g' |
  sed -E \
    -e 's#([A-Za-z][A-Za-z0-9+.-]*://)[^/[:space:]@]+@#\1<redacted>@#g' \
    -e 's/([A-Za-z0-9_.-]*(pass(word|wd)?|secret|token|api_?key|private_?key|encryption_?key)[A-Za-z0-9_.-]*"?[=:][[:space:]]*)("[^"]*"|'"'"'[^'"'"']*'"'"'|[^[:space:],;&}]+)/\1<redacted>/Ig' \
    -e 's/(--[a-z-]*(password|secret|token|key)[a-z-]*(=|[[:space:]]+))("[^"]*"|[^[:space:]]+)/\1<redacted>/Ig' \
    -e 's/((proxy-)?authorization:[[:space:]]*)[^"\r\n]+/\1<redacted>/Ig' \
    -e 's/((set-)?cookie:[[:space:]]*)[^"\r\n]+/\1<redacted>/Ig' \
    -e 's/([?&](sid|token|api_key|api_secret|key|password|pwd|otp|reset_key|access_token|refresh_token)=)[^& "]+/\1<redacted>/Ig' \
    -e 's/token [A-Za-z0-9]{10,}:[A-Za-z0-9]{10,}/token <redacted>/Ig' \
    -e 's/eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}/<redacted:jwt>/g' \
    -e 's/gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,}/<redacted:github-token>/g' \
    -e 's#(/api/resource/[^/?[:space:]"]+/)[^?[:space:]"]+#\1<id>#g' \
    -e 's/\?[^[:space:]"]*/?<qs>/g' \
    -e 's/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/<email>/g' \
    -e 's/(\+213|00213|\b0)[567]([ .-]?[0-9]){8}/<phone>/g'
}
redact < logs.raw > logs.txt && { shred -u logs.raw 2>/dev/null || rm -f logs.raw; }
```

Then, **before the bundle leaves the machine**:

```bash
# Fail closed: search for the actual secret. Do not print the match.
# (Layout A path shown; on Layout B read DB_PASSWORD from .env)
s="$(sed -n 's/^DB_PASSWORD=//p' /opt/kamra/kamra.env)"
[ -n "$s" ] && grep -rlF -- "$s" . && echo "SECRET STILL PRESENT - DO NOT SEND"
less logs.txt          # read it. This step is not optional.
tar czf ../"$(basename "$OUT")".tar.gz -C .. "$(basename "$OUT")"
```

What this stand-in does **not** do: it does not redact names (no pattern can);
it redacts the query string of every log line, including non-HTTP lines that
merely contain a `?`; it does not validate card numbers; it has no manifest. It
exists so the technician is not tempted to attach a raw log.

The deliberately omitted sources — database dumps, `docker inspect`,
`docker compose config`, `site_config.json`, `apps.json`, `.env`,
`PROCESSLIST`, the `Error Log` `error` column — are omitted for the reasons in
Section 9.3.

---

## 9. Specification: the support bundle that must be built

**Status: specification only. Nothing in this section is implemented.** It is
written so that whoever builds it cannot reasonably produce a bundle that leaks.
Design only — there is deliberately no code in this phase.

### 9.1 Goal and shape

One command, run on the host (not through the web UI — when the application is
down, the bundle is needed most). It writes **one local file**, never uploads
it, and tells the operator exactly what is inside before anything is sent.

Proposed invocation, **not implemented**: a host script (working name
`kamra-support-bundle`) with a counterpart `bench --site <site> execute` entry
for the in-container parts. The name is a proposal.

Output: a gzip tarball, mode `0600`, containing a `manifest.json` and the
sections in 9.2. The bundle must be producible when the application, the
database, or Redis is down; each section records its own failure
(`"status":"unavailable","reason":"..."`) and the rest continues.

### 9.2 What it MUST contain

| Section | Contents | Source (all read-only) |
| --- | --- | --- |
| **manifest** | bundle format version; generator version; creation time (UTC + offset); a random per-bundle ID; SHA-256 of every file; redaction ruleset version; per-rule redaction counts; list of sections that failed. When an Installation ID exists (it does not today), that too. | generated |
| **version** | `kamra` version; Frappe version; installed apps and versions; image ID, tag, created time; git revision if the image carries one; latest release known to GitHub and whether the check could reach it. | `bench version`; `docker image inspect --format`; `health.py` `version` check |
| **system info** | OS and kernel; CPU count; RAM and swap; host and container UTC offsets and `date -u` for host, `backend` and `db` (to tell clock drift from a time-zone offset); Docker and Compose versions; Docker root dir and storage driver; whether Docker is enabled at boot; Windows/WSL2 flag. | `uname`, `/etc/os-release`, `nproc`, `free`, `docker info --format`, `systemctl is-enabled` |
| **container status** | For each of the ten services: state, health status, restart count, started-at, exit code, image ID. **Via explicit `--format` fields only.** | `docker compose ps --format`; `docker inspect --format` |
| **service status** | Scheduler: enabled flag, job-type count, never-run count, last execution, count stamped in the future, site-now. Workers: count, per-queue depth. Redis: both instances' ping and memory. | `health.py` checks; SQL aggregates from R03; `redis-cli ping`, `info memory` |
| **health checks** | The full `system_health()` JSON. Its `detail` strings contain counts, versions and paths, not guest data (checked by reading `health.py`; re-verify whenever a check is added). | `kamra.health.system_health` |
| **recent logs** | Per service: last 500 lines and no more than 24 h, capped at 2 MB per service, **after redaction (9.4)**. Application `Error Log`: **titles, timestamps and counts only**; tracebacks only on explicit opt-in and only after redaction. | `docker compose logs`; `tabError Log` columns `creation`, `method` |
| **database health** | MariaDB version; uptime; `Threads_connected`, `Max_used_connections`, `Aborted_connects`, `max_connections`; size per schema (MB); table counts; whether `healthcheck.sh --connect --innodb_initialized` passes; free space on the `db-data` filesystem. Aggregates only. | `mariadb` over aggregate statements |
| **migration status** | Last 20 rows of `Patch Log` (patch name, time); last 5 lines of `apps/kamra/kamra/patches.txt`; the computed list of patches in the file but absent from `Patch Log` ("pending"). | `tabPatch Log`; file in the image |
| **configuration metadata** | **Allow-list.** Key *names* of the env file and `common_site_config.json` / `site_config.json` always; *values* only for: `CUSTOM_IMAGE`, `CUSTOM_TAG`, `PULL_POLICY`, `RESTART_POLICY`, `HTTP_PUBLISH_PORT`, `NGINX_LISTEN_PORT`, `GUNICORN_*`, `PROXY_READ_TIMEOUT`, `CLIENT_MAX_BODY_SIZE`, `socketio_port`, `chromium_path`, site time zone, `FRAPPE_SITE_NAME_HEADER`. Every other value is `<redacted>`. Whether `DB_PASSWORD` is set, and its length class (never the value). | env files, site config — parsed, not copied |
| **licence metadata** | **Reserved, empty today.** When a commercial licence exists: edition, licensee identifier, issue and expiry dates, last verification time and result, signature-valid boolean. Never key material. Until then the section reads `"status":"not_implemented"`; it must not be silently omitted. | none yet |
| **backup status** | Number of `*.sql.gz` in `private/backups`; newest age and size; file *timestamps*; whether a host-side schedule exists (presence of a crontab line or Task Scheduler task, not its contents); last recorded restore-test date **(does not exist yet — report `unknown`)**. | filesystem listing; host scheduler presence |
| **disk and volumes** | `df -h`; `docker system df`; per-volume size; size of each container's log file. | as named |

### 9.3 What it must NEVER contain

Absolute exclusions. A bundle containing any of these is a defect, not a
configuration choice.

| Never | Includes, concretely | Why it is a real risk here |
| --- | --- | --- |
| **Passwords** | `DB_PASSWORD`; `MYSQL_ROOT_PASSWORD`; `db_password` in `site_config.json`; the Administrator and any user password; SMTP passwords; Frappe `__Auth` table rows; cashier PINs (`Cashier PIN` doctype). | `docker inspect` on the `db` container prints `MYSQL_ROOT_PASSWORD` in clear. `docker compose config` expands `${DB_PASSWORD}` from `.env`. Both are the obvious things to run and both leak. |
| **API keys** | Frappe user `api_key` / `api_secret`; payment-gateway keys; WhatsApp Business tokens and app secrets; channel-manager credentials; MCP OAuth client secrets and tokens; LLM provider keys. | Stored encrypted in the database with `encryption_key`; leaked via config dumps and via logs that echo requests. |
| **Tokens** | Session IDs (`sid`); bearer and JWT tokens; OAuth access/refresh tokens; password-reset `key=` values; GitHub personal-access tokens. | `INSTALLATION.md` documents embedding a token in `KAMRA_GIT_URL` (`https://<token>@github.com/...`); that lands in `apps.json` and in build output. |
| **Private keys** | Any PEM private key; TLS private keys from the proxy; SSH keys; the deploy key used by `vps-doctor.yml`. | |
| **Database credentials** | Connection strings with userinfo (`mysql://user:pw@db`, `redis://:pw@host`); `site_config.json` as a file. | |
| **Licence private keys** | Any signing key, activation secret or licence-server credential. | Not an issue today; stated now so the future licence system cannot add one. |
| **The encryption key** | `encryption_key` in `site_config.json`. | Whoever holds it plus a database dump can decrypt every stored integration credential. |
| **Guest personal data** | Names, phone numbers, emails, addresses, nationality, dates of birth, ID numbers, payment-card data, reservation or folio contents, guest free-text notes, message bodies (WhatsApp, email), request bodies and query strings. | Law 18-07 personal data. A bundle that carries it turns a support call into a third-party or cross-border disclosure the hotel never agreed to. |
| **Identity documents** | Anything under `sites/<site>/private/files`; the `*-private-files.tar` backup archive; any image of an ID. | The `sites` volume holds guest ID scans (`kamra/id_documents.py`). |
| **Database dumps and backup archives** | `*.sql.gz`, `*-files.tar`, `*-private-files.tar`, `site_config_backup.json`. | They contain everything above. "Attach last night's backup" is never a valid support step. |
| **Raw runtime dumps** | Raw `docker inspect`; raw `docker compose config`; `SHOW PROCESSLIST`; `SHOW ENGINE INNODB STATUS`; process environments; `env`; core dumps. | Live query text and environments. |

### 9.4 How logs are sanitised

Three layers. The first is the one that actually protects people.

**Layer 1 — do not collect what you cannot sanitise (allow-list collection).**
Regular expressions cannot recognise a guest's name or an ID number. The only
reliable defence is never to read the sources that contain them. This is why
9.2 lists aggregates, titles and counts, and 9.3 bans dumps and raw SQL result
sets. Config metadata is **allow-listed by key**; unknown keys are redacted by
default. Every new collector added later must state which sources it reads and
justify each against 9.3.

**Layer 2 — redact the text stream before it touches disk.** Every collected
text is piped through the redactor in memory; the unredacted form is never
written to the bundle directory or to a temp file. Rules are ordered and
versioned (`ruleset_version` in the manifest). Replacement tokens name the rule
that fired (`<redacted:jwt>`) so a reader can tell a redaction from data.

Patterns below are PCRE (case-insensitive unless noted), for the implementation
language to adopt; the stand-in in Section 8 uses ERE equivalents. In the table,
`\|` stands for a literal alternation bar escaped for Markdown.

Secrets:

| ID | Target | Pattern | Replacement |
| --- | --- | --- | --- |
| R-PEM | PEM private keys (multi-line) | `-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----` | `<redacted:private-key>` |
| R-URL | credentials inside any URL | `\b([a-z][a-z0-9+.-]*://)[^/\s@]+@` | `\1<redacted>@` |
| R-KV | key/value and JSON pairs whose key names a secret | `([\w.-]*(?:pass(?:word\|wd)?\|secret\|token\|api[_-]?key\|private[_-]?key\|encryption[_-]?key\|credential)[\w.-]*"?\s*[=:]\s*)("[^"]*"\|'[^']*'\|[^\s,;&}]+)` | `\1<redacted>` |
| R-FLAG | secret-bearing CLI flags | `(--[\w-]*(?:password\|secret\|token\|key)[\w-]*(?:=\|\s+))("[^"]*"\|\S+)` | `\1<redacted>` |
| R-AUTH | auth headers | `((?:proxy-)?authorization:\s*)[^"\r\n]+` | `\1<redacted>` |
| R-COOKIE | cookie headers | `((?:set-)?cookie:\s*)[^"\r\n]+` | `\1<redacted>` |
| R-QS-SECRET | secret query parameters | `([?&](?:sid\|token\|api_key\|api_secret\|key\|password\|pwd\|otp\|reset_key\|access_token\|refresh_token)=)[^&\s"]+` | `\1<redacted>` |
| R-FRAPPE-TOKEN | Frappe `Authorization: token key:secret` | `\btoken\s+[A-Za-z0-9]{10,}:[A-Za-z0-9]{10,}` | `token <redacted>` |
| R-JWT | JSON Web Tokens | `\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}\b` (case-sensitive) | `<redacted:jwt>` |
| R-GITHUB | GitHub tokens | `\b(?:gh[pousr]_[A-Za-z0-9]{36,}\|github_pat_\w{50,})\b` (case-sensitive) | `<redacted:github-token>` |
| R-AWS | AWS access key IDs | `\b(?:AKIA\|ASIA)[A-Z0-9]{16}\b` (case-sensitive) | `<redacted:aws-key>` |
| R-SLACK | Slack tokens | `\bxox[abprs]-[A-Za-z0-9-]{10,}` | `<redacted:slack-token>` |

Personal data, applied to **every** text because logs echo guest input:

| ID | Target | Pattern | Replacement |
| --- | --- | --- | --- |
| R-EMAIL | email addresses | `[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}` | `<email>` |
| R-PHONE-DZ | Algerian numbers | `(?<!\d)(?:\+213\|00213\|0)[5-7](?:[ .-]?\d){8}(?!\d)` | `<phone>` |
| R-PHONE-INTL | E.164 | `(?<!\w)\+\d{8,15}(?!\d)` | `<phone>` |
| R-NIN | 18-digit national identification number | `(?<!\d)\d{18}(?!\d)` | `<id-number>` |
| R-PAN | card numbers | candidate `\b(?:\d[ -]?){13,19}\b`, **kept only if it passes the Luhn check** (otherwise timestamps match) | `<pan>` |

Applied to **HTTP access-log lines only** (the `frontend` service), where the
personal data is in the request line:

| ID | Pattern | Replacement |
| --- | --- | --- |
| R-RESOURCE | `(/api/(?:resource\|v2/document)/[^/?\s"]+/)[^?\s"]+` | `\1<id>` |
| R-QS-ALL | `\?[^\s"]*` | `?<qs>` |
| R-IP | `\b(\d{1,3}\.\d{1,3}\.\d{1,3})\.\d{1,3}\b` | `\1.0` |

R-IP is limited to access logs because applied everywhere it would mangle
four-part version strings and container addresses a technician needs. Whether
the `frontend` container's logs are in this format at all is **assumed, not
verified**.

**Layer 3 — verify the finished bundle, and fail closed.**

1. **Canary scan.** The generator already reads the live secrets to build the
   allow-list: `DB_PASSWORD`, `encryption_key`, `db_password`, every
   `api_secret`, SMTP password. Before sealing the tarball it searches the
   *entire bundle* for each of those exact values as fixed strings. **Any hit
   aborts the build, deletes the partial bundle and exits non-zero.** The error
   names the file and rule, never the matched text.
2. **Pattern re-scan.** The same ruleset is run again over the redacted output.
   Any match that survives is a bug in the redactor and also aborts.
3. **Entropy warning (report only).** Long high-entropy strings that survived
   are listed by file and line number in the manifest as `review`, not
   auto-redacted, because container IDs and commit hashes are legitimately
   high-entropy.
4. **Consent step.** The tool prints the manifest (sections, sizes, redaction
   counts per rule) and requires the operator to confirm. The bundle is **never
   transmitted by the tool**; sending it is the operator's decision.
5. **Optional:** gitleaks is already pinned in `.pre-commit-config.yaml`
   (`v8.30.1`) for commit-time scanning; its ruleset could back step 2. It is
   not present on a customer host today.

**Redaction cannot be proven complete.** Layer 3 reduces risk; it does not
eliminate it. That is why Layer 1 exists and why the operator reads the manifest.

### 9.5 Handling

Mode `0600`, directory `0700`; a default retention of 14 days after which the
tool offers to delete it; optional encryption to the support team's public key.
The bundle must be producible without network access. Law 18-07
responsibilities (controller, processor, any transfer abroad) are for the
hotel's legal adviser to settle; this specification only makes sure the bundle
does not create the question.

---

## 10. Back up

**Status: manual command exists; scheduling and verification do not.** Full
treatment: [`BACKUP.md`](../algeria/BACKUP.md). Short form:

**[repo]** (the command is in `BACKUP.md` §2 and `docs/self-hosting.md`)

```bash
dc exec -T backend bench --site "$SITE" backup --with-files
dc exec -T backend ls -lh "sites/$SITE/private/backups/"
```

`--with-files` is not optional: without it the guest ID scans, signed
registration cards and invoice attachments are not in the backup.

Get it off the machine, and off the building. A backup that exists only inside
the container dies with `down -v`, a bad disk, or a fire. **[standard]**

```bash
mkdir -p /opt/kamra/backups
dc cp "backend:/home/frappe/frappe-bench/sites/$SITE/private/backups/." /opt/kamra/backups/
```

(`BACKUP.md` flags the bench path inside the container as taken from upstream
and says to confirm it: `dc exec -T backend pwd`.)

Check the archives are at least valid gzip and tar:

```bash
cd /opt/kamra/backups
for f in *.sql.gz; do gzip -t "$f" && echo "ok  $f" || echo "BAD $f"; done
for f in *files*.tar; do [ -e "$f" ] && { tar -tf "$f" >/dev/null && echo "ok  $f" || echo "BAD $f"; }; done
```

This proves the file is not truncated. **It does not prove it restores.** Only
Section 11 does.

**Also back up, separately, as secrets:** the env file (`/opt/kamra/kamra.env`
or `.env`) and `sites/<site>/site_config.json`. Without the `encryption_key` in
`site_config.json`, a restored site signs in and then every stored integration
credential is undecryptable.

```bash
umask 077
dc exec -T backend cat "sites/$SITE/site_config.json" > /opt/kamra/site_config.json.bak
```

**Retention and guest IDs.** Backups made with `--with-files` still contain ID
scans the live site has since deleted under its retention policy
(`kamra/id_documents.py`). Backup retention is a privacy decision, not only an
IT one.

**Scheduling.** Not part of the product. Linux: root crontab line from
`BACKUP.md` §7. Windows: Task Scheduler, with the structural weakness
documented in `BACKUP.md` §6 (Docker Desktop is a user-session app). Then check
the job ran: the `backup` row of `/kamra/health` shows the newest backup's age.
It reports "Age only"; it turns to `attention` only after 48 hours.

---

## 11. Restore

**Status: manual. Never rely on a restore you have not rehearsed.** The
rehearsal procedure and the verification list are in `BACKUP.md` §4–5. Do not
restore onto a live site as a first attempt.

Always rehearse on a throwaway site first (`bench new-site restore-test.localhost`
with the exact flags in `BACKUP.md` §5, restore into it, `migrate`, verify, then
`bench drop-site`).

For the real thing:

1. **Back up the current state first**, even if it is broken (Section 10).
2. Stop writes: `dc exec -T backend bench --site "$SITE" set-maintenance-mode on` **[standard]**.
3. Read the real flags for your Frappe version, and write them down:

   ```bash
   dc exec -T backend bench --site "$SITE" restore --help
   ```

4. Restore. Skeleton only; the archive options come from step 3.
   **[repo]** for the shape and `--db-root-password` (same pattern as `install.sh`):

   ```bash
   dc exec -T backend bench --site "$SITE" restore \
     "sites/$SITE/private/backups/<timestamp>-...-database.sql.gz" \
     --db-root-password "$(sed -n 's/^DB_PASSWORD=//p' /opt/kamra/kamra.env)"
   ```

   The command line contains the password for the duration of the command and
   is visible in the process list to other local users. Do this on a host where
   you are the only operator. Add the public/private file-archive options from
   `--help`; **a restore without the files tarballs brings back a hotel whose ID
   scans have vanished.**

5. `migrate` and `clear-cache` (needed whenever the backup is older than the
   running image), then leave maintenance mode:

   ```bash
   dc exec -T backend bench --site "$SITE" migrate
   dc exec -T backend bench --site "$SITE" clear-cache
   dc exec -T backend bench --site "$SITE" set-maintenance-mode off
   dc restart backend frontend     # frontend too: see R02
   ```

6. Verify with the list in `BACKUP.md` §4: sign in; today's arrivals; a folio's
   totals; **an ID image actually loads**; one invoice prints with its legal
   footer; `bench doctor`. Then `/kamra/health`.
7. **Re-check the scheduler** ([R03](PRODUCTION_RUNBOOK.md#r03-scheduler-not-running)).
   A restore copies `Scheduled Job Type` rows, including their `last_execution`
   and `creation` stamps, from another time. Treat "scheduler still runs" as
   unproven until `MAX(last_execution)` advances.
8. Remember: a restore brings back guest ID scans that retention had deleted.

On a different host, the `encryption_key` in `site_config.json` must match the
original or stored credentials are lost (Section 15).

---

## 12. Update

**Status: exists, with no guard rails.** `install.sh update` does exactly this
(`deploy/install.sh`, the `update` block): check `kamra.env` and `apps.json`
exist, re-fetch the pinned `frappe_docker`, rebuild the image **over the same
tag** (`kamra:local`), `compose up -d --force-recreate`, wait for
`bench --version`, then `bench --site all migrate` and
`bench --site all clear-cache`. It does not take a backup, does not check health
afterwards, and does not keep the old image.

Before you run it:

1. `/kamra/health` has no `failed` row. Never update a sick site.
2. Disk: the build needs room (`df -h`, `docker system df`). The first build
   took 20–45 minutes and wants ~8 GB RAM.
3. A fresh backup, copied off ([Section 10](#10-back-up)).
4. **Tag the current image so rollback is possible** — the update retags
   `kamra:local` and orphans the old image:

   ```bash
   docker tag kamra:local "kamra:pre-$(date +%Y%m%d-%H%M)"
   docker image ls kamra
   ```

5. Write down: `bench version`, the newest `Patch Log` row (Section 14), and the
   time.
6. Agree a window with the hotel. The site is down during recreate and migrate.

Run it (Layout A):

```bash
sudo /opt/kamra/install.sh update
# to switch branch or tag:
sudo KAMRA_GIT_URL=<repo> KAMRA_BRANCH=<tag-or-branch> /opt/kamra/install.sh update
```

Layout B (no `install.sh`): rebuild the image by hand
(`deploy/linux/README.md`), then:

```bash
dc up -d && dc exec -T backend bench --site all migrate && dc exec -T backend bench --site all clear-cache
```

`--force-recreate` (and, in Layout B, a changed image) recreates `frontend`
along with `backend`, so the stale-address failure of R02 does not arise from an
update.

After it:

- `dc ps` — all up, `db` healthy
- the two `curl` probes in Section 5, step 2
- `/kamra/health` — compare with the pre-update state
- `bench version` — the version is what you intended
- Scheduler: **wait for `MAX(last_execution)` to advance** (R03). Do not
  declare the update done on container status alone.
- Note every release is a patch bump (`always-bump-patch`), so `2.6.4 → 2.6.5`
  does not tell you whether it is a fix or a feature.

If it fails: [R16](PRODUCTION_RUNBOOK.md#r16-update-failed).

---

## 13. Roll back

**There is no rollback tool, and no migration in this product has a "down".**
Frappe patches run forward only. What follows is a manual procedure from Docker
and Frappe primitives. **It has never been exercised.** Rehearse it on a trial
site before you need it.

Rolling back means two things at once, and doing one without the other fails:

- **The code**: run the previous image.
- **The data**: restore the database from the backup taken immediately before
  the update, because the new migrations changed the schema.

Anything entered at the hotel after the update started is **lost** by the data
rollback. Tell the hotel that before you do it, and have them decide.

Steps (Layout A; Layout B is the same with `dc`):

1. Decide. If the update only failed to start, the data may be untouched
   (check `Patch Log`, Section 14) and a code-only rollback may be enough.
2. Put the old image back under the name the stack uses. This needs the tag you
   made in Section 12 step 4:

   ```bash
   docker image ls kamra
   docker tag kamra:pre-YYYYMMDD-HHMM kamra:local
   dc up -d --force-recreate
   ```

   If you did **not** tag first, the old image is now an untagged `<none>`
   image; find it with `docker image ls -a` and `docker image inspect` (check
   `Created`) before any `docker image prune`. If it is gone, the only route is
   a rebuild from the previous release:
   `sudo KAMRA_BRANCH=<previous-tag> /opt/kamra/install.sh update` — 20–45
   minutes, and it will run `migrate` again on whatever database is there.
3. Restore the pre-update backup ([Section 11](#11-restore)). Run `migrate`
   afterwards: it should be a no-op because the old code matches the old
   schema.
4. Verify as in Section 12, including the scheduler.

Forward-only schema changes mean **never** run the old image against a
database the new migrations already altered, without the restore.

---

## 14. Migrate

**Status: exists** (`bench migrate`). Patches are listed in
`kamra/patches.txt`; `v36` (`backfill_room_levy_mode`) and `v37`
(`normalize_legal_id_columns`) are the newest, and have been applied on the live
install.

```bash
dc exec -T backend bench --site "$SITE" migrate          # one site
dc exec -T backend bench --site all migrate              # every site (what update does)
dc exec -T backend bench --site "$SITE" clear-cache
```

Back up first, every time (`BACKUP.md` §9).

**Migration status — what is applied versus what the code expects.** There is
no command in the product for this; compare two lists. **[standard]**

```bash
dc exec -T backend tail -n 8 apps/kamra/kamra/patches.txt
dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
SELECT patch, creation FROM `tabPatch Log` ORDER BY creation DESC LIMIT 8;
SQL
```

The last patch named in `patches.txt` must appear in `Patch Log`. A patch in the
file and not in the log is pending: `migrate` has not been run since the code
changed, or it failed partway. If it failed, the error is in the `migrate`
output; capture it next time with `... migrate 2>&1 | tee migrate.log`. Then
[R17](PRODUCTION_RUNBOOK.md#r17-migration-failed).

---

## 15. Recover a lost server

**Status: manual, never exercised end to end.** The scenario: the machine or its
disk is gone, and you have only what was copied off.

You need, all from off-box copies:

| Item | Without it |
| --- | --- |
| Latest backup set (`*.sql.gz`, files tarballs) | No hotel. |
| `kamra.env` / `.env` (`DB_PASSWORD`) | Recoverable: the dump can be restored into a new database with a new password. Keep it anyway. |
| `site_config.json` (`encryption_key`) | Database restores, but stored SMTP / gateway / OTA credentials are undecryptable and must be re-entered. |
| `apps.json` (repo + branch) | You must know which repository and branch built the image. For the Algeria distribution that is `ilyeseia/kamra-pms-algeria` on `feature/algeria-hospitality-platform`, not upstream. |

Procedure:

1. New host, same requirements as Section 4. Install Docker.
2. Install exactly as in Section 4.1 with the **same `SITE_NAME`**.
3. Restore into the freshly created site ([Section 11](#11-restore)). Put the
   original `encryption_key` into the new `site_config.json` **before** the
   restore verification, without echoing it to a terminal that is logged or
   shared.
4. `migrate`, `clear-cache`, restart `backend` and `frontend`.
5. Re-point DNS and TLS to the new host.
6. Verify (Section 11 step 6) and **re-check the scheduler** (R03). The night
   audit catch-up decision in R03 then applies for the days the hotel was down.

How long this takes has not been measured. Do not quote a recovery time to a
customer.

---

## 16. Verify the licence (does not exist)

**There is no licence verification in this product. Do not invent one.**

The audit found zero code for a commercial licence: no entitlement, no
activation, no expiry, no grace period, no enforcement, no licence server, no
Installation ID. `docs/algeria/LICENSING.md` is about the **AGPL-3.0 §13**
obligations of the software's own licence (offering source to network users). It
is not a commercial entitlement, and a customer is not "unlicensed" because
nothing can verify it.

What a technician can state truthfully today:

- which version is installed (`bench version`, `/kamra/health`);
- which repository and branch built the image (`apps.json`, or the install
  record);
- that the code is distributed under AGPL-3.0 (`license.txt` in the repository).

If a customer asks "is my licence valid?", the correct answer is that no
licence check exists yet, and that the question goes to whoever owns the
commercial terms. The support bundle reserves a "licence metadata" section for
when that changes (Section 9.2).

---

## 17. What this does not cover / has not been tested

- **No command in this manual was executed by its author.** The three live
  incident diagnostics (stale nginx upstream, `db` unhealthy during boot,
  scheduler future-stamp) were run on the live install by someone else and are
  labelled **[live]**; the exact invocations here, particularly
  `bench ... mariadb <<'SQL'` and `bench ... execute`, are **[standard]**:
  built from documented Frappe and MariaDB CLI behaviour and the files in this
  repository. Run them on a trial site first.
- **Not run on a Linux server.** The stack has only ever run on Docker Desktop
  over WSL2. `systemctl`, `certbot`, root crontab and log-driver behaviour on a
  real Linux host are described, not observed.
- **Layout A and `start_period`.** Whether the installer path actually fails the
  way R04 describes on a slow machine is inferred from the compose file's
  comment about upstream's 5 s value; the pinned upstream file was not re-read.
- **Redis key names.** `rq:*` as the queue key pattern is Frappe/RQ convention,
  not read from the image.
- **nginx log format.** That the `frontend` container writes access logs to
  stdout in the form the redaction rules assume is not verified.
- **Container log locations.** Whether Frappe's own log files persist in any
  volume is not verified and is assumed not to.
- **Rollback, recovery and restore** have not been rehearsed. Recovery time and
  recovery point are unmeasured. No restore of a real backup onto this stack is
  recorded.
- **The support bundle, licence verification, Installation ID, scheduled
  backup, backup verification, monitoring and alerting do not exist.** Sections
  8, 9, 10 and 16 say so; nothing here substitutes for them.
- **The `sed` redaction stand-in** in Section 8 was not run against real log
  output. It will miss things.
- **Windows.** The Windows installer path was read, not run, by this author.
- **Legal.** References to Law 18-07 flag a risk. They are not legal advice and
  do not state what the law requires.
- **Capacity, load, performance tuning** are not covered; nothing has been
  measured ([R11](PRODUCTION_RUNBOOK.md#r11-slow-system) is triage only).
- **Languages.** English only. The customer-facing guides exist in Arabic,
  French and English under `docs/algeria/guides/`; this manual does not.
