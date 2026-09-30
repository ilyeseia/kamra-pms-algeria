/*  Currency and tax vocabulary, from the property's localization pack. Loaded
    once per session. The last resolved locale is kept in localStorage so
    screens render with the right symbol immediately on reload, before the
    network answers.

    The defaults below are what is on screen BEFORE the pack resolves - on
    first run, for the moment after every reload, and permanently in a private
    window where localStorage throws. They used to be Indian, so an Algerian
    front desk opened to rupees, GST, GSTIN, Aadhaar and UPI and then watched
    them change. They are Algerian now, because that is who this build is for.
    Nothing here is authoritative: property_locale() overwrites all of it from
    the country pack a moment later. */

import { useEffect, useState } from "react"
import { call, getCurrentProperty } from "./api"

interface Locale {
  currency_symbol: string
  locale: string
  currency: string
  tax_label: string
  tax_id_label: string
  tax_rates: number[]
  /** ID documents this country's desk records (pack ID_TYPES). */
  id_types: string[]
  /** Ways to pay the desk offers - always canonical Folio Payment modes. */
  payment_modes: string[]
  default_nationality: string
}

let cache: Locale = {
  // trailing space because fmtMoney below prefixes the symbol: "DA 1 500"
  currency_symbol: "DA ",
  locale: "fr-DZ",
  currency: "DZD",
  tax_label: "TVA",
  tax_id_label: "NIF",
  tax_rates: [9, 19],
  id_types: ["National ID", "Passport", "Driving License", "Residence Permit", "Other"],
  payment_modes: ["Cash", "Card", "Bank Transfer"],
  default_nationality: "Algerian",
}

const listeners = new Set<() => void>()

try {
  const saved = JSON.parse(localStorage.getItem("kamra_locale") || "")
  if (saved && saved.currency_symbol) cache = { ...cache, ...saved }
} catch {
  /* first run, or a private window - the defaults above hold until the pack
     resolves, which is why they are Algerian rather than Indian */
}

function remember() {
  listeners.forEach((fn) => fn())
  try {
    localStorage.setItem("kamra_locale", JSON.stringify(cache))
  } catch {
    /* private mode */
  }
}

export function loadLocale(): Promise<Locale> {
  return call<Locale>("kamra.api.property_locale", {
    property: getCurrentProperty(),
  })
    .then((l) => {
      cache = { ...cache, ...l }
      remember()
      return cache
    })
    .catch(() => cache)
}

/** Public pages carry `ui_locale` in their payload - adopt it directly. */
export function adoptUiLocale(ui?: { currency_symbol?: string; locale?: string } | null) {
  if (!ui) return
  cache = {
    ...cache,
    // "" is a valid symbol (generic pack shows bare numbers)
    currency_symbol: ui.currency_symbol ?? cache.currency_symbol,
    locale: ui.locale || cache.locale,
  }
  remember()
}

export const locale = () => cache
/** The property's currency symbol, e.g. "DA " or "₹". */
export const cur = () => cache.currency_symbol
/** The number-formatting locale, e.g. "fr-DZ" or "en-IN" (lakhs). */
export const moneyLocale = () => cache.locale
export const fmtMoney = (n: unknown) =>
  cache.currency_symbol +
  Number(n ?? 0).toLocaleString(cache.locale, { maximumFractionDigits: 2 })
export const taxRates = () => cache.tax_rates
export const taxLabel = () => cache.tax_label

/** The property's locale, re-rendering when the country pack resolves. */
export function useLocale(): Locale {
  const [l, setL] = useState(cache)
  useEffect(() => {
    const fn = () => setL(cache)
    listeners.add(fn)
    loadLocale()
    return () => {
      listeners.delete(fn)
    }
  }, [])
  return l
}
