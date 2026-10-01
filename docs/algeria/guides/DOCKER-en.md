# Hotel MgM — Docker on Linux Installation Guide

**Version installed:** Hotel MgM, Algeria Distribution **1.0.0**, on Kamra
core **2.6.5**

This guide takes you from a bare Linux server to a working Hotel MgM site with
your hotel's own property record in it, running under Docker. Follow the steps
in order.

> **A note on the name.** The product you bought is **Hotel MgM**. Its underlying
> software component is named `kamra` internally, so you will see that word in
> file paths, image names, commands and web addresses — `/opt/kamra`,
> `kamra.env`, `kamra:local`, `--install-app kamra`,
> `http://<host>:8080/kamra`, `--project-name kamra`. That is normal and
> expected. **Do not "correct" those paths.** Type them exactly as printed or
> nothing will work.

---

## 1. What this is

This is the Docker install on a Linux server, and it is **the recommended home
for a hotel taking live bookings**. The Windows path in
[`INSTALL-en.md`](INSTALL-en.md) drives the same containers through WSL2 and
suits a demonstration or a pilot; it depends on Docker Desktop being started
and a user being logged in. A Linux server does not. The front desk installs
nothing at all and simply opens a web address.

The stack is **ten containers and three volumes**, defined in one file —
[`deploy/linux/docker-compose.yml`](../../../deploy/linux/docker-compose.yml).

| Service | What it is |
| --- | --- |
| `configurator` | a **one-shot**: writes the database and Redis configuration into the shared `sites` volume, then exits |
| `backend` | the application server (gunicorn) |
| `frontend` | nginx — serves the UI and routes requests to the site |
| `websocket` | the realtime channel |
| `queue-short` | background worker, short and default queues |
| `queue-long` | background worker, long, default and short queues |
| `scheduler` | **runs the night audit**, scheduled emails and timed jobs |
| `db` | `mariadb:11.8` |
| `redis-cache` | `redis:8.6-alpine` |
| `redis-queue` | `redis:8.6-alpine` |

| Volume | Holds |
| --- | --- |
| `sites` | site config, the **encryption key**, and every uploaded file including guest ID scans |
| `db-data` | the database |
| `redis-queue-data` | queued jobs |

**The compose file does not build the image.** The image comes from
frappe_docker's `images/layered/Containerfile`, pinned at SHA
`3d0a0e53d8ab03903f6c3f125976a37d7a0f9875`, which is deliberately not copied
into this repository — forking upstream's build would mean maintaining it. So
there are two honest routes, and Section 3 and Section 4 are exactly those two.

Use `docker compose` — the Compose **v2** plugin. Not `docker-compose`. Every
command in this guide assumes v2.

---

## 2. Before you start

Tick every line.

**The server**

- [ ] Linux **x86-64**. The services declare `platform: linux/amd64`, which is
      upstream's choice. On an ARM server every container runs under emulation,
      slowly. **Use x86-64.**
- [ ] Docker Engine with the **Compose v2 plugin** — `docker compose version`
      must succeed, not `docker-compose`
- [ ] `docker buildx version` must succeed. The layered Containerfile uses
      `RUN --mount=type=secret`, which needs BuildKit. Ubuntu's `docker.io`
      package ships without it; `install.sh` tries to install
      `docker-buildx-plugin` for you.
- [ ] **2 vCPU / 4 GB RAM / 40 GB disk** minimum. **8 GB RAM** makes the build
      comfortable — below 8 GB, `install.sh` adds a swap file for the build.
- [ ] Outbound HTTPS from the server (it clones from GitHub during the build)

**Decisions to make before install day**

- [ ] The site name, e.g. `pms.yourhotel.dz`. It must look like a domain —
      the installer rejects anything without a dot.
- [ ] The administrator email address, e.g. `gm@yourhotel.dz`
- [ ] The **administrator password**, generated in your own password manager,
      minimum **10 characters**. See Section 14. There is no default.
- [ ] Which HTTP port to publish. Default **8080**; make sure nothing else uses it.
- [ ] How TLS will be terminated. See Section 9. **Do not serve a hotel over
      plain HTTP.**

**Time**

- [ ] **The first build takes 20 to 45 minutes**, and longer on a slow disk or
      connection. This is not a hung progress bar: the image is **built locally
      on this server**, not pulled ready-made. There is no registry to pull
      from, which is why the pull policy is `never`. Do not schedule the install
      for the half hour before check-in.

