# ZIRI PMS — Error Code Taxonomy

**Status: 27 of the 67 allocated codes are emitted and visible on screen. The
rest are allocated against conditions that have no machine signal, and say so.**

This document was a specification for most of its life: it opened by saying that
a repository-wide search for `DB-001` or `UPDATE-003` returned zero hits, and
that was true. Section 1 defines the scheme and Section 3 allocates the codes so
that a technician, a customer and a developer refer to one failure by one
identifier.

What now emits them:

| Surface | What it shows | Where |
| --- | --- | --- |
| Health checks | `code` on every check that reports a condition | `kamra/health.py`, 23 branches |
| `bench ziri-doctor` | the code beside each row, and a `codes:` line to paste into a ticket | `kamra/commands.py` |
| Support bundle | `codes_fired` in `health.json` | `kamra/support_bundle.py` |
| `Error Log` titles | `[APP-007]`, `[APP-009]`, `[APP-010]` prefixes | `folio.py`, `reservation_state.py`, `api.py`, `payments.py` |
| Entitlement | LICENSE-001 to -004, never `failed` | `kamra/entitlement.py` via `health.py` |
| Channel webhooks | SECURITY-001 on a rejected signature | `kamra/whatsapp.py`, `kamra/voice_jambonz.py` |

`kamra/scripts/error_code_check.py` fails CI if the source emits a code this
document does not allocate, or if this status line goes stale again. It also
checks the two counts in this document against the source, because a prose
count nothing verifies is the same failure one digit smaller — adding the four
LICENSE codes made both numbers wrong in a single commit, and the guard caught
it.

It deliberately does **not** require every allocated code to be emitted: 40 are
not, because their basis is `doc`, `designed` or `live` — real conditions with
no machine signal. Requiring emission would force either fake signals or the
deletion of true entries.

Each entry says what exists today that identifies the condition (a health
check, an `Error Log` title, a message string, a script message), or says
plainly that nothing does.

Companions: [`../support/PRODUCTION_RUNBOOK.md`](../support/PRODUCTION_RUNBOOK.md)
(the procedure each code points to) and
[`../support/TECHNICIAN_MANUAL.md`](../support/TECHNICIAN_MANUAL.md).

---

## 1. The scheme

```
<CATEGORY>-<NNN>
```

- **CATEGORY**: one of thirteen fixed words (Section 2), upper case.
- **NNN**: three digits, allocated sequentially from `001` within the category.
- Examples: `DB-001`, `UPDATE-003`, `CONFIGURATION-004`.

Rules:

1. **A code names a condition, not a message.** The English text can change, be
   translated into French or Arabic, or be reworded; the code does not.
2. **Never reused, never renumbered.** If a condition disappears, the entry stays
   with status `RETIRED` so old tickets still resolve.
3. **Severity is not part of the code.** `APP-004` is "scheduler last ran a long
   time ago" whether a given site rates that a warning or an outage. Severity is
   a separate attribute so re-rating never forces a code to change. Where a signal
   exists today, its native level is given (`passed / attention / failed / info`
   from `health.py`).
4. **One condition, one code.** Different causes of the same condition share a
   code (the *Likely cause* column lists them). Different conditions with the
   same cause get different codes.
5. **A code is only allocated when** (a) a signal for the condition exists in this
   repository today, or (b) the condition is a documented failure of this stack
   that a human has observed, or (c) it is *designed* here with a stated
   detection method. The **Basis** line of every entry says which. No code exists
   "for completeness".
6. **A code must point somewhere.** Each entry links a runbook or manual section,
   or says `none yet`, which is a visible gap rather than a hidden one.
7. The category list is closed. A new category needs a decision, not a commit.

### Basis vocabulary

| Basis | Meaning |
| --- | --- |
| `health:<id>` | `kamra/health.py` already produces this, as the check with that `id` |
| `log:<title>` | The application already writes this title to the `Error Log` doctype via `frappe.log_error` |
| `message:<text>` | The application already raises this exact text |
| `script:<text>` | `deploy/install.sh` already prints this text |
| `doc` | A documented failure of this stack; observed by a human, with no machine signal |
| `live` | Observed on the live install during the first deployment |
| `designed` | Condition is real; **no signal exists**; the detection method is given |

### How a code is emitted

Built on what exists; no parallel system. This section described a design; it now
describes the implementation.

