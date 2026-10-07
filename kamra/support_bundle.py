# Copyright (c) 2026 Ilyes Keskas (Algeria)
# Part of the ZIRI PMS Algeria distribution of Kamra PMS.
# SPDX-License-Identifier: AGPL-3.0-or-later
# See NOTICE for the upstream authorship this builds on.
"""Diagnostic bundle for support, built to the specification in
docs/support/TECHNICIAN_MANUAL.md section 9.

THE POINT OF THIS FILE IS WHAT IT REFUSES TO COLLECT.

A hotel's database holds guest names, phone numbers, nationalities, ID numbers
and scans of identity documents - personal data under Algeria's Law 18-07. A
support bundle travels from the hotel to whoever is helping them, often by
email. If it carries any of that, a support call has quietly become a
third-party disclosure the guest never agreed to, and in the cross-border case
possibly an export. So the design is defensive in three layers, and the first
one is the only one that genuinely works:

  1. ALLOW-LIST COLLECTION. No regular expression recognises a guest's name.
     The reliable defence is never to read the sources that hold one. Hence
     aggregates, counts and titles - never rows, never dumps, never free text.
  2. REDACTION of the text that is collected, in memory, before it reaches
     disk, with ordered and versioned rules.
  3. A FAIL-CLOSED CANARY SCAN. Before the bundle is written out it is searched
     for the installation's actual live secrets. One hit and nothing is
     produced. A redactor that is never tested against real secrets is a
     hope, not a control.

Two commands that an engineer reaches for first are banned outright and are
never run from here, because both were checked on a live install and both print
the database root password in clear:

    docker inspect <db container>
    docker compose config

WHAT THIS CANNOT SEE
This runs inside the `backend` container, which has no Docker socket - by
design; handing the application container control of the host's Docker daemon
to improve diagnostics would be a far worse trade than the missing section.
Container state, image IDs, host disk and `docker compose ps` therefore cannot
be collected here. The bundle records that gap explicitly in
`collected_outside_container` rather than omitting the sections silently, so a
reader can tell "not applicable" from "nobody looked".
"""

from __future__ import annotations

import glob
import io
import json
import os
import platform
import re
import time
import zipfile
from datetime import datetime, timezone

import frappe

from kamra.authz import require_roles
from kamra.distribution import DISTRIBUTION, DISTRIBUTION_VERSION

BUNDLE_FORMAT = 1
# Bump when a rule is added, removed or changed. The manifest records it so a
# reader can tell which ruleset produced a bundle they are looking at.
RULESET_VERSION = 1


# ── layer 2: redaction ───────────────────────────────────────────────────
# Order matters. Multi-line and structural rules run before narrow token
# rules, so a key inside a JSON blob is caught by R-KV before a later rule
# gets a chance to half-match it. The replacement always names the rule that
# fired, so a reader can tell a redaction from data that happens to look odd.

def _quoted_value(match) -> str:
	"""Replace a key/value pair's VALUE, keeping its quotes if it had them.

	Sections are serialised to JSON and then redacted as text, so a rule that
	swallows the surrounding quotes leaves a file named `.json` that no JSON
	parser will read. That happened: configuration.json came out carrying
	`"db_password": <redacted:secret>` and died at line 5 column 18. The bundle
	exists to be read by whoever receives it, often by tooling, so redaction
	has to preserve the syntax it is editing.
	"""
	prefix, value = match.group(1), match.group(2)
	token = "<redacted:secret>"
	if value[:1] in ('"', "'"):
		q = value[0]
		return f"{prefix}{q}{token}{q}"
	return f"{prefix}{token}"


