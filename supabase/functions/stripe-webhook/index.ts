// Stripe calls this when a payment completes.
//
// It is the only place that may mark an order paid, because it is the
// only place that can verify Stripe actually sent the message. A page
// cannot: anything the browser knows, a buyer can forge, so "payment
// succeeded" arriving from the front end means nothing.
//
// Deploy from the dashboard (see ../_SETUP.md). Secrets live in Supabase,
// never in js/.

import Stripe from "https://esm.sh/stripe@14.21.0?target=deno";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY")!, {
  apiVersion: "2024-06-20",
  httpClient: Stripe.createFetchHttpClient(),
});

const admin = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const sig = req.headers.get("stripe-signature");
  const body = await req.text();

  // Without this check anyone who finds the URL could POST a fake
  // "paid" event and hand themselves the photographs for free. The
  // signature is what makes this endpoint safe to expose publicly.
  let event: Stripe.Event;
  try {
    event = await stripe.webhooks.constructEventAsync(
      body,
      sig!,
      Deno.env.get("STRIPE_WEBHOOK_SECRET")!,
      undefined,
      Stripe.createSubtleCryptoProvider(),
    );
  } catch (err) {
    console.error("bad signature:", err.message);
    return new Response("Invalid signature", { status: 400 });
  }

  if (event.type !== "checkout.session.completed") {
    return new Response(JSON.stringify({ ignored: event.type }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  const session = event.data.object as Stripe.Checkout.Session;
  const code = session.client_reference_id;
  const email = (session.customer_details?.email ||
                 session.customer_email || "").toLowerCase();

  if (!code) {
    console.error("no client_reference_id on session", session.id);
    return new Response("ok", { status: 200 });   // don't make Stripe retry
  }

  const { data: order, error } = await admin
    .from("orders")
    .select("*")
    .eq("code", code)
    .maybeSingle();

  if (error || !order) {
    console.error("no order for code", code, error?.message);
    return new Response("ok", { status: 200 });
  }

  // Stripe retries a webhook it thinks failed, so this can arrive more
  // than once for the same payment. Bailing on an already-paid order
  // keeps a retry from creating a second set of deliveries.
  if (order.paid) {
    return new Response(JSON.stringify({ already: true }), { status: 200 });
  }

  await admin.from("orders")
    .update({
      paid: true,
      paid_at: new Date().toISOString(),
      stripe_session: session.id,
    })
    .eq("code", code);

  // One delivery row per photograph. The row stores the object KEY, not
  // a URL: links expire, so the account page mints a fresh one on every
  // visit through the `download` function. That is what makes a bookmark
  // from six months from now still work.
  const items = (order.items || []) as Array<{ src: string; title: string; game: string }>;
  const to = email || (order.email || "").toLowerCase();

  const rows = items.map((it) => ({
    email: to,
    title: it.title,
    note: it.game,
    url: null,
    object_key: it.src.split("/").pop(),
    order_code: code,
  }));

  if (rows.length) {
    const { error: insErr } = await admin.from("deliveries").insert(rows);
    if (insErr) console.error("delivery insert failed:", insErr.message);
  }

  return new Response(JSON.stringify({ ok: true, delivered: rows.length }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
});