---

## 3. Route A — the scripted install

This is the simplest correct path on a fresh server. `install.sh` fetches
frappe_docker at the pinned SHA, builds the image, creates the site, installs
`payments` and `kamra`, runs first-boot wiring, and leaves the stack running.

> ### ⚠ The two environment variables are not optional
>
> `install.sh` defaults to **upstream Kamra on `main`**. Without these two
> overrides, a 20–45 minute build produces upstream software with **no Algerian
> localization in it at all** — no Algeria country pack, no TVA, no NIF, no
> *taxe de séjour*. It will look like a working hotel system. Export both
> before you run anything.

```bash
export KAMRA_GIT_URL=https://github.com/ilyeseia/kamra-pms-algeria
export KAMRA_BRANCH=feature/algeria-hospitality-platform
curl -fsSL https://raw.githubusercontent.com/ilyeseia/kamra-pms-algeria/feature/algeria-hospitality-platform/deploy/install.sh -o install.sh
```

Read the script before running it. Then:

```bash
sudo bash install.sh
```

It will ask for the site domain, an admin email and an admin password (minimum
10 characters, read straight from the console, never written to a log). Then
wait. 20 to 45 minutes is normal.

**The source repository is cloned from inside the build container, with no
credentials.** It must therefore be publicly readable, or the build fails
part-way through. If the build dies while fetching the app, that is the first
thing to check.

When it finishes, `install.sh` prints the sign-in address, and has left:

| | |
| --- | --- |
| Stack directory | `/opt/kamra` |
| Environment file | `/opt/kamra/kamra.env` (mode 600 — it holds the database password) |
| Recorded apps | `/opt/kamra/apps.json` |
| frappe_docker clone | `/opt/kamra/frappe_docker` |
| A copy of itself | `/opt/kamra/install.sh`, so updates work later |

Go to Section 7 to create the property.

### Why you might still want Section 4 afterwards

`install.sh` drives compose through a four-flag invocation from inside the
frappe_docker clone:

```bash
docker compose --project-name kamra --env-file /opt/kamra/kamra.env -f compose.yaml -f overrides/compose.mariadb.yaml -f overrides/compose.redis.yaml -f overrides/compose.noproxy.yaml ps
```

All four `-f` options, the project name and the env file are required; a plain
`docker compose ps` will not find that stack. `deploy/linux/docker-compose.yml`
is the flattened equivalent of that invocation, so that day-to-day work is just
`docker compose up -d` with nothing cloned. Moving an existing install over is
covered in Section 5.

---

## 4. Route B — build the image, then `docker compose up -d`

Take this route if you want `deploy/linux/` to be the whole story. You build
the image once by hand, then everything afterwards is plain `docker compose`.

This is exactly what `install.sh` does internally. Get frappe_docker at the
pinned SHA:

```bash
git clone --depth 1 https://github.com/frappe/frappe_docker.git /tmp/frappe_docker
cd /tmp/frappe_docker
git fetch --depth 1 origin 3d0a0e53d8ab03903f6c3f125976a37d7a0f9875 && git checkout --force FETCH_HEAD
```

Write the apps list. **The second entry is the Algeria distribution** — this is
the same thing the two environment variables do in Route A, and getting it wrong
has the same consequence:

```bash
cat > /tmp/apps.json <<'EOF'
[
  {"url": "https://github.com/frappe/payments", "branch": "develop"},
  {"url": "https://github.com/ilyeseia/kamra-pms-algeria", "branch": "feature/algeria-hospitality-platform"}
]
EOF
```

Build:

```bash
DOCKER_BUILDKIT=1 docker build -t kamra:local \
  -f images/layered/Containerfile \
  --build-arg FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg FRAPPE_BRANCH=version-16 \
  --build-arg CACHE_BUST="$(date +%s)" \
  --secret id=apps_json,src=/tmp/apps.json .
```

The repository in `apps.json` is cloned **from inside the container, with no
credentials**, so it must be publicly readable or the build fails part-way.

Then configure `.env` (Section 5), start the stack (Section 6), and create the
site by hand — `install.sh` does that step for you, Route B does not:

```bash
docker compose exec backend bench new-site pms.yourhotel.dz --no-mariadb-socket --mariadb-user-host-login-scope='%' --db-root-password "$DB_PASSWORD" --install-app payments --install-app kamra
```

