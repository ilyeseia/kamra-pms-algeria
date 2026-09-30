# Versioning — the Algeria distribution

Two version numbers exist here and they mean different things. Conflating them
is how a support call becomes unanswerable, so this file fixes what each one
is for.

| | Number | Owned by | Where it lives |
| --- | --- | --- | --- |
| Kamra core | **2.6.5** | upstream Kamra PMS | `kamra/__init__.py`, `.release-please-manifest.json` |
| Algeria distribution | **1.0.0** | this repository | git tag `algeria-v1.0.0`, `docs/algeria/` |

## Why the core version is not touched

`kamra/__init__.py` carries this line:

```python
__version__ = "2.6.5"  # x-release-please-version
```

That marker is machinery, not decoration. `release-please-config.json` lists
`kamra/__init__.py` under `extra-files` with `"versioning": "always-bump-patch"`,
so an automated release bumps that string and `.release-please-manifest.json`
together, generates `CHANGELOG.md`, and opens a draft release PR.

Writing `1.0.0` into that line would therefore do three bad things at once: it
would break the upstream release automation, it would misreport which Kamra
core the code actually is, and it would make a future `git fetch upstream`
conflict on a line that exists purely for a robot to edit.

**So the Algeria distribution is versioned alongside the core, not instead of
it.** This is ordinary practice for a downstream distribution — the same way a
Linux distribution has its own release number while the kernel keeps its.

## What "Algeria Distribution 1.0.0" covers

1.0.0 is the first version of the Algerian localization layer on top of Kamra
core 2.6.5:

- the Algeria country pack (`kamra/localization/algeria.py`) with DZD, TVA/NIF,
  `Africa/Algiers`, ANPDP, Algerian ID types and Algerian payment modes
- French as a third UI language, and Arabic brought up to full coverage of the
  extracted catalog
- the guest-facing screens localised and RTL-corrected
- the fixed per-person-per-night *taxe de séjour* basis (`v36`)
- Property fields for RC / NIS / AI (`v37`)
- `Dinars` / `Centimes` in amounts-in-words
- the Windows 10 installer (`deploy/windows/Install-Kamra.ps1`)

## Tagging

Distribution releases are tagged with an `algeria-v` prefix so they cannot
collide with upstream's `v2.6.5`-style tags in the same repository:

```bash
git tag -a algeria-v1.0.0 -m "Algeria distribution 1.0.0 on Kamra core 2.6.5"
git push origin algeria-v1.0.0
```

A tag is a claim that the thing works. Do not tag `1.0.0` until at least one
`bench migrate` has run against a real database — at time of writing, `v36`
and `v37` have never executed against one, so the honest state is
**1.0.0-rc**, not `1.0.0`. See `IMPLEMENTATION_STATUS.md`.

## How the two numbers move

- **Core changes** (a fetch from `upstream`): the core number moves, the
  distribution number gets a patch bump if the merge required Algeria-side
  work. Record the upstream commit in `IMPLEMENTATION_STATUS.md`.
- **Algeria-only changes**: only the distribution number moves. Patch for
  fixes and translations, minor for new localization capability, major for a
  change that needs operator action on upgrade (a migration that alters money,
  or a changed default).
- **Never** bump the core number by hand.

## Where the numbers are shown

`deploy/windows/Install-Kamra.ps1` prints both on every run:

```
Kamra PMS - Algeria Distribution 1.0.0
on Kamra core 2.6.5 - AGPL-3.0
```

That pairing is what a support request needs. "Kamra 2.6.5" alone does not say
whether the Algeria pack is present, and "Algeria 1.0.0" alone does not say
which core it sits on.

**Known gap:** the version string in the installer is currently hard-coded, so
it can drift from this file. Reading it from a single source — a constant in
the repository that both the installer and an About screen consume — is the
right fix and is not done yet.
