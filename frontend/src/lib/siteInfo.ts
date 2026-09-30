import { call } from "./api"

/** Mirrors `kamra.public_api.site_info`. Every field but `demo_mode` is
 * optional because the endpoint grew after this type did: for a long while it
 * returned `demo_mode` alone, so the version line on the login screen was
 * rendered from a field nobody sent and never once appeared. `version` and
 * `source_url` are supplied now; `app`, `site`, `branch`, `commit` and
 * `frappe_version` are still declared here and still not returned by the
 * backend, so anything reading them is dead code until it is. */
export type SiteInfo = {
  demo_mode: boolean
  version?: string
  /** AGPL-3.0 §13 source offer - where the Corresponding Source of this
   * running build lives. Overridable per site via `kamra_source_url`. */
  source_url?: string
  app?: string
  site?: string
  branch?: string | null
  commit?: string | null
  frappe_version?: string
}

let cached: Promise<SiteInfo> | null = null

export function getSiteInfo(): Promise<SiteInfo> {
  if (!cached) {
    cached = call<SiteInfo>("kamra.public_api.site_info").catch(() => ({
      demo_mode: false,
    }))
  }
  return cached
}