```bash
docker compose exec backend bench --site pms.yourhotel.dz execute kamra.scripts.first_boot.execute
```

Substitute your own site name in both. `FRAPPE_SITE_NAME_HEADER` in `.env` must
equal that site name **exactly** — see Section 5.

---

## 5. Configure `.env`

From `deploy/linux/`:

```bash
cp .env.example .env
```

Then edit `.env`. Read `.env.example` itself — every variable is commented with
why it is there. **Two are required**, and the stack will not start without
them.

### `DB_PASSWORD`

The MariaDB root password. **It has no default on purpose.** Upstream's fallback
is `123`, and that is not a password a hotel database should quietly end up
with, so the stack refuses to start instead of inheriting it. You will see
`DB_PASSWORD is required` on `up` if it is missing or empty. That is the file
working correctly.

Generate one:

```bash
openssl rand -hex 16
```

### `FRAPPE_SITE_NAME_HEADER`

**This must equal the Frappe site name exactly.** nginx routes on this header.
If it does not match, every single URL returns 404 against a site that exists
and is perfectly healthy. This is **the most common cause of "it installed but
shows nothing"** — if you see that symptom, check this variable first, before
anything else.

```
FRAPPE_SITE_NAME_HEADER=pms.yourhotel.dz
```

Exactly the name you passed to `bench new-site`, or exactly the site domain you
typed at the `install.sh` prompt. Not a variant, not with a port, not with
`https://`.

### Moving an existing `install.sh` install into `deploy/linux/`

An install made by `install.sh` **already has this file**, written for you, at
`/opt/kamra/kamra.env`. **Copy it. Do not write a new password.**

```bash
cp /opt/kamra/kamra.env .env
```

MariaDB keeps the password its `db-data` volume was initialised with. A fresh
`DB_PASSWORD` against an existing volume does not change the database password —
it simply locks you out, and you will get `Access denied for root`. If that
happens, restore the old `DB_PASSWORD`.

### The rest, briefly

| Variable | Notes |
| --- | --- |
| `CUSTOM_IMAGE` / `CUSTOM_TAG` | `kamra` / `local` — the locally built image |
| `PULL_POLICY` | `never`. There is no registry to pull from. |
| `HTTP_PUBLISH_PORT` | the host port nginx is published on, default `8080` |
| `NGINX_LISTEN_PORT` | the port inside the container. Leave it alone. |
| `UPSTREAM_REAL_IP_ADDRESS`, `UPSTREAM_REAL_IP_HEADER`, `UPSTREAM_REAL_IP_RECURSIVE` | commented out by default; see Section 9 |
| `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT` | raise only on a busy property with RAM to spare. Each worker is a process holding a full Python app — do not raise them on a 4 GB box. |
| `CLIENT_MAX_BODY_SIZE` | upload ceiling, default `50m`. Guest ID scans and room photos go through it. |
| `RESTART_POLICY` | `unless-stopped`, which keeps the hotel running across a reboot. Use `no` only while debugging. |

**Never commit `.env`.** It holds the database root password. The repository's
`.gitignore` already excludes `.env` and `.env.*` — keep it that way. And back
it up, as a secret, in a password manager: lose it and a database dump may be
unrestorable.

---

## 6. Start it, and check `configurator`

```bash
docker compose up -d
```

Then, immediately:

```bash
docker compose ps
```

> ### `configurator` must read `Exited (0)`
>
> **This is the single best diagnostic in the whole stack, and it deserves its
> own step.**
>
> `configurator` is a one-shot container. It writes the database and Redis host
> configuration into the shared `sites` volume and then exits. Every other
> service waits for it to **complete successfully** before it will start.
>
> - If it reads `Exited (0)`, the plumbing is correct and the rest of the stack
>   comes up behind it.
> - If it reads anything else — still running, restarting, `Exited (1)` —
>   **nothing else will start**, and you will see a stack that appears to be
>   doing something while serving nothing.
>
> Its log says why, in plain terms:
>
> ```bash
> docker compose logs configurator
> ```
>
> Most often it is the database password. `configurator` waits for MariaDB to
> pass its healthcheck, not merely to start, because `bench set-config` against
> a half-initialised MariaDB is how a first install fails confusingly.

Once `configurator` is `Exited (0)` and the others are up, watch the backend
come to life:

