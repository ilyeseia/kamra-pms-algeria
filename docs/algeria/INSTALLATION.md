# Installation — Algeria Distribution

A vendor runbook for putting ZIRI PMS in front of
a client whose machine runs **Windows 10**. Two profiles are covered: a trial
(*نسخة تجريبية*) meant for demonstration, and a production install
(*نسخة احترافية*) meant to run a hotel.

This is written for the person doing the install, not for the hotel's staff.
It assumes you will be the one holding the phone when something goes wrong, so
it says where the sharp edges are instead of hiding them.

**Version covered:** Algeria Distribution **1.0.0**, on Kamra core **2.6.5**.
See [`VERSIONING.md`](VERSIONING.md) for what those two numbers mean and how
they move independently.

---

## 1. Read this before you install anything

### The seeded demo accounts must never exist on a production site

`kamra/scripts/seed_users.py:67-86` creates **six accounts with fixed,
published passwords**:

| Account | Role |
| --- | --- |
| `admin@kamra.local` | System Manager |
| `gm@kamra.local` | Hotel Admin |
| `frontdesk@kamra.local` | Front Desk |
| `revenue@kamra.local` | Revenue Manager + Front Desk |
| `finance@kamra.local` | Finance |
| `hk@kamra.local` | Housekeeping |

Those passwords are not secrets and were never meant to be. They are printed
in `docs-dev.md:43-50`, and `frontend/src/screens/Login.tsx:15-22` defines the
same six pairs as `DEMO_ACCOUNTS` — so **they are compiled into the JavaScript
bundle that every visitor downloads**, on every site, demo or not.

The first of them, `admin@kamra.local`, holds `System Manager`. Anyone who has
read the public repository can sign in as the full administrator of any site
where that account exists.

Two consequences that must be understood exactly:

- **`kamra_demo_mode` is not a protection.** `Login.tsx` hides the one-tap
  demo buttons when `public_api.site_info()` reports demo mode off
  (`kamra/public_api.py:207-216`), and that is *all* it does. The credentials
  are still in the bundle. Hiding a button does not invalidate a password.
- **The only real protection is that the accounts do not exist.** So a
  production install must never run `seed_users.py`, and must never run
  `seed_demo.py` either — `seed_demo.py:39` imports `ensure_users` from
  `seed_users` and calls it, so seeding demo data creates all six accounts as
  a side effect.

`Install-Kamra.ps1 -Mode Production` seeds nothing and does not call either
script. If you ever seed a client site by hand "just to have some data to show
them", you have handed out an administrator password. Do not.

If a site has already been seeded and must now go live, treat it as
compromised: delete the six users, rotate the `Administrator` password, and
audit `Access Log` and `Activity Log` for sign-ins you cannot account for.
Changing the six passwords is weaker than deleting the accounts, because the
next `install.sh update` does not re-run the seeder but a careless operator
might.

### The repository and branch must be overridden

`deploy/install.sh:40-42` defaults to:

```
KAMRA_GIT_URL=https://github.com/Kamra-PMS/kamra-pms
KAMRA_BRANCH=main
```

Those are **upstream Kamra**. The Algeria country pack, the French UI, the
fixed per-person *taxe de séjour*, the RC/NIS/AI invoice fields and the
`v36`/`v37` migrations are none of them on `main`. An install that takes the
defaults produces a working hotel PMS with **zero Algeria work in it** — and
because it works, nobody notices until the first invoice prints without a NIF
and prices in rupees.

For this distribution both values must be:

```
KAMRA_GIT_URL=https://github.com/ilyeseia/kamra-pms-algeria
KAMRA_BRANCH=feature/algeria-hospitality-platform
```

`Install-Kamra.ps1` carries these as its `-RepoUrl` and `-Branch` defaults, so
the normal path is to pass neither. If you are ever driving `install.sh`
directly — recovery, a VPS, a support session over SSH — you must export both
yourself. There is no prompt and no warning; the build simply fetches the
wrong code.

The check after install is in §7: if the setup wizard does not offer *Algeria*,
you built the wrong branch.

---

## 2. Where this can actually run on a Windows 10 machine

Frappe does not support Windows. That is not a hedge, it is observable in this
repository: `deploy/install.sh` is a bash script that calls `systemctl`,
`apt-get`, `fallocate`, `mkswap` and `/proc/meminfo`, and requires `docker` on
`PATH` (`deploy/install.sh:92-108`). Nothing anywhere in the repository
mentions Windows or WSL. There is no native Windows path and inventing one is
not on the table.

That leaves two honest options.

### Option A — WSL2 + Docker Desktop on the Windows machine

Windows 10 runs a real Linux kernel under WSL2; Docker Desktop with the WSL2
backend runs the same Linux containers `install.sh` expects. The installer runs
inside the WSL distribution and the hotel's staff use the site through a
browser on the same machine at `http://localhost:8080/kamra`.

