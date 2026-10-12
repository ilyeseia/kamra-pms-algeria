# Release notes — ZIRI PMS distribution

What a release changes, what it requires of whoever applies it, and what
rollback means. The version number cannot carry any of that; this file is the
"release metadata the version number cannot carry" that
[`UPDATES.md`](UPDATES.md) §5 specifies, written by hand until the manifest it
describes exists.

GitHub's auto-generated notes list commit titles. They are useful and they do
not say whether a migration rewrites a row, so they are not a substitute for
this.

Newest first. The fields are §5's: `severity`, `migration.class`,
`migration.patches_added` (computed, not claimed), `requires_operator_action`.

---

## ziri-v1.1.0-rc.1

**Not a final release.** `-rc` because no `bench migrate` has run from 1.0.0
to here, anywhere — see *Why this is a candidate* below. The release workflow
marks it a prerelease, so no existing 1.0.0 install is told an update is
available.

| | |
| --- | --- |
| **severity** | `feature` |
| **migration.class** | **M2** |
| **migration.patches_added** | `kamra.patches.v38.move_spa_route_to_ziri` (one; diffed against `ziri-v1.0.0`) |
| **migration.rollback_mode** | `app-only`, plus one command — see *Rollback* |
| **requires_operator_action** | None to apply. Two things to know, below. |
| Kamra core | 2.6.5, unchanged |

### Why M2 and not M1

M1 is "additive: new columns/DocTypes, plus backfills that write **only blank
values**". `v38` writes `Website Settings.home_page` from `kamra` to `ziri` on
every existing site — a non-blank value over a non-blank one. That is not M1,
and §5's rule for an uncertain class is to take the more cautious reading.

It is narrower than M2 sounds: the patch moves **only** the exact value this
product wrote itself, so a hotel that pointed its home page at its own
marketing site keeps it. `install.py` promises in writing never to override a
custom home page and a patch is not a licence to break that quietly.

The new DocType (**Support Access Grant**) is additive and M1 on its own.

### What changed

**Public route moved from `/kamra` to `/ziri`.** Old links keep working:
`hooks.py` redirects `/kamra` and `/kamra/<anything>`, because guests were
sent self check-in links of that shape and those messages are already in
their hands. `v38` fixes the one thing a redirect cannot — the bare hostname,
which is the URL a hotel gives new staff.

**A guest-facing agent**, on a surface a stranger may use, with its own
channel-neutral brain and a tool surface limited to the guest-safe API.

**The agent can no longer change hotel data on its own.** Thirty mutating
tools now require a confirmation redeemed against a user turn the model did
not author.

**The hotel's phone can be answered by ZIRI**, over jambonz — MIT-licensed
and self-hostable, chosen after HeyKoala's chatbot was audited rather than
replaced blind.

**Temporary support access.** A technician can be let in, for a bounded
period, with the hotel's recorded permission. The clock is re-checked on
every call, so an expired grant authorises nothing even with the role still
attached — the difference between a support door and a backdoor.

**A resumable first-run wizard.** Progress survives a closed tab, and
nothing that looks like a credential is ever written to `site_config.json`.

**An optional daily entitlement fetch** (`kamra_entitlement_url`, off by
default) and **optional weekly telemetry** (two separate settings, off by
default). Neither gates anything; neither can. See
[`../algeria/LICENSING.md`](../algeria/LICENSING.md) §5a and §5b, both written
as tables to show a hotelier.

**Security scanning in CI** — gitleaks over the full history and failing,
dependency advisories reported and gated on what is actually shipped.

### Why this is a candidate

[`../algeria/VERSIONING.md`](../algeria/VERSIONING.md) says a tag is a claim
that the thing works, and not to drop the `-rc` suffix until at least one
`bench migrate` has run against a real database. For 1.0.0 that had happened.
For this it has not:

- No workflow in this repository runs `bench migrate`. CI creates a fresh
  site and installs the app, which exercises a **new** install and never the
  **upgrade** path. `v38` has therefore never executed anywhere.
- No server has been updated to this code.

Everything else is verified: CI is green across the eval harness, the banquet
suite, the agent tool-gate, guest-agent, confirmation-gate, jambonz, support
access, setup state, entitlement sync and telemetry modules, plus the
front-desk journey and the fresh-install checks.

**It becomes `ziri-v1.1.0`** when `install.sh update` has carried a real site
from 1.0.0 to here and that site passed its own health checks afterwards.
Nothing else is outstanding.

### Rollback

Putting the previous image back is enough for the application, and leaves one
thing wrong: `home_page` stays `ziri` while the reverted code serves the page
at `kamra`, so deep links work and the bare hostname does not. Fix it in one
command rather than restoring a backup:

```bash
<COMPOSE> exec -T backend bench --site "$SITE" set-value "Website Settings" "Website Settings" home_page kamra
```

`install.sh update` tags the outgoing image `kamra:rollback-<version>` before
it builds, so the image to go back to already has a name.

### Applying it

```bash
sudo KAMRA_BRANCH=ziri-v1.1.0-rc.1 /opt/kamra/install.sh update
```

The pre-flight gate will refuse unless there is ≥12 GB free where Docker
stores images, the backend and database are answering, and a backup exists
that is less than 24 hours old. That last one is the check the gate exists
for: `migrate` is the only part of an update that putting the old image back
cannot undo.

---

## ziri-v1.0.0

Released 2026-10-04, commit `f652dd2`. The first final release of the
distribution: the Algeria pack, the wilayas and communes, DZD, the
`/kamra`-era SPA, and the audit, monitoring, support-bundle and entitlement
layers. `bench migrate` had run against a real database repeatedly, and a
backup set from that install had been restored into a clean MariaDB and
verified table by table, before the `-rc` suffix was dropped.
