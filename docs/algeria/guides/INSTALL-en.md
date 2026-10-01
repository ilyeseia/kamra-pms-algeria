# ZIRI PMS — Installation Guide

**Version installed:** ZIRI PMS, Algeria Distribution 1.0.0, on Kamra core **2.6.5**

This guide takes you from a bare Windows 10 machine to a working ZIRI PMS site
with your hotel's own property record in it. Follow the steps in order.

> **A note on the name.** The product you bought is **ZIRI PMS**. Its underlying
> software component is named `kamra` internally, so you will see that word in
> file paths, commands and web addresses — `/opt/kamra`, `kamra.env`,
> `http://localhost:8080/kamra`. That is normal and expected. **Do not "correct"
> those paths.** Type them exactly as printed or nothing will work.

---

## 1. What this is, and what it needs

ZIRI PMS is a property management system: reservations, arrivals and departures,
folios, invoicing, housekeeping, and the Algerian tax and legal-identifier
fields (TVA, NIF, RC, NIS, AI, and the *taxe de séjour*).

**Two sentences you need to read before anything else.** The framework ZIRI PMS
is built on does not run natively on Windows — there is no Windows build. The
installer therefore checks that your Windows machine can host Linux containers,
then drives the real Linux installer inside **WSL2**, with **Docker Desktop**
running the containers.

That works, and it is the right setup for a demonstration, a pilot, or a single
machine whose owner knows what they have. **For a hotel taking live bookings, a
Linux server is the better home** — the Windows machine then installs nothing at
all and the front desk simply opens a web address. A Windows install depends on
Docker Desktop being started and a user being logged in; if that machine is shut
down or dies, the hotel's data goes with it. Decide this deliberately rather
than letting a trial quietly become your live system. Ask your vendor for the
Linux server option if you are in any doubt.

---

## 2. Before you start

Tick every line. The preflight check in Step 1 verifies most of them for you,
but the two hardware items are yours to sort out first.

**The machine**

- [ ] Windows 10, **64-bit**, version **2004** (build **19041**) or later
      (check with `winver`)
- [ ] Hardware virtualisation **enabled** in the BIOS/UEFI
      (Task Manager → Performance → CPU should read "Virtualization: Enabled")
- [ ] **8 GB RAM** minimum — **16 GB** is comfortable
- [ ] **40 GB free disk** minimum — 60 GB or more is safer, because the WSL2
      virtual disk grows as it is used and does not shrink back on its own
- [ ] WSL installed, with **default version 2**
- [ ] **Docker Desktop** installed, running, using the **WSL 2 based engine**
- [ ] Docker Desktop **WSL integration enabled for your distribution**
      (Settings → Resources → WSL integration)

**Decisions to make before install day**

- [ ] Trial or Production? (See Step 2 — they are not the same install.)
- [ ] For Production: the site hostname, e.g. `pms.yourhotel.dz`
- [ ] For Production: the administrator email address, e.g. `gm@yourhotel.dz`
- [ ] For Production: the **administrator password**, generated in your own
      password manager, minimum **10 characters**. See Section 8.
- [ ] Which HTTP port to publish on. Default is **8080**; make sure nothing else
      on the machine is using it.
- [ ] Outbound internet access (HTTPS) is available from the machine.

**Time**

- [ ] **The first install takes 20 to 45 minutes**, and can take longer on a slow
      disk or connection. This is not a hung progress bar: the software image is
      **built locally on your machine**, not downloaded ready-made. Do not
      schedule the install for the half hour before check-in.

**Preparing WSL2 and Docker Desktop (once per machine)**

In an **elevated** PowerShell (Run as administrator):

```powershell
wsl --install
wsl --set-default-version 2
```

Reboot if you are asked to. Then confirm:

```powershell
wsl --status
wsl --list --verbose
```

Every distribution you intend to use must show `VERSION 2`. Convert one that
does not:

```powershell
wsl --set-version <DistroName> 2
```

Install Docker Desktop, then in its settings enable **Use the WSL 2 based
engine** (General) and enable integration for your distribution
(Resources → WSL integration).

Finally, confirm Docker actually works *inside* WSL — this is the check that
matters, because the real installer runs there:

```powershell
wsl -d <DistroName> -- bash -lc "docker version && docker compose version && docker buildx version"
```

All three must succeed. If `docker` is not found, WSL integration is still off
for that distribution.

---

## 3. Step 1 — check the machine

Open PowerShell in the folder that contains `Install-Kamra.ps1` and run:

```powershell
.\Install-Kamra.ps1 -Preflight
```

**`-Preflight` changes nothing.** It inspects Windows, memory, disk, WSL, Docker
and the chosen port, then prints a summary and stops. Run it first, every time.

