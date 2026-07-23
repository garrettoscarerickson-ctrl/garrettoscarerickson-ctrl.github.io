#!/usr/bin/env python3
"""
STUDIO — local manager for the portfolio.

Run:      python3 studio.py
Site:     http://localhost:4173
Studio:   http://localhost:4173/studio

Drop photos in, fill in a title and tags, and Studio handles the rest:
files the image into images/, updates data/photos.json, regenerates
js/photos.js, and every page (filters, sports, home strips) sorts
itself. Local-only: it binds to 127.0.0.1 and is never deployed.
"""

import base64
import json
import os
import re
import shutil
import subprocess
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data", "photos.json")
PHOTOS_JS = os.path.join(ROOT, "js", "photos.js")
IMAGES = os.path.join(ROOT, "images")
REMOVED = os.path.join(IMAGES, "_removed")
PORT = 4173

VALID_FEATURES = ("hero", "panel")


# ---------------- manifest helpers ----------------

def load_photos():
    with open(DATA, "r", encoding="utf-8") as f:
        return json.load(f)


def save_photos(photos):
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(photos, f, indent=2, ensure_ascii=False)
        f.write("\n")
    regenerate_photos_js(photos)


def regenerate_photos_js(photos):
    header = (
        "/* GENERATED FILE - do not edit by hand.\n"
        "   Source of truth: data/photos.json\n"
        "   Edit via Studio (python3 studio.py -> http://localhost:4173/studio)\n"
        "   or edit data/photos.json and run: python3 studio.py --regen */\n\n"
    )
    body = "window.PHOTOS = " + json.dumps(photos, indent=2, ensure_ascii=False) + ";\n"
    with open(PHOTOS_JS, "w", encoding="utf-8") as f:
        f.write(header + body)


def all_tags(photos):
    tags = set()
    for p in photos:
        for t in p.get("tags", []):
            tags.add(t)
    return sorted(tags)


def slugify(title):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "photo"


def unique_src(slug, photos):
    taken = set(p["src"] for p in photos)
    candidate = "images/%s.jpg" % slug
    n = 2
    while candidate in taken or os.path.exists(os.path.join(ROOT, candidate)):
        candidate = "images/%s-%d.jpg" % (slug, n)
        n += 1
    return candidate


def clean_entry(body, photos, existing=None):
    """Validate + normalize an add/update payload into a manifest entry."""
    title = (body.get("title") or "").strip()
    if not title:
        raise ValueError("Title is required")
    tags = sorted(set(
        re.sub(r"[^a-z0-9-]", "", t.strip().lower())
        for t in body.get("tags", []) if t.strip()
    ))
    tags = [t for t in tags if t]
    if not tags:
        raise ValueError("At least one tag is required")
    entry = dict(existing) if existing else {}
    entry["title"] = title
    entry["location"] = (body.get("location") or "New York City").strip()
    try:
        entry["year"] = int(body.get("year") or time.localtime().tm_year)
    except (TypeError, ValueError):
        raise ValueError("Year must be a number")
    orientation = body.get("orientation") or entry.get("orientation") or "landscape"
    entry["orientation"] = "portrait" if orientation == "portrait" else "landscape"
    entry["tags"] = tags
    feature = body.get("feature") or ""
    if feature in VALID_FEATURES:
        entry["feature"] = feature
    else:
        entry.pop("feature", None)
    # only one hero: demote any other hero when this entry claims it
    if entry.get("feature") == "hero":
        for p in photos:
            if p is not existing and p.get("feature") == "hero":
                p.pop("feature", None)
    return entry


def decode_image(data_url):
    m = re.match(r"^data:image/(jpeg|png);base64,(.+)$", data_url or "", re.S)
    if not m:
        raise ValueError("Image must be a base64 JPEG data URL")
    return base64.b64decode(m.group(2))


# ---------------- request handler ----------------

