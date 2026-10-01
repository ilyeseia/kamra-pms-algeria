#!/usr/bin/env bash
# ZIRI — self-host install (build the image on this machine, then compose up).
#
#   curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | bash
#
# Or: clone the repo, cd deploy, ./install.sh
#
# Builds Frappe + payments + kamra locally via frappe_docker's layered
# Containerfile. Does NOT pull from ghcr.io (kept private for Kamra's own
# demo/nightly hosts). First install often takes 20–45 minutes.
#
# Asks three things (or reads env): SITE_NAME, ADMIN_EMAIL, ADMIN_PASSWORD.
# Creates the Frappe site, installs payments + kamra, enables the scheduler,
# points / at /kamra. There is no default password.
#
# Modes:
#   install.sh            install (safe to re-run; reuses DB password + site)
#   install.sh update     rebuild the image from apps.json, restart, migrate
#   install.sh build      build the image only (Packer / 1-Click snapshots)
#
# The installer copies itself to $INSTALL_DIR/install.sh, so updates are:
#   sudo /opt/kamra/install.sh update
set -euo pipefail

# Absolute path of this script (empty when piped via curl | bash); resolved
# now because later steps cd into frappe_docker.
SELF=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
fi

MODE="${1:-install}"
case "$MODE" in
  install|update|build) ;;
  *) echo "usage: install.sh [install|update|build]" >&2; exit 2 ;;
esac

KAMRA_IMAGE="${KAMRA_IMAGE:-kamra}"
KAMRA_TAG="${KAMRA_TAG:-local}"
# THIS distribution, not upstream. The default used to be upstream Kamra,
# which meant `install.sh update` on a ZIRI server rebuilt the site from a
# repository that has none of the Algeria localization in it - no country
# pack, no wilayas or communes, no DZD - and did so reporting success.
# deploy/linux/README.md had to warn in bold that two environment variables
# were "not optional"; a default that destroys the product unless the
# operator remembers to override it is not a default worth keeping.
KAMRA_GIT_URL="${KAMRA_GIT_URL:-https://github.com/ilyeseia/kamra-pms-algeria}"
KAMRA_BRANCH_OVERRIDE="${KAMRA_BRANCH:-}"
KAMRA_BRANCH="${KAMRA_BRANCH:-main}"
FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-16}"
FRAPPE_PATH="${FRAPPE_PATH:-https://github.com/frappe/frappe}"
INSTALL_DIR="${INSTALL_DIR:-/opt/kamra}"
FRAPPE_DOCKER_REPO="${FRAPPE_DOCKER_REPO:-https://github.com/frappe/frappe_docker.git}"
# Pinned so an upstream change can't break every fresh install. Bump
# deliberately after the deploy-smoke CI job passes on the new ref.
FRAPPE_DOCKER_REF="${FRAPPE_DOCKER_REF:-3d0a0e53d8ab03903f6c3f125976a37d7a0f9875}"
FORCE_REBUILD="${FORCE_REBUILD:-0}"
MIN_PASSWORD_LEN=10
# Build RAM floor (MiB, RAM + swap). Below this we add a swap file.
BUILD_MEM_MB=8000
ENVFILE="$INSTALL_DIR/kamra.env"
APPS_JSON="$INSTALL_DIR/apps.json"

