"""Algerian administrative geography - wilayas and their communes.

The 58 wilayas, in the official numbering. Codes 1-48 are the historic set;
49-58 were created in 2019 from the southern wilayas they were previously
districts of, which is why the numbering jumps geographically at the end.

Each entry carries both names because the two scripts are not decoration
here: a fiche de police is filed in Arabic, an invoice and a booking
confirmation are usually French, and the same hotel writes both in a day.

WHERE THE DATA COMES FROM
The 58 wilayas are written out below. The 1,541 communes are too many to write
from memory without inventing names, and a commune is not cosmetic - it goes on
the guest registration card the hotel files with the police, where a
plausible-looking wrong name is worse than a blank. So they load from
dz_communes.json, taken from the othmanus/algeria-cities open dataset of the
official division.

That dataset was checked rather than trusted: 1,541 records exactly, wilaya
codes 1-58 contiguous, no empty names, no duplicate commune within a wilaya,
all five spot-checks found (Bab El Oued and Hydra in Alger, Es Senia in Oran,
El Khroub in Constantine, Akbou in Bejaia), and - the useful one - its 58
wilaya names agree with the list below, which was written independently before
the dataset was fetched. Two sources agreeing on all 58 is the strongest check
available here.

They disagree on four spellings out of 116 name fields, all legitimate
transliteration variants in common use (El M'Ghair / El Meghaier, El Meniaa /
El Menia, عين الدفلى / عين الدفلة, عين تموشنت / عين تيموشنت). ALIASES below
accepts both forms so a stored value resolves whichever way it was typed.
"""

import json
import pathlib
from functools import lru_cache

import frappe

# (code, name_fr, name_ar)
WILAYAS: tuple[tuple[int, str, str], ...] = (
	(1, "Adrar", "أدرار"),
	(2, "Chlef", "الشلف"),
	(3, "Laghouat", "الأغواط"),
	(4, "Oum El Bouaghi", "أم البواقي"),
	(5, "Batna", "باتنة"),
	(6, "Béjaïa", "بجاية"),
	(7, "Biskra", "بسكرة"),
	(8, "Béchar", "بشار"),
	(9, "Blida", "البليدة"),
	(10, "Bouira", "البويرة"),
	(11, "Tamanrasset", "تمنراست"),
	(12, "Tébessa", "تبسة"),
	(13, "Tlemcen", "تلمسان"),
	(14, "Tiaret", "تيارت"),
	(15, "Tizi Ouzou", "تيزي وزو"),
	(16, "Alger", "الجزائر"),
	(17, "Djelfa", "الجلفة"),
	(18, "Jijel", "جيجل"),
	(19, "Sétif", "سطيف"),
	(20, "Saïda", "سعيدة"),
	(21, "Skikda", "سكيكدة"),
	(22, "Sidi Bel Abbès", "سيدي بلعباس"),
	(23, "Annaba", "عنابة"),
	(24, "Guelma", "قالمة"),
	(25, "Constantine", "قسنطينة"),
	(26, "Médéa", "المدية"),
	(27, "Mostaganem", "مستغانم"),
	(28, "M'Sila", "المسيلة"),
	(29, "Mascara", "معسكر"),
	(30, "Ouargla", "ورقلة"),
	(31, "Oran", "وهران"),
	(32, "El Bayadh", "البيض"),
	(33, "Illizi", "إليزي"),
	(34, "Bordj Bou Arréridj", "برج بوعريريج"),
	(35, "Boumerdès", "بومرداس"),
	(36, "El Tarf", "الطارف"),
	(37, "Tindouf", "تندوف"),
	(38, "Tissemsilt", "تيسمسيلت"),
	(39, "El Oued", "الوادي"),
	(40, "Khenchela", "خنشلة"),
	(41, "Souk Ahras", "سوق أهراس"),
	(42, "Tipaza", "تيبازة"),
	(43, "Mila", "ميلة"),
	(44, "Aïn Defla", "عين الدفلى"),
	(45, "Naâma", "النعامة"),
	(46, "Aïn Témouchent", "عين تموشنت"),
	(47, "Ghardaïa", "غرداية"),
	(48, "Relizane", "غليزان"),
	(49, "Timimoun", "تيميمون"),
	(50, "Bordj Badji Mokhtar", "برج باجي مختار"),
	(51, "Ouled Djellal", "أولاد جلال"),
	(52, "Béni Abbès", "بني عباس"),
	(53, "In Salah", "عين صالح"),
	(54, "In Guezzam", "عين قزام"),
	(55, "Touggourt", "تقرت"),
	(56, "Djanet", "جانت"),
	(57, "El M'Ghair", "المغير"),
	(58, "El Meniaa", "المنيعة"),
)