This works, and it is the right answer for a demonstration on a laptop.

### Option B — Linux VPS, Windows machine is only a browser

The stack runs on a small Linux server — a VPS, or a box in the hotel's back
office — installed exactly the way `deploy/README.md` describes, with the
Algeria repository and branch overridden. The Windows 10 machine installs
nothing at all; the front desk opens a URL.

### Which to sell

| | A — WSL2 on Windows 10 | B — Linux VPS |
| --- | --- | --- |
| Supported platform | No. WSL2 is a workaround | Yes. What the installer targets |
| Survives a reboot unattended | Needs Docker Desktop set to start at login, and a logged-in user | Yes, `systemd` |
| Reachable from a second machine | Awkward: port forwarding, host firewall, machine must be awake | Yes, natively |
| TLS / a real hostname | Hard. `localhost` has no certificate | Standard: DNS + certbot |
| Backups off the machine | Manual, via Task Scheduler into WSL | Standard cron + off-site copy |
| If the machine dies | The hotel's data dies with it | The hotel's data is elsewhere |
| RAM cost | Stack **plus** Docker Desktop and Windows on top | Stack only |
| Good for | A demo, a trial, a sales laptop | A hotel that takes bookings |

**Recommendation: Option B for any paying production client.** A hotel that
cannot check a guest in because someone's laptop was shut down is not a
deployment, it is an incident waiting for a date. Option A is a legitimate
trial and demonstration profile, and this document gives full steps for it —
but do not let a trial quietly become the hotel's live system. Migrating later
is a restore from backup (see [`BACKUP.md`](BACKUP.md)), so plan it deliberately
rather than discovering it.

§9 covers Option B.

---

## 3. Prerequisites

### Windows 10, for WSL2

| Requirement | Why |
| --- | --- |
| 64-bit Windows 10, version **2004** (build **19041**) or later | WSL2 is unavailable below this |
| Hardware virtualization enabled in BIOS/UEFI | WSL2 is a real VM |
| WSL installed, **default version 2** | WSL1 cannot run Docker's Linux containers |
| Docker Desktop with the **WSL2 backend** | Provides the Docker Engine |
| Docker Desktop **integration enabled for the distribution** | Otherwise `docker` is not on `PATH` inside WSL |

Check the build with `winver`, or:

```powershell
[System.Environment]::OSVersion.Version
```

Virtualization is visible in Task Manager → Performance → CPU
("Virtualization: Enabled"). If it reads Disabled, it is a BIOS/UEFI setting
(Intel VT-x / AMD-V) and sometimes a conflict with Hyper-V, VirtualBox or a
third-party anti-cheat driver. That is the client's IT problem to clear before
you arrive, and it is worth asking about in advance — it is the single most
common reason an install day is wasted.

### Resources

From `deploy/README.md`, the floor for the stack itself:

- **2 vCPU · 4 GB RAM · 40 GB disk** minimum
- under **8 GB** RAM the installer creates a swap file (`/swapfile-kamra`) so
  the image build does not run out of memory (`deploy/install.sh:112-137`)

On Windows those numbers are the floor for the *Linux side only*. Docker
Desktop, the WSL2 VM and Windows itself all want memory on top. In practice:

| | Works | Comfortable |
| --- | --- | --- |
| Windows 10 + WSL2 + Docker Desktop + ZIRI | 8 GB RAM, 60 GB free | **16 GB RAM, 100 GB free** |

Note that WSL2's virtual disk grows and does not shrink on its own, and the
image build is disk-hungry. 40 GB free on `C:` is not enough headroom for a
machine that also runs the hotel's other software.

### Time

**First install takes 20–45 minutes**, and can take longer on a laptop disk or
a slow connection. This is not a progress bar stalling: `install.sh` builds the
Frappe + payments + kamra image locally (`deploy/README.md`), it does not pull
a prebuilt one. Tell the client this before you start, and do not schedule the
install for the half hour before check-in.

### The repository must be reachable without credentials

`install.sh` writes `apps.json` (`deploy/install.sh:153-160`) and passes it to
`docker build` as a BuildKit secret. The clone happens **inside the container**,
from the URL in `apps.json`, **with no credentials**.

So if `https://github.com/ilyeseia/kamra-pms-algeria` is private, the build
fails at the clone step. Options, honestly stated:

1. **Make the repository public.** The project is AGPL-3.0, so the source is in
   any case something recipients are entitled to (see
   [`LICENSING.md`](LICENSING.md)). This is the clean answer.
2. **Bake a token into the URL** in `apps.json`, e.g.
   `https://<token>@github.com/...`. This works, and it means a GitHub
   credential sits in plaintext in `/opt/kamra/apps.json` on the client's
   machine, readable by anyone with a shell there, surviving in backups and
   in any image you build from it. It is a **poor trade** and should be a
   deliberate, time-boxed decision with a token scoped to read that one
   repository and nothing else — not a default.
