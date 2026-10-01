import { defineConfig } from "vitepress"

export default defineConfig({
  title: "ZIRI PMS Docs",
  description:
    "ZIRI PMS - Smart Hospitality Management. Install, self-host, connect your AI over MCP, and run your property.",
  base: "/docs/",
  cleanUrls: true,
  // `head` entries are emitted as raw HTML, so `base` is NOT applied to them:
  // these hrefs carry the "/docs/" prefix explicitly.
  head: [
    ["link", { rel: "icon", type: "image/png", href: "/docs/ziri-mark.png" }],
    ["link", { rel: "icon", type: "image/png", sizes: "32x32", href: "/docs/ziri-icon-32.png" }],
    ["link", { rel: "apple-touch-icon", sizes: "180x180", href: "/docs/ziri-icon-180.png" }],
    ["link", { rel: "icon", type: "image/png", sizes: "192x192", href: "/docs/ziri-icon-192.png" }],
    ["link", { rel: "icon", type: "image/png", sizes: "512x512", href: "/docs/ziri-icon-512.png" }],
  ],
  themeConfig: {
    // themeConfig.logo is passed through the theme's withBase(), so it must
    // stay "/"-relative (no "/docs/" prefix) or it would resolve to /docs/docs/.
    logo: { src: "/ziri-mark.png", width: 28, height: 28, alt: "ZIRI PMS" },
    siteTitle: "ZIRI PMS",
    nav: [
      { text: "GitHub", link: "https://github.com/ilyeseia/kamra-pms-algeria" },
    ],
    search: { provider: "local" },
    socialLinks: [
      { icon: "github", link: "https://github.com/ilyeseia/kamra-pms-algeria" },
    ],
    footer: {
      message:
        "Open source (AGPL-3.0) · based on Kamra PMS · every feature included, always.",
      copyright: "ZIRI PMS · Smart Hospitality Management",
    },
    sidebar: [
      {
        text: "Getting started",
        items: [
          { text: "Introduction", link: "/" },
          { text: "Quickstart (Docker)", link: "/quickstart" },
          { text: "Demo & sample data", link: "/demo" },
          { text: "Go-live checklist", link: "/go-live" },
          { text: "FAQ", link: "/faq" },
        ],
      },
      {
        text: "Self-hosting",
        items: [
          { text: "Overview & requirements", link: "/self-hosting/" },
          { text: "Hostinger", link: "/self-hosting/hostinger" },
          { text: "DigitalOcean", link: "/self-hosting/digitalocean" },
          { text: "Linode (Akamai)", link: "/self-hosting/linode" },
          { text: "AWS", link: "/self-hosting/aws" },
          { text: "AWS / Azure / GCP marketplaces", link: "/self-hosting/marketplace/hyperscalers" },
          { text: "Install with bench", link: "/self-hosting/bench" },
          { text: "Frappe Cloud marketplace", link: "/self-hosting/frappe-cloud" },
          { text: "ERPNext & Frappe HR", link: "/self-hosting/erpnext-hr" },
          { text: "Email (SMTP) setup", link: "/self-hosting/email" },
        ],
      },
      {
        text: "Using ZIRI",
        items: [
          { text: "Features tour", link: "/features" },
          { text: "Country setup & ZATCA", link: "/country-setup" },
          { text: "WhatsApp on your number", link: "/whatsapp" },
          { text: "Channel manager (OTA sync)", link: "/channel-manager" },
          { text: "User guide", link: "/user-guide" },
        ],
      },
      {
        text: "AI & integrations",
        items: [
          { text: "Connect your AI (MCP)", link: "/ai-and-mcp" },
          { text: "MCP tool reference", link: "/mcp-tools" },
          { text: "REST API basics", link: "/api" },
          { text: "REST API reference", link: "/api-reference" },
        ],
      },
      { text: "Community", items: [{ text: "Contributors", link: "/contributors" }] },
      { text: "FAQ", items: [{ text: "FAQ", link: "/faq" }] },
    ],
  },
})