# Wilaya names this file spells one way and the dataset spells another. Both
# are in use on real documents, so both must resolve.
ALIASES = {
	"el meghaier": 57,
	"el menia": 58,
	"عين الدفلة": 44,
	"عين تيموشنت": 46,
}

_COMMUNES_FILE = pathlib.Path(__file__).parent / "dz_communes.json"


@lru_cache(maxsize=1)
def _communes() -> dict[int, list[list[str]]]:
	"""Loaded once per process. 150 KB of JSON is not worth re-reading, and
	not worth holding as a Python literal either - this keeps the module
	readable and lets the data be replaced without touching code."""
	try:
		raw = json.loads(_COMMUNES_FILE.read_text(encoding="utf-8"))
	except (OSError, ValueError):
		# A missing or corrupt data file must not take the front desk down:
		# the UI falls back to free text, which is what it did before the
		# data existed at all.
		frappe.log_error(title="dz_geo: commune data unavailable")
		return {}
	return {int(k): v for k, v in (raw.get("communes") or {}).items()}


def wilayas(lang: str = "fr") -> list[dict]:
	"""The 58 wilayas, labelled in the caller's language."""
	key = 2 if lang == "ar" else 1
	return [{"code": w[0], "name": w[key], "name_fr": w[1], "name_ar": w[2]}
	        for w in WILAYAS]


def communes_for(code: int | str, lang: str = "fr") -> list[dict]:
	"""The communes of one wilaya, with the daira each belongs to.

	An empty list is a real answer, not an error - an unknown wilaya, or a
	data file that failed to load. The caller shows a free-text field rather
	than an empty dropdown nobody can satisfy."""
	try:
		code = int(code)
	except (TypeError, ValueError):
		return []
	key = 1 if lang == "ar" else 0
	return [{"name": c[key], "name_fr": c[0], "name_ar": c[1],
	         "daira": c[3] if lang == "ar" else c[2]}
	        for c in _communes().get(code, ())]


def wilaya_by_name(name: str | None) -> dict | None:
	"""Resolve a wilaya however it was typed - either script, any case, with
	or without the code. Property.state is free text, so a stored value can be
	'16', 'Alger', 'alger' or 'الجزائر' and all four mean the same place."""
	if not name:
		return None
	needle = " ".join(str(name).split()).casefold()
	target = ALIASES.get(needle)
	for code, fr, ar in WILAYAS:
		if target == code or needle in (str(code), f"{code:02d}", fr.casefold(), ar.casefold()):
			return {"code": code, "name_fr": fr, "name_ar": ar}
	return None


@frappe.whitelist()
def dz_geo(wilaya: int | str | None = None, lang: str = "fr") -> dict:
	"""Wilayas, and the communes of one of them when asked.

	`communes_loaded` lets the UI decide between a dropdown and a text box
	without guessing why the list came back empty.

	`wilaya` is annotated int | str on purpose, and the width is load-bearing
	rather than sloppy. Frappe v16 validates a whitelisted function's
	annotations with pydantic BEFORE the body runs, so a narrower `str | None`
	rejected the integer a JSON caller naturally sends - 417 EXPECTATION
	FAILED, raised before communes_for ever got to normalise it. The defensive
	int() below was unreachable from HTTP. The annotation has to describe what
	the function really takes, not the one shape a Python test happened to
	pass."""
	return {
		"wilayas": wilayas(lang),
		"communes": communes_for(wilaya, lang) if wilaya else [],
		"communes_loaded": bool(_communes()),
	}
