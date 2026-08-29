// Stripe calls this when a payment completes.
//
// It is the only place that may mark an order paid, because it is the
// only place that can verify Stripe actually sent the message. A page
// cannot: anything the browser knows, a buyer can forge, so "payment
// succeeded" arriving from the front end means nothing.
//
// It also emails the buyer their photographs. That matters more than it
// sounds — without it the only way to collect files is to sign in, and
// every extra step between paying and receiving is somewhere a sale
// quietly fails. The account page stays as the permanent copy.

import Stripe from "https://esm.sh/stripe@14.21.0?target=deno";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";
import { AwsClient } from "https://esm.sh/aws4fetch@1.0.20";

// Built on first use, not at module load. A missing secret in a
// top-level constructor kills the whole worker before it can run a line
// of handler code — the request then fails with an opaque 500 and no
// hint as to which secret is absent. Lazily, the same problem produces a
// message that names it.
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

let _r2: AwsClient | null = null;
function r2Client() {
  const id = Deno.env.get("R2_ACCESS_KEY_ID");
  const secret = Deno.env.get("R2_SECRET_ACCESS_KEY");
  if (!id || !secret) throw new Error("R2 credentials are not set");
  if (!_r2) {
    _r2 = new AwsClient({
      accessKeyId: id,
      secretAccessKey: secret,
      service: "s3",
      region: "auto",
    });
  }
  return _r2;
}

const ENDPOINT = `https://${Deno.env.get("R2_ACCOUNT_ID")}.r2.cloudflarestorage.com`;
const BUCKET = Deno.env.get("R2_BUCKET") || "garrettphoto";

// Seven days is the longest a signed URL can live. Long enough that a
// buyer who opens the email next weekend is fine; short enough that a
// forwarded link stops working. The account page is the answer after
// that, where a fresh link is minted on every visit.
const EMAIL_TTL = 604800;

async function signed(key: string, title: string) {
  const u = new URL(`${ENDPOINT}/${BUCKET}/${key}`);
  u.searchParams.set("X-Amz-Expires", String(EMAIL_TTL));
  u.searchParams.set(
    "response-content-disposition",
    `attachment; filename="${title.replace(/[^\w \-]/g, "")}.jpg"`,
  );
  const req = await r2Client().sign(new Request(u, { method: "GET" }),
                            { aws: { signQuery: true } });
  return req.url;
}

async function sendEmail(
  to: string,
  name: string,
  links: Array<{ title: string; url: string; key: string }>,
) {
  const apiKey = Deno.env.get("RESEND_API_KEY");
  const from = Deno.env.get("RESEND_FROM") || "onboarding@resend.dev";
  if (!apiKey) {
    console.error("no RESEND_API_KEY — files are on the account page only");
    return;
  }

  const btn = "display:inline-block;background:#111114;color:#ffffff;" +
    "text-decoration:none;padding:12px 22px;border-radius:999px;" +
    "font-weight:700;font-size:13px;letter-spacing:.08em;" +
    "text-transform:uppercase;font-family:Helvetica,Arial,sans-serif";

  /* Tables, not flexbox — Outlook renders almost no modern CSS, and an
     email that collapses there is an email the buyer thinks is broken.
     The thumbnail is the watermarked store preview, which is already
     public; a signed link would expire and leave a broken image. */
  const rows = links.map((l) => `
    <tr>
      <td width="88" style="padding:10px 14px 10px 0;vertical-align:middle">
        <img src="https://garrettphoto.store/images/shop/${l.key}"
             width="72" height="72" alt=""
             style="width:72px;height:72px;object-fit:cover;border-radius:8px;
                    display:block;border:1px solid #e5e5e5">
      </td>
      <td style="padding:10px 0;vertical-align:middle;font-family:Helvetica,Arial,sans-serif">
        <div style="font-size:15px;font-weight:700;color:#111114;padding-bottom:8px">
          ${l.title}
        </div>
        <a href="${l.url}" style="${btn}">Click here to download</a>
      </td>
    </tr>`).join("");

  const html = `
  <div style="background:#f6f6f4;padding:28px 12px;font-family:Helvetica,Arial,sans-serif">
    <div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:14px;
                padding:30px 28px;color:#111114">

      <div style="font-size:11px;letter-spacing:.28em;text-transform:uppercase;
                  color:#7a7a84;padding-bottom:14px">Garrett Erickson</div>

      <h1 style="margin:0 0 8px;font-size:26px;line-height:1.2">
        Your photographs${name ? ", " + name.split(" ")[0] : ""}
      </h1>
      <p style="margin:0 0 22px;font-size:15px;line-height:1.6;color:#3a3a42">
        Thanks for your order. ${links.length === 1
          ? "Here's your photograph"
          : `Here are your ${links.length} photographs`} — full resolution,
        no watermark.
      </p>

      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
        ${rows}
      </table>

      <div style="border-top:1px solid #e5e5e5;margin-top:24px;padding-top:20px">
        <a href="https://garrettphoto.store/account.html" style="${btn}">
          Get them any time
        </a>
        <p style="margin:14px 0 0;font-size:13px;line-height:1.6;color:#6a6a72">
          The download buttons above work for 7 days. After that, sign in at
          <a href="https://garrettphoto.store/account.html"
             style="color:#111114">garrettphoto.store</a>
          with this email address and they'll be waiting — permanently.
        </p>
        <p style="margin:12px 0 0;font-size:13px;line-height:1.6;color:#6a6a72">
          Personal use only. Please ask before using them commercially.
        </p>
        <p style="margin:16px 0 0;font-size:13px;color:#6a6a72">— Garrett</p>
      </div>
    </div>
  </div>`;

  const r = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: `Garrett Erickson <${from}>`,
      to: [to],
      subject: links.length === 1
        ? "Your photograph is ready to download"
        : `Your ${links.length} photographs are ready to download`,
      html,
    }),
  });
  if (!r.ok) console.error("resend failed:", r.status, await r.text());
}

