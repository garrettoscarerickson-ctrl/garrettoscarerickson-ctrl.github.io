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
  orders: {
    mode: "web3forms",     /* "none" | "web3forms" | "formspree" */
    accessKey: "ce2f0913-01f0-4515-af6a-aea1eea8606c",
    endpoint: ""           /* formspree endpoint URL             */
  },
  chat: {
    mode: "none",          /* "none" | "supabase"                */
    url: "",
    key: ""
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

  function chatReady() {
    return cfg.chat.mode === "supabase" && !!cfg.chat.url && !!cfg.chat.key;
  }

  /* unguessable room id — the order email carries the seller's link */
  function roomId() {
    var a = new Uint8Array(9);
    (window.crypto || window.msCrypto).getRandomValues(a);
    return Array.prototype.map.call(a, function (b) {
      return ("0" + b.toString(16)).slice(-2);
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

    var body = {
      subject: order.subject ||
               ("\uD83D\uDEA8\uD83D\uDEA8\uD83D\uDEA8 SHOP ORDER " +
                "\uD83D\uDEA8\uD83D\uDEA8\uD83D\uDEA8 — " + order.name),
      name: order.name,
      email: order.email,
      total: "$" + order.total,
      chat_link: order.chatUrl || "(chat not configured)",
      message: order.summary + "\n\n" +
               "From " + order.name + " <" + order.email + ">\n\n" +
               detail + "\n\n" +
               (order.note ? "Note: " + order.note + "\n\n" : "") +
               "Reply in chat: " + (order.chatUrl || "n/a") + "\n"
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

  /* ---------- chat ---------- */

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
    return rest("shop_messages?select=*&room=eq." +
                encodeURIComponent(room) + "&order=created_at.asc")
      .catch(function () { return []; });
  }

  function chatSend(room, who, text) {
    if (!chatReady()) return Promise.reject(new Error("Chat isn't switched on yet."));
    return rest("shop_messages", { method: "POST",
      body: { room: room, who: who, body: text } });
  }

  return {
    ordersReady: ordersReady,
    chatReady: chatReady,
    roomId: roomId,
    sendOrder: sendOrder,
    chatHistory: chatHistory,
    chatSend: chatSend
  };
})();
