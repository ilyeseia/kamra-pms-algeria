"""Which distribution this is, and where it gets its updates.

Two version numbers exist here and they are not interchangeable
(docs/algeria/VERSIONING.md):

  Kamra core     2.6.x   owned upstream, lives in kamra/__init__.py
  ZIRI PMS       1.0.x   owned by this repository, lives here and in git tags

Until this module existed the distribution version lived only in git tags and
prose, so nothing running could tell you which distribution it was. That had a
concrete consequence: health.py read the CORE version and compared it against
UPSTREAM's releases, so a ZIRI install was told "2.6.5 installed, 2.6.6
available" and pointed at upstream's release page. Taking that advice on the
Linux path means `install.sh update`, which defaults to upstream's repository
and rebuilds the site from it - discarding the Algeria pack, the wilayas and
communes, the DZD work and every patch this fork carries. An update offer that
silently uninstalls the product is the worst shape a version check can take.

The repository can be overridden per site so that a differently-branded build,
or an internal mirror for a hotel with no route to github.com, does not need a
code change:

    bench --site <site> set-config kamra_update_repo "owner/repo"
    bench --site <site> set-config kamra_update_tag_prefix "ziri-v"

Set `kamra_update_repo` to an empty string to switch update checking off
entirely. health.py then reports the installed versions and says checking is
disabled, which is honest; it does not quietly pass.
"""

from __future__ import annotations

import frappe

DISTRIBUTION = "ZIRI PMS"

# Keep in step with the newest `ziri-v*` tag. VERSIONING.md explains why the
# suffix is here: the documents describe 1.0.0, the tag records which candidate
# is actually checked out, and the suffix is dropped once a trial install has
# proven the migrations against a real database.
DISTRIBUTION_VERSION = "1.0.0-rc.2"

# Releases of THIS distribution, not upstream's. Tags carry a prefix so they
# cannot collide with upstream's `v2.6.5` style in the same repository.
DEFAULT_UPDATE_REPO = "ilyeseia/kamra-pms-algeria"
DEFAULT_TAG_PREFIX = "ziri-v"


def update_repo() -> str:
	"""`owner/repo` to check for updates; empty string disables checking."""
	v = frappe.conf.get("kamra_update_repo")
	return (DEFAULT_UPDATE_REPO if v is None else str(v)).strip()


def tag_prefix() -> str:
	v = frappe.conf.get("kamra_update_tag_prefix")
	return (DEFAULT_TAG_PREFIX if v is None else str(v)).strip()
