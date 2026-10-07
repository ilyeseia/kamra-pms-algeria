// The SPA is served at /ziri in production and at / by the Vite dev server.
//
// This is the ROUTE, which moved from /kamra when the public path was renamed
// to match the product. It is not the app name: the bundle still loads from
// /assets/kamra/frontend/ and every call still goes to /api/method/kamra.*,
// because those are named after the installed Frappe app and the database
// keys on it. Changing this constant alone is enough for the router; the
// server side is kamra/hooks.py and kamra/www/ziri.py.
export const ROUTER_BASENAME = import.meta.env.PROD ? "/ziri" : "/"

// Prefix an in-app path with the basename for a full-page navigation
// (window.location), which the router's own navigate() would otherwise add.
export function toFullPath(path: string): string {
  const base = ROUTER_BASENAME === "/" ? "" : ROUTER_BASENAME
  return base + (path.startsWith("/") ? path : "/" + path)
}
