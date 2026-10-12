/* ============================================================
   Renders the Home and Portfolio pages from window.PHOTOS (js/photos.js).
   Nothing here needs editing when photos are added.
   ============================================================ */

(function () {
  "use strict";

  var PHOTOS = window.PHOTOS || [];
  var page = document.body.dataset.page;
  var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- helpers ---------- */

  function el(tag, cls, html) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (html != null) node.innerHTML = html;
    return node;
  }

  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  function nPhotos(n) {
    return n + (n === 1 ? " photograph" : " photographs");
  }

  function tagLine(photo) {
    return photo.tags.join(" / ");
  }

  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  /* Alt text says what the photograph is and where, which is also what
     image search reads. Game photographs name the sport and the game. */
  var NOT_A_SPORT = ["sports", "people", "detail", "portraits"];

  function photoAlt(photo) {
    if (photo.game) {
      var sport = photo.tags.filter(function (t) {
        return NOT_A_SPORT.indexOf(t) === -1;
      })[0];
      return (sport ? cap(sport) + " photo" : "Photo") + " from " +
        photo.game + ", " + photo.location;
    }
    return photo.title + " — " + photo.location;
  }

  /* Photographs of people sort to the end of any run, so the work leads
     with places and closes with faces. Sort is stable, so the curated
     order is otherwise preserved. */
  var PEOPLE_TAGS = ["people", "portraits"];

  function isPeople(photo) {
    return photo.tags.some(function (t) {
      return PEOPLE_TAGS.indexOf(t) !== -1;
    });
  }

  function peopleLast(list) {
    return list.slice().sort(function (a, b) {
      return (isPeople(a) ? 1 : 0) - (isPeople(b) ? 1 : 0);
    });
  }

  /* ---------- casual save protection ----------
     Blocks right-click-save and drag-to-desktop on photographs. This
     deters casual copying only — anyone determined can still screenshot
     or pull the file directly. The visible watermark is the real claim. */

  function protectImages(scope) {
    (scope || document).addEventListener("contextmenu", function (e) {
      if (e.target.closest("img, .ph__img, .lightbox__frame, " +
                           ".panel__img-wrap, .hero__img-wrap")) {
        e.preventDefault();
      }
    });
    (scope || document).addEventListener("dragstart", function (e) {
      if (e.target.tagName === "IMG") e.preventDefault();
    });
  }

  /* ---------- archive masonry ----------
     Each card spans however many grid row-units its own height needs, so
     the grid fills row-wise (left to right) while keeping natural heights. */

  function layoutMasonry(grid) {
    if (!grid) return;
    var cs = getComputedStyle(grid);
    var unit = parseFloat(cs.getPropertyValue("--row-unit")) || 8;
    var gutter = parseFloat(cs.getPropertyValue("--gutter")) || 0;
    Array.prototype.forEach.call(grid.children, function (card) {
      if (card.classList.contains("archive-empty")) return;
      var h = card.getBoundingClientRect().height;
      if (!h) return;
      card.style.gridRowEnd = "span " + Math.ceil((h + gutter) / unit);
    });
  }

  function watchMasonry(grid) {
    var pending = false;
    function relayout() {
      if (pending) return;
      pending = true;
      requestAnimationFrame(function () {
        pending = false;
        layoutMasonry(grid);
      });
    }
    relayout();
    window.addEventListener("resize", relayout);
    /* images and webfonts change card heights after first paint */
    if ("ResizeObserver" in window) {
      var ro = new ResizeObserver(relayout);
      Array.prototype.forEach.call(grid.children, function (c) { ro.observe(c); });
    }
    Array.prototype.forEach.call(grid.querySelectorAll("img"), function (img) {
      if (!img.complete) img.addEventListener("load", relayout, { once: true });
    });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(relayout);
    return relayout;
  }

  /* A photo card <button class="ph"> used by both pages */
  function photoCard(photo, index, onClick) {
    var card = el("button", "ph" +
      (photo.orientation === "portrait" ? " ph--portrait" : ""));
    card.type = "button";
    card.setAttribute("aria-label", "View " + photo.title);
    /* real pixel ratio, so the grid can reserve exact space up front */
    var ar = photo.w && photo.h ? ' style="--ar:' + photo.w + "/" + photo.h + '"' : "";
    card.innerHTML =
      '<figure>' +
      '<span class="ph__img wm"' + ar + '><span class="ph__par">' +
      '<img loading="lazy" src="' + photo.src +
      '" alt="' + photoAlt(photo) + '"></span></span>' +
      '<figcaption>' +
      '<span class="ph__title">' + photo.title + "</span>" +
      '<span class="mono">' + tagLine(photo) + "</span>" +
      "</figcaption>" +
      "</figure>";
    card.addEventListener("click", function () { onClick(index); });
    return card;
  }

  /* ---------- lightbox (shared) ---------- */

  var lightboxSet = [];
  var lightboxIdx = 0;
  var lb = null;

  function buildLightbox() {
    lb = el("div", "lightbox");
    lb.setAttribute("role", "dialog");
    lb.setAttribute("aria-modal", "true");
    lb.innerHTML =
      '<button class="lightbox__close">Close ✕</button>' +
      '<div class="lightbox__stage">' +
      '<span class="lightbox__frame wm wm--lg"><img alt=""></span></div>' +
      '<div class="lightbox__bar">' +
      '<div><span class="ph__title" id="lb-title"></span>' +
      '<span class="mono" id="lb-meta" style="margin-left:1.25rem"></span></div>' +
      '<div class="lightbox__nav">' +
      '<span class="lb-rate" id="lb-rate" role="radiogroup" ' +
      'aria-label="Rate this photograph out of 5"></span>' +
      '<button id="lb-reviews" class="lb-reviews-btn"></button>' +
      '<span class="mono" id="lb-count"></span>' +
      '<button id="lb-prev">← Prev</button>' +
      '<button id="lb-next">Next →</button>' +
      '<button id="lb-remove" class="lb-remove">Request removal</button>' +
      "</div></div>" +
      '<aside class="lb-drawer" id="lb-drawer" aria-label="Reviews">' +
      '<div class="lb-drawer__head">' +
      '<span class="mono">Reviews</span>' +
      '<button class="lb-drawer__close" id="lb-drawer-close" ' +
      'aria-label="Close reviews">✕</button></div>' +
      '<div class="lb-drawer__score" id="lb-score"></div>' +
      '<div class="lb-drawer__list" id="lb-list"></div>' +
      '<form class="lb-drawer__form" id="lb-form">' +
      '<span class="mono">Your rating</span>' +
      '<div class="lb-form__stars" id="lb-form-stars"></div>' +
      '<input type="text" id="lb-form-name" placeholder="Your name" required>' +
      '<textarea id="lb-form-text" rows="3" placeholder="What did you think?"></textarea>' +
      '<button type="submit" class="lb-form__send">Post review</button>' +
      '<p class="lb-form__note mono" id="lb-form-note"></p>' +
      "</form></aside>";
    document.body.appendChild(lb);

    lb.querySelector(".lightbox__close").addEventListener("click", closeLightbox);
    lb.querySelector("#lb-prev").addEventListener("click", function () { stepLightbox(-1); });
    lb.querySelector("#lb-next").addEventListener("click", function () { stepLightbox(1); });
    lb.querySelector("#lb-remove").addEventListener("click", function () {
      openRemoval(lightboxSet[lightboxIdx]);
    });
    lb.addEventListener("click", function (e) {
      if (e.target === lb || e.target.classList.contains("lightbox__stage")) closeLightbox();
    });
    protectImages(lb);

    var rate = lb.querySelector("#lb-rate");
    for (var i = 1; i <= 5; i++) {
      var b = el("button", "star-btn", "\u2605");
      b.type = "button";
      b.dataset.v = i;
      b.setAttribute("aria-label", i + " star" + (i > 1 ? "s" : ""));
      rate.appendChild(b);
    }
    rate.addEventListener("click", function (e) {
      var b = e.target.closest(".star-btn");
      if (!b) return;
      setRating(lightboxSet[lightboxIdx].src, Number(b.dataset.v));
      paintRating();
      openReviews(Number(b.dataset.v));   /* jump straight into the form */
    });
    rate.addEventListener("mouseover", function (e) {
      var b = e.target.closest(".star-btn");
      if (b) paintRating(Number(b.dataset.v));
    });
    rate.addEventListener("mouseleave", function () { paintRating(); });

    /* review drawer */
    var fstars = lb.querySelector("#lb-form-stars");
    for (var k = 1; k <= 5; k++) {
      var sb = el("button", "star-btn", "\u2605");
      sb.type = "button";
      sb.dataset.v = k;
      sb.setAttribute("aria-label", k + " star" + (k > 1 ? "s" : ""));
      fstars.appendChild(sb);
    }
    fstars.addEventListener("click", function (e) {
      var b = e.target.closest(".star-btn");
      if (b) setFormStars(Number(b.dataset.v));
    });
    lb.querySelector("#lb-reviews").addEventListener("click", function () {
      lb.classList.contains("drawer-open") ? closeReviews() : openReviews();
    });
    lb.querySelector("#lb-drawer-close").addEventListener("click", closeReviews);
    lb.querySelector("#lb-form").addEventListener("submit", submitPhotoReview);

    document.addEventListener("keydown", function (e) {
      if (!lb.classList.contains("is-open")) return;
      if (e.key === "Escape") {
        if (lb.classList.contains("drawer-open")) { closeReviews(); return; }
        closeLightbox();
      }
      if (e.key === "ArrowLeft") stepLightbox(-1);
      if (e.key === "ArrowRight") stepLightbox(1);
    });
  }

  /* ---------- photo ratings ----------
     Stored in this browser only. A shared, public score needs a backend;
     until then a visitor sees and keeps their own ratings. */

  var RATING_KEY = "ge.ratings.v1";

  function allRatings() {
    try { return JSON.parse(localStorage.getItem(RATING_KEY)) || {}; }
    catch (e) { return {}; }
  }

  function getRating(src) { return allRatings()[src] || 0; }

  function setRating(src, v) {
    var all = allRatings();
    all[src] = v;
    try { localStorage.setItem(RATING_KEY, JSON.stringify(all)); } catch (e) {}
  }

  function paintRating(preview) {
    if (!lb) return;
    var photo = lightboxSet[lightboxIdx];
    var v = preview || (photo ? getRating(photo.src) : 0);
    lb.querySelectorAll("#lb-rate .star-btn").forEach(function (b) {
      b.classList.toggle("is-on", Number(b.dataset.v) <= v);
    });
    lb.querySelector("#lb-rate").classList.toggle("is-rated",
      !preview && v > 0);
  }

  /* ---------- per-photo reviews (shared when a backend is configured) ---------- */

  var formStars = 0;

  function setFormStars(v) {
    formStars = v;
    lb.querySelectorAll("#lb-form-stars .star-btn").forEach(function (b) {
      b.classList.toggle("is-on", Number(b.dataset.v) <= v);
    });
  }

  function openReviews(preset) {
    lb.classList.add("drawer-open");
    if (preset) setFormStars(preset);
    renderPhotoReviews();
  }

  function closeReviews() { lb.classList.remove("drawer-open"); }

  function fmtDate(iso) {
    if (!iso) return "";
    var d = new Date(iso);
    return isNaN(d) ? "" : d.toLocaleDateString(undefined,
      { year: "numeric", month: "short" });
  }

  function esc(str) {
    return String(str == null ? "" : str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  /* button label in the bar: count + average for the current photo */
  function paintReviewCount() {
    var photo = lightboxSet[lightboxIdx];
    if (!photo) return;
    var btn = lb.querySelector("#lb-reviews");
    ReviewStore.forPhoto(photo.src).then(function (rows) {
      if (lightboxSet[lightboxIdx] !== photo) return;   /* moved on already */
      if (!rows.length) { btn.textContent = "Reviews"; return; }
      var avg = rows.reduce(function (a, r) { return a + r.rating; }, 0) / rows.length;
      btn.textContent = "\u2605 " + avg.toFixed(1) + " · " + rows.length +
        (rows.length === 1 ? " review" : " reviews");
    });
  }

  function renderPhotoReviews() {
    var photo = lightboxSet[lightboxIdx];
    if (!photo) return;
    var score = lb.querySelector("#lb-score");
    var list = lb.querySelector("#lb-list");
    var note = lb.querySelector("#lb-form-note");
    list.innerHTML = '<p class="mono lb-list__empty">Loading…</p>';
    /* say what actually happens — with approval on, a review does not
       appear the moment it is posted, and telling someone it did would
       have them refreshing to look for it */
    note.textContent = !ReviewStore.isShared()
      ? "Saved in your browser. Shared reviews switch on once a backend is connected."
      : (window.REVIEW_BACKEND && REVIEW_BACKEND.requireApproval)
        ? "Goes to Garrett first, then appears on the site."
        : "Posts publicly — everyone visiting sees it.";

    ReviewStore.forPhoto(photo.src).then(function (rows) {
      if (lightboxSet[lightboxIdx] !== photo) return;
      if (!rows.length) {
        score.innerHTML = '<span class="mono">No reviews yet</span>';
        list.innerHTML = '<p class="mono lb-list__empty">Be the first to review ' +
          esc(photo.title) + ".</p>";
        return;
      }
      var avg = rows.reduce(function (a, r) { return a + r.rating; }, 0) / rows.length;
      score.innerHTML =
        '<strong>' + avg.toFixed(1) + "</strong>" + stars(Math.round(avg)) +
        '<span class="mono">' + rows.length +
        (rows.length === 1 ? " review" : " reviews") + "</span>";
      list.innerHTML = rows.map(function (r) {
        return '<article class="lb-review">' + stars(r.rating) +
          (r.text ? "<p>" + esc(r.text) + "</p>" : "") +
          '<footer class="mono">' + esc(r.name) +
          (r.created_at ? " · " + fmtDate(r.created_at) : "") +
          "</footer></article>";
      }).join("");
    });
  }

  function submitPhotoReview(e) {
    e.preventDefault();
    var photo = lightboxSet[lightboxIdx];
    var name = lb.querySelector("#lb-form-name").value.trim();
    var text = lb.querySelector("#lb-form-text").value.trim();
    var note = lb.querySelector("#lb-form-note");
    if (!formStars) { note.textContent = "Pick a star rating first."; return; }
    if (!name) { note.textContent = "Add your name."; return; }
    var btn = lb.querySelector(".lb-form__send");
    btn.disabled = true;
    note.textContent = "Posting…";
    ReviewStore.add({ photo: photo.src, name: name, rating: formStars, text: text })
      .then(function () {
        lb.querySelector("#lb-form-name").value = "";
        lb.querySelector("#lb-form-text").value = "";
        setFormStars(0);
        note.textContent = ReviewStore.isShared()
          ? "Posted — thank you."
          : "Saved to this browser — thank you.";
        renderPhotoReviews();
        paintReviewCount();
      })
      .catch(function (err) {
        note.textContent = "Could not post that review. " + err.message;
      })
      .finally(function () { btn.disabled = false; });
  }

  function openLightbox(set, index) {
    if (!lb) buildLightbox();
    lightboxSet = set;
    lightboxIdx = index;
    renderLightbox();
    lb.classList.add("is-open");
    document.body.style.overflow = "hidden";
  }

  function closeLightbox() {
    lb.classList.remove("is-open");
    document.body.style.overflow = "";
  }

  function stepLightbox(dir) {
    lightboxIdx = (lightboxIdx + dir + lightboxSet.length) % lightboxSet.length;
    renderLightbox();
  }

  function renderLightbox() {
    var photo = lightboxSet[lightboxIdx];
    lb.querySelector(".lightbox__stage img").src = photo.src;
    lb.querySelector(".lightbox__stage img").alt = photoAlt(photo);
    lb.querySelector(".lightbox__stage img").draggable = false;
    lb.querySelector("#lb-title").textContent = photo.title;
    lb.querySelector("#lb-meta").textContent =
      (photo.game ? photo.game + " · " : "") +
      photo.location + " · " + photo.year + " · " + tagLine(photo);
    lb.querySelector("#lb-count").textContent =
      pad2(lightboxIdx + 1) + " / " + pad2(lightboxSet.length);
    paintRating();
    paintReviewCount();
    if (lb.classList.contains("drawer-open")) renderPhotoReviews();
  }

  /* ---------- parallax ---------- */

  function initParallax() {
    /* the scroll-progress bar runs even with reduced motion (it's not motion,
       it's an indicator); the depth layers are gated on the motion pref. */
    var bar = document.querySelector(".scrollbar > i");

    var layers = [];
    if (!reducedMotion) {
      /* full-bleed hero + panel images move deep */
      document.querySelectorAll(".hero__img-wrap img, .panel__img-wrap img")
        .forEach(function (img) {
          layers.push({ node: img, box: img.parentElement, amp: 0.14 });
        });
      /* gallery frames: the oversized image drifts within its window */
      document.querySelectorAll(".strip__grid .ph__par").forEach(function (par) {
        layers.push({ node: par, box: par.closest(".ph__img"), amp: 0.08 });
      });
    }
    var heroContent = reducedMotion ? null : document.querySelector(".hero__content");
    var introWrap = document.querySelector(".intro-wrap");
    var intro = reducedMotion ? null : document.querySelector(".intro");

    var ticking = false;

    function update() {
      ticking = false;
      var vh = window.innerHeight;

      if (bar) {
        var doc = document.documentElement;
        var max = doc.scrollHeight - vh;
        var p = max > 0 ? window.scrollY / max : 0;
        bar.style.transform = "scaleX(" + p.toFixed(4) + ")";
      }

      if (intro) {
        /* 0 -> 1 across the pinned stretch */
        var pinned = introWrap.offsetHeight - vh;
        var t = pinned > 0 ? Math.min(1, Math.max(0, window.scrollY / pinned)) : 0;
        intro.style.opacity = (1 - Math.min(1, t * 1.35)).toFixed(3);
        intro.style.transform = "scale(" + (1 - t * 0.08).toFixed(4) + ")";
        intro.style.filter = t > 0.02 ? "blur(" + (t * 7).toFixed(2) + "px)" : "";
      }

      if (heroContent) {
        /* how far the hero has scrolled past the top of the screen. Not
           scrollY: the name card above takes two screens of scrolling
           first, which used to fade this out before it was ever seen. */
        var s = Math.max(0, -heroContent.parentElement.getBoundingClientRect().top);
        /* title lingers, then fades as the hero leaves */
        heroContent.style.transform = "translateY(" + (s * 0.28).toFixed(1) + "px)";
        heroContent.style.opacity = Math.max(0, 1 - s / (vh * 0.82)).toFixed(3);
      }

      layers.forEach(function (L) {
        var rect = L.box.getBoundingClientRect();
        if (rect.bottom < -80 || rect.top > vh + 80) return;
        /* progress: -1 (below viewport) → 1 (above viewport) */
        var progress = (rect.top + rect.height / 2 - vh / 2) / (vh / 2 + rect.height / 2);
        L.node.style.transform =
          "translateY(" + (progress * rect.height * L.amp).toFixed(1) + "px)";
      });
    }

    function onScroll() {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(update);
      }
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    update();
  }

  /* ---------- reveal on scroll ---------- */

  function initReveal() {
    var targets = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window) || reducedMotion) {
      targets.forEach(function (t) { t.classList.add("is-visible"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    targets.forEach(function (t) { io.observe(t); });
  }

  /* ============================================================
     HOME PAGE — the front door. Who I am, what I shoot, how to get
     a quote, what people say, and how to reach me. The full body of
     work lives on the Portfolio page.

     The words people search for (who, what, where) and the quote
     form are written straight into index.html, so they are there
     before any script runs. What is built from data here (the hero,
     selected work, reviews, contact) drops into its [data-slot]s.
     ============================================================ */

  var CONTACT = {
    email: "garrettoscarerickson@gmail.com",
    instagram: "shot_by_ge"
  };

  function buildAbout() {
    var root = document.getElementById("about-root");
    var hero = PHOTOS.filter(function (p) { return p.feature === "hero"; })[0] || PHOTOS[0];

    function fill(name, node) {
      var slot = root.querySelector('[data-slot="' + name + '"]');
      if (slot) slot.replaceWith(node); else root.appendChild(node);
    }

    /* scroll-progress bar */
    var scrollbar = el("div", "scrollbar");
    scrollbar.innerHTML = "<i></i>";
    document.body.appendChild(scrollbar);

    /* hero */
    var heroSec = el("section", "hero");
    heroSec.innerHTML =
      '<div class="hero__img-wrap" data-parallax>' +
      '<img src="' + hero.src + '" alt="' + photoAlt(hero) + '" fetchpriority="high">' +
      "</div>" +
      '<div class="hero__content">' +
      '<a class="quote-btn hero__cta" href="#quote">Get a quote</a>' +
      '<div class="hero__meta">' +
      '<span class="mono">Michigan sports photographer — booking now</span>' +
      '<span class="mono">Football · Soccer · Tennis · Volleyball</span>' +
      "</div></div>";
    fill("hero", heroSec);

    fill("marquee", buildMarquee(
      ["Football", "Soccer", "Tennis", "Volleyball", "Teams", "Events"]));

    fill("work", buildSelectedWork());
    fill("reviews", buildReviews());
    fill("contact", buildContact());

    /* CTA into the work */
    var cta = el("a", "cta reveal");
    cta.href = "portfolio.html";
    cta.innerHTML =
      '<span class="cta__big">See the Portfolio</span>' +
      '<span class="mono">' + nPhotos(PHOTOS.length) + ", filterable →</span>";
    fill("cta", cta);

    initQuote();
    initParallax();
    initReveal();
  }

  /* a short taste of the work, since the home page is not a gallery */
  function buildSelectedWork() {
    var sec = el("section", "selected reveal");
    var pool = PHOTOS.filter(function (p) { return p.feature || !p.archiveOnly; });
    if (pool.length < 6) pool = PHOTOS;
    var picks = peopleLast(pool).slice(0, 6);
    var grid = el("div", "selected__grid");
    picks.forEach(function (photo) {
      var card = photoCard(photo, picks.indexOf(photo), function (i) {
        openLightbox(picks, i);
      });
      grid.appendChild(card);
    });
    sec.innerHTML =
      '<div class="section__head"><span class="mono">02 — Selected work</span>' +
      '<a class="mono selected__all" href="portfolio.html">All ' +
      nPhotos(PHOTOS.length) + " →</a></div>";
    sec.appendChild(grid);
    return sec;
  }

  /* ---------- get a quote ----------
     There are no set prices: every shoot is quoted. The form lives in
     index.html; this sends it to Garrett through js/mailer.js and he
     replies with a price. No mail app opens on the visitor's end. */

  function initQuote() {
    var form = document.getElementById("quote-form");
    if (!form) return;
    var status = form.querySelector("#q-status");
    var send = form.querySelector(".quote__send");

    if (!Mailer.ready()) {
      status.className = "quote__status mono is-warn";
      status.textContent = "Sending isn't switched on — email " +
        CONTACT.email + " instead.";
    }

    /* a "Get a quote" button can say what it's for, so the form opens
       with that already picked */
    document.querySelectorAll("[data-quote]").forEach(function (a) {
      a.addEventListener("click", function () {
        form.querySelector("#q-type").value = a.dataset.quote;
      });
    });

    form.querySelector(".quote__again").addEventListener("click", function () {
      form.classList.remove("is-sent");
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      function v(id) { return form.querySelector("#" + id).value.trim(); }
      var type = v("q-type"), name = v("q-name"), email = v("q-email");

      status.className = "quote__status mono";
      if (!type) { status.textContent = "Pick what you're booking."; return; }
      if (!name) { status.textContent = "Add your name."; return; }
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
        status.textContent = "Add an email Garrett can send the quote to."; return;
      }

      var lines = [["Booking", type]];
      [["Sport", "q-sport"], ["School / team", "q-team"],
       ["Athletes", "q-count"], ["Date", "q-date"],
       ["Location", "q-where"], ["Phone", "q-phone"]].forEach(function (f) {
        var x = v(f[1]);
        if (x) lines.push([f[0], x]);
      });

      send.disabled = true;
      status.textContent = "Sending…";
      Mailer.send({
        subject: "🚨 Quote request — " + type + " — " + name,
        fromName: "Garrett Photo Quotes",
        summary: "Quote request: " + type,
        lines: lines,
        name: name,
        email: email,
        note: v("q-details")
      }).then(function () {
        form.reset();
        status.textContent = "";
        form.classList.add("is-sent");
      }).catch(function (err) {
        status.className = "quote__status mono is-warn";
        status.textContent = err.message + " Nothing was sent — email " +
          CONTACT.email + " instead.";
      }).finally(function () { send.disabled = false; });
    });
  }

  /* ---------- reviews ---------- */

  function stars(n, cls) {
    var out = "";
    for (var i = 1; i <= 5; i++) {
      out += '<span class="star' + (i <= n ? " is-on" : "") + '">★</span>';
    }
    return '<span class="stars ' + (cls || "") + '">' + out + "</span>";
  }

  function buildReviews() {
    var list = (window.REVIEWS || []).slice();
    var sec = el("section", "reviews reveal");
    /* approved site reviews arrive from the database and join the list
       that is curated by hand in data/reviews.json */
    ReviewStore.forSite().then(function (rows) {
      if (!rows.length) return;
      var box = sec.querySelector(".review-list");
      var empty = sec.querySelector(".reviews__empty");
      if (!box) {
        box = el("div", "review-list");
        if (empty) empty.replaceWith(box); else sec.insertBefore(box, sec.firstChild.nextSibling);
      }
      box.insertAdjacentHTML("afterbegin", rows.map(function (r) {
        return '<article class="review">' + stars(r.rating) +
          (r.text ? "<p>" + esc(r.text) + "</p>" : "") +
          '<footer class="mono">' + esc(r.name) +
          (r.role ? " · " + esc(r.role) : "") + "</footer></article>";
      }).join(""));
      var all = list.concat(rows);
      var a = all.reduce(function (x, r) { return x + r.rating; }, 0) / all.length;
      var h = sec.querySelector(".section__head .mono:last-child");
      if (h) h.textContent = a.toFixed(1) + " / 5 · " + all.length +
        (all.length === 1 ? " review" : " reviews");
    });
    var avg = list.length
      ? (list.reduce(function (s, r) { return s + r.rating; }, 0) / list.length)
      : 0;

    var head =
      '<div class="section__head">' +
      '<span class="mono">05 — Reviews</span>' +
      (list.length
        ? '<span class="mono">' + avg.toFixed(1) + " / 5 · " +
          list.length + (list.length === 1 ? " review" : " reviews") + "</span>"
        : '<span class="mono">Be the first</span>') +
      "</div>";

    var cards = list.length
      ? '<div class="review-list">' + list.map(function (r) {
          return '<article class="review">' + stars(r.rating) +
            "<p>" + r.text + "</p>" +
            '<footer class="mono">' + r.name +
            (r.role ? " · " + r.role : "") + "</footer></article>";
        }).join("") + "</div>"
      : '<p class="reviews__empty mono">No reviews yet — if we\'ve worked ' +
        "together, yours would be the first.</p>";

    sec.innerHTML = head + cards +
      '<form class="review-form" id="review-form">' +
      '<h3 class="review-form__title">Leave a review</h3>' +
      '<div class="review-form__stars" id="rf-stars" role="radiogroup" ' +
      'aria-label="Rating out of 5"></div>' +
      '<div class="review-form__row">' +
      '<label><span class="mono">Name</span>' +
      '<input type="text" id="rf-name" required autocomplete="name"></label>' +
      '<label><span class="mono">What you booked (optional)</span>' +
      '<input type="text" id="rf-role" placeholder="Team session, portraits…"></label>' +
      "</div>" +
      '<label class="review-form__msg"><span class="mono">Review</span>' +
      '<textarea id="rf-text" rows="4" required></textarea></label>' +
      '<button class="review-form__send" type="submit">Send review</button>' +
      '<p class="review-form__note mono" id="rf-note"></p>' +
      "</form>";

    /* interactive star picker */
    var chosen = 0;
    var box = sec.querySelector("#rf-stars");
    for (var i = 1; i <= 5; i++) {
      var b = el("button", "star-btn", "★");
      b.type = "button";
      b.dataset.v = i;
      b.setAttribute("aria-label", i + " star" + (i > 1 ? "s" : ""));
      box.appendChild(b);
    }
    function paint(v) {
      box.querySelectorAll(".star-btn").forEach(function (b) {
        b.classList.toggle("is-on", Number(b.dataset.v) <= v);
      });
    }
    box.addEventListener("click", function (e) {
      var b = e.target.closest(".star-btn");
      if (!b) return;
      chosen = Number(b.dataset.v);
      paint(chosen);
    });
    box.addEventListener("mouseover", function (e) {
      var b = e.target.closest(".star-btn");
      if (b) paint(Number(b.dataset.v));
    });
    box.addEventListener("mouseleave", function () { paint(chosen); });

    /* recent per-photo reviews, pulled from whatever backend is wired up */
    var recent = el("div", "recent-reviews");
    sec.insertBefore(recent, sec.querySelector("#review-form"));
    ReviewStore.forPhotos().then(function (rows) {
      if (!rows.length) { recent.remove(); return; }
      var avg = rows.reduce(function (a, r) { return a + r.rating; }, 0) / rows.length;
      var byTitle = {};
      PHOTOS.forEach(function (p) { byTitle[p.src] = p.title; });
      recent.innerHTML =
        '<div class="recent-reviews__head">' +
        '<span class="mono">On individual photographs</span>' +
        '<span class="mono">' + avg.toFixed(1) + " / 5 · " + rows.length +
        (rows.length === 1 ? " review" : " reviews") + "</span></div>" +
        '<div class="review-list">' + rows.slice(0, 3).map(function (r) {
          return '<article class="review">' + stars(r.rating) +
            (r.text ? "<p>" + esc(r.text) + "</p>" : "") +
            '<footer class="mono">' + esc(r.name) +
            (byTitle[r.photo] ? " · " + esc(byTitle[r.photo]) : "") +
            "</footer></article>";
        }).join("") + "</div>";
    });

    var note = sec.querySelector("#rf-note");
    var send = sec.querySelector(".review-form__send");
    note.textContent = !ReviewStore.isShared()
      ? "Saved in your browser. Shared reviews switch on once a backend is connected."
      : (window.REVIEW_BACKEND && REVIEW_BACKEND.requireApproval)
        ? "Goes to Garrett first, then appears here."
        : "Posts publicly — everyone visiting sees it.";

    /* Same one-tap path as a photo review: posted straight to the shared
       store, held for approval, and Garrett is emailed. It used to open
       the visitor's mail app, which asked them to do the work and lost
       anyone without mail set up. */
    sec.querySelector("#review-form").addEventListener("submit", function (e) {
      e.preventDefault();
      var name = sec.querySelector("#rf-name").value.trim();
      var role = sec.querySelector("#rf-role").value.trim();
      var text = sec.querySelector("#rf-text").value.trim();
      if (!chosen) { note.textContent = "Pick a star rating first."; return; }
      if (!name)   { note.textContent = "Add your name."; return; }
      if (!text)   { note.textContent = "Write a little about the shoot."; return; }

      send.disabled = true;
      note.textContent = "Sending…";
      ReviewStore.add({
        photo: ReviewStore.SITE, name: name, rating: chosen,
        text: text, role: role
      }).then(function () {
        sec.querySelector("#review-form").reset();
        chosen = 0; paint(0);
        note.textContent = REVIEW_BACKEND.requireApproval
          ? "Thank you — sent to Garrett. It appears here once he approves it."
          : "Thank you — your review is live.";
      }).catch(function (err) {
        note.textContent = "Couldn't send that (" + err.message +
          "). Email " + CONTACT.email + " instead.";
      }).finally(function () { send.disabled = false; });
    });

    return sec;
  }

  function buildContact() {
    var sec = el("section", "contact reveal");
    sec.innerHTML =
      '<div class="section__head"><span class="mono">07 — Contact</span>' +
      '<span class="mono">Michigan · booking now</span></div>' +
      '<div class="contact__grid">' +
      '<a class="contact__card" href="mailto:' + CONTACT.email + '">' +
      '<span class="mono">Email</span>' +
      "<strong>" + CONTACT.email + "</strong>" +
      '<span class="contact__go">Send a message →</span></a>' +
      '<a class="contact__card" href="https://www.instagram.com/' +
      CONTACT.instagram + '" target="_blank" rel="noopener noreferrer">' +
      '<span class="mono">Instagram</span>' +
      "<strong>@" + CONTACT.instagram + "</strong>" +
      '<span class="contact__go">See the feed →</span></a>' +
      "</div>";
    return sec;
  }

  /* full-width scrolling text band; content duplicated for a seamless loop */
  function buildMarquee(words) {
    var sec = el("section", "marquee");
    sec.setAttribute("aria-hidden", "true");
    var run = "";
    for (var i = 0; i < words.length; i++) {
      run += '<span' + (i % 2 ? ' class="on"' : "") + ">" + words[i] + "</span>" +
        '<span>—</span>';
    }
    var track = el("div", "marquee__track");
    track.innerHTML = run + run; /* two copies → -50% loop is seamless */
    sec.appendChild(track);
    return sec;
  }

  /* ============================================================
     PORTFOLIO PAGE — every photograph, sports first, with filters
     generated from whatever tags exist. Add a new tag in photos.js
     and a filter appears here.
     ============================================================ */

  /* ---------- filter panel ----------
     Builds the animated checkbox panel, owns the multi-select state, and
     re-renders the grid it was handed. `source` is the pool of
     photographs it filters; `lead` is a tag whose photographs come first;
     `initial` is a list of tags to start filtered to. */

  function mountFilterPanel(filtersEl, gridEl, source, opts) {
    opts = opts || {};
    var label    = opts.label    || "Filter by subject";
    var allLabel = opts.allLabel || "All photographs";
    var pinned   = opts.pinned   || [];
    var exclude  = opts.exclude  || [];
    var lead     = opts.lead     || null;

    /* tag universe for this pool, alphabetical, with counts. Pinned tags
       always get a row even at zero, so a planned series stays visible. */
    var tagCounts = {};
    source.forEach(function (p) {
      p.tags.forEach(function (t) {
        if (exclude.indexOf(t) !== -1) return;
        tagCounts[t] = (tagCounts[t] || 0) + 1;
      });
    });
    pinned.forEach(function (t) { if (!(t in tagCounts)) tagCounts[t] = 0; });
    var tags = Object.keys(tagCounts).sort();

    /* multi-select state — empty set means "show everything" */
    var selected = new Set();

    var funnel =
      '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true" ' +
      'fill="none" stroke="currentColor" stroke-width="1.5" ' +
      'stroke-linejoin="round"><path d="M1.8 3h12.4l-4.7 5.4V13l-3 1.4V8.4z"/></svg>';
    var caret =
      '<svg viewBox="0 0 10 6" width="10" height="6" aria-hidden="true" ' +
      'fill="none" stroke="currentColor" stroke-width="1.4" ' +
      'stroke-linecap="round" stroke-linejoin="round"><path d="M1 1l4 4 4-4"/></svg>';

    var opts_html = "";
    tags.forEach(function (t, i) {
      opts_html +=
        '<label class="filter-opt" style="--i:' + i + '">' +
        '<input type="checkbox" value="' + t + '">' +
        '<span class="filter-opt__box"></span>' +
        '<span class="filter-opt__name">' + t + "</span>" +
        '<span class="filter-opt__n">' + tagCounts[t] + "</span></label>";
    });

    filtersEl.innerHTML =
      '<span class="filters__summary mono">' + allLabel + "</span>" +
      '<div class="filters__control">' +
      '<button class="filter-toggle" type="button" aria-expanded="false" ' +
      'aria-haspopup="true">' + funnel +
      "<span>Filter</span>" +
      '<span class="filter-toggle__count" hidden></span>' +
      '<span class="filter-toggle__caret">' + caret + "</span></button>" +
      '<div class="filter-menu" role="dialog" aria-label="' + label + '">' +
      '<div class="filter-menu__head"><span class="mono">' + label + "</span>" +
      '<button class="filter-menu__clear" type="button" hidden>Clear</button></div>' +
      '<div class="filter-menu__list">' + opts_html + "</div>" +
      '<button class="filter-menu__apply" type="button"></button>' +
      "</div></div>";

    var toggle     = filtersEl.querySelector(".filter-toggle");
    var menu       = filtersEl.querySelector(".filter-menu");
    var summary    = filtersEl.querySelector(".filters__summary");
    var countBadge = filtersEl.querySelector(".filter-toggle__count");
    var clearBtn   = filtersEl.querySelector(".filter-menu__clear");
    var applyBtn   = filtersEl.querySelector(".filter-menu__apply");

    function openMenu(open) {
      menu.classList.toggle("is-open", open);
      toggle.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", String(open));
    }

    toggle.addEventListener("click", function (e) {
      e.stopPropagation();
      openMenu(!menu.classList.contains("is-open"));
    });
    applyBtn.addEventListener("click", function () { openMenu(false); });
    menu.addEventListener("click", function (e) { e.stopPropagation(); });
    document.addEventListener("click", function () { openMenu(false); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") openMenu(false);
    });

    filtersEl.querySelectorAll(".filter-opt input").forEach(function (cb) {
      cb.addEventListener("change", function () {
        if (cb.checked) selected.add(cb.value);
        else selected.delete(cb.value);
        syncUi();
        renderGrid();
      });
    });

    (opts.initial || []).forEach(function (t) {
      var cb = filtersEl.querySelector('.filter-opt input[value="' + t + '"]');
      if (!cb) return;
      cb.checked = true;
      selected.add(t);
    });
    syncUi();

    clearBtn.addEventListener("click", function () {
      selected.clear();
      filtersEl.querySelectorAll(".filter-opt input").forEach(function (cb) {
        cb.checked = false;
      });
      syncUi();
      renderGrid();
    });

    function syncUi() {
      var n = selected.size;
      countBadge.hidden = n === 0;
      countBadge.textContent = n;
      clearBtn.hidden = n === 0;
      toggle.classList.toggle("is-active", n > 0);
      summary.textContent = n === 0
        ? allLabel
        : Array.from(selected).sort().map(cap).join(", ");
    }

    function renderGrid() {
      gridEl.innerHTML = "";
      var visible = peopleLast(source.filter(function (p) {
        if (selected.size === 0) return true;
        return p.tags.some(function (t) { return selected.has(t); });
      }));
      if (lead) {
        var hasLead = function (p) { return p.tags.indexOf(lead) !== -1; };
        visible = visible.filter(hasLead)
          .concat(visible.filter(function (p) { return !hasLead(p); }));
      }

      applyBtn.textContent = visible.length
        ? "View " + nPhotos(visible.length)
        : "No matches";

      if (!visible.length) {
        gridEl.innerHTML =
          '<div class="archive-empty mono">Nothing matches those filters.</div>';
        return;
      }

      visible.forEach(function (photo, i) {
        var card = photoCard(photo, i, function (idx) {
          openLightbox(visible, idx);
        });
        card.style.animationDelay = (i * 0.04) + "s";
        gridEl.appendChild(card);
      });

      watchMasonry(gridEl);
    }

    renderGrid();
    return renderGrid;
  }

  /* A link like portfolio.html?tag=football opens already filtered, so
     the home page can point straight at one sport. */
  function buildPortfolio() {
    document.getElementById("portfolio-count").textContent =
      nPhotos(PHOTOS.length) + " · " + yearRange();
    var wanted = new URLSearchParams(location.search).getAll("tag");
    mountFilterPanel(
      document.getElementById("filters"),
      document.getElementById("portfolio-grid"),
      PHOTOS,
      { pinned: ["sports"], lead: "sports", initial: wanted }
    );
  }

  function yearRange() {
    var years = PHOTOS.map(function (p) { return p.year; });
    var min = Math.min.apply(null, years);
    var max = Math.max.apply(null, years);
    return min === max ? String(min) : min + "–" + max;
  }

  /* ============================================================
     SPA MODE — used by the single-file shareable build. Both pages
     live in one document inside [data-view] wrappers; nav links
     carry [data-goto] and toggle which view is visible.
     ============================================================ */

  function initSpa() {
    buildAbout();
    buildPortfolio();
    var views = document.querySelectorAll("[data-view]");
    var links = document.querySelectorAll("[data-goto]");

    function show(name) {
      views.forEach(function (v) {
        v.hidden = v.dataset.view !== name;
      });
      links.forEach(function (a) {
        if (a.dataset.goto === name) {
          a.setAttribute("aria-current", "page");
        } else {
          a.removeAttribute("aria-current");
        }
      });
      window.scrollTo(0, 0);
    }

    links.forEach(function (a) {
      a.addEventListener("click", function (e) {
        e.preventDefault();
        show(a.dataset.goto);
      });
    });
    show("home");
  }

  /* ---------- removal requests ----------
     Garrett photographs minors at school events. Someone who does not
     want their child on a public website needs a way to say so that does
     not depend on them finding an email address, and it must not be
     buried. This asks for nothing they might not want to give: every
     field is optional, because demanding ID before someone can ask for a
     photo of their kid to come down gets the request abandoned.

     It emails Garrett; it does not take the photo down by itself. If a
     button could remove a photo, anyone could remove any photo. */

  var removalEl = null;

  function openRemoval(photo) {
    if (!removalEl) buildRemoval();
    removalEl._photo = photo;
    removalEl.classList.remove("is-sent");
    removalEl.querySelector("#rm-which").textContent =
      photo ? photo.title + (photo.location ? " · " + photo.location : "") : "";
    var note = removalEl.querySelector("#rm-status");
    note.className = "co__status mono" + (Mailer.ready() ? "" : " is-warn");
    note.textContent = Mailer.ready() ? "" :
      "Sending isn't switched on — email " + CONTACT.email + " instead.";
    removalEl.classList.add("is-open");
    document.body.style.overflow = "hidden";
  }

  function closeRemoval() {
    removalEl.classList.remove("is-open");
    document.body.style.overflow = "";
  }

  function buildRemoval() {
    removalEl = el("div", "checkout removal");
    removalEl.setAttribute("role", "dialog");
    removalEl.setAttribute("aria-modal", "true");
    removalEl.innerHTML =
      '<div class="checkout__card glass">' +
      '<button class="checkout__close" type="button" aria-label="Close">✕</button>' +
      '<div class="checkout__form">' +
      '<span class="mono">Request removal</span>' +
      '<h3 class="checkout__sum">Ask for this photograph to be taken down</h3>' +
      '<p class="rm__which mono" id="rm-which"></p>' +
      '<p class="rm__lead">If this is a photograph of you or your child and you ' +
      "would rather it were not online, say so and Garrett will take it down. " +
      "You do not have to explain yourself, and you do not have to leave your " +
      "details — but an email lets him confirm once it is gone.</p>" +
      '<label><span class="mono">Your name (optional)</span>' +
      '<input type="text" id="rm-name" autocomplete="name"></label>' +
      '<label><span class="mono">Email, if you want a reply (optional)</span>' +
      '<input type="email" id="rm-email" autocomplete="email"></label>' +
      '<label><span class="mono">Anything you want to add (optional)</span>' +
      '<textarea id="rm-note" rows="3"></textarea></label>' +
      '<button class="checkout__send" id="rm-send" type="button">Send request</button>' +
      '<p class="co__status mono" id="rm-status"></p>' +
      "</div>" +
      '<div class="checkout__done">' +
      '<span class="checkout__tick"><svg viewBox="0 0 52 52" aria-hidden="true">' +
      '<circle class="tick-ring" cx="26" cy="26" r="23" fill="none"/>' +
      '<path class="tick-mark" fill="none" d="M14 27l8 8 16-17"/></svg></span>' +
      "<h3>Sent</h3>" +
      '<p class="checkout__done-note">Garrett has your request and will take ' +
      "the photograph down. If you left an email he will confirm when it is " +
      "done.</p>" +
      "</div></div>";
    document.body.appendChild(removalEl);

    removalEl.querySelector(".checkout__close").addEventListener("click", closeRemoval);
    removalEl.addEventListener("click", function (e) {
      if (e.target === removalEl) closeRemoval();
    });
    removalEl.querySelector("#rm-send").addEventListener("click", submitRemoval);
  }

  function submitRemoval() {
    var photo = removalEl._photo || {};
    var name = removalEl.querySelector("#rm-name").value.trim();
    var email = removalEl.querySelector("#rm-email").value.trim();
    var note = removalEl.querySelector("#rm-note").value.trim();
    var status = removalEl.querySelector("#rm-status");
    var btn = removalEl.querySelector("#rm-send");

    btn.disabled = true;
    status.className = "co__status mono";
    status.textContent = "Sending…";

    Mailer.send({
      subject: "\u26A0\uFE0F REMOVAL REQUEST — " + (photo.title || "a photograph"),
      fromName: "Garrett Photo — Removal request",
      summary: "Someone has asked for a photograph to be taken down.",
      lines: [
        ["Photograph", photo.title || "(unknown)"],
        ["File", photo.src || "(unknown)"],
        ["Location", photo.location || "—"],
        ["From", name || "(not given)"],
        ["Reply to", email || "(not given)"],
        ["Message", note || "(none)"]
      ],
      name: name || "Anonymous",
      email: email || "(no reply address given)"
    }).then(function () {
      removalEl.classList.add("is-sent");
    }).catch(function (err) {
      status.className = "co__status mono is-warn";
      status.textContent = err.message + " Nothing was sent — please email " +
        CONTACT.email + " instead.";
    }).finally(function () { btn.disabled = false; });
  }

  /* ---------- boot ---------- */

  /* Sign-in links for past buyers can land on any page (Supabase falls
     back to the Site URL). Pass them on to My Photos, the only page that
     still reads them. Delete this along with account.html. */
  if (location.hash.indexOf("access_token") > -1) {
    location.replace("/account.html" + location.hash);
  }

  protectImages(document);

  if (page === "about") buildAbout();
  if (page === "portfolio") buildPortfolio();
  if (page === "spa") initSpa();
})();
