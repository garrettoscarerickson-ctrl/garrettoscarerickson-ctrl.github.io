# Turning on shared reviews

Right now reviews are saved in each visitor's own browser, so people only
see their own. To make **everyone see everyone's reviews**, the site needs
somewhere shared to store them. A static site can't do that on its own.

This takes about five minutes, once.

## 1. Make a free Supabase project

Go to [supabase.com](https://supabase.com), sign up, and create a project.
The free tier is far more than this site will use.

## 2. Create the table

In your project: **SQL Editor → New query**, paste this, and hit Run.

```sql
create table photo_reviews (
  id          bigint generated always as identity primary key,
  photo       text not null,
  name        text not null,
  rating      int  not null check (rating between 1 and 5),
  text        text default '',
  approved    boolean not null default false,
  created_at  timestamptz not null default now()
);

alter table photo_reviews enable row level security;

-- the public only ever sees reviews you have approved
create policy "public read approved"
  on photo_reviews for select
  using (approved = true);

-- anyone may post a review, but only a well-formed one, and it lands
-- UNAPPROVED. The `approved = false` check is the important line: without
-- it a stranger could post a review already marked approved and put it
-- straight on your site.
create policy "public insert"
  on photo_reviews for insert
  with check (
    approved = false
    and rating between 1 and 5
    and length(name) between 1 and 60
    and length(text) <= 1000
  );
```

There is deliberately **no update or delete policy**, so a visitor can post
but can never edit, approve, or erase anything — including their own.
Approving is something only you can do, from the dashboard.

Two things about this schema that are easy to get wrong, both hit and
fixed while wiring it up:

- The site must send `approved: false` explicitly rather than relying on
  the column default. An omitted column reads as `NULL` when the policy
  is checked, and `NULL = false` is not true, so the database refuses
  every honest review while the security rule itself works fine.
- The insert must **not** ask for the new row back
  (`Prefer: return=minimal`). Reading it back runs the *select* policy
  against a row that is not approved yet, which is denied — so a
  perfectly legal write fails with a security error.

### Approving a review

You will get an email the moment one arrives (`⭐ 5-star review from …
needs approval`). To publish it:

**Table Editor → photo_reviews →** tick the `approved` box on that row.
That is the whole job. It appears on the site immediately.

### If you would rather skip approval entirely

In `js/reviews-store.js` set `requireApproval: false`, and change the read
policy to `using (true)`. Reviews then appear the instant someone posts
one. Understand what that means: there is no login on a static site, so
anyone on the internet can put any text they like on your page, in front
of the parents and coaches reading it, with nothing between them and it.
Approving takes one tap. I would keep it on.

## 3. Copy your keys

**Project Settings → API**, and copy:

- **Project URL** — looks like `https://abcdefgh.supabase.co`
- **anon public** key — the long one labelled `anon` `public`

The anon key is designed to be public and safe to ship in a website. The
policies above are what actually limit it: read and insert only.

## 4. Paste them in

Open `js/reviews-store.js` and edit the top:

```js
window.REVIEW_BACKEND = {
  mode: "supabase",
  supabaseUrl: "https://abcdefgh.supabase.co",
  supabaseKey: "eyJhbGciOi...."
};
```

Then publish:

```sh
cd ~/photography-portfolio
git add -A && git commit -m "Turn on shared reviews" && git push
```

That's it. The review drawer on every photograph, the star counts, and the
"On individual photographs" block on the About page all start showing
everyone's reviews. No other code changes.

## Moderating

Open the `photo_reviews` table in Supabase and delete any row you don't
want. The site re-reads on the next page load.

---

# Turning on payments

Same idea — the booking panel already does the maths and collects the
order, it just doesn't charge yet.

1. Make a [Stripe](https://stripe.com) account and add your bank details.
2. Create a **Payment Link** for each package (Products → Payment Links).
3. Open `js/main.js`, find `var PAYMENT = {` near the top, and fill in:

```js
var PAYMENT = {
  enabled: true,
  currency: "USD",
  links: {
    "Individual":    "https://buy.stripe.com/...",
    "Team":          "https://buy.stripe.com/...",
    "Event & Meets": "https://buy.stripe.com/..."
  }
};
```

4. Commit and push.

The "Request this booking" button becomes "Continue to payment" and sends
people to Stripe's own checkout. Card details are handled entirely by
Stripe and never touch this site.

Because Payment Links are a fixed price each, the per-athlete total shown
in the panel is an estimate for the customer; confirm the final amount
with them, or make one link per common team size.

---

## The store

`store.html` sells the game photos at $1 each. Two things need switching on
before it can actually take an order — until then the page says so plainly
instead of pretending an order went through.

### 1. Orders — one click, straight to your inbox

Go to **web3forms.com**, type your email, and they mail you an access key.
No account, no dashboard, free. Then in `js/shop-backend.js`:

```js
orders: {
  mode: "web3forms",
  accessKey: "paste-your-key-here",
  endpoint: ""
}
```

That's it. When someone hits *Send order* the order posts in the background
and lands in your inbox — no mail app opens on their end, and they never
type your address. The same rails carry booking requests from the About
page, so both work the moment this key is in.

### 2. Chat — already on, nothing to do

The chat runs on **ntfy.sh**, which needs no account, no key and no
signup, so it works out of the box. Each order opens a topic named after
its room id — 18 random hex characters, unguessable. The order email
contains **your** link to that room; open it on any device and you are in
the chat as Garrett.

Two limits worth knowing:

- **Messages last about 12 hours.** A conversation does not survive to
  the next day. The order email is the permanent record; the chat is for
  finishing the sale now. If you want history that keeps, switch to
  Supabase below.
- **Anyone with the room link can read that room**, so treat the link
  like a key, and never type a customer's email or phone into the chat.

Messages arrive over a live stream, not by polling. That matters: ntfy's
free tier rate-limits requests per IP, and polling every few seconds
trips it (HTTP 429) — which would throttle a real buyer, not just
testing. One long-lived connection per open chat stays well clear, and
messages land instantly instead of up to three seconds late.

**Getting into a room from your phone:** the notification service sends
plain text, so the chat link in the email is often *not* tappable. That
is why every order email also carries a short **chat code**. Bookmark
**garrettphoto.store/chat** on your phone, type the code, and you are in.
The page remembers the last room you opened, so getting back in is one
tap.

**If order emails land in spam:** they will, at first — a notification
from an unfamiliar sender usually does. Open one, hit *Report not spam*,
then make it permanent: Gmail → search the sender's address → Create
filter → **Never send it to Spam**. Do this once. A missed order is a
lost sale, and this is the only thing that reliably prevents it. It is
also why the emails use one siren rather than a row of them: three
emoji plus an all-caps sender got the whole message filtered.

**If a buyer closes the chat:** they get back in two ways, neither of
which involves making an account. Their browser remembers the room, so
returning to the store shows a "Reopen chat" bar. And the receipt shows
a chat code they can type at garrettphoto.store/chat from any device.

**Why there are no customer accounts.** A real login needs a server
holding password hashes, and this site has no server — GitHub Pages only
hands out files. Any login built here would keep the password somewhere
readable, and people reuse passwords, so it would be worse than having
none. It also would not help: chat messages expire in ~12 hours either
way, so logging in later would just show an empty room. **If a buyer has
gone quiet, reply to their email** — it is in every order notification,
it never expires, and it is the one channel that always reaches them.

**Notifications:** the chat itself cannot notify you — no website can
push to your phone without an installed app. So the first time a customer
writes in a room, the site emails you (`💬 CHAT — …`) using the same
Web3Forms key. Once per room, so a chatty buyer can't flood you. Your
inbox stays the thing you actually have to watch.

### Optional: Supabase, if you want chat history that keeps

In the Supabase SQL editor:

```sql
create table shop_messages (
  id         bigserial primary key,
  room       text not null,
  who        text not null,
  body       text not null,
  created_at timestamptz default now()
);
alter table shop_messages enable row level security;
create policy "read"  on shop_messages for select using (true);
create policy "write" on shop_messages for insert with check (true);
create index on shop_messages (room, created_at);
```

Then in `js/shop-backend.js`:

```js
chat: { mode: "supabase", url: "https://xxxx.supabase.co", key: "your-anon-key" }
```

---

## Store previews — how the watermark actually holds up

The portfolio's watermark is a CSS overlay: nothing is burned into those
files, exactly as you wanted. **The store is different.** An overlay can be
deleted in devtools in five seconds, and it doesn't exist at all if someone
just opens the `.jpg` URL directly. So the store serves its own separate
files with the mark burned into the pixels:

```bash
python3 tools/build_shop_previews.py
```

That writes `images/shop/`. Your originals in `images/` are never touched.
Run it again after adding photos to a game (it skips ones already built;
`--force` rebuilds everything).

What makes these hard for an AI to strip:

- **It covers the whole frame.** Erasing a corner mark is easy. Rebuilding
  every square inch of a photo is not — there's no clean area to copy from.
- **Every tile is jittered** in position, angle, size and opacity, seeded
  per file, so no two photos share a pattern. This matters more than it
  sounds: the classic attack on stock-photo watermarks is to average a
  bunch of images that share one identical mark and solve for it. There's
  nothing here to solve for.
- **It's drawn light *and* dark.** A single-tone mark can be pulled out by
  thresholding in one direction; this one pushes pixels both ways.
- **It's blended, not stamped.** The original pixel values underneath are
  genuinely gone. Removal can't recover them, only invent replacements.
- **Previews are 1100px at quality 72,** so the mark and the photo share
  compression artifacts and can't be cleanly separated — and even a perfect
  removal leaves someone with a small file that's useless for printing.

**Honest limit:** none of this is 100%. A determined person with good tools
can degrade any watermark. The point is to make it more work than paying $1.

### Screenshots

**Screenshots cannot be blocked on the web.** No site can do it — browsers
don't expose that ability, and iOS Safari especially. Anyone claiming
otherwise is selling something. What the store *does* do:

- right-click → Save Image is blocked
- drag-to-desktop is blocked
- **iPhone long-press → Save to Photos is blocked** — the photo sits under a
  transparent shield and is set to ignore touches, so iOS never offers the
  save sheet
- and if someone screenshots anyway, what they get is the watermarked
  1100px preview, which is the whole reason the mark is burned in

The real protection isn't stopping the screenshot. It's that the screenshot
isn't worth having.
