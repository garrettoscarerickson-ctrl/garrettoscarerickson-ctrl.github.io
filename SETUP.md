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

### Optional: the "what you booked" subtitle

The Home page's review form has an optional "What you booked" field
(`Team session`, `portraits`…) that shows as a subtitle under the
reviewer's name. Storing it needs one extra column:

```sql
alter table photo_reviews add column if not exists role text default '';
```

This is genuinely optional. Without it the site notices the column is
missing and posts the review without the subtitle rather than losing
someone's writing over a line of small text.

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
"On individual photographs" block on the Home page all start showing
everyone's reviews. No other code changes.

## Moderating

Open the `photo_reviews` table in Supabase and delete any row you don't
want. The site re-reads on the next page load.

---

# Quote and removal requests

Two things on the site email you: a **quote request** from the Get a
quote form on the Home page, and a **removal request** from the button
under any photograph in the portfolio. Both post in the background through
**Web3Forms**, so the visitor never opens a mail app or types your
address.

The key is already set in `js/mailer.js`. To change it, go to
**web3forms.com**, type your email, and they mail you a new one:

```js
window.MAILER = {
  mode: "web3forms",
  accessKey: "paste-your-key-here",
  endpoint: ""
};
```

There are no prices on the site. A quote request carries what they are
booking, the sport, team, number of athletes, date, location and their
notes; you reply with a price, and take payment however you like (the
contact card at `/card` has Venmo). The Bookings tab in Studio uses the
same booking types, so a request copies straight across.

**If these emails land in spam:** they will, at first. Open one, hit
*Report not spam*, then make it permanent: Gmail → search the sender's
address → Create filter → **Never send it to Spam**. It is also why the
subject line uses one emoji rather than a row of them: three emoji plus
an all-caps sender got the whole message filtered.

---

# My Photos — the page for past buyers

The site used to sell single game photographs. The store is gone, but
`account.html` is still up (not in the menu) so anyone who bought before
can sign in and download their files. It needs the Supabase `download`
Edge Function and the R2 bucket to keep working.

When past buyers have what they need:

1. Delete `account.html`, `js/account.js`, `js/account-page.js` and
   `css/account.css`, and the short sign-in redirect at the bottom of
   `js/main.js` (marked "Delete this along with account.html").
2. In Supabase, delete the `download` Edge Function, and the `deliveries`
   and `orders` tables once you have exported anything you want to keep.
3. In Cloudflare, delete the `garrettphoto` R2 bucket.

Already safe to switch off now, because nothing on the site uses them:
the Stripe payment links and webhook, and the Supabase `rapid-function`
(checkout) and `stripe-webhook` Edge Functions.
