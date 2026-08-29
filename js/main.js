/* ============================================================
   Renders both pages from window.PHOTOS (js/photos.js).
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
      '" alt="' + photo.title + " — " + photo.location + '"></span></span>' +
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
    lb.querySelector(".lightbox__stage img").alt = photo.title;
    lb.querySelector(".lightbox__stage img").draggable = false;
    lb.querySelector("#lb-title").textContent = photo.title;
    lb.querySelector("#lb-meta").textContent =
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
        var s = window.scrollY;
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
     ABOUT PAGE — the front door. Who I am, what it costs, what
     people say, and how to reach me. The photographs live in the
     Archive and Sports pages.
     ============================================================ */

  var CONTACT = {
    email: "garrettoscarerickson@gmail.com",
    instagram: "shot_by_ge"
  };

  /* Prices come from data/shop.json via js/shop-config.js so they can be
     changed in Studio without touching code. The literals below stay as
     the fallback for any page that has not loaded that file. Declared
     here, above first use — `var` hoists the name but not the value, so
     assigning it further down would read as undefined right here. */
  var CFG = window.SHOP_CONFIG || {};

  var PRICING = CFG.tiers || [
    {
      name: "Individual",
      price: "$20",
      unit: "per session",
      lead: "One athlete, one session.",
      items: ["10+ edited photographs",
              "Guaranteed 24-hour delivery",
              "Full-resolution digital files",
              "Personal and social use included"],
      featured: true
    },
    {
      name: "Team",
      price: "$10–15",
      unit: "per athlete",
      lead: "Whole roster, one shoot.",
      items: ["30+ edited photographs guaranteed",
              "One team photograph included",
              "Action and individual frames",
              "Per-athlete galleries"],
      featured: false
    },
    {
      name: "Event & Meets",
      price: "From $75",
      unit: "up to 2 hours",
      lead: "Car meets, games, gatherings.",
      items: ["40+ edited photographs",
              "48-hour delivery",
              "Extra hours billed at $30",
              "Commercial use on request"],
      featured: false
    }
  ];

  /* ---------- payments ----------
     Template only. Nothing is charged and no card data is ever handled
     here. When you're ready: create a Stripe Payment Link (or PayPal
     link) per package, paste it below, flip enabled to true, and the
     booking panel starts sending people to a real checkout. Until then
     the same panel sends a booking request by email. */
  var PAYMENT = {
    /* Slug of the deployed checkout Edge Function. Supabase generated
       this name itself; if it is ever redeployed under another, this is
       the one line to change. */
    checkoutFunction: "rapid-function",

    /* Card checkout via Stripe Payment Links. Needs an account holder who
       is 18+, so this stays off until a parent's account is set up. */
    enabled: true,
    currency: "USD",
    links: {
      /* Stripe Payment Link for store photographs. Create it as a $1
         product with "customers can adjust quantity" switched on. */
      "Photos": "",
      "Individual": "",
      "Team": "",
      "Event & Meets": ""
    },
    /* Peer-to-peer options that work today, including from a teen account.
       Fill in whichever you actually use and leave the rest blank — each
       one that has a value shows up as a button on the booking panel.
       Offer more than one: the sender needs that same app, so a client
       whose parent doesn't use Venmo can still pay without installing
       anything new. */
    venmo: "",        /* handle without the @, e.g. "Garrett-Erickson" */
    cashapp: "",      /* cashtag without the $, e.g. "garrettE"        */
    zelle: "",        /* email or phone shown as an instruction        */
    cash: false       /* offer "pay in person" as a fallback           */
  };

  var ADD_ONS = CFG.addOns || [
    ["Same-day rush delivery", "+$15"],
    ["Additional edited photograph", "$2 each"],
    ["Travel beyond 30 miles", "$0.30 / mile"]
  ];

  function buildAbout() {
    var root = document.getElementById("about-root");
    var hero = PHOTOS.filter(function (p) { return p.feature === "hero"; })[0] || PHOTOS[0];

    /* scroll-progress bar */
    var scrollbar = el("div", "scrollbar");
    scrollbar.innerHTML = "<i></i>";
    document.body.appendChild(scrollbar);

    /* intro name card — pinned, fades away as you scroll past it */
    var introWrap = el("div", "intro-wrap");
    introWrap.innerHTML =
      '<section class="intro">' +
      '<h1 class="intro__name"><span>Garrett</span> <span>Erickson</span></h1>' +
      '<span class="intro__role">Photographer</span>' +
      '<span class="intro__scroll mono">Scroll</span>' +
      "</section>";
    root.appendChild(introWrap);

    /* hero */
    var heroSec = el("section", "hero");
    heroSec.innerHTML =
      '<div class="hero__img-wrap" data-parallax>' +
      '<img src="' + hero.src + '" alt="' + hero.title + '" fetchpriority="high">' +
      "</div>" +
      '<div class="hero__content">' +
      '<div class="hero__meta">' +
      '<span class="mono">Michigan — booking now</span>' +
      '<span class="mono">Architecture · Street · Sports</span>' +
      "</div></div>";
    root.appendChild(heroSec);

    root.appendChild(buildMarquee(
      ["Architecture", "Street", "Portraits", "Sports"]));

    root.appendChild(buildAboutText());
    root.appendChild(buildSelectedWork());
    root.appendChild(buildPricing());
    root.appendChild(buildReviews());
    root.appendChild(buildContact());

    /* CTA into the work */
    var cta = el("a", "cta reveal");
    cta.href = "archive.html";
    cta.innerHTML =
      '<span class="cta__big">See the Work</span>' +
      '<span class="mono">' + nPhotos(PHOTOS.length) + ", filterable →</span>";
    root.appendChild(cta);

    initParallax();
    initReveal();
  }

  function buildAboutText() {
    var sec = el("section", "about reveal");
    sec.innerHTML =
      '<span class="mono about__eyebrow">01 — About</span>' +
      '<div class="about__body">' +
      "<p class=\"about__lead\">I'm a photographer based in Michigan, shooting " +
      "architecture, street and sports.</p>" +
      "<p>Most of my work happens close to home — tennis courts, car meets along " +
      "Woodward, the ordinary geometry of a city block — with a stretch of it made " +
      "in New York. I care about light, structure, and the moment a scene resolves " +
      "into something worth keeping.</p>" +
      "<p>I shoot teams and individuals, and I turn work around fast: individual " +
      "sessions are guaranteed back within 24 hours.</p>" +
      "</div>";
    return sec;
  }

  /* a short taste of the work, since the index is no longer a gallery */
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
      '<a class="mono selected__all" href="archive.html">All ' +
      nPhotos(PHOTOS.length) + " →</a></div>";
    sec.appendChild(grid);
    return sec;
  }

  function buildPricing() {
    var sec = el("section", "pricing reveal");
    var cards = "";
    PRICING.forEach(function (tier) {
      var items = tier.items.map(function (i) {
        return "<li>" + i + "</li>";
      }).join("");
      cards +=
        '<article class="tier' + (tier.featured ? " tier--featured" : "") + '">' +
        (tier.featured ? '<span class="tier__flag mono">Most booked</span>' : "") +
        '<h3 class="tier__name">' + tier.name + "</h3>" +
        '<p class="tier__lead mono">' + tier.lead + "</p>" +
        '<div class="tier__price"><span>' + tier.price + "</span>" +
        '<span class="mono">' + tier.unit + "</span></div>" +
        "<ul class=\"tier__items\">" + items + "</ul>" +
        '<button class="tier__cta" type="button" data-book="' + tier.name +
        '">Book ' + tier.name + "</button>" +
        "</article>";
    });
    var addons = ADD_ONS.map(function (a) {
      return '<div class="addon"><span>' + a[0] + '</span><span class="mono">' +
             a[1] + "</span></div>";
    }).join("");
    sec.innerHTML =
      '<div class="section__head">' +
      '<span class="mono">03 — Rates</span>' +
      '<span class="mono">All prices in USD</span></div>' +
      '<div class="tiers">' + cards + "</div>" +
      '<div class="addons"><span class="mono addons__label">Add-ons</span>' +
      addons + "</div>";

    sec.querySelectorAll("[data-book]").forEach(function (b) {
      b.addEventListener("click", function () { openBooking(b.dataset.book); });
    });
    return sec;
  }

  /* ---------- booking panel ---------- */

  var bookingEl = null;

  function money(n) { return "$" + n.toFixed(2).replace(/\.00$/, ""); }

  function openBooking(tierName) {
    var tier = PRICING.filter(function (t) { return t.name === tierName; })[0];
    if (!tier) return;
    if (!bookingEl) buildBooking();

    var unitPrice = tier.name === "Team" ? 12 : (tier.name === "Individual" ? 20 : 75);
    var perPerson = tier.name === "Team";

    bookingEl.querySelector("#bk-name").textContent = tier.name;
    bookingEl.querySelector("#bk-lead").textContent = tier.lead;
    bookingEl.querySelector("#bk-qty-label").textContent =
      perPerson ? "Athletes" : "Sessions";
    var qty = bookingEl.querySelector("#bk-qty");
    qty.value = perPerson ? 10 : 1;
    qty.min = perPerson ? 8 : 1;

    var addonBox = bookingEl.querySelector("#bk-addons");
    addonBox.innerHTML = ADD_ONS.map(function (a, i) {
      var val = [15, 2, 0][i];
      return '<label class="bk-addon"><input type="checkbox" data-amt="' + val +
        '" data-label="' + a[0] + ' (' + a[1] + ')' +
        '"><span class="bk-addon__box"></span><span>' + a[0] +
        '</span><span class="mono">' + a[1] + "</span></label>";
    }).join("");

    function recalc() {
      var n = Math.max(Number(qty.min), Number(qty.value) || 1);
      var base = unitPrice * n;
      var extra = 0;
      addonBox.querySelectorAll("input:checked").forEach(function (c) {
        extra += Number(c.dataset.amt) * (c.dataset.amt === "2" ? n : 1);
      });
      var total = base + extra;
      bookingEl.querySelector("#bk-base").textContent =
        money(unitPrice) + (perPerson ? " × " + n + " athletes" : " × " + n);
      bookingEl.querySelector("#bk-total").textContent = money(total);
      bookingEl.dataset.total = total;
      bookingEl.dataset.qty = n;
      return total;
    }
    qty.oninput = function () { recalc(); renderPayOptions(tier, perPerson); };
    addonBox.onchange = function () { recalc(); renderPayOptions(tier, perPerson); };
    recalc();

    var pay = bookingEl.querySelector("#bk-pay");
    var link = PAYMENT.links[tier.name];
    if (PAYMENT.enabled && link) {
      pay.textContent = "Continue to payment";
      pay.onclick = function () { window.open(link, "_blank", "noopener"); };
      bookingEl.querySelector("#bk-note").textContent =
        "Secure checkout opens in a new tab.";
    } else {
      /* same one-click send as the store: the request is posted straight
         to Garrett. No mail app opens, the visitor types nothing but
         their name and how to reach them. */
      pay.textContent = "Request this booking";
      pay.onclick = function () { openBookingSend(tier, perPerson); };
      bookingEl.querySelector("#bk-note").textContent = Shop.ordersReady()
        ? "Sends straight to Garrett — he confirms the date and total."
        : "Sending isn't switched on yet (see SETUP.md).";
    }

    renderPayOptions(tier, perPerson);

    bookingEl.classList.add("is-open");
    document.body.style.overflow = "hidden";
  }

  /* peer-to-peer buttons; each opens that app with the amount prefilled */
  function renderPayOptions(tier, perPerson) {
    var box = bookingEl.querySelector("#bk-p2p");
    var total = Number(bookingEl.dataset.total);
    var note = tier.name + " session";
    var opts = [];

    if (PAYMENT.venmo) {
      opts.push({ label: "Venmo", href: "https://venmo.com/" +
        encodeURIComponent(PAYMENT.venmo) + "?txn=pay&amount=" + total +
        "&note=" + encodeURIComponent(note) });
    }
    if (PAYMENT.cashapp) {
      opts.push({ label: "Cash App", href: "https://cash.app/$" +
        encodeURIComponent(PAYMENT.cashapp) + "/" + total });
    }
    if (PAYMENT.zelle) opts.push({ label: "Zelle", hint: PAYMENT.zelle });
    if (PAYMENT.cash) opts.push({ label: "Cash in person", hint: "on the day" });

    if (!opts.length) { box.innerHTML = ""; return; }

    box.innerHTML =
      '<span class="mono booking__p2p-label">Or pay directly</span>' +
      '<div class="booking__p2p-row">' + opts.map(function (o) {
        return o.href
          ? '<a class="booking__p2p-btn" href="' + o.href +
            '" target="_blank" rel="noopener noreferrer">' + o.label + "</a>"
          : '<span class="booking__p2p-btn is-static">' + o.label +
            '<em>' + o.hint + "</em></span>";
      }).join("") + "</div>" +
      '<p class="booking__note mono">Sending by app needs that same app on ' +
      "their end — pick whichever they already use.</p>";
  }

  function closeBooking() {
    bookingEl.classList.remove("is-open");
    document.body.style.overflow = "";
  }

  function buildBooking() {
    bookingEl = el("div", "booking");
    bookingEl.setAttribute("role", "dialog");
    bookingEl.setAttribute("aria-modal", "true");
    bookingEl.innerHTML =
      '<div class="booking__card glass">' +
      '<button class="booking__close" type="button" aria-label="Close">✕</button>' +
      '<span class="mono">Booking</span>' +
      '<h3 class="booking__name" id="bk-name"></h3>' +
      '<p class="booking__lead mono" id="bk-lead"></p>' +
      '<label class="booking__qty"><span class="mono" id="bk-qty-label"></span>' +
      '<input type="number" id="bk-qty" value="1" min="1" max="60"></label>' +
      '<div class="booking__addons" id="bk-addons"></div>' +
      '<div class="booking__sum"><span class="mono">Base</span>' +
      '<span class="mono" id="bk-base"></span></div>' +
      '<div class="booking__total"><span>Estimated total</span>' +
      '<strong id="bk-total"></strong></div>' +
      '<button class="booking__pay" id="bk-pay" type="button"></button>' +
      '<div class="booking__p2p" id="bk-p2p"></div>' +
      '<p class="booking__note mono" id="bk-note"></p>' +
      "</div>";
    document.body.appendChild(bookingEl);
    bookingEl.querySelector(".booking__close").addEventListener("click", closeBooking);
    bookingEl.addEventListener("click", function (e) {
      if (e.target === bookingEl) closeBooking();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && bookingEl.classList.contains("is-open")) closeBooking();
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
      '<span class="mono">04 — Reviews</span>' +
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
      '<div class="section__head"><span class="mono">05 — Contact</span>' +
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
     ARCHIVE PAGE — filters generated from whatever tags exist.
     Add a new tag in photos.js and a button appears here.
     ============================================================ */

  /* ---------- shared filter panel ----------
     Drives both the archive and the sports page: builds the animated
     checkbox panel, owns the multi-select state, and re-renders the grid
     it was handed. `source` is the pool of photographs it filters. */

  function mountFilterPanel(filtersEl, gridEl, source, opts) {
    opts = opts || {};
    var label    = opts.label    || "Filter by subject";
    var allLabel = opts.allLabel || "All photographs";
    var pinned   = opts.pinned   || [];
    var exclude  = opts.exclude  || [];

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

    clearBtn.addEventListener("click", function () {
      selected.clear();
      filtersEl.querySelectorAll(".filter-opt input").forEach(function (cb) {
        cb.checked = false;
      });
      syncUi();
      renderGrid();
    });

    function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

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

  function buildArchive() {
    document.getElementById("archive-count").textContent =
      nPhotos(PHOTOS.length) + " · " + yearRange();
    mountFilterPanel(
      document.getElementById("filters"),
      document.getElementById("archive-grid"),
      PHOTOS,
      { pinned: ["sports"] }
    );
  }

  /* ============================================================
     SPORTS PAGE — shows "coming soon" until any photo carries
     the "sports" tag in photos.js, then it becomes a real
     gallery automatically. Nothing else to wire up.
     ============================================================ */

  function buildSports() {
    var root = document.getElementById("sports-root");
    var sportsPhotos = PHOTOS.filter(function (p) {
      return p.tags.indexOf("sports") !== -1;
    });

    if (!sportsPhotos.length) {
      var soon = el("section", "soon");
      soon.innerHTML =
        '<div class="soon__frame">' +
        '<span class="mono">Next series — in the works</span>' +
        '<h1 class="soon__title">Sports</h1>' +
        '<span class="mono">Coming soon · 00 photographs · ' + new Date().getFullYear() + "</span>" +
        "</div>";
      root.appendChild(soon);
      return;
    }

    /* photos exist — render an archive-style grid */
    var head = el("header", "archive-head");
    head.innerHTML =
      "<h1>Sports</h1>" +
      '<span class="mono">' + nPhotos(sportsPhotos.length) + "</span>";
    root.appendChild(head);

    /* same animated panel as the archive, but scoped to this pool and
       filtering by sport — "sports" itself is every row here, so it is
       excluded from the chips. */
    var filtersEl = el("div", "filters");
    filtersEl.setAttribute("role", "toolbar");
    filtersEl.setAttribute("aria-label", "Filter by sport");
    root.appendChild(filtersEl);

    var grid = el("div", "archive-grid");
    root.appendChild(grid);

    mountFilterPanel(filtersEl, grid, sportsPhotos, {
      label: "Filter by sport",
      allLabel: "All sports",
      /* "sports" is on every row here, and "detail" describes the crop
         rather than the sport — neither works as a filter on this page */
      exclude: ["sports", "detail"]
    });
  }

  function yearRange() {
    var years = PHOTOS.map(function (p) { return p.year; });
    var min = Math.min.apply(null, years);
    var max = Math.max.apply(null, years);
    return min === max ? String(min) : min + "–" + max;
  }

  /* ============================================================
     SPA MODE — used by the single-file shareable build. All three
     pages live in one document inside [data-view] wrappers; nav
     links carry [data-goto] and toggle which view is visible.
     ============================================================ */

  function initSpa() {
    buildAbout();
    buildArchive();
    buildSports();
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

  /* ============================================================
     STORE — photographs for sale, grouped by game
     ============================================================ */

  var PRICE = CFG.photoPrice != null ? CFG.photoPrice : 1;          /* dollars per photograph */

  function buildStore() {
    var root = document.getElementById("store-root");
    var forSale = PHOTOS.filter(function (p) { return p.game; });

    var head = el("header", "archive-head");
    root.appendChild(head);

    if (!forSale.length) {
      head.innerHTML = "<h1>Store</h1>";
      root.appendChild(el("div", "archive-empty mono",
        "Nothing listed yet — photographs appear here once they're assigned to a game."));
      return;
    }

    /* how it works */
    var steps = el("section", "shop-how");
    steps.innerHTML =
      '<div class="shop-how__row">' +
      '<span class="shop-how__step"><b>1</b>Open your game</span>' +
      '<span class="shop-how__step"><b>2</b>Tap the photos you want</span>' +
      '<span class="shop-how__step"><b>3</b>Send your order in one click</span>' +
      "</div>" +
      '<p class="mono shop-how__note">Previews are watermarked. Clean ' +
      "full-resolution files are sent after payment.</p>";
    root.appendChild(steps);

    /* group by game, in manifest order */
    var order = [], groups = {};
    forSale.forEach(function (p) {
      if (!groups[p.game]) { groups[p.game] = []; order.push(p.game); }
      groups[p.game].push(p);
    });

    /* The cart lives out here, not inside a view, so a buyer can pick a
       few frames from one game, open another, and check out with the lot.
       Switching games never reloads the page — that would empty it. */
    var selected = new Set();
    var body = el("div", "shop-body");
    root.appendChild(body);

    function showGames() {
      body.innerHTML = "";
      head.innerHTML =
        "<h1>Store</h1>" +
        '<span class="mono">' + order.length +
        (order.length === 1 ? " game · " : " games · ") +
        nPhotos(forSale.length) + " · $" + PRICE + " each</span>";

      var grid = el("div", "album-grid");
      order.forEach(function (game) {
        var list = groups[game];
        var cover = list[0];
        var card = el("button", "album");
        card.type = "button";
        card.innerHTML =
          '<span class="album__img wm-heavy">' +
          '<img loading="lazy" draggable="false" src="' + shopSrc(cover) +
          '" alt="">' + "</span>" +
          '<span class="album__foot">' +
          "<b>" + game + "</b>" +
          '<span class="mono">' + nPhotos(list.length) + "</span></span>";
        card.addEventListener("click", function () { go(game); });
        grid.appendChild(card);
      });
      body.appendChild(grid);
      protectShopImages(body);
      updateCart();
    }

    function showGame(game) {
      var list = groups[game];
      if (!list) return showGames();
      body.innerHTML = "";
      head.innerHTML =
        "<h1>" + game + "</h1>" +
        '<span class="mono">' + nPhotos(list.length) + " · $" + PRICE +
        " each · pick as many as you like</span>";

      var back = el("button", "album-back");
      back.type = "button";
      back.innerHTML = '<span aria-hidden="true">←</span> All games';
      back.addEventListener("click", function () { go(null); });
      body.appendChild(back);

      var grid = el("div", "shop-grid");
      list.forEach(function (photo) {
        grid.appendChild(shopCard(photo, selected, updateCart));
      });
      body.appendChild(grid);
      protectShopImages(body);
      updateCart();
      window.scrollTo(0, 0);
    }

    /* keep the view in the URL so the phone back gesture does the
       obvious thing instead of leaving the store entirely */
    function go(game, replace) {
      var url = location.pathname + (game ? "?game=" + encodeURIComponent(game) : "");
      try {
        history[replace ? "replaceState" : "pushState"]({ game: game || null }, "", url);
      } catch (e) {}
      game ? showGame(game) : showGames();
    }

    window.addEventListener("popstate", function (e) {
      var g = (e.state && e.state.game) ||
              new URLSearchParams(location.search).get("game");
      g && groups[g] ? showGame(g) : showGames();
    });

    /* sticky cart */
    var cart = el("div", "cart");
    cart.innerHTML =
      '<span class="cart__count mono">No photos selected</span>' +
      '<div class="cart__right">' +
      '<button class="cart__clear" type="button">Clear</button>' +
      '<button class="cart__go" type="button" disabled>Checkout</button>' +
      "</div>";
    document.body.appendChild(cart);

    cart.querySelector(".cart__clear").addEventListener("click", function () {
      selected.clear();
      body.querySelectorAll(".shop-ph.is-picked")
          .forEach(function (c) { c.classList.remove("is-picked"); });
      updateCart();
    });
    cart.querySelector(".cart__go").addEventListener("click", function () {
      openCheckout(selected, body, updateCart);
    });

    function updateCart() {
      var n = selected.size;
      cart.classList.toggle("is-live", n > 0);
      cart.querySelector(".cart__count").textContent = n
        ? n + (n === 1 ? " photo · $" : " photos · $") + (n * PRICE)
        : "No photos selected";
      cart.querySelector(".cart__go").disabled = n === 0;
      cart.querySelector(".cart__go").textContent =
        n ? "Checkout · $" + (n * PRICE) : "Checkout";
    }

    var opening = new URLSearchParams(location.search).get("game");
    go(opening && groups[opening] ? opening : null, true);
  }

  /* a selectable, watermarked store card */
  /* Store previews are their OWN files: downscaled with the watermark
     burned into the pixels (see tools/build_shop_previews.py). The
     portfolio's originals are untouched — nothing is baked into those.
     Serving a separate file is the point: deleting the overlay in
     devtools, or opening the .jpg directly, still gets you a marked
     1100px preview and nothing better. */
  function shopSrc(photo) {
    return "images/shop/" + photo.src.split("/").pop();
  }

  function shopCard(photo, selected, onChange) {
    /* Cards are rebuilt every time a game is opened, so a photo already
       in the cart has to come back already ticked. Otherwise a buyer who
       returns to a game sees nothing selected, taps it again, and
       silently REMOVES it from their cart. */
    var picked = selected.has(photo.src);
    var card = el("button", "shop-ph" +
      (photo.orientation === "portrait" ? " shop-ph--portrait" : "") +
      (picked ? " is-picked" : ""));
    card.type = "button";
    card.setAttribute("aria-pressed", String(picked));
    card.setAttribute("aria-label", "Select " + photo.title);
    var ar = photo.w && photo.h ? ' style="--ar:' + photo.w + "/" + photo.h + '"' : "";
    card.innerHTML =
      '<span class="shop-ph__img wm-heavy"' + ar + '>' +
      '<img loading="lazy" draggable="false" src="' + shopSrc(photo) +
      '" alt="' + photo.title + '">' +
      '<span class="shop-ph__tick" aria-hidden="true">✓</span>' +
      '<span class="shop-ph__flag" role="button" tabindex="0" ' +
      'aria-label="Request removal of ' + esc(photo.title) + '" ' +
      'title="Request removal">!</span>' +
      "</span>" +
      '<span class="shop-ph__foot">' +
      '<span class="ph__title">' + photo.title + "</span>" +
      '<span class="mono">$' + PRICE + "</span></span>";
    /* the flag sits inside the card, so stop the click selecting the
       photo on its way out */
    var flag = card.querySelector(".shop-ph__flag");
    function flagged(e) { e.stopPropagation(); e.preventDefault(); openRemoval(photo); }
    flag.addEventListener("click", flagged);
    flag.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") flagged(e);
    });

    card.addEventListener("click", function () {
      var on = selected.has(photo.src);
      on ? selected.delete(photo.src) : selected.add(photo.src);
      card.classList.toggle("is-picked", !on);
      card.setAttribute("aria-pressed", String(!on));
      onChange();
    });
    return card;
  }

  /* deter casual saving: no context menu, no drag, no iOS long-press sheet */
  function protectShopImages(scope) {
    scope.addEventListener("contextmenu", function (e) {
      if (e.target.closest(".shop-ph")) e.preventDefault();
    });
    scope.addEventListener("dragstart", function (e) { e.preventDefault(); });
  }

  /* ---------- checkout ---------- */

  var checkoutEl = null;

  function openCheckout(selected, root, onChange) {
    if (!checkoutEl) buildCheckout();
    var items = PHOTOS.filter(function (p) { return selected.has(p.src); });
    checkoutEl._kind = "photos";
    checkoutEl.querySelector("#co-date-row").hidden = true;
    checkoutEl.dataset.total = items.length * PRICE;
    checkoutEl.querySelector("#co-summary").textContent =
      items.length + (items.length === 1 ? " photograph · $" : " photographs · $") +
      items.length * PRICE;
    /* Show the card fee up front. Finding an unexplained extra charge on
       the payment screen is how a buyer abandons a checkout. */
    var feeEl = checkoutEl.querySelector("#co-fee");
    if (PAYMENT.enabled) {
      var net = items.length * PRICE * 100;
      var gross = Math.ceil((net + 30) / (1 - 0.029));
      feeEl.textContent = "Card processing adds " + money((gross - net) / 100) +
        " — " + money(gross / 100) + " total.";
      feeEl.hidden = false;
    } else {
      feeEl.hidden = true;
    }
    var list = checkoutEl.querySelector("#co-items");
    list.innerHTML = items.map(function (i) {
      return '<li><span>' + i.title + "</span><span class=\"mono\">" +
             i.game + "</span></li>";
    }).join("");

    var note = checkoutEl.querySelector("#co-status");
    note.textContent = Shop.ordersReady()
      ? ""
      : "Ordering isn't switched on yet — see SETUP.md. Nothing will send.";
    note.className = "co__status mono" + (Shop.ordersReady() ? "" : " is-warn");

    /* No sign-in before paying. Every field between wanting a photo and
       paying for it is somewhere a buyer stops, and an account is not
       needed to buy — the delivery is addressed by the email they type,
       so signing in later reaches the same files. Offered afterwards. */
    checkoutEl.querySelector("#co-acct").hidden = true;
    /* When payment is on, the button leads to paying — saying "Send
       order" and then revealing a Pay button afterwards reads as though
       the order is finished, and buyers stop there. */
    checkoutEl.querySelector("#co-send").textContent = PAYMENT.enabled
      ? "Continue to payment · " + money(Math.ceil((items.length * PRICE * 100 + 30) / 0.971) / 100)
      : "Send order";
    checkoutEl.classList.remove("is-sent");
    checkoutEl.classList.add("is-open");
    document.body.style.overflow = "hidden";
    checkoutEl._items = items;
    checkoutEl._selected = selected;
    checkoutEl._root = root;
    checkoutEl._onChange = onChange;
  }


  /* The booking request rides the exact same rails as a photo order:
     one button, sent in the background, tick animation, then chat.
     No mail app, nothing for the visitor to copy or paste. */
  function openBookingSend(tier, perPerson) {
    if (!checkoutEl) buildCheckout();
    var n = Number(bookingEl.dataset.qty) || 1;
    var total = Number(bookingEl.dataset.total) || 0;

    var lines = [
      ["Package", tier.name],
      [perPerson ? "Athletes" : "Sessions", String(n)],
      ["Estimated total", money(total)]
    ];
    bookingEl.querySelectorAll("#bk-addons input:checked")
      .forEach(function (c) {
        lines.push(["Add-on", c.dataset.label || c.value || "yes"]);
      });

    checkoutEl._kind = "booking";
    checkoutEl._tier = tier;
    checkoutEl._lines = lines;
    checkoutEl.dataset.total = total;
    checkoutEl.querySelector("#co-summary").textContent =
      tier.name + " · " + money(total);
    checkoutEl.querySelector("#co-items").innerHTML = lines.map(function (l) {
      return "<li><span>" + l[0] + '</span><span class="mono">' + l[1] +
             "</span></li>";
    }).join("");
    checkoutEl.querySelector("#co-date-row").hidden = false;
    checkoutEl.querySelector("#co-acct").hidden = true;

    var note = checkoutEl.querySelector("#co-status");
    note.textContent = Shop.ordersReady()
      ? ""
      : "Sending isn't switched on yet — see SETUP.md. Nothing will send.";
    note.className = "co__status mono" + (Shop.ordersReady() ? "" : " is-warn");

    checkoutEl.classList.remove("is-sent");
    checkoutEl.classList.add("is-open");
    document.body.style.overflow = "hidden";
  }

  /* Signing in is asked for HERE and nowhere else. Browsing, the archive,
     reviews and removal requests all stay open — a login in front of the
     photographs would cost far more sales than it saves. It earns its
     place at checkout because it is what lets someone come back for their
     files months later instead of hunting for a lost email. */
  function paintAccountGate() {
    var box = checkoutEl.querySelector("#co-acct");
    if (!window.Account || !Account.ready()) { box.hidden = true; return; }
    box.hidden = false;

    var who = Account.email();
    if (who) {
      box.className = "checkout__acct is-in";
      box.innerHTML = '<span class="mono">Signed in · ' + esc(who) + "</span>" +
        '<span class="mono checkout__acct-sub">Your files will wait for you at ' +
        'garrettphoto.store/account</span>';
      var f = checkoutEl.querySelector("#co-email");
      if (f && !f.value) f.value = who;
      return;
    }

    box.className = "checkout__acct";
    box.innerHTML =
      '<span class="mono">Sign in so your photographs are saved</span>' +
      '<p class="checkout__acct-sub">No password. We email you a one-time link. ' +
      "This is what lets you re-download your files any time instead of " +
      "digging for an old email.</p>" +
      '<div class="checkout__acct-row">' +
      '<input type="email" id="co-acct-email" placeholder="you@example.com" ' +
      'autocomplete="email" aria-label="Email for sign-in">' +
      '<button type="button" id="co-acct-go">Send link</button></div>' +
      '<p class="checkout__acct-msg mono" id="co-acct-msg"></p>';

    box.querySelector("#co-acct-go").addEventListener("click", function () {
      var addr = box.querySelector("#co-acct-email").value.trim();
      var msg = box.querySelector("#co-acct-msg");
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(addr)) {
        msg.textContent = "Add an email first."; return;
      }
      msg.textContent = "Sending…";
      Account.signIn(addr, location.origin + "/account.html")
        .then(function () {
          msg.innerHTML = "<b>Check your email</b> — the link signs you in. " +
            "You can finish this order now either way.";
        })
        .catch(function (err) { msg.textContent = err.message; });
    });
  }

  /* Sends the buyer to Stripe carrying their order code, so the webhook
     can tie the payment back to exactly which photographs were bought.
     Hidden entirely until a payment link exists — a dead "Pay now"
     button is worse than none. */
  /* Asks the Edge Function for a Stripe session and goes there. The
     amount is computed server-side from the saved order — a total the
     page could name is a total a buyer could edit. */
  function goToPayment(code) {
    var rb = window.REVIEW_BACKEND || {};
    return fetch(rb.supabaseUrl.replace(/\/$/, "") + "/functions/v1/" +
                 (PAYMENT.checkoutFunction || "rapid-function"), {
      method: "POST",
      headers: {
        "apikey": rb.supabaseKey,
        "Authorization": "Bearer " + rb.supabaseKey,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ code: code })
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok || !j.url) {
          throw new Error(j.detail || j.error || "Couldn't start checkout.");
        }
        window.location.href = j.url;
      });
    });
  }

  function paintPayButton(info) {
    var a = checkoutEl.querySelector("#co-pay");
    if (!info || !PAYMENT.enabled) { a.hidden = true; return; }
    a.hidden = false;
    a.textContent = "Pay " + money(info.total) + " now";
    a.removeAttribute("href");

    /* The amount is worked out server-side from the saved order, not
       here — a price the page could name is a price a buyer could edit.
       The card fee is added there too, since it is mostly a flat 30c and
       so cannot be expressed as a per-photo markup. */
    a.onclick = function (e) {
      e.preventDefault();
      a.textContent = "Opening checkout…";
      var rb = window.REVIEW_BACKEND || {};
      /* Supabase auto-named this one on deploy and its slug cannot be
         changed afterwards — renaming the function only relabels it. The
         URL is what matters, so it is pinned here rather than fought. */
      fetch(rb.supabaseUrl.replace(/\/$/, "") + "/functions/v1/" +
            (PAYMENT.checkoutFunction || "rapid-function"), {
        method: "POST",
        headers: {
          "apikey": rb.supabaseKey,
          "Authorization": "Bearer " + rb.supabaseKey,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ code: info.code })
      }).then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          if (!r.ok || !j.url) throw new Error(j.error || "Couldn't start checkout.");
          window.location.href = j.url;
        });
      }).catch(function (err) {
        a.textContent = "Pay " + money(info.total) + " now";
        var note = checkoutEl.querySelector("#co-status");
        note.className = "co__status mono is-warn";
        note.textContent = err.message + " You can still pay in the chat.";
      });
    };
  }

  function closeCheckout() {
    checkoutEl.classList.remove("is-open");
    document.body.style.overflow = "";
  }

  function buildCheckout() {
    checkoutEl = el("div", "checkout");
    checkoutEl.setAttribute("role", "dialog");
    checkoutEl.setAttribute("aria-modal", "true");
    checkoutEl.innerHTML =
      '<div class="checkout__card glass">' +
      '<button class="checkout__close" type="button" aria-label="Close">✕</button>' +
      '<div class="checkout__form">' +
      '<span class="mono">Your order</span>' +
      '<h3 class="checkout__sum" id="co-summary"></h3>' +
      '<ul class="checkout__items" id="co-items"></ul>' +
      '<div class="checkout__acct" id="co-acct"></div>' +
      '<label><span class="mono">Your name <b class="req">required</b></span>' +
      '<input type="text" id="co-name" autocomplete="name" required></label>' +
      '<label><span class="mono">Your email <b class="req">required</b></span>' +
      '<input type="email" id="co-email" autocomplete="email" required>' +
      '<span class="field-note">Your photographs are sent here, and it\'s ' +
      "the account you sign in with to download them again later.</span></label>" +
      '<label id="co-date-row" hidden><span class="mono">Preferred date '
        + 'and location</span>' +
      '<input type="text" id="co-date" placeholder="e.g. Fri Sept 12, '
        + 'Country Day"></label>' +
      '<label><span class="mono">Anything I should know (optional)</span>' +
      '<textarea id="co-note" rows="2"></textarea></label>' +
      '<p class="checkout__fee mono" id="co-fee"></p>' +
      '<p class="checkout__licence">Personal use only. These photographs may ' +
      "not be used commercially — no advertising, resale, merchandise, or " +
      "business promotion — without written permission.</p>" +
      '<button class="checkout__send" id="co-send" type="button">Send order</button>' +
      '<p class="co__status mono" id="co-status"></p>' +
      "</div>" +
      '<div class="checkout__done">' +
      '<span class="checkout__tick"><svg viewBox="0 0 52 52" aria-hidden="true">' +
      '<circle class="tick-ring" cx="26" cy="26" r="23" fill="none"/>' +
      '<path class="tick-mark" fill="none" d="M14 27l8 8 16-17"/></svg></span>' +
      "<h3>Sent</h3>" +
      '<p class="checkout__done-note">Garrett will reach you shortly to finish ' +
      "the sale.</p>" +
      '<div class="checkout__code" id="co-code-box">' +
      '<span class="mono">Your chat code</span>' +
      '<b id="co-code"></b>' +
      '<span class="checkout__code-note">Keep this. If you close the chat, ' +
      'reopen it any time at garrettphoto.store/chat</span>' +
      "</div>" +
      '<a class="checkout__pay" id="co-pay" target="_blank" rel="noopener" hidden>Pay now</a>' +
      '<button class="checkout__chat" id="co-chat" type="button">Open chat</button>' +
      "</div></div>";
    document.body.appendChild(checkoutEl);

    checkoutEl.querySelector(".checkout__close").addEventListener("click", closeCheckout);
    checkoutEl.addEventListener("click", function (e) {
      if (e.target === checkoutEl) closeCheckout();
    });
    checkoutEl.querySelector("#co-send").addEventListener("click", submitOrder);
    checkoutEl.querySelector("#co-chat").addEventListener("click", function () {
      closeCheckout();
      openChat(checkoutEl._room, "customer");
    });
  }

  function submitOrder() {
    var name = checkoutEl.querySelector("#co-name").value.trim();
    var email = checkoutEl.querySelector("#co-email").value.trim();
    var note = checkoutEl.querySelector("#co-note").value.trim();
    var status = checkoutEl.querySelector("#co-status");
    var btn = checkoutEl.querySelector("#co-send");

    if (!name) { status.textContent = "Add your name."; return; }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      status.textContent = "Add an email Garrett can reply to."; return;
    }

    var room = Shop.roomId();
    checkoutEl._room = room;
    var chatUrl = Shop.chatReady()
      ? Shop.roomUrl(room)
      : "";

    btn.disabled = true;
    status.className = "co__status mono";
    status.textContent = "Sending…";

    var booking = checkoutEl._kind === "booking";
    var when = booking
      ? checkoutEl.querySelector("#co-date").value.trim() : "";
    var total = Number(checkoutEl.dataset.total);
    var order = booking
      ? {
          subject: "\uD83D\uDEA8 Booking request — " +
                   checkoutEl._tier.name + " — " + name,
          summary: "Booking request for " + checkoutEl._tier.name,
          lines: checkoutEl._lines.concat(when ? [["When / where", when]] : []),
          total: total
        }
      : {
          subject: "\uD83D\uDEA8 Shop order — " + name + " — " +
                   checkoutEl._items.length +
                   (checkoutEl._items.length === 1 ? " photo" : " photos") +
                   ", " + money(total),
          summary: checkoutEl._items.length + " photo(s), total " + money(total),
          items: checkoutEl._items,
          total: total
        };
    order.name = name; order.email = email; order.note = note;
    order.account = (window.Account && Account.email()) || "(not signed in)";
    order.chatUrl = chatUrl;
    order.fromName = booking ? "Garrett Photo Booking" : "Garrett Photo Store";
    order.room = room;

    Shop.sendOrder(order).then(function () {
      var paying = !booking && PAYMENT.enabled;
      /* Don't show the "Sent — Garrett will reach you shortly" panel when
         payment is next. It reads as the order being finished, and the
         redirect that follows looks like the page jumping for no reason.
         The panel is for the fallback path only. */
      if (!paying) checkoutEl.classList.add("is-sent");
      chatName = name;
      checkoutEl.querySelector("#co-code").textContent = room;
      rememberMyRoom(room, name);

      /* The order row must exist before Stripe is asked for a session —
         the amount is read from it, not from the browser. So wait for the
         save rather than firing both off together. */
      var saved = (!booking && window.ShopOrders)
        ? ShopOrders.save({
            code: room, email: email, name: name, total: total,
            items: checkoutEl._items.map(function (i) {
              return { src: i.src, title: i.title, game: i.game };
            })
          })
        : Promise.resolve(false);

      if (paying) {
        var status = checkoutEl.querySelector("#co-status");
        status.className = "co__status mono";
        status.textContent = "Taking you to payment…";
        saved.then(function (ok) {
          if (!ok) throw new Error("Couldn't save the order.");
          return goToPayment(room);
        }).catch(function (err) {
          /* Fall back to the chat flow rather than stranding them: the
             order email has already reached Garrett either way. */
          checkoutEl.classList.add("is-sent");
          paintPayButton({ code: room, email: email,
                           count: checkoutEl._items.length, total: total });
          var note = checkoutEl.querySelector("#co-status");
          note.className = "co__status mono is-warn";
          note.textContent = err.message + " Your order reached Garrett — " +
            "use the button below to pay, or sort it out in the chat.";
        });
      } else {
        paintPayButton(booking ? null : {
          code: room, email: email, count: checkoutEl._items.length, total: total
        });
      }
      if (!booking) {
        checkoutEl._selected.clear();
        checkoutEl._root.querySelectorAll(".shop-ph.is-picked")
          .forEach(function (c) { c.classList.remove("is-picked"); });
        checkoutEl._onChange();
      } else if (bookingEl) {
        bookingEl.classList.remove("is-open");
      }
      if (Shop.chatReady()) {
        Shop.chatSend(room, "system", name + " — " + order.summary)
          .catch(function () {});
      }
    }).catch(function (err) {
      status.className = "co__status mono is-warn";
      status.textContent = err.message +
        " Nothing was sent — email Garrettoscarerickson@gmail.com instead.";
    }).finally(function () { btn.disabled = false; });
  }

  /* A buyer who closes the chat has no way back in — they never made an
     account, and there is nothing to make one against. So their own
     browser holds the room for them: come back to the store and there is
     a button waiting. The code on the receipt covers the other case,
     where they return on a different device. */
  var MY_ROOM = "gep-my-room";

  function rememberMyRoom(room, name) {
    try {
      localStorage.setItem(MY_ROOM, JSON.stringify({
        room: room, name: name, at: Date.now()
      }));
    } catch (e) {}
  }

  function myRoom() {
    try {
      var v = JSON.parse(localStorage.getItem(MY_ROOM) || "null");
      if (!v || !v.room) return null;
      /* messages only live ~12h, so a older room would open empty and
         read as broken. Better to offer nothing than an empty room. */
      if (Date.now() - (v.at || 0) > 12 * 60 * 60 * 1000) {
        localStorage.removeItem(MY_ROOM);
        return null;
      }
      return v;
    } catch (e) { return null; }
  }

  function mountResume(root) {
    var mine = myRoom();
    if (!mine) return;
    var bar = el("button", "resume");
    bar.type = "button";
    bar.innerHTML = '<span class="resume__dot"></span>' +
      '<span>You have a conversation open with Garrett</span>' +
      '<span class="resume__go mono">Reopen chat</span>';
    bar.addEventListener("click", function () {
      chatName = mine.name || "";
      openChat(mine.room, "customer");
    });
    root.insertBefore(bar, root.firstChild);
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
    note.className = "co__status mono" + (Shop.ordersReady() ? "" : " is-warn");
    note.textContent = Shop.ordersReady() ? "" :
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

    Shop.sendOrder({
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
      email: email || "(no reply address given)",
      total: 0
    }).then(function () {
      removalEl.classList.add("is-sent");
    }).catch(function (err) {
      status.className = "co__status mono is-warn";
      status.textContent = err.message + " Nothing was sent — please email " +
        CONTACT.email + " instead.";
    }).finally(function () { btn.disabled = false; });
  }

  /* ---------- chat ---------- */

  var chatEl = null, chatRoom = null, chatWho = "customer", chatTimer = null;
  var chatName = "", chatStop = null, chatSeen = {};

  function openChat(room, who) {
    if (!room) return;
    chatRoom = room; chatWho = who || "customer";
    if (!chatEl) buildChat();
    chatEl.classList.add("is-open");
    chatEl.querySelector("#chat-who").textContent =
      chatWho === "seller" ? "You are replying as Garrett" : "Chat with Garrett";
    chatSeen = {};
    pullChat();

    /* prefer the live stream; only fall back to polling if there isn't
       one, because polling a rate-limited service throttles the buyer */
    clearInterval(chatTimer);
    if (chatStop) { chatStop(); chatStop = null; }
    chatStop = Shop.chatSubscribe(chatRoom, function (m) {
      if (m.id && chatSeen[m.id]) return;
      if (m.id) chatSeen[m.id] = 1;
      appendChat(m);
    });
    if (!chatStop) chatTimer = setInterval(pullChat, 3000);
  }

  function appendChat(m) {
    var log = chatEl.querySelector("#chat-log");
    var empty = log.querySelector(".chat__err");
    if (empty) empty.remove();
    var cls = m.who === chatWho ? "is-mine" : (m.who === "system" ? "is-sys" : "");
    log.insertAdjacentHTML("beforeend",
      '<div class="chat__msg ' + cls + '">' + esc(m.body) + "</div>");
    log.scrollTop = log.scrollHeight;
  }

  function closeChat() {
    chatEl.classList.remove("is-open");
    clearInterval(chatTimer);
    if (chatStop) { chatStop(); chatStop = null; }
  }

  function buildChat() {
    chatEl = el("div", "chat glass");
    chatEl.innerHTML =
      '<div class="chat__head"><span class="mono" id="chat-who"></span>' +
      '<button class="chat__close" type="button" aria-label="Close chat">✕</button></div>' +
      '<div class="chat__log" id="chat-log"></div>' +
      '<form class="chat__form" id="chat-form">' +
      '<input type="text" id="chat-input" placeholder="Write a message…" autocomplete="off">' +
      '<button type="submit">Send</button></form>';
    document.body.appendChild(chatEl);
    chatEl.querySelector(".chat__close").addEventListener("click", closeChat);
    chatEl.querySelector("#chat-form").addEventListener("submit", function (e) {
      e.preventDefault();
      var input = chatEl.querySelector("#chat-input");
      var text = input.value.trim();
      if (!text) return;
      input.value = "";
      Shop.chatSend(chatRoom, chatWho, text)
        .then(function () {
          /* nothing notifies Garrett of a chat message, so the customer's
             first one pings the channel he actually watches */
          if (chatWho === "customer") Shop.chatNotify(chatRoom, chatName, text);
          if (!chatStop) return pullChat();
        })
        .catch(function (err) {
          chatEl.querySelector("#chat-log").insertAdjacentHTML("beforeend",
            '<p class="chat__err mono">' + err.message + "</p>");
        });
    });
  }

  function pullChat() {
    var log = chatEl.querySelector("#chat-log");
    if (!Shop.chatReady()) {
      log.innerHTML = '<p class="chat__err mono">Chat isn\'t switched on yet — ' +
        "see SETUP.md. Your order was still sent.</p>";
      return;
    }
    Shop.chatHistory(chatRoom).then(function (rows) {
      rows.forEach(function (m) { if (m.id) chatSeen[m.id] = 1; });
      log.innerHTML = rows.map(function (m) {
        var cls = m.who === chatWho ? "is-mine" : (m.who === "system" ? "is-sys" : "");
        return '<div class="chat__msg ' + cls + '">' + esc(m.body) + "</div>";
      }).join("") || '<p class="chat__err mono">No messages yet.</p>';
      log.scrollTop = log.scrollHeight;
    });
  }

  /* seller opens ?room=…&as=seller from the order email */
  function maybeOpenSellerChat() {
    var q = new URLSearchParams(location.search);
    var room = q.get("room");
    if (room) openChat(room, q.get("as") === "seller" ? "seller" : "customer");
  }

  /* ---------- account page ---------- */

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
            /* The watermarked store preview doubles as the thumbnail:
               already public, already tiny, and it identifies the photo
               without needing a signed link just to draw a 60px image. */
            /* The thumbnail is the WATERMARKED preview, so long-pressing
               it saves the wrong file — and it looks exactly like the one
               they paid for. Someone will try. Make it unsaveable so the
               only route to a photograph is the Open button. */
            var thumb = d.object_key
              ? '<span class="delivery__thumb wm-block"><img src="images/shop/' +
                esc(d.object_key) + '" alt="" loading="lazy" draggable="false">' +
                "</span>"
              : "";
            return '<li class="delivery">' + thumb +
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

  /* ---------- boot ---------- */

  /* A sign-in link can land anywhere. Supabase falls back to the Site URL
     when a redirect is not in its allow-list, so the tokens arrive on
     whatever page that is — and a page not looking for them drops them,
     leaving someone who did everything right still signed out with no
     explanation. Catch them wherever they land and carry on to the
     account page. */
  if (location.hash && location.hash.indexOf("access_token") > -1 &&
      window.Account && document.body.dataset.page !== "account") {
    Account.absorbRedirect().then(function () {
      location.replace("/account.html");
    });
  }

  /* Flag a signed-in buyer so the nav can show it. Their photographs are
     the reason they came back; making them hunt for an old email to find
     them is the difference between a repeat customer and a lost one. */
  if (window.Account && Account.email()) {
    document.body.classList.add("is-signed-in");
  }

  protectImages(document);

  if (page === "about") buildAbout();
  if (page === "archive") buildArchive();
  if (page === "sports") buildSports();
  if (page === "store") {
    buildStore();
    mountResume(document.getElementById("store-root"));
    maybeOpenSellerChat();
  }
  if (page === "account") buildAccount();
  if (page === "spa") initSpa();
})();
