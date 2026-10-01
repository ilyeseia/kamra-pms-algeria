"""Bench commands: `bench kamra-doctor` and `bench kamra-support-bundle`.

Both capabilities already existed as whitelisted functions, reachable only
through `bench --site X execute kamra.health.system_health`, which returns a
wall of JSON. That is a fine API and a poor tool. A technician diagnosing a
hotel at 23:00 needs the answer, an exit code a script can branch on, and no
need to remember a dotted module path.

EXIT CODES, because a human is not always the caller
    0  healthy, or healthy with advisories
    1  at least one check FAILED
    2  could not run at all (no site, database unreachable)

`attention` deliberately does not fail the command. An installation with no
backup yet, or a newer release available, is not broken, and a monitoring
system that pages someone for it will be muted within a week - at which point
the real failures are muted too. Use --strict when you do want advisories to
fail, such as in a pre-update gate where "no recent backup" must stop the line.
"""

from __future__ import annotations

import json
import sys

import click
import frappe
from frappe.commands import get_site, pass_context

_MARK = {
	"passed": "OK",
	"attention": "WARN",
	"failed": "FAIL",
	"info": "INFO",
}


def _print_human(result: dict) -> None:
	inst = result.get("installed", {})
	click.echo("")
	click.echo(f"  {inst.get('distribution', 'Kamra')} "
	           f"{inst.get('distribution_version', '')}"
	           f"  (core {inst.get('kamra', '?')}, Frappe {inst.get('frappe', '?')})")
	click.echo(f"  site: {inst.get('site', '?')}")
	click.echo("")
	for c in result.get("checks", []):
		mark = _MARK.get(c["status"], c["status"].upper())
		click.echo(f"  [{mark:<4}] {c['title']:<22} {c['detail']}")
	s = result.get("summary", {})
	click.echo("")
	click.echo(f"  {result.get('overall', '?').upper()}  "
	           f"passed {s.get('passed', 0)} · attention {s.get('attention', 0)} · "
	           f"failed {s.get('failed', 0)} · info {s.get('info', 0)}")
	click.echo("")


@click.command("kamra-doctor")
@click.option("--json", "as_json", is_flag=True,
              help="Machine-readable output instead of the table.")
@click.option("--strict", is_flag=True,
              help="Exit non-zero on advisories too, for a pre-update gate.")
@pass_context
def kamra_doctor(context, as_json: bool, strict: bool):
	"""Check this installation and say what is actually wrong."""
	site = get_site(context)
	try:
		frappe.init(site=site)
		frappe.connect()
	except Exception as e:
		click.echo(f"cannot open site {site}: {type(e).__name__}: {e}", err=True)
		sys.exit(2)
	try:
		from kamra.health import system_health
		# the check is read-only, but it is whitelisted and role-gated; on the
		# command line the caller already has shell access to the bench
		frappe.set_user("Administrator")
		result = system_health(refresh=1)
	except Exception as e:
		click.echo(f"health check failed to run: {type(e).__name__}: {e}", err=True)
		sys.exit(2)
	finally:
		frappe.destroy()

	if as_json:
		click.echo(json.dumps(result, indent=2, default=str, ensure_ascii=False))
	else:
		_print_human(result)

	summary = result.get("summary", {})
	if summary.get("failed"):
		sys.exit(1)
	if strict and summary.get("attention"):
		sys.exit(1)
	sys.exit(0)


@click.command("kamra-support-bundle")
@click.option("--out", "out_dir", default=None,
              help="Directory to write into. Defaults to the site's private files.")
@pass_context
def kamra_support_bundle(context, out_dir):
	"""Build a redacted diagnostic bundle for support.

	Refuses to produce anything if its canary scan finds a live secret in the
	collected text - see kamra/support_bundle.py. A refusal is a defect report
	about the redactor, not a reason to retry.
	"""
	site = get_site(context)
	try:
		frappe.init(site=site)
		frappe.connect()
	except Exception as e:
		click.echo(f"cannot open site {site}: {type(e).__name__}: {e}", err=True)
		sys.exit(2)
	try:
		from kamra.support_bundle import build
		frappe.set_user("Administrator")
		result = build(out_dir)
	except Exception as e:
		click.echo(f"bundle failed to run: {type(e).__name__}: {e}", err=True)
		sys.exit(2)
	finally:
		frappe.destroy()

	if not result.get("ok"):
		click.echo("")
		click.echo("  REFUSED — no bundle was written.")
		click.echo(f"  {result.get('reason', 'unknown')}")
		for hit in result.get("leaked", []):
			click.echo(f"    found: {hit}")
		click.echo(f"  {result.get('action', '')}")
		click.echo("")
		sys.exit(1)

	click.echo("")
	click.echo(f"  wrote {result['path']}")
	click.echo(f"  {result['size_kb']} KB · {result['sections']} sections · "
	           f"{result['redactions']} redactions {result.get('redaction_counts', {})}")
	if result.get("failed_sections"):
		click.echo(f"  sections that failed to collect: "
		           f"{', '.join(result['failed_sections'])}")
	click.echo("  Read it before sending it. It is designed to be safe to share,")
	click.echo("  but you are the one accountable for what leaves the hotel.")
	click.echo("")
	sys.exit(0)


commands = [kamra_doctor, kamra_support_bundle]