red() { printf '\033[31m%s\033[0m\n' "$*" >&2; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
die() { red "error: $*"; exit 1; }

need_cmd() { command -v "$1" >/dev/null 2>&1 || die "need '$1' on PATH"; }

# When piped (curl | bash), stdin is the script — reopen the terminal for prompts.
if [ "$MODE" = install ] && [ ! -t 0 ] && [ -z "${SITE_NAME:-}" ]; then
  exec < /dev/tty || die "cannot read prompts (run: bash install.sh, or export SITE_NAME ADMIN_EMAIL ADMIN_PASSWORD)"
fi

prompt() {
  local var="$1" label="$2" secret="${3:-}"
  if [ -n "${!var:-}" ]; then
    return 0
  fi
  if [ -n "$secret" ]; then
    read -r -s -p "$label: " value
    echo
  else
    read -r -p "$label: " value
  fi
  export "$var=$value"
}

echo
echo "  ZIRI — open-source hotel PMS"
echo "  https://kamrapms.com"
echo
echo "  This installer builds the Docker image on THIS server"
echo "  (Frappe + payments + kamra). Plan for 20–45 minutes and"
echo "  40 GB disk. Under 8 GB RAM a swap file is added for the build."
echo

# --- Docker -----------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker not found. Installing Docker Engine…"
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker 2>/dev/null || true
fi
need_cmd docker
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 required (docker compose)"
# layered Containerfile uses RUN --mount=type=secret, which needs BuildKit
# via buildx. Ubuntu's docker.io package ships without it.
if ! docker buildx version >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "Installing docker buildx…"
    DEBIAN_FRONTEND=noninteractive apt-get install -y docker-buildx >/dev/null 2>&1 \
      || DEBIAN_FRONTEND=noninteractive apt-get install -y docker-buildx-plugin >/dev/null 2>&1 || true
  fi
  docker buildx version >/dev/null 2>&1 || die "docker buildx is required (apt install docker-buildx-plugin)"
fi
export DOCKER_BUILDKIT=1

# --- helpers used by every mode ---------------------------------------------
ensure_build_memory() {
  local mem_mb swap_mb need_mb
  mem_mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)
  swap_mb=$(awk '/SwapTotal/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)
  [ "$mem_mb" -gt 0 ] || return 0  # not Linux; let docker decide
  if [ $((mem_mb + swap_mb)) -ge "$BUILD_MEM_MB" ]; then
    return 0
  fi
  need_mb=$((BUILD_MEM_MB - mem_mb - swap_mb))
  [ "$need_mb" -lt 2048 ] && need_mb=2048
  if [ -e /swapfile-kamra ]; then
    swapon /swapfile-kamra 2>/dev/null || true
    return 0
  fi
  echo "Only ${mem_mb} MB RAM + ${swap_mb} MB swap — adding a ${need_mb} MB swap file for the build…"
  if fallocate -l "${need_mb}M" /swapfile-kamra 2>/dev/null \
    || dd if=/dev/zero of=/swapfile-kamra bs=1M count="$need_mb" status=none; then
    chmod 600 /swapfile-kamra
    mkswap /swapfile-kamra >/dev/null
    swapon /swapfile-kamra
    grep -q '^/swapfile-kamra ' /etc/fstab 2>/dev/null \
      || echo '/swapfile-kamra none swap sw 0 0' >> /etc/fstab
  else
    red "warning: could not add swap; the build may run out of memory"
  fi
}

checkout_frappe_docker() {
  mkdir -p "$INSTALL_DIR"
  if [ ! -d "$INSTALL_DIR/frappe_docker/.git" ]; then
    echo "Fetching frappe_docker@${FRAPPE_DOCKER_REF:0:12} → $INSTALL_DIR/frappe_docker"
    git init -q "$INSTALL_DIR/frappe_docker"
    git -C "$INSTALL_DIR/frappe_docker" remote add origin "$FRAPPE_DOCKER_REPO"
  fi
  if [ "$(git -C "$INSTALL_DIR/frappe_docker" rev-parse HEAD 2>/dev/null)" != "$FRAPPE_DOCKER_REF" ]; then
    git -C "$INSTALL_DIR/frappe_docker" fetch -q --depth 1 origin "$FRAPPE_DOCKER_REF"
    git -C "$INSTALL_DIR/frappe_docker" checkout -q --force FETCH_HEAD
  fi
  cd "$INSTALL_DIR/frappe_docker"
  write_kamra_override
}

# Upstream's compose.mariadb.yaml gives the database a 5s start_period, which
# is right for a Linux server where MariaDB is listening almost immediately.
# It is not survivable everywhere: measured on Docker Desktop over WSL2, the
# entrypoint took a full minute to reach "Switching to dedicated user mysql",
# so with 5s plus five 5s retries the container was declared unhealthy roughly
# ninety seconds before it could have answered. Every service waiting on
# `condition: service_healthy` was then cancelled and the install aborted
# mid-way with "dependency failed to start: container db is unhealthy" - on a
# database that was simply still booting.
#
# deploy/linux/docker-compose.yml already carries this fix, but that file is
# the flattened stack for day-to-day operation; this script is the path an
# actual customer installs through, and it reads upstream's overrides straight
# from the frappe_docker checkout. Fixing only the first one left the installer
# exposed, and the Windows installer drives this script.
#
# Written as a separate override rather than by editing upstream's file, so
# `git checkout --force` on a new FRAPPE_DOCKER_REF cannot silently revert it.
# start_period only widens the grace window - failures inside it do not count
# toward `retries`, and the container is healthy the moment one check passes -
# so a fast machine loses nothing.
write_kamra_override() {
  cat > "$INSTALL_DIR/frappe_docker/kamra.override.yaml" <<'EOF'
services:
  db:
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      start_period: 180s
      interval: 5s
      timeout: 5s
      retries: 5
EOF
}

write_apps_json() {
  cat > "$APPS_JSON" <<EOF
[
  {"url": "https://github.com/frappe/payments", "branch": "develop"},
  {"url": "${KAMRA_GIT_URL}", "branch": "${KAMRA_BRANCH}"}
]
EOF
}

# CACHE_BUST changes every run, so Docker re-runs `bench init` and fetches
# the current apps. (The apps.json secret alone does not bust the cache.)
build_image() {
  ensure_build_memory
  echo "Building ${KAMRA_IMAGE}:${KAMRA_TAG} from ${KAMRA_GIT_URL}@${KAMRA_BRANCH}…"
  echo "  (first build downloads the Frappe toolchain — go stretch)"
  docker build \
    -t "${KAMRA_IMAGE}:${KAMRA_TAG}" \
    -f images/layered/Containerfile \
    --build-arg "FRAPPE_PATH=${FRAPPE_PATH}" \
    --build-arg "FRAPPE_BRANCH=${FRAPPE_BRANCH}" \
    --build-arg "CACHE_BUST=${KAMRA_BRANCH}-$(date +%s)" \
    --secret "id=apps_json,src=${APPS_JSON}" \
    . || die "docker build failed — see output above (disk full? out of memory?)"
}

compose() {
  docker compose --project-name kamra --env-file "$ENVFILE" \
    -f compose.yaml \
    -f overrides/compose.mariadb.yaml \
    -f overrides/compose.redis.yaml \
    -f overrides/compose.noproxy.yaml \
    -f kamra.override.yaml "$@"
}

wait_for_backend() {
  echo "Waiting for MariaDB and backend…"
  for _ in $(seq 1 60); do
    if compose exec -T backend bench --version >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  die "backend did not become ready — check: docker compose -p kamra logs"
}

# ── update safety ────────────────────────────────────────────────────────
# `install.sh update` used to build, recreate and migrate with nothing in
# front of it and nothing behind it. The three things that go wrong on a
# hotel server are all preventable here: updating onto a full disk, updating
# with no way back, and updating a database with no recent backup.
#
# ZIRI_FORCE=1 skips the gate. It exists because a support engineer at 02:00
# with a hotel down sometimes has to, and refusing absolutely would just get
# the script edited. It is not a flag to put in a runbook.

# How much free space the image build and the backup need, in GB. The build
# alone pulls several GB of layers; 12 is the figure install.sh has always
# used for a fresh install, so the update should not pretend to need less.
UPDATE_MIN_FREE_GB="${UPDATE_MIN_FREE_GB:-12}"
# A backup older than this is not protection against what this update is about
# to do.
UPDATE_MAX_BACKUP_AGE_H="${UPDATE_MAX_BACKUP_AGE_H:-24}"

gate_fail() {
  red "PRE-FLIGHT FAILED: $*"
  red "The update has NOT been applied and nothing has changed."
  red "Fix it, or re-run with ZIRI_FORCE=1 if you accept the risk."
  exit 1
}

preflight() {
  echo "Pre-flight…"

  # disk - the build writes layers and the backup writes a dump; running out
  # halfway leaves a half-pulled image and a site that will not start
  local free_gb
  free_gb=$(df -BG --output=avail /var/lib/docker 2>/dev/null | tail -1 | tr -dc '0-9')
  [ -n "$free_gb" ] || free_gb=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
  if [ "${free_gb:-0}" -lt "$UPDATE_MIN_FREE_GB" ]; then
    gate_fail "${free_gb}GB free where Docker stores images; need ${UPDATE_MIN_FREE_GB}GB"
  fi
  echo "  disk: ${free_gb}GB free"

  # the stack has to be answering before we touch it, or "it broke after the
  # update" will be impossible to tell from "it was already broken"
  compose exec -T backend bench --version >/dev/null 2>&1     || gate_fail "the backend is not responding; fix the running stack first"
  echo "  backend: responding"

  compose exec -T db healthcheck.sh --connect --innodb_initialized >/dev/null 2>&1     || gate_fail "the database is not healthy"
  echo "  database: healthy"

  # a backup, and a recent one. This is the check the whole gate exists for:
  # the migrate step below is the only part of an update that cannot simply be
  # rolled back by putting the old image back.
  local newest age_h
  newest=$(compose exec -T backend bash -lc 'ls -t /home/frappe/frappe-bench/sites/*/private/backups/*-database.sql.gz 2>/dev/null | head -1' | tr -d '\r')
  if [ -z "$newest" ]; then
    gate_fail "no backup exists on this site - take one before updating"
  fi
  age_h=$(compose exec -T backend bash -lc "stat -c %Y '$newest'" | tr -d '\r')
  age_h=$(( ( $(date +%s) - ${age_h:-0} ) / 3600 ))
  if [ "${age_h:-999}" -ge "$UPDATE_MAX_BACKUP_AGE_H" ]; then
    gate_fail "newest backup is ${age_h}h old; the limit is ${UPDATE_MAX_BACKUP_AGE_H}h"
  fi
  echo "  backup: $(basename "$newest") (${age_h}h old)"
}

# install.sh builds to one tag and overwrites it, and the VPS workflows run
# `docker system prune -af`, which deletes untagged images. Without this the
# only way back from a bad image is a 20-45 minute rebuild against floating
# dependencies, which is not a rollback.
tag_rollback() {
  local cur stamp
  cur="${KAMRA_IMAGE}:${KAMRA_TAG}"
  docker image inspect "$cur" >/dev/null 2>&1 || return 0
  stamp="${KAMRA_IMAGE}:rollback-$(date -u +%Y%m%d-%H%M%S)"
  docker tag "$cur" "$stamp" && green "Previous image tagged ${stamp}"
  echo "$stamp" > "$INSTALL_DIR/.last-rollback-tag"
}

# A migrate that ran is not an update that worked. If the site cannot pass its
# own checks afterwards, say so plainly and hand over the way back rather than
# printing a success line over a broken hotel.
post_update_gate() {
  local rb; rb=$(cat "$INSTALL_DIR/.last-rollback-tag" 2>/dev/null || true)
  if compose exec -T backend bench --site all ziri-doctor >/dev/null 2>&1; then
    echo "  health: passed"
    return 0
  fi
  red ""
  red "UPDATE APPLIED, BUT THE HEALTH CHECK FAILED."
  red "Run this to see what is wrong:"
  red "  ${INSTALL_DIR}/install.sh doctor"
  if [ -n "$rb" ]; then
    red ""
    red "To put the previous image back (this does NOT undo the database"
    red "migration - read docs/product/ROLLBACK.md before you do):"
    red "  KAMRA_TAG=${rb#*:} ${INSTALL_DIR}/install.sh update"
  fi
  return 1
}

install_self() {
  # Keep a copy next to the stack so `install.sh update` works later.
  if [ -n "$SELF" ] && [ "$SELF" != "$INSTALL_DIR/install.sh" ]; then
    cp "$SELF" "$INSTALL_DIR/install.sh" && chmod +x "$INSTALL_DIR/install.sh"
  elif [ ! -f "$INSTALL_DIR/install.sh" ]; then
    curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh \
      -o "$INSTALL_DIR/install.sh" && chmod +x "$INSTALL_DIR/install.sh" || true
  fi
}

# --- build: image only (Packer / Marketplace snapshots) ---------------------
if [ "$MODE" = build ]; then
  checkout_frappe_docker
  write_apps_json
  build_image
  install_self
  green "Built ${KAMRA_IMAGE}:${KAMRA_TAG}. First boot: ${INSTALL_DIR}/install.sh"
  exit 0
fi

# --- update: rebuild from the recorded apps.json, restart, migrate ----------
if [ "$MODE" = update ]; then
  [ -f "$ENVFILE" ] || die "no ${ENVFILE} — run install first"
  [ -f "$APPS_JSON" ] || die "no ${APPS_JSON} — run install first"
  checkout_frappe_docker
  # KAMRA_BRANCH=… on the command line switches branch/tag; otherwise keep
  # whatever apps.json already records.
  if [ -n "${KAMRA_BRANCH_OVERRIDE:-}" ]; then
    KAMRA_BRANCH="$KAMRA_BRANCH_OVERRIDE"
    write_apps_json
  else
    KAMRA_BRANCH=$(grep -o '"branch": *"[^"]*"' "$APPS_JSON" | tail -1 | sed 's/.*"\([^"]*\)"$/\1/')
  fi
  if [ "${ZIRI_FORCE:-0}" = "1" ]; then
    red "ZIRI_FORCE=1 - skipping pre-flight. You own what happens next."
  else
    preflight
  fi
  tag_rollback
  build_image
  echo "Restarting the stack on the new image…"
  compose up -d --force-recreate
  wait_for_backend
  echo "Migrating sites…"
  compose exec -T backend bench --site all migrate
  compose exec -T backend bench --site all clear-cache
  _health_ok=1; post_update_gate || _health_ok=0
  install_self
  if [ "$_health_ok" = "1" ]; then
    green "ZIRI updated to ${KAMRA_GIT_URL}@${KAMRA_BRANCH}."
  else
    # Do not print a success line over a site that cannot pass its own
    # checks, and do not exit 0: a caller scripting this update has to
    # be able to tell the two outcomes apart.
    red "Updated to ${KAMRA_GIT_URL}@${KAMRA_BRANCH}, but the site is NOT healthy."
    exit 1
  fi
  exit 0
fi

# --- Prompts (WordPress install.php shape) ----------------------------------
# Non-interactive (cloud-init / 1-click): export SITE_NAME ADMIN_EMAIL ADMIN_PASSWORD first.
if [ -z "${SITE_NAME:-}" ] || [ -z "${ADMIN_EMAIL:-}" ] || [ -z "${ADMIN_PASSWORD:-}" ]; then
  prompt SITE_NAME "Site domain (e.g. pms.yourhotel.com)"
  prompt ADMIN_EMAIL "Admin email"
  prompt ADMIN_PASSWORD "Admin password (min ${MIN_PASSWORD_LEN} chars)" secret
  prompt ADMIN_PASSWORD_CONFIRM "Confirm admin password" secret
  [ "${ADMIN_PASSWORD}" = "${ADMIN_PASSWORD_CONFIRM}" ] || die "passwords do not match"
fi

[ -n "${SITE_NAME}" ] || die "SITE_NAME is required"
[[ "${SITE_NAME}" == *.* ]] || die "SITE_NAME should look like a domain (pms.yourhotel.com)"
[[ "${ADMIN_EMAIL}" == *@* ]] || die "ADMIN_EMAIL must be an email address"
[ "${#ADMIN_PASSWORD}" -ge "$MIN_PASSWORD_LEN" ] || die "password must be at least ${MIN_PASSWORD_LEN} characters"

# Re-runs must keep the DB password MariaDB was initialised with.
if [ -z "${DB_PASSWORD:-}" ] && [ -f "$ENVFILE" ]; then
  DB_PASSWORD=$(sed -n 's/^DB_PASSWORD=//p' "$ENVFILE" | head -1)
fi
DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | xxd -p -c 32)}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-$ADMIN_EMAIL}"
HTTP_PUBLISH_PORT="${HTTP_PUBLISH_PORT:-8080}"

