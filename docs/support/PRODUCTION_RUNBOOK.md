# ZIRI PMS — Production Runbook

What to do when a live ZIRI PMS install is misbehaving. Each procedure has the
same shape: **symptom**, **confirm it is really this**, **immediate action**,
**fix**, **verify the fix worked**.

Read [`TECHNICIAN_MANUAL.md`](TECHNICIAN_MANUAL.md) §1 first. It defines the
`dc` shell function, `$SITE`, and the **[live] / [repo] / [standard]** labels
used here, and it explains the two stack layouts. Error identifiers used below
are specified in [`../product/ERROR_CODES.md`](../product/ERROR_CODES.md) and are
**not emitted by any code yet**; they are cross-references for the future, not
something you will see on screen.

---

## How this runbook is ordered

Not alphabetically, and not by severity. By how likely you are to meet it, on
the evidence available:

1. **Seen on the live install** (R02, R03, R04). Three real failures were hit
   during the first deployment; those come first because they have already
   happened once.
2. **Expected from how the stack is built and operated** (R05–R11): login,
   certificates, email, backup, disk, workers, slowness.
3. **Needs a component to actually die** (R12–R13), and **application-level
   faults** (R14–R15), then **change-related** (R16–R17).

R01 is the entry point and sits first because you do not yet know which of the
others you have.

**There are no incident statistics.** One install, one deployment. This order is
a judgement, labelled as one. Re-order it when real tickets exist.

## Ground rules for every procedure

1. **Capture evidence before you fix.** Several fixes destroy the symptom
   (restarting a container clears its state). Save the relevant command output
   first.
2. **Never `docker compose down -v`.** It deletes the database, the uploaded
   files and the encryption key. `down` without `-v` is safe; `restart` and
   `up -d` are safe.
3. **Never edit hotel data with SQL** (`UPDATE` on reservation, folio, invoice or
   ledger tables). The application enforces rules, writes ledger entries and
   audit side effects that raw SQL bypasses. The single exception in this
   runbook is the scheduler timestamp repair in R03, which touches a system
   table and no hotel record.
4. **Do not paste secrets or guest data into a ticket.** Titles from `Error
   Log` are safe; tracebacks, access logs and `docker inspect` are not (see the
   manual, §7–9).
5. **After any fix that restarts `backend` alone, restart `frontend` too** (R02).
6. **Tell the hotel what is down and what it means for them**, in their terms:
   "nobody can check in", "the night audit did not run", "emails are queued".

## Symptom index

