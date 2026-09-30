import { useCallback, useEffect, useState } from "react"
import { getLang, langDef, type Lang } from "./dir"
import ar from "../i18n/locales/ar.json"
import fr from "../i18n/locales/fr.json"

/** Locale dictionaries keyed by English source string. Missing keys fall back
 * to English so the app never blanks as coverage expands. */
const DICT: Record<string, Record<string, string>> = {
  en: {},
  fr: fr as Record<string, string>,
  ar: ar as Record<string, string>,
}

export type Vars = Record<string, string | number>

/** Placeholders that carry ENGLISH morphology rather than content. Call sites
 * compute them locally - `s: n === 1 ? "" : "s"`, `ies: n === 1 ? "y" : "ies"`,
 * `ord` for "st/nd/rd/th" - so the value handed in is only ever correct for a
 * language that pluralises by suffix. Dropped for languages that do not.
 *
 * STOPGAP, and worth naming as one. It stops the visible damage: Arabic showed
 * "3 ليلةs" and "الطابق 3rd" on screens including the guest booking page. It is
 * NOT plural support - Arabic has six plural categories and this expresses
 * none of them, it merely declines to append an English suffix. Real support
 * means per-category forms in the dictionaries driven by Intl.PluralRules,
 * which changes the dictionary format and every affected key. Until then a
 * translator writes the noun in whatever form reads best unmarked.
 *
 * `{ord}` is tracked separately because the two properties differ: French
 * pluralises with -s, so it keeps `{s}`, but writes ordinals 1er / 3e, so
 * "3rd etage" would be as wrong as "الطابق 3rd". */
const PLURAL_SUFFIXES = new Set(["s", "s2", "s3", "ies"])
const ORDINAL_SUFFIXES = new Set(["ord"])

/** Replace `{name}` placeholders in a template. Arabic (and others) can
 * reorder words by placing the same placeholders differently. */
function interpolate(template: string, vars: Vars | undefined, lang: Lang): string {
  if (!vars) return template
  const def = langDef(lang)
  return template.replace(/\{(\w+)\}/g, (_, k: string) => {
    if (!def.suffixPlural && PLURAL_SUFFIXES.has(k)) return ""
    if (!def.ordinalSuffix && ORDINAL_SUFFIXES.has(k)) return ""
    return vars[k] !== undefined && vars[k] !== null ? String(vars[k]) : `{${k}}`
  })
}

/** Translate an English string for the current language (falls back to it). */
export function t(s: string, vars?: Vars): string {
  const lang = getLang()
  const dict = DICT[lang] ?? {}
  return interpolate(dict[s] ?? s, vars, lang)
}

/** Translate for a specific language (e.g. offline export). */
export function tFor(lang: Lang, s: string, vars?: Vars): string {
  const dict = DICT[lang] ?? {}
  return interpolate(dict[s] ?? s, vars, lang)
}

/** Subscribe a component to the language: re-renders on change, returns a
 * bound translator. */
export function useT() {
  const [lang, setL] = useState<Lang>(getLang())
  useEffect(() => {
    const on = () => setL(getLang())
    window.addEventListener("kamra:lang", on)
    return () => window.removeEventListener("kamra:lang", on)
  }, [])
  const t = useCallback(
    (s: string, vars?: Vars) => {
      const dict = DICT[lang] ?? {}
      return interpolate(dict[s] ?? s, vars, lang)
    },
    [lang],
  )
  return { lang, t }
}
