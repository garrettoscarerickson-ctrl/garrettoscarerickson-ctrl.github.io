/* Meta (Facebook) pixel: counts who arrives from the ads and whether
   they asked for a quote. Paste the pixel ID from Events Manager into
   PIXEL_ID. Left blank, this file does nothing.

   It only runs on the live site, so Studio previews and localhost never
   count as visits.

   Only three events are ever sent:
     PageView - a page was opened
     Lead     - a quote request went through (js/main.js calls Pixel.lead)
     Contact  - an email, phone or Instagram link was tapped
   Nothing typed into the quote form goes to Meta, because the athletes
   are minors. autoConfig is off so Meta doesn't scrape button text or
   page metadata either. Keep Automatic Advanced Matching switched off
   in Events Manager for the same reason. */

(function () {
  var PIXEL_ID = "975790085574374";

  window.Pixel = { lead: function () {} };
  var live = /(^|\.)garrettphoto\.store$/.test(location.hostname);
  if (!PIXEL_ID || !live) return;

  /* Meta's standard loader */
  !function (f, b, e, v, n, t, s) {
    if (f.fbq) return; n = f.fbq = function () {
      n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments);
    };
    if (!f._fbq) f._fbq = n; n.push = n; n.loaded = !0; n.version = "2.0";
    n.queue = []; t = b.createElement(e); t.async = !0; t.src = v;
    s = b.getElementsByTagName(e)[0]; s.parentNode.insertBefore(t, s);
  }(window, document, "script", "https://connect.facebook.net/en_US/fbevents.js");

  fbq("set", "autoConfig", false, PIXEL_ID);
  fbq("init", PIXEL_ID);
  fbq("track", "PageView");

  window.Pixel.lead = function () { fbq("track", "Lead"); };

  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest(
      'a[href^="mailto:"], a[href^="tel:"], a[href*="instagram.com/"]');
    if (a) fbq("track", "Contact");
  }, true);
})();
