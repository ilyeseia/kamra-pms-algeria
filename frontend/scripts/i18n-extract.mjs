#!/usr/bin/env node
/**
 * Extract English UI strings into catalog.csv.
 *
 * Sources of strings:
 *   1. Direct calls  — t("literal") / translate("literal"), and the
 *      t(expr || "literal") fallback form.
 *   2. Spec tables   — string literals assigned to `label:`, `hint:` and
 *      `placeholder:` inside object literals, plus the string members of
 *      `options:` arrays. These reach t() indirectly via t(spec.label),
 *      t(spec.hint), t(o) and friends, so a literal-only scan misses them
 *      and then reports every one of them as a dead key.
 *
 * Every locale in src/i18n/locales/*.json gets its own column, named after
 * the locale code, so adding a locale needs no edit to this script.
 *
 * Usage: node scripts/i18n-extract.mjs
 */
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.join(__dirname, "..")
const src = path.join(root, "src")
const outCsv = path.join(root, "src/i18n/catalog.csv")
const localesDir = path.join(root, "src/i18n/locales")

/**
 * Structural exclusions only. This deliberately names no product file:
 * a per-screen denylist rots silently the moment that screen gets its first
 * t() call (it hid the whole guest-facing surface — PublicBooking,
 * PublicListing, QrMenu — for exactly that reason), whereas these rules
 * describe categories of file that can never hold shippable UI copy.
 */
const SKIP_DIRS = new Set([
  "node_modules",
  "dist",
  "build",
  "coverage",
  "__tests__",
  "__mocks__",
  "__snapshots__",
])
const isSourceFile = (name) =>
  /\.(tsx|ts)$/.test(name) &&
  !name.endsWith(".d.ts") &&
  !/\.(test|spec|stories)\.tsx?$/.test(name)

function walk(dir, files = []) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name)
    const st = fs.statSync(p)
    if (st.isDirectory()) {
      if (SKIP_DIRS.has(name) || name.startsWith(".")) continue
      walk(p, files)
    } else if (isSourceFile(name)) files.push(p)
  }
  return files
}

