-- Orders and deliveries. Run this in the Supabase SQL editor.
--
-- An order is written by the store when the buyer sends it, BEFORE any
-- payment. It is `paid` only by the Stripe webhook, which is the one
-- place that can verify Stripe really sent the message — a page cannot,
-- because anything the browser knows a buyer can forge.

create table if not exists orders (
  code           text primary key,
  email          text not null,
  name           text,
  items          jsonb not null default '[]'::jsonb,
  total          numeric not null default 0,
  paid           boolean not null default false,
  paid_at        timestamptz,
  stripe_session text,
  created_at     timestamptz not null default now()
);

alter table orders enable row level security;

-- Anyone may create an order (that is just "I would like these"), but
-- nobody browsing the site may read, edit or mark one paid. Only the
-- Edge Function, which holds the service key, can do that.
create policy "public insert order"
  on orders for insert
  with check (paid = false);

create index if not exists orders_email_idx on orders (lower(email));


-- Deliveries. If you already made this table, the three added columns
-- are what the R2 flow needs; the rest is unchanged.
create table if not exists deliveries (
  id          bigint generated always as identity primary key,
  email       text not null,
  title       text not null,
  note        text default '',
  url         text,
  created_at  timestamptz not null default now()
);

alter table deliveries add column if not exists object_key text;
alter table deliveries add column if not exists order_code text;

alter table deliveries enable row level security;

drop policy if exists "read own deliveries" on deliveries;
create policy "read own deliveries"
  on deliveries for select
  using (lower(email) = lower(auth.jwt() ->> 'email'));

create index if not exists deliveries_email_idx on deliveries (lower(email));
