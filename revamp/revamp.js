/* Revamped home page: the scroll film, chapter fades, camera callouts,
   availability calendar and the quote form (sent through js/mailer.js). */
(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var vh = window.innerHeight;

  /* ---------- scroll film ----------
     Each chapter owns a stretch of the film. When a chapter's top reaches
     the top of the screen the film is at that chapter's start time, and
     scrolling between chapter tops plays the frames in between. */
  /* hero, stats, lens, tunnel, field. The tunnel starts just after the
     bright flash through the aperture (~0.49) so its text never sits on it. */
  var CHAPTER_T = [0, 0.03, 0.2, 0.52, 0.8];

  function initFilm() {
    var film = document.querySelector("[data-film]");
    if (!film) return;
    var cfg = JSON.parse(film.dataset.film);
    var canvas = film.querySelector(".film__canvas");
    var ctx = canvas.getContext("2d");
    var chaps = Array.prototype.slice.call(film.querySelectorAll("[data-chap]"));
    var set, frames = [], anchors = [], wanted = 0, shown = 0, drawn = -1, running = false;

    function pickSet() {
      var portrait = window.innerWidth / window.innerHeight < 0.9;
      return portrait || window.innerWidth < 700 ? cfg.mobile : cfg.desktop;
    }

    function src(i) {
      return set.path + String(i + 1).padStart(4, "0") + "." + set.ext;
    }

    /* coarse to fine: every 8th frame first so scrubbing works right away,
       then the gaps fill in */
    function load() {
      frames = new Array(set.n);
      var order = [], seen = {};
      [8, 4, 2, 1].forEach(function (step) {
        for (var i = 0; i < set.n; i += step) if (!seen[i]) { seen[i] = 1; order.push(i); }
      });
      var next = 0, active = 0, MAX = 6;
      function pump() {
        while (active < MAX && next < order.length) {
          (function (i) {
            var img = new Image();
            img.decoding = "async";
            active++;
            img.onload = function () {
              frames[i] = img; active--;
              if (Math.abs(i - shown) < 9) draw(shown, true);
              pump();
            };
            img.onerror = function () { active--; pump(); };
            img.src = src(i);
          })(order[next++]);
        }
      }
      pump();
    }

    function nearest(i) {
      for (var d = 0; d < set.n; d++) {
        if (frames[i - d]) return frames[i - d];
        if (frames[i + d]) return frames[i + d];
      }
      return null;
    }

    function size() {
      var dpr = Math.min(window.devicePixelRatio || 1, 1.6);
      canvas.width = Math.round(canvas.clientWidth * dpr);
      canvas.height = Math.round(canvas.clientHeight * dpr);
      drawn = -1;
    }

    /* landscape: cover. portrait: a wide band through the middle showing
       ~58% of the frame width, feathered into black for the text */
    function place(img) {
      var W = canvas.width, H = canvas.height, iw = img.naturalWidth, ih = img.naturalHeight;
      if (W / H >= 0.9) {
        var s = Math.max(W / iw, H / ih);
        return { x: (W - iw * s) / 2, y: (H - ih * s) / 2, w: iw * s, h: ih * s, band: false };
      }
      var bw = W / 0.58, bh = bw * ih / iw;
      return { x: (W - bw) / 2, y: H * 0.44 - bh / 2, w: bw, h: bh, band: true };
    }

    /* pos is a fractional frame: the two frames either side are blended,
       so slow scrolling moves smoothly instead of stepping */
    function draw(pos, force) {
      if (Math.abs(pos - drawn) < 0.004 && !force) return;
      var i = Math.floor(pos), t = pos - i;
      var a = frames[i] || nearest(i), b = t > 0.02 ? frames[i + 1] : null;
      if (!a) return;
      drawn = pos;
      var W = canvas.width, H = canvas.height, r = place(a);
      ctx.globalAlpha = 1;
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, W, H);
      ctx.drawImage(a, r.x, r.y, r.w, r.h);
      if (b && b !== a) {
        ctx.globalAlpha = t;
        ctx.drawImage(b, r.x, r.y, r.w, r.h);
        ctx.globalAlpha = 1;
      }
      if (r.band) {
        var y = r.y, bh = r.h, f = bh * 0.22;
        var g = ctx.createLinearGradient(0, y, 0, y + f);
        g.addColorStop(0, "#000"); g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = g; ctx.fillRect(0, y, W, f);
        g = ctx.createLinearGradient(0, y + bh - f, 0, y + bh);
        g.addColorStop(0, "rgba(0,0,0,0)"); g.addColorStop(1, "#000");
        ctx.fillStyle = g; ctx.fillRect(0, y + bh - f, W, f);
      }
      if (!film.classList.contains("is-live")) film.classList.add("is-live");
    }

    function measure() {
      vh = window.innerHeight;
      var top = film.getBoundingClientRect().top + window.scrollY;
      anchors = chaps.map(function (c, k) {
        return [c.getBoundingClientRect().top + window.scrollY - top, CHAPTER_T[k]];
      });
      anchors.push([film.offsetHeight - vh, 1]);
      anchors.top = top;
    }

    function timeAt(y) {
      var p = y - anchors.top;
      if (p <= anchors[0][0]) return 0;
      for (var k = 1; k < anchors.length; k++) {
        if (p <= anchors[k][0]) {
          var a = anchors[k - 1], b = anchors[k];
          return a[1] + (b[1] - a[1]) * (p - a[0]) / Math.max(1, b[0] - a[0]);
        }
      }
      return 1;
    }

    /* The film eases toward the scroll position rather than snapping to it,
       so a flick of the wheel plays out as motion. */
    function tick() {
      var gap = wanted - shown;
      shown = Math.abs(gap) < 0.02 || reduced ? wanted : shown + gap * 0.14;
      draw(shown);
      fadeChapters();
      if (shown !== wanted) requestAnimationFrame(tick);
      else running = false;
    }

    function update() {
      wanted = timeAt(window.scrollY) * (set.n - 1);
      if (!running) { running = true; requestAnimationFrame(tick); }
    }

    function fadeChapters() {
      chaps.forEach(function (c) {
        if (c.classList.contains("chap--stats")) return;
        var r = c.getBoundingClientRect();
        /* fully visible while the chapter's middle is on screen, fading
           out over the last stretch before it leaves */
        var mid = r.top + r.height / 2, d = Math.abs(mid - vh / 2) / (r.height / 2 + vh * 0.15);
        c.style.opacity = c.classList.contains("chap--hero")
          ? Math.max(0, Math.min(1, 1 - (-r.top) / (vh * 0.7))).toFixed(3)
          : Math.max(0, Math.min(1, (1 - d) * 2.2)).toFixed(3);
      });
    }

    function onScroll() { update(); }

    function reset() {
      var next = pickSet();
      size();
      measure();
      if (next !== set) { set = next; load(); }
      update();
    }

    set = pickSet();
    size();
    measure();
    load();
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    var t;
    window.addEventListener("resize", function () { clearTimeout(t); t = setTimeout(reset, 150); });
    window.addEventListener("load", function () { measure(); update(); });
  }

  /* ---------- callouts, reveals, nav ---------- */
  function initReveals() {
    var items = document.querySelectorAll(".reveal, .callout, .reveal-img, [data-chap]");
    if (reduced || !("IntersectionObserver" in window)) {
      items.forEach(function (n) { n.classList.add("is-in"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("is-in");
          if (e.target.classList.contains("callout")) countUp(e.target.querySelector("[data-count]"));
          io.unobserve(e.target);
        }
      });
    }, { rootMargin: "0px 0px -12% 0px" });
    items.forEach(function (n) { io.observe(n); });
  }

  /* "1,303" counts up from zero; "24 hr" keeps its unit */
  function countUp(node) {
    if (!node || reduced) return;
    var text = node.textContent, m = text.match(/^([\d,]+)(.*)$/);
    if (!m) return;
    var end = parseInt(m[1].replace(/,/g, ""), 10), t0 = null;
    function step(t) {
      if (!t0) t0 = t;
      var k = Math.min(1, (t - t0) / 1100), v = Math.round(end * (1 - Math.pow(1 - k, 3)));
      node.textContent = v.toLocaleString("en-US") + m[2];
      if (k < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  /* photos drift a little slower than the page, so they sit behind it */
  function initParallax() {
    if (reduced) return;
    var imgs = Array.prototype.map.call(document.querySelectorAll("[data-parallax]"), function (n) {
      return [n, n.querySelector("img")];
    });
    var queued = false;
    function paint() {
      queued = false;
      imgs.forEach(function (p) {
        var r = p[0].getBoundingClientRect();
        if (r.bottom < -100 || r.top > vh + 100) return;
        var off = (r.top + r.height / 2 - vh / 2) / (vh / 2 + r.height / 2);
        p[1].style.setProperty("--py", (off * -0.07 * r.height).toFixed(1) + "px");
      });
    }
    window.addEventListener("scroll", function () {
      if (!queued) { queued = true; requestAnimationFrame(paint); }
    }, { passive: true });
    paint();
  }

  function initNav() {
    var nav = document.querySelector("[data-nav]");
    if (!nav) return;
    function paint() { nav.classList.toggle("is-solid", window.scrollY > vh * 0.6); }
    window.addEventListener("scroll", paint, { passive: true });
    paint();
  }

  /* ---------- availability (same rules as the live site) ---------- */
  function pad2(n) { return (n < 10 ? "0" : "") + n; }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function initAvailability() {
    var host = document.querySelector("[data-availability]");
    var blob = document.querySelector("[data-availability-json]");
    if (!host || !blob) return;
    var cfg;
    try { cfg = JSON.parse(blob.textContent || "{}"); } catch (e) { return; }
    var weekly = {}, forceBooked = {}, forceOpen = {};
    (cfg.weeklyBooked || [1, 2, 3, 4, 5]).forEach(function (n) { weekly[n] = true; });
    (cfg.booked || []).forEach(function (d) { forceBooked[d] = true; });
    (cfg.open || []).forEach(function (d) { forceOpen[d] = true; });
    function isBooked(k, dow) {
      if (forceOpen[k]) return false;
      if (forceBooked[k]) return true;
      return !!weekly[dow];
    }
    function key(y, m, d) { return y + "-" + pad2(m + 1) + "-" + pad2(d); }
    var openLabel = cfg.openLabel || "Available", bookedLabel = cfg.bookedLabel || "Booked";
    var now = new Date(), today = key(now.getFullYear(), now.getMonth(), now.getDate());
    var MONTHS = ["January", "February", "March", "April", "May", "June", "July",
                  "August", "September", "October", "November", "December"];
    host.innerHTML = "";
    for (var i = 0; i < Math.max(1, Math.min(6, cfg.months || 2)); i++) {
      var when = new Date(now.getFullYear(), now.getMonth() + i, 1);
      var y = when.getFullYear(), m = when.getMonth();
      var month = el("div", "avail__month");
      month.appendChild(el("h3", "avail__mname", MONTHS[m] + " " + y));
      var grid = el("div", "avail__days");
      ["S", "M", "T", "W", "T", "F", "S"].forEach(function (d) {
        var h = el("span", "avail__dow mono", d);
        h.setAttribute("aria-hidden", "true");
        grid.appendChild(h);
      });
      for (var b = new Date(y, m, 1).getDay(); b > 0; b--) grid.appendChild(el("span", "avail__pad"));
      for (var d = 1, last = new Date(y, m + 1, 0).getDate(); d <= last; d++) {
        var k = key(y, m, d), cell = el("span", "avail__day");
        cell.appendChild(el("b", "avail__num", String(d)));
        var state = k < today ? "past" : isBooked(k, new Date(y, m, d).getDay()) ? bookedLabel : openLabel;
        cell.className += k < today ? " is-past" : state === bookedLabel ? " is-booked" : " is-open";
        if (k >= today) cell.appendChild(el("span", "avail__state", state));
        cell.setAttribute("aria-label", MONTHS[m] + " " + d + " — " + state);
        if (k === today) cell.className += " is-today";
        grid.appendChild(cell);
      }
      month.appendChild(grid);
      host.appendChild(month);
    }
  }

  /* ---------- quote form: same message the live site sends ---------- */
  function initQuote() {
    var form = document.getElementById("quote-form");
    if (!form || !window.Mailer) return;
    var status = form.querySelector("#q-status"), send = form.querySelector(".quote__send");
    var email = (window.CONTACT || {}).email;
    if (!Mailer.ready()) {
      status.className = "quote__status mono is-warn";
      status.textContent = "Sending isn't switched on — email " + email + " instead.";
    }
    document.querySelectorAll("[data-quote]").forEach(function (a) {
      a.addEventListener("click", function () { form.querySelector("#q-type").value = a.dataset.quote; });
    });
    form.querySelector(".quote__again").addEventListener("click", function () { form.classList.remove("is-sent"); });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      function v(id) { return form.querySelector("#" + id).value.trim(); }
      var type = v("q-type"), name = v("q-name"), mail = v("q-email");
      status.className = "quote__status mono";
      if (!type) { status.textContent = "Pick what you're booking."; return; }
      if (!name) { status.textContent = "Add your name."; return; }
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(mail)) { status.textContent = "Add an email Garrett can send the quote to."; return; }
      var lines = [["Booking", type]];
      [["Sport", "q-sport"], ["School / team", "q-team"], ["Athletes", "q-count"], ["Date", "q-date"],
       ["Location", "q-where"], ["Phone", "q-phone"], ["Heard about me", "q-source"]].forEach(function (f) {
        var x = v(f[1]);
        if (x) lines.push([f[0], x]);
      });
      send.disabled = true;
      status.textContent = "Sending…";
      Mailer.send({
        subject: "🚨 Quote request — " + type + " — " + name,
        fromName: "Garrett Photo Quotes",
        summary: "Quote request: " + type,
        lines: lines, name: name, email: mail, note: v("q-details")
      }).then(function () {
        form.reset();
        status.textContent = "";
        form.classList.add("is-sent");
        if (window.Pixel) Pixel.lead();
      }).catch(function (err) {
        status.className = "quote__status mono is-warn";
        status.textContent = err.message + " Nothing was sent — email " + email + " instead.";
      }).finally(function () { send.disabled = false; });
    });
  }

  document.querySelectorAll("[data-year]").forEach(function (n) { n.textContent = new Date().getFullYear(); });
  initFilm();
  initReveals();
  initParallax();
  initNav();
  initAvailability();
  initQuote();
})();
