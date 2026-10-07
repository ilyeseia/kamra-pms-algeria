# Copyright (c) 2026 Ilyes Keskas (Algeria)
# Part of the ZIRI PMS Algeria distribution of Kamra PMS.
# SPDX-License-Identifier: AGPL-3.0-or-later
# See NOTICE for the upstream authorship this builds on.
"""The Installation ID: a stable, non-personal name for one deployment.

WHY IT IS GENERATED, NOT DERIVED

The obvious design is to hash something the site already has - the database
name, the site name, the encryption key - so the identifier needs no storage
and survives a wipe. Every version of that is wrong here:

  - A hash of the site name leaks the hotel's domain to anyone who can guess
    it, which is the whole point of the name being non-personal.
  - A hash of the encryption key makes a support identifier a function of the
    secret that protects every stored credential. Nobody should ever be in a
    position where publishing an ID weakens a key, however many rounds sit in
    between.
  - A hash of the database name is stable but meaningless to the person
    reading it, and it changes if the site is ever restored under a new name -
    which is exactly the moment support most needs continuity.

So it is random, generated once, and stored. It survives a restore because it
rides in the database, which is what a restore brings back.

WHAT IT IS FOR, AND WHAT IT MUST NEVER BECOME

It names a deployment in a support conversation, a bundle manifest, an update
check and - when one exists - a licence. It is designed to be quotable in a
ticket, read aloud on a phone call, and typed back without error. That is why
it is short, upper-case, hyphenated and drawn from an alphabet with no 0/O or
1/I/L to confuse.

It is NOT a secret and must never be treated as one. Anyone who can open the
site can read it. It authenticates nothing. A licence that trusts an
Installation ID alone is a licence that anyone can claim.
"""

from __future__ import annotations

import re
import secrets

import frappe

# No 0/O, 1/I/L, 5/S, 8/B. A support engineer reading this back over a bad
# phone line should not have to ask "zero or letter O".
_ALPHABET = "ACDEFGHJKMNPQRTUVWXY2346789"
_BODY_LEN = 6
_KEY = "kamra_installation_id"
_PATTERN = re.compile(r"^[A-Z]{2,4}-[A-Z]{3,10}-[%s]{%d}$" % (_ALPHABET, _BODY_LEN))


def _region_token() -> str:
	"""A coarse, non-identifying region hint, for sorting a support inbox.

	The country of the property, not its name, city or address. On a
	distribution that ships one country this is always DZA, which makes it
	nearly useless here - it is carried because a multi-country build would
	want it and because retro-fitting a segment into an identifier people have
	already written down is worse than carrying a constant.
	"""
	try:
		country = frappe.db.get_value("Property", {}, "country")
	except Exception:
		country = None
	return {"Algeria": "DZA"}.get(country or "", "XXX")


def _generate() -> str:
	body = "".join(secrets.choice(_ALPHABET) for _ in range(_BODY_LEN))
	return f"{_region_token()}-ZIRI-{body}"


def installation_id(create: bool = True) -> str | None:
	"""The ID for this site, creating it on first call.

	Stored in site config rather than a DocType: it must be readable before
	any app logic runs, by a support script that cannot assume the database
	schema is intact, and during a restore when DocTypes may not yet exist.
	"""
	try:
		existing = frappe.conf.get(_KEY)
	except Exception:
		return None
	if existing and _PATTERN.match(str(existing)):
		return str(existing)
	if not create:
		return None

	new = _generate()
	try:
		from frappe.installer import update_site_config

		update_site_config(_KEY, new, validate=False)
		# update_site_config rewrites the file; frappe.conf in this process is
		# a snapshot, so set it too or the value read back in this same request
		# is the old one.
		frappe.conf[_KEY] = new
	except Exception:
		# A read-only config, a permissions problem, a site being restored: the
		# caller gets nothing rather than an exception, because an installation
		# that cannot name itself must still serve its hotel.
		frappe.log_error(title="installation_id: could not persist")
		return None
	return new


@frappe.whitelist()
def get_installation_id() -> dict:
	"""Readable by any logged-in user. It is not a secret - see the module
	docstring - and withholding it would only make a support call harder."""
	iid = installation_id()
	return {
		"installation_id": iid,
		"is_secret": False,
		"note": ("Quote this in a support ticket. It identifies the deployment "
		         "and authenticates nothing."),
	}