_RULES: tuple[tuple[str, re.Pattern, object], ...] = (
	("R-PEM", re.compile(
		r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
		"<redacted:private-key>"),
	("R-URL", re.compile(
		r"\b([a-z][a-z0-9+.-]*://)[^/\s@]+@", re.I),
		r"\1<redacted:url-credentials>@"),
	("R-KV", re.compile(
		r"([\w.-]*(?:pass(?:word|wd)?|secret|token|api[_-]?key|private[_-]?key"
		r"|encryption[_-]?key|credential)[\w.-]*\"?\s*[=:]\s*)"
		r"(\"[^\"]*\"|'[^']*'|[^\s,;&}]+)", re.I),
		_quoted_value),
	("R-FLAG", re.compile(
		r"(--[\w-]*(?:password|secret|token|key)[\w-]*(?:=|\s+))(\"[^\"]*\"|\S+)", re.I),
		_quoted_value),
	("R-AUTH", re.compile(
		r"((?:proxy-)?authorization:\s*)[^\"\r\n]+", re.I),
		r"\1<redacted:auth>"),
	("R-COOKIE", re.compile(
		r"((?:set-)?cookie:\s*)[^\"\r\n]+", re.I),
		r"\1<redacted:cookie>"),
	("R-QS-SECRET", re.compile(
		r"([?&](?:sid|token|api_key|api_secret|key|password|pwd|otp|reset_key"
		r"|access_token|refresh_token)=)[^&\s\"]+", re.I),
		r"\1<redacted:secret>"),
	("R-FRAPPE-TOKEN", re.compile(
		r"\btoken\s+[A-Za-z0-9]{10,}:[A-Za-z0-9]{10,}"),
		"token <redacted:frappe-token>"),
	("R-JWT", re.compile(r"\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}\b"),
		"<redacted:jwt>"),
	("R-GITHUB", re.compile(
		r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_\w{50,})\b"),
		"<redacted:github-token>"),
	("R-AWS", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
		"<redacted:aws-key>"),
	("R-SLACK", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
		"<redacted:slack-token>"),
	# Personal data. These are a backstop, not the defence - layer 1 is. They
	# exist because logs echo whatever a caller sent.
	("R-EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b"),
		"<redacted:email>"),
	("R-PHONE-DZ", re.compile(r"(?:\+213|00213|\b0)\s?[5-7]\d(?:[ .-]?\d{2}){3}\b"),
		"<redacted:phone>"),
	("R-CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b"), "<redacted:card-like>"),
)


def redact(text: str) -> tuple[str, dict[str, int]]:
	"""Apply every rule in order. Returns the text and per-rule hit counts.

	Counts go in the manifest. A section that redacted nothing when it should
	have is the signal that a rule stopped matching after a log format change,
	which is otherwise invisible.
	"""
	counts: dict[str, int] = {}
	if not text:
		return "", counts
	for rid, pattern, replacement in _RULES:
		text, n = pattern.subn(replacement, text)
		if n:
			counts[rid] = counts.get(rid, 0) + n
	return text, counts


# Keys whose VALUE is a secret regardless of what type it holds. Checked by
# name against the key, so a boolean, a number or a nested object is handled
# the same way a string is.
_SECRET_KEY = re.compile(
	r"pass(word|wd)?|secret|token|api[_-]?key|private[_-]?key|encryption[_-]?key"
	r"|credential|auth|cookie", re.I)


def redact_obj(obj, counts: dict | None = None):
	"""Redact a data STRUCTURE, then let json.dumps serialise it.

	Redacting the serialised text instead was the original design and it is
	wrong in a way that unit tests on tidy samples do not reveal: a rule that
	rewrites `"db_password": "x"` correctly will also rewrite
	`"_db_password_set": true` into an unquoted token and produce a file named
	`.json` that no parser will read. Both happened. Walking the structure
	makes validity a property of the design rather than something every future
	regular expression has to be careful not to break.

	Free text - log lines, error titles - still goes through redact(), which is
	where a pattern-based redactor belongs.
	"""
	if counts is None:
		counts = {}
	if isinstance(obj, dict):
		out = {}
		for k, v in obj.items():
			if isinstance(k, str) and _SECRET_KEY.search(k) and not isinstance(v, bool):
				out[k] = "<redacted:secret>"
				counts["R-KEY"] = counts.get("R-KEY", 0) + 1
			else:
				out[k] = redact_obj(v, counts)
		return out
	if isinstance(obj, (list, tuple)):
		return [redact_obj(v, counts) for v in obj]
	if isinstance(obj, str):
		text, c = redact(obj)
		for rid, n in c.items():
			counts[rid] = counts.get(rid, 0) + n
		return text
	return obj