# --- frappe_docker checkout + image -----------------------------------------
checkout_frappe_docker
write_apps_json

# 1-Click snapshots ship a pre-built image; plain re-runs reuse it too.
if docker image inspect "${KAMRA_IMAGE}:${KAMRA_TAG}" >/dev/null 2>&1 && [ "$FORCE_REBUILD" != "1" ]; then
  echo "Image ${KAMRA_IMAGE}:${KAMRA_TAG} already present — skipping build."
  echo "  (to pull new ZIRI code later: ${INSTALL_DIR}/install.sh update)"
else
  build_image
fi

umask 077
cat > "$ENVFILE" <<EOF
# Generated by ZIRI install.sh — do not commit.
DB_PASSWORD=${DB_PASSWORD}
CUSTOM_IMAGE=${KAMRA_IMAGE}
CUSTOM_TAG=${KAMRA_TAG}
# never: image is local; do not hit a registry
PULL_POLICY=never
# compose still interpolates this even with CUSTOM_IMAGE set
ERPNEXT_VERSION=${KAMRA_TAG}
FRAPPE_SITE_NAME_HEADER=${SITE_NAME}
HTTP_PUBLISH_PORT=${HTTP_PUBLISH_PORT}
EOF

umask 022

echo "Starting the stack with local image ${KAMRA_IMAGE}:${KAMRA_TAG}…"
compose up -d
wait_for_backend

