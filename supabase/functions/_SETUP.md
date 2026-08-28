# Edge Functions — deploy from the Supabase dashboard

No CLI needed. For each function:

1. https://supabase.com/dashboard/project/wtvoftdnoptgxwbnzbzq/functions
2. **Deploy a new function → Via Editor**
3. Name it exactly as the folder here (`stripe-webhook`, `download`)
4. Paste the contents of that folder's `index.ts`
5. Deploy

## Secrets they need

**Project Settings → Edge Functions → Secrets.** These live server-side
and are never in the page — which is the whole reason the functions
exist. Anything that can mint a download link or write a delivery row
has to run somewhere the public cannot read it.

| Secret | Where it comes from |
|---|---|
| `STRIPE_SECRET_KEY` | Stripe → Developers → API keys (`sk_live_…`) |
| `STRIPE_WEBHOOK_SECRET` | Stripe → Webhooks → your endpoint (`whsec_…`) |
| `R2_ACCOUNT_ID` | same as .env.local |
| `R2_BUCKET` | `garrettphoto` |
| `R2_ACCESS_KEY_ID` | same as .env.local |
| `R2_SECRET_ACCESS_KEY` | same as .env.local |

`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are injected automatically
by Supabase — do not add them yourself.

## Point Stripe at the webhook

Stripe → Developers → Webhooks → Add endpoint:

```
https://wtvoftdnoptgxwbnzbzq.supabase.co/functions/v1/stripe-webhook
```

Listen for **`checkout.session.completed`** only. Copy the signing secret
it gives you into `STRIPE_WEBHOOK_SECRET`.
