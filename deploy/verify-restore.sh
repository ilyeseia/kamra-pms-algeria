#!/usr/bin/env bash
# Level 2 restore verification (docs/product/RESTORE.md 2.3).
#
# WHAT THIS ADDS OVER backup-verify.sh
# Level 1 proves a dump imports into a clean MariaDB with its row counts
# intact. That is necessary and it is not enough: it never starts the
# application, so it cannot tell you the site boots, that migrate runs on the
# restored schema, or that the encryption key still decrypts anything. A hotel
# does not need a database that loads. It needs a PMS that opens.
#
# So this one restores into a real, disposable ZIRI stack built from the same
# image production runs, and then asks the application questions.
#
# THE TEST STACK MUST NOT REACH THE WORLD
# A restored site holds the production encryption key, which makes every stored
# credential live. hooks.py pushes rates and availability hourly and emails
# arriving guests at 09:00. verify.override.yml puts the project on an
# `internal: true` network with no published ports and keeps the scheduler,
# workers, websocket and frontend down; the site is restored with
# pause_scheduler set. This script then PROVES the isolation rather than
# assuming it - an unexercised control is what RESTORE.md exists to warn about.
#
# USAGE
#   ./verify-restore.sh [SET_DIR]     verify the newest set, or SET_DIR
#   ./verify-restore.sh --teardown    remove the verify project and its volumes
#
# EXIT 0 verified | 1 verification failed | 2 could not run

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$HERE/linux/docker-compose.yml}"
OVERRIDE="$HERE/verify.override.yml"
SETS_DIR="${SETS_DIR:-$HERE/../.backup-sets}"
PROJECT="kamra-verify"
VSITE="verify.localhost"
BENCH=/home/frappe/frappe-bench
WORK="${TMPDIR:-/tmp}/ziri-verify.$$"

FAILED=0
say() { printf '  %s\n' "$*"; }
ok()  { printf '  [ OK ] %s\n' "$*"; }
bad() { printf '  [FAIL] %s\n' "$*"; FAILED=1; }
na()  { printf '  [ NA ] %s\n' "$*"; }   # not PASS - RESTORE.md 2.3 check 10
die() { printf '  ERROR: %s\n' "$*" >&2; teardown; exit 2; }

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 2; }

vdc() { docker compose -p "$PROJECT" --env-file "$WORK/verify.env" \
            -f "$COMPOSE_FILE" -f "$OVERRIDE" "$@"; }
vexec() { vdc exec -T backend bash -lc "$1"; }

# ── teardown, with the guard RESTORE.md 2.6 asks for ─────────────────────
teardown() {
	docker compose -p "$PROJECT" --env-file "$WORK/verify.env" \
		-f "$COMPOSE_FILE" -f "$OVERRIDE" down >/dev/null 2>&1 || true
	# Never pass -v to a compose down here. Remove volumes by name, and only
	# ones that carry the verify project prefix: a typo in PROJECT must not be
	# able to take the hotel's data with it.
	local v
	for v in $(docker volume ls --format '{{.Name}}' | grep "^${PROJECT}_" || true); do
		case "$v" in
			"${PROJECT}_"*) docker volume rm -f "$v" >/dev/null 2>&1 || true ;;
			*) echo "  refusing to remove volume outside the verify project: $v" >&2 ;;
		esac
	done
	rm -rf "$WORK"
}

if [ "${1:-}" = "--teardown" ]; then
	WORK="$(mktemp -d)"; : > "$WORK/verify.env"
	teardown; echo "  verify project removed"; exit 0
fi