# Idempotent: skip new-site only if this site already has a site_config.json
# (sites/ also holds apps.txt, apps.json, assets, common_site_config.json).
if ! compose exec -T backend test -f "sites/${SITE_NAME}/site_config.json"; then
  echo "Creating site ${SITE_NAME} (this takes a few minutes)…"
  compose exec -T backend bench new-site "$SITE_NAME" \
    --mariadb-user-host-login-scope='%' \
    --db-root-password "$DB_PASSWORD" \
    --admin-password "$ADMIN_PASSWORD" \
    --install-app payments --install-app kamra --no-mariadb-socket
else
  echo "Site ${SITE_NAME} already present — skipping new-site."
fi

echo "First-boot wiring (home → /kamra, admin email, scheduler)…"
compose exec -T \
  -e "KAMRA_ADMIN_EMAIL=${ADMIN_EMAIL}" \
  -e "KAMRA_SITE_URL=https://${SITE_NAME}" \
  backend bench --site "$SITE_NAME" execute kamra.scripts.first_boot.execute

# Never leave the password sitting in the shell history file if we can help it
unset ADMIN_PASSWORD ADMIN_PASSWORD_CONFIRM
# Strip any leftover from a previous interactive shell export
export ADMIN_PASSWORD=""

green ""
green "ZIRI is up."
green "  Sign in:  http://<server-ip>:${HTTP_PUBLISH_PORT}/kamra"
green "            (or https://${SITE_NAME} after you point DNS + TLS)"
green "  User:     Administrator  (email ${ADMIN_EMAIL})"
green "  Password: the one you just set — there is no default."
green "  Next:     open /kamra/setup and create your property."
green ""
green "TLS tip: put nginx/Caddy in front, or:"
green "  certbot --nginx -d ${SITE_NAME}"
green ""
install_self
green "Stack dir: ${INSTALL_DIR}   env: ${ENVFILE}   apps: ${APPS_JSON}"
green "Update later (rebuilds the image, restarts, migrates):"
green "  sudo ${INSTALL_DIR}/install.sh update"
