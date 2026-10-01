# Demo & sample data

There is **no public ZIRI PMS demo site**. Instead, every ZIRI install can
seed itself with a full sample hotel — rooms, guests, reservations,
folios, a restaurant menu and experiences — so you can click around a
living property before you put real guests in it.

Seed it on a fresh install:

```
bench --site <your-site> execute kamra.scripts.seed_demo.execute
```

It is **idempotent**: it does nothing if the demo property already
exists. It also turns on the site's demo mode, which is what puts the
one-tap role logins on the sign-in screen.

::: warning Don't seed a production site
Seeding creates a sample property, sample guests and sample users, and
flips the site into demo mode. Do it on a scratch site or a local bench —
not on the site that runs your hotel.
:::

## One-tap logins

With demo mode on, the sign-in screen shows a button per role. Each opens
the same hotel through different eyes.

| Role | What they see |
| --- | --- |
| System Admin | Everything, plus user management and developer settings |
| Hotel Admin (GM) | Runs the property end to end, no IT surfaces |
| Front Desk | Bookings, check-in/out, folios, night audit |
| Revenue | Rate plans, seasons, vouchers, guardrails |
| Finance | Billing, GST invoices, reports |
| Housekeeping | The room board and the floor phone app |

## Worth trying

- The **guest booking page**: `/book` — no login
- The **housekeeping phone app**: `/hk` on a phone
- The **restaurant POS + kitchen display** under the F&B app
- A **QR menu**: F&B → Outlets, then `/menu/<outlet>` as a guest would

## Wiping a playground

To wipe everything people created on a throwaway playground and reseed
from scratch:

```
bench --site <your-site> execute kamra.scripts.reset_demo.execute
```

This one is **deliberately hard to fire**: it refuses unless the site's
demo mode is on *and* the site is a recognised playground (a
`*.localhost` bench, or one of the upstream project's own demo hosts). A
real tenant can never trip it. Use `seed_demo` for anything else.