3. **Pre-build the image elsewhere** and load it on the client machine
   (`install.sh build`, then `docker save` / `docker load`). Keeps the
   credential off the client's disk entirely. More moving parts, but this is
   the option to reach for if the repository must stay private.

Decide this before install day. Discovering it at the clone step costs you the
whole build.

---

## 4. Preflight checklist

`Install-Kamra.ps1 -Preflight` runs the checks and changes nothing. Run it
first, every time, on the client's machine.

Confirm before you proceed:

- [ ] Windows 10 64-bit, build 19041 or later
- [ ] Virtualization enabled in BIOS/UEFI
- [ ] WSL installed, default version 2, a distribution present and starting
- [ ] Docker Desktop installed, running, WSL2 backend, integration on for the distro
- [ ] `docker version` and `docker compose version` both succeed **inside WSL**
- [ ] `docker buildx version` succeeds — the layered `Containerfile` uses
      `RUN --mount=type=secret` and needs BuildKit (`deploy/install.sh:101-108`)
- [ ] ≥ 8 GB RAM, ≥ 60 GB free on the WSL disk
- [ ] Chosen HTTP port free (default **8080** — check nothing else on the
      machine has it; IIS, Jenkins and several vendor tools like 8080)
- [ ] Outbound HTTPS reachable — the build pulls from GitHub and PyPI
- [ ] The Algeria repository is reachable **without credentials**, or you have
      chosen option 2 or 3 above and written down which
- [ ] The client knows the install takes 20–45 minutes
- [ ] For production: site hostname decided, admin email decided, admin
      password generated in a password manager (min **10** characters —
      `deploy/install.sh:51,255`) and a plan for who holds it

---

## 5. The two profiles, side by side

| | **Trial** — نسخة تجريبية | **Production** — نسخة احترافية |
| --- | --- | --- |
| Invocation | `.\Install-Kamra.ps1 -Mode Trial` | `.\Install-Kamra.ps1 -Mode Production -SiteName pms.hotel.dz -AdminEmail gm@hotel.dz` |
| Site name | `kamra.localhost` (default) | required, a real hostname |
| Sample data | Seeded — demo property, rooms, guests, stays | **None** |
| `kamra_demo_mode` | On | Off |
| Demo accounts | Created — all six, known passwords | **Never created** |
| Login screen demo buttons | Shown | Hidden |
| Demo reset available | Yes | No — and that is intentional |
| Admin password | prompted by the Linux installer, both modes | prompted by the Linux installer, both modes |
| HTTP port | `-HttpPort`, default 8080 | `-HttpPort`, default 8080 |
| TLS | None. `localhost` over plain HTTP | **Required** — see §8.6 |
| Backups | Not configured; the data is disposable | **Mandatory** — see [`BACKUP.md`](BACKUP.md) |
| Intended life | Days or weeks, then discard | Years |

### Why the trial site is called `kamra.localhost`

Because of the demo reset guard. `kamra/scripts/reset_demo.py:59-63`:

```python
def is_playground() -> bool:
	if frappe.db.get_default("kamra_demo_mode") != "1":
		return False
	site = frappe.local.site or ""
	return site in PLAYGROUND_SITES or site.endswith(".localhost")
```

`execute()` (`reset_demo.py:73-80`) **refuses and throws** unless that returns
true: demo mode must be on *and* the site must be `demo.kamrapms.com`,
`nightly.kamrapms.com`, or a `*.localhost` name. A site called `pms.hotel.dz`
can never be reset by that script, whatever its demo-mode flag says.

So a trial you want to re-demonstrate from a clean slate must live on a
`.localhost` name. `kamra.localhost` satisfies the guard and the installer's
domain-shape validation (`deploy/install.sh:253` requires a dot in the name).

The same guard is why a production site cannot accidentally be wiped by this
script. That is the guard doing its job; do not work around it.

---

## 6. Installing

Both profiles share the same shape: prepare WSL2 and Docker, run the
installer, verify. What differs is what the installer does inside, per §5.

### 6.1 Prepare WSL2 and Docker Desktop (once per machine)

In an **elevated** PowerShell:

```powershell
wsl --install
wsl --set-default-version 2
```

Reboot if asked. Then confirm:

```powershell
wsl --status
wsl --list --verbose
```

Every distribution you intend to use must show `VERSION 2`. Convert one that
does not:

```powershell
wsl --set-version <DistroName> 2
```

Install Docker Desktop, and in its settings:

- **General** → *Use the WSL 2 based engine*
- **Resources → WSL integration** → enable the distribution you will install into
- **General** → *Start Docker Desktop when you log in* (for a trial this is a
  convenience; treat it as a reason not to run production this way)

Confirm from inside WSL — this is the check that actually matters, because
`install.sh` runs there:

