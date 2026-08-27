/* ============================================================
   REVIEW STORE
   One small API the site talks to, with two backends behind it.

   mode "local"    — reviews live in the visitor's own browser. Works
                     with zero setup, but each person only sees their own.
   mode "supabase" — reviews live in a shared database, so EVERYONE on
                     the site sees every review. Free tier is plenty.

   To switch the whole site to shared reviews:
     1. Make a free project at supabase.com
     2. SQL editor -> run the schema in SETUP.md
     3. Settings -> API: copy the Project URL and the anon public key
     4. Paste them below and set mode to "supabase"
   Nothing else changes — the UI already reads from this API.
   The anon key is meant to be public; row-level security decides what
   it may do, which the schema in SETUP.md pins to read + insert only.
   ============================================================ */

window.REVIEW_BACKEND = {
  mode: "supabase",
  supabaseUrl: "https://wtvoftdnoptgxwbnzbzq.supabase.co",
  supabaseKey: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0dm9mdGRub3B0Z3h3Ym56YnpxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc3OTUwMjAsImV4cCI6MjEwMzM3MTAyMH0.32Wl8vMG-HM7J-TJbIAPVhL1sDYIWxNlPUE3mfNc-wA",

  /* Reviews are public and anyone can post one — there is no login on a
     static site, so there is nothing stopping a stranger putting
     anything they like on Garrett's page in front of the parents who
     read it. With this on, a new review is stored but stays hidden until
     Garrett approves it in the Supabase dashboard, and he gets an email
     the moment one arrives. Set it to false for instant publishing. */
  requireApproval: true
};

window.ReviewStore = (function () {
  "use strict";

  var KEY = "ge.photoreviews.v1";
  var cfg = window.REVIEW_BACKEND;
  var memo = null;           /* cache of the shared fetch */

  function isShared() {
    return !!(cfg.mode === "supabase" && cfg.supabaseUrl && cfg.supabaseKey);
  }

  function rest(path, opts) {
    opts = opts || {};
    return fetch(cfg.supabaseUrl.replace(/\/$/, "") + "/rest/v1/" + path, {
      method: opts.method || "GET",
      headers: {
        "apikey": cfg.supabaseKey,
        "Authorization": "Bearer " + cfg.supabaseKey,
        "Content-Type": "application/json",
        "Prefer": opts.prefer || "return=representation"
      },
      body: opts.body ? JSON.stringify(opts.body) : undefined
    }).then(function (r) {
      if (!r.ok) throw new Error("Review service error " + r.status);
      if (r.status === 204) return null;
      return r.text().then(function (t) {
        return t ? JSON.parse(t) : null;
      });
    });
  }

  function localAll() {
    try { return JSON.parse(localStorage.getItem(KEY)) || []; }
    catch (e) { return []; }
  }

  function localSave(rows) {
    try { localStorage.setItem(KEY, JSON.stringify(rows)); } catch (e) {}
  }

  /* every review, newest first */
  function all(force) {
    if (!isShared()) return Promise.resolve(localAll());
    if (memo && !force) return memo;
    var q = "photo_reviews?select=*&order=created_at.desc";
    if (cfg.requireApproval) q += "&approved=eq.true";
    memo = rest(q).catch(function () { return []; });
    return memo;
  }

  function forPhoto(src) {
    return all().then(function (rows) {
      return rows.filter(function (r) { return r.photo === src; });
    });
  }

  function add(review) {
    var row = {
      photo: review.photo,
      name: review.name,
      rating: review.rating,
      text: review.text || "",
      created_at: new Date().toISOString()
    };
    if (!isShared()) {
      var rows = localAll();
      rows.unshift(row);
      localSave(rows);
      return Promise.resolve(row);
    }
    return rest("photo_reviews", { method: "POST", body: {
      photo: row.photo, name: row.name, rating: row.rating, text: row.text,
      /* Sent explicitly rather than left to the column default. The
         insert policy checks `approved = false`, and an omitted column
         reads as NULL at check time — NULL = false is not true, so the
         database refused every honest review while still (correctly)
         refusing hostile ones. Stating it fails closed either way: a
         client that sends true is rejected by the same policy. */
      approved: false
    },
      /* Do NOT ask for the row back. Reading it would run the select
         policy against a row that is not approved yet, which is denied —
         so the whole insert failed with an RLS error even though the
         write itself was perfectly legal. */
      prefer: "return=minimal"
    }).then(function (res) {
      memo = null;                       /* force a refetch next read */
      notify(row);
      return (res && res[0]) || row;
    });
  }

  /* A held review is invisible until approved, so Garrett needs telling
     it exists. Reuses the order email that is already working — a
     failure here must never break leaving a review, so it is swallowed. */
  function notify(row) {
    if (!window.Shop || !Shop.ordersReady()) return;
    var held = cfg.requireApproval;
    Shop.sendOrder({
      subject: "\u2B50 " + row.rating + "-star review from " +
               (row.name || "someone") + (held ? " — needs approval" : ""),
      fromName: "Garrett Photo Reviews",
      summary: held
        ? "A new review is waiting for approval. It is not on the site yet."
        : "A new review just went live on the site.",
      lines: [
        ["Rating", row.rating + " / 5"],
        ["From", row.name || "(no name)"],
        ["Photo", row.photo],
        ["Review", row.text || "(no text)"]
      ],
      name: row.name || "Reviewer",
      email: "(no reply address — reviews are anonymous)",
      total: 0
    }).catch(function () {});
  }

  /* { src: {avg, count} } for every photo that has reviews */
  function summary() {
    return all().then(function (rows) {
      var by = {};
      rows.forEach(function (r) {
        var s = by[r.photo] || (by[r.photo] = { total: 0, count: 0 });
        s.total += r.rating;
        s.count += 1;
      });
      Object.keys(by).forEach(function (k) {
        by[k].avg = by[k].total / by[k].count;
      });
      return by;
    });
  }

  return {
    isShared: isShared,
    all: all,
    forPhoto: forPhoto,
    add: add,
    summary: summary
  };
})();