SET_DIR="${1:-}"
[ -n "$SET_DIR" ] || SET_DIR=$(ls -d "$SETS_DIR"/*/ 2>/dev/null | grep -v selftest | sort | tail -1 || true)
[ -n "$SET_DIR" ] && [ -d "$SET_DIR" ] || die "no backup set found in $SETS_DIR"
SET_DIR="${SET_DIR%/}"
[ -f "$SET_DIR/database.sql.gz" ] || die "$SET_DIR has no database.sql.gz"

mkdir -p "$WORK"
trap teardown EXIT

V_PW=$(head -c16 /dev/urandom | od -An -tx1 | tr -d ' \n')
cat > "$WORK/verify.env" <<EOF
DB_PASSWORD=$V_PW
CUSTOM_IMAGE=${CUSTOM_IMAGE:-kamra}
CUSTOM_TAG=${CUSTOM_TAG:-v1.0.0-rc.3}
PULL_POLICY=never
FRAPPE_SITE_NAME_HEADER=$VSITE
EOF

say "set     : $SET_DIR"
say "image   : $(grep CUSTOM_IMAGE "$WORK/verify.env" | cut -d= -f2):$(grep CUSTOM_TAG "$WORK/verify.env" | cut -d= -f2)"
say "project : $PROJECT (isolated, no published ports)"
echo

# ── bring up only what bench needs ───────────────────────────────────────
say "starting db, redis, configurator, backend…"
vdc up -d db redis-cache redis-queue configurator backend >/dev/null 2>&1 \
	|| die "the verify stack did not start"

tries=0
until [ "$(vdc ps --format '{{.Service}} {{.State}}' 2>/dev/null | grep -c '^backend running')" -ge 1 ]; do
	tries=$((tries+1)); [ $tries -gt 120 ] && die "backend never started"
	sleep 3
done
# Same gate production uses: a configurator that did not exit 0 means nothing
# downstream is trustworthy.
cfg=$(docker inspect "${PROJECT}-configurator-1" --format '{{.State.ExitCode}}' 2>/dev/null || echo "?")
[ "$cfg" = "0" ] && ok "configurator exited 0" || bad "configurator exit code $cfg"

# ── check: the isolation is real, not assumed (RESTORE.md 2.4) ───────────
if vexec "timeout 8 bash -c 'cat < /dev/null > /dev/tcp/1.1.1.1/443' 2>/dev/null"; then
	bad "the test stack CAN reach the internet - a restored site would push rates and email guests"
	say "       refusing to restore into a stack that is not isolated"
	exit 1
fi
ok "isolation: no outbound route from the test stack"

# ── create a throwaway site, then restore into it ────────────────────────
say "creating $VSITE…"
vexec "cd $BENCH && bench new-site $VSITE --no-mariadb-socket \
	--mariadb-user-host-login-scope='%' --db-root-password '$V_PW' \
	--admin-password '$(head -c12 /dev/urandom | od -An -tx1 | tr -d ' \n')' \
	--install-app payments --install-app kamra" >/dev/null 2>&1 \
	|| die "could not create the verify site"
vexec "cd $BENCH && bench --site $VSITE set-config pause_scheduler 1" >/dev/null 2>&1

vdc cp "$SET_DIR/database.sql.gz" "backend:$BENCH/sites/$VSITE/private/backups/restore.sql.gz" >/dev/null \
	|| die "could not copy the dump into the verify stack"

say "restoring…"
t0=$(date +%s)
if vexec "cd $BENCH && bench --site $VSITE restore sites/$VSITE/private/backups/restore.sql.gz \
	--db-root-password '$V_PW' --force" >"$WORK/restore.log" 2>&1; then
	t_restore=$(( $(date +%s) - t0 ))
	ok "restore completed in ${t_restore}s"
else
	bad "restore failed"
	tail -4 "$WORK/restore.log" | sed 's/^/        /'
	exit 1
fi

# ── check: the application answers on the restored data ──────────────────
if vexec "cd $BENCH && bench --site $VSITE execute frappe.ping" >/dev/null 2>&1; then
	ok "the site boots on the restored database"
else
	bad "the site does not boot on the restored database"
fi

counts=$(vexec "cd $BENCH && bench --site $VSITE execute frappe.client.get_count --args '[\"Property\"]' 2>/dev/null" | tr -d '\r' | tail -1)
say "       properties restored: ${counts:-unknown}"

# ── check: migrate runs on the restored schema, and times it ─────────────
say "migrating…"
t0=$(date +%s)
if vexec "cd $BENCH && bench --site $VSITE migrate" >"$WORK/migrate.log" 2>&1; then
	t_migrate=$(( $(date +%s) - t0 ))
	ok "migrate completed in ${t_migrate}s"
else
	bad "migrate failed on the restored site"
	tail -4 "$WORK/migrate.log" | sed 's/^/        /'
fi

# ── check 10: every private file the database references exists ──────────
urls=$(vexec "cd $BENCH && bench --site $VSITE execute frappe.client.get_list \
	--args '[\"File\", {\"filters\": {\"is_private\": 1, \"is_folder\": 0}, \"fields\": [\"file_url\"], \"limit_page_length\": 0}]' 2>/dev/null" \
	| tr -d '\r' | grep -o "/private/files/[^\"']*" || true)
n_tot=$(printf '%s\n' "$urls" | grep -c . || true)
if [ "${n_tot:-0}" -eq 0 ]; then
	na "10 no private files referenced - nothing to check. N/A is not a pass."
	say "       This set carries no guest documents, so it cannot show that a"
	say "       files archive would have restored. Re-run once the site has one."
else
	n_miss=0
	while IFS= read -r u; do
		[ -n "$u" ] || continue
		vexec "test -f $BENCH/sites/$VSITE$u" >/dev/null 2>&1 || n_miss=$((n_miss+1))
	done <<< "$urls"
	pct=$(( n_miss * 100 / n_tot ))
	if [ "$pct" -le "${FILE_MISS_PCT:-1}" ]; then
		ok "10 files: $n_tot referenced, $n_miss missing (${pct}%)"
	else
		bad "10 files: $n_tot referenced, $n_miss missing (${pct}%) - the files archive did not restore"
	fi
fi

# ── the shipped health check, on the checks that mean anything here ──────
# ziri-doctor is run against the restored site, but its verdict cannot be used
# whole. This stack deliberately runs without the queue workers, the scheduler,
# websocket and frontend - that is the isolation, not a defect - so the worker
# and scheduler checks report exactly what the design asked for and the overall
# verdict comes back FAILED. An earlier version of this script took that at face
# value and failed every verification of a perfectly good backup.
#
# The excluded ids are listed here rather than hidden behind a flag, because
# narrowing what a check looks at is the kind of change that quietly turns a
# gate into decoration. Everything else - database, redis, apps, frappe,
# version, disk, timezone - is evaluated, and a failure in any of them still
# fails the run.
vexec "cd $BENCH && bench --site $VSITE ziri-doctor --json" >"$WORK/doctor.json" 2>/dev/null
if [ -s "$WORK/doctor.json" ]; then
	eval "$(
		python3 - "$WORK/doctor.json" <<'PY'
import json, sys
raw = open(sys.argv[1], encoding="utf-8").read()
data = json.loads(raw[raw.index("{"):])
# not meaningful on a stack that is partial by design
skip = {"workers", "scheduler", "backup"}
failed = [c["id"] for c in data["checks"]
          if c["status"] == "failed" and c["id"] not in skip]
judged = [c["id"] for c in data["checks"] if c["id"] not in skip]
print("DOC_FAILED='%s'" % " ".join(failed))
print("DOC_JUDGED=%d" % len(judged))
print("DOC_SKIPPED=%d" % (len(data["checks"]) - len(judged)))
PY
	)" 2>/dev/null
	if [ -z "${DOC_FAILED:-}" ]; then
		ok "ziri-doctor: ${DOC_JUDGED:-?} applicable checks pass (${DOC_SKIPPED:-?} not applicable to a partial stack)"
	else
		bad "ziri-doctor failed on the restored site: $DOC_FAILED"
	fi
else
	bad "ziri-doctor produced no output on the restored site"
fi

echo
say "--- timings, which are the first real RTO inputs this repo has ---"
say "    restore : ${t_restore:-?}s"
say "    migrate : ${t_migrate:-?}s"
echo
if [ "$FAILED" -eq 0 ]; then
	say "VERIFIED (Level 2) - this set restored into a real stack, the site"
	say "boots, migrate runs and the shipped health check passes."
	say "What this still does not prove: that a folio adds up. Counts cannot"
	say "tell you that. RESTORE.md 2.3 asks a human to sign in once at handover"
	say "and read today's arrivals, one folio total and one invoice footer."
	exit 0
fi
say "NOT VERIFIED - do not rely on this set."
exit 1