function csvEscape(s) {
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

function placeholders(s) {
  return [...new Set([...s.matchAll(/\{(\w+)\}/g)].map((x) => x[1]))].join(" ")
}

function unescapeLiteral(s) {
  return s.replace(/\\n/g, "\n").replace(/\\'/g, "'").replace(/\\"/g, '"')
}

// ---------------------------------------------------------------- locales --
const locales = (
  fs.existsSync(localesDir)
    ? fs
        .readdirSync(localesDir)
        .filter((n) => n.endsWith(".json"))
        .map((n) => n.slice(0, -5))
    : []
).sort((a, b) => a.localeCompare(b))

const dicts = new Map()
for (const code of locales) {
  let parsed = {}
  try {
    parsed = JSON.parse(fs.readFileSync(path.join(localesDir, `${code}.json`), "utf8"))
  } catch (err) {
    console.error(`! could not read locales/${code}.json — ${err.message}`)
  }
  const dict = new Map()
  for (const [k, v] of Object.entries(parsed || {})) {
    if (typeof v === "string" && v.trim()) dict.set(k, v)
  }
  dicts.set(code, dict)
}

// ------------------------------------------------------------- extraction --
const keys = new Map()
const origins = new Map() // key -> Set<"direct"|"spec">

function add(key, source, origin) {
  if (!key || !/[A-Za-z]/.test(key)) return
  if (key.includes("${")) return
  if (!keys.has(key)) {
    keys.set(key, new Set())
    origins.set(key, new Set())
  }
  keys.get(key).add(path.relative(src, source))
  origins.get(key).add(origin)
}

// t("x") / translate('x') / t(spec.hint || "x")
const tCall =
  /\b(?:t|translate)\(\s*(?:[A-Za-z_$][\w$.?[\]]*\s*(?:\|\||\?\?)\s*)?(["'`])((?:\\.|(?!\1)[^\\])*)\1/g

// label: "x" / hint: 'x' / placeholder: "x"  (quoted or bare property name)
const specField =
  /(?:^|[\s,{(])["']?(?:label|hint|placeholder)["']?\s*:\s*(["'])((?:\\.|(?!\1)[^\\])*)\1/g

// options: [ "a", "b" ]  — flat array literal, string members only
const optionsArray = /\boptions\s*:\s*\[([^\]]*)\]/g
// options: IDENT  — resolved against a same-file `const IDENT = [...]`
const optionsIdent = /\boptions\s*:\s*([A-Za-z_$][\w$]*)/g
const stringLiteral = /(["'])((?:\\.|(?!\1)[^\\])*)\1/g

/** Find `const NAME = [ ...string literals... ]` in the same file. */
function constArrayLiterals(text, name) {
  const decl = new RegExp(`\\bconst\\s+${name}\\s*(?::[^=]*)?=\\s*\\[([^\\]]*)\\]`)
  const m = decl.exec(text)
  if (!m) return []
  return [...m[1].matchAll(stringLiteral)].map((x) => unescapeLiteral(x[2]))
}

const files = walk(src)
for (const file of files) {
  const text = fs.readFileSync(file, "utf8")

  for (const m of text.matchAll(tCall)) add(unescapeLiteral(m[2]), file, "direct")
  for (const m of text.matchAll(specField)) add(unescapeLiteral(m[2]), file, "spec")

  for (const m of text.matchAll(optionsArray))
    for (const s of m[1].matchAll(stringLiteral))
      add(unescapeLiteral(s[2]), file, "spec")

  for (const m of text.matchAll(optionsIdent))
    for (const s of constArrayLiterals(text, m[1])) add(s, file, "spec")
}

// ----------------------------------------------------------------- output --
/**
 * status reflects every locale:
 *   translated         — present in all locales
 *   needs_translation  — present in none (the old script's wording, kept)
 *   missing:<codes>    — space separated locale codes still to do
 * Space separated rather than comma separated so the field never needs
 * quoting and stays greppable: `grep 'missing:.*fr' catalog.csv`.
 */
function statusFor(key) {
  const missing = locales.filter((c) => !dicts.get(c).has(key))
  if (!locales.length) return "no_locales"
  if (!missing.length) return "translated"
  if (missing.length === locales.length) return "needs_translation"
  return `missing:${missing.join(" ")}`
}

const rows = [...keys.entries()].sort((a, b) => a[0].localeCompare(b[0]))
const lines = [["key", "english", ...locales, "sources", "placeholders", "status"].join(",")]
for (const [key, sources] of rows) {
  lines.push(
    [
      csvEscape(key),
      csvEscape(key),
      ...locales.map((c) => csvEscape(dicts.get(c).get(key) ?? "")),
      csvEscape([...sources].sort().join("; ")),
      csvEscape(placeholders(key)),
      statusFor(key),
    ].join(","),
  )
}

fs.writeFileSync(outCsv, "﻿" + lines.join("\n") + "\n", "utf8")

// ---------------------------------------------------------------- summary --
const total = rows.length
const pct = (n) => (total ? ((n / total) * 100).toFixed(1) : "0.0") + "%"
const specOnly = rows.filter(
  ([k]) => origins.get(k).has("spec") && !origins.get(k).has("direct"),
).length
const fullyTranslated = rows.filter(([k]) => statusFor(k) === "translated").length

console.log(`Wrote ${total} keys → ${path.relative(root, outCsv)}`)
console.log(
  `  scanned ${files.length} source files · ${total - specOnly} keys from t() calls · ${specOnly} from spec tables`,
)
console.log(`  locales: ${locales.length ? locales.join(", ") : "(none found)"}`)
for (const code of locales) {
  const dict = dicts.get(code)
  const have = rows.filter(([k]) => dict.has(k)).length
  const dead = [...dict.keys()].filter((k) => !keys.has(k)).length
  console.log(
    `    ${code.padEnd(4)} ${String(have).padStart(5)}/${total} translated (${pct(have).padStart(6)})` +
      `  ${String(total - have).padStart(4)} missing  ${String(dead).padStart(4)} unused in ${code}.json`,
  )
}
console.log(`  fully translated in every locale: ${fullyTranslated}/${total} (${pct(fullyTranslated)})`)
if (locales.length) {
  console.log(
    `  columns are named by locale code — import with: node scripts/i18n-import.mjs --lang ${locales[0]} --column ${locales[0]}`,
  )
}
