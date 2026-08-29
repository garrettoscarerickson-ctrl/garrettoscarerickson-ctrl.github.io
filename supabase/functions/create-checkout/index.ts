// Creates a Stripe Checkout session for one order.
//
// Payment Links cannot do this. They charge quantity x fixed price, and
// Stripe's fee is 2.9% + a flat 30c — so the fee is a third of a $1 sale
// and 6% of a $10 one. Any fixed markup either overcharges large orders
// or undercharges small ones. Computing it here charges the exact amount.
//
// The amount is calculated from the ORDER ROW, never from the request.
// A browser that could name its own price would be a browser that could
// buy 50 photographs for a cent.

import Stripe from "https://esm.sh/stripe@14.21.0?target=deno";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

// Built on first use. A missing secret in a top-level constructor kills
// the worker before any handler code runs, and the caller gets an opaque
// 500 with no hint which secret is absent.
let _stripe: Stripe | null = null;
function stripeClient() {
  const key = Deno.env.get("STRIPE_SECRET_KEY");
  if (!key) throw new Error("STRIPE_SECRET_KEY is not set");
  if (!_stripe) {
    _stripe = new Stripe(key, {
      apiVersion: "2024-06-20",
      httpClient: Stripe.createFetchHttpClient(),
    });
  }
  return _stripe;
}

let _admin: ReturnType<typeof createClient> | null = null;
function adminClient() {
  if (!_admin) {
    _admin = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );
  }
  return _admin;
}

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, content-type, apikey",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });
}

// Stripe's published rate, kept here rather than in the page so it can be
// corrected in one place.
const PCT = 0.029;
const FLAT = 30;   // cents

/** What the buyer pays so the seller nets `netCents` after Stripe. */
function grossFor(netCents: number) {
  // net = gross - (gross * PCT + FLAT)  =>  gross = (net + FLAT) / (1 - PCT)
  return Math.ceil((netCents + FLAT) / (1 - PCT));
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  // Check the maths without spending anything.
  if (req.method === "GET") {
    const n = Number(new URL(req.url).searchParams.get("net") || 100);
    const gross = grossFor(n);
    return json({
      net: n / 100,
      gross: gross / 100,
      fee: (gross - n) / 100,
      stripe_takes: (Math.round(gross * PCT) + FLAT) / 100,
      stripe_key: !!Deno.env.get("STRIPE_SECRET_KEY"),
    });
  }

  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);

  let code = "";
  try {
    ({ code } = await req.json());
  } catch {
    return json({ error: "Bad request" }, 400);
  }
  if (!code) return json({ error: "Which order?" }, 400);

  const { data: order, error: readErr } = await adminClient()
    .from("orders").select("*").eq("code", code).maybeSingle();

  if (readErr) {
    console.error("order read failed:", readErr.message);
    return json({ error: "Could not read the order", detail: readErr.message }, 502);
  }
  if (!order) return json({ error: "Order not found" }, 404);
  if (order.paid) return json({ error: "That order is already paid" }, 409);

  const items = (order.items || []) as Array<{ title: string }>;
  if (!items.length) return json({ error: "Nothing in that order" }, 400);

  const netCents = Math.round(Number(order.total) * 100);
  const grossCents = grossFor(netCents);
  const feeCents = grossCents - netCents;

  const origin = req.headers.get("origin") || "https://garrettphoto.store";

  // Two line items so the buyer sees exactly what the fee is, rather than
  // a total that does not match the price they were shown.
  let session;
  try {
    session = await stripeClient().checkout.sessions.create({
      mode: "payment",
      client_reference_id: code,
      customer_email: order.email || undefined,
      line_items: [
        {
          quantity: 1,
          price_data: {
            currency: "usd",
            unit_amount: netCents,
            product_data: {
              name: `${items.length} photograph${items.length === 1 ? "" : "s"}`,
              description: items.map((i) => i.title).join(", ").slice(0, 250),
            },
          },
        },
        {
          quantity: 1,
          price_data: {
            currency: "usd",
            unit_amount: feeCents,
            product_data: { name: "Card processing fee" },
          },
        },
      ],
      success_url: `${origin}/account.html?paid=${code}`,
      cancel_url: `${origin}/store.html`,
    });
  } catch (err) {
    // Say what Stripe actually objected to. A bare 500 sends someone
    // hunting through five settings for a fault the error already names.
    console.error("stripe session failed:", err);
    return json({
      error: "Stripe refused to create the checkout",
      detail: String((err && (err as Error).message) || err),
    }, 502);
  }

  const { error: upErr } = await adminClient().from("orders")
    .update({ fee: feeCents / 100, gross: grossCents / 100 })
    .eq("code", code);
  if (upErr) console.error("could not record fee:", upErr.message);

  return json({ url: session.url, gross: grossCents / 100, fee: feeCents / 100 });
});