class StudioHandler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, fmt, *args):
        pass  # keep the console quiet

    # -- helpers --

    def send_json(self, obj, status=200):
        payload = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > 80 * 1024 * 1024:
            raise ValueError("Upload too large")
        return json.loads(self.rfile.read(length) or b"{}")

    # -- routes --

    def do_GET(self):
        if self.path.rstrip("/") == "/studio":
            page = STUDIO_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return
        if self.path == "/api/manifest":
            photos = load_photos()
            self.send_json({"photos": photos, "tags": all_tags(photos)})
            return
        super().do_GET()

    def do_POST(self):
        try:
            if self.path == "/api/add":
                self.api_add()
            elif self.path == "/api/update":
                self.api_update()
            elif self.path == "/api/remove":
                self.api_remove()
            elif self.path == "/api/publish":
                self.api_publish()
            else:
                self.send_json({"error": "Unknown endpoint"}, 404)
        except ValueError as e:
            self.send_json({"error": str(e)}, 400)
        except Exception as e:  # keep the server alive on bugs
            self.send_json({"error": "Server error: %s" % e}, 500)

    # -- API implementations --

    def api_add(self):
        body = self.read_body()
        photos = load_photos()
        raw = decode_image(body.get("image"))
        entry = clean_entry(body, photos)
        src = unique_src(slugify(entry["title"]), photos)
        with open(os.path.join(ROOT, src), "wb") as f:
            f.write(raw)
        entry["src"] = src
        # field order matters to nobody but humans reading the JSON
        ordered = {k: entry[k] for k in
                   ("src", "title", "location", "year", "orientation", "tags")}
        if "feature" in entry:
            ordered["feature"] = entry["feature"]
        photos.insert(0, ordered)
        save_photos(photos)
        self.send_json({"ok": True, "photo": ordered})

    def api_update(self):
        body = self.read_body()
        photos = load_photos()
        for p in photos:
            if p["src"] == body.get("src"):
                updated = clean_entry(body, photos, existing=p)
                p.clear()
                p.update(updated)
                save_photos(photos)
                self.send_json({"ok": True, "photo": p})
                return
        raise ValueError("Photo not found: %s" % body.get("src"))

    def api_remove(self):
        body = self.read_body()
        photos = load_photos()
        keep = [p for p in photos if p["src"] != body.get("src")]
        if len(keep) == len(photos):
            raise ValueError("Photo not found: %s" % body.get("src"))
        os.makedirs(REMOVED, exist_ok=True)
        img = os.path.join(ROOT, body["src"])
        if os.path.exists(img):
            dest = os.path.join(
                REMOVED, time.strftime("%Y%m%d-%H%M%S-") + os.path.basename(img))
            shutil.move(img, dest)
        save_photos(keep)
        self.send_json({"ok": True})

    def api_publish(self):
        def run(*cmd):
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                               text=True, timeout=120)
            return r.returncode, (r.stdout + r.stderr).strip()

        code, out = run("git", "rev-parse", "--is-inside-work-tree")
        if code != 0:
            self.send_json({"ok": False, "log":
                            "Not a git repository yet - run deploy.sh first."})
            return
        run("git", "add", "-A")
        code, commit_out = run("git", "commit", "-m",
                               "Update photos via Studio")
        log = commit_out
        if code != 0 and "nothing to commit" in commit_out:
            log = "Nothing new to commit."
        code, remote = run("git", "remote")
        if not remote.strip():
            log += ("\nNo remote configured - run deploy.sh to put the site "
                    "on GitHub Pages, then Publish will push automatically.")
            self.send_json({"ok": True, "log": log})
            return
        code, push_out = run("git", "push")
        log += "\n" + push_out
        self.send_json({"ok": code == 0, "log": log.strip()})


# ---------------- studio UI ----------------

STUDIO_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Studio — Garrett Erickson</title>
<style>
:root {
  --bg:#0a0a0a; --raise:#141414; --ink:#e8e8e6; --dim:#8f8f8c;
  --line:rgba(255,255,255,.14); --soft:rgba(255,255,255,.07);
  --ok:#8fd18f; --bad:#d18f8f;
  --sans:"Helvetica Neue",Helvetica,Arial,sans-serif;
  --mono:ui-monospace,"SF Mono",Menlo,monospace;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);
  padding:0 clamp(1rem,4vw,3rem) 6rem;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.mono{font-family:var(--mono);font-size:.6875rem;letter-spacing:.14em;
  text-transform:uppercase;color:var(--dim)}
header{display:flex;justify-content:space-between;align-items:baseline;
  flex-wrap:wrap;gap:1rem;padding:1.4rem 0;border-bottom:1px solid var(--line)}
