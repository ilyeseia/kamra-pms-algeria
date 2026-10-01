# Disaster recovery - design

**Status: design. No scenario below has been rehearsed.** The stack has run on
one machine, Docker Desktop over WSL2, and never on the Linux server it is
written for ([`PRODUCTIZATION_AUDIT.md`](PRODUCTIZATION_AUDIT.md), "What this
document does not establish"). Recovery times in this file are **planning
targets derived from stated assumptions**, not measurements, and say so where
they appear.

Read with [`BACKUP.md`](BACKUP.md) (what exists to recover from) and
[`RESTORE.md`](RESTORE.md) (how, and how to know the copy is good). Procedures
are referenced, not repeated. `DC` is your install's compose invocation
(`../algeria/BACKUP.md` section 1). Database: **MariaDB 11.8**. Services:
`backend`, `frontend`, `db`, `redis-cache`, `redis-queue`, `queue-short`,
`queue-long`, `scheduler`, `websocket`, `configurator`. Volumes: `sites`,
`db-data`, `redis-queue-data`.

---

## 1. How to read this

**Detection is weaker than the scenarios assume.** The audit found no
monitoring, metrics endpoint or alerting (gaps for brief sections 30 and 55).
What exists is the `/kamra/health` page (`kamra/health.py`). As read today it
also carries Redis, worker and backup-age checks that the audit's list did not
mention. Two limits apply to all of them:

- they run **inside the application**, so they cannot report that the
  application, the container or the host is down;
- they are only seen by someone who opens the page. Nothing pages anyone.

Its disk check is `shutil.disk_usage` - **free space, not disk health**. Its
backup check is age of the newest dump in the site's own backup directory,
48 h threshold. In practice, in every scenario below, the front desk finds out
before the software tells anyone. "Detection" lists what would show it and, where
that is a person, says so.

**The first hour, in any scenario:**

1. **Do not make it worse.** Stop things that write or send: `DC stop frontend
   scheduler queue-short queue-long websocket`. Do not retry the thing that
   just failed. Do not `down -v`, `prune`, `fsck` in place, or "reinstall".
2. **Preserve what remains** before any repair: a cold copy of the volumes
   (`RESTORE.md` section 4.1) when the data may be the only copy.
3. **Name the class** (section 2): is the host and its disk alive, is the
   building alive. That decides which copy you can reach.
4. **Run the desk on paper.** Arrivals, in-house list, rate and room status
   from the last printout. Nothing in this design produces that printout and
   it has not been checked whether the product can (listed under "not
   covered" below). Without it, RTO is felt as turned-away guests.
5. **Fence the scheduler** on any copy you bring up (`RESTORE.md` section 1,
   rule 1): the restored site will push availability to OTAs and message guests.

---

## 2. RPO and RTO

Definitions. **RPO**: the most recent work you can lose, measured back from the
moment of failure. **RTO**: from the decision to recover until the desk can
use the system again.

### 2.1 RPO, derived

Backup cadence (`BACKUP.md` section 4.1): a **full** set (database, files,
config) at 05:30; **intra-day database-only** sets at 01:00, 09:00, 13:00,
17:00, 21:00. The longest gap between consecutive database sets is
**G = 4.5 h** (01:00 to 05:30). Without the intra-day sets, G = 24 h.

For a copy that receives each set `S` after the dump starts, and a dump that
takes `D`, worst-case loss is **G + D + S**: the failure lands just before the
next set reaches that copy, so the newest available one is a full gap old plus
its own dump and transfer time. `D` and `S` have not been measured. The
figures below assume `D + S <= 30 minutes` for the database sets and say
"approximately" for that reason: **if the assumption is false, the RPO is
wrong by the difference.**

Which copy you recover from depends on what survived:

| Class | What failed | Copy you can reach |
| --- | --- | --- |
| 1 | Software, data or a person; host and disk survive | host staging / second disk |
| 2 | Host or its disks lost; building survives | NAS / external disk / remote |
| 3 | Everything online lost: building, or ransomware that reached every online copy | only the off-site or unplugged copy |

| Profile | Class 1 | Class 2 | Class 3 | Files (ID scans) |
| --- | --- | --- | --- | --- |
| **A. One hotel, one server - recommended** (full + intra-day; copy to NAS or external disk after every set; automatic remote copy when a link exists) | G + D = approx **4.5 h** | G + D + S_nas = approx **5 h** | remote copy: approx **5 h**, **only while the link is up**; otherwise the age of the last shipped set, unbounded | **24 h** + D + S (files are in full sets only) |
| **A2. One hotel - baseline** (daily full only) | approx **24 h** | approx **24.5 h** | as above, with G = 24 h | 24 h + D + S |
| **A3. One hotel - local-only** (daily to a second disk; weekly full to an external disk that leaves the building) | approx **4.5 h** or 24 h per cadence chosen | second disk survives a failed system disk but **not** a power surge or fire that takes the whole server: treat as class 3 | up to **7 days** (the swap interval) + D | as chosen |
| **B. Multi-property** | same as A, per site | same | same | same - see below |

What those numbers do and do not say:

- **They hold only while sets are produced, shipped and verified.** Each is
  the best case of a working pipeline. Remote RPO degrades for as long as the
  link is down and reaches "unbounded" if nobody notices. The design's answer
  is to make the age of the newest *shipped* set visible (`BACKUP.md` section 8),
  not to promise it cannot happen.
- **They are for unverified sets.** A set that has never been restored may be
  unusable; the RPO then is the age of the newest *verified* one
  (`RESTORE.md` section 5). Until Level 2 has passed from an off-site copy, treat the
  figures as `UNVERIFIED`.
- **Files have a longer RPO than data.** A guest ID scan uploaded at 10:00 is
  not in any backup until 05:30 the next day. For a person still in the house
  that is recoverable by scanning again; for one who has left, it is not.
- **Do not take 4.5 h from "5 times a day".** It is the longest *gap*, which
  includes the overnight stretch.

Multi-property, restated honestly:

- **B1, several sites on one server:** backup unit is the site; `D` and `S`
  sum across sites and must still finish inside each gap. RPO per site equals A.
  One host is one failure for every property; one `down -v` in the wrong
  directory removes all.
- **B2, several properties inside one site:** restore granularity is the whole
  site (`RESTORE.md` section 4.7). To recover one property's mistake you either
  roll all properties back to the same RPO, or extract records by hand.
- **B3, one stack per property:** each is profile A; independent failures. Give
  each its own backup repository and password. An integrator holding one shared
  password across unrelated owners makes one leak everyone's.

### 2.2 RTO, derived

RTO is a sum, and most of its terms have not been measured:

`RTO = T_hw + T_stack + T_fetch + T_restore + T_migrate + T_verify`

| Term | What it is | What is actually known |
| --- | --- | --- |
| `T_hw` | Replacement host | 0 for a same-host problem. With a spare on site: setup time, unknown. With none: procurement - **not something this design controls** |
| `T_stack` | Image and stack up | With an off-host image archive: `docker load` + `docker compose up -d`, unmeasured. **Without**: the build, documented as **20-45 minutes** (`deploy/linux/README.md`) and dependent on internet access |
| `T_fetch` | Set to the new host | Negligible from a local disk or NAS. From a remote or cloud copy over a poor link it can dominate: the files archive of ID scans is unmeasured and may be gigabytes |
| `T_restore` | `bench restore` | Unmeasured; scales with database and files size |
| `T_migrate` | `bench migrate` | Unmeasured; the first run of `v36`/`v37` on real data is unknown |
| `T_verify` | Manual checklist (`algeria/BACKUP.md` section 4) | Human step; planning figure 15-30 minutes |

Planning targets, **not commitments**:

| Class | Condition | Target | Why that, and what would invalidate it |
| --- | --- | --- | --- |
| 1 | Host alive, local set at hand, image present | **2 h** | `T_hw = T_stack = T_fetch = 0`; assumes `T_restore + T_migrate <= ~1 h`. Wrong if the first Level 2 run measures more - then the number changes, not the measurement |
| 2 | Spare machine on site; image archive and a verified set on a local/NAS/external copy | **4 h** | Adds `T_hw` and `T_stack` in minutes. Wrong if `docker load` or the fetch is slow |
| 2 | Same, **no image archive** | **no target** | Adds a 20-45 min build **and** needs a working internet link at the worst moment. For a hotel with a poor link, this is the case that fails |
| 3 | Site loss or all-online-copies loss | **no target** | Bounded by hardware procurement, bandwidth to fetch, and (ransomware) forensics. The honest statement is "days" and nothing here shortens it |

Multi-property: server-wide recovery builds the stack once, then restores
sites one after another, so
`RTO(site k) = T_hw + T_stack + sum over sites 1..k of (T_fetch + T_restore + T_migrate + T_verify)`.
It grows with the number of sites, and **the order is a business decision made
in advance**, not at 2am. Parallel restore into one MariaDB is not recommended
here because it is unmeasured.

These become commitments only after a **host-loss drill** (`RESTORE.md`
section 5) has produced real values for the terms above. Until then, quoting a
number to a customer as an SLA is quoting something this design has not shown
it can deliver.

---

## 3. Scenarios

Each: how you would know, the first action, the recovery path, what is lost.
Class numbers refer to section 2.

### 3.1 Server failure

The host will not boot or has died; its disks may be fine.

- **Detection.** The desk cannot reach the PMS. No monitor sees it.
- **Immediate.** Rule out cheap causes before declaring hardware dead: the
  `configurator` not `Exited (0)`, `db` not healthy, the nginx stale-IP 502
  (`deploy/linux/README.md`, troubleshooting table). If the host is truly
  dead, do not power-cycle it repeatedly.
- **Recovery.** If the disks read in another Linux machine, the volumes can be
  copied cold from Docker's volume directory (`db-data`, `sites`) and mounted
  into a fresh stack - potentially **no data loss**, since MariaDB's crash
  recovery handles an unclean stop **[not rehearsed]**. If not: provision and
  restore, `RESTORE.md` section 4.5.
- **Lost.** Salvaged disk: nothing committed. Otherwise: class 2 RPO (approx 5 h
  in profile A), files up to 24 h, queued jobs in `redis-queue-data`.

### 3.2 Disk failure

- **Detection.** I/O errors or a read-only filesystem in `DC logs db`;
  SMART warnings on the host; `db` restart loop. The health page does **not**
  detect a failing disk (free space only).
- **Immediate.** `DC stop`; do not run repairs in place. Image the disk with a
  tool that tolerates read errors if the data matters. The system disk and a
  directory on it are the same disk: if `/opt/kamra/backups` was there, those
  sets are gone too (`BACKUP.md` section 5, "Local disk").
- **Recovery.** New disk, then as 3.1: install, fetch a set from a copy not on
  the failed disk, restore.
- **Lost.** Everything since the newest set on a surviving device. A "second
  disk" in the same chassis may share a power supply and die with it.

### 3.3 Database corruption

Physical (the engine will not start) or logical (a bug or script wrote bad
data; the engine is happy).

- **Detection.** Physical: `db` unhealthy or restarting (`healthcheck.sh
  --connect --innodb_initialized`, per compose), InnoDB errors in `DC logs db`,
  500s from the app, the health page's database check red. Logical: only a
  person - a wrong total, missing reservations. The software will not notice.
- **Immediate.** Stop writers and the OTA push (section 1 step 1). **Cold-copy
  `db-data` before any repair.** Do not experiment with
  `innodb_force_recovery` on the only copy.
- **Recovery.** Physical: new `db-data`, restore the latest verified set
  (`RESTORE.md` section 4.2). Logical: find when it began; restore the last
  verified set before that, or extract the good records into a side site
  (`RESTORE.md` section 4.7). Every set taken after the corruption began
  contains it - the reason for keeping 7 dailies and for the watermark check.
- **Lost.** Since the chosen set (class 1, approx 4.5 h at best). For logical
  corruption discovered days later, days of work, because the clean set is old.
  Silent corruption that predates the oldest retained set is unrecoverable
  from backup.

### 3.4 Application corruption

The database is fine; the image, containers or the `sites` volume are not.

- **Detection.** Containers in a restart loop; `exec ...entrypoint.sh: no such
  file or directory` (the CRLF-image failure in `deploy/linux/README.md`);
  404/502s; `configurator` not `Exited (0)`.
- **Immediate.** Leave `db-data` alone. `DC logs configurator backend`.
- **Recovery.** Recreate containers from a known-good image
  (`kamra:pre-<version>` if tagged, the image archive, or a rebuild) with
  `DC up -d --force-recreate`, then restart `frontend` to re-resolve upstreams.
  If the `sites` volume is damaged: put back `site_config.json` from escrow
  (`BACKUP.md` section 6.2) and files from the newest full set. No database
  restore.
- **Lost.** No database content. Uploads since the last full set if the files
  were damaged (up to 24 h of scans).

### 3.5 Accidental deletion

A person deletes reservations, a guest, or runs a bulk delete.

- **Detection.** A person reports it. The audit found no protected audit log
  for deletions (brief section 29); Frappe's own deletion record is the only
  trail.
- **Immediate.** Stop the person retrying. Write down what and when. Do not
  restore anything yet.
- **Recovery.** Frappe's Deleted Document restore first **[confirm it covers
  the ZIRI doctypes]**; else extract from a set into a side site
  (`RESTORE.md` section 4.7). Roll the whole site back only if the deletion was
  massive, and accept it discards everyone else's work since the set.
- **Lost.** Nothing if the record is recovered. Otherwise whatever was edited
  between the set and the deletion. **Not** a loss: guests erased by the
  retention job (`kamra.privacy.apply_retention`) or scans discarded at
  checkout are deletions by policy; restoring them undoes a Law 18-07 duty.

### 3.6 Ransomware

- **Detection.** Renamed or unreadable files, a ransom note, `db` failing,
  `sites` unreadable. Exfiltration without encryption is not detectable with
  anything that exists.
- **Immediate.** Isolate from the network (cable out; do not trust the host's
  own firewall). Do not plug any backup disk or NAS into it, and unplug any
  that is. Do not log into other systems from it. Note which backup copies the
  host could reach: those are suspect. Paying is not a recovery path this
  design relies on.
- **Recovery.** Treat the host as lost and untrusted: a clean OS and stack
  (`RESTORE.md` section 4.5), never the old disk. Restore from a copy the host
  **could not modify** (`BACKUP.md` section 5 requirement) and prove it predates
  the intrusion - the intrusion date is unknown, so verify and step back
  through the dailies, weeklies and monthlies until a set verifies and is
  plausible. **Rotate every secret**: DB root, admin passwords, and the
  gateway, SMTP and channel-manager credentials at their providers; the
  attacker may have read `site_config.json` and the database. The backup
  repository password also lived on that host: treat the old repository as
  readable by the attacker, start a new one under a new password, and keep the
  old read-only. Whether to rotate Frappe's `encryption_key` itself is a
  procedure this repository does not define.
- **Lost.** Back to the newest clean copy the host could not touch: hours in
  profile A with a pulled or object-locked copy; up to a week in A3; **everything**
  if no such copy existed. Also **confidentiality**: assume guest ID scans and
  personal data were read. Whether and when Law 18-07 requires notification
  to the data-protection authority is a legal question not answered here;
  take advice immediately.

### 3.7 Power failure

- **Detection.** Obvious at the desk. On return of power the stack should come
  back by itself: services use `restart: unless-stopped`
  (`deploy/linux/docker-compose.yml`), and MariaDB runs InnoDB crash recovery
  on start. The `db` healthcheck allows 180 s (`start_period`), so give it time.
  On the Windows profile it will **not** come back until someone logs in:
  Docker Desktop is a user-session application (`../algeria/BACKUP.md`
  section 6).
- **Immediate.** Wait for `DC ps`: `db` healthy, `configurator` `Exited (0)`.
  Then check for the 502-on-every-page condition (stale upstream) and restart
  `frontend`. **Do not restore from backup** unless the database genuinely
  fails to start; crash recovery normally suffices **[not rehearsed here]**.
- **Recovery.** Check `/kamra/health`; look in `/kamra/activity` for a
  `Night Audit Run` gap (night audit is 03:00 and does not run while the stack
  is down); confirm a backup did not silently get skipped; spot-check the last
  transactions against paper.
- **Lost.** Normally nothing committed. The compose file does not override
  MariaDB's durability defaults, but a write cache on the disk or controller
  that does not honour flushes can lose acknowledged writes - not examined. If
  the database cannot start, this becomes 3.3. Missed scheduled jobs and a
  missed backup are the routine cost. The real control is a UPS with graceful
  shutdown, which is hardware this design neither includes nor verifies.

### 3.8 Network failure

LAN and WAN differ; this stack is self-hosted, so most of the PMS keeps working.

- **Detection.** LAN: desk machines cannot reach the server. WAN: the app
  works locally; the age of the newest *shipped* set grows; channel pushes
  fail.
- **Immediate.** LAN: switch, cabling, `DC ps` on the server. WAN: carry on
  locally. **OTA availability is stale** (`push_all_ari` runs hourly and will
  fail): for an outage of any length, close availability on the OTA extranets
  by hand to avoid overbooking.
- **Recovery.** Self-healing: the staging queue drains when the link returns,
  the push resumes. Confirm the shipped-set age recovers, and reconcile
  bookings that arrived during the outage. How the channel manager behaves
  after a gap was not verified.
- **Lost.** Nothing in the PMS. The remote RPO widens for the duration. A very
  long outage can also break certificate renewal, if the proxy relies on it.

### 3.9 Bad update

`install.sh update` rebuilds and runs `bench --site all migrate`. The audit
records that it has no pre-flight, no backup-before, no health gate after and
no rollback. Until that is built, every step below is manual.

- **Detection.** `migrate` exits non-zero; the health page fails; 502s or a
  broken UI after the rebuild; wrong totals the desk notices later.
- **Immediate.** Stop. Do not re-run the update. Do not let the desk resume
  writing to a half-migrated database.
- **The pair rule.** The database and the image roll back **together**.
  Migrations are not reversed; older code on a newer schema is unsupported
  (`RESTORE.md` section 4.6). Rolling back the image alone is not a rollback.
- **Before any update** (manual today): stop `frontend` so no one writes; take
  a full set and label it pre-update; `docker tag kamra:local kamra:pre-<version>`;
  optionally cold-archive `db-data` and `sites`. Then update. Then a health
  gate: `/kamra/health` and a Level 2 restore of the new pre-update set if time
  allows, before reopening.
- **Recovery.** Retag the saved image to `kamra:local`, restore the pre-update
  set into it (`RESTORE.md` section 4.2), verify, reopen.
- **Lost.** **Nothing** if the rollback happens before the desk resumes (writes
  were stopped before the backup). Everything since reopening otherwise. If the
  image was not tagged and there is no archive, "the old version" may not exist
  to roll back to (`BACKUP.md` section 4.4); the answer then is to fix forward.

### 3.10 Human error

`down -v`, `drop-site`, restoring the wrong set over the live site, editing
`DB_PASSWORD` against an existing `db-data` (access denied; `deploy/linux/README.md`),
or `docker system prune --volumes` while the stack is stopped, which removes
volumes no container is using - all three.

- **Detection.** Usually the operator, at once, because the command prints it.
  Sometimes a missing-data report hours later.
- **Immediate.** **Stop typing.** Do not start the stack again if volumes were
  recreated empty; starting writes new state on top of what you are trying to
  save. `docker volume ls` to see what survives. If a volume still exists with
  changed content, cold-copy it.
- **Recovery.** This is a host-intact restore: latest verified set, class 1
  (`RESTORE.md` section 4.2 / 4.5 without provisioning). Frappe's own backups in
  `sites/<site>/private/backups` died with the volume (`BACKUP.md` section 2);
  only copies in host staging or elsewhere survive. That is why staging is
  outside the volume.
- **Lost.** Since the newest set that survived. Prevention is cheap and not in
  the repository: no `-v` in any runbook, a production project name that
  differs from every test project, and no Docker rights for desk staff.

---

## What this does not cover / has not been tested

- **No scenario has been rehearsed.** Not one. The procedures are the
  composition of commands that are themselves unrun (`BACKUP.md`,
  `RESTORE.md`). The first host-loss drill will find faults in this document.
- **RTO is not measured, and for most terms nothing is known.** The only
  documented duration in the repository is the 20-45 minute image build. Every
  other term in section 2.2 is a placeholder, and the 2 h and 4 h targets are
  conditional guesses, labelled as such.
- **RPO assumes `D + S <= 30 minutes`** and a working pipeline. Both are
  unverified. If the nightly night audit (03:00) or the retention job (03:30)
  runs long, the 05:30 full set may overlap them; their duration has not been
  measured.
- **There is no monitoring or alerting** (audit). The detection lines describe
  what *would* show a failure to a person looking, not an alarm that exists.
- **Paper fallback.** Whether the product can produce a printable arrivals and
  in-house list on demand was not checked.
- **Power and storage hardware** (UPS, RAID, write-cache behaviour, SMART
  monitoring) is outside the repository and unexamined.
- **Salvaging Docker volumes from a dead host's disk** and **MariaDB crash
  recovery after an unclean stop** are plausible and not exercised here.
- **Channel-manager behaviour after an outage, and OTA availability recovery,**
  were not read or tested.
- **Ransomware forensics, key rotation** (including Frappe's `encryption_key`)
  **and breach-notification duties under Law 18-07** are not defined here.
- **Multi-property** analysis assumes the three shapes in section 2.1; which
  one a given customer runs, and whether the application supports several
  properties per site as the Property doctype suggests, was not established.
- **Only Docker Desktop over WSL2 has ever run this stack.** Linux-server
  behaviour (restart policy at boot, volume paths, mounts) is unseen.
