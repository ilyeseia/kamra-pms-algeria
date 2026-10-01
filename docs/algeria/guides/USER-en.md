# ZIRI PMS — Staff Guide

For receptionists, night auditors, housekeepers, cashiers and restaurant
staff. It covers the jobs you do every shift. No technical knowledge needed.

ZIRI PMS runs in a web browser. There is nothing to install on your
computer or phone.

---

## 1. Signing in, and choosing your language

Open the address your hotel gave you. It ends in `/kamra` — for example
`http://localhost:8080/kamra`. That is just the internal name of the
program; type the address exactly as it was given to you.

**To sign in:**

1. Open the hotel's address in the browser.
2. Type your **Email or username** and your **Password**.
3. Press **Sign in**.

If you see *"Wrong email, username, or password."*, check for capital
letters and for a space at the end. If you see *"Your session ended. Sign in
to pick up where you left off."*, you were simply signed out after a long
idle period — sign in again.

### Choosing your language

There are three languages: **English**, **Français** and **العربية**.

- On the sign-in screen there is a **Language** selector. Set it before you
  sign in if you prefer.
- Once you are signed in: **Settings → Appearance → Language**.

Choosing **العربية** flips the whole interface right-to-left: the menu moves
to the right side of the screen, and tables and buttons mirror across.

The language is stored in the browser you are using, not in your staff
account. So the reception PC can stay in French while your own phone is in
Arabic. If you sign in on a different computer, set the language again
there.

### Signing out

Top bar → **Sign out**.

---

## 2. Finding your way around

ZIRI PMS is divided into **apps**. The top bar shows which app you are in;
**Switch app** moves between them, and **View all apps** shows them all on
one page. You only see the apps your role allows.

| App | What it is for |
| --- | --- |
| **Front Desk** | Arrivals, departures, bookings, guests |
| **Housekeeping** | Room status board, tasks, laundry, lost & found, the phone app |
| **Operations** | Guest requests, WhatsApp |
| **F&B** | Restaurant POS, kitchen display, the menu |
| **Banquets & Groups** | Functions, halls, groups |
| **Revenue** | Rates, seasons, offers, partners |
| **Finance** | Cashier till, folios, night audit, ledgers |
| **Booking Engine** | The hotel's own online booking page |
| **Admin** | Property setup, rooms, users |

### Search

**Open search** in the top bar, or press **Ctrl + K** (**Cmd + K** on a Mac).
Type a guest name, a reservation, a room number — it also jumps to any
screen. This is the fastest way around; you do not have to hunt through
menus.

### The screens you will use most

| Screen | Where | What you do there |
| --- | --- | --- |
| **Today** | Front Desk | The whole day: arrivals, departures, in-house, room board |
| **Tape Chart** | Front Desk | Who is in which physical room, across dates |
| **Reservations** | Front Desk | The list of bookings |
| **Guests** | Front Desk | Guest records and their past stays |
| **Registration card** | Opened from an arrival | The fiche de police |
| **Room Board** | Housekeeping | Every room's cleaning status |
| **Billing** | Finance | All open folios, and the night audit |
| **My Till** | Finance | Your cash drawer |
| **Restaurant POS** | F&B | Taking restaurant orders |
| **Kitchen Display** | F&B | The kitchen pass |

### If the connection drops

A banner reads **"Connection lost — reconnecting…"**. Wait for it to clear.
Do not retype what you were doing — the screen reconnects on its own and
refreshes.

---

## 3. Front desk

### Today — the day at a glance

**Today** is the home screen (**Front Desk → Today**). It refreshes itself
every half minute. It shows:

- **Arrivals** — who is due in
- **Departures** — who is due out
- **In-house guests** — who is staying tonight
- **Room board** — every room and its cleaning status
- **Occupancy**, **Revenue** and **Open tasks** at the top

Every stay row carries a small money chip from the folio: **Paid**,
an amount **due**, or **Unpaid**. Read that chip before you let a guest
leave.

An arrival row also shows:

- **GRC** — opens the registration card
- **copy check-in link** — copies the guest's own online check-in link so you
  can send it. Hover it: it tells you whether the link should go to the guest
  or to whoever booked the room.