Read the summary. Blocking problems are listed as `[FAIL]` with a suggested fix,
and the script exits without touching anything. Warnings are listed separately
and do not block the install.

If PowerShell refuses to run the file because it is unsigned, allow it for this
one session rather than weakening the machine's policy permanently:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-Kamra.ps1 -Preflight
```

Do not go on to Step 2 until the preflight reports that the environment can host
the stack.

---

## 4. Step 2 — install

There are two profiles and they are genuinely different installs. Choose before
you run anything.

| | **Trial** | **Production** |
| --- | --- | --- |
| Site name | `kamra.localhost` (the default) | required, a real hostname |
| Sample hotel data | seeded | **none** |
| Demo accounts | created | **never created** |
| Demo reset available | yes | no, by design |
| Intended life | days or weeks, then discard | years |
| Backups | not needed, the data is disposable | **mandatory** |

### Trial

A disposable demonstration with a sample hotel already in it.

```powershell
.\Install-Kamra.ps1 -Mode Trial
```

Defaults apply: site `kamra.localhost`, port 8080, sample data seeded.

### Production

The live install. Nothing is seeded — the site starts genuinely empty and your
hotel's own data is created through the setup wizard in Step 3.

```powershell
.\Install-Kamra.ps1 -Mode Production -SiteName pms.yourhotel.dz -AdminEmail gm@yourhotel.dz
```

`-SiteName` and `-AdminEmail` are **required** for Production. The site name must
contain a dot — the installer rejects anything that does not look like a domain.

To publish on a different port, add `-HttpPort`:

```powershell
.\Install-Kamra.ps1 -Mode Production -SiteName pms.yourhotel.dz -AdminEmail gm@yourhotel.dz -HttpPort 9090
```

### The administrator password

**The Windows installer never asks for, stores, or forwards the administrator
password.** Part-way through, the Linux installer running inside WSL will prompt
for it and read it straight from the console. It never enters a PowerShell
variable, the environment, a log file, or your command history.

Minimum **10 characters**. **There is no default password anywhere in this
system.** Choose it yourself, from your own password manager, and see Section 8.

Then wait. 20 to 45 minutes is normal.

---

## 5. Step 3 — first setup

When the installer finishes it prints the address to open. With the default port
that is:

```
http://localhost:8080/kamra
```

If you used `-HttpPort`, substitute your port number; the `/kamra` part of the
address never changes.

Sign in as `Administrator` with the password you typed during the install.

Then open the setup wizard:

```
http://localhost:8080/kamra/setup
```

Create your property — name, address, contact details, rooms.

### Choose Algeria as the country

**This is the single most important field in the wizard, and getting it wrong
fails silently.**

- Pick **Algeria** from the country list. Not a variant spelling, not the French
  or Arabic name — the entry that reads `Algeria`.
- Then confirm, on screen: amounts display in **DA** (the dinar symbol; `DZD` is the currency code behind it), and the tax column is
  labelled **TVA** (not VAT, not GST).
- Also confirm the property form offers the **NIF** field, plus **RC**, **NIS**
  and **AI**, and that the room levy is labelled **Taxe de séjour**.

**If Algeria does not appear in the country list at all, the wrong version was
installed.** Stop, do not enter any data, and tell your vendor: the install was
built from the upstream software instead of the Algeria distribution. It will
look like a working hotel system while containing none of the Algerian work.

If the country is left blank or misspelled, the system falls back to another
country's tax vocabulary without warning you — you would get prices in the wrong
currency and a tax column labelled GST. So verify what is on screen; do not
assume what you typed was stored.

### The tax rates

The TVA rates the system offers (19% standard, 9% reduced) and the *taxe de
séjour* amount are **configurable defaults, not legal advice**. Which rate
applies to your accommodation and to your food and beverage outlets depends on
the finance law, the outlet, and your hotel's classification.

**Your accountant must confirm the treatment before you issue the first real
invoice.** Set the rate on each Room Type as data. For the *taxe de séjour*, set
the mode to **Fixed per person per night** and enter your municipality's amount.
See [`TAXES.md`](../TAXES.md) for the full picture.

---

## 6. Step 4 — verify it works

Do not call the install done because the login page loaded. Work through this
list.

1. **The login page loads** at `http://localhost:8080/kamra` and you can sign in
   as `Administrator`.
2. **Algeria, DA and TVA** are confirmed on screen, as in Step 3.
3. **The time zone list contains `Africa/Algiers`.**
4. **A reservation saves.** Create a throwaway reservation, save it, reopen it.
   This is the first honest proof the database is healthy — see Section 9.
5. **A night posts and an invoice prints.** Post a night on that reservation and
   print the folio. Check that the footer carries whichever of **RC · NIF · NIS ·
   AI** you filled in, and that the amount in words reads *Dinars …* rather than
   *DZD …*.