header h1{font-size:.9rem;font-weight:600;letter-spacing:.32em;text-transform:uppercase}
header nav{display:flex;gap:1.5rem;align-items:baseline}
header nav a:hover{color:var(--ink)}
h2{font-size:1rem;letter-spacing:.2em;text-transform:uppercase;
  font-weight:600;margin:3rem 0 1.2rem}
#drop{margin-top:2rem;border:1px dashed var(--line);padding:3.5rem 1rem;
  text-align:center;cursor:pointer;transition:border-color .2s,background .2s}
#drop.over,#drop:hover{border-color:var(--dim);background:var(--raise)}
#drop input{display:none}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:1.25rem}
.card{background:var(--raise);border:1px solid var(--soft);padding:1rem;
  display:flex;flex-direction:column;gap:.75rem}
.card img{width:100%;aspect-ratio:3/2;object-fit:cover;display:block;background:#000}
.card label{display:block}
.card label span{display:block;margin-bottom:.25rem}
.card input[type=text],.card input[type=number]{width:100%;background:var(--bg);
  border:1px solid var(--line);color:var(--ink);padding:.5rem .6rem;
  font-family:var(--sans);font-size:.9rem}
.card input:focus{outline:1px solid var(--dim)}
.row{display:flex;gap:.75rem}
.row>*{flex:1}
.tags{display:flex;flex-wrap:wrap;gap:.4rem}
.tag{font-family:var(--mono);font-size:.65rem;letter-spacing:.12em;
  text-transform:uppercase;color:var(--dim);background:none;
  border:1px solid var(--line);border-radius:999px;padding:.32rem .7rem;cursor:pointer}
.tag.on{color:var(--bg);background:var(--ink);border-color:var(--ink)}
.tag.add{border-style:dashed}
select{background:var(--bg);border:1px solid var(--line);color:var(--ink);
  padding:.5rem .4rem;font-family:var(--sans);font-size:.9rem;width:100%}
button.primary{background:var(--ink);color:var(--bg);border:0;padding:.7rem 1rem;
  font-family:var(--mono);font-size:.7rem;letter-spacing:.16em;
  text-transform:uppercase;cursor:pointer}
button.primary:hover{opacity:.85}
button.ghost{background:none;border:1px solid var(--line);color:var(--dim);
  padding:.7rem 1rem;font-family:var(--mono);font-size:.7rem;
  letter-spacing:.16em;text-transform:uppercase;cursor:pointer}
button.ghost:hover{color:var(--ink);border-color:var(--dim)}
.status{font-family:var(--mono);font-size:.7rem;letter-spacing:.08em;
  white-space:pre-wrap;color:var(--dim);margin-top:.75rem}
.status.ok{color:var(--ok)}.status.bad{color:var(--bad)}
.lib-meta{display:flex;justify-content:space-between;align-items:baseline;gap:1rem}
#publish-wrap{margin-top:3rem;border-top:1px solid var(--line);padding-top:1.5rem;
  display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
</style>
</head>
<body>
<header>
  <h1>Studio</h1>
  <nav class="mono">
    <a href="/" target="_blank">Site →</a>
    <a href="/archive.html" target="_blank">Archive →</a>
    <a href="/sports.html" target="_blank">Sports →</a>
  </nav>
</header>

<div id="drop">
  <span class="mono">Drop photos here — or click to choose (JPG / PNG)</span>
  <input type="file" id="file-input" multiple accept="image/jpeg,image/png">
</div>

<div id="pending" class="cards" style="margin-top:1.25rem"></div>

<h2>Library <span class="mono" id="lib-count"></span></h2>
<div id="library" class="cards"></div>

<div id="publish-wrap">
  <button class="primary" id="publish">Publish to the web</button>
  <span class="mono">commits &amp; pushes — needs deploy.sh once first</span>
  <div class="status" id="publish-status"></div>
</div>

<script>
"use strict";
var KNOWN_TAGS = [];

function el(tag, cls, html) {
  var n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  return n;
}

/* ---------- tag chips widget ---------- */
function tagPicker(selected) {
  var wrap = el("div", "tags");
  var state = new Set(selected || []);
  function chip(name) {
    var c = el("button", "tag" + (state.has(name) ? " on" : ""), name);
    c.type = "button";
    c.onclick = function () {
      state.has(name) ? state.delete(name) : state.add(name);
      c.classList.toggle("on", state.has(name));
    };
    return c;
  }
  KNOWN_TAGS.forEach(function (t) { wrap.appendChild(chip(t)); });
  (selected || []).forEach(function (t) {
    if (KNOWN_TAGS.indexOf(t) === -1) wrap.appendChild(chip(t));
  });
  var add = el("button", "tag add", "+ new tag");
  add.type = "button";
  add.onclick = function () {
    var name = prompt("New tag (lowercase, one word — it becomes a filter):");
    if (!name) return;
    name = name.trim().toLowerCase().replace(/[^a-z0-9-]/g, "");
    if (!name || state.has(name)) return;
    state.add(name);
    wrap.insertBefore(chip(name), add);
    wrap.lastChild.previousSibling.classList.add("on");
  };
  wrap.appendChild(add);
  wrap.getTags = function () { return Array.from(state); };
  return wrap;
}

/* ---------- shared card form ---------- */
function metaForm(photo) {
  var f = el("div");
  f.innerHTML =
    '<label><span class="mono">Title</span><input type="text" data-f="title"></label>' +
    '<div class="row" style="margin-top:.6rem">' +
    '<label><span class="mono">Location</span><input type="text" data-f="location"></label>' +
    '<label><span class="mono">Year</span><input type="number" data-f="year"></label>' +
    "</div>" +
    '<div style="margin-top:.6rem"><span class="mono">Tags — pick or add; each becomes a filter</span></div>';
  f.querySelector('[data-f=title]').value = photo.title || "";
  f.querySelector('[data-f=location]').value = photo.location || "New York City";
  f.querySelector('[data-f=year]').value = photo.year || new Date().getFullYear();
  var picker = tagPicker(photo.tags || []);
  picker.style.marginTop = ".4rem";
  f.appendChild(picker);
  var feat = el("label");
  feat.style.marginTop = ".6rem";
  feat.innerHTML = '<span class="mono">Feature on home page</span>' +
    '<select data-f="feature">' +
    '<option value="">— gallery only</option>' +
    '<option value="panel">Parallax panel</option>' +
    '<option value="hero">Hero (replaces current hero)</option></select>';
  feat.querySelector("select").value = photo.feature || "";
  f.appendChild(feat);
  f.read = function () {
    return {
      title: f.querySelector('[data-f=title]').value,
      location: f.querySelector('[data-f=location]').value,
      year: f.querySelector('[data-f=year]').value,
      feature: f.querySelector('[data-f=feature]').value,
      tags: picker.getTags()
    };
  };
  return f;
}

/* ---------- pending uploads ---------- */
var drop = document.getElementById("drop");
var input = document.getElementById("file-input");
drop.onclick = function () { input.click(); };
drop.ondragover = function (e) { e.preventDefault(); drop.classList.add("over"); };
drop.ondragleave = function () { drop.classList.remove("over"); };
drop.ondrop = function (e) {
  e.preventDefault();
  drop.classList.remove("over");
  handleFiles(e.dataTransfer.files);
};
input.onchange = function () { handleFiles(input.files); input.value = ""; };

function handleFiles(files) {
  Array.prototype.forEach.call(files, function (file) {
    if (!/^image\/(jpeg|png)$/.test(file.type)) return;
    prepareFile(file);
  });
}

function prepareFile(file) {
  var img = new Image();
  img.onload = function () {
    var MAX = 2400;
    var scale = Math.min(1, MAX / Math.max(img.width, img.height));
    var canvas = document.createElement("canvas");
    canvas.width = Math.round(img.width * scale);
    canvas.height = Math.round(img.height * scale);
    canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
    var dataUrl = canvas.toDataURL("image/jpeg", 0.88);
    URL.revokeObjectURL(img.src);
    addPendingCard(file, dataUrl,
      canvas.width >= canvas.height ? "landscape" : "portrait");
  };
  img.src = URL.createObjectURL(file);
}

function addPendingCard(file, dataUrl, orientation) {
  var card = el("div", "card");
  var thumb = el("img");
  thumb.src = dataUrl;
  card.appendChild(thumb);
  var guessTitle = file.name.replace(/\.[^.]+$/, "")
    .replace(/[-_]+/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  var form = metaForm({
    title: guessTitle,
    year: new Date(file.lastModified).getFullYear(),
    tags: []
  });
  card.appendChild(form);
  var btnRow = el("div", "row");
  var addBtn = el("button", "primary", "Add to site");
  var cancel = el("button", "ghost", "Discard");
  btnRow.appendChild(addBtn); btnRow.appendChild(cancel);
  card.appendChild(btnRow);
  var status = el("div", "status");
  card.appendChild(status);
  cancel.onclick = function () { card.remove(); };
  addBtn.onclick = function () {
    var meta = form.read();
    meta.orientation = orientation;
    meta.image = dataUrl;
    addBtn.disabled = true;
    status.textContent = "Uploading…"; status.className = "status";
    api("/api/add", meta).then(function (res) {
      if (res.error) throw new Error(res.error);
      status.textContent = "Added ✓ — it's live in the archive" +
        (meta.tags.indexOf("sports") !== -1 ? " and on the Sports page" : "");
      status.className = "status ok";
      addBtn.remove(); cancel.textContent = "Done — clear card";
      loadLibrary();
    }).catch(function (err) {
      status.textContent = err.message; status.className = "status bad";
      addBtn.disabled = false;
    });
  };
  document.getElementById("pending").appendChild(card);
}

/* ---------- library ---------- */
function loadLibrary() {
  fetch("/api/manifest").then(function (r) { return r.json(); }).then(function (data) {
    KNOWN_TAGS = data.tags;
    var lib = document.getElementById("library");
    lib.innerHTML = "";
    document.getElementById("lib-count").textContent =
      "— " + data.photos.length + " photographs";
    data.photos.forEach(function (photo) {
      var card = el("div", "card");
      var meta = el("div", "lib-meta");
      meta.appendChild(el("span", "mono", photo.src));
      if (photo.feature) meta.appendChild(el("span", "mono", "★ " + photo.feature));
      card.appendChild(meta);
      var thumb = el("img");
      thumb.src = "/" + photo.src; thumb.loading = "lazy";
      card.appendChild(thumb);
      var form = metaForm(photo);
      card.appendChild(form);
      var btnRow = el("div", "row");
      var save = el("button", "primary", "Save");
      var remove = el("button", "ghost", "Remove");
      btnRow.appendChild(save); btnRow.appendChild(remove);
      card.appendChild(btnRow);
      var status = el("div", "status");
      card.appendChild(status);
      save.onclick = function () {
        var body = form.read();
        body.src = photo.src;
        status.textContent = "Saving…"; status.className = "status";
        api("/api/update", body).then(function (res) {
          if (res.error) throw new Error(res.error);
          status.textContent = "Saved ✓"; status.className = "status ok";
          loadLibrary();
        }).catch(function (err) {
          status.textContent = err.message; status.className = "status bad";
        });
      };
      remove.onclick = function () {
        if (!confirm('Remove "' + photo.title + '" from the site?\n' +
          "The image file is kept in images/_removed/.")) return;
        api("/api/remove", { src: photo.src }).then(function () { loadLibrary(); });
      };
      lib.appendChild(card);
    });
  });
}

function api(path, body) {
  return fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  }).then(function (r) { return r.json(); });
}

/* ---------- publish ---------- */
document.getElementById("publish").onclick = function () {
  var s = document.getElementById("publish-status");
  s.textContent = "Publishing…"; s.className = "status";
  api("/api/publish", {}).then(function (res) {
    s.textContent = res.log || (res.ok ? "Done" : "Failed");
    s.className = "status " + (res.ok ? "ok" : "bad");
  });
};

loadLibrary();
</script>
</body>
</html>
"""


# ---------------- entry point ----------------

if __name__ == "__main__":
    import sys
    regenerate_photos_js(load_photos())
    if "--regen" in sys.argv:
        print("js/photos.js regenerated from data/photos.json")
        sys.exit(0)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), StudioHandler)
    print("Site:   http://localhost:%d" % PORT)
    print("Studio: http://localhost:%d/studio" % PORT)
    server.serve_forever()