```powershell
wsl -d <DistroName> -- bash -lc "docker version && docker compose version && docker buildx version"
```

All three must succeed. If `docker` is not found, WSL integration is off for
that distribution.

### 6.2 Trial — نسخة تجريبية

```powershell
.\Install-Kamra.ps1 -Preflight
.\Install-Kamra.ps1 -Mode Trial
```

Defaults apply: site `kamra.localhost`, port 8080, the Algeria repository and
branch, sample data seeded, demo mode on. Expect 20–45 minutes.

When it finishes, open:

```
http://localhost:8080/kamra
```

The login screen shows the six demo accounts as one-tap buttons. That is
correct here and only here.

To re-demonstrate from a clean slate, from `/opt/kamra/frappe_docker` inside
WSL:

```bash
cd /opt/kamra/frappe_docker
docker compose --project-name kamra --env-file /opt/kamra/kamra.env \
  -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.noproxy.yaml \
  exec -T backend bench --site kamra.localhost execute kamra.scripts.reset_demo.execute
```

That compose invocation — project name, env file, and all four `-f` overrides —
is the one `install.sh` itself uses (`deploy/install.sh:178-184`), run from the
`frappe_docker` directory it checks out. **Every `bench` command in this
document and in [`BACKUP.md`](BACKUP.md) goes through it.** A plain
`docker compose` without those flags will not find the stack.

`reset_demo` deletes everything anyone created on the trial site and reseeds
the sample hotel (`reset_demo.py:83-101`). It is destructive by design. Never
point it at a production site — and it will refuse anyway.

### 6.3 Production — نسخة احترافية

```powershell
.\Install-Kamra.ps1 -Preflight
.\Install-Kamra.ps1 -Mode Production -SiteName pms.hotel.dz -AdminEmail gm@hotel.dz
```

`Install-Kamra.ps1` never asks for, stores or forwards the admin password — a
stronger guarantee than handling it carefully would be. It exports `SITE_NAME`
and `ADMIN_EMAIL` only; because `prompt()` in `deploy/install.sh` returns early
for a variable that is already set, the Linux installer asks for the password
itself and reads it straight from the console (`install.sh:67-80`, `:244-249`).
So it never enters a PowerShell variable, the environment block, a transcript or
shell history — there is nothing holding it to leak.

This applies to **both** modes, Trial included. Minimum 10 characters
(`deploy/install.sh:51,255`); there is **no default password** anywhere in this
stack, by design.

Generate it in a password manager, give it to the person who will own it, and
do not keep a copy. If you are the vendor and you hold the hotel's
administrator password after handover, you have taken on a liability you were
not paid for.

Nothing is seeded. The site starts genuinely empty and the hotel's own data is
created through the setup wizard.

### 6.4 First-boot wiring

For either profile, the installer runs
`kamra.scripts.first_boot.execute` (`deploy/install.sh:311-314`), which
(`kamra/scripts/first_boot.py:23-30`):

- points the site's home page at `/kamra` so visitors land on the app rather
  than an empty Frappe Desk
- sets the admin email on the `Administrator` user
- sets `host_name` from the site URL
- ensures the scheduler is enabled — the night audit and the housekeeping SLA
  escalations depend on it

It only fills blanks, so it is safe to re-run.

### 6.5 Create the property

Open `/kamra/setup` and create the property. **Pick `Algeria` from the country
list.** See §7.3 — this is not cosmetic, and getting it wrong is silent.

### 6.6 Production only — TLS and exposure

The installer publishes plain HTTP on `-HttpPort` and terminates no TLS;
`install.sh` says as much and suggests nginx, Caddy or
`certbot --nginx -d <site>` (`deploy/install.sh:329-330`).

For a production site:

- Do not expose port 8080 to the internet directly.
- Put a reverse proxy in front and terminate TLS there.
- Point DNS for `pms.hotel.dz` at the host, so the certificate and
  `FRAPPE_SITE_NAME_HEADER` (`deploy/install.sh:287`) agree.
- Then set `developer_mode 0` and confirm `ignore_csrf` is off, per
  `docs/self-hosting.md:82-83`.

On Windows 10 via WSL2 all of this is materially harder than on a Linux host —
you are proxying into a VM whose IP can change, on a desktop OS with its own
firewall. It is one more reason §2 recommends Option B for production.

---

## 7. Verifying the install actually worked

Do not hand over on "the login page loaded". Work through all of these. Every
`bench` command below uses the compose invocation from §6.2.

### 7.1 The stack is up

```bash
cd /opt/kamra/frappe_docker
docker compose --project-name kamra --env-file /opt/kamra/kamra.env \
  -f compose.yaml -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml -f overrides/compose.noproxy.yaml ps
```

Then, using `<COMPOSE>` as shorthand for that command:

```bash
<COMPOSE> exec -T backend bench --version
<COMPOSE> exec -T backend bench --site <site> list-apps
```