```bash
docker compose logs -f backend
```

---

## 7. Create the property

Open, substituting your server's address:

```
http://<host>:8080/kamra
```

If you changed `HTTP_PUBLISH_PORT`, substitute your port; **the `/kamra` part of
the address never changes.**

Sign in as `Administrator` with the password you set during the install. Then
open the setup wizard:

```
http://<host>:8080/kamra/setup
```

Create your property — name, address, contact details, rooms.

### Choose Algeria as the country

**This is the single most important field in the wizard, and getting it wrong
fails silently.**

- Pick **Algeria** from the country list. Not a variant spelling, not the French
  or Arabic name — the entry that reads `Algeria`.
- Then confirm, on screen: amounts display with **DA**, and the tax column is
  labelled **TVA** (not VAT, not GST).
- Also confirm the property form offers **NIF**, plus **RC**, **NIS** and **AI**,
  and that the room levy is labelled **Taxe de séjour**.
- Confirm the time zone list contains **`Africa/Algiers`**.

**If Algeria does not appear in the country list at all, the image was built
from upstream.** Stop. Do not enter any data. Check `apps.json` — the second
entry must be `https://github.com/ilyeseia/kamra-pms-algeria` on branch
`feature/algeria-hospitality-platform` — and rebuild the image. A build that
silently used upstream will look like a working hotel system while containing
none of the Algerian work.

If the country is left blank or misspelled, the system falls back to another
country's tax vocabulary without warning you — wrong currency, a tax column
labelled GST. So verify what is on screen; do not assume what you typed was
stored.

### The tax rates

The TVA rates the system offers (19% standard, 9% reduced) and the *taxe de
séjour* amount are **configurable defaults, not legal advice.** Which rate
applies to your accommodation and to your food and beverage outlets depends on
the finance law, the outlet, and your hotel's classification.

**Your accountant must confirm the treatment before you issue the first real
invoice.** Set the rate on each Room Type as data, not in code. For the *taxe de
séjour*, set the mode to **Fixed per person per night** and enter your
municipality's amount. See [`TAXES.md`](../TAXES.md) for the full picture.

---

## 8. Verify it works

Do not call the install done because the login page loaded.

1. **`docker compose ps`** — `configurator` is `Exited (0)`; `backend`,
   `frontend`, `websocket`, `queue-short`, `queue-long`, `scheduler`, `db`,
   `redis-cache` and `redis-queue` are all up.
2. **The login page loads** at `http://<host>:8080/kamra` and you can sign in as
   `Administrator`.
3. **Algeria, DA and TVA** are confirmed on screen, as in Section 7, and the time
   zone list contains `Africa/Algiers`.
4. **A reservation saves.** Create a throwaway reservation, save it, reopen it.
   This is the first honest proof the database is healthy — see Section 15.
5. **A night posts and an invoice prints.** Post a night on that reservation and
   print the folio. Check the footer carries whichever of **RC · NIF · NIS · AI**
   you filled in, and that the amount in words reads *Dinars …* rather than
   *DZD …*.
6. **Delete the throwaway reservation** afterwards, before staff start entering
   real data.
7. **The scheduler is running.** The night audit (03:00 site time) and the
   housekeeping escalations are scheduled jobs. A site whose scheduler is off
   looks perfectly fine all day and then silently never closes the night:

   ```bash
   docker compose exec backend bench --site <your-site-name> doctor
   ```

8. **No demo accounts exist.** See Section 14. This is the check that matters
   most; do not accept the system until it passes.

---

## 9. TLS and exposing it safely

`frontend` publishes **plain HTTP** straight to the host port. It terminates no
TLS. That comes from upstream's `noproxy` override and it is the right default
for a file you put your own proxy in front of — it is not a suggestion that you
run it that way.

> **Do not serve a hotel over plain HTTP.** Guest identity documents, card
> references, folios and staff passwords all cross that connection.

Put **nginx** or **Caddy** in front, terminate TLS there, and proxy to
`127.0.0.1:8080`. Do not expose port 8080 to the internet directly — bind it to
localhost or firewall it, and let only the proxy reach it.

`install.sh` prints the usual one-liner for the certificate once DNS points at
the server:

```bash
certbot --nginx -d pms.yourhotel.dz
```

