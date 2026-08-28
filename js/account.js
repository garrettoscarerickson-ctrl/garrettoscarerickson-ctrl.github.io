/* ============================================================
   ACCOUNTS
   So a buyer can always get their files back.

   Passwordless on purpose. Supabase emails a one-time link; clicking it
   signs them in. Nothing here ever sees, stores, or transmits a
   password, which matters because people reuse them and a static site
   has nowhere safe to keep one.

   It also solves a problem the store had on its own: Web3Forms only
   emails Garrett, never the customer, so there was no way to reach a
   buyer after the sale. Supabase Auth can email them, so the sign-in
   link doubles as the channel that reaches them.

   Two tokens come back from a sign-in. The access token is a JWT that
   expires in about an hour and is what the database checks; the refresh
   token buys a new one. Both live in localStorage, so a buyer stays
   signed in on that device and only needs the email again on a new one.
   ============================================================ */

window.Account = (function () {
  "use strict";

  var KEY = "ge.session.v1";
  var listeners = [];

  function cfg() { return window.REVIEW_BACKEND || {}; }

  function ready() {
    return !!(cfg().mode === "supabase" && cfg().supabaseUrl && cfg().supabaseKey);
  }

  function base() { return cfg().supabaseUrl.replace(/\/$/, ""); }

  /* ---------- session ---------- */

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || "null"); }
    catch (e) { return null; }
  }

  function save(s) {
    try {
      if (s) localStorage.setItem(KEY, JSON.stringify(s));
      else localStorage.removeItem(KEY);
    } catch (e) {}
    listeners.forEach(function (fn) { try { fn(user()); } catch (e) {} });
  }

  var session = load();

  function user() {
    return session && session.user ? session.user : null;
  }

  function email() {
    var u = user();
    return u ? u.email : null;
  }

  function onChange(fn) {
    listeners.push(fn);
    return function () {
      listeners = listeners.filter(function (f) { return f !== fn; });
    };
  }

  /* A token that expires mid-request reads to the buyer as "my files
     vanished", so refresh a minute early rather than on the boundary. */
  function fresh() {
    if (!session) return Promise.resolve(null);
    if (session.expires_at && Date.now() < session.expires_at - 60000) {
      return Promise.resolve(session.access_token);
    }
    if (!session.refresh_token) { save(null); return Promise.resolve(null); }
    return fetch(base() + "/auth/v1/token?grant_type=refresh_token", {
      method: "POST",
      headers: { "apikey": cfg().supabaseKey, "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: session.refresh_token })
    }).then(function (r) {
      if (!r.ok) throw new Error("session expired");
      return r.json();
    }).then(function (j) {
      session = shape(j);
      save(session);
      return session.access_token;
    }).catch(function () {
      /* refresh failed for good — sign out rather than leaving them in a
         half-signed-in state where nothing loads and nothing explains why */
      session = null; save(null);
      return null;
    });
  }

  function shape(j) {
    return {
      access_token: j.access_token,
      refresh_token: j.refresh_token,
      expires_at: Date.now() + ((j.expires_in || 3600) * 1000),
      user: j.user || (session && session.user) || null
    };
  }

  /* ---------- signing in ---------- */

  /* Sends the one-time link. `shouldCreateUser` stays on so a first-time
     buyer does not have to "register" before they can buy. */
  function signIn(addr, redirectTo) {
    if (!ready()) return Promise.reject(new Error("Accounts aren't switched on yet."));
    return fetch(base() + "/auth/v1/otp", {
      method: "POST",
      headers: { "apikey": cfg().supabaseKey, "Content-Type": "application/json" },
      body: JSON.stringify({
        email: addr,
        create_user: true,
        options: { email_redirect_to: redirectTo || (location.origin + "/account.html") }
      })
    }).then(function (r) {
      if (r.ok) return true;
      return r.json().catch(function () { return {}; }).then(function (j) {
        throw new Error(j.msg || j.error_description || j.message ||
                        ("Sign-in service returned " + r.status));
      });
    });
  }

  function signOut() {
    var t = session && session.access_token;
    session = null; save(null);
    if (t && ready()) {
      fetch(base() + "/auth/v1/logout", {
        method: "POST",
        headers: { "apikey": cfg().supabaseKey, "Authorization": "Bearer " + t }
      }).catch(function () {});
    }
  }

  /* The link lands back on the site with the tokens in the URL fragment.
     Read them, then strip the fragment — a URL carrying a live token is
     one screenshot or shared link away from being someone else's. */
  function absorbRedirect() {
    if (!location.hash || location.hash.indexOf("access_token") === -1) {
      return Promise.resolve(user());
    }
    var p = new URLSearchParams(location.hash.slice(1));
    var at = p.get("access_token");
    if (!at) return Promise.resolve(user());

    session = {
      access_token: at,
      refresh_token: p.get("refresh_token"),
      expires_at: Date.now() + (Number(p.get("expires_in") || 3600) * 1000),
      user: null
    };
    history.replaceState(null, "", location.pathname + location.search);

    return fetch(base() + "/auth/v1/user", {
      headers: { "apikey": cfg().supabaseKey, "Authorization": "Bearer " + at }
    }).then(function (r) { return r.ok ? r.json() : null; })
      .then(function (u) {
        session.user = u;
        save(session);
        return user();
      }).catch(function () { save(session); return user(); });
  }

  /* ---------- what they bought ---------- */

  function rest(path) {
    return fresh().then(function (t) {
      if (!t) throw new Error("Not signed in.");
      return fetch(base() + "/rest/v1/" + path, {
        headers: {
          "apikey": cfg().supabaseKey,
          "Authorization": "Bearer " + t
        }
      });
    }).then(function (r) {
      if (!r.ok) throw new Error("Service error " + r.status);
      return r.json();
    });
  }

  /* Row-level security does the filtering, not this query — a buyer can
     only ever read rows whose email matches their signed-in one. */
  function deliveries() {
    return rest("deliveries?select=*&order=created_at.desc")
      .catch(function () { return []; });
  }

  return {
    ready: ready,
    signIn: signIn,
    signOut: signOut,
    user: user,
    email: email,
    onChange: onChange,
    absorbRedirect: absorbRedirect,
    deliveries: deliveries,
    token: fresh
  };
})();
