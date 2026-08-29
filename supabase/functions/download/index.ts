// Mints a short-lived download link for one photograph a buyer owns.
//
// The bucket is private and nothing in it is ever public. A buyer's
// account page calls this per file, and it answers only after checking
// that a delivery row exists for that signed-in email. The check runs
// here rather than in the page because a page cannot be trusted to say
// truthfully who is asking.
//
// Links are deliberately short-lived. They expire, but the account page
// asks for a new one every visit — so a bookmark from six months from
// now still works, and a link forwarded to a friend stops working
// within the hour.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";
import { AwsClient } from "https://esm.sh/aws4fetch@1.0.20";

const admin = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

const r2 = new AwsClient({
  accessKeyId: Deno.env.get("R2_ACCESS_KEY_ID")!,
  secretAccessKey: Deno.env.get("R2_SECRET_ACCESS_KEY")!,
  service: "s3",
  region: "auto",
});

const ENDPOINT = `https://${Deno.env.get("R2_ACCOUNT_ID")}.r2.cloudflarestorage.com`;
const BUCKET = Deno.env.get("R2_BUCKET") || "garrettphoto";
const TTL = 3600;   // one hour

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

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);

  // Who is asking? Their access token proves it; the request body does
  // not, so the email is taken from the verified token and never from
  // anything the caller sent.
  const auth = req.headers.get("Authorization") || "";
  const token = auth.replace(/^Bearer\s+/i, "");
  if (!token) return json({ error: "Not signed in" }, 401);

  const { data: userData, error: userErr } = await admin.auth.getUser(token);
  if (userErr || !userData?.user?.email) {
    return json({ error: "Not signed in" }, 401);
  }
  const email = userData.user.email.toLowerCase();

  let id: number | null = null;
  let inline = false;
  try {
    ({ id, inline } = await req.json());
  } catch {
    return json({ error: "Bad request" }, 400);
  }
  if (!id) return json({ error: "Which delivery?" }, 400);

  // The row must belong to this email. Asking for someone else's id
  // returns the same "not found" as an id that does not exist, so the
  // response cannot be used to probe what other people bought.
  const { data: row } = await admin
    .from("deliveries")
    .select("id, email, title, object_key, url")
    .eq("id", id)
    .maybeSingle();

  if (!row || (row.email || "").toLowerCase() !== email) {
    return json({ error: "Not found" }, 404);
  }

  // A row may carry a plain URL instead (e.g. a Drive folder from before
  // R2). Hand that back untouched rather than trying to sign it.
  if (row.url) return json({ url: row.url });
  if (!row.object_key) return json({ error: "Not ready yet" }, 409);

  const target = new URL(`${ENDPOINT}/${BUCKET}/${row.object_key}`);
  target.searchParams.set("X-Amz-Expires", String(TTL));
  /* `attachment` forces a download, which on a phone lands in Files —
     not the camera roll, which is where someone who just bought a photo
     of their kid expects it. Served inline the image simply opens, and a
     long press offers "Add to Photos". Desktop keeps the download, where
     a file in the Downloads folder is what people want. */
  const filename = `${row.title.replace(/[^\w \-]/g, "")}.jpg`;
  target.searchParams.set(
    "response-content-disposition",
    `${inline ? "inline" : "attachment"}; filename="${filename}"`,
  );

  const signed = await r2.sign(
    new Request(target, { method: "GET" }),
    { aws: { signQuery: true } },
  );

  return json({ url: signed.url, expires_in: TTL });
});
