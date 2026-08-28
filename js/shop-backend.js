/* ============================================================
   SHOP BACKEND
   Two capabilities the store needs that a static site can't do
   on its own: send you an order email, and carry a chat.

   Both are OFF until configured, and the UI says so honestly
   rather than pretending an order went through.

   ---- ORDERS (one click -> email in your inbox) ----
   Web3Forms is the least friction: go to web3forms.com, type
   your email, and they mail you an access key. No account, no
   dashboard. Paste the key below and orders start arriving.
   Formspree works too if you'd rather have a dashboard.

   ---- CHAT ----
   Uses the same free Supabase project as reviews (see SETUP.md).
   Each order opens a room with an unguessable id; the order
   email contains your link to that room. Anyone holding a room
   link can read that room, so treat the link as the key.
   ============================================================ */

window.SHOP_BACKEND = {
  /* The store's real public address. Chat links in email are built from
     THIS, never from location.origin — otherwise an order placed while
     testing on localhost mails out a link that only works on that one
     machine, which is useless on a phone. */
  siteUrl: "https://garrettphoto.store/store.html",

  orders: {
    mode: "web3forms",     /* "none" | "web3forms" | "formspree" */
    accessKey: "ce2f0913-01f0-4515-af6a-aea1eea8606c",
    endpoint: ""           /* formspree endpoint URL             */
  },
  chat: {
    mode: "ntfy",          /* "none" | "ntfy" | "supabase"       */
    topicPrefix: "gep-",   /* ntfy: room topics live under this  */
    url: "",               /* supabase only                      */
    key: ""                /* supabase only                      */
  }
};