`list-apps` must show **`frappe`, `payments` and `kamra`** — those are the three
`install.sh` installs (`deploy/install.sh:301-305`).

### 7.2 Migrations ran

```bash
<COMPOSE> exec -T backend bench --site <site> migrate
```

It should complete without error and be a no-op on a fresh install. This is
also the first real execution of `v36` and `v37` — see §8.

### 7.3 Algeria is registered and selectable

The pack is registered in `kamra/hooks.py:72-80`:

```python
kamra_localization = {
	"India": "kamra.localization.india",
	...
	"Algeria": "kamra.localization.algeria",
}
```

`kamra/api.py:4667-4673` exposes `localization_countries()`, which calls
`supported_countries()` in `kamra/localization/__init__.py:133-153`. That
function reads the hook, imports each pack, and calls
`pack.invoice_context(...)` on it — so if it returns an Algeria row, the pack
imported and executed, not merely existed.

```bash
<COMPOSE> exec -T backend bench --site <site> execute kamra.api.localization_countries
```

Expected, among the other countries:

```
{"country": "Algeria", "currency": "DZD", "timezone": "Africa/Algiers",
 "tax_label": "TVA", "tax_id_label": "NIF"}
```

Verified against the source: `kamra/localization/algeria.py:69-75` sets
`DEFAULT_TVA = Decimal("19")`, `DEFAULT_CURRENCY = "DZD"`,
`DEFAULT_TIMEZONE = "Africa/Algiers"` and
`ROOM_LEVY_LABEL = "Taxe de séjour"`.

**If Algeria is missing, you built the wrong branch.** Go back to §1 and
check `/opt/kamra/apps.json`:

```bash
cat /opt/kamra/apps.json
```

It must name `ilyeseia/kamra-pms-algeria` and
`feature/algeria-hospitality-platform`. If it names `Kamra-PMS/kamra-pms` or
`main`, fix it and run `sudo KAMRA_BRANCH=feature/algeria-hospitality-platform
KAMRA_GIT_URL=https://github.com/ilyeseia/kamra-pms-algeria /opt/kamra/install.sh update`.

### 7.4 The property resolved to the Algeria pack — check this carefully

`kamra/localization/__init__.py:27-44`:

```python
def pack_for(property=None):
	country = None
	if property:
		country = frappe.get_cached_value("Property", property, "country")
	return pack_for_country(country or "India")
```

Two traps, both silent:

- `Property.country` is a free-text `Data` field
  (`IMPLEMENTATION_STATUS.md`, limitation 3). `pack_for_country` does an
  **exact dictionary lookup**, so `algeria`, `Algérie`, `Algeria ` with a
  trailing space, or the Arabic name all miss and fall through to the
  **generic** pack. No error, no warning — the hotel just gets no TVA
  labelling and no *taxe de séjour*.
- A **blank** country is worse: `country or "India"` means an empty country
  loads the **India** pack. The client would get GST vocabulary and INR.

So verify the stored value, not what you think you typed:

```bash
<COMPOSE> exec -T backend bench --site <site> execute \
  frappe.client.get_value --kwargs "{'doctype':'Property','fieldname':'country','filters':{}}"
```

It must be exactly `Algeria`. Then confirm the invoice context the property
actually resolves to shows `TVA`, `NIF`, `DZD` and `Taxe de séjour`.

### 7.5 Currency and tax vocabulary in the UI

Sign in and confirm on screen:

- amounts render in **DZD**
- the tax column is labelled **TVA**, not GST or VAT
- the Property settings screen offers the **NIF** field, and the **RC**, **NIS**
  and **AI** fields (these are `rc_number`, `nis_number`, `ai_number`, added
  by patch `v37`)
- the room levy is labelled **Taxe de séjour**, and the mode switch offers
  *Fixed per person per night*
- the time zone list contains **`Africa/Algiers`**

### 7.6 Print one invoice

Create a throwaway reservation, post a night, and print the folio. Confirm the
footer carries `RC · NIF · NIS · AI` for whichever of those the property has
filled, and that the amount in words reads *Dinars …* and not *DZD …*
(`kamra/localization/words.py` carries `"DZD": ("Dinars", "Centimes")`).

Then delete the throwaway reservation. On a production site, do this **before**
the hotel starts entering real data, so there is nothing to disentangle.

### 7.7 Production only — confirm the demo surface is absent

This is the check that matters most.

```bash
# must be empty — not "the passwords were changed", empty
<COMPOSE> exec -T backend bench --site <site> execute frappe.client.get_list \
  --kwargs "{'doctype':'User','filters':{'name':['like','%@kamra.local']},'fields':['name']}"
```

And confirm `site_info` reports demo mode off, so the login screen shows no
demo buttons:

```bash
<COMPOSE> exec -T backend bench --site <site> execute kamra.public_api.site_info
# expected: {'demo_mode': False}
```

