import os

import frappe

# The SPA owns its own routing; never cache the boot shell.
no_cache = 1


def _is_root_request() -> bool:
	"""True when this page is being served as the site's home page at "/".

	Read from the real request path rather than frappe.local.path, which by
	this point has already been rewritten from "" to the home page's route and
	so reads "kamra" for both "/" and "/kamra" - the two cases this has to tell
	apart. Outside a request (bench execute, a test) there is no path and the
	answer is no.
	"""
	request = getattr(frappe.local, "request", None)
	if request is None:
		return False
	return (getattr(request, "path", "") or "").strip("/") == ""


def get_context(context):
	"""Serve the built React SPA shell with the session CSRF token injected.

	The front-end is built by Vite into kamra/public/frontend (served by Frappe
	at /assets/kamra/frontend/). We read that index.html at request time — so
	asset hashes never need to be hard-coded — and inject window.csrf_token so
	the SPA can POST to whitelisted endpoints once the user is logged in.
	"""
	# Served at "/"? Send the browser to the canonical /kamra before rendering.
	#
	# install.py and first_boot.py set Website Settings.home_page = "kamra" so a
	# visitor lands on the product instead of an empty Frappe Desk. That is the
	# right intent and it stays. What it also does is make Frappe render THIS
	# page at the site root, so the shell arrives with the browser sitting on
	# "/" while the SPA's router is mounted at "/kamra" (frontend/src/lib/
	# routing.ts). React Router then refuses to render anything and says so:
	#
	#   <Router basename="/kamra"> is not able to match the URL "/" because it
	#   does not start with the basename, so the <Router> won't render anything.
	#
	# A blank page with one console warning. Reproduced here before this was
	# written, and it is what any deployment that reaches the app at a hostname
	# root hits - which is every tsdproxy, Tailscale Serve or reverse-proxy
	# setup that maps a host to this container, since none of them add a path
	# prefix.
	#
	# Fixing it here rather than in website_redirects is deliberate: a redirect
	# hook fires for "/" unconditionally, including on a site whose owner has
	# pointed home_page at their own marketing page - and install.py promises in
	# writing never to override that. This function only runs when the kamra
	# page is the one being rendered, so the condition is structural rather than
	# something a future reader has to maintain.
	#
	# 302, not 301: the canonical path is a property of this configuration, not
	# of the universe. A hotelier who later sets a custom home page should not
	# have to fight a permanent redirect cached in every staff browser.
	if _is_root_request():
		frappe.local.flags.redirect_location = "/kamra"
		raise frappe.Redirect(302)

	index_path = frappe.get_app_path("kamra", "public", "frontend", "index.html")
	if not os.path.exists(index_path):
		frappe.throw(
			frappe._(
				"ZIRI front-end is not built. Run "
				"<code>cd apps/kamra/frontend && yarn install && yarn build</code> "
				"(Frappe Cloud runs this automatically on deploy)."
			),
			title="ZIRI not built",
		)

	with open(index_path, encoding="utf-8") as f:  # nosemgrep: frappe-security-file-traversal -- serves the app's own built index.html from a fixed app path, not user input
		html = f.read()

	csrf = frappe.sessions.get_csrf_token()
	boot = f'<script>window.csrf_token = "{csrf}";</script>'
	# Inject before the module script so the token is set before the app boots.
	html = html.replace("</head>", boot + "</head>", 1)

	context.spa_html = html
	context.no_cache = 1
	return context
