# Licensing — Algeria Distribution

What the licence permits, what it requires, and what both mean in practice when
you install this for a paying hotel.

> **This is an engineering summary of a licence text, not legal advice.** It is
> written by the people who read the source, to make the obligations concrete
> and checkable. It is not a substitute for a lawyer, and a commercial offering
> built on this software should be reviewed by one — particularly in Algeria,
> where free-software licences have little local case law and your contract
> with the hotel will do most of the work.

---

## 1. The licence

Kamra PMS is licensed under the **GNU Affero General Public License, version 3**
(AGPL-3.0). The full text is in `license.txt` at the repository root — 661
lines, the FSF's canonical text, unmodified. `README.md` states AGPL-3.0, and so
do `CONTRIBUTING.md`, `RELEASING.md`, `deploy/README.md` and the project's own
documentation site.

The AGPL is a strong copyleft licence. Its distinguishing feature, compared to
the GPL, is **§13 — Remote Network Interaction** (`license.txt:540-551`), which
extends the source-offer obligation to people who use the software *over a
network* without ever receiving a copy of it. That matters here because a PMS is
exactly that kind of software: staff use it in a browser, and so do guests on
the public booking pages.

**The changes on this branch are themselves AGPL-3.0.** The Algeria country
pack, the French UI, the fixed per-person *taxe de séjour*, the RC/NIS/AI
invoice fields, the `v36`/`v37` migrations — all of it is derivative work of an
AGPL program and carries the same licence. This is not a choice made later; it
is the condition under which the work could be done at all.

---

## 2. You may sell this

Plainly, and without hedging: **the AGPL does not prohibit commercial use, and
it does not prohibit charging money.** You may:

- **charge for installation, configuration and deployment.** Getting this
  running on a client's infrastructure is your labour and you may price it.
- **charge for support, maintenance and training.** Ongoing service is a
  service.
- **charge for customisation.** Building an Algeria localisation, writing
  migrations, translating the interface — work, billable.
- **charge for hosting.** Running it on your own infrastructure for a hotel is
  a service you may sell.
- **charge for the software itself.** The AGPL sets no price ceiling on
  conveying a copy.
- **use it commercially without limit** — no per-room fee, no seat count, no
  module licence, no phone-home.

What the licence constrains is not whether you charge, but **what the recipient
receives along with it**. That is §3.

One note in passing, because it sits in this repository:
`deploy/README.md` says *"Do not put a price on AGPL Kamra itself"* in the
context of hyperscaler marketplace listings. That is the upstream project's own
commercial posture for its own storefronts. It is not a licence term and it does
not bind you.

---

## 3. What you must do

Four obligations. All four are achievable and none is onerous, but they are
conditions on the permission, not suggestions — under §8 of the licence, failing
them terminates your rights.

### 3.1 Offer the Corresponding Source to everyone who uses it over a network

This is §13, and it is the one people miss. The operative text
(`license.txt:542-548`):

> if you modify the Program, your modified version must prominently offer all
> users interacting with it remotely through a computer network […] an
> opportunity to receive the Corresponding Source of your version by providing
> access to the Corresponding Source from a network server at no charge

Unpack that for a hotel deployment:

- **"if you modify"** — this branch modifies. The Algeria work is a
  modification. §13 applies.
- **"all users interacting with it remotely"** — the front desk staff on the
  `/kamra` app, the housekeeping phones, and **the guests on the public booking
  and check-in pages**. Not just whoever paid you.
- **"prominently offer"** — reachable from the interface, not buried in a
  contract annexe.
- **"from a network server at no charge"** — a URL. A private repository behind
  a login that a guest cannot reach does not satisfy this; a public repository,
  or a source tarball on a web server, does.

**In practice:** put a source link in the interface. A footer line or an About
page is the usual and expected form, and it is what a reviewer will look for.

Something of the shape:

> Kamra PMS — Algeria Distribution 1.0.0 (Kamra core 2.6.5).
> Free software under the GNU AGPL-3.0.
> Source code: `https://github.com/ilyeseia/kamra-pms-algeria`

Two practical notes on placing it:

- **It must be on surfaces guests reach**, not only on staff screens. The
  public booking page, the public listing page and the public check-in page are
  network interaction under §13 just as much as the front desk console.
- **The login screen already has a slot begging for it.**
  `frontend/src/screens/Login.tsx:181-183` renders `Kamra PMS v{version}` when
  a version is present — but it reads `info.version` from
  `public_api.site_info()` (`Login.tsx:42`), and that endpoint returns only
  `{"demo_mode": …}` (`kamra/public_api.py:207-216`). So **the version line
  never renders today.** Making `site_info()` return a version and a source URL
  would light up that line and give you the §13 notice in one place the whole
  app already renders. That is an implementation note for the orchestrator, not
  a documentation task — but it is the cheapest correct fix available.

"Corresponding Source" means the source for the version actually running,
including build scripts. If you install commit `abc1234`, the offer must lead to
`abc1234` — not "roughly this project". Pinning the client's install to a tag
and naming that tag in the notice is the clean way to keep the offer honest;
[`VERSIONING.md`](VERSIONING.md) covers how the Algeria Distribution version is
tracked separately from Kamra core 2.6.5.

There is a direct consequence for §3 of [`INSTALLATION.md`](INSTALLATION.md):
if you keep `ilyeseia/kamra-pms-algeria` private and bake a token into
`apps.json` to build it, you still owe every user of that deployment a source
offer they can actually use. A private repository does not satisfy it. Making
the repository public is both the cheaper engineering answer and the one that
discharges the obligation.

### 3.2 Preserve the upstream copyright and attribution

Kamra PMS is upstream work by HeyKoala and contributors — `pyproject.toml` names
the author, and files carry headers such as
`# Copyright (c) 2026, HeyKoala and contributors / For license information,
please see license.txt` (`kamra/scripts/first_boot.py:1-2`).

You must not:

- remove or alter those copyright notices
- remove the licence notices, or the notices stating the absence of warranty
- present the software as though it originated with you

You **may** add your own copyright for your own contributions, and you may
brand your distribution and your service. "Algeria Distribution, by
[your company], built on Kamra PMS" is accurate and permitted. Silently
rebranding it so the hotel believes you wrote it is not — and it is also the
kind of thing that surfaces awkwardly the first time a client reads the source
link you are obliged to give them.

The practical rule: **the hotel must be able to find out what this software is
and where it comes from.** If they cannot, something has gone wrong with your
attribution.

### 3.3 Convey derivative work under the same licence

Anything you build on top — a new country pack, a channel-manager integration,
a bespoke report for one hotel, a modified invoice template — is derivative work
of an AGPL program. When you convey it, or deploy it where users interact with
it over a network, it goes out under AGPL-3.0.

You cannot take this codebase, add a proprietary module, and ship the
combination under a closed licence. That is the copyleft, and it is the
mechanism, not a side effect.

What this does **not** prevent:

- **Configuration is not derivative work.** Rates, room types, tax percentages,
  property records, the hotel's own data — all just data. Nothing about the
  licence touches it, and the hotel owns it.
- **Genuinely separate programs** that talk to Kamra over its HTTP API or MCP
  tools are a different matter from code linked into the app. Where the boundary
  falls is a fact-specific legal question, and it is exactly the sort of
  question to put to a lawyer *before* you build the thing, not after you have
  sold it.

Custom work you do for one hotel is AGPL. In practice this rarely troubles
anyone, because a bespoke report for one Algerian hotel has no commercial value
to a competitor and your client has no interest in publishing it. But it is the
position, and you should know it rather than discover it.

### 3.4 Give the client the licence

The recipient must receive the AGPL-3.0 text. `license.txt` ships in the
repository, so any install already carries it — but "it is in a folder on the
server" is a thin reading of an obligation.