If either check comes back wrong, do not hand over. Go to §1.

### 7.8 Scheduler

```bash
<COMPOSE> exec -T backend bench --site <site> doctor
```

The scheduler must be enabled — the night audit (03:00 site time) and the
housekeeping SLA escalations are scheduled jobs. A site whose scheduler is off
looks fine all day and silently never closes a night.

---

## 8. What is not proven

Everything in this section is a real, current gap. It is here because a vendor
who buries these is selling a liability, and because the client's own testing
is what closes them. None of it is speculative — each item was checked against
the repository.

### 8.1 No backend test has ever run against a real site

`IMPLEMENTATION_STATUS.md` records it plainly: there is no `bench` and no site
on the development machine, so the Frappe/Python test suite has **never been
executed**. The quality gate on this branch is static analysis plus arithmetic
against stubbed modules. That is not the same as a passing test run, and it
should not be described to a client as one.

**What to do:** treat the first install as the test. Budget time for it, and do
it on a trial site before a production one.

### 8.2 Migrations `v36` and `v37` have never touched a database

`kamra/patches.txt` ends with:

```
kamra.patches.v36.backfill_room_levy_mode
kamra.patches.v37.normalize_legal_id_columns
```

`v36` backfills the fixed per-person room levy mode; `v37` normalises the
`rc_number` / `nis_number` / `ai_number` columns. Neither has ever run against
a MariaDB instance. **The first `bench migrate` is their first real test.**

**What to do:** run migrations on the trial profile first. Back up before
migrating a site that has data ([`BACKUP.md`](BACKUP.md)), every time, without
exception.

### 8.3 Nobody has looked at the Arabic RTL layout in a browser

The RTL work — logical `start`/`end` classes, the mirrored sheet animation, the
`rtl:rotate-180` variant, bidi isolation on price and phone runs — type-checks
and is written correctly as far as reading it can establish. **No one has
rendered it in a browser and looked.** `IMPLEMENTATION_STATUS.md` lists this as
open under limitation 17 and under *Not started*, for Arabic, French and
English print layouts alike.

**What to do:** have someone who reads Arabic click through the front desk,
the guest booking page and a printed invoice before go-live. Expect to find
things. They will be cosmetic rather than arithmetic, but a hotel judges
software on what it looks like to a guest.

### 8.4 The tax rates are defaults, not legal advice

19% standard and 9% reduced TVA are **configurable defaults**. The pack
asserts no legal position and says so in its own docstring
(`kamra/localization/algeria.py:7-14`). Whether a given house's accommodation
and its F&B outlets fall on the standard rate, the reduced rate or a mix
depends on the finance law, the outlet and the hotel's classification.

`DEFAULT_TVA` is only the fallback for a room type nobody has typed a number
on; the real rate lives on each Room Type as data.

**The client's accountant must confirm the treatment before the first live
invoice.** Put that in writing. See [`TAXES.md`](TAXES.md) for the full
picture, including the *taxe de séjour* basis and the four legal identifiers.

### 8.5 A known defect: Percent-mode levy disagrees with a discount voucher

With a discount voucher applied and the room levy in **Percent** mode, the
quote and the posted folio produce different numbers: the quote levies on the
discount-reduced room net, the folio levies on the full night rate. On the
worked example in `IMPLEMENTATION_STATUS.md` (limitation 2) that is **1350 in
the quote against 1500 on the folio**.

It was reproduced against pristine upstream `HEAD`, so it **predates this
branch** — but it will bite an Algerian hotel that runs promotions.

**Fixed-amount mode is unaffected**, and fixed-amount is what an Algerian
house actually wants for a *taxe de séjour* anyway. So:

**What to do:** set `room_levy_mode` to *Fixed per person per night* and fill
`room_levy_amount`. If the client insists on Percent mode and uses vouchers,
tell them about this discrepancy before they discover it on a guest's bill.
Fixing it properly needs an owner decision — is a percentage levy
discountable? — and both calculation sites (`kamra/pricing.py:299` and
`kamra/folio.py:349`) must change together.

### 8.6 A tax-exempt room type cannot be expressed

`Room Type.tax_percent` is a Frappe `Percent`. Frappe stores blank as `0`, and
the field's own description says blank means "use your country's standard
rate" — so `0` and "not configured" are **the same value in the database**,
and every country pack reads `0` as "fall back to the national rate".

Algeria's dropdown therefore offers only `[9, 19]`, deliberately: offering `0`
would present a choice the arithmetic silently converts to 19%. This is an
upstream-wide collapse, not an Algeria defect — see [`TAXES.md`](TAXES.md).

**What to do:** if the client has a genuinely exempt room type, this system
cannot represent it today. Say so before the sale, not after.

### 8.7 Smaller things worth knowing

