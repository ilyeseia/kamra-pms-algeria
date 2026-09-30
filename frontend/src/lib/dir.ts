/** Interface direction / language. Stored per device (like the theme) and
 * applied to the document so the whole UI flips together. Direction comes
 * from the language registry (not a hard-coded `=== "ar"`), so Urdu/Hebrew
 * can join later without touching every call site. */

export interface LangDef {
  code: string
  /** Native name shown in the language picker, e.g. "العربية". */
  nativeLabel: string
  /** English label for the picker, e.g. "Arabic". */
  englishLabel: string
  dir: "ltr" | "rtl"
  /** Does this language form a plural by suffixing the noun? English and
   * French do ("3 nights", "3 nuits"), so the `{s}`-family placeholders that
   * callers pass ("" or "s") land correctly. Arabic does not - suffixing "s"
   * onto ليلة produces "3 ليلةs", which is what a guest was actually seeing.
   * i18n.ts drops those placeholders where this is false. See its comment for
   * why this is a stopgap and not real plural support. */
  suffixPlural: boolean
  /** Does this language write ordinals as an English-style suffix on the
   * numeral - 1st, 2nd, 3rd? Only English does. French writes 1er / 3e and
   * Arabic does not suffix at all, so "3rd étage" would be as wrong as
   * "الطابق 3rd". Separate from suffixPlural because French pluralises with
   * -s but does NOT take English ordinals. */
  ordinalSuffix: boolean
}

/** Supported UI languages. Add a row + a locales/<code>.json to ship another. */
export const LANGS: LangDef[] = [
  { code: "en", nativeLabel: "English", englishLabel: "English", dir: "ltr",
    suffixPlural: true, ordinalSuffix: true },
  { code: "fr", nativeLabel: "Français", englishLabel: "French", dir: "ltr",
    suffixPlural: true, ordinalSuffix: false },
  { code: "ar", nativeLabel: "العربية", englishLabel: "Arabic", dir: "rtl",
    suffixPlural: false, ordinalSuffix: false },
]

export type Lang = string

const KEY = "kamra-lang"
const codes = new Set(LANGS.map((l) => l.code))

export function langDef(code: string): LangDef {
  return LANGS.find((l) => l.code === code) ?? LANGS[0]
}

export const getLang = (): Lang => {
  const raw = localStorage.getItem(KEY) || "en"
  return codes.has(raw) ? raw : "en"
}

export function applyLang(l: Lang) {
  const def = langDef(l)
  const el = document.documentElement
  el.setAttribute("lang", def.code)
  el.setAttribute("dir", def.dir)
}

export function setLang(l: Lang) {
  const code = codes.has(l) ? l : "en"
  localStorage.setItem(KEY, code)
  applyLang(code)
  // let listeners (React trees) re-render with the new direction/strings
  window.dispatchEvent(new Event("kamra:lang"))
}

/** Call once at boot. */
export function initLang() {
  applyLang(getLang())
}