Once a proxy is in front, Frappe sees the proxy's address as the client address
for every request, which makes rate limiting and the audit trail useless. The
three `UPSTREAM_REAL_IP_*` variables exist for exactly this; they are commented
out in `.env.example`. Set `UPSTREAM_REAL_IP_ADDRESS` to the **proxy's** address:

```
UPSTREAM_REAL_IP_ADDRESS=127.0.0.1
UPSTREAM_REAL_IP_HEADER=X-Forwarded-For
UPSTREAM_REAL_IP_RECURSIVE=off
```

---

## 10. Day-to-day

Run these from `deploy/linux/`, the directory holding `docker-compose.yml` and
`.env`.

| | |
| --- | --- |
| Status | `docker compose ps` |
| Logs | `docker compose logs -f backend` |
| A shell | `docker compose exec backend bash` |
| Restart | `docker compose restart backend frontend` |
| Stop (keeps data) | `docker compose down` |
| Backup | `docker compose exec backend bench --site <site> backup --with-files` |
| Migrate after an update | `docker compose exec backend bench --site all migrate` |
| Is the scheduler alive? | `docker compose exec backend bench --site <site> doctor` |

`docker compose down` leaves all three volumes in place. **`docker compose
down -v` does not.** See Section 13.

---

## 11. Backups

A property management system holds the only record of who is arriving tonight,
what they agreed to pay, what they have already paid, and what the hotel owes
the tax authority. Losing it is not an IT inconvenience.

```bash
docker compose exec backend bench --site <your-site-name> backup --with-files
```

**The one rule: a backup nobody has restored is not a backup. It is a file.**

Perform a full restore test before handover and once a quarter after. Restore
into a separate throwaway site, confirm reservations, money **and uploaded
files** came back, and **write down what you had to do**. That note is the
runbook someone uses at 2am. Full procedures — scheduling, retention, getting
archives off the machine, and the restore test itself — are in
[`BACKUP.md`](../BACKUP.md). Read it before go-live, not after.

Three things from `BACKUP.md` worth repeating here:

- Always back up **with files** (`--with-files`). A database-only backup restores
  a hotel whose guest ID scans, signed registration cards and invoice
  attachments have all vanished — which for an Algerian house keeping a *fiche
  de police* trail is a compliance problem, not a partial backup.
- **Back up `.env` (and `/opt/kamra/kamra.env` if it exists).** It holds the
  database password. Lose it and a database dump may be unrestorable.
- **Back up before every update**, without exception. An update runs database
  migrations, and migrations are not reversible — rollback means restore.

On a Linux host, scheduling is root's crontab and nothing more:

```cron
30 3 * * * /opt/kamra/backup.sh >> /var/log/kamra-backup.log 2>&1
```

`BACKUP.md` §6 has the script that line runs. No Docker Desktop, no logged-in
user, no sleeping laptop — which is most of why a Linux server is the
recommended profile.

---

## 12. Updating

**Back up first. Every time.** An update rebuilds the image and runs database
migrations, and migrations are not reversible.

If you installed with `install.sh`:

```bash
sudo /opt/kamra/install.sh update
```

That rebuilds the image from the recorded `apps.json`, recreates the containers,
and runs `bench --site all migrate` and `clear-cache` for you.

If you are on Route B, rebuild the image with the `docker build` command in
Section 4, then:

```bash
docker compose up -d && docker compose exec backend bench --site all migrate
```

Afterwards, work back through Section 8. An update that leaves the scheduler
down is an update that stopped the night audit.

---

## 13. The data lives in volumes

Not in the `deploy/linux/` directory. Copying that directory elsewhere copies
nothing of the hotel.

| Volume | Holds |
| --- | --- |
| `sites` | site config, the **encryption key**, and every uploaded file including guest ID scans |
| `db-data` | the database |
| `redis-queue-data` | queued jobs |

> ### ⚠ `docker compose down -v` destroys the data
>
> `docker compose down` stops the containers and **leaves all three volumes**.
> That is the safe one, and it is the one you want.
>
> `docker compose down -v` **destroys `sites` and `db-data`**. For a live
> property that is every reservation, every folio and every guest record, plus
> the encryption key and the guest ID scans. **There is no undo.** No
> confirmation prompt either.
>
> Never type `-v` on a property server unless you have just verified a restore
> works and you intend exactly that.

---

## 14. Security

### The administrator password

- `install.sh` prompts for it and reads it **straight from the console**. It
  never enters an environment variable, a log file, or your shell history.