Deno.serve(async (req) => {
  // GET reports which secrets are present, so a misconfiguration is
  // findable without reading worker logs.
  if (req.method === "GET") {
    return new Response(JSON.stringify({
      ok: true,
      stripe_key: !!Deno.env.get("STRIPE_SECRET_KEY"),
      stripe_webhook_secret: !!Deno.env.get("STRIPE_WEBHOOK_SECRET"),
      r2: !!Deno.env.get("R2_ACCESS_KEY_ID") && !!Deno.env.get("R2_SECRET_ACCESS_KEY"),
      r2_account: !!Deno.env.get("R2_ACCOUNT_ID"),
      resend: !!Deno.env.get("RESEND_API_KEY"),
    }), { status: 200, headers: { "Content-Type": "application/json" } });
  }

  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const sig = req.headers.get("stripe-signature");
  const body = await req.text();

  // Without this check anyone who finds the URL could POST a fake
  // "paid" event and hand themselves the photographs for free.
  let event: Stripe.Event;
  try {
    event = await stripeClient().webhooks.constructEventAsync(
      body,
      sig!,
      Deno.env.get("STRIPE_WEBHOOK_SECRET")!,
      undefined,
      Stripe.createSubtleCryptoProvider(),
    );
  } catch (err) {
    if (String(err.message).includes("is not set")) {
      console.error(err.message);
      return new Response(err.message, { status: 503 });
    }
    console.error("bad signature:", err.message);
    return new Response("Invalid signature", { status: 400 });
  }

  if (event.type !== "checkout.session.completed") {
    return new Response(JSON.stringify({ ignored: event.type }), { status: 200 });
  }

  const session = event.data.object as Stripe.Checkout.Session;
  const code = session.client_reference_id;
  const paidEmail = (session.customer_details?.email ||
                     session.customer_email || "").toLowerCase();

  if (!code) {
    console.error("no client_reference_id on session", session.id);
    return new Response("ok", { status: 200 });
  }

  const { data: order, error } = await adminClient()
    .from("orders").select("*").eq("code", code).maybeSingle();

  if (error || !order) {
    console.error("no order for code", code, error?.message);
    return new Response("ok", { status: 200 });
  }

  // Stripe retries a webhook it thinks failed, so this can arrive more
  // than once. Bailing on an already-paid order stops a retry creating
  // a second set of deliveries and a second email.
  if (order.paid) {
    return new Response(JSON.stringify({ already: true }), { status: 200 });
  }

  await adminClient().from("orders").update({
    paid: true,
    paid_at: new Date().toISOString(),
    stripe_session: session.id,
  }).eq("code", code);

  const items = (order.items || []) as Array<{ src: string; title: string; game: string }>;
  const to = paidEmail || (order.email || "").toLowerCase();

  // The row stores the object KEY, not a URL. A stored link would expire
  // and leave a dead download months later, which is the exact failure
  // this feature exists to prevent; the account page mints a fresh one
  // on every visit instead.
  const rows = items.map((it) => ({
    email: to,
    title: it.title,
    note: it.game,
    url: null,
    object_key: it.src.split("/").pop(),
    order_code: code,
  }));

  if (rows.length) {
    const { error: insErr } = await adminClient().from("deliveries").insert(rows);
    if (insErr) console.error("delivery insert failed:", insErr.message);
  }

  // Email last, and never let a failure here fail the webhook — the
  // payment is real and the files are already on the account page. A
  // non-200 would make Stripe retry and double everything.
  try {
    const links = [];
    for (const it of items) {
      const key = it.src.split("/").pop()!;
      links.push({ title: it.title, url: await signed(key, it.title), key: key });
    }
    if (links.length && to) await sendEmail(to, order.name || "", links);
  } catch (e) {
    console.error("email step failed:", e.message);
  }

  return new Response(JSON.stringify({ ok: true, delivered: rows.length }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
});