# ── layer 3: the canary ──────────────────────────────────────────────────

def _live_secrets() -> list[tuple[str, str]]:
	"""The installation's real secrets, to search the finished bundle for.

	Read fresh from site config, never cached and never written anywhere. If
	one of these appears in the bundle the redactor failed and the bundle must
	not be produced - no amount of rule review substitutes for checking.
	"""
	out: list[tuple[str, str]] = []
	conf = frappe.get_site_config() or {}
	for key in ("db_password", "encryption_key", "admin_password",
	            "root_password", "mysql_root_password"):
		v = conf.get(key)
		if isinstance(v, str) and len(v) >= 6:
			out.append((key, v))
	for env_key in ("DB_PASSWORD", "MYSQL_ROOT_PASSWORD", "ADMIN_PASSWORD"):
		v = os.environ.get(env_key)
		if isinstance(v, str) and len(v) >= 6:
			out.append((env_key, v))
	return out


def _canary_scan(blobs: dict[str, str]) -> list[str]:
	"""Names of secrets found in the bundle. Values are never returned,
	logged or printed - knowing WHICH secret leaked is enough to act."""
	hits: list[str] = []
	secrets = _live_secrets()
	if not secrets:
		return ["__no_canary_available__"]
	for name, value in secrets:
		for section, text in blobs.items():
			if value in text:
				hits.append(f"{name} in {section}")
				break
	return hits


# ── layer 1: allow-list collection ───────────────────────────────────────
# Each collector returns aggregates. None of them reads a guest-bearing row.

# Config values safe to report verbatim. Everything else is reported as a KEY
# NAME with its value replaced, so a reader can see that a setting exists and
# ask about it without the bundle carrying it.
_CONFIG_VALUE_ALLOWLIST = frozenset({
	"custom_image", "custom_tag", "pull_policy", "restart_policy",
	"http_publish_port", "nginx_listen_port", "proxy_read_timeout",
	"client_max_body_size", "socketio_port", "chromium_path",
	"frappe_site_name_header", "time_zone", "developer_mode",
	"maintenance_mode", "pause_scheduler", "scheduler_disabled",
	"kamra_update_repo", "kamra_update_tag_prefix", "backup_limit",
	"db_type", "db_host", "db_port", "redis_cache", "redis_queue",
})


def _installation_id() -> str | None:
	try:
		from kamra.installation import installation_id
		return installation_id()
	except Exception:
		return None


def _section_versions() -> dict:
	from kamra import __version__ as core
	return {
		"distribution": DISTRIBUTION,
		"distribution_version": DISTRIBUTION_VERSION,
		"kamra_core": core,
		"frappe": getattr(frappe, "__version__", None),
		"installed_apps": frappe.get_installed_apps(),
		"python": platform.python_version(),
		"site": frappe.local.site,
	}


def _section_system() -> dict:
	now = datetime.now(timezone.utc)
	try:
		site_now = frappe.utils.now_datetime()
	except Exception:
		site_now = None
	return {
		"platform": platform.platform(),
		"cpu_count": os.cpu_count(),
		"utc_now": now.isoformat(),
		"site_now": str(site_now) if site_now else None,
		# the pair above is how a time-zone misconfiguration is told from
		# clock drift; it is what found the stalled scheduler
		"site_timezone": frappe.db.get_single_value("System Settings", "time_zone"),
	}


