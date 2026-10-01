import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import "./index.css"
import App from "./App"
import { initTheme } from "./lib/theme"
import { initLang } from "./lib/dir"
import { asset } from "./lib/asset"
import { AuthProvider } from "./lib/auth"
import { CashierAuthProvider } from "./lib/cashierAuth"
import { ROUTER_BASENAME } from "./lib/routing"

initTheme()
initLang()

// Favicons and the web manifest, base-aware (see index.html note).
function setLink(rel: string, href: string, type?: string) {
  const link = document.createElement("link")
  link.rel = rel
  link.href = asset(href)
  if (type) link.type = type
  document.head.appendChild(link)
}
// The ZIRI mark, not the full lockup: at 32px the wordmark under the arch is
// an illegible smudge. There is no SVG of the logo, only the supplied PNG, so
// these are PNG at several sizes rather than one scalable icon.
setLink("icon", "ziri-icon-512.png", "image/png")
setLink("icon", "favicon-32.png", "image/png")
// iOS ignores alpha and composites onto black, which would bury a dark-green
// logo - this one is flattened onto the brand's warm background instead.
setLink("apple-touch-icon", "apple-touch-180.png")
setLink("manifest", "manifest.webmanifest")

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter basename={ROUTER_BASENAME}>
      <AuthProvider>
        <CashierAuthProvider>
          <App />
        </CashierAuthProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
