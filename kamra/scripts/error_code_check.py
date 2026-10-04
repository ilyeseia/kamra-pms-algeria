"""Keep the error-code taxonomy and the code that emits it from drifting apart.

WHY THIS EXISTS

docs/product/ERROR_CODES.md spent its whole life carrying the line "Status:
specification. Nothing in this repository emits these codes." It was a careful,
323-line document describing a vocabulary that no running system spoke, and
nothing anywhere would have noticed if that stayed true for another year - or
if, once codes started being emitted, someone typed APP-05 for APP-005, or
allocated a code in the source that the catalogue never heard of.

A taxonomy's entire value is that one failure has one identifier. The moment
the source and the catalogue disagree, a technician searching for the code on
their screen finds nothing, which is worse than having had no code at all.

So this is the guard, and it runs without a site, a database or Frappe:

  1. Every code emitted by the source is allocated in the catalogue.
  2. Every code in the catalogue is well-formed under the scheme in Section 1.
  3. The catalogue does not still claim that nothing emits codes.

WHAT IT DELIBERATELY DOES NOT CHECK

That every allocated code is emitted. Most are not, and should not be: the
catalogue allocates codes with basis `doc`, `designed` and `live` for real
conditions that have no machine signal, and saying so in writing is the honest
position. Requiring emission would force either fake signals or the deletion of
true entries.
"""

from __future__ import annotations

import pathlib
import re
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_CATALOGUE = _ROOT / "docs" / "product" / "ERROR_CODES.md"
_SOURCE = _ROOT / "kamra"

# The scheme: <CATEGORY>-<NNN>, category from the closed list in Section 2.
_CATEGORIES = (
	"APP", "DB", "NETWORK", "AUTH", "SECURITY", "LICENSE", "BACKUP",
	"UPDATE", "MIGRATION", "DOCKER", "STORAGE", "CONFIGURATION", "INTEGRATION",
)
_CODE = re.compile(r"\b(" + "|".join(_CATEGORIES) + r")-(\d{3})\b")

# Where a code is allocated: the leading cell of a Section 3 table row.
_ALLOCATION = re.compile(r"^\|\s*(" + "|".join(_CATEGORIES) + r")-(\d{3})\s*\|")

# How a code is emitted: as a string literal holding exactly a code, or as a
# bracketed prefix inside one. The first version of this matched the syntax
# around the literal instead - `code="X"`, a dict value, a log title - and
# missed `code=None if status == "passed" else "APP-004"`, because the quote no
# longer followed the `=`. It reported 21 of 22 and looked like it was working.
#
# Matching the literal itself has no such blind spot: any expression that puts
# a code in the source puts it in quotes. It also cannot match prose, because
# a code mentioned in a comment or a docstring is not a quoted literal of its
# own - and that distinction matters, or every design note becomes a claim.
_EMIT = (
	re.compile(r"""["']([A-Z]+-\d{3})["']"""),
	re.compile(r"""["']\s*\[([A-Z]+-\d{3})\]"""),
)


def _allocated() -> set[str]:
	text = _CATALOGUE.read_text(encoding="utf-8")
	out = set()
	for line in text.splitlines():
		m = _ALLOCATION.match(line.strip())
		if m:
			out.add(f"{m.group(1)}-{m.group(2)}")
	return out


def _emitted() -> dict[str, list[str]]:
	"""code -> the files that emit it."""
	out: dict[str, list[str]] = {}
	for path in sorted(_SOURCE.rglob("*.py")):
		if "/scripts/" in path.as_posix() or "/tests/" in path.as_posix():
			continue
		try:
			text = path.read_text(encoding="utf-8")
		except (OSError, UnicodeDecodeError):
			continue
		for pattern in _EMIT:
			for code in pattern.findall(text):
				out.setdefault(code, [])
				rel = path.relative_to(_ROOT).as_posix()
				if rel not in out[code]:
					out[code].append(rel)
	return out


def main() -> int:
	if not _CATALOGUE.exists():
		print(f"FAIL  catalogue missing: {_CATALOGUE}")
		return 2

	allocated = _allocated()
	emitted = _emitted()
	problems: list[str] = []

	if not allocated:
		problems.append("no codes parsed from the catalogue - has its table "
		                "format changed? This check would then pass vacuously.")

	# 1. Emitted but not allocated: the failure that makes a code useless.
	for code, files in sorted(emitted.items()):
		if code not in allocated:
			problems.append(f"{code} is emitted by {', '.join(files)} but is not "
			                f"allocated in ERROR_CODES.md")

	# 2. Malformed allocations. The regex only matches well-formed codes, so
	#    this catches the near-miss that slipped past it in a table cell.
	near = re.compile(r"^\|\s*([A-Z]{2,13}-\d{1,4})\s*\|")
	for line in _CATALOGUE.read_text(encoding="utf-8").splitlines():
		m = near.match(line.strip())
		if m and m.group(1) not in allocated:
			problems.append(f"{m.group(1)} in the catalogue does not fit "
			                "<CATEGORY>-<NNN> with a category from Section 2")

	# 3. The stale claim. Checked as a substring of the whole document because
	#    it appeared in the status line and again in the caveats section.
	text = _CATALOGUE.read_text(encoding="utf-8")
	if emitted and "Nothing in this repository emits these codes" in text:
		problems.append("the catalogue still says nothing emits these codes, "
		                f"but {len(emitted)} are emitted")

	if problems:
		print(f"FAIL  {len(problems)} problem(s)")
		for p in problems:
			print(f"  - {p}")
		return 1

	print(f"OK ({len(emitted)} codes emitted, {len(allocated)} allocated)")
	return 0


if __name__ == "__main__":
	sys.exit(main())