def _section_health() -> dict:
	from kamra.health import system_health
	try:
		result = system_health(refresh=1)
		# TECHNICIAN_MANUAL.md section 9: the bundle lists the codes whose
		# signals fired. Each check already carries its own code, but a reader
		# opening a 10-section bundle should not have to scan for them - this
		# is the line that goes into the ticket.
		result["codes_fired"] = [
			{"code": c["code"], "check": c["id"], "status": c["status"]}
			for c in result.get("checks", []) if c.get("code")
		]
		return result
	except Exception as e:
		return {"error": f"{type(e).__name__}: {e}"}


def _section_scheduler() -> dict:
	try:
		now = frappe.utils.now_datetime()
		total = frappe.db.count("Scheduled Job Type")
		never = frappe.db.count("Scheduled Job Type", {"last_execution": ("is", "not set")})
		future = frappe.db.sql(
			"""SELECT COUNT(*) FROM `tabScheduled Job Type`
			   WHERE COALESCE(last_execution, creation) > %s""", now)[0][0]
		last = frappe.db.sql(
			"SELECT MAX(last_execution) FROM `tabScheduled Job Type`")[0][0]
		return {
			"enabled": bool(frappe.db.get_single_value(
				"System Settings", "enable_scheduler")),
			"job_types": total,
			"never_run": never,
			"stamped_in_future": future,
			"last_execution": str(last) if last else None,
			"site_now": str(now),
		}
	except Exception as e:
		return {"error": f"{type(e).__name__}: {e}"}


def _section_queues() -> dict:
	try:
		from frappe.utils.background_jobs import get_queue, get_workers
		depths = {}
		for q in ("short", "default", "long"):
			try:
				depths[q] = len(get_queue(q))
			except Exception as e:
				depths[q] = f"unreadable: {type(e).__name__}"
		return {"workers": len(get_workers()), "queue_depth": depths}
	except Exception as e:
		return {"error": f"{type(e).__name__}: {e}"}


def _section_database() -> dict:
	"""Aggregates only. No PROCESSLIST - it carries live query text, which
	carries guest data."""
	out: dict = {}
	try:
		out["version"] = frappe.db.sql("SELECT VERSION()")[0][0]
		for var in ("Threads_connected", "Max_used_connections",
		            "Aborted_connects", "Uptime"):
			r = frappe.db.sql("SHOW GLOBAL STATUS LIKE %s", var)
			if r:
				out[var] = r[0][1]
		r = frappe.db.sql("SHOW VARIABLES LIKE 'max_connections'")
		if r:
			out["max_connections"] = r[0][1]
		out["size_mb"] = frappe.db.sql(
			"""SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 1)
			   FROM information_schema.tables WHERE table_schema = DATABASE()""")[0][0]
		out["table_count"] = frappe.db.sql(
			"""SELECT COUNT(*) FROM information_schema.tables
			   WHERE table_schema = DATABASE()""")[0][0]
	except Exception as e:
		out["error"] = f"{type(e).__name__}: {e}"
	return out


def _section_migrations() -> dict:
	try:
		applied = frappe.db.sql(
			"""SELECT patch, creation FROM `tabPatch Log`
			   ORDER BY creation DESC LIMIT 20""", as_dict=True)
		applied_set = {r["patch"] for r in frappe.db.sql(
			"SELECT patch FROM `tabPatch Log`", as_dict=True)}
		declared, pending = [], []
		path = frappe.get_app_path("kamra", "..", "kamra", "patches.txt")
		try:
			with open(os.path.normpath(path), encoding="utf-8") as f:
				for line in f:
					line = line.strip()
					if line and not line.startswith(("#", "[")):
						declared.append(line)
		except OSError as e:
			return {"error": f"patches.txt unreadable: {e}"}
		pending = [p for p in declared if p not in applied_set]
		return {
			"declared": len(declared),
			"applied": len(applied_set),
			"pending": pending,
			"recent": [{"patch": r["patch"], "at": str(r["creation"])}
			           for r in applied],
		}
	except Exception as e:
		return {"error": f"{type(e).__name__}: {e}"}


