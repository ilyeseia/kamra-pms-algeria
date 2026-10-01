// Resolve a static asset shipped in frontend/public against the build base.
// Dev: BASE_URL is "/", so asset("ziri-mark.png") -> "/ziri-mark.png".
// Prod: BASE_URL is "/assets/kamra/frontend/", so the same call resolves to
// "/assets/kamra/frontend/ziri-mark.png" (where Frappe serves it).
export const asset = (path: string) =>
  import.meta.env.BASE_URL + path.replace(/^\//, "")