- **Pre-checked-in** — the guest already filled in their details online

### Checking a guest in

1. **Front Desk → Today → Arrivals**, find the guest's row.
2. Press **Check in**.
3. The check-in panel opens. If a room was assigned it says
   *"Room {number} is assigned"*; otherwise press **Pick a room** (or
   **Or pick another room** to change it).
4. Fill in **ID type** and **ID number** if they are not on file.
5. Press **Check in to {room}**.

Notes:

- If the room is not cleaned yet, the panel warns
  *"{room} hasn't been cleaned yet"*. You can still check in — housekeeping
  will see the room flip to occupied — but tell them.
- If there is no free room of that type, the panel says so and tells you to
  check the tape chart for a move or an upgrade.
- Capturing the ID never blocks check-in. But the guest register wants it
  **before the night audit** runs.

### A walk-in

1. Press **New booking** (top right, from any screen).
2. Set **Booking mode** to **Walk-in** — *"A walk-in arrives today"*. This
   books the stay, checks the guest in and takes the money in one step.
3. Enter the **Guest name**, **Phone**, **Room type**, **Nights**,
   **Adults** / **Children** and the **Meal plan**. The **Quote** updates as
   you type.
4. Enter what you are collecting under **Amount collected** and the
   **Payment mode**.
5. Press **Check in & collect {amount}** (or **Check in** if you are
   collecting nothing — then it all stays on the bill).

### The registration card (fiche de police)

The legal guest register. Open it from the arrival row's **GRC** button, or
from the check-in panel's **Open GRC**. The printed heading reads
**GUEST REGISTRATION CARD**.

1. Check the **Name**, **Phone**, **Address**, **Nationality** and
   **ID document**. Press **edit** beside **Nationality** to correct it —
   it then prints on the folio and the invoice too.
2. Under **Occupants**, record **everyone** sleeping in the room, not only
   the person who booked. The counter reads
   *"Occupants registered ({n} of {pax})"* — it should not be short.
3. Add each occupant's ID and nationality in the same list.
4. Press **Print GRC**.
5. Have the guest sign — on the printed card, or on screen under
   **Guest signature** if they are in front of you. A guest who checked in
   online shows as **Signed online**.
6. Sign the **Front desk (name & sign)** line yourself.

