/* The home page intro. Plays once per visit after the visitor picks sound or
   muted: an about-me wall of the work, a look through the viewfinder with a
   burst of real photos, the tunnel and the field, then the shutter fires on
   the hero photo and the page unlocks.

   Everything sits on the song's beat grid: 126 BPM, beat k at T(k) seconds,
   k = 0 being the drop. render(t) sets the whole frame for time t; with sound
   on, the audio clock drives it so picture and sound can't drift apart.
   Repeat visits in the same session get only the shutter and the name. */
(function () {
  "use strict";

  var root = document.querySelector("[data-intro]");
  if (!root) return;

  var MUSIC = false;         /* true adds the song (intro.mp3 + tail.mp3, kept out of git until it is cleared for the web) */
  var BEAT = 0.47602;
  function T(k) { return 1.905 + BEAT * k; }
  var END = T(37) + 0.3;
  var cfg = JSON.parse(root.dataset.intro);
  var html = document.documentElement;
  var q = function (s) { return root.querySelector(s); };
  var hero = root.closest(".hero");
  var photo = hero.querySelector("[data-hero-photo]"), shade = hero.querySelector("[data-hero-shade]");
  var copy = hero.querySelector("[data-hero-copy]"), cue = hero.querySelector("[data-hero-cue]");
  var nav = document.querySelector("[data-nav]"), soundBtn = document.querySelector("[data-sound]");
  var reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var seen = false;
  try { seen = sessionStorage.getItem("ge.intro") === "1"; } catch (e) {}

  if (reduced) { root.remove(); return; }

  /* ---------- timing helpers ---------- */
  function clamp(x, a, b) { return Math.max(a, Math.min(b, x)); }
  function seg(t, a, b) { return clamp((t - a) / (b - a), 0, 1); }
  function eo(x) { return 1 - Math.pow(1 - x, 3); }
  function eio(x) { return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; }
  function ei(x) { return x * x * x; }
  function bump(t, a, peak, b) { return t < a || t > b ? 0 : t < peak ? eio(seg(t, a, peak)) : 1 - eio(seg(t, peak, b)); }
  function hash(i, k) { var x = Math.sin(i * 12.9898 + k * 78.233) * 43758.5453; return x - Math.floor(x); }

  /* ---------- the film: tunnel, field, stadium ---------- */
  var canvas = q(".i-film canvas"), ctx = canvas.getContext("2d"), frames = [], spans = [];
  var small = innerWidth < 760 || innerWidth / innerHeight < 0.9;
  var FRAMES = "revamp/intro/" + (small ? "m/" : "d/");
  function size() {
    var d = Math.min(devicePixelRatio || 1, 1.5);
    canvas.width = Math.round(canvas.clientWidth * d); canvas.height = Math.round(canvas.clientHeight * d);
  }
  function framePos(t) {
    for (var i = spans.length - 1; i >= 0; i--) {
      var s = spans[i];
      if (t >= s.t0) return s.f0 + clamp((t - s.t0) / (s.t1 - s.t0), 0, 1) * (s.n - 1);
    }
    return 0;
  }
  function nearest(i) {
    for (var d = 0; d < frames.length; d++) { if (frames[i - d]) return frames[i - d]; if (frames[i + d]) return frames[i + d]; }
    return null;
  }
  function drawFilm(pos) {
    var i = Math.floor(pos), f = pos - i, a = frames[i] || nearest(i), b = frames[i + 1];
    if (!a) return;
    var W = canvas.width, H = canvas.height, s = Math.max(W / a.naturalWidth, H / a.naturalHeight);
    var w = a.naturalWidth * s, h = a.naturalHeight * s;
    ctx.globalAlpha = 1; ctx.drawImage(a, (W - w) / 2, (H - h) / 2, w, h);
    if (b && f > .02) { ctx.globalAlpha = f; ctx.drawImage(b, (W - w) / 2, (H - h) / 2, w, h); ctx.globalAlpha = 1; }
  }

  /* ---------- text ---------- */
  function riseIn(el, p) { el.style.clipPath = "inset(-30% -5% " + (100 - 130 * p) + "% -5%)"; el.style.transform = "translateY(" + (0.35 * (1 - p)) + "em)"; }
  function writeIn(el, p) { el.style.clipPath = "inset(-30% " + (105 - 110 * p) + "% -30% -5%)"; el.style.transform = "translateX(" + (-0.25 * (1 - p)) + "em)"; }
  var beats = Array.prototype.map.call(root.querySelectorAll("[data-beat]"), function (el) {
    var k = el.dataset.beat.split(","), tin = T(+k[0]), tout = T(+k[1]);
    var sans = el.querySelector(".combo__sans"), serif = el.querySelector(".combo__serif");
    return function (t) {
      riseIn(sans, eo(seg(t, tin, tin + .55)));
      writeIn(serif, eio(seg(t, tin + .18, tin + .95)));
      var o = seg(t, tout, tout + .35);
      el.style.opacity = t < tin ? 0 : 1 - o;
      el.style.filter = o > 0 ? "blur(" + (o * 8).toFixed(1) + "px)" : "";
      el.style.transform = "translateY(" + (-24 * eo(o)) + "px)";
    };
  });

  /* ---------- about me ---------- */
  var about = q(".i-about"), wall = q(".i-wall"), tiles = wall.children;
  var words = root.querySelectorAll(".i-slam span"), slamN = q(".i-slam small");
  var aCopy = q(".i-about__copy"), aSans = aCopy.querySelector(".combo__sans"), aSerif = aCopy.querySelector(".combo__serif");
  var aKick = aCopy.querySelector(".kicker"), aLine = q(".i-about__line");
  function renderAbout(t) {
    var on = t > T(0) - .2 && t < T(8) + .1;
    about.style.opacity = on ? eo(seg(t, T(0) - .12, T(0) + .02)) * (1 - seg(t, T(8) - .02, T(8) + .1)) : 0;
    if (!on) return;
    var drift = seg(t, T(0), T(7)), rush = ei(seg(t, T(6.9), T(8)));
    wall.style.transform = "translate(-50%,-50%) rotateX(" + (24 - 10 * drift) + "deg) rotateZ(" + (-9 + 4 * drift) + "deg) translateZ(" +
      (-380 + 300 * eo(drift) + 1250 * rush).toFixed(1) + "px) translateX(" + (-40 * drift).toFixed(1) + "px)";
    wall.style.filter = rush > 0 ? "blur(" + (rush * 14).toFixed(1) + "px) brightness(" + (1 + rush * 2.2).toFixed(2) + ")" : "";
    var kb = Math.floor((t - T(0)) / BEAT), since = t - T(kb);
    for (var i = 0; i < tiles.length; i++) {
      var hit = kb >= 0 && kb < 8 && hash(i, kb) > .82 ? 1 - seg(since, 0, .32) : 0;
      tiles[i].style.filter = "brightness(" + (.5 + .9 * hit).toFixed(2) + ") saturate(" + (.85 + .3 * hit).toFixed(2) + ")";
    }
    for (var w = 0; w < words.length; w++) {
      var a = T(w), live = t >= a && t < T(w + 1), p = seg(t, a, a + .12);
      words[w].style.opacity = live ? (w === 3 ? 1 - seg(t, T(4) - .1, T(4)) : 1) : 0;
      words[w].style.transform = "scale(" + (1.22 - .22 * eo(p)).toFixed(3) + ")";
      words[w].style.filter = p < 1 ? "blur(" + ((1 - p) * 10).toFixed(1) + "px)" : "";
    }
    slamN.style.opacity = t >= T(0) && t < T(4) ? .9 : 0;
    slamN.textContent = "0" + clamp(kb + 1, 1, 4) + " / 04";
    riseIn(aSans, eo(seg(t, T(4), T(4) + .5)));
    writeIn(aSerif, eio(seg(t, T(4.4), T(4.4) + .85)));
    aKick.style.opacity = eo(seg(t, T(4), T(4.6)));
    aLine.style.opacity = eo(seg(t, T(5), T(5.8)));
    var o = seg(t, T(6.7), T(7.2));
    aCopy.style.opacity = t < T(4) ? 0 : 1 - o;
    aCopy.style.filter = o > 0 ? "blur(" + (o * 10).toFixed(1) + "px)" : "";
    aCopy.style.transform = "translateY(" + (-30 * eo(o)) + "px) scale(" + (1 + .08 * o) + ")";
  }

  /* ---------- the viewfinder: focus locks, a burst of real frames ---------- */
  var vf = q(".i-vf"), vfImgs = [], hud = q(".i-hud"), af = q(".i-af"), shotsEl = q(".i-shots b");
  var vfFlash = q(".i-vf__flash"), vfBlack = q(".i-vf__black");
  var SHOTS = [T(9.5), T(10), T(10.5), T(11), T(11.5)];
  function renderVf(t) {
    var on = t > T(8) - .2 && t < T(12) + .08;
    vf.style.opacity = on ? eo(seg(t, T(8) - .06, T(8) + .08)) : 0;
    if (!on) return;
    var idx = 0;
    SHOTS.forEach(function (s) { if (t >= s) idx++; });
    vfImgs.forEach(function (im, i) { im.style.display = i === idx ? "block" : "none"; });
    var img = vfImgs[idx];
    shotsEl.textContent = (cfg.shots - SHOTS.length + idx).toLocaleString("en-US");
    var hunt = seg(t, T(8), T(9)), locked = t >= T(9);
    af.className = "i-af" + (locked ? " lock" : "");
    var jx = locked ? 0 : Math.sin(t * 41) * 16 * (1 - hunt), jy = locked ? 0 : Math.cos(t * 33) * 11 * (1 - hunt);
    var asc = locked ? 1 + .12 * (1 - eo(seg(t, T(9), T(9) + .18))) : 1.45 - .45 * eio(hunt);
    af.style.transform = "translate(" + jx.toFixed(1) + "px," + jy.toFixed(1) + "px) scale(" + asc.toFixed(3) + ")";
    af.style.opacity = locked && t > T(9) + .12 ? (Math.floor((t - T(9)) * 8) % 2 ? .85 : 1) : 1;
    var last = idx ? SHOTS[idx - 1] : -9;
    vfBlack.style.opacity = SHOTS.some(function (s) { return t >= s - .025 && t < s + .035; }) ? 1 : 0;
    vfFlash.style.opacity = (.32 * (1 - seg(t, last, last + .14))).toFixed(3);
    var blur = idx === 0 ? 12 * (1 - eio(seg(t, T(8.3), T(9)))) : 0;
    var sc = idx === 0 ? 1.08 - .08 * eo(seg(t, T(8), T(9))) : 1.035 - .035 * eo(seg(t, last, last + .22));
    var fly = eio(seg(t, T(11.5) + .06, T(12)));
    sc *= 1 + .65 * fly;
    if (img) {
      img.style.transform = "scale(" + sc.toFixed(4) + ")";
      img.style.filter = "blur(" + (blur + 7 * fly).toFixed(1) + "px) brightness(" + (1 + 1.8 * fly).toFixed(2) + ")";
    }
    hud.style.opacity = 1 - seg(t, T(11.5) + .05, T(11.5) + .3);
    hud.style.transform = "scale(" + (1 + .04 * (1 - eo(seg(t, T(8), T(8.6))))) + ")";
  }

  /* ---------- the shutter ---------- */
  var shutter = q(".i-shutter"), irisPath = shutter.querySelector("path"), blades = shutter.querySelector("g");
  function iris(r, rot) {
    var cx = 800, cy = 450, n = 7, pts = [], d = "M-10 -10H1610V910H-10Z", g = "";
    for (var k = 0; k < n; k++) { var a = rot + k * 2 * Math.PI / n; pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
    if (r > 0.5) {
      d += "M" + pts.map(function (p) { return p[0].toFixed(1) + " " + p[1].toFixed(1); }).join("L") + "Z";
      for (k = 0; k < n; k++) {
        var p = pts[k], qq = pts[(k + 1) % n], dx = qq[0] - p[0], dy = qq[1] - p[1], L = Math.hypot(dx, dy) || 1;
        g += '<line x1="' + p[0].toFixed(1) + '" y1="' + p[1].toFixed(1) + '" x2="' + (p[0] - dx / L * 1400).toFixed(1) + '" y2="' + (p[1] - dy / L * 1400).toFixed(1) + '"/>';
      }
    }
    irisPath.setAttribute("d", d); blades.innerHTML = g;
  }

  /* ---------- one frame ---------- */
  var film = q(".i-film"), flash = q(".i-flash"), flare = q(".i-flare");
  var loader = q(".i-loader"), bars = root.querySelectorAll(".i-bar"), skipBtn = q(".i-skip");
  var nameEl = copy.querySelector(".name span"), kick = copy.querySelector(".kicker");
  var role = copy.querySelector(".hero__role"), ctas = copy.querySelector(".hero__ctas");

  function render(t) {
    var lo = eio(seg(t, 1.5, 1.9));
    loader.style.opacity = 1 - lo;
    loader.style.transform = "translateY(" + (-30 * lo) + "px)";
    loader.style.display = t > 1.95 ? "none" : "";

    film.style.opacity = t < T(12) - .05 ? 0 : 1;
    var punch = 1 + .07 * bump(t, T(12) - .1, T(12) + .2, T(13.5)) + .05 * eio(seg(t, T(26.5), T(28)));
    film.style.transform = "scale(" + punch.toFixed(4) + ")";
    if (t >= T(12) - .05 && t < T(28.2)) drawFilm(framePos(t));
    flash.style.opacity = (.95 * bump(t, T(12) - .32, T(12), T(12) + .5)).toFixed(3);

    renderAbout(t);
    renderVf(t);
    beats.forEach(function (b) { b(t); });

    var lb = eio(seg(t, T(27), T(28))) * (1 - eio(seg(t, T(35), T(35) + .7)));
    bars[0].style.height = bars[1].style.height = (10.5 * lb).toFixed(2) + "vh";
    flare.style.opacity = (.85 * bump(t, T(27), T(28), T(28) + .45)).toFixed(3);
    var close = eio(seg(t, T(28), T(29))), open = eo(seg(t, T(30) - .03, T(30) + .72));
    if (t < T(28) || t > T(30) + .72) shutter.style.display = "none";
    else {
      shutter.style.display = "block";
      iris(t < T(30) - .03 ? 980 * (1 - close) : 980 * open, t < T(30) - .03 ? close * 1.3 : 1.3 + open * 1.1);
    }
    photo.style.opacity = t >= T(29.5) ? 1 : 0;
    photo.style.transform = "scale(" + (1.1 - .09 * eo(seg(t, T(30), END))).toFixed(4) + ")";
    shade.style.opacity = t >= T(29.5) ? eo(seg(t, T(30) + .2, T(31.5))) : 0;
    var np = eio(seg(t, T(31), T(34)));
    nameEl.style.clipPath = np >= 1 ? "" : "polygon(0 -20%, " + (122 * np) + "% -20%, " + (122 * np - 22) + "% 120%, -22% 120%)";
    kick.style.opacity = eo(seg(t, T(30.5), T(31.5)));
    var r1 = eo(seg(t, T(34), T(35))), r2 = eo(seg(t, T(34.5), T(35.5)));
    role.style.opacity = r1; role.style.transform = r1 < 1 ? "translateY(" + (18 * (1 - r1)) + "px)" : "";
    ctas.style.opacity = r2; ctas.style.transform = r2 < 1 ? "translateY(" + (18 * (1 - r2)) + "px)" : "";
    nav.style.opacity = eo(seg(t, T(35), T(36)));
    if (cue) cue.style.opacity = eo(seg(t, T(35.5), T(36.5)));
    skipBtn.style.opacity = (eo(seg(t, .6, 1.1)) * (1 - seg(t, T(32), T(33))) * .9).toFixed(3);
  }

  /* ---------- sound: the intro mix, then ~9 s of the crowd settling (and the
     song carrying on quieter when MUSIC is on) so nothing stops dead ---------- */
  var ac = null, master = null, introBuf = null, tailBufs = [], introSrc = null, tailSrcs = [], startAt = 0;
  var soundOn = false;
  function fetchBuf(url) { return fetch(url).then(function (r) { return r.arrayBuffer(); }); }
  var audioFiles = Promise.all([
    fetchBuf(MUSIC ? "revamp/intro/audio/intro.mp3" : "revamp/intro/audio/intro-fx.mp3"),
    fetchBuf("revamp/intro/audio/fx-tail.mp3"),
    MUSIC ? fetchBuf("revamp/intro/audio/tail.mp3") : Promise.resolve(null),
  ]).catch(function () { return [null, null, null]; });

  function setSound(on) {
    soundOn = on;
    if (master) master.gain.setTargetAtTime(on ? 1 : 0, ac.currentTime, .05);
    if (soundBtn) { soundBtn.setAttribute("aria-pressed", on ? "true" : "false"); soundBtn.classList.toggle("is-on", on); }
  }
  function startTail(when) {
    if (!ac || !tailBufs.length || tailSrcs.length) return;
    tailSrcs = tailBufs.map(function (buf) {
      var src = ac.createBufferSource(); src.buffer = buf; src.connect(master); src.start(when); return src;
    });
  }
  function stopTail() {
    tailSrcs.forEach(function (src) { try { src.stop(); } catch (e) {} });
    tailSrcs = [];
  }
  function startAudio(files) {
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC || !files[0]) return Promise.resolve(false);
    ac = new AC(); master = ac.createGain(); master.connect(ac.destination);
    return ac.resume().then(function () {
      return Promise.all(files.map(function (f) { return f ? ac.decodeAudioData(f) : null; }));
    }).then(function (b) {
      introBuf = b[0]; tailBufs = b.slice(1).filter(Boolean);
      startAt = ac.currentTime + .08;
      introSrc = ac.createBufferSource(); introSrc.buffer = introBuf; introSrc.connect(master); introSrc.start(startAt);
      startTail(startAt + introBuf.duration);
      if (soundBtn) soundBtn.hidden = false;
      setSound(true);
      return true;
    }).catch(function () { return false; });
  }

  /* ---------- running it ---------- */
  var clock = null, from = 0, done = false;
  function now() { return ac && startAt ? ac.currentTime - startAt : (performance.now() - clock) / 1000 + from; }
  function loop() {
    if (done) return;
    var t = now();
    render(Math.max(0, Math.min(t, END)));
    if (t >= END) finish(); else requestAnimationFrame(loop);
  }
  function finish() {
    done = true;
    render(END);
    html.classList.remove("intro-on");
    root.classList.add("is-done");
    try { sessionStorage.setItem("ge.intro", "1"); } catch (e) {}
    setTimeout(function () { root.hidden = true; }, 400);
  }
  function skip() {
    if (done) return;
    if (introSrc) { try { introSrc.stop(); } catch (e) {} }
    stopTail();
    if (ac) startTail(ac.currentTime + .02);
    finish();
  }
  function play(at) {
    clock = performance.now(); from = at || 0;
    requestAnimationFrame(loop);
  }

  /* ---------- loading ---------- */
  html.classList.add("intro-on");
  size();
  render(0);
  var bar = q(".i-loader__line i"), num = q(".i-loader__num");
  function progress(p) {
    bar.style.transform = "scaleX(" + p + ")";
    num.textContent = String(Math.round(p * 100)).padStart(3, "0");
  }

  /* Essentials first (the burst photos, the wall, the hero photo, the sound),
     then the film frames eight at a time. The film isn't on screen until
     ~7.6 s in, so Enter appears once the essentials and 60% of the frames are
     here (or after 15 s); the rest keeps loading while the intro plays. */
  function img(src) {
    return new Promise(function (res) {
      var im = new Image();
      im.onload = function () { if (im.decode) im.decode().catch(function () {}); res(im); };
      im.onerror = function () { res(null); };
      im.src = src;
    });
  }
  function load() {
    var t0 = performance.now();
    var essentials = [];
    cfg.burst.forEach(function (src, i) {
      var el = document.createElement("img"); el.alt = ""; el.src = src; vfImgs[i] = el; q(".i-vf__imgs").appendChild(el);
      essentials.push(el.complete ? Promise.resolve() : new Promise(function (r) { el.onload = el.onerror = r; }));
    });
    Array.prototype.forEach.call(tiles, function (el) { essentials.push(el.complete ? Promise.resolve() : new Promise(function (r) { el.onload = el.onerror = r; })); });
    essentials.push(photo.complete ? Promise.resolve() : new Promise(function (r) { photo.onload = photo.onerror = r; }));
    essentials.push(audioFiles);
    if (document.fonts) essentials.push(document.fonts.ready);
    var essN = essentials.length, essDone = 0, total = 1, got = 0;
    function tick() { progress(clamp((essDone / essN) * .35 + (got / total) * .65, 0, 1)); }
    var essAll = Promise.all(essentials.map(function (p) { return p.then(function () { essDone++; tick(); }); }));

    var framesPart = fetch("revamp/intro/intro.json").then(function (r) { return r.json(); }).then(function (c) {
      var tt = [[T(12), T(16)], [T(16), T(22)], [T(22), T(28)]];
      spans = c.segs.map(function (s, i) { return { t0: tt[i][0], t1: tt[i][1], f0: s.start, n: s.n }; });
      total = c.segs[c.segs.length - 1].start + c.segs[c.segs.length - 1].n;
      frames = new Array(total);
      var next = 0;
      return new Promise(function (enough) {
        function worker() {
          if (next >= total) return;
          var i = next++;
          img(FRAMES + String(i + 1).padStart(4, "0") + ".webp").then(function (im) {
            frames[i] = im; got++; tick();
            if (got / total >= .6) enough();
            worker();
          });
        }
        for (var w = 0; w < 8; w++) worker();
      });
    });
    var timeout = new Promise(function (r) { setTimeout(r, 15000); });
    return Promise.race([Promise.all([essAll, framesPart]), essAll.then(function () { return timeout; })]).then(function () {
      progress(1);
    });
  }

  skipBtn.addEventListener("click", skip);
  addEventListener("resize", function () { size(); if (done) return; });
  addEventListener("keydown", function (e) { if (e.key === "Escape" && !done) skip(); });
  if (soundBtn) soundBtn.addEventListener("click", function () {
    if (!ac) {     /* entered muted: sound now starts the song from here */
      audioFiles.then(function (f) {
        var AC = window.AudioContext || window.webkitAudioContext;
        if (!AC || !f[2]) return;
        ac = new AC(); master = ac.createGain(); master.connect(ac.destination);
        ac.resume().then(function () { return ac.decodeAudioData(f[2].slice(0)); }).then(function (b) { tailBufs = [b]; startTail(ac.currentTime + .02); setSound(true); });
      });
      return;
    }
    setSound(!soundOn);
  });
  if (soundBtn && MUSIC) soundBtn.hidden = false;
  document.querySelectorAll("[data-replay]").forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      try { sessionStorage.removeItem("ge.intro"); } catch (er) {}
      location.hash = ""; location.reload();
    });
  });

  if (seen) {
    /* repeat visit: just the shutter firing on the photo and the name */
    load();
    loader.style.display = "none";
    play(T(28));
    return;
  }

  load().then(function () {
    loader.classList.add("is-ready");
    root.querySelectorAll("[data-enter]").forEach(function (b) {
      b.addEventListener("click", function () {
        loader.classList.remove("is-ready");
        if (b.dataset.enter === "sound") {
          audioFiles.then(function (f) { return startAudio(f.map(function (x) { return x && x.slice(0); })); })
            .then(function (ok) { play(0); if (!ok) ac = null; });
        } else play(0);
      }, { once: true });
    });
  });
})();