window.Shop = (function () {
  "use strict";

  var cfg = window.SHOP_BACKEND;

  function ordersReady() {
    var o = cfg.orders;
    return (o.mode === "web3forms" && !!o.accessKey) ||
           (o.mode === "formspree" && !!o.endpoint);
  }

  /* seller's link into a room — always on the public site */
  function roomUrl(room) {
    var base = cfg.siteUrl || (location.origin + location.pathname);
    return base + "?room=" + room + "&as=seller";
  }

  function chatReady() {
    if (cfg.chat.mode === "ntfy") return true;   /* no credentials needed */
    return cfg.chat.mode === "supabase" && !!cfg.chat.url && !!cfg.chat.key;
  }

  /* Room code. Short on purpose: the notification service sends plain
     text, so the link in the email is not clickable on a phone — Garrett
     has to be able to read this off the screen and type it. Six
     characters from a 31-symbol alphabet is about a billion combinations,
     and a room only lives ~12 hours, so guessing one is not a real
     threat. The ambiguous characters (0/O, 1/I/L) are left out so there
     is nothing to squint at. */
  function roomId() {
    var alpha = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
    var a = new Uint8Array(6);
    (window.crypto || window.msCrypto).getRandomValues(a);
    return Array.prototype.map.call(a, function (b) {
      return alpha.charAt(b % alpha.length);
    }).join("");
  }

  function sendOrder(order) {
    if (!ordersReady()) {
      return Promise.reject(new Error("Ordering isn't switched on yet."));
    }
    var o = cfg.orders;

    /* two shapes go through here: a photo order (items) and a booking
       request (lines). Both land in Garrett's inbox the same way — the
       visitor never opens a mail app or types an address. */
    var detail = order.items
      ? order.items.map(function (i) {
          return "  - " + i.title + "  (" + i.game + ")  " + i.src;
        }).join("\n")
      : (order.lines || []).map(function (l) {
          return "  " + l[0] + ": " + l[1];
        }).join("\n");

    /* One siren, not three, and no emoji in the sender name.
       Three sirens plus an all-caps sender got the whole email filed as
       spam by Gmail — which for an order notification is worse than being
       quiet, because a missed order is a lost sale. A single emoji in the
       subject is common in ordinary transactional mail and passes. The
       durable fix is a "never send to spam" filter on the sender; see
       SETUP.md. */
    var SIREN = "\uD83D\uDEA8";

    var body = {
      subject: order.subject || (SIREN + " Shop order — " + order.name),
      from_name: order.fromName || "Garrett Photo Store",
      name: order.name,
      email: order.email,
      total: "$" + order.total,
      account: order.account || "(not signed in)",
      chat_code: order.room || "(none)",
      chat_link: order.chatUrl || "(chat not configured)",
      message: (order.subject || (SIREN + " Shop order")) + "\n\n" +
               order.summary + "\n\n" +
               "From " + order.name + " <" + order.email + ">\n" +
               (order.account ? "Account: " + order.account + "\n" : "") + "\n" +
               detail + "\n\n" +
               (order.note ? "Note: " + order.note + "\n\n" : "") +
               (order.room
                 ? ("TO CHAT: open garrettphoto.store/chat and enter code " +
                    order.room + "\n\nOr open this link directly:\n" +
                    (order.chatUrl || "") + "\n")
                 : ("Reply in chat: " + (order.chatUrl || "n/a") + "\n"))
    };
    if (order.items) body.photos = String(order.items.length);

    if (o.mode === "web3forms") {
      body.access_key = o.accessKey;
      return fetch("https://api.web3forms.com/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify(body)
      }).then(check);
    }
    return fetch(o.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(body)
    }).then(check);
  }

  /* Never show "Sent" on a bare 200 — only when the service itself says
     it succeeded. A silent false positive here means Garrett thinks an
     order arrived when it never did, which is the worst way to fail. */
  function check(r) {
    return r.json().catch(function () { return {}; }).then(function (j) {
      if (!r.ok || j.success === false) {
        throw new Error(j.message || ("Order service returned " + r.status));
      }
      return j;
    });
  }

  /* ---------- chat ----------

     ntfy.sh is the transport by default: no account, no key, no signup,
     and it allows browser calls. Each order gets its own topic named
     after its room id, which is 18 random hex characters — unguessable,
     the same way the room link already was.

     Two honest limits:
       - ntfy.sh keeps messages for about 12 hours, so a conversation
         does not survive to the next day. The order email is the
         durable record; the chat is for finishing the sale now.
       - A topic is readable by anyone who knows its name, so the room
         link is the key. Never put a customer's email in the chat.

     Supabase is still supported for a permanent history (SETUP.md).
  -------------------------------------------------------------------- */

  function ntfyTopic(room) {
    return (cfg.chat.topicPrefix || "gep-") + room;
  }

  function ntfyHistory(room) {
    return fetch("https://ntfy.sh/" + ntfyTopic(room) +
                 "/json?poll=1&since=all")
      .then(function (r) {
        if (!r.ok) throw new Error("Chat service error " + r.status);
        return r.text();
      })
      .then(function (txt) {
        return txt.split("\n").filter(Boolean).map(function (line) {
          try {
            var env = JSON.parse(line);
            if (env.event !== "message") return null;
            var m = JSON.parse(env.message);
            m.created_at = env.time;
            m.id = env.id;
            return m;
          } catch (e) { return null; }
        }).filter(Boolean);
      });
  }

  function ntfySend(room, who, text) {
    return fetch("https://ntfy.sh/" + ntfyTopic(room), {
      method: "POST",
      body: JSON.stringify({ who: who, body: text })
    }).then(function (r) {
      if (!r.ok) throw new Error("Chat service error " + r.status);
      return r.json().catch(function () { return {}; });
    });
  }

  /* Polling ntfy every few seconds trips its free-tier rate limit (429)
     and would throttle a real buyer, not just testing. So take the live
     stream instead: one long-lived connection per open chat, no repeated
     requests, and messages land instantly rather than up to 3s late. */
  function ntfySubscribe(room, onMsg) {
    var es;
    try {
      es = new EventSource("https://ntfy.sh/" + ntfyTopic(room) + "/sse");
    } catch (e) { return null; }
    es.onmessage = function (ev) {
      try {
        var env = JSON.parse(ev.data);
        if (env.event !== "message") return;
        var m = JSON.parse(env.message);
        m.created_at = env.time;
        m.id = env.id;
        onMsg(m);
      } catch (e) { /* keepalives and non-JSON frames are not messages */ }
    };
    return function () { try { es.close(); } catch (e) {} };
  }

  /* null means "no stream available — caller should poll instead" */
  function chatSubscribe(room, onMsg) {
    if (!chatReady() || cfg.chat.mode !== "ntfy") return null;
    return ntfySubscribe(room, onMsg);
  }

  /* ---- supabase (optional, permanent history) ---- */

  function rest(path, opts) {
    opts = opts || {};
    return fetch(cfg.chat.url.replace(/\/$/, "") + "/rest/v1/" + path, {
      method: opts.method || "GET",
      headers: {
        "apikey": cfg.chat.key,
        "Authorization": "Bearer " + cfg.chat.key,
        "Content-Type": "application/json",
        "Prefer": "return=representation"
      },
      body: opts.body ? JSON.stringify(opts.body) : undefined
    }).then(function (r) {
      if (!r.ok) throw new Error("Chat service error " + r.status);
      return r.status === 204 ? null : r.json();
    });
  }

  function chatHistory(room) {
    if (!chatReady()) return Promise.resolve([]);
    var p = cfg.chat.mode === "ntfy"
      ? ntfyHistory(room)
      : rest("shop_messages?select=*&room=eq." +
             encodeURIComponent(room) + "&order=created_at.asc");
    return p.catch(function () { return []; });
  }

  function chatSend(room, who, text) {
    if (!chatReady()) return Promise.reject(new Error("Chat isn't switched on yet."));
    if (cfg.chat.mode === "ntfy") return ntfySend(room, who, text);
    return rest("shop_messages", { method: "POST",
      body: { room: room, who: who, body: text } });
  }

  /* The chat has no notifications of its own — if Garrett isn't looking
     at the room, a message just sits there. So the first time a customer
     writes in a room, ping the one channel he does watch: his inbox.
     Once per room, so a chatty buyer can't burn the email quota. */
  function chatNotify(room, name, text) {
    var flag = "gep-pinged-" + room;
    try { if (localStorage.getItem(flag)) return Promise.resolve(); } catch (e) {}
    if (!ordersReady()) return Promise.resolve();
    try { localStorage.setItem(flag, "1"); } catch (e) {}

    return sendOrder({
      subject: "\uD83D\uDCAC Chat — " + (name || "a customer") + " is messaging you",
      fromName: "Garrett Photo Chat",
      summary: "New chat message on an order",
      lines: [["From", name || "customer"], ["Message", text]],
      name: name || "customer",
      email: "(reply in the chat room)",
      total: 0,
      room: room,
      chatUrl: roomUrl(room)
    }).catch(function () { /* a failed ping must never break the chat */ });
  }

  return {
    ordersReady: ordersReady,
    chatReady: chatReady,
    roomId: roomId,
    roomUrl: roomUrl,
    sendOrder: sendOrder,
    chatHistory: chatHistory,
    chatSend: chatSend,
    chatSubscribe: chatSubscribe,
    chatNotify: chatNotify
  };
})();
