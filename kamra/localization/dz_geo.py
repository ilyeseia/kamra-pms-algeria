"""Algerian administrative geography - wilayas and their communes.

The 58 wilayas, in the official numbering. Codes 1-48 are the historic set;
49-58 were created in 2019 from the southern wilayas they were previously
districts of, which is why the numbering jumps geographically at the end.

Each entry carries both names because the two scripts are not decoration
here: a fiche de police is filed in Arabic, an invoice and a booking
confirmation are usually French, and the same hotel writes both in a day.

WHAT IS AND IS NOT IN THIS FILE
The wilayas are complete and verifiable - 58 rows, numbered, and anyone from
the country can check them at a glance.

The communes are NOT complete. Algeria has roughly 1,541 of them, and a list
that size cannot be written from memory without inventing names. A commune is
not cosmetic: it goes on the guest registration card the hotel files with the
police, so a plausible-looking wrong name is worse than an empty field. So
COMMUNES below holds only what has been confirmed, `communes_for()` returns an
empty list for a wilaya that has none yet, and the UI must fall back to free
text rather than forcing a choice from a partial list.

Filling it in is a data task, not a code task: drop an authoritative source
into COMMUNES keyed by wilaya code and everything downstream starts working.
"""

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

# wilaya code -> ((name_fr, name_ar), ...)
# Deliberately empty until an authoritative source is loaded. See the module
# docstring: a guessed commune lands on a police document.
COMMUNES: dict[int, tuple[tuple[str, str], ...]] = {}


def wilayas(lang: str = "fr") -> list[dict]:
	"""The 58 wilayas, labelled in the caller's language."""
	key = 2 if lang == "ar" else 1
	return [{"code": w[0], "name": w[key], "name_fr": w[1], "name_ar": w[2]}
	        for w in WILAYAS]


def communes_for(code: int | str, lang: str = "fr") -> list[dict]:
	"""The communes of one wilaya - empty where the data is not loaded yet.

	An empty list is a real answer, not an error: the caller shows a free-text
	field instead of an empty dropdown nobody can satisfy."""
	try:
		code = int(code)
	except (TypeError, ValueError):
		return []
	key = 1 if lang == "ar" else 0
	return [{"name": c[key], "name_fr": c[0], "name_ar": c[1]}
	        for c in COMMUNES.get(code, ())]


def wilaya_by_name(name: str | None) -> dict | None:
	"""Resolve a wilaya however it was typed - either script, any case, with
	or without the code. Property.state is free text, so a stored value can be
	'16', 'Alger', 'alger' or 'الجزائر' and all four mean the same place."""
	if not name:
		return None
	needle = " ".join(str(name).split()).casefold()
	for code, fr, ar in WILAYAS:
		if needle in (str(code), f"{code:02d}", fr.casefold(), ar.casefold()):
			return {"code": code, "name_fr": fr, "name_ar": ar}
	return None


@frappe.whitelist()
def dz_geo(wilaya: str | None = None, lang: str = "fr") -> dict:
	"""Wilayas, and the communes of one of them when asked.

	`communes_loaded` lets the UI decide between a dropdown and a text box
	without guessing why the list came back empty."""
	return {
		"wilayas": wilayas(lang),
		"communes": communes_for(wilaya, lang) if wilaya else [],
		"communes_loaded": bool(COMMUNES),
	}
