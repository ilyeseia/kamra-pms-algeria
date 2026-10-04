#!/usr/bin/env bash
# Install the ZIRI backup and verification timers on this host.
#
# WHY THIS EXISTS
# deploy/backup-verify.sh has worked, and been proven to work, for some time -
# and on a real host it ran only when a human ran it. docs/product/BACKUP.md
# section 4.3 said the schedule belongs in "cron or a systemd timer" and
# nothing installed one. A backup procedure nobody runs protects nobody, and
# PRODUCTIZATION_AUDIT.md recorded it as gap section 22 with zero hits.
#
# WHY systemd AND NOT cron
# Persistent=true. A hotel server that was off, asleep or mid-update at 05:30
# does not silently skip the night: it backs up when it comes back. cron has no
# equivalent, and anacron does not run a fixed-time job the way this needs.
# Beyond that: output goes to the journal instead of to root's mail, and
# `systemctl list-timers` answers "when did it last run, when does it run next"
# in one line.
#
# USAGE
#   sudo ./install-timers.sh              install and start
#   sudo ./install-timers.sh --uninstall  stop, disable and remove
#   sudo ./install-timers.sh --status     what is installed and when it next runs
#   sudo ./install-timers.sh --dry-run    print the units that would be written
#
# This writes to /etc/systemd/system. It does not touch the application, the
# containers or the data.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZIRI_DIR="$(cd "$HERE/../.." && pwd)"
UNIT_DIR=/etc/systemd/system
UNITS=(ziri-backup.service ziri-backup.timer ziri-verify.service ziri-verify.timer)
TIMERS=(ziri-backup.timer ziri-verify.timer)

say()  { printf '  %s\n' "$*"; }
ok()   { printf '  [ OK ] %s\n' "$*"; }
die()  { printf '  ERROR: %s\n' "$*" >&2; exit 2; }

need_root() {
	[ "$(id -u)" = "0" ] || die "run this with sudo - it writes to $UNIT_DIR"
}

preflight() {
	# Each of these is a way the timers would install cleanly and then never
	# work, which is worse than refusing: the operator would believe backups
	# are running.
	command -v systemctl >/dev/null 2>&1 || die "no systemctl - this host does not use systemd. Use cron; docs/product/BACKUP.md section 4.3"
	command -v flock >/dev/null 2>&1 || die "flock is required (util-linux); the units use it to keep backup and verify from overlapping"
	command -v docker >/dev/null 2>&1 || die "docker is required - backup-verify.sh talks to the compose project"
	[ -f "$ZIRI_DIR/deploy/backup-verify.sh" ] || die "cannot find deploy/backup-verify.sh under $ZIRI_DIR"
	[ -f "$ZIRI_DIR/deploy/linux/docker-compose.yml" ] || die "cannot find deploy/linux/docker-compose.yml under $ZIRI_DIR"

	# The timers fire at a LOCAL time chosen to sit after the night audit. If
	# the host clock is in a different zone from the site, 05:30 is not the
	# 05:30 the schedule was reasoned about. Reported, not fatal - a correct
	# answer here needs the site's own setting, which this script will not
	# start a container to read.
	local hosttz
	hosttz=$(timedatectl show --property=Timezone --value 2>/dev/null || echo unknown)
	say "host timezone: $hosttz (the units assume this equals the site's)"
}

render() {   # render <unit> -> stdout
	[ -f "$HERE/$1" ] || die "missing template: $HERE/$1"
	sed "s|@@ZIRI_DIR@@|$ZIRI_DIR|g" "$HERE/$1"
}

cmd_install() {
	need_root
	preflight
	local u
	for u in "${UNITS[@]}"; do
		render "$u" > "$UNIT_DIR/$u"
		chmod 644 "$UNIT_DIR/$u"
		ok "wrote $UNIT_DIR/$u"
	done
	systemctl daemon-reload
	for u in "${TIMERS[@]}"; do
		systemctl enable --now "$u" >/dev/null
		ok "enabled $u"
	done
	echo
	# Proving the unit can run is the point. An enabled timer only shows that
	# systemd accepted the file; it says nothing about whether the script works
	# as root, finds Docker, and can reach the site.
	say "running one backup now to prove the unit works…"
	if systemctl start ziri-backup.service; then
		ok "ziri-backup.service completed"
	else
		say "ziri-backup.service FAILED - the timer is installed but the backup"
		say "does not work. Read it with:  journalctl -u ziri-backup.service -n 50"
		exit 1
	fi
	echo
	cmd_status
	echo
	say "The backup set is written to $ZIRI_DIR/.backup-sets and contains the"
	say "database, the uploaded files and site_config.json - which holds the"
	say "encryption key AND the database password. It is as sensitive as the"
	say "database. Copy it off this host, and do not put it anywhere public."
}

cmd_uninstall() {
	need_root
	local u
	for u in "${TIMERS[@]}"; do
		systemctl disable --now "$u" >/dev/null 2>&1 || true
		ok "disabled $u"
	done
	for u in "${UNITS[@]}"; do
		rm -f "$UNIT_DIR/$u" && ok "removed $UNIT_DIR/$u"
	done
	systemctl daemon-reload
	echo
	say "Timers removed. Backup sets in $ZIRI_DIR/.backup-sets were NOT touched"
	say "- removing a schedule is not a reason to delete a hotel's backups."
}

cmd_status() {
	local u found=0
	for u in "${UNITS[@]}"; do
		[ -f "$UNIT_DIR/$u" ] && found=1
	done
	[ "$found" = 1 ] || { say "no ZIRI timers are installed"; return 0; }
	systemctl list-timers --all 'ziri-*' --no-pager || true
	echo
	for u in "${TIMERS[@]}"; do
		say "$u: $(systemctl is-enabled "$u" 2>/dev/null || echo unknown) / $(systemctl is-active "$u" 2>/dev/null || echo unknown)"
	done
	say "last backup run:  $(systemctl show -p ExecMainStatus --value ziri-backup.service 2>/dev/null || echo '?') (0 = success)"
	say "last verify run:  $(systemctl show -p ExecMainStatus --value ziri-verify.service 2>/dev/null || echo '?') (0 = verified)"
}

cmd_dry_run() {
	local u
	for u in "${UNITS[@]}"; do
		printf '\n───── %s ─────\n' "$UNIT_DIR/$u"
		render "$u"
	done
}

case "${1:-install}" in
	install|--install)     cmd_install ;;
	--uninstall|uninstall) cmd_uninstall ;;
	--status|status)       cmd_status ;;
	--dry-run|dry-run)     cmd_dry_run ;;
	-h|--help|help)
		sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
		;;
	*) die "unknown argument: $1 (try --help)" ;;
esac
