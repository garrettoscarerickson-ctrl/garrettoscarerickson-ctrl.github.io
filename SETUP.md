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
  created_at  timestamptz not null default now()
);

alter table photo_reviews enable row level security;

-- anyone may read reviews
create policy "public read"
  on photo_reviews for select
  using (true);

-- anyone may post a review, but only a well-formed one
create policy "public insert"
  on photo_reviews for insert
  with check (
    rating between 1 and 5
    and length(name) between 1 and 60
    and length(text) <= 1000
  );
```

Note there is deliberately **no update or delete policy**, so visitors can
post but can never edit or erase anyone's reviews. You can always remove
one yourself from the Supabase table editor.

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