- **`health.py`**: `_check()` takes an optional `code` keyword (`None` default,
  so nothing existing changed) and `system_health()` returns it per check. The
  code is set **per branch, not per function**, because it names the condition
  and not the check: `_scheduler_check` alone returns APP-001, APP-002, APP-003
  or APP-004. A healthy branch carries no code, and neither does a branch
  reporting something true but unactionable — "no releases published yet" is
  not a fault.
- **`Error Log`**: titles gain a bracketed prefix, e.g. `[APP-007] Night audit
  failed: <property>`. Titles are already the thing technicians query
  (`method` column), so no schema change is needed.
- **Raised messages**: the existing `PIN_*` and `SUPERVISOR_PIN_REQUIRED` strings
  already carry a machine prefix. Keep them as they are for compatibility and
  map them (Section 3, AUTH).
- **Support bundle**: lists the codes whose signals fired
  ([`TECHNICIAN_MANUAL.md` §9](../support/TECHNICIAN_MANUAL.md#9-specification-the-support-bundle-that-must-be-built)).
- **Never** put guest data, a secret or a path containing one into a code's
  message. The code is the safe, shareable part.

---

## 2. Categories

| Category | Covers |
| --- | --- |
| APP | The ZIRI application itself: scheduler, workers, night audit, business logic faults |
| DB | MariaDB and the two Redis instances — the data stores |
| NETWORK | Reachability between containers, to the user, and to the outside world |
| AUTH | Who is acting: cashier PINs, roles, property access |
| SECURITY | Protection of data and keys, retention failures, webhook integrity |
| LICENSE | Commercial licence state. **No codes allocated** — see Section 3 |
| BACKUP | Existence, age and integrity of backups |
| UPDATE | Getting a new version onto the install |
| MIGRATION | Schema and data patches |
| DOCKER | Container runtime and compose stack state |
| STORAGE | Disk, volumes, log growth |
| CONFIGURATION | Wrong or missing settings |
| INTEGRATION | Mail, channel manager, messaging, e-invoicing |

Redis is filed under DB ("data stores"), not NETWORK, because what fails is the
data service.

---

## 3. Allocated codes

Runbook links are to
[`../support/PRODUCTION_RUNBOOK.md`](../support/PRODUCTION_RUNBOOK.md); `manual §n`
is [`TECHNICIAN_MANUAL.md`](../support/TECHNICIAN_MANUAL.md).

### APP

| Code | Meaning | Likely cause | First action | Runbook |
| --- | --- | --- | --- | --- |
| APP-001 | Scheduler is switched off. **Basis:** `health:scheduler` (`attention`) | `enable_scheduler` off in System Settings | Turn it on, then verify it *executes* (APP-003/004) | [R03](../support/PRODUCTION_RUNBOOK.md#r03-scheduler-not-running) |
| APP-002 | Scheduled jobs are stamped in the future, so none will ever come due; the night audit does not run. **Basis:** `health:scheduler` (`failed`, with a count); `live` | Site time zone moved to a lower UTC offset after the site was created; or a restore carrying other timestamps. **Not** clock drift | Compare `frappe.utils.now_datetime()` with `MIN(creation)` on `tabScheduled Job Type`; repair `last_execution` on the affected rows | [R03](../support/PRODUCTION_RUNBOOK.md#r03-scheduler-not-running) |
| APP-003 | Scheduler is enabled but no scheduled job has ever executed. **Basis:** `health:scheduler` (`attention`) | Normal for minutes after first boot. Afterwards: `scheduler` container not running, or APP-002 | Check `dc ps scheduler`, then compare clocks as for APP-002 | [R03](../support/PRODUCTION_RUNBOOK.md#r03-scheduler-not-running) |
| APP-004 | Last scheduled job ran over 6 h ago (`attention`) or over 24 h ago (`failed`). **Basis:** `health:scheduler` | Scheduler process stopped or crash-looping; workers down so jobs are not completing | `dc logs scheduler`; `dc ps` | [R03](../support/PRODUCTION_RUNBOOK.md#r03-scheduler-not-running) |
| APP-005 | No background worker is running. **Basis:** `health:workers` (`failed`) | `queue-short` / `queue-long` down; Redis queue unreachable | `dc up -d queue-short queue-long`; read their logs | [R10](../support/PRODUCTION_RUNBOOK.md#r10-background-worker-down-or-queue-backing-up) |
| APP-006 | More than 1000 jobs are waiting despite live workers. **Basis:** `health:workers` (`attention`) | Workers stuck or too slow; a job type failing and retrying | Read worker logs; check memory | [R10](../support/PRODUCTION_RUNBOOK.md#r10-background-worker-down-or-queue-backing-up) |
| APP-007 | Night audit raised an exception for a property and did not complete it. **Basis:** `log:Night audit failed: <property>` | Data the audit did not expect; database or lock error | Read the sanitised traceback; do not re-run blindly (idempotent per date, but partial effects are possible) | [R03](../support/PRODUCTION_RUNBOOK.md#r03-scheduler-not-running) |
| APP-008 | A property's business date is behind the calendar date. **Basis:** `designed` — compare `Property.business_date` with today; the audit advances it by exactly one day per run, so a stall leaves it permanently behind | Missed night audits (APP-002/003/004/007) | Do **not** catch up without front-office sign-off | [R03](../support/PRODUCTION_RUNBOOK.md#r03-scheduler-not-running) (catch-up section) |
| APP-009 | Releasing an expired hold failed for a reservation. **Basis:** `log:Hold expiry failed for <reservation>` | Data or database fault on that row | Open that reservation in the UI; escalate with the traceback | [R14](../support/PRODUCTION_RUNBOOK.md#r14-reservation-issue) |
| APP-010 | A ledger write failed (charge, payment, refund, void reversal, or payment link). **Basis:** `log:ledger charge write failed`, `ledger payment write failed`, `ledger refund write failed`, `ledger void reversal failed`, `ledger payment-link write failed` | Database fault during a money action; the sale and its ledger entry may disagree | Hold the order; **do not retry the payment**; escalate with the traceback | [R15](../support/PRODUCTION_RUNBOOK.md#r15-pos-failure) |
| APP-011 | The application does not answer end to end. **Basis:** `designed` — the health screen cannot report its own outage; needs an *external* probe of `/api/method/ping` | Any of R01's findings | `dc ps`; the two `curl` probes | [R01](../support/PRODUCTION_RUNBOOK.md#r01-application-down) |

### DB

| Code | Meaning | Likely cause | First action | Runbook |
| --- | --- | --- | --- | --- |
| DB-001 | MariaDB does not answer queries. **Basis:** `health:database` (`failed`) | Container down; booting; disk full; out of memory; corruption | `dc ps db`; `healthcheck.sh`; `dc logs db` | [R12](../support/PRODUCTION_RUNBOOK.md#r12-database-down) |
| DB-002 | `Access denied for user 'root'` after `.env` was edited. **Basis:** `doc` (`deploy/linux/README.md`) | MariaDB keeps the password its `db-data` volume was initialised with; the edited `DB_PASSWORD` is not the original | Restore the original `DB_PASSWORD` from the off-box copy | [R12](../support/PRODUCTION_RUNBOOK.md#r12-database-down) |
| DB-003 | The cache accepts a write but cannot round-trip it, or is unreachable. **Basis:** `health:redis` (`failed`) | `redis-cache` down or out of memory | `redis-cli ping`; `dc logs redis-cache` | [R13](../support/PRODUCTION_RUNBOOK.md#r13-redis-down) |
| DB-004 | The job-queue broker cannot be reached. **Basis:** `health:workers` (`failed`, "Could not reach the queue broker") | `redis-queue` down | `redis-cli ping` on `redis-queue` | [R13](../support/PRODUCTION_RUNBOOK.md#r13-redis-down) |

### NETWORK

| Code | Meaning | Likely cause | First action | Runbook |
| --- | --- | --- | --- | --- |
| NETWORK-001 | Pages and API return 502 while static assets return 200. **Basis:** `live` | nginx in `frontend` cached the IP of `backend` at its own start; `backend` was restarted alone and got a new address | `dc restart frontend` | [R02](../support/PRODUCTION_RUNBOOK.md#r02-pages-and-api-return-502-after-a-restart) |
| NETWORK-002 | The public TLS certificate is expired or about to expire. **Basis:** `designed` — an external `openssl x509 -checkend` probe against the public name; the stack serves plain HTTP and no check exists | Failed renewal (port 80 blocked, DNS moved, timer disabled) | `openssl s_client` against the public name | [R06](../support/PRODUCTION_RUNBOOK.md#r06-certificate-expired) |
| NETWORK-003 | The site could not reach GitHub to compare versions. **Basis:** `health:version` (`info`, "Could not reach GitHub") | No outbound HTTPS; GitHub rate limit; DNS | Informational. Not a fault in the hotel's operation | none (informational) |

### AUTH

The first six are text the application **already raises**; the codes give them
stable names. Keep the existing prefixes in the messages.

| Code | Meaning | Likely cause | First action | Runbook |
| --- | --- | --- | --- | --- |
| AUTH-001 | Cashier has no PIN yet. **Basis:** `message:PIN_NOT_SET` | Property requires a cashier PIN; user never enrolled | User enrols a PIN on the prompting screen | [R05](../support/PRODUCTION_RUNBOOK.md#r05-login-failure) |
| AUTH-002 | An admin reset the PIN; a new one must be enrolled. **Basis:** `message:PIN_MUST_RESET` | Admin reset | User enrols a new PIN | [R05](../support/PRODUCTION_RUNBOOK.md#r05-login-failure) |
| AUTH-003 | A money action needs the PIN and none was supplied. **Basis:** `message:PIN_REQUIRED` | Normal prompt | Enter PIN | [R05](../support/PRODUCTION_RUNBOOK.md#r05-login-failure) |
| AUTH-004 | Wrong cashier PIN. **Basis:** `message:Wrong cashier PIN.` | Mistyped; counts toward the lock | Retry carefully | [R05](../support/PRODUCTION_RUNBOOK.md#r05-login-failure) |
| AUTH-005 | PIN locked after 5 wrong attempts, for 15 minutes. **Basis:** `message:PIN_LOCKED` | Repeated wrong PIN | Wait 15 min or an administrator resets | [R05](../support/PRODUCTION_RUNBOOK.md#r05-login-failure) |
| AUTH-006 | The selected reason code needs supervisor approval. **Basis:** `message:SUPERVISOR_PIN_REQUIRED` | Reason code flagged `requires_supervisor` | Hotel Admin / Finance user approves | [R05](../support/PRODUCTION_RUNBOOK.md#r05-login-failure) |
| AUTH-007 | Action restricted to IT administrators. **Basis:** `message:Needs a System / site administrator (IT).` | A Hotel Admin (business role) attempted a System Manager action | Use a System Manager account | [R05](../support/PRODUCTION_RUNBOOK.md#r05-login-failure) |
| AUTH-008 | User may not act on this property. **Basis:** `message:You don't have access to <property>.` | User restricted to other properties | Administrator adjusts the user's property access | [R05](../support/PRODUCTION_RUNBOOK.md#r05-login-failure) |

### SECURITY

| Code | Meaning | Likely cause | First action | Runbook |
| --- | --- | --- | --- | --- |
| SECURITY-001 | An inbound channel webhook failed signature verification and was rejected. **Basis:** `log:WhatsApp webhook signature rejected`, `log:[SECURITY-001] jambonz call hook: bad signature` | Wrong/rotated app secret (misconfiguration) — or someone forging requests | Compare the configured secret with the provider's; if it was not recently changed, treat as hostile | none yet |
| SECURITY-002 | A guest ID image could not be deleted under the retention policy, so personal data was kept longer than intended. **Basis:** `log:ID document discard failed: <reservation>`, `log:ID document: stale file kept (...)` | File-system or database error during discard | Escalate to development and to the person responsible for data protection. Do not delete files by hand | none yet |
| SECURITY-003 | Demo accounts (`@kamra.local`) exist on a production site. **Basis:** `doc` (`INSTALLATION.md` §7.7 — query must return empty) | A trial/demo site promoted, or demo seed run on production | Do not hand the site over; follow `INSTALLATION.md` §1 | none yet (installation doc) |
| SECURITY-004 | A public endpoint refused a caller for exceeding its hourly limit (10–30 per hour per endpoint). **Basis:** `doc` — `@rate_limit` in `kamra/public_api.py`; Frappe responds HTTP 429 | A guest retrying a self check-in step; or abuse | Normally none; if repeated from one source, treat as abuse | none yet |
| SECURITY-005 | The support bundle's canary scan found a live secret in the finished bundle and aborted. **Basis:** `designed` ([manual §9.4](../support/TECHNICIAN_MANUAL.md#94-how-logs-are-sanitised)) | Redaction rule gap | Fix the ruleset; never send the partial bundle | manual §9 |

### LICENSE

Four codes, and only four. `kamra/entitlement.py` records what a customer
bought and reports when it lapses; it gates nothing, because ZIRI PMS is
AGPL-3.0 and section 7 of that licence does not permit restricting the right to
run the program (see that module's header, and `docs/algeria/LICENSING.md`).

That is why **no code here is ever `failed`.** Nothing has broken. An expired
invoice reported as a red cross teaches an operator that red crosses are noise,
and the next one is a database that has stopped answering. monitoring.py alerts
only on `failed`, so none of these will ever page anyone.

The states this section once reserved numbers for - "signature invalid",
"activation failed" - are **not allocated**, because there is no signature and
no activation to fail. Rule 5: no code exists for completeness.

| Code | Meaning | Likely cause | First action | Runbook |
| --- | --- | --- | --- | --- |
| LICENSE-001 | The entitlement expires within 30 days. **Basis:** `health:entitlement` (`attention`) | Normal; a renewal is due | Renew, or clear the record if the relationship has ended | none yet |
| LICENSE-002 | The entitlement expired within the last 30 days - the grace window. **Basis:** `health:entitlement` (`attention`) | Renewal not yet processed | Confirm with the vendor whether it was renewed; the hotel's PMS is unaffected either way | none yet |
| LICENSE-003 | The entitlement expired more than 30 days ago. **Basis:** `health:entitlement` (`attention`) | The relationship lapsed or ended | Renew, or run `bench ziri-entitlement --clear`: a lapsed record reported for ever is noise, and no record is a supported state | none yet |
| LICENSE-004 | An entitlement record is present in site config and cannot be parsed. **Basis:** `health:entitlement` (`info`) | Hand-edited `site_config.json`; invalid JSON or an unparseable `expires` date | Rewrite it with `bench ziri-entitlement --set`, which validates | none yet |

No code is allocated for `unregistered`, `active` or `perpetual`. An install
with no commercial relationship at all is exactly what the AGPL permits and is
not a fault.

### BACKUP

| Code | Meaning | Likely cause | First action | Runbook |
| --- | --- | --- | --- | --- |
| BACKUP-001 | The site has taken no backup. **Basis:** `health:backup` (`attention`) | No schedule was ever created — scheduling is not part of the product — **or** the hotel backs up externally and the check cannot see it | Ask which; if external, verify its restore has been tested | [R08](../support/PRODUCTION_RUNBOOK.md#r08-backup-failed-or-missing) |
| BACKUP-002 | Newest backup is older than 48 hours. **Basis:** `health:backup` (`attention`) | Scheduled job failing silently; machine off; Docker not running at job time | Run the backup by hand and read the error | [R08](../support/PRODUCTION_RUNBOOK.md#r08-backup-failed-or-missing) |
| BACKUP-003 | The backup directory could not be read. **Basis:** `health:backup` (`info`) | Site path or permissions | `ls` the directory from `backend` | [R08](../support/PRODUCTION_RUNBOOK.md#r08-backup-failed-or-missing) |
| BACKUP-004 | The scheduled backup job (host cron / Windows Task Scheduler) is failing. **Basis:** `doc` (`BACKUP.md` §6–7); invisible to the application | Docker Desktop not running (user-session app); sleeping machine; script error | Host job log; `Get-ScheduledTaskInfo` `LastTaskResult` | [R08](../support/PRODUCTION_RUNBOOK.md#r08-backup-failed-or-missing) |
| BACKUP-005 | No restore of this install's backups has ever been rehearsed. **Basis:** `designed` — needs a recorded restore-test date, which does not exist | Nobody did it | Rehearse a restore onto a throwaway site (`BACKUP.md` §5) | [R08](../support/PRODUCTION_RUNBOOK.md#r08-backup-failed-or-missing) |
| BACKUP-006 | A backup archive fails an integrity test. **Basis:** `doc` — `gzip -t` / `tar -tf` in [manual §10](../support/TECHNICIAN_MANUAL.md#10-back-up) | Truncated by a full disk or interrupted copy | Take a new backup; do not delete the failing one until the new one passes | [R08](../support/PRODUCTION_RUNBOOK.md#r08-backup-failed-or-missing) |

### UPDATE

| Code | Meaning | Likely cause | First action | Runbook |
| --- | --- | --- | --- | --- |
| UPDATE-001 | A newer release exists. **Basis:** `health:version` (`attention`) | Normal | Plan an update window; back up first | [manual §12](../support/TECHNICIAN_MANUAL.md#12-update) |
| UPDATE-002 | The image build failed. **Basis:** `script:docker build failed — see output above (disk full? out of memory?)` | Disk, memory, source repository not public, no network | Read build output; the running site is unaffected | [R16](../support/PRODUCTION_RUNBOOK.md#r16-update-failed) |
| UPDATE-003 | The backend did not become ready after the new image was started. **Basis:** `script:backend did not become ready — check: docker compose -p kamra logs` | Database not healthy (DOCKER-001); crash on start | `dc logs backend db` | [R16](../support/PRODUCTION_RUNBOOK.md#r16-update-failed) |
| UPDATE-004 | An update ran with no pre-update backup and no tagged previous image, so there is no rollback point. **Basis:** `designed` — `install.sh update` has no pre-flight; detection would be a pre-flight gate | The guard does not exist | Take the backup and `docker tag` the image before updating | [manual §12](../support/TECHNICIAN_MANUAL.md#12-update) |
| UPDATE-005 | After an update the health screen has `failed` rows, or the scheduler is not executing. **Basis:** `designed` — `install.sh update` runs no health gate afterward | Anything | Run the checks in [manual §12](../support/TECHNICIAN_MANUAL.md#12-update) "After it" | [R16](../support/PRODUCTION_RUNBOOK.md#r16-update-failed) |

### MIGRATION

| Code | Meaning | Likely cause | First action | Runbook |
| --- | --- | --- | --- | --- |
| MIGRATION-001 | `bench migrate` raised an error in a patch. **Basis:** `doc` — the traceback in `migrate` output | Transient (disk, lock) or a defect in the patch | Back up the half-migrated state before anything else | [R17](../support/PRODUCTION_RUNBOOK.md#r17-migration-failed) |
| MIGRATION-002 | Patches listed in `kamra/patches.txt` are absent from `Patch Log` (code newer than database). **Basis:** `designed` — no command reports it; compare as in [manual §14](../support/TECHNICIAN_MANUAL.md#14-migrate) | `migrate` not run after an update or restore of an older backup; or MIGRATION-001 | Run `migrate` after a backup | [R17](../support/PRODUCTION_RUNBOOK.md#r17-migration-failed) |

### DOCKER

| Code | Meaning | Likely cause | First action | Runbook |
| --- | --- | --- | --- | --- |
| DOCKER-001 | `docker compose up -d` aborts: `dependency failed to start: container db is unhealthy`. **Basis:** `live` | MariaDB still booting; healthcheck `start_period` too short (upstream's is 5 s; this repository's compose file uses 180 s) | Wait for `db` to report healthy, run `up -d` again | [R04](../support/PRODUCTION_RUNBOOK.md#r04-docker-compose-up-fails-with-db-unhealthy) |
| DOCKER-002 | `configurator` is not `Exited (0)`, so nothing else starts. **Basis:** `doc` (`deploy/linux/README.md`) | Usually the database password | `dc logs configurator` | [R01](../support/PRODUCTION_RUNBOOK.md#r01-application-down) |
| DOCKER-003 | Every container restarts with `exec ...entrypoint.sh: no such file or directory`. **Basis:** `doc` (`deploy/linux/README.md`) | Image built from a Windows checkout with CRLF line endings | Re-clone with `core.autocrlf=false`; rebuild | [manual §4.3](../support/TECHNICIAN_MANUAL.md#43-compose-by-hand-layout-b) |
| DOCKER-004 | A required service container is not running. **Basis:** `doc` — visible with `docker compose ps`; no application signal for container state | Crash, OOM kill, stopped by hand | `dc ps -a`; `dc logs <service>` | [R01](../support/PRODUCTION_RUNBOOK.md#r01-application-down) |
| DOCKER-005 | The Docker daemon is not running or not enabled at boot (Windows: Docker Desktop not running or nobody logged in). **Basis:** `doc` (`BACKUP.md` §6) | Host reboot; user-session application | `systemctl is-active docker`; start Docker Desktop | [R01](../support/PRODUCTION_RUNBOOK.md#r01-application-down) |

### STORAGE

| Code | Meaning | Likely cause | First action | Runbook |
| --- | --- | --- | --- | --- |
| STORAGE-001 | Free disk below 5 GB or 10%. **Basis:** `health:disk` (`attention`) | Logs, build cache, backups, real growth | `docker system df` | [R09](../support/PRODUCTION_RUNBOOK.md#r09-disk-full) |
| STORAGE-002 | Free disk below 2 GB or 5%. **Basis:** `health:disk` (`failed`) | As above; writes are about to fail | Free space safely, in the runbook's order | [R09](../support/PRODUCTION_RUNBOOK.md#r09-disk-full) |
| STORAGE-003 | Container logs are growing without limit. **Basis:** `designed` — the compose file sets no `logging:` options (read from the file); detection is the size of each container's `LogPath`; `health.py` measures only the site path and cannot see it | Docker default `json-file` driver with no rotation | Measure log sizes; configure rotation | [R09](../support/PRODUCTION_RUNBOOK.md#r09-disk-full) |

### CONFIGURATION

| Code | Meaning | Likely cause | First action | Runbook |
| --- | --- | --- | --- | --- |
| CONFIGURATION-001 | Every URL returns 404 against a site that exists. **Basis:** `doc` (`deploy/linux/README.md`) | `FRAPPE_SITE_NAME_HEADER` does not equal the site name | Correct the env file; `dc up -d` | [R01](../support/PRODUCTION_RUNBOOK.md#r01-application-down) |
| CONFIGURATION-002 | `DB_PASSWORD is required` on `up`. **Basis:** `message` from the compose file's `${DB_PASSWORD:?...}` | No `.env`, or the variable is empty | Create the env file; on an existing install copy the original | [R01](../support/PRODUCTION_RUNBOOK.md#r01-application-down) |
| CONFIGURATION-003 | Property time zone differs from the site time zone. **Basis:** `health:timezone` (`attention`) | Set inconsistently in setup | Align them in Admin → Settings → Property. **If the site zone was changed after the site was created, also check APP-002** | [R03](../support/PRODUCTION_RUNBOOK.md#r03-scheduler-not-running) |
| CONFIGURATION-004 | A required app (`frappe`, `kamra`) is missing. **Basis:** `health:apps` (`failed`) | Broken install or image | Rebuild the image | [R16](../support/PRODUCTION_RUNBOOK.md#r16-update-failed) |
| CONFIGURATION-005 | Frappe older than v16. **Basis:** `health:frappe` (`attention`) | Wrong base image | Rebuild from the correct `FRAPPE_BRANCH` (`version-16`) | [R16](../support/PRODUCTION_RUNBOOK.md#r16-update-failed) |
| CONFIGURATION-006 | The install was built from upstream Kamra instead of the Algeria distribution (Algeria missing from the setup country list). **Basis:** `doc` (`deploy/linux/README.md`) | `KAMRA_GIT_URL` / `KAMRA_BRANCH` not overridden | Rebuild with the correct `apps.json` | [manual §4.1](../support/TECHNICIAN_MANUAL.md#41-linux-server-recommended-for-a-hotel-taking-live-bookings) |

### INTEGRATION

| Code | Meaning | Likely cause | First action | Runbook |
| --- | --- | --- | --- | --- |
| INTEGRATION-001 | Outgoing email is not being sent. **Basis:** `doc` — `Email Queue` rows in `Not Sent`/`Error` ([`docs/email-setup.md`](../email-setup.md)) | Scheduler/worker down; SMTP credentials or port; no default outgoing account | Count `Email Queue` by status | [R07](../support/PRODUCTION_RUNBOOK.md#r07-email-not-sending) |
| INTEGRATION-002 | Pushing availability and rates to an OTA failed for one connection. **Basis:** `log:ARI push failed: <connection>`; also `enqueue_property_push failed` | Provider down; expired credentials; scheduler stalled | Read the `Error Log` title; check that connection's credentials | [R14](../support/PRODUCTION_RUNBOOK.md#r14-reservation-issue) |
| INTEGRATION-003 | E-invoicing submission failed for a document. **Basis:** `log:e-invoicing: <name> failed` | The tax authority's endpoint, credentials, or the document | Escalate with the sanitised traceback | none yet |
| INTEGRATION-004 | An outbound WhatsApp message failed. **Basis:** `log:Banquet: WhatsApp alert to staff failed`, `banquet send_quotation whatsapp` | Provider credentials or template | Check WhatsApp configuration | none yet |
| INTEGRATION-005 | Pre-arrival self check-in outreach failed for a reservation. **Basis:** `log:Pre-arrival outreach failed for <reservation>` | Email/WhatsApp channel down | Check the channel; see INTEGRATION-001 | none yet |

---

## 4. Mapping of existing signals to codes

The table `health.py` was built from. All nineteen rows are implemented.

One deliberate departure. This table reads `health:timezone | attention |
CONFIGURATION-003`, but that check has **two** `attention` branches: the
property zone differing from the site zone, and no Property existing yet.
CONFIGURATION-003 names the first condition only, so the second carries no
code — rule 4, one condition one code. The table was coarser than the code it
described; where the two disagree, the rule decides.

| Existing signal | Level | Code |
| --- | --- | --- |
| `health:version` | `attention` (behind) | UPDATE-001 |
| `health:version` | `info` (GitHub unreachable) | NETWORK-003 |
| `health:frappe` | `attention` | CONFIGURATION-005 |
| `health:apps` | `failed` | CONFIGURATION-004 |
| `health:database` | `failed` | DB-001 |
| `health:redis` | `failed` | DB-003 |
| `health:workers` | `failed` (no worker) | APP-005 |
| `health:workers` | `failed` (broker unreachable) | DB-004 |
| `health:workers` | `attention` (queue over 1000) | APP-006 |
| `health:scheduler` | `attention` (off) | APP-001 |
| `health:scheduler` | `failed` (future-stamped) | APP-002 |
| `health:scheduler` | `attention` (never executed) | APP-003 |
| `health:scheduler` | `attention` / `failed` (stale) | APP-004 |
| `health:backup` | `attention` (none) | BACKUP-001 |
| `health:backup` | `attention` (older than 48 h) | BACKUP-002 |
| `health:backup` | `info` (unreadable) | BACKUP-003 |
| `health:disk` | `attention` | STORAGE-001 |
| `health:disk` | `failed` | STORAGE-002 |
| `health:timezone` | `attention` | CONFIGURATION-003 |
| `health:entitlement` | `attention` (expiring) | LICENSE-001 |
| `health:entitlement` | `attention` (in grace) | LICENSE-002 |
| `health:entitlement` | `attention` (lapsed) | LICENSE-003 |
| `health:entitlement` | `info` (unparseable record) | LICENSE-004 |

---

## 5. Adding a code

1. The condition must satisfy rule 5 (Section 1): a signal, an observed
   failure, or a designed detection method — stated, not implied.
2. Take the next number in the category. Do not fill gaps and do not skip.
3. Write all five columns. If there is no runbook yet, write `none yet`.
4. Add the runbook entry in the same change, or say in the entry that it is
   missing.
5. If the signal is code, the code is the stable identifier and the English text
   is free to change; add the translation keys for French and Arabic against the
   code, not against the sentence.

---

## What this does not cover / has not been tested

- **40 of the 67 allocated codes are still not emitted by anything.** Their
  basis is `doc`, `designed` or `live`: the condition is real, the signal is
  not built. A technician will not see those on a screen.
- **Most of the 26 that are emitted were verified by reading the branch, not
  by triggering it.** The exceptions are APP-001 and CONFIGURATION-003, which
  were induced on the live install inside a rolled-back transaction, and all
  four LICENSE codes, which were driven through every state. The rest are
  single-line keyword additions to branches that were themselves already in
  use, which is weak evidence next to a reproduction.
- **Prefixing the `Error Log` titles splits their history.** The support
  bundle groups errors by title over a seven-day window, so for seven days
  after an update a site can show both `Night audit failed: X` and
  `[APP-007] Night audit failed: X` as separate rows.
- **Every `Basis` was read from the source, not triggered.** The `Error Log`
  titles and message strings were found by searching the repository; none was
  reproduced against a running site, and the exact wording in a production log
  may differ if the source changed after this was written.
- **The list is limited to what a single install and a read of the repository
  show.** Frappe, MariaDB, Redis, nginx, Docker and the OTA/e-invoicing providers
  have many failure modes this does not name. Absence of a code does not mean the
  condition cannot occur; it means nothing here establishes it.
- **LICENSE has four codes and no `failed` status**, because an entitlement
  that has lapsed breaks nothing - `kamra/entitlement.py` is a record, not a
  gate. There is no "signature invalid" or "activation failed" code because
  there is no signature and no activation.
- **Several codes have no runbook yet** (SECURITY-001 to -004, INTEGRATION-003 to
  -005). That gap is deliberate and visible.
- **`designed` codes (APP-008, APP-011, NETWORK-002, SECURITY-005, BACKUP-005,
  UPDATE-004, UPDATE-005, MIGRATION-002, STORAGE-003) have no detection built.**
  The method stated is a proposal and has not been prototyped.
- **Severity, alert routing and customer-facing wording are not defined.** Rule 3
  separates severity from the code; assigning it is future work.
- **Translations** (French, Arabic) are not provided.
- English only.