- Minimum **10 characters**. **There is no default anywhere in this system.**
- **Choose it yourself**, in your own password manager, and hold it yourself.
- **After handover, do not share it with the vendor** — and if the vendor still
  holds a copy, ask them to destroy it. Nobody outside the hotel needs the
  administrator password of the system that holds your guests' identity
  documents.

### A production site must never have the demo accounts

> ### ⚠ WARNING — read this before you seed anything
>
> Seeding sample data creates **six user accounts whose passwords are published
> in the product's public source code**. One of them is a **full system
> administrator**.
>
> Those passwords are also compiled into the JavaScript bundle that every
> visitor to the site downloads. Turning `demo_mode` off only hides the one-tap
> demo login buttons — **it does not invalidate the passwords**. Hiding a button
> is not security.
>
> **The only real protection is that the accounts do not exist.**
>
> `install.sh` seeds nothing and creates none of them, and neither does
> `bench new-site` in Route B. So:
>
> - **Never seed sample data on a live site**, not even "just to have something
>   to show".
> - **Never create those accounts by hand.**
> - If a site was already seeded and must now go live, treat it as
>   **compromised**: have the six accounts *deleted* (not merely given new
>   passwords), the `Administrator` password rotated, and the access logs
>   audited.

To confirm a production site is clean, no account may exist whose address ends
in `@kamra.local`. Your vendor can run that check for you; ask to see the
output. It must come back **empty** — not "the passwords were changed", empty.

### Other things to settle before go-live

- **Put HTTPS in front of the site** (Section 9) and do not expose port 8080 to
  the internet directly.
- **`.env` must stay mode 600 and must never be committed.** It holds the
  database root password. `install.sh` writes `/opt/kamra/kamra.env` under
  `umask 077` for the same reason.
- **Create named staff accounts** with the right roles (Hotel Admin, Front Desk,
  Revenue, Finance, Housekeeping) rather than sharing one login.

---

## 15. What is not yet proven

This section is here because a supplier who hides these is selling you a
liability. None of it is speculative, and none of it is a reason to panic. It is
a list of things your own first days of use will settle.

- **This compose file has never been started.** It was checked against
  upstream's four files service-by-service — the set of services, the images,
  the commands, the ports, the healthchecks, the environment keys and the
  volumes all match — but there is **no Docker daemon on the machine it was
  written on**. So `docker compose config` never validated it, and no container
  has ever run from it. **Your first `docker compose up -d` is the real test.**
  What to do: run it somewhere disposable before you run it on the property
  server, and read `docker compose logs configurator` the moment anything looks
  wrong.

- **Migrations `v36` and `v37` have never run against a database.** One handles
  the fixed per-person *taxe de séjour* basis, the other the RC/NIS/AI Property
  fields. Neither had executed against an actual database anywhere. If your
  install completed, **they have just run for the first time.** What to do:
  verify a reservation saves (Section 8, item 4), and **take a backup before
  every future update**, which also runs migrations.

- **Nobody has viewed the Arabic right-to-left layout in a browser.** The RTL
  work is written and type-checks correctly as far as reading the code can
  establish, but no one has rendered it on screen and looked at it. The same is
  open for the French, Arabic and English print layouts. What to do: have
  someone who reads Arabic click through the front desk, the guest booking page
  and a printed invoice before go-live. Expect to find things. They are very
  likely cosmetic rather than arithmetic — but a hotel is judged on what a guest
  sees.

- **Money renders `DA 1 500`; Algerian convention is `1 500,00 DA`.** The
  amount, the separators and the symbol are all correct — only the position is
  not. So nothing is ambiguous or wrong; it simply is not how a local accountant
  writes it. This was **deliberately deferred**, with the cost measured rather
  than guessed: the symbol position is not a setting but is baked into 233 money
  display sites across the product, including printed invoices, and a partial
  migration would be worse than none — one screen reading `DA 1 500` while
  another reads `1 500 DA` is a defect in a way that consistent non-convention
  is not. Recorded as limitation 19 in
  [`IMPLEMENTATION_STATUS.md`](../IMPLEMENTATION_STATUS.md), with the sequenced
  plan for doing it properly once screens can actually be looked at.

- **No automated backend test has ever run against a real site.** The quality
  gate on this release was static analysis and arithmetic checks, not an
  executed test suite. Treat your first install as the test, and budget time
  for it.

