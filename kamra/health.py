"""Site health and version checks for self-hosted / cloud installs.

Read-only diagnostics for Admin → System Health. Upgrade is guided (bench /
Docker / Frappe Cloud) — we never mutate the install from this screen.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import frappe
from frappe.utils import cint

from kamra import __version__ as KAMRA_VERSION
from kamra.authz import require_roles

GITHUB_REPO = "Kamra-PMS/kamra-pms"
GITHUB_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES = f"https://github.com/{GITHUB_REPO}/releases"
CACHE_KEY = "kamra:github_latest_release"
CACHE_TTL = 3600  # 1 hour — polite to GitHub's unauthenticated rate limit


def _parse_semver(tag: str) -> tuple[int, int, int] | None:
	"""v2.6.2 / 2.6.2 → (2, 6, 2). Ignores prerelease suffixes for compare."""
	m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", (tag or "").strip())
	if not m:
		return None
	return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _cmp_semver(a: str, b: str) -> int | None:
	"""-1 if a < b, 0 equal, 1 if a > b, None if unparsable."""
	pa, pb = _parse_semver(a), _parse_semver(b)
	if not pa or not pb:
		return None
	if pa < pb:
		return -1
	if pa > pb:
		return 1
	return 0


def _fetch_github_latest() -> dict:
	cached = frappe.cache.get_value(CACHE_KEY)
	if isinstance(cached, dict) and cached.get("tag"):
		return cached

	req = Request(
		GITHUB_LATEST,
		headers={
			"Accept": "application/vnd.github+json",
			"User-Agent": f"Kamra-PMS/{KAMRA_VERSION}",
			"X-GitHub-Api-Version": "2022-11-28",
		},
	)
	try:
		with urlopen(req, timeout=8) as resp:  # nosemgrep: python.lang.security - public GitHub API over HTTPS
			payload = json.loads(resp.read().decode("utf-8"))
	except (HTTPError, URLError, TimeoutError, ValueError, OSError) as e:
		return {
			"ok": False,
			"error": str(e)[:200],
			"tag": None,
			"name": None,
			"url": GITHUB_RELEASES,
			"published_at": None,
		}

	tag = (payload.get("tag_name") or "").strip()
	out = {
		"ok": True,
		"error": None,
		"tag": tag,
		"name": payload.get("name") or tag,
		"url": payload.get("html_url") or GITHUB_RELEASES,
		"published_at": payload.get("published_at"),
		"body_preview": (payload.get("body") or "")[:400],
	}
	frappe.cache.set_value(CACHE_KEY, out, expires_in_sec=CACHE_TTL)
	return out


def _check(id_: str, title: str, status: str, detail: str, *,
           link: str | None = None) -> dict:
	"""status: passed | attention | failed | info"""
	return {
		"id": id_,
		"title": title,
		"status": status,
		"detail": detail,
		"link": link,
	}


def _disk_check() -> dict:
	try:
		usage = shutil.disk_usage(frappe.get_site_path())
		free_gb = usage.free / (1024 ** 3)
		total_gb = usage.total / (1024 ** 3)
		pct_free = (usage.free / usage.total) * 100 if usage.total else 0
		if free_gb < 2 or pct_free < 5:
			status = "failed"
		elif free_gb < 5 or pct_free < 10:
			status = "attention"
		else:
			status = "passed"
		return _check(
			"disk",
			"Disk space",
			status,
			f"{free_gb:.1f} GB free of {total_gb:.1f} GB ({pct_free:.0f}% free).",
		)
	except OSError as e:
		return _check("disk", "Disk space", "info", f"Could not measure: {e}")


def _fmt_age(seconds: float) -> str:
	if seconds < 90:
		return f"{int(seconds)}s ago"
	if seconds < 5400:
		return f"{int(seconds // 60)} min ago"
	if seconds < 172800:
		return f"{seconds / 3600:.1f} h ago"
	return f"{int(seconds // 86400)} days ago"


def _scheduler_check() -> dict:
	"""Is the scheduler ENABLED, and has it actually RUN?

	These are two different questions and only the first used to be asked. The
	setting lives in System Settings; the scheduler itself is a separate
	process in its own container, and it can be dead while the setting still
	reads enabled. On the trial install this check reported "passed" with a
	green tick while `tabScheduled Job Type` held no execution record at all -
	nothing had ever run, and the night audit with it. A check that cannot
	distinguish "working" from "switched on" is not a check.
	"""
	enabled = cint(frappe.db.get_single_value("System Settings", "enable_scheduler"))
	if not enabled:
		return _check(
			"scheduler",
			"Scheduler",
			"attention",
			"Scheduler is off — night audit and reminder jobs will not run.",
			link="/app/system-settings",
		)

	try:
		last = frappe.db.sql(
			"""SELECT MAX(last_execution) FROM `tabScheduled Job Type`
			   WHERE last_execution IS NOT NULL"""
		)
		last = last[0][0] if last else None
	except Exception as e:
		return _check("scheduler", "Scheduler", "info",
		              f"Enabled, but the job log could not be read: {str(e)[:120]}")

	# The stall that hides itself: Frappe computes a job's next run from
	# `last_execution or creation`. Change the site's time zone to a lower UTC
	# offset after the site was built and every one of those rows is suddenly
	# stamped in the FUTURE, so nothing is ever due. The scheduler process
	# stays alive, logs nothing, and `bench doctor` reports workers online -
	# while the night audit never runs. Measured on the trial install: all 51
	# job types stamped 16:15 against a site clock reading 14:19, and zero
	# executions since the site was created. Worth naming explicitly, because
	# "has never run" sends an operator to look at a container that is fine.
	try:
		future = frappe.db.sql(
			"""SELECT COUNT(*) FROM `tabScheduled Job Type`
			   WHERE COALESCE(last_execution, creation) > %s""",
			frappe.utils.now_datetime(),
		)[0][0]
	except Exception:
		future = 0
	if future:
		return _check(
			"scheduler",
			"Scheduler",
			"failed",
			f"{future} scheduled job(s) are stamped in the future, so none will "
			"ever come due and the night audit will not run. This happens when "
			"the site time zone is moved to a lower UTC offset after the site "
			"was created. Fix: set last_execution to now on the affected rows.",
			link="/app/scheduled-job-type",
		)

	if not last:
		# Normal for the first minutes of a fresh site; alarming after that.
		return _check(
			"scheduler",
			"Scheduler",
			"attention",
			"Enabled, but no scheduled job has ever run. Expected on a site "
			"created minutes ago; otherwise the scheduler container is not "
			"running and the night audit is not happening.",
			link="/app/scheduled-job-type",
		)

	age = (frappe.utils.now_datetime() - frappe.utils.get_datetime(last)).total_seconds()
	when = _fmt_age(age)
	if age > 86400:
		status, detail = "failed", (
			f"Enabled, but the last scheduled job ran {when}. The night audit "
			"has not run for over a day.")
	elif age > 21600:
		status, detail = "attention", (
			f"Enabled, but the last scheduled job ran {when}.")
	else:
		status, detail = "passed", f"Running — last job {when}."
	return _check("scheduler", "Scheduler", status, detail,
	              link="/app/scheduled-job-type")


def _redis_check() -> dict:
	"""Round-trip a value. A connection that accepts and returns nothing is
	not a working cache, so this writes and reads back rather than pinging."""
	try:
		token = f"health-{time.time()}"
		frappe.cache.set_value("kamra:health_probe", token, expires_in_sec=60)
		got = frappe.cache.get_value("kamra:health_probe")
		if got != token:
			return _check("redis", "Redis", "failed",
			              "Cache accepted a write but returned a different value.")
		return _check("redis", "Redis", "passed", "Cache read-write round trip OK.")
	except Exception as e:
		return _check("redis", "Redis", "failed",
		              f"Cache unreachable: {str(e)[:160]}")


def _workers_check() -> dict:
	"""Are there live RQ workers, and is anything piling up behind them?

	Queues drain to zero on a healthy site. A deep queue with workers present
	means they are stuck or too slow; no workers at all means nothing queued
	will ever run - emails, sync and the night audit included.
	"""
	try:
		from frappe.utils.background_jobs import get_queue, get_workers
	except ImportError as e:
		return _check("workers", "Background workers", "info",
		              f"Cannot inspect queues on this Frappe build: {e}")
	try:
		workers = get_workers()
	except Exception as e:
		return _check("workers", "Background workers", "failed",
		              f"Could not reach the queue broker: {str(e)[:160]}")

	if not workers:
		return _check("workers", "Background workers", "failed",
		              "No worker is running. Queued jobs will never execute.")

	depth, unreadable = 0, []
	for q in ("short", "default", "long"):
		try:
			depth += len(get_queue(q))
		except Exception:
			unreadable.append(q)

	n = len(workers)
	note = f" Queues unreadable: {', '.join(unreadable)}." if unreadable else ""
	if depth > 1000:
		status = "attention"
		detail = f"{n} worker(s), but {depth} jobs are waiting.{note}"
	else:
		status = "passed"
		detail = f"{n} worker(s) running, {depth} job(s) queued.{note}"
	return _check("workers", "Background workers", status, detail)


def _backup_check() -> dict:
	"""How old is the newest backup this site took itself?

	Deliberately never "failed": a hotel may back up by volume snapshot, by
	the host's own tooling, or to a destination this process cannot see, and
	a red cross on a site that is in fact well protected trains people to
	ignore the panel. It reports what it can see and says what it cannot.
	"""
	try:
		d = frappe.get_site_path("private", "backups")
		files = glob.glob(os.path.join(d, "*.sql.gz"))
	except Exception as e:
		return _check("backup", "Backup", "info",
		              f"Could not read the backup directory: {str(e)[:140]}")

	if not files:
		return _check(
			"backup",
			"Backup",
			"attention",
			"No backup taken by this site. If backups are handled outside the "
			"application (volume snapshots, host tooling), that is fine and "
			"this check cannot see them - verify a restore has been tested.",
		)

	newest = max(files, key=os.path.getmtime)
	age = time.time() - os.path.getmtime(newest)
	size_mb = os.path.getsize(newest) / (1024 ** 2)
	when = _fmt_age(age)
	status = "attention" if age > 172800 else "passed"
	return _check(
		"backup",
		"Backup",
		status,
		f"Newest backup {when} ({size_mb:.1f} MB), {len(files)} on disk. "
		"Age only - this does not prove it can be restored.",
	)


def _database_check() -> dict:
	try:
		frappe.db.sql("select 1")
		return _check("database", "Database", "passed", "Responding to queries.")
	except Exception as e:
		return _check("database", "Database", "failed", str(e)[:200])


def _frappe_check() -> dict:
	ver = getattr(frappe, "__version__", None) or "unknown"
	major = int(str(ver).split(".")[0]) if str(ver)[0:1].isdigit() else 0
	if major and major < 16:
		status = "attention"
		detail = f"Frappe {ver} — Kamra targets Frappe v16."
	else:
		status = "passed"
		detail = f"Frappe {ver}."
	return _check("frappe", "Frappe", status, detail)


def _apps_check() -> dict:
	apps = frappe.get_installed_apps()
	need = ["frappe", "kamra"]
	missing = [a for a in need if a not in apps]
	if missing:
		return _check(
			"apps",
			"Installed apps",
			"failed",
			f"Missing required app(s): {', '.join(missing)}. Installed: {', '.join(apps)}.",
		)
	optional = [a for a in ("payments", "erpnext", "hrms") if a in apps]
	extra = f" Optional: {', '.join(optional)}." if optional else ""
	return _check(
		"apps",
		"Installed apps",
		"passed",
		f"kamra + frappe present.{extra}",
	)


def _timezone_check() -> dict:
	site_tz = frappe.db.get_single_value("System Settings", "time_zone") or ""
	props = frappe.get_all("Property", fields=["name", "timezone"], limit=5)
	if not props:
		return _check(
			"timezone",
			"Time zone",
			"attention",
			f"Site clock is {site_tz or 'unset'}; no Property yet.",
		)
	mismatched = [
		p.name for p in props
		if (p.timezone or "").strip() and (p.timezone or "").strip() != site_tz
	]
	if mismatched and len(props) == 1:
		return _check(
			"timezone",
			"Time zone",
			"attention",
			f"Property timezone differs from site ({site_tz}). "
			"Set Time zone under Admin → Settings → Property.",
			link="/kamra/settings",
		)
	return _check(
		"timezone",
		"Time zone",
		"passed",
		f"Site clock: {site_tz or 'unset'}.",
	)


def _version_check(latest: dict) -> dict:
	installed = KAMRA_VERSION
	tag = latest.get("tag")
	url = latest.get("url") or GITHUB_RELEASES
	if not latest.get("ok") or not tag:
		return _check(
			"version",
			"Version",
			"info",
			f"Installed {installed}. Could not reach GitHub "
			f"({latest.get('error') or 'unknown'}).",
			link=url,
		)
	cmp = _cmp_semver(installed, tag)
	if cmp is None:
		return _check(
			"version",
			"Version",
			"info",
			f"Installed {installed}; latest on GitHub is {tag}.",
			link=url,
		)
	if cmp < 0:
		return _check(
			"version",
			"Version",
			"attention",
			f"Installed {installed} — latest stable is {tag.lstrip('v')}.",
			link=url,
		)
	if cmp > 0:
		return _check(
			"version",
			"Version",
			"info",
			f"Installed {installed} is ahead of latest GitHub release {tag} "
			"(develop / pre-release build).",
			link=url,
		)
	return _check(
		"version",
		"Version",
		"passed",
		f"Installed {installed} matches latest stable {tag}.",
		link=url,
	)


@frappe.whitelist()
@require_roles("Hotel Admin", "System Manager", "Administrator")
def system_health(refresh: int = 0):
	"""Admin diagnostics: version vs GitHub + site component checks."""
	if cint(refresh):
		frappe.cache.delete_value(CACHE_KEY)

	latest = _fetch_github_latest()
	checks = [
		_version_check(latest),
		_frappe_check(),
		_apps_check(),
		_database_check(),
		_redis_check(),
		_workers_check(),
		_scheduler_check(),
		_backup_check(),
		_disk_check(),
		_timezone_check(),
	]

	summary = {
		"passed": sum(1 for c in checks if c["status"] == "passed"),
		"attention": sum(1 for c in checks if c["status"] == "attention"),
		"failed": sum(1 for c in checks if c["status"] == "failed"),
		"info": sum(1 for c in checks if c["status"] == "info"),
	}
	overall = "passed"
	if summary["failed"]:
		overall = "failed"
	elif summary["attention"]:
		overall = "attention"

	return {
		"overall": overall,
		"summary": summary,
		"installed": {
			"kamra": KAMRA_VERSION,
			"frappe": getattr(frappe, "__version__", None),
			"site": frappe.local.site,
		},
		"latest": latest,
		"upgrade": {
			"docs": "https://kamrapms.com/docs/self-hosting/",
			"releases": GITHUB_RELEASES,
			"docker_latest": "ghcr.io/kamra-pms/kamra:latest",
			"docker_nightly": "ghcr.io/kamra-pms/kamra:nightly",
			"bench": (
				"bench get-app kamra https://github.com/Kamra-PMS/kamra-pms "
				"--branch main && bench --site <site> migrate && bench build "
				"--app kamra && bench restart"
			),
			"note": (
				"Kamra does not auto-upgrade the site from this screen. "
				"Self-host: pull the new image or bench update, then migrate. "
				"Frappe Cloud: create a Marketplace release from main."
			),
		},
		"checks": checks,
	}