Do it properly: hand over the licence with the documentation, and say in one
sentence what it means — that the hotel has received free software, that they
have the right to the source, and that nothing stops them hosting it elsewhere
or hiring someone else to maintain it.

That last point is worth saying out loud rather than hoping they never ask. It
is also, in a competitive sale, a genuine advantage: no lock-in is a feature the
incumbent per-room-licence vendors cannot match. `README.md:75-81` makes exactly
that argument.

---

## 4. Handover checklist

Tick these at handover, alongside the operational checklist in
[`INSTALLATION.md`](INSTALLATION.md) §11.

- [ ] A **source offer** is reachable from the running interface — staff
      screens **and** the public guest pages (§3.1)
- [ ] The URL in that offer is **publicly reachable**, at no charge, and leads
      to the version actually installed
- [ ] The installed version is identified: **Algeria Distribution 1.0.0 on
      Kamra core 2.6.5**, ideally a tag
- [ ] Upstream copyright headers and licence notices are intact (§3.2)
- [ ] Your own branding, if any, does not misrepresent the origin
- [ ] `license.txt` handed over with the documentation
- [ ] The client has been told, in plain language, that this is free software,
      that they are entitled to the source, and that they are not locked in
- [ ] Your invoice describes what you actually sold — installation,
      configuration, localisation, support — rather than a "software licence"
      you are not in a position to grant
- [ ] Any bespoke work you did for this client is understood by both sides to
      be AGPL

---

## 5. What the licence does not give the client

Worth stating, because it is where support contracts and expectations collide.

**No warranty.** §15 and §16 of the licence disclaim warranty and limit
liability, in the customary all-caps. The software is provided as-is.

That disclaimer covers the *licence*. It does **not** cover promises **you**
make. If you tell a hotel their invoices are compliant with Algerian tax law,
you have made a representation on your own account, and the AGPL's disclaimer
will not help you. This is why [`TAXES.md`](TAXES.md) and
[`INSTALLATION.md`](INSTALLATION.md) §8.4 are emphatic that the rates are
configurable defaults and that the client's accountant must confirm the
treatment before the first live invoice — and why that confirmation should be on
record.

The same applies to everything in [`INSTALLATION.md`](INSTALLATION.md) §8. The
untested migrations, the unverified RTL layout, the Percent-mode levy defect —
a client who was told about them and proceeded is in a different position from
one who was not. Disclosure is both the honest thing and the commercially
sensible one.

**No support.** The licence grants no right to support. Support is what you
sell, and it belongs in a contract with a defined scope, defined response times
and a defined price.

---

## 6. Summary

| Question | Answer |
| --- | --- |
| Can I sell this to a hotel? | Yes |
| Can I charge for installation, support, training, customisation? | Yes |
| Can I charge for hosting it for them? | Yes |
| Can I keep the source secret from the hotel? | No |
| Can I keep the source secret from their guests, who use the booking page? | No — §13 |
| Can I remove the upstream copyright? | No |
| Can I rebrand it as my own product? | Brand your distribution, yes. Misrepresent its origin, no |
| Can I add a proprietary module and ship it closed? | No |
| Does the hotel's own data fall under the licence? | No. Their data is theirs |
| Can the hotel take it elsewhere and hire someone else? | Yes. That is the deal |
| Is my Algeria localisation work AGPL? | Yes |
| Does the licence warrant that this works, or that it is tax-compliant? | No, expressly not |
| Is this document legal advice? | **No.** See a lawyer |

---

## See also

- `license.txt` — the AGPL-3.0 text; §13 at lines 540-551
- [`INSTALLATION.md`](INSTALLATION.md) — install, verification, §8 *What is not proven*
- [`TAXES.md`](TAXES.md) — why the tax rates are defaults and not advice
- [`VERSIONING.md`](VERSIONING.md) — identifying the version a source offer must lead to
- [`BACKUP.md`](BACKUP.md) — the client's data, and their right to leave with it