6. **Delete the throwaway reservation** afterwards — on a production site, before
   staff start entering real data.
7. **The background scheduler is running.** The night audit (03:00 site time) and
   the housekeeping escalations are scheduled jobs. A site whose scheduler is off
   looks perfectly fine all day and then silently never closes the night. Check
   it from inside WSL:

   ```bash
   cd /opt/kamra/frappe_docker
   docker compose --project-name kamra --env-file /opt/kamra/kamra.env \
     -f compose.yaml \
     -f overrides/compose.mariadb.yaml \
     -f overrides/compose.redis.yaml \
     -f overrides/compose.noproxy.yaml \
     exec -T backend bench --site <your-site-name> doctor
   ```

   All four `-f` options, the project name and the env file are required. A plain
   `docker compose exec backend …` will not find the stack.

8. **Production only — no demo accounts exist.** See Section 8. This is the check
   that matters most; do not accept the system until it passes.

---

## 7. Backups

A property management system holds the only record of who is arriving tonight,
what they agreed to pay, what they have already paid, and what the hotel owes
the tax authority. Losing it is not an IT inconvenience.

Full procedures — what to back up, how to schedule it on Windows, and how to
restore — are in [`BACKUP.md`](../BACKUP.md). Read it before go-live, not after.

**The one rule: a backup nobody has restored is not a backup. It is a file.**

Perform a full restore test before handover and once a quarter after. Restore
into a separate throwaway site, confirm reservations, money **and uploaded files**
came back, and **write down what you had to do**. That note is the runbook
someone uses at 2am.

Three things from `BACKUP.md` worth repeating here:

- Always back up **with files** (`--with-files`). A database-only backup restores
  a hotel whose guest ID scans, signed registration cards and invoice
  attachments have all vanished — which for an Algerian house keeping a *fiche de
  police* trail is a compliance problem, not a partial backup.
- **Back up `/opt/kamra/kamra.env`.** It holds the database password. Lose it and
  a database dump may be unrestorable.
- **Back up before every update**, without exception. An update runs database
  migrations, and migrations are not reversible — rollback means restore.

```bash
cd /opt/kamra/frappe_docker
docker compose --project-name kamra --env-file /opt/kamra/kamra.env \
  -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.noproxy.yaml \
  exec -T backend bench --site <your-site-name> backup --with-files
```

---

## 8. Security

### The administrator password

- The Windows installer **never handles it**. The Linux installer prompts for it
  and reads it straight from the console.
- Minimum **10 characters**. **There is no default.**
- **Choose it yourself**, in your own password manager, and hold it yourself.
- **After handover, do not share it with the vendor** — and if the vendor still
  holds a copy, ask them to destroy it. Nobody outside the hotel needs the
  administrator password of the system that holds your guests' identity documents.

### A production site must never have the demo accounts

> ### ⚠ WARNING — read this before you seed anything
>
> Seeding sample data creates **six user accounts whose passwords are published
> in the product's public source code**. One of them is a **full system
> administrator**.
>
> Those passwords are also compiled into the JavaScript that every visitor to
> the site downloads. Turning "demo mode" off only hides the one-tap demo login
> buttons — **it does not invalidate the passwords**. Hiding a button is not
> security.
>
> **The only real protection is that the accounts do not exist.**
>
> `-Mode Production` seeds nothing and creates none of them. So:
>
> - **Never seed sample data on a live site**, not even "just to have something
>   to show".
> - **Never create those accounts by hand.**
> - If a site was already seeded and must now go live, treat it as
>   **compromised**: have the six accounts *deleted* (not merely given new
>   passwords), the `Administrator` password rotated, and the access logs
>   audited.

To confirm a production site is clean, no account may exist whose address ends in
`@kamra.local`. Your vendor can run that check for you; ask to see the output. It
must come back **empty** — not "the passwords were changed", empty.

### Other things to settle before go-live

- **Put HTTPS in front of the site.** The installer publishes plain HTTP and
  terminates no TLS. A hotel should not run over plain HTTP.
- **Do not expose port 8080 to the internet** directly.
- **Create named staff accounts** with the right roles (Hotel Admin, Front Desk,
  Revenue, Finance, Housekeeping) rather than sharing one login.
- **`/opt/kamra/kamra.env` must stay mode 600.** It holds the database password.

---

## 9. What is not yet proven

This section is here because a supplier who hides these is selling you a
liability. None of it is speculative, and none of it is a reason to panic. It is
a list of things your own first days of use will settle.