The **ID document** list offers: **National ID** (the Carte Nationale
d'Identité), **Passport**, **Driving License**, **Residence Permit** and
**Other**. *"Residence Permit"* is currently shown in English even when the
rest of the interface is French or Arabic — it is the residence permit.

The card also carries **Actual check-in** / **Actual check-out**,
**Assign room** / **Change room**, and **Open bill** to jump straight to the
folio.

### Checking a guest out

1. **Front Desk → Today → Departures**, find the row.
2. Read the money chip. If money is owed, settle it first — see section 5.
3. Press **Check out**.

Checkout fills in any room nights that had not yet been posted, so the final
bill is complete.

### Room status from the front desk

The **Room board** on **Today** shows every room. Click a room to advance its
cleaning status. The four statuses are **Clean**, **Dirty**, **Inspected**
and **Out of Order**.

---

## 4. Reservations

### Creating a booking

1. Press **New booking**.
2. Type the **Guest name**. A returning guest appears as you type — pick them
   and the stay attaches to their record (*"Returning guest · {n} stays"*).
3. Set **Room type**, **Check-in**, **Check-out**, **Adults**, **Children**
   and **Meal plan**. The **Quote** recalculates live and shows the
   cancellation terms and any deposit expected.
4. Optional: **Add another room** turns it into a group — one **Confirm
   booking** books every room under one reference.
5. Optional: company, add-ons, a **Promo code**.
6. Press **Confirm booking**. You get a reference (*"Booked · {ref}"*), and
   the stay appears under **Arrivals** on its check-in date.

If no room was assigned automatically you will see
*"No room auto-assigned — pick one from Reservations."*

### The tape chart

**Front Desk → Tape Chart.** One row per physical room, dates across the top.
Each coloured bar is a stay. The legend marks **Free**, **Confirmed**,
**Checked in**, **Occupied**, **Held (house use / VIP / maintenance)**,
**Group**, **Corporate**, **VIP**, **OTA** and **Hourly**.

- **Filter by room type** narrows it down.
- **Auto-assign arrivals** proposes a **Suggested room plan for {date}**;
  review it, then **Assign {n} rooms**. If every arrival already has a room
  it tells you so.
- **CHANGEOVER CONFLICT** means an arrival is timed before the previous
  guest's departure in the same room. Fix the **Arrival / departure times
  (ETA · ETD)**, or move one of the two.

The **Calendar** screen is the other view: it sells by room *type* and shows
rates and availability. The tape chart operates — who is in which actual
room.

### Moving a guest to another room

1. **Tape Chart** → click the guest's bar (or open the reservation).
2. Press **Move room** — or **Change room** from the registration card.
3. Choose **Same type**, or **All types (upgrade)** to look wider. Use
   **Search room number** to find one directly.
4. The panel shows the price effect before you commit —
   *"No change to the price."* or the new stay total.
5. Add a **Reason** and, if useful, a **Note (optional)**, then press
   **Move to {room}**.

If the guest is already in-house, the old room is automatically marked
**Dirty** for housekeeping. If the new room is not clean yet the panel warns
*"{room} hasn't been cleaned yet."*

### Changing dates

Click the bar on the tape chart and press **Update stay**. Date changes
re-price automatically — unless the booking holds a manually set amount —
and the system re-checks the room for double bookings.

### Cancelling a booking

1. Open the reservation.
2. Press **Cancel this stay…**.
3. Read what it costs **before** you confirm. The panel says either
   *"Outside the fee window - cancellation is free."* or *"Inside the {days}-day
   window - the {basis} ({amount}) will be charged."*
4. Pick a **Reason**.
5. A manager may tick **Waive the fee (logged - manager's call)** — this is
   recorded against the booking.
6. Press **Confirm cancellation**.
7. Give the guest the **cancellation number** shown
   (*"Cancelled - {number}"*), and use **Print / share the confirmation
   letter** if they want it in writing. The letter shows any refund due.

You cannot set a booking to Cancelled by editing its status field. Use
**Cancel this stay…** so the policy and the fee are always applied.

### No-shows

You do not mark a no-show by hand. The **Night audit** (section 8) flags
guests who never arrived and charges them according to the hotel's
cancellation policy. The audit result line reports how many it flagged.

---

## 5. Money

### The folio

The **folio** is a guest's running bill. One opens automatically at
check-in. Find it under **Finance → Billing** — the list of every open folio
with its **Total**, **Paid** and **Balance** — or from the guest's
registration card via **Open bill**.

A folio has two halves: **Charges** and **Payments**. **Balance** is what is
still owed.

### Unlocking money actions

Before posting payments or settling a folio you need your cashier PIN. The
folio shows *"Cashier PIN required for money actions."*

1. Press **Unlock**, type your PIN.
2. *"Cashier unlocked — money actions are open for 15 minutes."*

The first time, press **Set PIN** and choose one. Never share it — every
money action is recorded against whoever was unlocked.

### Adding a charge

1. Open the folio.
2. Press **Post a charge**.
3. Fill in the **Description**, the **Amount** and the tax rate.
4. Press **Post**.

To move a charge to another folio, or split it, open the line and use
**Move or split this charge**: enter either a percentage or an amount
(`30% or 1500`). To cancel a charge that should never have been there, use
**Void this charge** and give a reason — it is kept on the record.

### Taking a payment

1. Open the folio.
2. Press **Record a payment**.
3. Choose the **Payment mode**: **Cash**, **Card** or **Bank Transfer**.
   A CIB or Edahabia card is recorded as **Card** — that is correct, and it
   keeps the till and the ledger balanced.
4. Type the **Amount** and, for a card or a transfer, the
   **Card slip / transfer ref (optional)**.
5. Say what the money is — against the bill, an advance, or a refundable
   deposit.
6. Press **Record**.

**Payment link** instead creates a payment link for the balance and copies
it, so you can send it to the guest.

### Deposits

The deposit panel on a reservation shows **Expected**, **Received** and
**Still due**, and marks the booking **Secured**, **Part paid** or
**Not paid**.

- **Record payment** logs a deposit taken at the desk.
- **Send payment link** lets the guest pay it themselves — **Copy message**
  gives you the text to send. When they pay, the deposit posts by itself.

A deposit is carried to the guest's folio and counts against the bill at
check-in.

### Printing an invoice

1. Open the folio and check that **Balance** is zero.
2. Press **Close & generate invoice**. This assigns the invoice number.
3. Press **Print invoice**.

Before that step the document is only a **Provisional Bill** / **Proforma**,
and it says so: *"Not a tax invoice yet — the number is issued when the folio
is settled."* Use **Print folio** if the guest just wants to see the running
total, or **Advance bill** for a bill in advance.

If the guest is staying on but wants this period closed, use **Settle &
continue stay**.

If an invoice was issued in error, **Cancel invoice** puts the number on the
cancelled register and reopens the folio for correction. A **Credit note**
corrects an amount without cancelling the invoice.

### TVA and the taxe de séjour on a bill

Two different things sit on the tax side of an Algerian bill.

**TVA** — *Taxe sur la valeur ajoutée* — is a percentage of what the guest
consumed. On the folio you see a **TVA %** column, a **TVA** amount column
and a **TVA summary** block that groups the bill by rate. The hotel's tax
registration prints on the invoice as **NIF**.

**Taxe de séjour** is the municipal stay tax. It is a separate charge line on
the folio, named by whatever the hotel typed as its levy name — by default
**Taxe de séjour**, printed in Latin script even when your interface is
Arabic. Depending on how the hotel set it up, it is either a percentage of
the room rate or a fixed amount per person per night. It is charged on adults
only.

One leftover to know about: the **Billing** screen's own subtitle still reads
*"Click a folio to post charges, settle and print the GST invoice"*, and the
same wording appears in French and Arabic. GST is another country's tax name.
On your bills the tax is **TVA**; the folio columns and the printed invoice
say so correctly. Ignore the word GST where you see it, and mention it if
support asks.

**The rates are not fixed by the software.** The hotel configures them, room
type by room type. If a rate on a bill looks wrong, do not change anything —
tell your manager, and the hotel's accountant confirms what is correct. The
figure you were quoted at booking is the figure that is charged: a guest who
accepted one number is never handed another.

### Your till

**Finance → My Till.**

1. **Open till** at the start of your shift, and enter the **Opening float**.
2. Post cash as you take it; the session lists **Recent transactions**.
3. Use **Drop to safe** for a **Cash drop** during the shift, and
   **Paid out** for money going out.
4. At the end: **Close till**. Enter your **Counted cash (expected
   {amount})**. The screen shows the **Variance**.
5. Print the **Shift report**.

A variance is not a disaster — report it, do not adjust the count to make it
disappear.

---

## 6. Housekeeping

### The room board

**Housekeeping → Room Board.** Every room at a glance, with a colour for each
status.

| Status | Meaning |
| --- | --- |
| **Dirty** | Needs cleaning |
| **Clean** | Cleaned |
| **Inspected** | Checked by a supervisor |
| **Out of Order** | Not sellable |

**To change a room's status:**

1. **Housekeeping → Room Board.**
2. Use **Filter rooms** or **All Floors** to narrow it down.
3. Tap the room.
4. Press **Mark {status}**.

Room attendants can mark rooms **Dirty** or **Clean** only. Passing a room
as **Inspected**, or blocking it **Out of Order**, is a supervisor's call.

The board also flags **Due out** (a departure today), **Occupied** and
**Unassigned**.

### Marking a room out of order

A supervisor tapping the room and choosing **Mark Out of Order** takes it off
sale — reception cannot then put a guest in it. Put it back to **Dirty** or
**Clean** when it is repaired, or reception will keep working around a room
that is fine.

### The phone / tablet app

Room attendants work from the phone app, not the board. Open `/kamra/hk` —
for example `http://localhost:8080/kamra/hk`. Save it to your phone's home
screen.

1. Sign in. **My Tasks** lists your rooms, arrivals first.
2. Press **Start** when you begin a room.
3. Press **Done** when it is finished — that marks it **Room clean** on
   everyone's board immediately.
4. If you have nothing assigned, look at the unassigned rooms and press
   **Take this room** to add one to your list.
5. **Refresh** pulls in new work.

Also from the phone:

- **Post to room {number}** — minibar or laundry taken in an occupied room.
  Tap the room, enter what it was (for example `2 cola, 1 water`), press
  **Post {amount}**.
- **Log a lost or found item** — describe it (for example
  `black umbrella`), add a photo with **Add photo / video**, press
  **Log it**.
- **Laundry** — pickups and returns.

Rows are flagged **arrival today**, **overdue** and **VIP** so you know what
to do first.

---

## 7. Restaurant and POS

### Taking an order

**F&B → Restaurant POS.**

1. Pick the table under **Tables**, or press **New bill**.
2. Use **Search menu items…** or tap the menu items to add them. Items are
   marked **Veg** / **Non-veg**.
3. They build up under **Order items** with the **Subtotal** and **Total**.
4. Press **Send to kitchen** — the kitchen ticket (**Fire KOT**) goes to the
   **Kitchen Display**.
5. For a second round on the same table, add the items and press
   **Add round & fire KOT**.

Other buttons: **Hold bill** parks it, **Split** moves selected lines to a
new bill (*"Tick the lines moving to the new bill."*), **Add discount**
applies a reduction, **Print bill** gives the guest the note,
**Complimentary** marks an order not to be billed.

**Tables & running bills** and **Running tables** show what is open, with
seats and status (**Available**, **Occupied**, **Cleaning**, **Reserve**).

### Posting a charge to a room

1. In the POS, select the bill.
2. If the table is linked to an in-house guest, the settle button reads
   **Settle / post to room** instead of **Settle**.
3. Press it. The charge lands on that guest's folio and appears in
   **Finance → Billing**.

If the button still says only **Settle**, the table is not linked to a room —
take payment at the restaurant, or link the table to the guest first.

### The kitchen

**F&B → Kitchen Display** — the **Kitchen pass**. Tickets arrive marked
**NEW**.

1. Press **Start / accept** — the ticket goes to **COOKING**.
2. Press **Mark ready** per item, or **All ready — send to pass** for the
   whole ticket.
3. **Recall** brings back a ticket you closed by mistake
   (**Undo — put it back on the board**).

Watch for **LATE** on a ticket that has been waiting, **Guest allergy** and
**Table note**, and **CANCELLED — STOP COOKING** — stop, the order is off.
**Fire {course}** releases a held course.

---

## 8. Night audit

The night audit closes the hotel's day. It:

- posts tonight's room charge and tax for every in-house guest
- opens any folio that was still missing
- flags and charges no-shows according to the hotel's policy

**It runs by itself every night at 3 AM.** You normally do nothing.

**To run it by hand:**

1. **Finance → Billing.**
2. Press **Run night audit**.
3. Read the result line: how many room nights it posted, how many folios it
   opened, how many no-shows it flagged.

**Recent runs** lists the last few.

It is safe to run twice. If it has already run it says
*"Already ran for today"* and nothing is charged again.

Run it by hand only when the automatic run was missed — for example after a
power cut or a night when the server was down. Check **Recent runs** first.

Before the audit, make sure every arrival that came in is actually checked
in and every departure is checked out. A guest left unchecked-in overnight
will be treated as a no-show.

---

## 9. Guests booking online

### The booking page

The hotel's own booking page is at `/kamra/book` — for example
`http://localhost:8080/kamra/book`. A guest needs no account.

They pick dates and guests, press **Check availability**, choose a room,
enter their name and phone, and press **Confirm & pay** or **Book now**. The
page also shows **Photo Gallery**, **Hotel Policies & Rules**,
**House rules**, **Frequently Asked Questions**, **Location & Directions**,
any **Security deposit**, and takes a **Promo code** and **Special
requests**.

Bookings made there arrive in **Reservations** and on **Today** like any
other.

The page has its own language picker — **English**, **Français**,
**العربية** — that a guest can reach without signing in, and it mirrors
right-to-left in Arabic. On a phone set to Arabic, the page opens in Arabic
by itself.

### The QR menu

A guest scanning the table or room QR code lands on `/kamra/menu/<outlet>`,
which shows the outlet's menu with its own language picker. It says which
**Table {n}** or **Room {n}** they are at.

They press **Add one** on the items they want and then **Place order**. The
page tells them plainly: *"A server confirms your order before the kitchen
starts."* So watch for incoming orders and confirm them — nothing reaches the
kitchen until someone on the floor does.

### One thing to expect

The interface translates. **The hotel's own text does not.** Property and
room descriptions, house rules, the FAQ, amenity names, meal plans and menu
item names are typed in once by the hotel and stored as typed. So a guest
reading an Arabic interface may well see French or English inside it — the
buttons and labels in Arabic, the description of the room in whatever
language it was written.

That is not a fault, and it is not something you can fix from the front desk.
If guests comment on it, tell your manager: the hotel can retype that content
in the language most of its guests read.

---

## 10. Common problems and what to do

| What you see | What to do |
| --- | --- |
| **"Connection lost — reconnecting…"** | Wait. Do not retype. The screen reconnects and refreshes by itself. |
| **"Cashier PIN required for money actions."** | Press **Unlock** and enter your PIN. First time: **Set PIN**. |
| Money buttons do nothing | Your 15-minute unlock expired. **Unlock** again. |
| **"{room} hasn't been cleaned yet"** at check-in | You can still check in. Tell housekeeping, or press **Or pick another room**. |
| **"No free room of this type for these dates"** | Open the **Tape Chart** and look for a move or an upgrade. |
| **"No room auto-assigned — pick one from Reservations."** | Open the reservation and assign a room, or use **Auto-assign arrivals** on the tape chart. |
| **CHANGEOVER CONFLICT** on the tape chart | An arrival is timed before a departure in the same room. Fix the **ETA · ETD**, or move one guest. |
| You cannot set a booking to Cancelled | That is deliberate. Use **Cancel this stay…** so the fee and policy apply. |
| Night audit says **"Already ran for today"** | Nothing to do. It has already closed the day and will not charge twice. |
| A guest is due out but the chip says money is owed | Settle the folio before **Check out**. |
| **Settle** does not offer **Settle / post to room** | The table is not linked to an in-house guest. Take payment at the outlet, or link the table first. |
| The interface is in the wrong language | **Settings → Appearance → Language.** It is set per browser, so each device is separate. |
| An Arabic screen shows French or English text | That will be the hotel's own content — descriptions, rules, menu names. It is stored in one language. Tell your manager. |
| An Arabic screen looks misaligned, overlapping or cut off | **Report it.** The Arabic layout has not yet been checked screen by screen, and printed cards and invoices have not been checked in any language. Do not assume it is meant to look that way. |
| A tax rate on a bill looks wrong | Do not change it. Tell your manager — the hotel sets the rates and the accountant confirms them. |
| The cash count does not match | Report the **Variance** on the **Shift report**. Do not adjust the count. |

---

## 11. Who to call

First, your duty manager or the hotel's own administrator. Most problems —
a rate, a room blocked, a user who cannot sign in — are settled inside the
hotel.

If it has to go to support, have this ready:

| Tell them | Where to find it |
| --- | --- |
| The product: **ZIRI PMS** | — |
| The version: **2.6.5** | Not shown on staff screens — quote this guide, or ask your administrator whether it has been updated |
| The property name | Top bar |
| The exact address you had open | The browser's address bar |
| The screen you were on | Its title, e.g. **Today**, **Tape Chart**, **Billing** |
| The interface language | English, Français or العربية |
| The message, word for word | On screen — a photo of the screen is ideal |
| The record number | The reservation, folio or invoice number |
| The time it happened | Your watch |
| What you were doing | One sentence: "I pressed **Check out** on room 204 and…" |

Say plainly whether the guest is waiting at the desk. That changes how fast
it is picked up.

---

*ZIRI PMS 2.6.5 — staff guide. Screen and button names in this guide match
the English interface. If your interface is in Français or العربية, the same
buttons are in the same places with the translated labels.*