def _section_config() -> dict:
	"""Key names always; values only from the allow-list. An unknown key is
	reported as present-but-redacted rather than dropped, because the fact
	that someone set it is itself diagnostic."""
	try:
		conf = frappe.get_site_config() or {}
	except Exception as e:
		return {"error": f"{type(e).__name__}: {e}"}
	out = {}
	for k in sorted(conf):
		if k.lower() in _CONFIG_VALUE_ALLOWLIST:
			out[k] = conf[k]
		else:
			v = conf[k]
			out[k] = f"<redacted:not-allow-listed:{type(v).__name__}>"
	# whether the password exists, and a coarse length class - never the value
	pw = conf.get("db_password")
	out["_db_password_set"] = bool(pw)
	out["_db_password_length_class"] = (
		"none" if not pw else "short(<12)" if len(str(pw)) < 12 else "ok(>=12)")
	return out


def _section_backups() -> dict:
	try:
		d = frappe.get_site_path("private", "backups")
		files = sorted(glob.glob(os.path.join(d, "*.sql.gz")),
		               key=os.path.getmtime, reverse=True)
		# The audit trail answers "was a restore ever tested, and when" from
		# recorded fact rather than from the presence of files. A directory full
		# of dumps says a backup was WRITTEN; only a verify line says one was
		# ever read back. That distinction is the whole point of the trail.
		# The prefix is imported rather than repeated: two copies of a marker
		# that must match is a silent break waiting for whoever edits one.
		from kamra.monitoring import _AUDIT_PREFIX, recent_data_operations

		trail = recent_data_operations(15)
		verifies = [t for t in trail
		            if t["subject"].startswith(f"{_AUDIT_PREFIX} verify")
		            and t["status"] == "Success"]
		return {
			"count": len(files),
			"newest_age_hours": (
				round((time.time() - os.path.getmtime(files[0])) / 3600, 1)
				if files else None),
			"newest_size_mb": (
				round(os.path.getsize(files[0]) / (1024 ** 2), 1) if files else None),
			# filenames only - never contents, never the files themselves
			"filenames": [os.path.basename(f) for f in files[:10]],
			"restore_tested_at": (
				str(verifies[0]["creation"]) if verifies
				else "never - no successful verify has been recorded"),
			"data_operations": [
				{"when": str(t["creation"]), "what": t["subject"], "result": t["status"]}
				for t in trail
			],
		}
	except Exception as e:
		return {"error": f"{type(e).__name__}: {e}"}


def _section_entitlement() -> dict:
	"""The licence-metadata section ERROR_CODES.md reserved.

	Included because the first question on a support call is "what did this
	customer buy", and the answer being in the bundle saves asking. It is a
	record, not a credential: it authorises nothing, and the vendor reading
	this bundle is the party that issued it.
	"""
	try:
		from kamra.entitlement import state
		s = state()
		return {
			"state": s["state"],
			"days": s.get("days"),
			"record": s.get("record"),
			"enforced": False,
			"note": ("Informational. ZIRI PMS is AGPL-3.0 and no feature "
			         "depends on this record."),
		}
	except Exception as e:
		return {"error": f"{type(e).__name__}: {e}"}


def _section_errors() -> dict:
	"""Error Log TITLES and counts. Never the `error` column - it holds
	tracebacks, and a traceback holds whatever was being processed."""
	try:
		rows = frappe.db.sql(
			"""SELECT method, COUNT(*) AS n, MAX(creation) AS last
			   FROM `tabError Log`
			   WHERE creation > NOW() - INTERVAL 7 DAY
			   GROUP BY method ORDER BY n DESC LIMIT 25""", as_dict=True)
		return {"window": "7 days", "by_title": [
			{"title": (r["method"] or "")[:120], "count": r["n"],
			 "last": str(r["last"])} for r in rows]}
	except Exception as e:
		return {"error": f"{type(e).__name__}: {e}"}


_SECTIONS = {
	"versions": _section_versions,
	"system": _section_system,
	"health": _section_health,
	"scheduler": _section_scheduler,
	"queues": _section_queues,
	"database": _section_database,
	"migrations": _section_migrations,
	"configuration": _section_config,
	"backups": _section_backups,
	"entitlement": _section_entitlement,
	"errors": _section_errors,
}