- **The database migrations have never run against a real database before your
  install.** Two migration steps — one for the fixed per-person *taxe de séjour*,
  one for the RC/NIS/AI fields — had never executed against an actual database
  anywhere. If your install completed, **they have just run for the first time.**
  What to do: run the Trial profile before Production if you can, check that the
  site loads and that a reservation saves (Step 4, item 4), and **take a backup
  before every future update**, which also runs migrations.

- **Nobody has viewed the Arabic layout in a browser.** The right-to-left work is
  written and type-checks correctly as far as reading the code can establish, but
  no one has rendered it on screen and looked at it. The same is open for the
  French, Arabic and English print layouts. What to do: have someone who reads
  Arabic click through the front desk, the guest booking page and a printed
  invoice before go-live. Expect to find things. They are very likely to be
  cosmetic rather than arithmetic — but a hotel is judged on what a guest sees.

- **No automated backend test has ever run against a real site.** The quality
  gate on this release was static analysis and arithmetic checks, not an executed
  test suite. Treat your first install as the test, and budget time for it.

- **A tax-exempt room type cannot be expressed today.** The data model cannot
  distinguish "0%" from "not configured", so the rate list deliberately offers
  only 9 and 19. If you have a genuinely exempt room type, this system cannot
  represent it yet — tell your vendor now rather than discovering it on an
  invoice.

- **A known defect with percentage-mode levy and discount vouchers.** If the
  *taxe de séjour* is set to **Percent** mode *and* a discount voucher is applied,
  the quote and the posted folio can produce different figures. **Fixed per
  person per night mode is unaffected** — and fixed is what an Algerian house
  actually wants for a *taxe de séjour* anyway. Use fixed mode.

- **Interface language does not translate your own content.** The interface is
  Arabic, French and English, but property and room descriptions, house rules,
  FAQs, amenities and menu items are whatever language you typed them in. An
  Arabic-speaking guest gets an Arabic interface around your French text unless
  you write it twice. Interface coverage is also not yet complete — some strings
  still appear in English.

---

## 10. If something goes wrong

| Symptom | Likely cause |
| --- | --- |
| `need 'docker' on PATH` | Docker Desktop WSL integration is off for your distribution |
| `docker buildx is required` | Docker's BuildKit is missing; the image build needs it |
| The build fails while fetching the software | The source repository is not reachable — ask your vendor |
| The build is killed, or reports out of memory | Below the 8 GB RAM floor; raise Docker Desktop's memory limit |
| `docker build failed` after a long run | Usually a full disk. The WSL2 virtual disk grows; check free space on `C:` |
| The site never becomes reachable | The containers are still starting or failing; the installer waits 5 minutes before giving up. Your vendor can read the container logs |
| **Algeria is missing from the country list** | The wrong version was installed. Stop and contact your vendor — see Step 3 |
| Prices show in a foreign currency, tax reads GST | The property's country was left **blank**, so another country's pack loaded. Fix the country field — see Step 3 |
| No TVA label, no *Taxe de séjour* | The property's country is **misspelled**. It must read exactly `Algeria` |
| The night audit never runs | The background scheduler is disabled — see Step 4, item 7 |
| `ERPNEXT_VERSION` warnings during install | Harmless noise from the underlying container files |
| PowerShell refuses to run the installer | The script is unsigned; use the one-session command in Step 1 |

---

## 11. Getting help

Before you contact support, gather this. Without it, the first reply will only
be a request for it.

**Always include the product name and both version numbers:**

```
ZIRI PMS
Algeria Distribution 1.0.0
on Kamra core 2.6.5
```

Both numbers matter. "Kamra core 2.6.5" on its own does not say whether the
Algeria pack is installed, and the distribution number on its own does not say
which core it sits on. The installer prints both on every run.

**Then add:**

- Which profile you installed — **Trial** or **Production**
- The exact command you ran, copied from PowerShell
- Your site name and the port you used
- Windows version and build (`winver`), and how much RAM the machine has
- Whether `.\Install-Kamra.ps1 -Preflight` passes **now**, and its full output
- The exact error text, copied as text rather than described or photographed
- At what point it failed — preflight, image build, site creation, first login,
  the setup wizard
- Whether it ever worked, and what changed since

**If the problem is about money or tax on a document**, attach the printed
invoice or folio and say which figure you expected and why.

**Never include the administrator password**, and never send it to anyone who
asks for it — including someone claiming to be your supplier. Support never
needs it.

---

## See also

- [`../BACKUP.md`](../BACKUP.md) — backup, restore, scheduling, and the restore test
- [`../TAXES.md`](../TAXES.md) — TVA, *taxe de séjour*, and the legal identifiers
- [`../VERSIONING.md`](../VERSIONING.md) — what the two version numbers mean
- [`INSTALL-fr.md`](INSTALL-fr.md) — this guide in French
- [`INSTALL-ar.md`](INSTALL-ar.md) — this guide in Arabic