- **Children are not counted in the levy** — adults only, at both calculation
  sites. Several Algerian municipalities exempt or halve children. This is an
  operator policy decision the system currently makes one way.
- **The fixed levy is treated as tax-exclusive** even on a `rates_include_tax`
  property (limitation 7).
- **Hotel-authored content stays monolingual.** The interface is Arabic,
  French and English, but property and room descriptions, house rules, FAQ,
  amenities, meal plans and menu items are backend data in whatever language
  the operator typed. An Arabic guest gets an Arabic interface around
  French text unless the hotel writes it twice.
- **Localization coverage is 78.2% Arabic and 75.5% French** against a 1593-key
  catalog, honestly measured. Part of the remainder is deliberate (acronyms,
  product names); part is genuine backlog. Some strings will appear in English.
- **Plural and ordinal forms are a stopgap.** The visible damage — `3 ليلةs`,
  `الطابق 3rd` — is fixed, but no real plural selection exists (limitation 12).
- **`marketplace_install_check.py` crashes on Windows** with a
  `UnicodeDecodeError` unless `PYTHONUTF8=1` is set (limitation 18). Only
  relevant if you run repository tooling on the Windows host rather than
  inside WSL.

---

## 9. The recommended alternative: a Linux VPS

For a production hotel, this is the install to sell. The Windows 10 machine
installs nothing.

On a fresh Ubuntu VPS meeting 2 vCPU / 4 GB / 40 GB — realistically 8 GB for a
comfortable build:

```bash
export KAMRA_GIT_URL=https://github.com/ilyeseia/kamra-pms-algeria
export KAMRA_BRANCH=feature/algeria-hospitality-platform
export SITE_NAME=pms.hotel.dz
export ADMIN_EMAIL=gm@hotel.dz
# ADMIN_PASSWORD will be prompted; do not put it in the environment or history
bash install.sh
```

Both overrides are mandatory and there is no prompt for them. Verify
`/opt/kamra/apps.json` afterwards, then work through §7 unchanged — the
verification steps are identical, since it is the same stack.

Then: point DNS at the host, terminate TLS with nginx or Caddy
(`certbot --nginx -d pms.hotel.dz`), and configure backups per
[`BACKUP.md`](BACKUP.md) on the server's own cron rather than Task Scheduler.

Updates, on either platform (`deploy/README.md`):

```bash
sudo /opt/kamra/install.sh update
```

That rebuilds the image from `/opt/kamra/apps.json` with a fresh `CACHE_BUST`,
recreates the containers, and runs `bench --site all migrate` and
`clear-cache`. To pin or move the branch, pass it:

```bash
sudo KAMRA_BRANCH=<tag-or-branch> /opt/kamra/install.sh update
```

**Back up before every update.** The update runs migrations.

---

## 10. Install layout

After either profile, from `deploy/README.md`:

```
/opt/kamra/
  install.sh          # copy of the installer, so `install.sh update` works
  kamra.env           # compose secrets (DB password, site header), mode 600
  apps.json           # apps + branch baked into the local image
  frappe_docker/      # upstream compose files (MariaDB + Redis + noproxy)
```

Two of these matter more than they look:

- **`kamra.env` holds the MariaDB password** and is mode 600
  (`deploy/install.sh:277-289` sets `umask 077` before writing it).
  `install.sh` re-reads it on a re-run so the database password stays the one
  MariaDB was initialised with (`deploy/install.sh:257-260`). **Lose it and a
  database dump may be unrestorable.** It must be in your backups, and it must
  not be in the repository — `.gitignore` covers `kamra.env` on this branch.
- **`apps.json` is the record of which branch is installed**, and what
  `install.sh update` will rebuild from. It is the first thing to look at when
  someone asks why Algeria features vanished after an update.

---

## 11. Client handover checklist

Do not consider the job done until every line is true.

**Access**

- [ ] The client has the `Administrator` password, from their own password
      manager, and you do **not** have a copy
- [ ] Named staff users exist with appropriate roles (Hotel Admin / Front Desk
      / Revenue / Finance / Housekeeping). **Created by hand — not by
      `seed_users.py`**
- [ ] The URL the staff use is written down, along with what to do if it stops
      answering

**Security**

- [ ] Zero `*@kamra.local` users exist (§7.7)
- [ ] `site_info` reports `demo_mode: False`
- [ ] `developer_mode 0`, CSRF protection on
- [ ] HTTPS in front of the site, certificate valid, renewal automatic
- [ ] Port 8080 not exposed to the internet
- [ ] `/opt/kamra/kamra.env` still mode 600

**Correctness**

- [ ] `Property.country` is exactly `Algeria`, verified by reading the stored
      value (§7.4)
- [ ] Currency shows DZD; tax reads TVA; levy reads *Taxe de séjour*
- [ ] Room levy mode is *Fixed per person per night*, with the municipality's
      amount, unless the client consciously chose Percent **and** has been
      told about §8.5