`IMPLEMENTATION_STATUS.md` carries the full list, including the tax-exempt room
type that cannot be expressed today and the percentage-mode levy defect with
discount vouchers (use **Fixed per person per night** mode, which is unaffected
and is what an Algerian house wants anyway).

---

## 16. Troubleshooting

| Symptom | Usually |
| --- | --- |
| Every URL 404s but the site exists | **`FRAPPE_SITE_NAME_HEADER` does not match the site name.** Check this first. |
| Nothing starts; `configurator` is not `Exited (0)` | read `docker compose logs configurator` — most often the database password |
| `DB_PASSWORD is required` on `up` | no `.env`, or the variable is empty. Intended — see Section 5. |
| `Access denied for root` after changing `.env` | MariaDB kept the password its `db-data` volume was initialised with; restore the old `DB_PASSWORD` |
| **Algeria missing from the setup country list** | the image was built from upstream — check `apps.json` and rebuild. See Section 7. |
| Prices in a foreign currency, tax reads GST | the property's country was left **blank**, so another country's pack loaded |
| No TVA label, no *Taxe de séjour* | the property's country is **misspelled**. It must read exactly `Algeria`. |
| The night audit never runs | the `scheduler` container is down |
| Build fails while fetching the app | the source repository is not publicly readable — it is cloned from inside the container with no credentials |
| Build killed, or out of memory | below the RAM floor; `install.sh` adds a swap file, a hand build does not |
| `docker build failed` after a long run | usually a full disk. 40 GB is the minimum, not the target. |
| Everything is extremely slow | an ARM server emulating `linux/amd64`. Use x86-64. |
| `docker-compose: command not found` | you need the Compose **v2** plugin — `docker compose`, two words |
| `docker buildx is required` | BuildKit is missing; the layered Containerfile needs it (`apt install docker-buildx-plugin`) |
| `ERPNEXT_VERSION` warnings during install | harmless noise from the underlying container files |

More in [`deploy/TROUBLESHOOTING.md`](../../../deploy/TROUBLESHOOTING.md) and
[`deploy/linux/README.md`](../../../deploy/linux/README.md).

---

## 17. Getting help

Before you contact support, gather this. Without it, the first reply will only
be a request for it.

**Always include the product name and both version numbers:**

```
Hotel MgM
Algeria Distribution 1.0.0
on Kamra core 2.6.5
```

Both numbers matter. "Kamra core 2.6.5" on its own does not say whether the
Algeria pack is installed, and the distribution number on its own does not say
which core it sits on.

**Then add:**

- Which route you used — **A (`install.sh`)** or **B (hand build + `docker
  compose`)**
- The output of `docker compose ps`, as text — including what state
  `configurator` is in
- `docker compose logs configurator` and `docker compose logs backend`
- The exact command you ran, copied from the terminal
- Your site name, the value of `FRAPPE_SITE_NAME_HEADER`, and the published port
- The Linux distribution and version, `docker compose version`, the CPU
  architecture (`uname -m`), and how much RAM and free disk the server has
- The exact error text, copied as text rather than described or photographed
- At what point it failed — image build, `up`, `configurator`, site creation,
  first login, the setup wizard
- Whether it ever worked, and what changed since

**If the problem is about money or tax on a document**, attach the printed
invoice or folio and say which figure you expected and why.

**Never include the administrator password or the contents of `.env`**, and
never send either to anyone who asks for them — including someone claiming to be
your supplier. Support never needs them.

---

## See also

- [`INSTALL-en.md`](INSTALL-en.md) — the Windows 10 / WSL2 install
- [`USER-en.md`](USER-en.md) — the day-to-day user guide
- [`../BACKUP.md`](../BACKUP.md) — backup, restore, scheduling, and the restore test
- [`../TAXES.md`](../TAXES.md) — TVA, *taxe de séjour*, and the legal identifiers
- [`../IMPLEMENTATION_STATUS.md`](../IMPLEMENTATION_STATUS.md) — the full list of what is and is not proven
- [`../VERSIONING.md`](../VERSIONING.md) — what the two version numbers mean
- [`../../../deploy/linux/README.md`](../../../deploy/linux/README.md) — the operator reference this guide distils
- [`DOCKER-fr.md`](DOCKER-fr.md) — this guide in French
- [`DOCKER-ar.md`](DOCKER-ar.md) — this guide in Arabic
