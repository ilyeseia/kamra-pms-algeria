#!/usr/bin/env bash
# ZIRI PMS - take a backup set, and prove it can be restored.
#
# Implements docs/product/RESTORE.md section 2.1 (Level 1). The point is the
# second half: a backup nobody has restored is not a backup, it is a file.
#
# WHY THIS RUNS ON THE HOST
# Verification needs a throwaway MariaDB, which needs Docker. The backend
# container deliberately has no Docker socket - giving the application control
# of the host's daemon to improve diagnostics would be a far worse trade than
# running this one script outside it.
#
# WHAT A SET CONTAINS, AND WHY site_config.json IS IN IT
# Frappe encrypts stored secrets - SMTP passwords, payment keys, channel
# manager credentials - with the site's `encryption_key`, which lives in
# site_config.json and NOT in the database dump. A dump restored without it
# comes back with every integration credential unreadable. Most backup
# procedures miss this; it is the single most common way a restore "succeeds"
# and the hotel still cannot take a booking. The set therefore carries
# site_config.json, and because that file contains the key AND the database
# password, the set is as sensitive as the database itself. Store it
# accordingly.
#
# USAGE
#   ./backup-verify.sh backup            take a set and write its manifest
#   ./backup-verify.sh verify [DIR]      verify the newest set, or DIR
#   ./backup-verify.sh self-test         prove the verifier can FAIL (N1, N2)
#
# EXIT CODES
#   0 verified   1 verification failed   2 could not run

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$HERE/linux/docker-compose.yml}"
SITE="${SITE:-ziri.localhost}"
SETS_DIR="${SETS_DIR:-$HERE/../.backup-sets}"
BENCH=/home/frappe/frappe-bench
# Must match production's db service or the import can behave differently from
# the real thing, which would make the test lie.
DB_IMAGE="${DB_IMAGE:-mariadb:11.8}"
DB_FLAGS=(--character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
          --skip-character-set-client-handshake)
VERIFY_CT="ziri-verify-db"

say()  { printf '  %s\n' "$*"; }
ok()   { printf '  [ OK ] %s\n' "$*"; }
bad()  { printf '  [FAIL] %s\n' "$*"; FAILED=1; }
die()  { printf '  ERROR: %s\n' "$*" >&2; exit 2; }
dc()   { docker compose -f "$COMPOSE_FILE" "$@"; }
bexec(){ dc exec -T backend bash -lc "$1"; }

# SQL against the LIVE database goes straight to the db service rather than
# through `bench mariadb`, whose contract is "enter a console": it does accept
# forwarded client flags, but its output carries the console's own noise. The
# password is passed as MYSQL_PWD so it never appears in a command line that
# ps or a shell history would show.
DB_PW=""
load_db_pw() {
	[ -n "$DB_PW" ] && return 0
	local envfile="${ENV_FILE:-$(dirname "$COMPOSE_FILE")/.env}"
	[ -f "$envfile" ] || die "no .env beside the compose file (looked in $envfile)"
	DB_PW=$(grep -E '^DB_PASSWORD=' "$envfile" | head -1 | cut -d= -f2-)
	[ -n "$DB_PW" ] || die "DB_PASSWORD is not set in $envfile"
}
lq() {   # live query -> tab-separated rows, no header
	load_db_pw
	dc exec -T -e MYSQL_PWD="$DB_PW" db mariadb -uroot --skip-column-names --batch -e "$1" 2>/dev/null | tr -d '\r'
}

need() { command -v "$1" >/dev/null 2>&1 || die "$1 is required"; }
need docker