- [ ] RC, NIF, NIS and AI filled on the Property and printing in the footer
- [ ] TVA rates on each Room Type **confirmed by the client's accountant**,
      with that confirmation on record
- [ ] One invoice printed and checked by a human

**Operations**

- [ ] Scheduler enabled; `bench doctor` clean
- [ ] Backups scheduled, **and one restore test performed and documented**
      ([`BACKUP.md`](BACKUP.md))
- [ ] Outgoing email configured, and a confirmation email actually received
- [ ] Payment gateway keys are the client's, test mode **off**
- [ ] The update procedure is written down, including "back up first"

**Documentation handed over**

- [ ] This document
- [ ] [`BACKUP.md`](BACKUP.md), [`LICENSING.md`](LICENSING.md),
      [`TAXES.md`](TAXES.md), [`VERSIONING.md`](VERSIONING.md)
- [ ] §8 of this document, walked through in conversation and acknowledged in
      writing. Not emailed as an attachment nobody opens
- [ ] The AGPL licence text (`license.txt`) and the source offer —
      see [`LICENSING.md`](LICENSING.md)
- [ ] The installed version: **Algeria Distribution 1.0.0 on Kamra core 2.6.5**

---

## 12. Uninstall and rollback

### Rolling back an update

An update rebuilds the image and migrates. Frappe migrations are not reversible
in the general case, so **rollback means restore**:

1. Restore the database and files from the backup you took before the update
   ([`BACKUP.md`](BACKUP.md)).
2. Rebuild on the previous branch or tag:
   `sudo KAMRA_BRANCH=<previous> /opt/kamra/install.sh update`

If you did not take that backup, you do not have a rollback path. This is the
whole reason §9 and §11 insist on it.

### Removing a trial

Inside WSL, with `<COMPOSE>` as in §7.1:

```bash
<COMPOSE> down            # stop, keep the volumes (data survives)
<COMPOSE> down -v         # stop AND DELETE THE VOLUMES — all data gone
docker image rm kamra:local
sudo rm -rf /opt/kamra
```

`down -v` is irreversible. On a trial that is the point. On anything else,
take a backup first — and note that `rm -rf /opt/kamra` destroys `kamra.env`
and with it the database password, which a restore may need.

To remove the Windows side as well: uninstall Docker Desktop, then
`wsl --unregister <DistroName>` — which deletes that distribution's entire
filesystem, including anything else stored there. Check what else lives in it
before running it.

### Removing a production install

Do not, until:

1. A full backup exists, restored and verified **somewhere else** (§"Test your
   restore" in [`BACKUP.md`](BACKUP.md)).
2. The client has confirmed in writing that they have their data.

The hotel's reservations, folios, invoices and guest records are in that
database. Some of it they are legally required to retain. Deleting it is not a
technical decision.

---

## 13. When something goes wrong

| Symptom | Likely cause |
| --- | --- |
| `need 'docker' on PATH` | Docker Desktop WSL integration off for the distro |
| `docker buildx is required` | BuildKit missing; the layered Containerfile needs `RUN --mount=type=secret` |
| Build fails at the ZIRI clone | Repository is private — see §3 |
| Build killed / out of memory | Under the 8 GB floor and swap could not be created; raise Docker Desktop's memory limit |
| `docker build failed` after a long run | Usually disk full. WSL2's virtual disk grows; check free space on `C:` |
| Backend never becomes ready | `<COMPOSE> logs backend` and `logs db`; `install.sh` waits 5 minutes (`deploy/install.sh:186-195`) |
| Algeria not in the country list | Wrong branch built. §1, §7.3 |
| Prices in INR, tax reads GST | `Property.country` blank → India pack. §7.4 |
| No TVA, no *Taxe de séjour* | `Property.country` misspelled → generic pack. §7.4 |
| `ERPNEXT_VERSION` warnings | Harmless upstream compose noise (`deploy/TROUBLESHOOTING.md`) |
| `unauthorized` pulling from ghcr.io | An old installer trying to pull a private image. Use the current one, which builds locally (`deploy/TROUBLESHOOTING.md`) |
| Night audit never runs | Scheduler disabled. §7.8 |

`deploy/TROUBLESHOOTING.md` covers the upstream cases in more detail.

---

## See also

- [`BACKUP.md`](BACKUP.md) — backup, restore, scheduling, and the restore test
- [`LICENSING.md`](LICENSING.md) — AGPL-3.0 and what it means for selling this
- [`TAXES.md`](TAXES.md) — TVA, *taxe de séjour*, the legal identifiers
- [`VERSIONING.md`](VERSIONING.md) — Algeria Distribution vs Kamra core
- [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) — what is delivered,
  what is not, and what was verified versus merely written
- `deploy/README.md`, `deploy/TROUBLESHOOTING.md` — upstream self-host notes