| What you see | Go to |
| --- | --- |
| Nothing loads | [R01](#r01-application-down) |
| Pages and API return 502 but images/CSS load, often just after a restart | [R02](#r02-pages-and-api-return-502-after-a-restart) |
| Everything looks fine, but the business date did not advance / no night audit / holds never expire | [R03](#r03-scheduler-not-running) |
| `docker compose up -d` stops with `container db is unhealthy` | [R04](#r04-docker-compose-up-fails-with-db-unhealthy) |
| Someone cannot sign in; PIN messages | [R05](#r05-login-failure) |
| Browser says the certificate is invalid | [R06](#r06-certificate-expired) |
| Confirmations / invoices not arriving | [R07](#r07-email-not-sending) |
| Health says no backup, or the backup job is failing | [R08](#r08-backup-failed-or-missing) |
| Disk full; writes failing | [R09](#r09-disk-full) |
| Health says no worker, or a deep queue | [R10](#r10-background-worker-down-or-queue-backing-up) |
| Everything is slow | [R11](#r11-slow-system) |
| Database errors everywhere | [R12](#r12-database-down) |
| Redis errors; logins failing | [R13](#r13-redis-down) |
| Reservation cancelled unexpectedly, availability wrong, status refuses to change | [R14](#r14-reservation-issue) |
| POS order will not close, PIN prompts, kitchen screen stale | [R15](#r15-pos-failure) |
| `install.sh update` stopped | [R16](#r16-update-failed) |
| `bench migrate` printed a traceback | [R17](#r17-migration-failed) |

---

## R01. Application down

**Symptom.** The browser cannot load `/kamra`, or times out. Every user is
affected. **Impact: nobody can check in, post charges or take POS orders.** No
offline or downtime mode is documented in this repository; the hotel needs its
own paper fallback.

**Confirm it is really this.** Run the first-five-minutes sequence
([manual §5](TECHNICIAN_MANUAL.md#5-diagnose-the-first-five-minutes)):

```bash
dc ps
HTTP_PORT=8080
curl -sS -o /dev/null -w 'page  %{http_code}\n' "http://localhost:${HTTP_PORT}/api/method/ping"
curl -sS -o /dev/null -w 'asset %{http_code}\n' "http://localhost:${HTTP_PORT}/assets/kamra/ziri-mark.png"
systemctl is-active docker
```

| Finding | It is |
| --- | --- |
| `docker` not active (Windows: Docker Desktop not running, or nobody logged in) | Docker daemon down. Start it. |
| `frontend` not `Up` | Start it: below. |
| `configurator` is not `Exited (0)` | Nothing else starts. `dc logs configurator` — usually the database password. |
| `page` 502, `asset` 200 | [R02](#r02-pages-and-api-return-502-after-a-restart) |
| `page` 404 | `FRAPPE_SITE_NAME_HEADER` does not equal `$SITE`. Fix the env file, `dc up -d`. |
| `db` not `(healthy)` | [R04](#r04-docker-compose-up-fails-with-db-unhealthy) or [R12](#r12-database-down) |
| All containers `Up`, `page` 200 locally, but unreachable from outside | Host firewall, the TLS proxy, or DNS. [R06](#r06-certificate-expired) if it is a certificate error. |

**Immediate action.** Bring up whatever is missing; `up -d` is idempotent and
recreates only what is absent or changed:

```bash
sudo systemctl start docker        # if the daemon was down
dc up -d
```

**Fix.** The cause is in the finding column; this step only restores service.
Read the log of whatever would not stay up: `dc logs --tail=100 --timestamps <service>`.

**Verify.** `dc ps` is clean; both `curl` probes return 200; `/kamra/health`
loads and has no `failed` row. Then ask someone at the front desk to open a
reservation.

**Then.** Find out why the daemon or container stopped. A host that reboots and
leaves the hotel down means Docker is not enabled at boot
(`systemctl is-enabled docker`).

---

## R02. Pages and API return 502 after a restart

**Symptom.** After `docker compose restart backend` (and nothing else), static
assets such as CSS and images still return 200, but every page and every API
call returns **502**. The login page may even half-render from cache. `docker
compose ps` shows everything `Up` and healthy. **[live]**

**Why.** nginx in the `frontend` container resolves the hostname `backend` to an
IP address **once, when nginx itself starts**, and caches it. A restarted
container can come back with a new IP. nginx keeps sending traffic to the old
address. Static files are served by nginx directly from the shared volume, so
they never touch `backend` and keep working — which is why this looks like a
half-broken site.

`docker compose up -d` does **not** cause it: it recreates `frontend` when it
recreates `backend`. Only restarting the backend alone does.

**Confirm it is really this.**

1. Is the backend itself healthy? Ask it directly, bypassing nginx. **[standard]**

   ```bash
   dc exec -T backend python -c "import urllib.request as u; r=u.Request('http://127.0.0.1:8000/api/method/ping', headers={'Host':'$SITE'}); print(u.urlopen(r).read().decode())"
   ```

   Expected: `{"message":"pong"}`. If this fails, it is not R02; it is a
   backend fault — read `dc logs --tail=100 backend`.

2. What does the `frontend` container's resolver say `backend` is right now?
   **[live]**

   ```bash
   dc exec frontend getent hosts backend
   ```

3. What is the backend's real address? **[live]**

   ```bash
   docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$(dc ps -q backend)"
   ```

4. **What nginx is actually trying.** Steps 2 and 3 show the current DNS answer
   and the current address; they agree after a restart because DNS is current.
   They do not show nginx's cached copy. The decisive evidence is nginx's error
   log, which names the upstream address it tried. **[standard]**

   ```bash
   dc logs --tail=50 --timestamps frontend | grep -i upstream
   ```

   If the address in the `upstream: "http://<ip>:8000/..."` lines is **not** the
   address from step 3, it is R02. (This log line was not captured verbatim from
   the live incident; the format is nginx's standard.)

**Immediate action and fix** — the same thing:

```bash
dc restart frontend
```

nginx re-resolves `backend` on start.

**Verify.** **[standard]**

```bash
curl -sS -o /dev/null -w 'page  %{http_code}\n' "http://localhost:${HTTP_PORT:-8080}/api/method/ping"
```

200 where it was 502. Open the site in a browser and sign in.

**Prevent.** Whenever you restart `backend`, restart `frontend` with it:
`dc restart backend frontend` (the README's day-to-day table already says so).
The same mechanism should apply to `websocket` (`SOCKETIO: websocket:9000`) —
**inferred from how nginx works, not observed** — so restart `frontend` after
restarting `websocket` too. `install.sh update` recreates every container and
cannot cause this.

The durable fix would be nginx re-resolving the name per request, which lives in
the upstream image and is not changed here.

---

## R03. Scheduler not running

**Symptom.** *There may be none.* This is the failure that does not announce
itself. The `scheduler` container is `Up`, its log is empty, `bench doctor`
reports workers online, `/kamra/health` used to show the scheduler `passed`
(before it was fixed). Meanwhile **the night audit never runs**. The hotel finds
out when:

- the business date has not advanced;
- no `Night Audit Run` exists for last night;
- room charges for in-house guests were not posted;
- expired holds still block inventory;
- scheduled emails and reminders did not go out.

**This is a financial failure, not a technical curiosity**: it is a hotel whose
folios are not being charged.

**What happened on the live install.** **[live]** The scheduler was alive as
pid 1 and logged nothing. It had **never executed a single job since the site
was created**. Frappe computes a job's next run from `last_execution or
creation`. The site time zone had been moved to a lower UTC offset *after* the
site was built, which left all 51 `Scheduled Job Type` rows stamped in the
future — `16:15:14` against a site clock reading `14:19:50`. Nothing was ever
due. The host, container and database clocks all agreed to the second, so this
was **not clock drift**; it was a time-zone change.

`kamra/health.py` now detects this and reports the scheduler `failed` with the
count of future-stamped rows. It cannot fix it.

**Confirm it is really this.** Do all of these; each rules out a different
confusion.

1. The container exists and is quiet (this proves nothing, and that is the
   point):

   ```bash
   dc ps scheduler
   dc logs --tail=30 --timestamps scheduler
   dc exec -T backend bench --site "$SITE" doctor
   ```

2. The setting is on:

   ```bash
   dc exec -T backend bench --site "$SITE" scheduler status
   ```

3. **The decisive comparison — the site's clock against the rows.** **[live]**
   (invocation **[standard]**)

   ```bash
   dc exec -T backend bench --site "$SITE" execute frappe.utils.now_datetime
   dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
   SELECT COUNT(*)                    AS job_types,
          SUM(last_execution IS NULL) AS never_run,
          MIN(creation)               AS oldest_creation,
          MAX(creation)               AS newest_creation,
          MAX(last_execution)         AS last_run
   FROM `tabScheduled Job Type`;
   SQL
   ```

   It is this failure if `MIN(creation)` is **later than** the site's
   `now_datetime()`, and `last_run` is `NULL` or also in the future.

4. Count exactly the rows that are stuck (replace the literal with the
   `now_datetime()` value, to the second):

   ```bash
   dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
   SET @now = '2026-10-01 14:19:50';
   SELECT COUNT(*) AS stuck FROM `tabScheduled Job Type`
   WHERE COALESCE(last_execution, creation) > @now;
   SQL
   ```

5. Rule out clock drift. These should agree to the second:

   ```bash
   date -u; dc exec -T backend date -u; dc exec -T db date -u
   ```

   If they do not, the clocks are the problem: fix NTP on the host first.
   Otherwise continue; the time zone is the cause.

6. Confirm nothing has run, from the job log:

   ```bash
   dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
   SELECT COUNT(*) AS executions, MAX(creation) AS last FROM `tabScheduled Job Log`;
   SQL
   ```

**Immediate action.** Restarting the scheduler container will not help — it is
healthy. **Do not repair yet.** Record the outputs above. Then, before
anything is changed, read **R14** (expired holds) and the catch-up warning below.

**Fix.** Set `last_execution` to the current site time on the affected rows
only. Take a backup first (`TECHNICIAN_MANUAL.md` §10); it costs a minute.

First save what you are about to change:

```bash
dc exec -T backend bench --site "$SITE" mariadb <<'SQL' > scheduler-before.txt
SELECT name, method, frequency, cron_format, creation, last_execution
FROM `tabScheduled Job Type`;
SQL
```

Then, with `@now` set to `now_datetime()` **at the moment you run it**:

```bash
dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
SET @now = '2026-10-01 14:19:50';
UPDATE `tabScheduled Job Type`
   SET last_execution = @now
 WHERE COALESCE(last_execution, creation) > @now;
SELECT ROW_COUNT() AS rows_repaired;
SQL
```

`ROW_COUNT()` should equal the `stuck` count from step 4. Jobs then execute
within minutes. No container restart was needed on the live install.

**Verify the fix worked.** Do not accept "no error".

```bash
# wait 2-5 minutes, then:
dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
SELECT COUNT(*) AS executions, MAX(creation) AS last FROM `tabScheduled Job Log`;
SELECT MAX(last_execution) AS last_run FROM `tabScheduled Job Type`;
SQL
```

`executions` must be above zero and `last_run` must be moving. Refresh
`/kamra/health`: the `scheduler` row must be `passed` with "Running — last job
...". Check again after the next quarter-hour (the `*/15` housekeeping and
hold-expiry jobs) and again the next morning: the `Night Audit Run` for the
night must exist.

**Prevent.** Set the site and Property time zone *before* the first night. If it
must change on a live site, repeat step 3 immediately afterwards. A restore from
another time also carries other timestamps in (manual §11 step 7).

### The part after the fix: the night audit catch-up

Fixing the timestamps makes the scheduler work **from now**. It does not
reconstruct the nights that were missed. Reading `kamra/folio.py`:

- `run_night_audit` audits **one business date** per call and advances the
  property's business date by exactly one day.
- The 03:00 job therefore audits one date per night. After a stall of N days the
  business date lags the calendar by N days and **stays lagging**; the 03:00 job
  will not catch up on its own.
- It posts room charges for reservations whose status is **currently** `Checked
  In` and whose stay covers the date. A guest who checked **out** during the
  stall is not `Checked In` any more, so nights already behind them may not be
  posted by a catch-up run.
- It flags `Confirmed` arrivals dated before the business date as `No Show` and
  can post a no-show charge. Running old dates against reservations that the
  front desk has since dealt with can mis-flag them.

**Do not run a catch-up without the front-office manager's sign-off.** Show them
the lag and the checked-out guests who stayed during the stall; the folios for
those stays may need manual attention. If they agree, per property and per
missed date, oldest first (idempotent per date — a repeat reports
`already_ran`): **[standard]**

```bash
dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
SELECT name, business_date FROM `tabProperty`;
SELECT property, MAX(business_date) AS last_audited FROM `tabNight Audit Run` GROUP BY property;
SQL

dc exec -T backend bench --site "$SITE" execute kamra.folio.run_night_audit \
  --kwargs "{'property': '<PROPERTY NAME>', 'business_date': 'YYYY-MM-DD'}"
```

This path has never been exercised against a stalled site. Rehearse it on a
restored copy first.

---

## R04. Docker compose up fails with db unhealthy

**Symptom.** `docker compose up -d` exits with:

```
dependency failed to start: container db is unhealthy
```

and nothing after `db` starts. **[live]** On a fresh `up`, a `down`/`up` cycle,
or a first install on a slow machine. In Layout A this makes `install.sh` abort
mid-install.

**Why.** MariaDB was **still booting**, not broken. The healthcheck's
`start_period` is a grace window during which failures do not count; upstream's
is **5 s**. On Docker Desktop over WSL2, MariaDB took more than 60 seconds to
begin starting — the entrypoint logged its first line at 12:16:29 and did not
reach "Switching to dedicated user 'mysql'" until 12:17:29. With 5 s plus five
checks, Docker declared the container unhealthy long before it could answer,
cancelled every service waiting on `condition: service_healthy`, and aborted.
`deploy/linux/docker-compose.yml` raises `start_period` to **180 s**. It costs a
fast machine nothing: the container is marked healthy the moment one check
passes.

**Confirm it is really this and not a dead database.**

```bash
dc ps -a
docker inspect --format '{{json .State.Health}}' "$(dc ps -q db)"
dc logs --timestamps db | tail -40
```

| What the log shows | It is |
| --- | --- |
| The entrypoint progressing slowly, then `ready for connections`; or still starting | **R04.** Booting. |
| `No space left on device`, `Can't open`, `InnoDB: ...` corruption, `Permission denied`, `Aborting` | Real database fault: [R12](#r12-database-down) (and [R09](#r09-disk-full) if disk). |
| Healthy status flips to `healthy` on its own a minute later | **R04.** Confirmed. |

**Immediate action.** Do not touch `db-data`. Do not `down -v`. The `db`
container is usually still running and will go healthy by itself; wait for it:

```bash
until [ "$(docker inspect -f '{{.State.Health.Status}}' "$(dc ps -q db)")" = healthy ]; do sleep 5; done; echo db healthy
```

**Fix.** Run the command again; the database is now ready and the rest start:

```bash
dc up -d
dc ps            # configurator Exited (0); everything else Up
```

Layout A (`install.sh`): re-run it — it is safe to re-run and reuses the
existing database password and site.

**Make it stick.**

- **Layout B**: confirm the file has the long grace window:
  `grep -n start_period docker-compose.yml` must show `180s`. An older copy of the
  file has `5s`; replace it.
- **Layout A (and therefore the Windows installer)**: the stack comes from
  upstream's `compose.mariadb.yaml`, not from this repository's compose file. As
  far as this repository shows, **nothing outside `deploy/linux/` carries the
  180 s fix**, so a Layout A install on a slow WSL2 machine can hit this again on
  any cold `up`. Waiting and re-running is the workaround; the permanent fix
  needs a compose override or a change to `install.sh` and has not been made
  (see the recommendations in the delivery report).

**Verify.** `dc ps` shows `db` `(healthy)`, `configurator` `Exited (0)`, all
other services `Up`; `curl` the ping URL → 200; `/kamra/health` → `database
passed`.

---

## R05. Login failure

**Symptom.** A user cannot sign in, or is signed in but refused an action.

**Confirm — which kind is it?**

| Message / behaviour | Meaning | Action |
| --- | --- | --- |
| Whole site fails to load | Not login. | [R01](#r01-application-down) |
| 404 on every URL | Site name header mismatch | Fix `FRAPPE_SITE_NAME_HEADER`, `dc up -d` |
| "Incorrect password" / unknown user | Credentials | Reset below |
| Login page loads; submitting hangs or errors; others affected too | Redis (sessions/cache) or backend | [R13](#r13-redis-down), then `dc logs backend` |
| `PIN_NOT_SET`, `PIN_MUST_RESET`, `PIN_REQUIRED` | Cashier PIN, **not** the login | Enrol / enter PIN in the app |
| `PIN_LOCKED` | 5 wrong PINs; locked 15 minutes | Wait 15 min, or an administrator resets the PIN |
| `SUPERVISOR_PIN_REQUIRED` | The selected reason code needs a supervisor | A Hotel Admin / Finance user must approve |
| "Needs a System / site administrator (IT)" | Role: IT-only action | Use a System Manager account |
| "You don't have access to `<property>`" | User is restricted to other properties | Property permission, set by an administrator |

**Immediate action.** Establish whether it is one user or all. One user →
credentials or permissions. All users → R01 / R13.

**Fix — forgotten or unknown administrator password.** It prompts, so the
password never lands in shell history or the process list: **[standard]**

```bash
dc exec backend bench --site "$SITE" set-admin-password
```

(No `-T`: it needs a terminal.) Other users are reset by an administrator in the
UI.

**Fix — production hygiene.** Confirm no demo accounts exist on a production
site; the check and its expected empty result are `INSTALLATION.md` §7.7.

**Verify.** The user signs in and performs the action that failed. For PINs, the
action that demanded one.

**Note.** If a user reports being "locked out" after repeated wrong passwords,
Frappe applies its own lockout; the duration is a System Settings value that
was **not verified** for this install.

---

## R06. Certificate expired

**Symptom.** Browsers show a certificate warning (`NET::ERR_CERT_DATE_INVALID`)
for the hotel's address. Integrations calling the site over HTTPS (OTA
callbacks, WhatsApp webhooks) may fail silently. **The product has no check for
this and nothing alerts.**

**Confirm.** From outside the server: **[standard]**

```bash
SITE_FQDN=pms.yourhotel.dz
echo | openssl s_client -connect "$SITE_FQDN:443" -servername "$SITE_FQDN" 2>/dev/null | openssl x509 -noout -subject -issuer -dates
```

`notAfter` in the past, or the connection works only on a different name, is
this. If the connection refuses entirely, the proxy is down — R01.

**Immediate action.** Do not train staff to click through certificate warnings;
a hotel that does so cannot tell an expired certificate from an attack. If the
hotel must operate in the meantime, that is their decision, made knowingly.

**Fix — certbot on the host:**

```bash
sudo certbot certificates
sudo certbot renew
sudo systemctl reload nginx         # or the proxy you actually run
```

If `renew` fails: `sudo certbot renew --dry-run` and read why. Usual causes: port
80 blocked by a firewall; DNS no longer points here; the renewal timer is
disabled (`systemctl list-timers | grep -i certbot`); the proxy configuration was
changed. **Caddy** renews itself; read `journalctl -u caddy`.

**Verify.** Repeat the `openssl` command: `notAfter` is in the future. Reload the
site in a browser with no warning. `sudo certbot renew --dry-run` succeeds.

**Prevent.** The stack's nginx does not hold the certificate; the proxy in front
does. Put the expiry date in the hotel's calendar until a certificate check
exists (see ERROR_CODES `NETWORK-002`).

---

## R07. Email not sending

**Symptom.** Booking confirmations, invoices or notifications do not arrive.

**Confirm.** The `Email Queue` doctype is the record
(`docs/email-setup.md`). **[standard]**

```bash
dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
SELECT status, COUNT(*) AS n, MIN(creation) AS oldest
FROM `tabEmail Queue` GROUP BY status;
SELECT email_id, enable_outgoing, default_outgoing, smtp_server, smtp_port
FROM `tabEmail Account`;
SQL
```

| Finding | Meaning |
| --- | --- |
| Many `Not Sent`, oldest is old | Nothing is flushing the queue: scheduler or worker. [R03](#r03-scheduler-not-running), [R10](#r10-background-worker-down-or-queue-backing-up). |
| `Error` rows | SMTP is rejecting. Read the reason with the query below. **It may contain a recipient address; do not forward it raw.** |
| No row with `default_outgoing = 1` and `enable_outgoing = 1` | No outgoing account. Create one (`docs/email-setup.md` §2). |
| Queue empty, mail still missing | The email was never queued: look in `Error Log` for the module that should have sent it. |

To read why messages are failing (local use only, not for a ticket):

```bash
dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
SELECT LEFT(error, 200) AS reason FROM `tabEmail Queue`
WHERE status = 'Error' ORDER BY creation DESC LIMIT 3;
SQL
```

Is the SMTP port reachable from the container? **[standard]**

```bash
dc exec -T backend python -c "import socket; socket.create_connection(('smtp.example.com',587),5); print('open')"
```

**Immediate action.** Messages are retained in the queue; nothing is lost while
the cause is found. Tell the front desk to send critical confirmations by
another channel.

**Fix.** By finding: restore the scheduler/worker; correct the SMTP host, port or
app-password in **Email Account** and use **Send Test Email**; open the outbound
port on the host firewall. Deliverability (mail accepted but in spam) is a DNS
SPF/DKIM/DMARC matter, not a fault (`docs/email-setup.md` §3).

**Verify.** Send a test email from the Email Account screen and receive it.
Re-run the `GROUP BY status` query: `Not Sent` falls to zero and `Sent` rises.

---

## R08. Backup failed or missing

**Symptom.** `/kamra/health` shows `Backup` as `attention`: "No backup taken by
this site", or the newest is over 48 hours old. Or the scheduled job is failing.

**First, do not over-react.** The check cannot see backups taken outside the
application (volume snapshots, host tooling). "No backup taken by this site"
may be a hotel that is protected another way. **Ask**, then verify that the
other way has a tested restore. It reports age only; it never proves a backup
restores.

**Confirm.**

```bash
dc exec -T backend ls -lh "sites/$SITE/private/backups/"
tail -n 30 /var/log/kamra-backup.log        # Linux: the cron job's log (BACKUP.md §7)
```

Windows: `Get-ScheduledTaskInfo -TaskName "Kamra backup"` — `LastTaskResult` must be
`0` (`BACKUP.md` §6). Then run the real command by hand and read the error:

```bash
dc exec -T backend bench --site "$SITE" backup --with-files
```

| Finding | Cause |
| --- | --- |
| Job log shows `docker: command not found` / cannot connect to the daemon | Docker not running at job time (Windows: Docker Desktop is a user-session app; a sleeping or logged-out machine runs nothing) |
| `No space left on device` | [R09](#r09-disk-full) |
| Access denied / database error | [R12](#r12-database-down) |
| No cron entry / no scheduled task | The job was never created. Backup scheduling is **not part of the product**. |
| Backups exist but old, job "succeeds" | The script's `set -e` pipeline hid an earlier failure, or the copy-off step is failing |

**Immediate action.** Take a manual backup now and copy it off the machine
(`TECHNICIAN_MANUAL.md` §10).

**Fix.** Repair the cause above. If no schedule exists, create one per
`BACKUP.md` §6–7 and then **run it by hand and read the output before relying
on it**.

**Verify.**

```bash
cd /opt/kamra/backups && for f in *.sql.gz; do gzip -t "$f" && echo "ok $f"; done
```

and `/kamra/health` shows the `Backup` row `passed` with a fresh age. **Then,
once, restore it onto a throwaway site** (`BACKUP.md` §5). Until that has been
done, record the hotel as having a backup *file*, not a backup. No restore test
is recorded for this stack.

---

## R09. Disk full

**Symptom.** `/kamra/health` `Disk space` is `failed` (under 2 GB or 5% free) or
`attention` (under 5 GB or 10%). Writes fail; MariaDB logs `No space left on
device`; containers restart; uploads fail.

**Confirm — and find what is eating it.** `health.py` only measures the site
path, so look wider. **[standard]**

```bash
df -h /
df -h "$(docker info --format '{{.DockerRootDir}}')"
docker system df
docker system df -v | head -60
sudo du -h $(docker inspect --format '{{.LogPath}}' $(dc ps -q)) 2>/dev/null | sort -h | tail
ls -lh /opt/kamra/backups 2>/dev/null
```

Usual suspects, in order:

1. **Container logs.** The compose file configures no log rotation, so the
   `json-file` logs of busy containers (nginx access logs in `frontend`) grow
   without limit.
2. **Docker build cache and old images** after repeated `install.sh update`.
3. **Backups** kept on the same disk.
4. **The database and uploaded files** — real growth.

**Immediate action — free space safely, in this order:**

```bash
docker builder prune -f                                   # build cache: safe
sudo truncate -s 0 "$(docker inspect --format '{{.LogPath}}' "$(dc ps -q frontend)")"   # log history lost, nothing else
```

Delete old backups only **after** confirming a copy exists off the machine.

**Do not**: `docker system prune -a`, `docker volume prune`, `docker compose down
-v`, or `docker image prune` before you have decided about rollback — a pruned
image is the previous version you would need ([manual §13](TECHNICIAN_MANUAL.md#13-roll-back)).

**Fix.** Stop the logs growing. Docker's daemon-wide setting, in
`/etc/docker/daemon.json`:

```json
{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "5" } }
```

then `sudo systemctl restart docker` and **recreate the containers** (`dc up -d
--force-recreate`) — existing containers keep the logging config they were
created with. This is a recommended change to the host; it is not yet part of
the compose file. If the real data grew, enlarge the disk. If MariaDB crashed
when the disk filled, see [R12](#r12-database-down).

**Verify.** `df -h` shows headroom; `docker system df` stable over a day;
`/kamra/health` `Disk space` is `passed`; `dc ps` all healthy; take a fresh
backup.

---

## R10. Background worker down or queue backing up

**Symptom.** `/kamra/health` `Background workers` is `failed` ("No worker is
running. Queued jobs will never execute.") or `attention` (over 1000 jobs
waiting). Emails and background work stall.

**Confirm.**

```bash
dc ps queue-short queue-long
dc exec -T backend bench --site "$SITE" doctor
dc logs --tail=100 --timestamps queue-short queue-long
docker inspect --format '{{.Name}} oom={{.State.OOMKilled}} restarts={{.RestartCount}}' "$(dc ps -q queue-short)" "$(dc ps -q queue-long)"
```

A worker count above zero with a deep queue means workers are stuck or slow.
Zero means they are down. Remember `doctor` showing workers proves **nothing
about the scheduler** (R03).

**Immediate action.** `dc up -d queue-short queue-long`. If they are running but
stuck, `dc restart queue-short queue-long`. **Do not purge the queue** to "clear
the backlog": the jobs are emails and other real work.

**Fix.** By cause: Redis unreachable → [R13](#r13-redis-down); database →
[R12](#r12-database-down); `oom=true` → the host is out of memory, reduce
`GUNICORN_WORKERS` or add RAM; a crash loop with a Python traceback → capture
the (sanitised) traceback and escalate.

**Verify.** `/kamra/health` shows workers present and the queued count falling
over a few minutes; a queued email goes out ([R07](#r07-email-not-sending)).

---

## R11. Slow system

**Symptom.** Pages take many seconds; the front desk complains. **There is no
capacity data for this product** — nothing has been load-tested or measured —
so this section is triage, not tuning. Do not quote a "supported number of
rooms" to anyone.

**Confirm — where is the time going?** **[standard]**

```bash
uptime; free -m; df -h /
docker stats --no-stream
dc exec -T backend bench --site "$SITE" doctor      # queue depth
dc exec -T db sh -c 'mariadb -uroot -p"$MYSQL_ROOT_PASSWORD"' <<'SQL'
SHOW GLOBAL STATUS WHERE Variable_name IN ('Threads_connected','Threads_running','Max_used_connections');
SHOW VARIABLES LIKE 'max_connections';
SQL
```

| Finding | Likely |
| --- | --- |
| Swap in use / low free RAM | Memory starvation. 4 GB is the stated minimum; each gunicorn worker holds a full app. |
| One container pinned at 100% CPU | That container. `dc logs --tail=100` it. |
| Windows: slow after Docker Desktop has run a while | The WSL2 VM has a memory limit (`%UserProfile%\.wslconfig`) and a disk that never shrinks. |
| Deep job queue | [R10](#r10-background-worker-down-or-queue-backing-up). A backlog competes for the same database. |
| Slow only around 03:00 | The night audit and retention jobs run then (manual §3). |
| `Threads_connected` near `max_connections` | Connection exhaustion: [R12](#r12-database-down). |
| Disk nearly full | [R09](#r09-disk-full) |

**Immediate action.** Restart only the container that is demonstrably wrong, not
the whole stack. If you restart `backend`, restart `frontend` (R02).

**Fix.** Free memory; reduce `GUNICORN_WORKERS` on a small machine (raising it on
4 GB makes this worse); move off Docker Desktop to a Linux host.

**Verify.** The same page now loads in the time the hotel finds acceptable, and
`docker stats` is calm for a business day. Record the before/after numbers; they
are the only capacity data that will exist.

---

## R12. Database down

**Symptom.** Every page errors; `/kamra/health` (if it loads) shows `Database`
`failed`; logs show `Can't connect to MySQL server`, `Too many connections`, or
`Access denied`. This is **MariaDB 11.8** — there is no PostgreSQL.

**Confirm.**

```bash
dc ps db
dc exec db healthcheck.sh --connect --innodb_initialized; echo "exit=$?"
dc logs --tail=100 --timestamps db
df -h /
docker inspect --format 'oom={{.State.OOMKilled}} restarts={{.RestartCount}} exit={{.State.ExitCode}}' "$(dc ps -q db)"
```

| Finding | Cause and next |
| --- | --- |
| Just started / log still progressing | Booting: [R04](#r04-docker-compose-up-fails-with-db-unhealthy). Wait; InnoDB crash recovery after a hard stop can take a while — watch the log, do not restart it in the middle. |
| `No space left on device` | [R09](#r09-disk-full), then restart `db`. |
| `oom=true` | The host killed it for memory. Free RAM; check what else is running. |
| `Access denied for user 'root'` after someone edited `.env` | MariaDB keeps the password its `db-data` volume was **initialised** with. Put the **original** `DB_PASSWORD` back (from your off-box copy of the env file). A new value cannot be applied by editing `.env`. |
| `Too many connections` | `Threads_connected` at `max_connections`: find the offender (workers in a crash loop reconnecting) and fix it. |
| InnoDB corruption / `Aborting` | Real damage. Go to the restore path below. |

**Immediate action.** Do not delete `db-data`. Do not `down -v`. Do not "reinitialise
the database". Before any destructive recovery, **copy the volume aside**, with
`db` stopped (the copy holds all hotel and guest data; keep it on the machine,
mode 700):

```bash
dc stop db
docker volume ls | grep db-data            # note the exact volume name
docker run --rm -v <exact_volume_name>:/v -v "$PWD":/b alpine tar czf /b/db-data-copy.tgz -C /v .
```

**Fix.** Per cause above. If the data is genuinely damaged, restore the newest
backup ([manual §11](TECHNICIAN_MANUAL.md#11-restore)) — and accept the data loss
since that backup, which the hotel must be told about in numbers (hours).

**Verify.** `healthcheck.sh` exits 0; `dc ps db` healthy; `/kamra/health`
`Database passed`; sign in and open a reservation; check `Patch Log`'s newest
entry is still present (manual §14); re-check the scheduler (R03) if you
restored.

---

## R13. Redis down

**Symptom.** Logins fail or hang; `/kamra/health` `Redis` is `failed` ("Cache
unreachable") and/or `Background workers` says "Could not reach the queue
broker". There are **two** Redis instances: `redis-cache` and `redis-queue`.

**Confirm.** **[standard]**

```bash
dc ps redis-cache redis-queue
dc exec redis-cache redis-cli ping
dc exec redis-queue redis-cli ping
dc logs --tail=50 --timestamps redis-cache redis-queue
dc exec redis-cache redis-cli info memory | grep -E 'used_memory_human|maxmemory_human'
```

Which one answers tells you which half is broken: `redis-cache` → sessions and
cached pages; `redis-queue` → background jobs.

**Immediate action.** `dc restart redis-cache` and/or `dc restart redis-queue`.
`redis-cache` has no volume: its contents are cache and are rebuilt. `redis-queue`
has a volume (`redis-queue-data`) but how much of the queue survives a restart
depends on its persistence settings, which this compose file does not set and
which were **not verified**; assume jobs queued since the last snapshot may be
lost, and check afterwards that expected emails went out.

**Fix.** If Redis is healthy again but the application still errors, its
connections are stale: restart the clients — `dc restart backend queue-short
queue-long scheduler` — **and then `frontend`** (R02). If Redis will not stay up,
read its log (out of memory, disk).

**Verify.** Both `ping`s return `PONG`; `/kamra/health` `Redis passed` and
`Background workers` shows workers; a login succeeds; queue depth falls.

---

## R14. Reservation issue

**Symptom and confirm — which one is it?** These are different problems that
look alike to the front desk.

**A. A reservation was cancelled that the guest says they confirmed.** The
`*/15` job `expire_holds` cancels reservations in `Held` or `Pending Payment`
whose `hold_expires_on` has passed, with the reason "Hold / payment window
expired". Confirm without reading guest data: **[standard]**

```bash
dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
SELECT COUNT(*) AS cancelled_by_hold_expiry
FROM `tabReservation` WHERE cancellation_reason = 'Hold / payment window expired';
SQL
```

and look at the one reservation in the UI (reason, timestamps, payments). **If
the scheduler was stalled (R03) and has just been repaired, the first run will
cancel every hold that lapsed during the stall in a single burst — including
ones the guest has since paid for.** Before repairing R03, count them and give
the list to the front desk:

```bash
dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
SELECT status, COUNT(*) FROM `tabReservation`
WHERE status IN ('Held','Pending Payment') AND hold_expires_on < NOW() GROUP BY status;
SQL
```

(`NOW()` is the database's clock; use the site's time if the two offsets differ.)

**B. "Cannot move reservation from X to Y."** An invalid status change. This is a
rule, not a fault; the reservation must follow the allowed path. No technician
action.

**C. "Assign a room before check-in."** Validation. Assign a room.

**D. Availability or rates on OTAs are wrong.** The hourly `push_all_ari` job
pushes them and logs `ARI push failed: <connection>` to `Error Log` when one
fails. **[standard]**

```bash
dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
SELECT creation, method FROM `tabError Log` WHERE method LIKE 'ARI push failed%' ORDER BY creation DESC LIMIT 10;
SQL
```

A failure is per connection; the others are unaffected. Causes: provider down,
credentials expired, scheduler stalled (R03).

**E. Arrivals flagged `No Show` that did arrive, or charges missing, or the
business date is behind.** The night audit flags and charges as it runs. Read the
catch-up warning at the end of R03 before running anything.

**Immediate action.** Do not edit reservation rows with SQL. A reservation
change that bypasses the application also bypasses its validation, the ledger and
the audit trail. Staff with the right role make the correction in the UI.

**Fix.** A → reinstate through the UI after the hotel confirms with the guest;
fix the scheduler. D → fix the connection's credentials in the Channel Manager
screen, wait for the next hourly push or trigger one by changing availability.

**Verify.** The reservation shows the right status; the OTA shows the right
availability; the `Error Log` stops growing new `ARI push failed` titles.

---

## R15. POS failure

**Symptom.** A POS order will not create, close or pay; a prompt demands a PIN;
the kitchen screen is stale.

**Confirm — most POS "failures" are the application refusing on purpose.**

| Message | Meaning | Action |
| --- | --- | --- |
| "Add at least one available item." | Items unavailable / empty order | Menu availability |
| "This order is already closed." / "Already paid." | State | None; refresh |
| "Already posted to the room folio - settle it there." | The charge went to a room | Settle on the folio |
| "Pick a payment mode: Cash, Card or UPI." | No payment mode chosen | Staff |
| "This is an NC (complimentary) bill - close it with ..." / "Who authorized the NC?" | Complimentary orders need an authoriser | Staff |
| `PIN_NOT_SET` / `PIN_MUST_RESET` / `PIN_REQUIRED` / `PIN_LOCKED` / `SUPERVISOR_PIN_REQUIRED` | Cashier PIN guard on money actions | See [R05](#r05-login-failure) |

Genuine faults leave a trail in `Error Log`: **[standard]**

```bash
dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
SELECT creation, method FROM `tabError Log`
WHERE method LIKE 'ledger%' OR method LIKE 'shift handover%' OR method LIKE '%payment%'
ORDER BY creation DESC LIMIT 20;
SQL
```

Kitchen or table screens not updating live: `dc ps websocket` — the
`websocket` service being down stops live updates while pages still work.

**Immediate action.** For `ledger ... write failed`: the sale and its ledger
entry may disagree. **Do not retry the payment blindly** — you may charge twice.
Note the order, the time and the title; have the cashier hold the order open.

**Fix.** Messages above need no technician. A genuine ledger fault needs the
(sanitised) traceback and a developer. A stale kitchen screen: `dc up -d
websocket`, then `dc restart frontend` (R02 applies to websocket).

**Verify.** The order closes; a test sale reaches the cashier session's totals;
no new matching `Error Log` titles appear.

---

## R16. Update failed

**Symptom.** `install.sh update` (or the manual equivalent) stopped.

**Confirm — which stage?** The script prints each stage. The failure message
tells you where:

| Output | Stage | State of the site |
| --- | --- | --- |
| `docker build failed — see output above (disk full? out of memory?)` | Image build | **The running site is untouched.** The old image still holds the `kamra:local` tag (a failed build does not retag). |
| `no <env> — run install first` / `no <apps.json> — run install first` | Pre-checks | Untouched. |
| `backend did not become ready — check: docker compose -p kamra logs` | After recreate | New image running, backend not up. |
| Output stops after `Migrating sites…` or shows a traceback | Migration | New code, partly migrated database: [R17](#r17-migration-failed). |
| `unauthorized` when pulling `ghcr.io/kamra-pms/kamra` | An old installer | `deploy/TROUBLESHOOTING.md` |

**Immediate action.** Read the failure; **do not simply re-run `update`** — each
run rebuilds the image (20–45 minutes) and recreates every container. If the
failure was at build, the site is still serving the old version: leave it
serving while you find the cause.

**Fix.** Build failures: disk ([R09](#r09-disk-full)), memory (the build wants
~8 GB RAM+swap; `install.sh` adds a swap file below that), the source repository
no longer publicly readable (the build clones it with no credentials), or no
network to GitHub/PyPI. Backend not ready: `dc logs --tail=100 backend`;
[R04](#r04-docker-compose-up-fails-with-db-unhealthy) if the database is the
cause. If it is unrecoverable quickly, roll back
([manual §13](TECHNICIAN_MANUAL.md#13-roll-back)) — which needs the pre-update
backup and the image tag you made beforehand.

**Verify.** `dc ps` clean; `bench version` is the version you intended;
`/kamra/health`; the two `curl` probes; **the scheduler is executing (R03)**. If
you rolled back, the version is the old one and `migrate` is a no-op.

---

## R17. Migration failed

**Symptom.** `bench migrate` ended with a traceback, or `install.sh update`
stopped after `Migrating sites…`. The site may show an error or maintenance page.

**Confirm.** What was applied, and where did it stop? **[standard]**

```bash
dc exec -T backend tail -n 8 apps/kamra/kamra/patches.txt
dc exec -T backend bench --site "$SITE" mariadb <<'SQL'
SELECT patch, creation FROM `tabPatch Log` ORDER BY creation DESC LIMIT 8;
SQL
```

The first patch in `patches.txt` that is missing from `Patch Log` is the one that
failed (or never ran). The traceback names it. The newest patches in this
product are `v36.backfill_room_levy_mode` and `v37.normalize_legal_id_columns`;
both have been applied on the live install.

**Immediate action.** The database is now at an in-between state. **Take a
backup of it as it is** before anything else (manual §10) — it is evidence and
the only copy of whatever was done. Check whether maintenance mode was left on
(symptom: a maintenance/"updating" page).

**Fix.** Two cases:

- **Transient** (disk full, database restart, lock timeout): fix the cause
  ([R09](#r09-disk-full), [R12](#r12-database-down)) and run `migrate` again. The
  patch runner skips patches recorded in `Patch Log`; a patch that failed
  halfway is **not** recorded and runs again **from the beginning**. Whether
  the failed patch is safe to re-run is a question for the developer — do not
  assume.
- **Deterministic** (a bug in the patch, or data it did not expect): re-running
  will fail identically. Roll back: put the previous image back and **restore
  the pre-update backup** ([manual §13](TECHNICIAN_MANUAL.md#13-roll-back)), then
  send the developer the patch name and the (sanitised) error. Do not hand-edit
  the schema.

Afterwards, if maintenance mode is stuck: `dc exec -T backend bench --site
"$SITE" set-maintenance-mode off`.

**Verify.** `migrate` completes with no error; the last line of `patches.txt` is
in `Patch Log`; `clear-cache`; `/kamra/health`; sign in and open a reservation
and a folio; scheduler executing (R03).

---

## What this does not cover / has not been tested

- **No procedure here has been executed by its author.** R02, R03 and R04 were
  diagnosed and fixed on the live install by someone else; the confirm steps and
  the fix for those three come from that record and are labelled **[live]**
  where they were used. Everything else is **[standard]** usage composed from
  the repository's files and the documented behaviour of Docker, Frappe, MariaDB
  and Redis. Run on a trial site first.
- **Not exercised on a Linux server.** The stack has only run on Docker Desktop
  over WSL2.
- **R02 step 4** (the nginx upstream log line) was not captured from the live
  incident. **R02's websocket analogue** is inference.
- **R03's catch-up reasoning** is from reading `kamra/folio.py`, not from
  running the audit against a stalled site. The statement that guests who
  checked out are not charged for missed nights is a reading of the query, not a
  tested outcome. `run_night_audit` as invoked from `bench execute` is untested.
- **R03's SQL assumes** the `tabScheduled Job Type`, `tabScheduled Job Log`,
  `tabPatch Log`, `tabEmail Queue`, `tabEmail Account`, `tabError Log` and
  `tabProperty` table and column names of the Frappe v16 schema as read from
  Frappe conventions and this repository; they were not run against the live
  database by the author.
- **R04 on Layout A** is an inference from the compose file's comment about
  upstream's 5 s value, not a reproduction.
- **R05 lockout duration** and **R13 queue persistence** were not verified.
- **Recovery time, recovery point, capacity, response-time targets**: none have
  been measured. This runbook contains no SLA and promises none.
- **There is no monitoring or alerting.** Every procedure here starts when a
  human notices. The scheduler failure in R03 notified nobody. Certificate
  expiry in R06 and a failing backup job in R08 notify nobody.
- **Not covered:** hardware failure, ransomware, network and ISP faults,
  Frappe Cloud hosting, multi-site stacks, the channel-manager and
  e-invoicing providers' own outages, data-protection incident handling under
  Law 18-07 (legal process, not technical), anything on the Windows host outside
  WSL2.
- **Support at a distance** is limited by the absence of a support bundle
  ([manual §8–9](TECHNICIAN_MANUAL.md#8-create-a-support-bundle-does-not-exist-yet)).
- English only.
