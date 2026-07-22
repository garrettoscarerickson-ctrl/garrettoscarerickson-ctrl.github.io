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

  /* A photo card <button class="ph"> used by both pages */
  function photoCard(photo, index, onClick) {
    var card = el("button", "ph");
    card.type = "button";
    card.setAttribute("aria-label", "View " + photo.title);
    card.innerHTML =
      '<figure>' +
      '<img loading="lazy" src="' + photo.src + '" alt="' + photo.title + " — " + photo.location + '">' +
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
      '<div class="lightbox__stage"><img alt=""></div>' +
      '<div class="lightbox__bar">' +
      '<div><span class="ph__title" id="lb-title"></span>' +
      '<span class="mono" id="lb-meta" style="margin-left:1.25rem"></span></div>' +
      '<div class="lightbox__nav">' +
      '<span class="mono" id="lb-count"></span>' +
      '<button id="lb-prev">← Prev</button>' +
      '<button id="lb-next">Next →</button>' +
      "</div></div>";
    document.body.appendChild(lb);

    lb.querySelector(".lightbox__close").addEventListener("click", closeLightbox);
    lb.querySelector("#lb-prev").addEventListener("click", function () { stepLightbox(-1); });
    lb.querySelector("#lb-next").addEventListener("click", function () { stepLightbox(1); });
    lb.addEventListener("click", function (e) {
      if (e.target === lb || e.target.classList.contains("lightbox__stage")) closeLightbox();
    });
    document.addEventListener("keydown", function (e) {
      if (!lb.classList.contains("is-open")) return;
      if (e.key === "Escape") closeLightbox();
      if (e.key === "ArrowLeft") stepLightbox(-1);
      if (e.key === "ArrowRight") stepLightbox(1);
    });
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
    lb.querySelector("#lb-title").textContent = photo.title;
    lb.querySelector("#lb-meta").textContent =
      photo.location + " · " + photo.year + " · " + tagLine(photo);
    lb.querySelector("#lb-count").textContent =
      pad2(lightboxIdx + 1) + " / " + pad2(lightboxSet.length);
  }

  /* ---------- parallax ---------- */

  function initParallax() {
    if (reducedMotion) return;
    var layers = Array.prototype.slice.call(
      document.querySelectorAll("[data-parallax] img")
    );
    if (!layers.length) return;

    var ticking = false;

    function update() {
      ticking = false;
      var vh = window.innerHeight;
      layers.forEach(function (img) {
        var rect = img.parentElement.getBoundingClientRect();
        if (rect.bottom < 0 || rect.top > vh) return;
        /* progress: -1 (below viewport) → 1 (above viewport) */
        var progress = (rect.top + rect.height / 2 - vh / 2) / (vh / 2 + rect.height / 2);
        img.style.transform = "translateY(" + (progress * rect.height * 0.12).toFixed(1) + "px)";
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
     HOME PAGE — hero → statement → alternating parallax panels
     and gallery strips, all chosen from the manifest.
     ============================================================ */

  function buildHome() {
    var root = document.getElementById("home-root");
    var hero = PHOTOS.filter(function (p) { return p.feature === "hero"; })[0] || PHOTOS[0];
    var panels = PHOTOS.filter(function (p) { return p.feature === "panel"; });
    var galleryPhotos = PHOTOS.filter(function (p) { return !p.feature; });

    /* hero */
    var heroSec = el("section", "hero");
    heroSec.innerHTML =
      '<div class="hero__img-wrap" data-parallax>' +
      '<img src="' + hero.src + '" alt="' + hero.title + '" fetchpriority="high">' +
      "</div>" +
      '<div class="hero__content">' +
      '<h1 class="hero__title">Garrett<br>Erickson</h1>' +
      '<div class="hero__meta">' +
      '<span class="mono">Architecture &amp; street — New York City</span>' +
      '<span class="mono">' + nPhotos(PHOTOS.length) + " — " + hero.year + "</span>" +
      "</div></div>" +
      '<span class="hero__scroll mono">Scroll ↓</span>';
    root.appendChild(heroSec);

    /* statement */
    var statement = el("section", "statement reveal");
    statement.innerHTML =
      '<span class="mono">01 — About the work</span>' +
      "<p>Concrete, glass and steel — and the small living things moving between them. " +
      "<em>Shot on the street, looking up.</em></p>";
    root.appendChild(statement);

    /* interleave: strip, panel, strip, panel ... */
    var chunks = [];
    var perStrip = Math.ceil(galleryPhotos.length / Math.max(panels.length, 1)) || galleryPhotos.length;
    for (var i = 0; i < galleryPhotos.length; i += perStrip) {
      chunks.push(galleryPhotos.slice(i, i + perStrip));
    }

    var stripNo = 0;
    var max = Math.max(chunks.length, panels.length);
    for (var k = 0; k < max; k++) {
      if (chunks[k]) {
        stripNo++;
        root.appendChild(buildStrip(chunks[k], stripNo));
      }
      if (panels[k]) {
        root.appendChild(buildPanel(panels[k]));
      }
    }

    /* CTA to archive */
    var cta = el("a", "cta reveal");
    cta.href = "archive.html";
    cta.innerHTML =
      '<span class="cta__big">Full Archive</span>' +
      '<span class="mono">All ' + nPhotos(PHOTOS.length) + ", filterable →</span>";
    root.appendChild(cta);

    initParallax();
    initReveal();
  }

  function buildStrip(photos, n) {
    var strip = el("section", "strip");
    var head = el("div", "strip__head");
    head.innerHTML =
      '<span class="mono">' + pad2(n + 1) + " — Selected</span>" +
      '<span class="mono">' + photos.length + " frames</span>";
    strip.appendChild(head);

    var grid = el("div", "strip__grid");
    photos.forEach(function (photo) {
      var globalSet = PHOTOS;
      var card = photoCard(photo, globalSet.indexOf(photo), function (idx) {
        openLightbox(globalSet, idx);
      });
      card.classList.add("reveal");
      grid.appendChild(card);
    });
    strip.appendChild(grid);
    return strip;
  }

  function buildPanel(photo) {
    var isPortrait = photo.orientation === "portrait";
    var panel = el("section", "panel" + (isPortrait ? " panel--portrait" : ""));
    panel.innerHTML =
      '<div class="panel__img-wrap" data-parallax>' +
      '<img loading="lazy" src="' + photo.src + '" alt="' + photo.title + '"></div>' +
      (isPortrait
        ? '<div class="panel__side reveal">' +
          '<span class="mono">' + tagLine(photo) + "</span>" +
          "<h2>" + photo.title + "</h2>" +
          '<span class="mono">' + photo.location + " · " + photo.year + "</span>" +
          "</div>"
        : "") +
      '<div class="panel__caption">' +
      "<h2>" + photo.title + "</h2>" +
      '<span class="mono">' + photo.location + " · " + photo.year + " · " + tagLine(photo) + "</span>" +
      "</div>";
    panel.addEventListener("click", function () {
      openLightbox(PHOTOS, PHOTOS.indexOf(photo));
    });
    panel.style.cursor = "pointer";
    return panel;
  }

  /* ============================================================
     ARCHIVE PAGE — filters generated from whatever tags exist.
     Add a new tag in photos.js and a button appears here.
     ============================================================ */

  function buildArchive() {
    var countEl = document.getElementById("archive-count");
    var filtersEl = document.getElementById("filters");
    var gridEl = document.getElementById("archive-grid");
    var activeTag = "all";

    countEl.textContent =
      nPhotos(PHOTOS.length) + " · New York City · " + yearRange();

    /* union of all tags, alphabetical, with counts */
    var tagCounts = {};
    PHOTOS.forEach(function (p) {
      p.tags.forEach(function (t) { tagCounts[t] = (tagCounts[t] || 0) + 1; });
    });
    var tags = Object.keys(tagCounts).sort();

    function makeBtn(label, value, count) {
      var btn = el("button", "filter-btn");
      btn.type = "button";
      btn.innerHTML = label + (count != null ? "<sup>" + count + "</sup>" : "");
      btn.dataset.tag = value;
      btn.addEventListener("click", function () {
        activeTag = value;
        filtersEl.querySelectorAll(".filter-btn").forEach(function (b) {
          b.classList.toggle("is-active", b.dataset.tag === value);
        });
        renderGrid();
      });
      return btn;
    }

    filtersEl.appendChild(makeBtn("All", "all", PHOTOS.length));
    tags.forEach(function (t) {
      filtersEl.appendChild(makeBtn(t, t, tagCounts[t]));
    });
    filtersEl.querySelector('[data-tag="all"]').classList.add("is-active");

    function renderGrid() {
      gridEl.innerHTML = "";
      var visible = PHOTOS.filter(function (p) {
        return activeTag === "all" || p.tags.indexOf(activeTag) !== -1;
      });

      if (!visible.length) {
        gridEl.innerHTML =
          '<div class="archive-empty mono">Nothing here yet.</div>';
        return;
      }

      visible.forEach(function (photo, i) {
        var card = photoCard(photo, i, function (idx) {
          openLightbox(visible, idx);
        });
        card.style.animationDelay = (i * 0.04) + "s";
        gridEl.appendChild(card);
      });
    }

    renderGrid();
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

    var grid = el("div", "archive-grid");
    sportsPhotos.forEach(function (photo, i) {
      var card = photoCard(photo, i, function (idx) {
        openLightbox(sportsPhotos, idx);
      });
      card.style.animationDelay = (i * 0.04) + "s";
      grid.appendChild(card);
    });
    root.appendChild(grid);
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
    buildHome();
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

  /* ---------- boot ---------- */

  if (page === "home") buildHome();
  if (page === "archive") buildArchive();
  if (page === "sports") buildSports();
  if (page === "spa") initSpa();
})();