def collect() -> tuple[dict, dict, list[str]]:
	"""Returns (sections, redaction_counts, failed_section_names)."""
	sections, counts, failed = {}, {}, []
	for name, fn in _SECTIONS.items():
		try:
			data = fn()
		except Exception as e:
			data = {"error": f"{type(e).__name__}: {e}"}
			failed.append(name)
		c: dict[str, int] = {}
		cleaned = redact_obj(data, c)
		for k, v in c.items():
			counts[k] = counts.get(k, 0) + v
		sections[name] = json.dumps(cleaned, indent=2, default=str,
		                            ensure_ascii=False)
	return sections, counts, failed


def build(out_dir: str | None = None) -> dict:
	"""Write a support bundle. Returns a summary, or refuses and explains.

	Refusal is the designed outcome when the canary fires. A bundle that is
	not produced costs a support engineer an hour; one that leaks a guest
	register costs the hotel its relationship with its guests and possibly a
	regulator's attention.
	"""
	started = datetime.now(timezone.utc)
	sections, counts, failed = collect()

	hits = _canary_scan(sections)
	if hits and hits != ["__no_canary_available__"]:
		# Deliberately not written anywhere: refusing means refusing.
		return {
			"ok": False,
			"refused": True,
			"reason": "canary scan found live secrets in the collected text",
			"leaked": hits,
			"action": ("A redaction rule failed. Fix kamra/support_bundle.py "
			           "before generating a bundle; do not bypass this."),
		}

	manifest = {
		"bundle_format": BUNDLE_FORMAT,
		"ruleset_version": RULESET_VERSION,
		"generator": f"{DISTRIBUTION} {DISTRIBUTION_VERSION}",
		"created_utc": started.isoformat(),
		"bundle_id": frappe.generate_hash(length=12),
		# Names the deployment across bundles, tickets and update checks. Not a
		# secret (kamra/installation.py), so it belongs in the manifest rather
		# than being redacted out of it.
		"installation_id": _installation_id(),
		"site": frappe.local.site,
		"sections": sorted(sections),
		"failed_sections": failed,
		"redaction_counts": counts,
		"canary": ("no live secret found in bundle"
		           if hits != ["__no_canary_available__"]
		           else "NOT RUN - no readable secret to search for; treat this "
		                "bundle as unverified"),
		"collected_outside_container": [
			"container state and health (docker compose ps)",
			"image id, tag and creation time",
			"host disk usage and docker system df",
			"per-container log files and their sizes",
			"host clock and OS details",
		],
		"never_collected": [
			"passwords, API keys, tokens, private keys, the encryption key",
			"guest personal data and identity documents",
			"database dumps and backup archives",
			"raw docker inspect / docker compose config / SHOW PROCESSLIST",
			"Error Log tracebacks",
		],
	}

	out_dir = out_dir or frappe.get_site_path("private", "files")
	os.makedirs(out_dir, exist_ok=True)
	name = f"support-bundle-{started.strftime('%Y%m%d-%H%M%S')}-{manifest['bundle_id']}.zip"
	path = os.path.join(out_dir, name)

	buf = io.BytesIO()
	with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
		z.writestr("manifest.json",
		           json.dumps(manifest, indent=2, ensure_ascii=False))
		for sec, text in sections.items():
			z.writestr(f"{sec}.json", text)
	data = buf.getvalue()
	with open(path, "wb") as f:
		f.write(data)

	return {
		"ok": True,
		"path": path,
		"size_kb": round(len(data) / 1024, 1),
		"sections": len(sections),
		"failed_sections": failed,
		"redactions": sum(counts.values()),
		"redaction_counts": counts,
	}


@frappe.whitelist()
@require_roles("Hotel Admin", "System Manager", "Administrator")
def create_support_bundle() -> dict:
	return build()
