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
from kamra.distribution import (DISTRIBUTION, DISTRIBUTION_VERSION,
                                tag_prefix)

# Resolved per site, not fixed at import: see kamra/distribution.py for why a
# ZIRI install must not ask upstream what version it should be running.
def _repo() -> str:
	from kamra.distribution import update_repo
	return update_repo()


def _latest_url(repo: str) -> str:
	return f"https://api.github.com/repos/{repo}/releases/latest"


def _releases_url(repo: str) -> str:
	return f"https://github.com/{repo}/releases"
CACHE_KEY = "kamra:github_latest_release"
CACHE_TTL = 3600  # 1 hour — polite to GitHub's unauthenticated rate limit


def _strip_prefix(tag: str, prefix: str = "") -> str:
	t = (tag or "").strip()
	if prefix and t.startswith(prefix):
		t = t[len(prefix):]
	return t


def _parse_semver(tag: str, prefix: str = ""):
	"""`ziri-v1.0.0-rc.2` / `v2.6.2` / `2.6.2` -> comparable key.

	Returns (major, minor, patch, release_rank, prerelease_parts) where
	release_rank is 1 for a final release and 0 for a prerelease, so that
	1.0.0-rc.2 sorts BEFORE 1.0.0 as semver requires.

	The prerelease part used to be discarded outright, with a docstring saying
	so. That made `2.6.6-beta.1` compare EQUAL to `2.6.6`, so an install on the
	beta would have been told it was current - which is precisely backwards for
	the one channel where knowing your exact build matters.
	"""
	t = _strip_prefix(tag, prefix)
	m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?", t)
	if not m:
		return None
	core = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
	pre = m.group(4)
	if not pre:
		# a final release outranks every prerelease of the same core version
		return core + (1, ())
	# numeric identifiers compare numerically and rank below alphanumeric ones,
	# so rc.2 < rc.10 rather than the string order that would put rc.10 first
	parts = tuple((0, int(x)) if x.isdigit() else (1, x) for x in pre.split("."))
	return core + (0, parts)


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
	"""Newest published release of THIS distribution.

	`no_releases` is distinct from `ok: False`. A repository that has simply
	not published a release yet is a normal state - it is where this
	distribution starts - and reporting it as a failed update check would
	train the operator to ignore a panel that is telling the truth.
	"""
	repo = _repo()
	if not repo:
		return {"ok": False, "disabled": True, "no_releases": False,
		        "error": None, "tag": None, "name": None, "url": None,
		        "published_at": None}

	cached = frappe.cache.get_value(CACHE_KEY)
	if isinstance(cached, dict) and cached.get("repo") == repo:
		return cached

	req = Request(
		_latest_url(repo),
		headers={
			"Accept": "application/vnd.github+json",
			"User-Agent": f"ZIRI-PMS/{DISTRIBUTION_VERSION}",
			"X-GitHub-Api-Version": "2022-11-28",
		},
	)
	base = {"ok": False, "disabled": False, "no_releases": False,
	        "repo": repo, "tag": None, "name": None,
	        "url": _releases_url(repo), "published_at": None}
	try:
		with urlopen(req, timeout=8) as resp:  # nosemgrep: python.lang.security - public GitHub API over HTTPS
			payload = json.loads(resp.read().decode("utf-8"))
	except HTTPError as e:
		# GitHub answers 404 both for "no releases yet" and for a repository
		# that is private or misspelt. They are not the same situation and the
		# caller has to tell them apart, so ask whether the repo itself exists.
		if e.code == 404:
			# Confirm the repository itself resolves, so a typo in
			# kamra_update_repo does not masquerade as "no releases yet".
			#
			# Only an HTTP answer settles this. An earlier version caught every
			# exception here and reported "not reachable or not public", which
			# turned an ordinary network timeout into a confident claim about
			# the repository's visibility - and it fired on a repository that
			# answers 200. A timeout is evidence of nothing.
			try:
				probe = Request(
					f"https://api.github.com/repos/{repo}",
					headers={"Accept": "application/vnd.github+json",
					         "User-Agent": f"ZIRI-PMS/{DISTRIBUTION_VERSION}"},
				)
				with urlopen(probe, timeout=6) as r2:  # nosemgrep: python.lang.security - public GitHub API over HTTPS
					r2.read(1)
			except HTTPError as e2:
				# a definite answer: the repo is absent, private, or we are
				# rate limited - each worth saying precisely
				if e2.code in (404, 403):
					out = dict(base, no_releases=False, error=(
						f"{repo} returned HTTP {e2.code} - check the name, "
						"its visibility, or wait out a rate limit"))
				else:
					out = dict(base, no_releases=False,
					           error=f"{repo} returned HTTP {e2.code}")
				frappe.cache.set_value(CACHE_KEY, out, expires_in_sec=CACHE_TTL)
				return out
			except (URLError, TimeoutError, OSError):
				# inconclusive: say so, and do NOT cache a guess
				return dict(base, no_releases=False, error=(
					"no release found, and the repository could not be "
					"reached to confirm why"))
			out = dict(base, error=None, no_releases=True)
			frappe.cache.set_value(CACHE_KEY, out, expires_in_sec=CACHE_TTL)
			return out
		return dict(base, error=f"HTTP {e.code}")
	except (URLError, TimeoutError, ValueError, OSError) as e:
		return dict(base, error=str(e)[:200])

	tag = (payload.get("tag_name") or "").strip()
	out = dict(
		base,
		ok=True,
		error=None,
		tag=tag,
		name=payload.get("name") or tag,
		url=payload.get("html_url") or _releases_url(repo),
		published_at=payload.get("published_at"),
		body_preview=(payload.get("body") or "")[:400],
	)
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
	#
	# The repair is NOT just "set last_execution to now", which is what an
	# earlier version of this message said. Restarting a schedule that has been
	# stalled for days is a business event, not a maintenance one: the first
	# pass of expire_holds (every 15 min, kamra/reservation_state.py) cancels
	# every Held / Pending Payment reservation whose window lapsed while the
	# scheduler was down - including ones the guest has since paid for - and
	# run_night_audit handles exactly one business date per run and does not
	# catch up, so the missed nights are not charged by simply switching it
	# back on. The detail therefore points at the runbook rather than handing
	# an operator a one-line UPDATE for a live property.
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
			"was created. Repairing it restarts the whole schedule at once - "
			"read the runbook before you do, the first run cancels holds that "
			"lapsed during the stall and the night audit does not back-fill "
			"the days it missed.",
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
		detail = f"Frappe {ver} — ZIRI targets Frappe v16."
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
	"""Is this DISTRIBUTION current against ITS OWN releases?

	It used to read the Kamra CORE version and compare it against upstream's
	releases, which told a ZIRI install that 2.6.6 was available and linked to
	upstream's release page. Acting on that rebuilds the site from upstream and
	removes everything this distribution adds. See kamra/distribution.py.
	"""
	installed = DISTRIBUTION_VERSION
	prefix = tag_prefix()
	tag = latest.get("tag")
	url = latest.get("url")
	both = f"{DISTRIBUTION} {installed} (Kamra core {KAMRA_VERSION})"

	if latest.get("disabled"):
		return _check("version", "Version", "info",
		              f"{both}. Update checking is switched off for this site "
		              "(kamra_update_repo is empty).")

	repo = latest.get("repo") or ""
	if latest.get("no_releases"):
		# Not a failure. It is where a new distribution starts, and saying so
		# is more useful than an error the operator cannot act on.
		return _check("version", "Version", "info",
		              f"{both}. {repo} has published no releases yet, so there "
		              "is nothing to compare against.", link=url)

	if not latest.get("ok") or not tag:
		return _check("version", "Version", "info",
		              f"{both}. Could not check {repo} "
		              f"({latest.get('error') or 'unknown'}).", link=url)

	shown = _strip_prefix(tag, prefix)
	cmp = _cmp_semver(_strip_prefix(installed, prefix), shown)
	if cmp is None:
		return _check("version", "Version", "info",
		              f"{both}. Latest published is {tag}; the two cannot be "
		              "compared as versions.", link=url)
	if cmp < 0:
		return _check("version", "Version", "attention",
		              f"{both}. {shown} is available. Read the release notes "
		              "and UPDATES.md before applying it.", link=url)
	if cmp > 0:
		return _check("version", "Version", "info",
		              f"{both} is ahead of the newest published release "
		              f"({shown}) - a development build.", link=url)
	return _check("version", "Version", "passed",
	              f"{both} is the newest published release.", link=url)

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
			"distribution": DISTRIBUTION,
			"distribution_version": DISTRIBUTION_VERSION,
			"kamra": KAMRA_VERSION,
			"frappe": getattr(frappe, "__version__", None),
			"site": frappe.local.site,
		},
		"latest": latest,
		# Every instruction here names THIS distribution. The previous version
		# of this block handed the operator `bench get-app` against upstream
		# and a ghcr.io/kamra-pms image, either of which replaces the app with
		# upstream Kamra and silently removes the Algeria localization.
		"upgrade": {
			"repo": latest.get("repo") or "",
			"releases": latest.get("url"),
			"docs": "docs/product/UPDATES.md",
			"note": (
				f"{DISTRIBUTION} does not upgrade itself from this screen. "
				"Back up first, read docs/product/UPDATES.md, and apply the "
				"update from the distribution's own release - never by "
				"pointing bench or Docker at upstream Kamra, which would "
				"replace this build and remove its localization."
			),
		},
		"checks": checks,
	}
