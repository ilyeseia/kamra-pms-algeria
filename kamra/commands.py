# Copyright (c) 2026 Ilyes Keskas (Algeria)
# Part of the ZIRI PMS Algeria distribution of Kamra PMS.
# SPDX-License-Identifier: AGPL-3.0-or-later
# See NOTICE for the upstream authorship this builds on.
"""Bench commands: `bench ziri-doctor` and `bench ziri-support-bundle`.

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
	click.echo(f"  {inst.get('distribution', 'ZIRI')} "
	           f"{inst.get('distribution_version', '')}"
	           f"  (core {inst.get('kamra', '?')}, Frappe {inst.get('frappe', '?')})")
	click.echo(f"  site: {inst.get('site', '?')}")
	click.echo("")
	for c in result.get("checks", []):
		mark = _MARK.get(c["status"], c["status"].upper())
		# The code goes before the detail, not after: it is the part a
		# technician reads out on the phone and searches ERROR_CODES.md for,
		# and the detail is long enough to wrap off the end of a narrow
		# terminal and take a trailing code with it.
		code = f"{c.get('code') or '':<16}"
		click.echo(f"  [{mark:<4}] {c['title']:<22} {code}{c['detail']}")
	s = result.get("summary", {})
	click.echo("")
	click.echo(f"  {result.get('overall', '?').upper()}  "
	           f"passed {s.get('passed', 0)} · attention {s.get('attention', 0)} · "
	           f"failed {s.get('failed', 0)} · info {s.get('info', 0)}")
	fired = [c["code"] for c in result.get("checks", []) if c.get("code")]
	if fired:
		# One line to carry into a ticket, so the codes do not have to be read
		# out of the table one at a time.
		click.echo(f"  codes: {', '.join(fired)}  "
		           "(docs/product/ERROR_CODES.md)")
	click.echo("")


@click.command("ziri-doctor")
@click.option("--json", "as_json", is_flag=True,
              help="Machine-readable output instead of the table.")
@click.option("--strict", is_flag=True,
              help="Exit non-zero on advisories too, for a pre-update gate.")
@pass_context
def ziri_doctor(context, as_json: bool, strict: bool):
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
		# The check is read-only and role-gated. Elevating here is not a
		# privilege escalation: reaching this line already required shell
		# access to the bench container, which is strictly more power than
		# the Administrator role inside it.
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- CLI context; caller already holds bench shell access, and system_health only reads
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


@click.command("ziri-support-bundle")
@click.option("--out", "out_dir", default=None,
              help="Directory to write into. Defaults to the site's private files.")
@pass_context
def ziri_support_bundle(context, out_dir):
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
		# Same reasoning as ziri-doctor above. The bundle collects aggregates
		# and writes one file into the site's private directory; it changes no
		# document and the canary refuses the write if anything leaked.
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser -- CLI context; caller already holds bench shell access, and the collector only reads
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


@click.command("ziri-entitlement")
@click.option("--set", "plan", default=None,
              help="Record a plan, e.g. --set 'Support - Standard'.")
@click.option("--expires", default=None, help="Renewal date, YYYY-MM-DD.")
@click.option("--customer", default=None, help="Who the entitlement is for.")
@click.option("--reference", default=None, help="Contract or invoice number.")
@click.option("--starts", default=None, help="Start date, YYYY-MM-DD.")
@click.option("--services", default=None,
              help="Comma-separated vendor services, e.g. updates,support.")
@click.option("--clear", is_flag=True, help="Remove the record.")
@click.option("--fetch", "do_fetch", is_flag=True,
              help="Ask the vendor now (needs kamra_entitlement_url).")
@pass_context
def ziri_entitlement(context, plan, expires, customer, reference, starts,
                     services, clear, do_fetch):
	"""Show or set what this installation's customer bought.

	This RECORDS a commercial relationship. It does not enforce one: ZIRI PMS
	is AGPL-3.0 and no feature of it depends on this record. Read the header of
	kamra/entitlement.py before changing that.

	Only a shell can write it, deliberately - the customer should not be the
	one typing what they agreed to buy.
	"""
	site = get_site(context)
	try:
		frappe.init(site=site)
		frappe.connect()
	except Exception as e:
		click.echo(f"cannot open site {site}: {type(e).__name__}: {e}", err=True)
		sys.exit(2)
	try:
		from kamra.entitlement import clear_record, set_record, state

		if clear:
			result = clear_record()
			click.echo("")
			click.echo("  record removed. An install with no entitlement is a")
			click.echo("  supported state, not an unlicensed one.")
		elif do_fetch:
			from kamra.entitlement_sync import sync

			outcome = sync(force=True)
			click.echo("")
			click.echo(f"  fetch:    {outcome['outcome']}")
			if outcome.get("detail"):
				click.echo(f"  detail:   {outcome['detail']}")
			if outcome.get("changed"):
				click.echo(f"  changed:  {', '.join(outcome['changed'])}")
			elif outcome.get("ok") and not outcome.get("acted"):
				click.echo("  nothing to change - the stored record already "
				           "matches.")
			if outcome["outcome"] == "not-configured":
				click.echo("")
				click.echo("  Set the vendor's endpoint first:")
				click.echo("    bench --site <site> set-config "
				           "kamra_entitlement_url \\")
				click.echo("      \"https://vendor.example/api/method/"
				           "ziri_vendor.api.entitlement\"")
			result = state()
		elif plan:
			if expires:
				# Checked before writing, because a date that will not parse
				# turns the record into LICENSE-004 and the person who typed
				# it is standing right here.
				try:
					frappe.utils.getdate(expires)
				except Exception:
					click.echo(f"  --expires {expires!r} is not a date "
					           "(use YYYY-MM-DD)", err=True)
					sys.exit(2)
			result = set_record(plan, expires=expires, customer=customer,
			                    reference=reference, starts=starts,
			                    services=services)
		else:
			result = state()
	except Exception as e:
		click.echo(f"could not read or write the record: "
		           f"{type(e).__name__}: {e}", err=True)
		sys.exit(2)
	finally:
		frappe.destroy()

	rec = result.get("record") or {}
	click.echo("")
	click.echo(f"  state:    {result['state']}")
	for field in ("plan", "customer", "reference", "starts", "expires"):
		if rec.get(field):
			click.echo(f"  {field + ':':<11}{rec[field]}")
	if rec.get("services"):
		click.echo(f"  services: {', '.join(rec['services'])}")
	if result.get("days") is not None:
		d = result["days"]
		click.echo(f"  days:     {d}" + (" (past)" if d < 0 else ""))

	# Where the record came from. A technician looking at last year's plan
	# needs to tell "nobody updated it" from "the vendor is unreachable".
	try:
		from kamra.entitlement_sync import last_sync

		s = last_sync()
	except Exception:
		s = {"configured": False}
	click.echo("")
	if not s.get("configured"):
		click.echo("  vendor:   not configured - the record is set by hand")
		click.echo("            (kamra_entitlement_url). This is the default,")
		click.echo("            and a supported way to run.")
	else:
		click.echo(f"  vendor:   last checked {s.get('last_attempt') or 'never'}"
		           f" ({s.get('outcome') or 'no result yet'})")
		if s.get("last_success") and s.get("last_success") != s.get("last_attempt"):
			click.echo(f"            last succeeded {s['last_success']}")

	click.echo("")
	click.echo("  Informational. Nothing in ZIRI PMS is gated on this.")
	click.echo("")
	sys.exit(0)


@click.command("ziri-telemetry")
@click.option("--consent", "agree", is_flag=True,
              help="Agree to send it. Prints the payload first.")
@click.option("--withdraw", is_flag=True, help="Stop sending it.")
@click.option("--send-now", "send_now", is_flag=True,
              help="Send one report now (needs a URL and consent).")
@pass_context
def ziri_telemetry(context, agree, withdraw, send_now):
	"""Show, agree to, or stop the optional telemetry report.

	With no options it prints exactly what WOULD be sent and whether anything
	is being sent, which is the only order that makes agreeing meaningful.
	Nothing is sent by default, on any site.
	"""
	site = get_site(context)
	try:
		frappe.init(site=site)
		frappe.connect()
	except Exception as e:
		click.echo(f"cannot open site {site}: {type(e).__name__}: {e}", err=True)
		sys.exit(2)

	try:
		from kamra import telemetry as T

		if withdraw:
			T.withdraw_consent()
			click.echo("")
			click.echo("  consent withdrawn. Nothing further will be sent.")
			click.echo("  The endpoint is left configured so changing your")
			click.echo("  mind back does not mean re-typing a URL.")
		elif agree:
			# Printed BEFORE the agreement is recorded, every time, even for
			# somebody who passed --consent without looking. The whole claim
			# of this feature is that what you agree to is what you read.
			click.echo("")
			click.echo("  This is the entire report. Read it before agreeing.")
			click.echo("")
			click.echo(frappe.as_json(T._payload()))
			click.echo("")
			if not click.confirm("  Send reports like this one?", default=False):
				click.echo("  nothing changed.")
				# SystemExit is not an Exception, so it passes the handler
				# below and the `finally` closes the site exactly once.
				sys.exit(0)
			result = T.give_consent()
			click.echo("")
			click.echo(f"  consent recorded by {result['consent']['by']}"
			           f" at {result['consent']['at']}")
			if not result.get("configured"):
				click.echo("  No endpoint is configured yet, so nothing will")
				click.echo("  be sent until somebody sets:")
				click.echo("    bench --site <site> set-config "
				           "kamra_telemetry_url \"https://...\"")
		elif send_now:
			out = T.send(force=True)
			click.echo("")
			click.echo(f"  outcome:  {out['outcome']}")
			if out["outcome"] == "not-enabled":
				click.echo("  Needs BOTH kamra_telemetry_url and a recorded")
				click.echo("  consent. Run this command with no options to")
				click.echo("  see which is missing.")
		else:
			state = T.preview()
			sent = T.last_sent()
			click.echo("")
			click.echo(f"  sending:  {'yes' if state['enabled'] else 'no'}")
			click.echo(f"  endpoint: "
			           f"{'configured' if state['configured'] else 'not set'}")
			consent = state["consent"]
			if consent.get("by"):
				click.echo(f"  consent:  {consent['by']} at {consent['at']}")
			else:
				click.echo("  consent:  nobody has agreed")
			if sent.get("last_attempt"):
				click.echo(f"  last try: {sent['last_attempt']}"
				           f" ({sent.get('outcome')})")
			click.echo("")
			click.echo("  What WOULD be sent, built by the same function that")
			click.echo("  sends it:")
			click.echo("")
			click.echo(frappe.as_json(state["payload"]))
			click.echo("")
			click.echo("  Every value above is an enum, a count or a version.")
			click.echo("  No guest, reservation, rate, revenue, staff name,")
			click.echo("  property name or site hostname can appear here -")
			click.echo("  there is no field for one. See kamra/telemetry.py.")
			if not state["enabled"]:
				click.echo("")
				click.echo("  To start sending it:")
				click.echo("    bench --site <site> set-config "
				           "kamra_telemetry_url \"https://...\"")
				click.echo("    bench --site <site> ziri-telemetry --consent")
	except Exception as e:
		click.echo(f"telemetry: {type(e).__name__}: {e}", err=True)
		sys.exit(2)
	finally:
		frappe.destroy()

	click.echo("")
	click.echo("  Optional. Nothing in ZIRI PMS depends on this.")
	click.echo("")
	sys.exit(0)


commands = [ziri_doctor, ziri_support_bundle, ziri_entitlement, ziri_telemetry]
