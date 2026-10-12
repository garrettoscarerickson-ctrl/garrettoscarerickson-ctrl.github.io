/* ============================================================
   MAILER
   Booking requests and photo-removal requests land in Garrett's
   inbox. A static site cannot send email on its own, so this
   posts to Web3Forms, which forwards the message.

   Web3Forms: go to web3forms.com, type your email, and they mail
   you an access key. No account, no dashboard. Formspree works
   too if you'd rather have a dashboard.
   ============================================================ */

window.MAILER = {
  mode: "web3forms",     /* "none" | "web3forms" | "formspree" */
  accessKey: "ce2f0913-01f0-4515-af6a-aea1eea8606c",
  endpoint: ""           /* formspree endpoint URL             */
};

window.Mailer = (function () {
  "use strict";

  var cfg = window.MAILER;

  function ready() {
    return (cfg.mode === "web3forms" && !!cfg.accessKey) ||
           (cfg.mode === "formspree" && !!cfg.endpoint);
  }

  /* msg: { subject, fromName, summary, lines: [[label, value]], name,
            email, note } */
  function send(msg) {
    if (!ready()) {
      return Promise.reject(new Error("Sending isn't switched on yet."));
    }

    var detail = (msg.lines || []).map(function (l) {
      return "  " + l[0] + ": " + l[1];
    }).join("\n");

    var body = {
      subject: msg.subject,
      from_name: msg.fromName || "Garrett Photo",
      name: msg.name,
      email: msg.email,
      message: msg.subject + "\n\n" +
               (msg.summary ? msg.summary + "\n\n" : "") +
               "From " + msg.name + " <" + msg.email + ">\n\n" +
               detail + "\n" +
               (msg.note ? "\nNote: " + msg.note + "\n" : "")
    };

    var url = cfg.endpoint;
    if (cfg.mode === "web3forms") {
      body.access_key = cfg.accessKey;
      url = "https://api.web3forms.com/submit";
    }
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(body)
    }).then(check);
  }

  /* Never show "Sent" on a bare 200 — only when the service itself says
     it succeeded. A silent false positive means Garrett thinks a request
     arrived when it never did. */
  function check(r) {
    return r.json().catch(function () { return {}; }).then(function (j) {
      if (!r.ok || j.success === false) {
        throw new Error(j.message || ("Mail service returned " + r.status));
      }
      return j;
    });
  }

  return { ready: ready, send: send };
})();
