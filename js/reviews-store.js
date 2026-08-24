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
  mode: "local",
  supabaseUrl: "",
  supabaseKey: ""
};

window.ReviewStore = (function () {
  "use strict";

  var KEY = "ge.photoreviews.v1";
  var cfg = window.REVIEW_BACKEND;
  var memo = null;           /* cache of the shared fetch */

  function isShared() {
    return cfg.mode === "supabase" && cfg.supabaseUrl && cfg.supabaseKey;
  }

  function rest(path, opts) {
    opts = opts || {};
    return fetch(cfg.supabaseUrl.replace(/\/$/, "") + "/rest/v1/" + path, {
      method: opts.method || "GET",
      headers: {
        "apikey": cfg.supabaseKey,
        "Authorization": "Bearer " + cfg.supabaseKey,
        "Content-Type": "application/json",
        "Prefer": "return=representation"
      },
      body: opts.body ? JSON.stringify(opts.body) : undefined
    }).then(function (r) {
      if (!r.ok) throw new Error("Review service error " + r.status);
      return r.status === 204 ? null : r.json();
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
    memo = rest("photo_reviews?select=*&order=created_at.desc")
      .catch(function () { return []; });
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
      photo: row.photo, name: row.name, rating: row.rating, text: row.text
    }}).then(function (res) {
      memo = null;                       /* force a refetch next read */
      return (res && res[0]) || row;
    });
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
