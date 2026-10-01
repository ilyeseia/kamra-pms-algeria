# Hotel MgM on Linux — Docker Compose

A self-contained `docker-compose.yml` for running the stack on a Linux server.
This is the recommended home for a hotel taking live bookings; the Windows
path in [`../windows/`](../windows/) drives the same containers through WSL2
and suits a demo or a pilot.

## What this is, and what it is not

`docker-compose.yml` here is the **flattened equivalent** of what
[`../install.sh`](../install.sh) runs — frappe_docker's `compose.yaml` merged
with its `mariadb`, `redis` and `noproxy` overrides. Every service, image tag,
command, healthcheck and environment variable was read out of frappe_docker at
the SHA this distribution pins (`3d0a0e5`), not reconstructed from memory.

**It does not build the image.** The image comes from frappe_docker's
`images/layered/Containerfile`, which is deliberately not copied into this
repository — forking upstream's build would mean maintaining it. So there are
two honest routes:

| | Use when |
| --- | --- |
| `install.sh` | A fresh server. It fetches frappe_docker, builds the image, creates the site and wires first boot. |
| This directory | You already have the image, or you built it with the command below, and you want plain `docker compose` for day-to-day work. |

Either way, once the image exists, everything below works with no frappe_docker
clone present.

## Prerequisites

- Linux x86-64, Docker Engine with the Compose v2 plugin (`docker compose`, not
  `docker-compose`)
- 2 vCPU / 4 GB RAM / 40 GB disk minimum; 8 GB makes the build comfortable
- The services declare `platform: linux/amd64`, upstream's choice. On an ARM
  server every container runs under emulation — slowly. Use x86-64.

## First install, from nothing

The simplest correct path is still the project installer:

```bash
export KAMRA_GIT_URL=https://github.com/ilyeseia/kamra-pms-algeria
export KAMRA_BRANCH=feature/algeria-hospitality-platform
curl -fsSL https://raw.githubusercontent.com/ilyeseia/kamra-pms-algeria/feature/algeria-hospitality-platform/deploy/install.sh -o install.sh
```

Read it, then run it:

```bash
sudo bash install.sh
```

**Those two environment variables are not optional.** `install.sh` defaults to
upstream Kamra on `main`; without the overrides a 20–45 minute build produces
upstream with no Algerian localization in it at all.

It will ask for the site domain, an admin email and an admin password
(10 characters minimum, no default). Then see
[`../../docs/algeria/INSTALLATION.md`](../../docs/algeria/INSTALLATION.md).

## Building the image by hand

If you want this directory to be the whole story, build the image yourself
once. This is exactly what `install.sh` does:

```bash
git clone --depth 1 https://github.com/frappe/frappe_docker.git /tmp/frappe_docker
cd /tmp/frappe_docker
git fetch --depth 1 origin 3d0a0e53d8ab03903f6c3f125976a37d7a0f9875 && git checkout --force FETCH_HEAD
```

```bash
cat > /tmp/apps.json <<'EOF'
[
  {"url": "https://github.com/frappe/payments", "branch": "develop"},
  {"url": "https://github.com/ilyeseia/kamra-pms-algeria", "branch": "feature/algeria-hospitality-platform"}
]
EOF
```

```bash
DOCKER_BUILDKIT=1 docker build -t kamra:local \
  -f images/layered/Containerfile \
  --build-arg FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg FRAPPE_BRANCH=version-16 \
  --build-arg CACHE_BUST="$(date +%s)" \
  --secret id=apps_json,src=/tmp/apps.json .
```

The repository in `apps.json` is cloned **from inside the container, with no
credentials**, so it must be publicly readable or the build fails partway.

## Running it

```bash
cp .env.example .env
```

Edit `.env` — `DB_PASSWORD` and `FRAPPE_SITE_NAME_HEADER` are required. Then:

```bash
docker compose up -d
```

Watch the one-shot configurator finish before anything else starts:

```bash
docker compose ps
```

`configurator` must read `Exited (0)`. If it is anything else, nothing else
will start, and its log says why:

```bash
docker compose logs configurator
```

### Moving an existing install here

