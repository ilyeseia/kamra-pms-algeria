# ZIRI PMS on Windows 10 — quick reference

Full runbook: [`docs/algeria/INSTALLATION.md`](../../docs/algeria/INSTALLATION.md).
This file is the short version for someone standing at the machine.

## Read this first

**Frappe does not run on Windows.** There is no Windows build, and the
project's own installer is a bash script that calls `systemctl` and `apt-get`.
`Install-Kamra.ps1` does not change that. What it does is verify Windows can
host Linux containers, then drive the Linux installer inside WSL2, where
Docker Desktop actually runs the stack.

For a hotel that takes live bookings, **a Linux VPS is the better home** and
the Windows machine is just a browser pointed at it. Use this path for a demo
on a laptop, a pilot, or a single-site install the operator owns knowingly.

## Prerequisites

- Windows 10 64-bit, version 2004 (build 19041) or later
- Hardware virtualisation enabled in BIOS/UEFI
- WSL2 with a distribution installed — `wsl --install -d Ubuntu`
- Docker Desktop, WSL2 backend, **integration enabled for that distribution**
  (Settings → Resources → WSL integration) and reported *Running*
- 8 GB RAM (16 GB comfortable), 40 GB free disk
- First install takes **20–45 minutes**: the image is built locally, not pulled

## Use it

Always run the preflight first. It changes nothing.

```powershell
.\Install-Kamra.ps1 -Preflight
```

Trial — disposable demo with sample data:

```powershell
.\Install-Kamra.ps1 -Mode Trial
```

Production — live site, no sample data, no demo accounts:

```powershell
.\Install-Kamra.ps1 -Mode Production -SiteName pms.yourhotel.dz -AdminEmail gm@yourhotel.dz
```

If PowerShell refuses to run the file, it is unsigned; run it for this session
only rather than weakening the machine's policy permanently:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-Kamra.ps1 -Preflight
```

## Profiles

| | Trial | Production |
| --- | --- | --- |
| Site name | `kamra.localhost` (default) | required, must be a real domain |
| Sample hotel data | seeded | none |
| `kamra_demo_mode` | on | off |
| Demo accounts | none created by this script | **never** — see below |
| Admin password | prompted by the Linux installer | prompted by the Linux installer |
| Demo reset job | works (`.localhost` counts as a playground) | refuses, by design |

## The password

This script never asks for, stores, or forwards the admin password. It exports
`SITE_NAME` and `ADMIN_EMAIL` only; `install.sh`'s `prompt()` skips variables
that are already set, so the Linux installer asks for the password itself and
reads it straight from the console. It never enters a PowerShell variable, the
environment block, a transcript, or your shell history. Minimum 10 characters,
no default.

## Never run this on a production site

`kamra/scripts/seed_users.py` creates six accounts whose passwords are
published in the repository and compiled into the shipped JavaScript bundle.
`demo_mode` only hides the demo login buttons client-side — the credentials are
in the bundle either way. The protection is that **the accounts must not
exist**. Production mode never creates them; do not add them by hand.

## Both versions matter in a support request

```
ZIRI PMS - Algeria Distribution 1.0.0
on Kamra core 2.6.5
```

"Kamra 2.6.5" alone does not say whether the Algeria pack is installed. See
[`docs/algeria/VERSIONING.md`](../../docs/algeria/VERSIONING.md).

## Afterwards

| | |
| --- | --- |
| Open | `http://localhost:8080/kamra` |
| Stack directory | `/opt/kamra` inside WSL — `wsl -d Ubuntu` |
| Secrets | `/opt/kamra/kamra.env`, mode 600, holds the database password |
| Update | `sudo /opt/kamra/install.sh update` |
| Backups | [`docs/algeria/BACKUP.md`](../../docs/algeria/BACKUP.md) — and test a restore |
| Troubleshooting | [`../TROUBLESHOOTING.md`](../TROUBLESHOOTING.md) |

Verify the Algeria pack is actually live: open `/kamra/setup`, confirm
**Algeria** appears in the country list, then that the currency reads **DZD**
and the tax label reads **TVA**. If Algeria is missing, the install built from
upstream instead of this distribution — check `KAMRA_GIT_URL` and
`KAMRA_BRANCH` in `/opt/kamra/apps.json`.

## Not proven yet

Migrations `v36` (fixed per-person *taxe de séjour*) and `v37` (RC/NIS/AI
fields) had never run against a database before this installer existed. A
completed install means they have just run for the first time. Confirm the site
loads and that a reservation saves before trusting it with a real hotel, and
read the honest gaps section in
[`docs/algeria/INSTALLATION.md`](../../docs/algeria/INSTALLATION.md).
