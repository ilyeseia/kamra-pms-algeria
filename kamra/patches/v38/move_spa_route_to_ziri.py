import frappe


def execute():
	"""Point existing sites' home page at /ziri, the SPA's new public route.

	The product's page route moved from /kamra to /ziri. Code changes cover a
	fresh install, but Website Settings.home_page is a value sitting in every
	existing site's database, written once at install time, and nothing in the
	new code goes back for it. Left alone, a site that updates keeps home_page
	= "kamra" pointing at a www page that no longer exists - and the symptom
	is the worst shape it could take: everything a hotelier reaches by a
	bookmarked deep link still works, and only the bare hostname, the one URL
	they give to new staff, breaks.

	WHAT THIS DELIBERATELY DOES NOT DO

	It does not touch a home_page the hotelier chose. install.py promises in
	writing never to override a custom home page, and a patch is not a licence
	to break that promise quietly - so only the exact value this product wrote
	itself is moved. A site whose owner pointed home at their own marketing
	page keeps it, and reaches the console at /ziri like any other deep link.

	It also does not touch the app name. `kamra` is still the installed Frappe
	app: the Python module, /assets/kamra/, and the prefix of every
	/api/method/kamra.* endpoint. Only a URL changed.

	Old links keep working regardless of this patch - kamra/hooks.py redirects
	/kamra and /kamra/<anything> to the new route, because guests were sent
	self check-in links of the form /kamra/checkin/<token> and those messages
	are already in their hands.
	"""
	try:
		current = (frappe.db.get_single_value("Website Settings", "home_page") or "").strip()
	except Exception:
		# A site mid-migration with an unreadable Singles row is not a reason
		# to abort the whole patch run; the route still resolves via the
		# redirect, and first_boot/install will set it on the next pass.
		frappe.log_error(title="v38: could not read Website Settings.home_page")
		return

	if current != "kamra":
		return

	frappe.db.set_single_value("Website Settings", "home_page", "ziri")
	frappe.clear_cache()