```bash
cp /opt/kamra/kamra.env .env
```

Copy it rather than writing a new password: MariaDB keeps the password its
`db-data` volume was initialised with, so a fresh `DB_PASSWORD` simply locks
you out.

## Creating the site, if you built the image by hand

`install.sh` does this for you. By hand:

```bash
docker compose exec backend bench new-site pms.yourhotel.dz --no-mariadb-socket --mariadb-user-host-login-scope='%' --db-root-password "$DB_PASSWORD" --install-app payments --install-app kamra
```

```bash
docker compose exec backend bench --site pms.yourhotel.dz execute kamra.scripts.first_boot.execute
```

`FRAPPE_SITE_NAME_HEADER` in `.env` must equal that site name exactly.

## Day-to-day

| | |
| --- | --- |
| Status | `docker compose ps` |
| Logs | `docker compose logs -f backend` |
| A shell | `docker compose exec backend bash` |
| Restart | `docker compose restart backend frontend` |
| Stop (keeps data) | `docker compose down` |
| Backup | `docker compose exec backend bench --site <site> backup --with-files` |
| Migrate after an update | `docker compose exec backend bench --site all migrate` |

Back up before every update: updates run migrations. See
[`../../docs/algeria/BACKUP.md`](../../docs/algeria/BACKUP.md) — and test a
restore, because a backup nobody has restored is not a backup.

## Updating

```bash
sudo /opt/kamra/install.sh update
```

That rebuilds the image from `apps.json`, recreates the containers and runs
`bench --site all migrate`. If you are not using `install.sh`, rebuild the
image with the command above, then:

```bash
docker compose up -d && docker compose exec backend bench --site all migrate
```

## The data lives in volumes, not in this directory

| Volume | Holds |
| --- | --- |
| `sites` | site config, the **encryption key**, and every uploaded file including guest ID scans |
| `db-data` | the database |
| `redis-queue-data` | queued jobs |

`docker compose down` leaves all three. `docker compose down -v` **destroys
them**, which for a live property means every reservation, folio and guest
record. There is no undo. Check your restore works before you ever type it.

## If something is wrong

| Symptom | Usually |
| --- | --- |
| Every URL 404s but the site exists | `FRAPPE_SITE_NAME_HEADER` does not match the site name |
| Nothing starts; `configurator` is not `Exited (0)` | read `docker compose logs configurator`; most often the database password |
| `DB_PASSWORD is required` on `up` | no `.env`, or the variable is empty — intended, see `.env.example` |
| Access denied for root after changing `.env` | MariaDB kept the original password; restore the old `DB_PASSWORD` |
| Night audit never runs | the `scheduler` container is down |
| Algeria missing from the setup country list | the image was built from upstream — check `apps.json` and rebuild |
| Build fails fetching the app | the source repository is not publicly readable |

More in [`../TROUBLESHOOTING.md`](../TROUBLESHOOTING.md).

## Keeping this file honest

If `FRAPPE_DOCKER_REF` in `install.sh` ever moves, this flattened file can
drift from it silently. Re-derive instead of hand-editing — run this inside a
frappe_docker checkout at the new ref and diff against `docker-compose.yml`:

```bash
docker compose -f compose.yaml -f overrides/compose.mariadb.yaml -f overrides/compose.redis.yaml -f overrides/compose.noproxy.yaml config
```

Two places here depart from upstream on purpose, both noted in the file:
`MYSQL_ROOT_PASSWORD` has no `123` fallback and fails loudly instead, and
`configurator` waits for the database healthcheck explicitly rather than
relying on override merge order.

## Not yet proven

This compose file has been checked against upstream's four files
service-by-service — set, images, commands, ports, healthchecks, environment
keys and volumes all match — but **it has never been started**. There is no
Docker daemon on the machine it was written on, so `docker compose config`
never validated it and no container has ever run from it. Treat the first
`docker compose up -d` as the real test, and read
[`../../docs/algeria/IMPLEMENTATION_STATUS.md`](../../docs/algeria/IMPLEMENTATION_STATUS.md)
for what else is unproven — notably that migrations `v36` and `v37` have never
touched a database.
