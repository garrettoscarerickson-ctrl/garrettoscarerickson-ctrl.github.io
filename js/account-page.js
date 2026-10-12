/* ============================================================
   MY PHOTOS — download page for people who bought photographs
   while the site still had a store.

   The store is gone, but anyone who paid can still sign in here
   (the link is no longer in the menu) and download their files.
   Once past buyers have what they need, delete this page:
   account.html, js/account.js, js/account-page.js and
   css/account.css, then the Supabase "download" function and the
   R2 bucket.
   ============================================================ */

(function () {
  "use strict";

  function el(tag, cls, html) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (html != null) node.innerHTML = html;
    return node;
  }

  function esc(str) {
    return String(str == null ? "" : str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function buildAccount() {
    var root = document.getElementById("account-root");
    root.innerHTML = "";

    var head = el("header", "archive-head");
    root.appendChild(head);
    var body = el("div", "account");
    root.appendChild(body);

    function signedOut(msg) {
      head.innerHTML = "<h1>Your photographs</h1>" +
        '<span class="mono">Sign in to download what you have bought</span>';
      body.innerHTML =
        '<form class="entry__form account__form" id="ac-form">' +
        '<input class="account__email" id="ac-email" type="email" ' +
        'placeholder="you@example.com" autocomplete="email" ' +
        'aria-label="Your email"> ' +
        '<button class="entry__go" type="submit">Email me a link</button>' +
        "</form>" +
        '<p class="account__note" id="ac-note">' + (msg ||
          "No password. Enter the email you used when ordering and we'll " +
          "send you a one-time link.<br><b>Open that link on this device</b> " +
          "— whichever device opens it is the one that gets signed in. " +
          "You stay signed in afterwards, so this is a one-time step per " +
          "phone or computer.") + "</p>";

      body.querySelector("#ac-form").addEventListener("submit", function (e) {
        e.preventDefault();
        var addr = body.querySelector("#ac-email").value.trim();
        var note = body.querySelector("#ac-note");
        if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(addr)) {
          note.textContent = "That doesn't look like an email address."; return;
        }
        note.textContent = "Sending…";
        Account.signIn(addr, location.origin + location.pathname)
          .then(function () {
            note.innerHTML = "<b>Check your email.</b> Open the link " +
              "<b>on this device</b> — it signs in whichever one opens it. " +
              "Works once, lasts an hour. Look in spam if it isn't there.";
          })
          .catch(function (err) { note.textContent = err.message; });
      });
    }

    function signedIn() {
      head.innerHTML = "<h1>Your photographs</h1>" +
        '<span class="mono">' + esc(Account.email()) + "</span>";
      body.innerHTML = '<p class="account__note">Loading your files…</p>';

      Account.deliveries().catch(function (err) {
        body.innerHTML = '<p class="account__note"><b>Couldn\'t load your ' +
          "photographs.</b><br>" + esc(err.message) + "</p>";
        return null;
      }).then(function (rows) {
        if (rows === null) return;
        var out = '<div class="account__bar">' +
          '<span class="mono">Signed in as ' + esc(Account.email()) + "</span>" +
          '<button class="account__out" type="button" id="ac-out">Sign out</button>' +
          "</div>";

        if (!rows.length) {
          out += '<p class="account__note">Nothing delivered yet. Once Garrett ' +
            "sends your photographs they appear here, and they stay here — you " +
            "can come back and download them again any time.</p>";
        } else {
          if (Account.wantsInline()) {
          out += '<p class="account__note account__hint">Tap <b>Open</b>, ' +
            "then press and hold the photograph and choose " +
            "<b>Add to Photos</b> to save it to your camera roll.</p>";
        }
        out += '<ul class="deliveries">' + rows.map(function (d) {
            var when = d.created_at
              ? new Date(d.created_at).toLocaleDateString(undefined,
                  { year: "numeric", month: "short", day: "numeric" })
              : "";
            return '<li class="delivery">' +
              '<div class="delivery__meta"><b>' + esc(d.title || "Your photographs") + "</b>" +
              (d.note ? '<span class="delivery__note">' + esc(d.note) + "</span>" : "") +
              '<span class="mono delivery__when">' + when + "</span></div>" +
              ((d.url || d.object_key)
                ? '<button class="delivery__get" type="button" data-id="' +
                  d.id + '">' + (Account.wantsInline() ? "Open" : "Download") +
                  "</button>"
                : '<span class="mono delivery__pending">Preparing</span>') +
              "</li>";
          }).join("") + "</ul>";
        }
        body.innerHTML = out;
        /* Each click mints a new link rather than reusing a stored one,
           so a download still works however long after the sale it is. */
        body.querySelectorAll(".delivery__get").forEach(function (b) {
          b.addEventListener("click", function () {
            var was = b.textContent;
            b.disabled = true;
            b.textContent = "Preparing…";
            Account.link(Number(b.dataset.id)).then(function (url) {
              b.textContent = was;
              b.disabled = false;
              window.location.href = url;
            }).catch(function (e) {
              b.textContent = was;
              b.disabled = false;
              var note = el("p", "account__note", esc(e.message));
              b.parentNode.appendChild(note);
            });
          });
        });

        body.querySelector("#ac-out").addEventListener("click", function () {
          Account.signOut();
          signedOut("Signed out.");
        });
      });
    }

    if (!Account.ready()) {
      head.innerHTML = "<h1>Your photographs</h1>";
      body.innerHTML = '<p class="account__note">Accounts aren\'t switched ' +
        "on yet.</p>";
      return;
    }

    Account.absorbRedirect().then(function (u) {
      u ? signedIn() : signedOut();
    });
  }

  buildAccount();
})();