# ── manifest ─────────────────────────────────────────────────────────────
# Exact COUNT(*) per table, not information_schema.TABLE_ROWS, which is an
# estimate for InnoDB and would pass a lossy import.
table_counts() {           # $1 = schema
	local q
	q=$(cat <<SQL
SELECT GROUP_CONCAT(CONCAT('SELECT ''', table_name, ''' AS t, COUNT(*) AS n FROM \`', table_name, '\`') SEPARATOR ' UNION ALL ')
FROM information_schema.tables WHERE table_schema = '$1' AND table_type = 'BASE TABLE';
SQL
)
	printf '%s' "$q"
}

cmd_backup() {
	mkdir -p "$SETS_DIR"
	local stamp set_dir
	stamp=$(date -u +%Y%m%d-%H%M%S)
	set_dir="$SETS_DIR/$stamp"
	mkdir -p "$set_dir"
	say "set: $set_dir"

	# 1. counts BEFORE the dump. The site stays live, so a table may
	#    legitimately shrink between here and the dump; rule 5 allows that
	#    only for tables on the churn allowlist.
	say "reading table counts…"
	local dbname inner
	dbname=$(bexec "python3 -c \"import json;print(json.load(open('$BENCH/sites/$SITE/site_config.json'))['db_name'])\"" | tr -d '\r\n')
	[ -n "$dbname" ] || die "could not read db_name for $SITE"
	inner=$(lq "$(table_counts "$dbname")" | head -1)
	[ -n "$inner" ] && [ "$inner" != "NULL" ] || die "could not build the counts query for $dbname"
	# -F'	' is load-bearing. Frappe table names contain spaces
	# (`tabScheduled Job Type`), so awk's default whitespace split makes
	# NF==2 drop every one of them: the manifest came back with 52 of 352
	# tables and the verifier would have checked 15% of the database while
	# printing a pass.
	lq "USE \`$dbname\`; $inner" | awk -F'\t' 'NF==2 {print $1"\t"$2}' | sort > "$set_dir/manifest.tsv"
	[ -s "$set_dir/manifest.tsv" ] || die "manifest came back empty"
	say "manifest: $(wc -l < "$set_dir/manifest.tsv") tables"

	# 2. the dump
	say "taking backup…"
	bexec "cd $BENCH && bench --site $SITE backup --with-files" >/dev/null 2>&1 || die "bench backup failed"
	local newest
	newest=$(bexec "ls -t $BENCH/sites/$SITE/private/backups/*-database.sql.gz 2>/dev/null | head -1" | tr -d '\r\n')
	[ -n "$newest" ] || die "no database dump was produced"
	dc cp "backend:$newest" "$set_dir/database.sql.gz" >/dev/null

	# 3. the encryption key - see the header
	dc cp "backend:$BENCH/sites/$SITE/site_config.json" "$set_dir/site_config.json" >/dev/null
	chmod 600 "$set_dir/site_config.json" 2>/dev/null || true

	# 4. provenance, so a verifier can tell a stale set from a current one
	{
		echo "site=$SITE"
		echo "taken_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
		echo "db_image=$DB_IMAGE"
		echo "source_dump=$(basename "$newest")"
	} > "$set_dir/SET.info"

	( cd "$set_dir" && sha256sum database.sql.gz manifest.tsv site_config.json > SHA256SUMS )
	ok "set written: $(du -sh "$set_dir" | cut -f1)"
	echo "$set_dir"
}

# ── verification ─────────────────────────────────────────────────────────
teardown() { docker rm -fv "$VERIFY_CT" >/dev/null 2>&1 || true; }

cmd_verify() {
	local set_dir="${1:-}"
	[ -n "$set_dir" ] || set_dir=$(ls -d "$SETS_DIR"/*/ 2>/dev/null | sort | tail -1 || true)
	[ -n "$set_dir" ] && [ -d "$set_dir" ] || die "no backup set found in $SETS_DIR"
	set_dir="${set_dir%/}"
	FAILED=0
	say "verifying: $set_dir"
	[ -f "$set_dir/SET.info" ] && sed 's/^/    /' "$set_dir/SET.info"

	# check 1 - checksums as fetched from the destination
	if ( cd "$set_dir" && sha256sum -c SHA256SUMS >/dev/null 2>&1 ); then
		ok "1 checksums match"
	else
		bad "1 checksum mismatch - corruption in storage or transit"
	fi

	# check 2 - archive integrity
	if gzip -t "$set_dir/database.sql.gz" 2>/dev/null; then
		ok "2 gzip integrity"
	else
		bad "2 archive is truncated or corrupt"
		say "    stopping: a corrupt archive cannot be imported"
		return $FAILED
	fi

	trap teardown EXIT
	teardown
	local pw; pw=$(head -c16 /dev/urandom | od -An -tx1 | tr -d ' \n')
	docker run -d --name "$VERIFY_CT" --network none \
		-e MARIADB_ROOT_PASSWORD="$pw" -e MARIADB_DATABASE=verify \
		"$DB_IMAGE" "${DB_FLAGS[@]}" >/dev/null || die "could not start $DB_IMAGE"

	# the entrypoint starts TWO servers; waiting for the first one races the
	# init shutdown and the import dies mid-stream
	local tries=0
	until [ "$(docker logs "$VERIFY_CT" 2>&1 | grep -c 'ready for connections')" -ge 2 ]; do
		tries=$((tries+1)); [ $tries -gt 90 ] && die "verify database never became ready"
		sleep 2
	done

	# From here the checks RECORD failures; they must not abort. A failed
	# check 4 on an empty dump used to kill the script through set -e, so
	# checks 5 and 6 never ran and the verdict was never printed - a
	# verifier that stops at the first problem and says nothing is worse
	# than one that says nothing at all.
	# Remember what the caller had: forcing `set -e` back on at the end
	# leaked out of this function and defeated the self-test's own
	# `set +e`, so a verify that correctly returned 1 killed the script
	# before the caller could read the code it was waiting for.
	local _had_e=0; case $- in *e*) _had_e=1;; esac
	set +e
	# check 3 - import, with pipefail so a truncated dump cannot be hidden by
	# a successful final stage
	local imp=0
	set +e
	( set -o pipefail
	  gzip -dc "$set_dir/database.sql.gz" \
	  | docker exec -i -e MYSQL_PWD="$pw" "$VERIFY_CT" mariadb -uroot verify ) 2>"$set_dir/.import.err"
	imp=$?
	# (no `set -e` here: the whole checks section runs with it off)
	if [ $imp -eq 0 ] && ! grep -qi "^ERROR" "$set_dir/.import.err"; then
		ok "3 import completed"
	else
		bad "3 import failed (exit $imp)"
		head -3 "$set_dir/.import.err" 2>/dev/null | sed 's/^/        /'
	fi

	vq() { docker exec -i -e MYSQL_PWD="$pw" "$VERIFY_CT" mariadb -uroot --skip-column-names --batch verify -e "$1" 2>/dev/null; }

	# check 4 - table count
	local want got
	want=$(wc -l < "$set_dir/manifest.tsv")
	got=$(vq "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='verify' AND table_type='BASE TABLE';" | tr -d '\r')
	if [ "${got:-0}" = "$want" ]; then
		ok "4 table count $got matches the manifest"
	else
		bad "4 table count $got, manifest says $want"
	fi

	# check 5 - exact per-table counts
	local inner cmp_file shrunk missing
	inner=$(vq "$(table_counts verify)" | tr -d '\r' | head -1)
	cmp_file="$set_dir/.restored.tsv"
	if [ -n "$inner" ]; then
		vq "$inner" | tr -d '\r' | awk -F'\t' 'NF==2 {print $1"\t"$2}' | sort > "$cmp_file"
		missing=$(join -t"$(printf '\t')" -v1 "$set_dir/manifest.tsv" "$cmp_file" | wc -l)
		shrunk=$(join -t"$(printf '\t')" "$set_dir/manifest.tsv" "$cmp_file" \
			| awk -F'\t' '$3+0 < $2+0 {print}' | wc -l)
		if [ "$missing" -eq 0 ] && [ "$shrunk" -eq 0 ]; then
			ok "5 every table restored with at least its manifest count"
		else
			bad "5 $missing table(s) missing, $shrunk short of the manifest"
			join -t"$(printf '\t')" "$set_dir/manifest.tsv" "$cmp_file" \
				| awk -F'\t' '$3+0 < $2+0 {printf "        %s: manifest %s, restored %s\n", $1, $2, $3}' | head -5
		fi
	else
		bad "5 could not read restored counts"
	fi

	# check 6 - the encryption key, compared against the LIVE site.
	#
	# Frappe generates encryption_key lazily, on the first thing it actually
	# encrypts. A site where nobody has configured SMTP, a payment gateway or
	# a channel manager genuinely has none, and failing that is a red light
	# on a healthy install - which teaches people to ignore red lights.
	#
	# The dangerous case is narrower and this is what the check looks for:
	# the live site HAS a key and the set does not. Then the dump restores,
	# every check above passes, and every stored credential comes back as
	# unreadable ciphertext.
	local live_key=0 set_key=0
	bexec "grep -q encryption_key $BENCH/sites/$SITE/site_config.json" >/dev/null 2>&1 && live_key=1
	grep -q '\"encryption_key\"' "$set_dir/site_config.json" 2>/dev/null && set_key=1
	if [ "${live_key:-0}" = "1" ] && [ "$set_key" = "0" ]; then
		bad "6 the site has an encryption key and this set does not - stored credentials would not decrypt after a restore"
	elif [ "${live_key:-0}" = "1" ]; then
		ok "6 encryption key present in the set"
	elif [ "$set_key" = "1" ]; then
		ok "6 encryption key present in the set (the live site no longer reports one)"
	else
		say "  [INFO] 6 no encryption key anywhere yet - nothing on this site has"
		say "         been encrypted. The moment SMTP, a payment gateway or a"
		say "         channel manager is configured, a key appears and every set"
		say "         taken after that must carry it."
	fi

	[ "$_had_e" = 1 ] && set -e
	rm -f "$set_dir/.import.err" "$cmp_file"
	teardown; trap - EXIT
	echo
	if [ "$FAILED" -eq 0 ]; then
		say "VERIFIED - this set imported into a clean MariaDB with its counts intact."
		say "That is evidence, not a guarantee: it does not prove the application"
		say "runs on it. See docs/product/RESTORE.md section 2.3 for the Level 2 run."
		return 0
	fi
	say "NOT VERIFIED - do not rely on this set."
	return 1
}

# ── the verifier must be seen to fail ────────────────────────────────────
# A check that has never rejected anything is a decoration. RESTORE.md 2.5
# makes this mandatory: until the negative controls have been seen to fail,
# a deployment's verification status is UNPROVEN whatever the checks printed.
cmd_self_test() {
	local src; src=$(ls -d "$SETS_DIR"/*/ 2>/dev/null | sort | tail -1 || true)
	[ -n "$src" ] || die "take a backup first: $0 backup"
	src="${src%/}"
	local work="$SETS_DIR/.selftest"; rm -rf "$work"; mkdir -p "$work"
	local rc pass=0 fail=0 total=2

	say "N1 - truncated dump (must FAIL)"
	cp -r "$src/." "$work/"
	local sz; sz=$(stat -c%s "$work/database.sql.gz")
	head -c $(( sz / 2 )) "$src/database.sql.gz" > "$work/database.sql.gz"
	set +e; cmd_verify "$work" >/dev/null 2>&1; rc=$?; set -e
	if [ $rc -ne 0 ]; then ok "N1 rejected"; pass=$((pass+1)); else bad "N1 PASSED - the verifier is broken"; fail=$((fail+1)); fi

	say "N2 - empty database (must FAIL)"
	rm -rf "$work"; mkdir -p "$work"; cp -r "$src/." "$work/"
	: | gzip -c > "$work/database.sql.gz"
	( cd "$work" && sha256sum database.sql.gz manifest.tsv site_config.json > SHA256SUMS )
	set +e; cmd_verify "$work" >/dev/null 2>&1; rc=$?; set -e
	if [ $rc -ne 0 ]; then ok "N2 rejected"; pass=$((pass+1)); else bad "N2 PASSED - the verifier is broken"; fail=$((fail+1)); fi

	# N3 only means something where the live site HAS a key. Frappe creates
	# one lazily, on the first thing it encrypts, so a site with no SMTP, no
	# payment gateway and no channel manager genuinely has none - and check 6
	# correctly reports that as information rather than failure. Running N3
	# there tests a condition that cannot arise, and counting it as a pass
	# would be claiming evidence this run did not produce.
	local live_key=0
	bexec "grep -q encryption_key $BENCH/sites/$SITE/site_config.json" >/dev/null 2>&1 && live_key=1
	if [ "$live_key" = "1" ]; then
		say "N3 - key removed from the set (must FAIL)"
		rm -rf "$work"; mkdir -p "$work"; cp -r "$src/." "$work/"
		echo '{}' > "$work/site_config.json"
		( cd "$work" && sha256sum database.sql.gz manifest.tsv site_config.json > SHA256SUMS )
		set +e; cmd_verify "$work" >/dev/null 2>&1; rc=$?; set -e
		if [ $rc -ne 0 ]; then ok "N3 rejected"; pass=$((pass+1)); else bad "N3 PASSED - the verifier is broken"; fail=$((fail+1)); fi
		total=$((total+1))
	else
		say "N3 - skipped: this site has no encryption key, so the condition"
		say "     it tests cannot occur. Re-run the self-test once SMTP or a"
		say "     payment gateway is configured."
	fi

	rm -rf "$work"
	echo
	if [ $fail -eq 0 ]; then
		say "SELF-TEST PASSED - $pass/$total applicable controls were rejected."
		return 0
	fi
	say "SELF-TEST FAILED - $fail control(s) slipped through. Every earlier pass is void."
	return 1
}

case "${1:-}" in
	backup)    cmd_backup ;;
	verify)    cmd_verify "${2:-}" ;;
	self-test) cmd_self_test ;;
	*) sed -n '1,30p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
