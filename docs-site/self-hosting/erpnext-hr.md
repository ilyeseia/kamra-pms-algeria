---
title: ERPNext and Frappe HR with ZIRI
description: Optional same-site accounting and HR — Marketplace, own server, and what each system owns.
---

# ERPNext and Frappe HR with ZIRI

ZIRI is the **hotel** system (rooms, folios, cashier, night audit, POS).
[ERPNext](https://erpnext.com) is the optional **company books** (chart of
accounts, invoicing, bank, tax reports). [Frappe HR](https://frappe.io/hr)
(`hrms`) is the optional **people** system (employees, leave, payroll).

You can run all three on **one Frappe site** — same login, same Apps
grid (`/apps`), different tiles for different jobs. ZIRI’s Marketplace
install does **not** force ERPNext or HR: most hotels already use Tally,
Zoho, Xero, or a local accountant.

## Who owns what

| Concern | System |
| --- | --- |
| Guest folios, cashier till, night audit, POS cash | **ZIRI** |
| Chart of accounts, GL, bank reconciliation, budgets | **ERPNext** |
| Payroll, leave, attendance | **Frappe HR** |
| Closed guest invoices → books (today) | **ZIRI → Accounting Export** (CSV for Tally / Zoho / ERPNext) |

This matches the usual PMS pattern: front office feeds the ledger; it
does not replace it.

## Packaging (one Marketplace app, three practical setups)

1. **PMS only** — install ZIRI (+ `payments`). Use Finance → Accounting
   Export for your existing ledger.
2. **PMS + books** — same site, also install **ERPNext**.
3. **PMS + books + HR** — same site, also install **Frappe HR** (after
   ERPNext).

Country or compliance apps (for example India Compliance) install on the
same site when you need them — they are not part of the ZIRI package.

## Where to find the apps after install

Open **`/apps`** (or the app switcher in the Desk top bar):

- **ZIRI** → hotel UI at `/kamra`
- **Accounting** (and Selling, Stock, …) → ERPNext workspaces
- **HR** / payroll → Frappe HR

Give staff roles so Front Desk lives in ZIRI, Accounts in ERPNext, and
HR in Frappe HR.

## Frappe Cloud (Marketplace)

Marketplace **ZIRI** only installs `payments` + `kamra` on your site.
To add books and HR on **that same site**:

1. Create a site on a **Frappe v16** bench (see
   [Frappe Cloud marketplace](/self-hosting/frappe-cloud)).
2. Marketplace → install **ZIRI**. Complete `/kamra/setup`.
3. On the **same site**, install **ERPNext** from Marketplace / Site Apps
   (use a v16-compatible release — same major as your bench).
4. Optionally install **Frappe HR** (`hrms`) the same way (it depends on
   ERPNext).
5. Run ERPNext’s company / chart-of-accounts setup, then open `/apps` and
   confirm ZIRI, Accounting, and HR tiles.

You do **not** need a second Frappe Cloud site for accounting.

**Versions:** ZIRI is the approved Marketplace `main` SHA. ERPNext and
HR follow whatever Frappe Cloud ships on that v16 bench. Keep majors
aligned (ZIRI + ERPNext + HRMS all on Frappe **v16**).

## Own server (bench)

After ZIRI is running (see [Install with bench](/self-hosting/bench)):

```bash
cd frappe-bench

# Same major as your Frappe (v16)
bench get-app --branch version-16 erpnext
bench get-app --branch version-16 hrms

bench --site pms.yourhotel.com install-app erpnext
bench --site pms.yourhotel.com install-app hrms

bench --site pms.yourhotel.com migrate
bench build --app erpnext --app hrms
```

Then open `/apps`, finish the ERPNext setup wizard (Company, chart of
accounts), and map staff roles.

For **Docker** images built with only `payments` + `kamra`, either:

- add `erpnext` and `hrms` to your `apps.json` and rebuild the image, or
- `bench get-app` / `install-app` inside the backend container on an
  existing site (same commands as above).

Plan **more RAM** when ERPNext + HR share the box (8 GB is a safer
floor for a busy property than the ZIRI-only 4 GB minimum).

## Own server — without ERPNext

If your accountant stays on Tally, Zoho, or another ledger:

1. Install ZIRI only.
2. In ZIRI: Finance → **Accounting Export**.
3. Download closed invoices in the format your books import.

No ERPNext required.

## Day-to-day bridge (today)

Until live posting ships:

1. Close guest stays and settle folios in ZIRI.
2. Export from **Accounting Export**.
3. Import or post into ERPNext (or Tally / Zoho).

Payroll journals from Frappe HR post into the same ERPNext company when
HR is installed.

## What ZIRI will not do

- Bundle ERPNext or HR into every Marketplace install
- Replace Chart of Accounts, bank recon, or statutory filings inside
  the PMS
- Rebuild payroll inside ZIRI

## Related

- [Frappe Cloud marketplace](/self-hosting/frappe-cloud)
- [Install with bench](/self-hosting/bench)
- [Quickstart (Docker)](/quickstart)
- [Features — billing & export](/features)
