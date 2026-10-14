#!/usr/bin/env python3
"""
STUDIO — local manager for the portfolio.

Run:      python3 studio.py
Site:     http://localhost:4173
Studio:   http://localhost:4173/studio

Drop photos in, fill in a title and tags, and Studio handles the rest:
files the image into images/, updates data/photos.json, regenerates
js/photos.js, and every page (portfolio filters, home strips) sorts
itself. Local-only: it binds to 127.0.0.1 and is never deployed.

The Bookings tab is the one part of Studio that never touches the site:
it is a private diary of who is booked, kept in data/bookings.json.
"""

import base64
import glob
import hashlib
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
THUMBS = os.path.join(IMAGES, "thumbs")
HOME_JSON = os.path.join(ROOT, "data", "home.json")
THUMB_EDGE = 600        # long edge; the portfolio grid shows these, the lightbox the full file
PORT = 4173

VALID_FEATURES = ("hero", "panel")

# the home page is built from data/home.json by tools/home_page.py
import sys as _sys
_sys.path.insert(0, os.path.join(ROOT, "tools"))
import home_page  # noqa: E402


# ---------------- manifest helpers ----------------

def load_photos():
    with open(DATA, "r", encoding="utf-8") as f:
        return json.load(f)


def save_photos(photos):
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(photos, f, indent=2, ensure_ascii=False)
        f.write("\n")
    regenerate_photos_js(photos)
    make_thumbs(photos)
    # the home page names its photos and counts them, so rebuild it too
    home_page.build(photos)


BOOKINGS = os.path.join(ROOT, "data", "bookings.json")

BOOKING_STATUS = ("booked", "shot", "delivered", "cancelled")


def load_bookings():
    """Who is booked. Private by design — see save_bookings."""
    try:
        with open(BOOKINGS, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (IOError, ValueError):
        return []
    rows = data.get("bookings", []) if isinstance(data, dict) else data
    return rows if isinstance(rows, list) else []


def save_bookings(rows):
    """These rows carry minors' names and their parents' phone numbers, so
    unlike every other manifest here this one is never generated into js/
    and never deployed. It is gitignored, and Publish refuses to run while
    it is not — see api_publish."""
    rows.sort(key=lambda b: ((b.get("date") or "9999-99-99"),
                             (b.get("athlete") or "").lower()))
    with open(BOOKINGS, "w", encoding="utf-8") as f:
        json.dump({"bookings": rows}, f, indent=2, ensure_ascii=False)
        f.write("\n")


def booking_id(row):
    base = "%s-%s" % (row.get("date") or "undated",
                      slugify(row.get("athlete") or "athlete"))
    if row.get("number"):
        base += "-" + str(row["number"])
    return base


def clean_booking(body, existing=None):
    row = dict(existing or {})
    row["date"] = (body.get("date") or "").strip()
    row["athlete"] = " ".join((body.get("athlete") or "").split())
    # Jersey numbers are worn, not calculated — keep them as typed so "05"
    # stays "05".
    row["number"] = re.sub(r"[^0-9]", "", str(body.get("number") or ""))[:3]
    row["school"] = " ".join((body.get("school") or "").split())
    row["sport"] = (body.get("sport") or "").strip()
    row["tier"] = (body.get("tier") or "").strip()
    row["contact"] = (body.get("contact") or "").strip()
    row["note"] = (body.get("note") or "").strip()
    row["paid"] = bool(body.get("paid"))
    status = (body.get("status") or "booked").strip().lower()
    row["status"] = status if status in BOOKING_STATUS else "booked"

    rate = body.get("rate")
    if rate in (None, ""):
        row["rate"] = ""
    else:
        try:
            rate = float(rate)
        except (TypeError, ValueError):
            raise ValueError("Rate must be a number.")
        row["rate"] = int(rate) if rate == int(rate) else rate

    if not row["athlete"]:
        raise ValueError("Needs a name.")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", row["date"]):
        raise ValueError("Needs a date.")
    row["id"] = existing.get("id") if existing else booking_id(row)
    return row


def regenerate_reviews_js():
    """Approved reviews -> js/reviews.js for the Home page."""
    path = os.path.join(ROOT, "data", "reviews.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        reviews = json.load(f)
    header = (
        "/* GENERATED FILE - do not edit by hand.\n"
        "   Source of truth: data/reviews.json\n"
        "   Add an approved review, then: python3 studio.py --regen */\n\n"
    )
    with open(os.path.join(ROOT, "js", "reviews.js"), "w", encoding="utf-8") as f:
        f.write(header + "window.REVIEWS = " +
                json.dumps(reviews, indent=2, ensure_ascii=False) + ";\n")


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


def make_thumbs(photos):
    """images/thumbs/<name>.jpg for every photograph, so the portfolio grid
    loads small files. A thumbnail is rebuilt when it is missing or older
    than its photograph, and dropped when its photograph is gone."""
    os.makedirs(THUMBS, exist_ok=True)
    wanted = set()
    for p in photos:
        src = os.path.join(ROOT, p["src"])
        name = os.path.basename(src)
        wanted.add(name)
        out = os.path.join(THUMBS, name)
        if not os.path.exists(src):
            continue
        if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(src):
            continue
        try:
            from PIL import Image
            im = Image.open(src).convert("RGB")
            im.thumbnail((THUMB_EDGE, THUMB_EDGE), Image.LANCZOS)
            im.save(out, "JPEG", quality=80, optimize=True, progressive=True)
        except ImportError:
            subprocess.run(["sips", "-Z", str(THUMB_EDGE), "-s", "format", "jpeg",
                            "-s", "formatOptions", "80", src, "--out", out],
                           capture_output=True)
    for name in os.listdir(THUMBS):
        if name.endswith(".jpg") and name not in wanted:
            os.remove(os.path.join(THUMBS, name))


# Pages that load the site's own css/ and js/ files.
PAGES = ["*.html", "card/*.html"]
ASSET_REF = re.compile(
    r'((?:href|src)=")((?:\.\./|/)?(?:css|js)/[\w.-]+\.(?:css|js))'
    r'(?:\?v=[0-9a-f]+)?(")')


def stamp_assets():
    """Give every css/js link a fingerprint of the file it points at:
    js/main.js?v=3f9a1c2e. GitHub Pages tells browsers to keep files for
    ten minutes, so after a publish a visitor could get the new page with
    yesterday's styles and script - an unstyled page with the old one
    built underneath it. A new fingerprint is a new address, which the
    browser has to fetch. Unchanged files keep theirs and stay cached."""
    for pattern in PAGES:
        for page in glob.glob(os.path.join(ROOT, pattern)):
            here = os.path.dirname(page)
            with open(page, encoding="utf-8") as f:
                html = f.read()

            def stamp(m):
                ref = m.group(2)
                path = (os.path.join(ROOT, ref[1:]) if ref.startswith("/")
                        else os.path.normpath(os.path.join(here, ref)))
                if not os.path.exists(path):
                    return m.group(0)
                with open(path, "rb") as f:
                    v = hashlib.sha1(f.read()).hexdigest()[:8]
                return m.group(1) + ref + "?v=" + v + m.group(3)

            out = ASSET_REF.sub(stamp, html)
            if out != html:
                with open(page, "w", encoding="utf-8") as f:
                    f.write(out)


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
    # placement decides where a photo lives:
    #   archive  -> portfolio only, never on the home page (all Studio uploads)
    #   gallery  -> shown in the home gallery (subject to the 10-photo cap)
    #   panel    -> full-screen parallax section on the home page
    #   hero     -> the big opening image (only one)
    # When placement is omitted (e.g. a metadata-only edit) the photo keeps
    # whatever placement it already had.
    placement = body.get("placement")
    if placement is not None:
        entry.pop("feature", None)
        entry.pop("archiveOnly", None)
        if placement == "archive":
            entry["archiveOnly"] = True
        elif placement in VALID_FEATURES:
            entry["feature"] = placement
        # "gallery" -> neither flag
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

    def end_headers(self):
        # Studio is for editing: never let the browser show a stale copy
        # of a page or stylesheet that was just rebuilt.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

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
        if self.path == "/api/home":
            photos = load_photos()
            self.send_json({
                "home": home_page.clean(home_page.load(photos), photos),
                "photos": [{k: p.get(k) for k in ("src", "title", "game", "tags", "orientation")}
                           for p in photos],
                "quoteTypes": home_page.QUOTE_TYPES,
                "fonts": sorted(home_page.FONTS),
                "defaultTheme": home_page.DEFAULT_THEME,
            })
            return
        if self.path == "/api/manifest":
            photos = load_photos()
            self.send_json({"photos": photos, "tags": all_tags(photos),
                            "bookings": load_bookings()})
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
            elif self.path == "/api/home":
                self.api_home()
            elif self.path == "/api/home/revert":
                self.api_home_revert()
            elif self.path == "/api/booking":
                self.api_booking()
            elif self.path == "/api/game":
                self.api_game()
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
        # Studio uploads always go to the portfolio only — never the home page.
        body["placement"] = "archive"
        entry = clean_entry(body, photos)
        src = unique_src(slugify(entry["title"]), photos)
        with open(os.path.join(ROOT, src), "wb") as f:
            f.write(raw)
        entry["src"] = src
        # record pixel dimensions so the portfolio can reserve exact space
        # for each frame before the image loads (no layout shift)
        try:
            body_w = int(body.get("w") or 0)
            body_h = int(body.get("h") or 0)
        except (TypeError, ValueError):
            body_w = body_h = 0
        if body_w > 0 and body_h > 0:
            entry["w"], entry["h"] = body_w, body_h
        # field order matters to nobody but humans reading the JSON
        ordered = {k: entry[k] for k in
                   ("src", "title", "location", "year", "orientation", "tags")}
        if "w" in entry:
            ordered["w"], ordered["h"] = entry["w"], entry["h"]
        ordered["archiveOnly"] = True
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
        stamp = time.strftime("%Y%m%d-%H%M%S-")
        img = os.path.join(ROOT, body["src"])
        if os.path.exists(img):
            shutil.move(img, os.path.join(REMOVED, stamp + os.path.basename(img)))

        save_photos(keep)
        self.send_json({"ok": True})

    def api_home(self):
        """Save the home page from the editor and rebuild index.html."""
        body = self.read_body()
        if not isinstance(body.get("home"), dict):
            raise ValueError("Nothing to save.")
        home = home_page.build(load_photos(), body["home"])
        stamp_assets()
        self.send_json({"ok": True, "home": home})

    def api_home_revert(self):
        """Put the home page back the way it was at the last publish."""
        r = subprocess.run(["git", "show", "HEAD:data/home.json"], cwd=ROOT,
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise ValueError("Nothing published yet to go back to.")
        home = home_page.build(load_photos(), json.loads(r.stdout))
        stamp_assets()
        self.send_json({"ok": True, "home": home})

    def api_booking(self):
        """Add, edit or drop one booking. Nothing here reaches the site."""
        body = self.read_body()
        rows = load_bookings()
        bid = (body.get("id") or "").strip()

        if body.get("action") == "delete":
            keep = [r for r in rows if r.get("id") != bid]
            if len(keep) == len(rows):
                raise ValueError("Booking not found.")
            save_bookings(keep)
            self.send_json({"ok": True, "bookings": keep})
            return

        existing = next((r for r in rows if r.get("id") == bid), None)
        row = clean_booking(body, existing)
        if existing:
            existing.clear()
            existing.update(row)
        else:
            rows.append(row)
        save_bookings(rows)
        self.send_json({"ok": True, "booking": row, "bookings": rows})

    def api_game(self):
        """Rename a group (one game or shoot), or clear it from its photographs."""
        body = self.read_body()
        old_name = (body.get("from") or "").strip()
        new_name = (body.get("to") or "").strip()
        if not old_name:
            raise ValueError("Which group?")

        photos = load_photos()
        hits = [p for p in photos if p.get("game") == old_name]
        if not hits:
            raise ValueError("No photographs in group: %s" % old_name)

        for p in hits:
            if new_name:
                p["game"] = new_name
            else:
                # clearing the game leaves the photographs in the portfolio -
                # removing a photograph is a separate act
                p.pop("game", None)
        save_photos(photos)

        self.send_json({"ok": True, "moved": len(hits)})

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
        # Publish is `git add -A`, so anything sitting in the working tree
        # goes public on the next click. The bookings file holds athletes'
        # names and their families' phone numbers; refuse rather than push
        # it. check-ignore also returns non-zero for an already-tracked
        # file, which is the case that actually needs catching.
        if os.path.exists(BOOKINGS):
            code, _ = run("git", "check-ignore", "-q", "data/bookings.json")
            if code != 0:
                self.send_json({"ok": False, "log":
                                "Stopped: data/bookings.json is not ignored by "
                                "git. It holds athletes' names and contact "
                                "details and must not go to a public repo. Add "
                                "data/bookings.json to .gitignore, then "
                                "publish again."})
                return

        stamp_assets()
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
.tabs{display:flex;gap:.4rem;margin:0 0 1.5rem}
.tab{background:none;border:1px solid var(--line);color:var(--dim);
     border-radius:999px;padding:.5rem 1.1rem;cursor:pointer;font:inherit;
     font-size:.72rem;letter-spacing:.1em;text-transform:uppercase}
.tab.is-on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.hint{max-width:46rem;line-height:1.6;margin:-.4rem 0 1rem}
.gcard{border:1px solid var(--line);border-radius:14px;padding:1rem 1.15rem;
       margin-bottom:.9rem}
.ghead{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap}
.ghead input{flex:1;min-width:14rem;background:#111;border:1px solid var(--line);
             border-radius:8px;color:var(--ink);font:inherit;padding:.5rem .7rem}
.gthumbs{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.9rem}
.gthumb{position:relative;width:78px;height:78px;border-radius:8px;
        overflow:hidden;border:1px solid var(--line)}
.gthumb img{width:100%;height:100%;object-fit:cover;display:block}
.gthumb button{position:absolute;top:2px;right:2px;width:20px;height:20px;
  border-radius:50%;border:0;background:rgba(0,0,0,.72);color:#f87171;
  cursor:pointer;font-size:12px;line-height:1;padding:0}
.gthumb button:hover{background:#f87171;color:#000}
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
/* ---- bookings ---- */
.bkform{border:1px solid var(--line);border-radius:14px;padding:1.15rem;
        max-width:52rem;display:grid;gap:.7rem;
        grid-template-columns:9rem 4.5rem 1fr 1fr}
.bkform label{display:flex;flex-direction:column;gap:.3rem}
.bkform input,.bkform select{background:#111;border:1px solid var(--line);
  border-radius:8px;color:var(--ink);font:inherit;font-size:.9rem;
  padding:.45rem .6rem;width:100%}
.bkform .wide{grid-column:1/-1}
.bkform .actions{grid-column:1/-1;display:flex;gap:.75rem;align-items:center}
.bk{border:1px solid var(--line);border-radius:14px;padding:.85rem 1.1rem;
    margin-bottom:.65rem;display:grid;gap:.9rem;align-items:center;
    grid-template-columns:6.5rem 2.6rem 1fr auto}
.bk.is-next{border-color:var(--ink);background:var(--raise)}
.bk.is-done{opacity:.45}
.bk__when b{display:block;font-size:.9rem;letter-spacing:.02em}
.bk__when span{display:block;font-family:var(--mono);font-size:.6rem;
  letter-spacing:.12em;text-transform:uppercase;color:var(--dim);margin-top:.15rem}
.bk__num{width:2.6rem;height:2.6rem;border-radius:50%;border:1px solid var(--line);
  display:flex;align-items:center;justify-content:center;font-size:1.05rem;
  font-weight:600}
.bk.is-next .bk__num{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.bk__who b{display:block;font-size:1rem}
.bk__who span{display:block;font-family:var(--mono);font-size:.65rem;
  letter-spacing:.1em;text-transform:uppercase;color:var(--dim);margin-top:.2rem}
.bk__side{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;
  justify-content:flex-end}
.bk__side select{width:auto;padding:.35rem .4rem;font-size:.8rem;border-radius:8px;
  background:#111;border:1px solid var(--line)}
.bk__paid{display:flex;align-items:center;gap:.35rem;font-family:var(--mono);
  font-size:.62rem;letter-spacing:.12em;text-transform:uppercase;color:var(--dim);
  cursor:pointer;white-space:nowrap}
.bk__paid input{accent-color:var(--ok)}
.bk__x{background:none;border:0;color:var(--dim);cursor:pointer;font-size:1rem;
  line-height:1;padding:.25rem .4rem}
.bk__x:hover{color:var(--bad)}
.bk__note{grid-column:1/-1;font-size:.85rem;color:var(--dim);line-height:1.5;
  border-top:1px solid var(--soft);padding-top:.6rem;margin-top:-.2rem}
@media (max-width:640px){
  .bkform{grid-template-columns:1fr 1fr}
  .bk{grid-template-columns:1fr auto}
  .bk__when,.bk__num{grid-column:auto}
}
#publish-wrap{margin-top:3rem;border-top:1px solid var(--line);padding-top:1.5rem;
  display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
/* ---------- home page editor ---------- */
body.is-wide{padding-bottom:2rem}
.he{display:grid;grid-template-columns:minmax(300px,380px) 1fr;gap:1.25rem;
    height:calc(100vh - 140px);min-height:520px}
.he__side{position:relative;overflow-y:auto;padding-right:.4rem;display:flex;
  flex-direction:column;gap:.9rem}
.he__bar{position:sticky;top:0;z-index:2;background:var(--bg);padding-bottom:.6rem;
  border-bottom:1px solid var(--line);display:flex;flex-direction:column;gap:.5rem}
.he__bar .row{display:flex;gap:.5rem;flex-wrap:wrap}
.he__status{font-size:.8rem;color:var(--dim);line-height:1.4}
.he__status.ok{color:var(--ok)} .he__status.bad{color:var(--bad)}
.he__group{margin-top:.2rem}
.he__list{list-style:none;display:flex;flex-direction:column;gap:.3rem}
.he__item{display:flex;align-items:center;gap:.35rem;border:1px solid var(--line);
  border-radius:10px;padding:.35rem .4rem .35rem .7rem;background:var(--raise)}
.he__item.is-on{border-color:#6ee7a8;box-shadow:0 0 0 1px #6ee7a8 inset}
.he__item.is-off .he__name{opacity:.45;text-decoration:line-through}
.he__name{flex:1;background:none;border:0;color:var(--ink);font:inherit;font-size:.9rem;
  text-align:left;cursor:pointer;padding:.3rem 0}
.he__icon{background:none;border:1px solid var(--line);color:var(--dim);border-radius:7px;
  width:1.9rem;height:1.9rem;cursor:pointer;font-size:.8rem;line-height:1}
.he__icon:hover{color:var(--ink);border-color:var(--ink)}
.he__icon:disabled{opacity:.3;cursor:default}
.he__form{display:flex;flex-direction:column;gap:.85rem;border:1px solid var(--line);
  border-radius:14px;padding:1rem}
.he__form h3{font-size:.95rem;font-weight:600}
.he__form .note{font-size:.8rem;color:var(--dim);line-height:1.5}
.hf{display:flex;flex-direction:column;gap:.35rem}
.hf > .mono{display:flex;justify-content:space-between;gap:.5rem}
.hf input[type=text],.hf textarea,.hf select{width:100%;background:#111;border:1px solid var(--line);
  border-radius:8px;color:var(--ink);font:inherit;font-size:.9rem;padding:.5rem .6rem}
.hf textarea{resize:vertical;min-height:4.5rem;line-height:1.5}
.hf input:focus,.hf textarea:focus,.hf select:focus{outline:none;border-color:var(--ink)}
.hf__row{display:flex;gap:.35rem;align-items:flex-start}
.hf__row > :first-child{flex:1}
.hf__obj{border:1px solid var(--soft);border-radius:10px;padding:.6rem;display:flex;
  flex-direction:column;gap:.5rem;background:#0f0f0f}
.hf__objhead{display:flex;justify-content:space-between;align-items:center;gap:.4rem}
.hf__add{align-self:flex-start;background:none;border:1px dashed var(--line);color:var(--ink);
  border-radius:8px;padding:.45rem .8rem;cursor:pointer;font:inherit;font-size:.8rem}
.hf__add:hover{border-color:var(--ink)}
.hf__photos{display:flex;flex-wrap:wrap;gap:.45rem}
.hf__ph{position:relative;width:84px;height:84px;border-radius:8px;overflow:hidden;
  border:1px solid var(--line);background:#111;cursor:pointer}
.hf__ph img{width:100%;height:100%;object-fit:cover;display:block}
.hf__ph .tools{position:absolute;left:0;right:0;bottom:0;display:flex;justify-content:space-between;
  background:rgba(0,0,0,.65)}
.hf__ph .tools button{background:none;border:0;color:#fff;cursor:pointer;font-size:.75rem;
  padding:.2rem .35rem}
.hf__ph .tools button:hover{color:#6ee7a8}
.hf__ph .tools .x:hover{color:#f87171}
.hf__new{width:84px;height:84px;border-radius:8px;border:1px dashed var(--line);background:none;
  color:var(--dim);cursor:pointer;font:inherit;font-size:.75rem}
.hf__new:hover{border-color:#6ee7a8;color:var(--ink)}
.hf__colors{display:grid;grid-template-columns:1fr 1fr;gap:.6rem}
.hf__color{display:flex;align-items:center;gap:.5rem;font-size:.82rem}
.hf__color input{width:2.4rem;height:2rem;border:1px solid var(--line);border-radius:6px;
  background:none;padding:0;cursor:pointer}
.hf__count{font-size:.7rem}
.hf__count.over{color:var(--bad)}
.he__stage{display:flex;flex-direction:column;gap:.6rem;min-width:0}
.he__devices{display:flex;gap:.4rem;align-items:center;flex-wrap:wrap}
.he__devices .tab{padding:.4rem .9rem}
.he__hint{font-size:.78rem;color:var(--dim);margin-left:auto}
.he__frame-wrap{flex:1;display:flex;justify-content:center;background:#050505;
  border:1px solid var(--line);border-radius:12px;overflow:hidden}
#he-frame{border:0;width:100%;height:100%;background:#0b0b0e}
.he__frame-wrap.is-phone #he-frame{width:390px;border-left:1px solid var(--line);
  border-right:1px solid var(--line)}
.hep{position:fixed;inset:0;z-index:50;background:rgba(0,0,0,.78);display:flex;
  align-items:center;justify-content:center;padding:2rem}
.hep[hidden]{display:none}
.hep__card{background:var(--raise);border:1px solid var(--line);border-radius:14px;
  width:min(1100px,100%);height:min(86vh,900px);display:flex;flex-direction:column}
.hep__bar{display:flex;gap:.5rem;padding:1rem;border-bottom:1px solid var(--line);flex-wrap:wrap}
.hep__bar input,.hep__bar select{background:#111;border:1px solid var(--line);border-radius:8px;
  color:var(--ink);font:inherit;padding:.5rem .7rem}
.hep__bar input{flex:1 1 14rem;width:auto;min-width:0}
.hep__bar select,.hep__bar button{width:auto;flex:0 0 auto}
.hep__grid{flex:1;overflow-y:auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));
  gap:4px;padding:1rem;align-content:start}
.hep__grid button{position:relative;aspect-ratio:1;border:0;padding:0;cursor:pointer;background:#111}
.hep__grid button img{width:100%;height:100%;object-fit:cover;display:block}
.hep__grid button:hover{outline:3px solid #6ee7a8;outline-offset:-3px}
.hep__grid button.is-used::after{content:"on page";position:absolute;left:4px;top:4px;
  background:#6ee7a8;color:#000;font-size:10px;padding:2px 5px;border-radius:4px}
.hep__more{grid-column:1/-1;justify-self:center;margin:1rem}
@media (max-width:900px){.he{grid-template-columns:1fr;height:auto}
  .he__frame-wrap{height:70vh}}
</style>
</head>
<body>
<header>
  <h1>Studio</h1>
  <nav class="mono">
    <a href="/" target="_blank">Site →</a>
    <a href="/portfolio.html" target="_blank">Portfolio →</a>
  </nav>
</header>

<div class="tabs mono" id="tabs">
  <button class="tab is-on" data-panel="panel-photos">Photos</button>
  <button class="tab" data-panel="panel-home">Home page</button>
  <button class="tab" data-panel="panel-games">Games</button>
  <button class="tab" data-panel="panel-bookings">Bookings</button>
</div>

<section id="panel-photos">
  <div id="drop">
    <span class="mono">Drop photos here — or click to choose (JPG / PNG)</span>
    <input type="file" id="file-input" multiple accept="image/jpeg,image/png">
  </div>

  <div id="pending" class="cards" style="margin-top:1.25rem"></div>

  <h2>Library <span class="mono" id="lib-count"></span></h2>
  <div id="library" class="cards"></div>
</section>

<section id="panel-games" hidden>
  <h2>Groups <span class="mono" id="sh-gcount"></span></h2>
  <p class="mono hint">A group is one game or shoot. Renaming one renames it on
    every photograph in it, and the name shows on the portfolio. Removing a
    photograph here takes it off the whole site.</p>
  <div id="sh-games"></div>
</section>

<section id="panel-bookings" hidden>
  <h2>Add a booking</h2>
  <p class="mono hint">Private. This never goes on the site and never leaves
    this machine &mdash; Publish refuses to run if the file is not gitignored.</p>
  <div class="bkform">
    <label><span class="mono">Date</span><input type="date" id="bk-date"></label>
    <label><span class="mono">Number</span><input type="text" id="bk-number"
      inputmode="numeric" placeholder="5"></label>
    <label><span class="mono">Athlete</span><input type="text" id="bk-athlete"
      placeholder="First Last"></label>
    <label><span class="mono">School / team</span><input type="text" id="bk-school"
      placeholder="DCDS"></label>
    <label><span class="mono">Sport</span><input type="text" id="bk-sport"
      placeholder="Football"></label>
    <label><span class="mono">Booking</span><select id="bk-tier"></select></label>
    <label><span class="mono">Quoted ($)</span><input type="number" id="bk-rate"
      min="0" step="1" placeholder="40"></label>
    <label><span class="mono">Contact</span><input type="text" id="bk-contact"
      placeholder="Phone, email or @handle"></label>
    <label class="wide"><span class="mono">Note</span><input type="text"
      id="bk-note" placeholder="Where to meet, who to ask for, anything owed"></label>
    <div class="actions">
      <button class="primary" id="bk-save">Save booking</button>
      <span class="status" id="bk-status"></span>
    </div>
  </div>

  <h2>Booked <span class="mono" id="bk-count"></span></h2>
  <div id="bk-upcoming"></div>
  <h2>Done <span class="mono" id="bk-donecount"></span></h2>
  <div id="bk-past"></div>
</section>

<section id="panel-home" hidden>
  <div class="he">
    <aside class="he__side">
      <div class="he__bar">
        <div class="he__status" id="he-status">Loading…</div>
        <div class="row">
          <button class="primary" id="he-publish" type="button">Publish to the web</button>
          <button class="ghost" id="he-revert" type="button">Undo changes since last publish</button>
        </div>
      </div>

      <div class="he__group">
        <div class="mono" style="margin-bottom:.4rem">Whole page</div>
        <ul class="he__list" id="he-page"></ul>
      </div>

      <div class="he__group">
        <div class="mono" style="margin-bottom:.4rem">Sections, top to bottom</div>
        <ul class="he__list" id="he-sections"></ul>
      </div>

      <div id="he-editor"></div>
    </aside>

    <div class="he__stage">
      <div class="he__devices mono">
        <button class="tab is-on" type="button" data-device="desktop">Computer</button>
        <button class="tab" type="button" data-device="phone">Phone</button>
        <a class="tab" href="/index.html" target="_blank">Open in a new tab</a>
        <span class="he__hint">Click any part of the page to edit it. Green outlines are photo spots.</span>
      </div>
      <div class="he__frame-wrap" id="he-frame-wrap">
        <iframe id="he-frame" title="Home page preview"></iframe>
      </div>
    </div>
  </div>

  <div class="hep" id="he-picker" hidden>
    <div class="hep__card">
      <div class="hep__bar">
        <input type="text" id="hep-q" placeholder="Search by game, sport, title or file name">
        <select id="hep-tag"><option value="">Every subject</option></select>
        <button class="ghost" id="hep-close" type="button">Cancel</button>
      </div>
      <div class="hep__grid" id="hep-grid"></div>
    </div>
  </div>
</section>

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

/* ---------- shared card form ----------
   mode "add"     -> new uploads, always go to the Portfolio (no placement UI)
   mode "library" -> existing photos, can be placed on the home page        */
function metaForm(photo, mode) {
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

  var place = null;
  if (mode === "add") {
    var note = el("div", "mono", "Adds to the Portfolio →");
    note.style.marginTop = ".7rem";
    note.style.opacity = ".7";
    f.appendChild(note);
  } else {
    var where = el("div", "mono", "Front-page photos are picked in the Home page tab");
    where.style.marginTop = ".7rem";
    where.style.opacity = ".7";
    f.appendChild(where);
  }

  f.read = function () {
    var out = {
      title: f.querySelector('[data-f=title]').value,
      location: f.querySelector('[data-f=location]').value,
      year: f.querySelector('[data-f=year]').value,
      tags: picker.getTags()
    };
    if (place) out.placement = place.value;
    return out;
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
      canvas.width >= canvas.height ? "landscape" : "portrait",
      canvas.width, canvas.height);
  };
  img.src = URL.createObjectURL(file);
}

function addPendingCard(file, dataUrl, orientation, pxW, pxH) {
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
  }, "add");
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
    meta.w = pxW; meta.h = pxH;
    meta.image = dataUrl;
    addBtn.disabled = true;
    status.textContent = "Uploading…"; status.className = "status";
    api("/api/add", meta).then(function (res) {
      if (res.error) throw new Error(res.error);
      status.textContent = "Added ✓ — it's in the portfolio";
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
    renderBookings(data.bookings || []);
    renderGames(data.photos);
    var lib = document.getElementById("library");
    lib.innerHTML = "";
    document.getElementById("lib-count").textContent =
      "— " + data.photos.length + " photographs";
    data.photos.forEach(function (photo) {
      var card = el("div", "card");
      var meta = el("div", "lib-meta");
      meta.appendChild(el("span", "mono", photo.src));
      if (photo.feature) meta.appendChild(el("span", "mono", "★ " + photo.feature));
      else if (photo.archiveOnly) meta.appendChild(el("span", "mono", "portfolio"));
      card.appendChild(meta);
      var thumb = el("img");
      thumb.src = "/" + photo.src; thumb.loading = "lazy";
      card.appendChild(thumb);
      var form = metaForm(photo, "library");
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
          "The original moves to images/_removed/, " +
          "so the picture stops being reachable on the site.")) return;
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

/* ---------- bookings ----------
   A private list of who is booked. Kept beside the photographs because
   the shoot and the delivery are the same job. */

var BOOKINGS = [];

/* "2026-09-11" is a calendar day, not an instant. new Date() on that
   string parses it as UTC midnight, which is the evening before in
   Michigan — a Friday booking would read Thursday. Build it locally. */
function dayOf(iso) {
  var p = String(iso || "").split("-");
  return new Date(+p[0], +p[1] - 1, +p[2]);
}

function todayStart() {
  var n = new Date();
  return new Date(n.getFullYear(), n.getMonth(), n.getDate());
}

function daysAway(iso) {
  return Math.round((dayOf(iso) - todayStart()) / 86400000);
}

function whenText(iso) {
  var d = daysAway(iso);
  if (d === 0) return "today";
  if (d === 1) return "tomorrow";
  if (d === -1) return "yesterday";
  if (d > 1 && d < 7) return "in " + d + " days";
  if (d < 0) return Math.abs(d) + " days ago";
  return "in " + d + " days";
}

function dateText(iso) {
  return dayOf(iso).toLocaleDateString(undefined,
    { weekday: "short", month: "short", day: "numeric" });
}

/* The same choices as "What are you booking?" on the site's quote form,
   so a request copies straight across. A booking saved under an older
   name keeps it. */
var BOOKING_TYPES = ["Individual athlete session", "Team shoot",
  "Game or tournament coverage", "Senior or recruiting photos",
  "Car meet or other event", "Something else"];

function tierOptions(sel, current) {
  sel.innerHTML = '<option value=""></option>';
  var names = BOOKING_TYPES.slice();
  if (current && names.indexOf(current) === -1) names.push(current);
  names.forEach(function (name) {
    var o = document.createElement("option");
    o.value = name; o.textContent = name;
    sel.appendChild(o);
  });
  sel.value = current || "";
}

function bookingRow(b) {
  var row = el("div", "bk");
  var away = daysAway(b.date);
  var done = b.status === "delivered" || b.status === "cancelled";
  if (done) row.classList.add("is-done");

  var when = el("div", "bk__when");
  when.innerHTML = "<b>" + dateText(b.date) + "</b><span>" +
                   (done ? b.status : whenText(b.date)) + "</span>";
  row.appendChild(when);

  row.appendChild(el("div", "bk__num", b.number ? "#" + b.number : "—"));

  var who = el("div", "bk__who");
  var sub = [b.school, b.sport, b.tier,
             (b.rate === "" || b.rate == null) ? "" : "$" + b.rate]
            .filter(Boolean).join(" · ");
  who.innerHTML = "<b>" + esc(b.athlete) + "</b>" +
                  (sub ? "<span>" + esc(sub) + "</span>" : "") +
                  (b.contact ? "<span>" + esc(b.contact) + "</span>" : "");
  row.appendChild(who);

  var side = el("div", "bk__side");

  var paid = el("label", "bk__paid");
  paid.innerHTML = '<input type="checkbox"' + (b.paid ? " checked" : "") + ">paid";
  paid.querySelector("input").onchange = function () {
    saveBooking(Object.assign({}, b, { paid: this.checked }));
  };
  side.appendChild(paid);

  var st = document.createElement("select");
  ["booked", "shot", "delivered", "cancelled"].forEach(function (v) {
    var o = document.createElement("option");
    o.value = v; o.textContent = v;
    st.appendChild(o);
  });
  st.value = b.status || "booked";
  st.onchange = function () {
    saveBooking(Object.assign({}, b, { status: this.value }));
  };
  side.appendChild(st);

  var x = el("button", "bk__x", "&times;");
  x.type = "button";
  x.title = "Delete this booking";
  x.onclick = function () {
    if (!confirm("Delete the booking for " + b.athlete + "?")) return;
    api("/api/booking", { action: "delete", id: b.id }).then(afterBooking);
  };
  side.appendChild(x);
  row.appendChild(side);

  if (b.note) row.appendChild(el("div", "bk__note", esc(b.note)));

  /* The next shoot is the one thing worth spotting from across the room. */
  if (!done && away >= 0 && away <= 2) row.classList.add("is-next");
  return row;
}

function esc(t) {
  return String(t == null ? "" : t)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderBookings(rows) {
  BOOKINGS = rows || [];
  tierOptions(document.getElementById("bk-tier"),
              document.getElementById("bk-tier").value);

  var up = document.getElementById("bk-upcoming");
  var past = document.getElementById("bk-past");
  up.innerHTML = ""; past.innerHTML = "";

  var open = BOOKINGS.filter(function (b) {
    return b.status !== "delivered" && b.status !== "cancelled";
  });
  var done = BOOKINGS.filter(function (b) {
    return b.status === "delivered" || b.status === "cancelled";
  }).reverse();

  open.forEach(function (b) { up.appendChild(bookingRow(b)); });
  done.forEach(function (b) { past.appendChild(bookingRow(b)); });

  if (!open.length) {
    up.innerHTML = '<p class="mono hint">Nothing booked yet.</p>';
  }
  var owed = open.filter(function (b) { return !b.paid && b.rate; })
                 .reduce(function (n, b) { return n + Number(b.rate || 0); }, 0);
  document.getElementById("bk-count").textContent =
    "— " + open.length + (open.length === 1 ? " booking" : " bookings") +
    (owed ? " · $" + owed + " outstanding" : "");
  document.getElementById("bk-donecount").textContent =
    done.length ? "— " + done.length : "— none yet";
}

function afterBooking(res) {
  var s = document.getElementById("bk-status");
  if (res.error) {
    s.textContent = res.error; s.className = "status bad";
    return;
  }
  renderBookings(res.bookings || []);
  s.textContent = "Saved."; s.className = "status ok";
}

function saveBooking(b) {
  return api("/api/booking", b).then(afterBooking);
}

document.getElementById("bk-save").onclick = function () {
  var g = function (id) { return document.getElementById(id).value.trim(); };
  saveBooking({
    date: g("bk-date"), athlete: g("bk-athlete"), number: g("bk-number"),
    school: g("bk-school"), sport: g("bk-sport"), tier: g("bk-tier"),
    rate: g("bk-rate"), contact: g("bk-contact"), note: g("bk-note"),
    status: "booked"
  }).then(function () {
    ["bk-athlete", "bk-number", "bk-rate", "bk-contact", "bk-note"]
      .forEach(function (id) { document.getElementById(id).value = ""; });
  });
};

/* ---------- tabs ---------- */
document.getElementById("tabs").addEventListener("click", function (e) {
  var b = e.target.closest(".tab");
  if (!b) return;
  document.querySelectorAll(".tab").forEach(function (t) {
    t.classList.toggle("is-on", t === b);
  });
  ["panel-photos", "panel-home", "panel-games", "panel-bookings"].forEach(function (id) {
    document.getElementById(id).hidden = (id !== b.dataset.panel);
  });
  document.body.classList.toggle("is-wide", b.dataset.panel === "panel-home");
  if (b.dataset.panel === "panel-home") heInit();
});

function q(v) { return String(v == null ? "" : v).replace(/"/g, "&quot;"); }

/* ---------- games ---------- */

function renderGames(photos) {
  var order = [], groups = {};
  photos.forEach(function (p) {
    if (!p.game) return;
    if (!groups[p.game]) { groups[p.game] = []; order.push(p.game); }
    groups[p.game].push(p);
  });

  document.getElementById("sh-gcount").textContent =
    "- " + order.length + (order.length === 1 ? " group" : " groups");

  var wrap = document.getElementById("sh-games");
  wrap.innerHTML = "";
  if (!order.length) {
    wrap.innerHTML = "<p class='mono'>No groups yet. Give a photograph a game " +
      "in the Photos tab and it shows up here.</p>";
    return;
  }

  order.forEach(function (game) {
    var list = groups[game];
    var card = el("div", "gcard");
    var head = el("div", "ghead");
    head.innerHTML = '<input value="' + q(game) + '">' +
      "<span class='mono'>" + list.length + " photos</span>" +
      "<button class='ghost'>Rename</button>";
    card.appendChild(head);

    var input = head.querySelector("input");
    head.querySelector("button").onclick = function () {
      var to = input.value.trim();
      if (!to || to === game) return;
      api("/api/game", { from: game, to: to })
        .then(function () { loadLibrary(); })
        .catch(function (e) { alert(e.message); });
    };

    var thumbs = el("div", "gthumbs");
    list.forEach(function (p) {
      var t = el("div", "gthumb");
      t.innerHTML = '<img src="/' + p.src + '" alt="" loading="lazy">' +
                    "<button title='Remove'>x</button>";

      t.querySelector("button").onclick = function () {
        if (!confirm('Remove "' + p.title + '" from the site?\n\n' +
          "It comes off the portfolio. The original moves to " +
          "images/_removed/.")) return;
        api("/api/remove", { src: p.src })
          .then(function () { loadLibrary(); })
          .catch(function (e) { alert(e.message); });
      };
      thumbs.appendChild(t);
    });
    card.appendChild(thumbs);
    wrap.appendChild(card);
  });
}

/* ---------- home page editor ----------
   data/home.json is the page. Every change is saved straight away and
   index.html rebuilt (tools/home_page.py), then the preview reloads.
   Nothing reaches the web until Publish. */

var HE = { home: null, photos: [], by: {}, quoteTypes: [], fonts: [],
           defaultTheme: {}, sel: null, timer: null, saving: false, again: false,
           ready: false };

var LINKS = ["#quote", "portfolio.html", "portfolio.html?tag=sports",
  "portfolio.html?tag=football", "portfolio.html?tag=soccer", "portfolio.html?tag=tennis",
  "portfolio.html?tag=volleyball", "portfolio.html?tag=hockey", "#about", "#faq",
  "#contact", "#sports-photography"];

var RICH = "Tip: **bold** makes text bold, and [words](link) makes a link.";

var SECTIONS = {
  intro: { name: "Name card", about: "The big name that fills the first screen.",
    fields: [{ k: "name", label: "Your name" },
             { k: "role", label: "Line under your name" }] },
  hero: { name: "Opening photo",
    about: "The full-screen photo under your name. Add more than one and they fade from one to the next.",
    fields: [{ k: "photos", label: "Photos", type: "photos" },
             { k: "button", label: "Button text (leave blank for no button)" },
             { k: "buttonLink", label: "Button goes to", type: "link" },
             { k: "left", label: "Caption, left" },
             { k: "right", label: "Caption, right" }] },
  marquee: { name: "Scrolling words", about: "The band of words that slides across the screen.",
    fields: [{ k: "words", label: "Words", type: "list" }] },
  about: { name: "About",
    fields: [{ k: "photo", label: "Photo on the left (optional)", type: "photo" },
             { k: "label", label: "Section label" },
             { k: "heading", label: "Headline", type: "textarea" },
             { k: "paragraphs", label: "Paragraphs", type: "list", long: true, rich: true },
             { k: "button", label: "Button text (leave blank for no button)" },
             { k: "buttonLink", label: "Button goes to", type: "link" }] },
  work: { name: "Selected work", about: "A few photos that open full size. Six fills the grid.",
    fields: [{ k: "label", label: "Section label" },
             { k: "photos", label: "Photos", type: "photos" }] },
  services: { name: "Sports photography",
    fields: [{ k: "label", label: "Section label" },
             { k: "aside", label: "Small text on the right" },
             { k: "heading", label: "Headline" },
             { k: "cards", label: "Cards", type: "objects", item: "card",
               blank: { title: "New card", text: "", linkText: "", link: "", quote: "" },
               sub: [{ k: "title", label: "Title" },
                     { k: "text", label: "Text", type: "textarea", rich: true },
                     { k: "linkText", label: "Link text (blank for none)" },
                     { k: "link", label: "Link goes to", type: "link" },
                     { k: "quote", label: "If it opens the quote form, pick this booking type",
                       type: "quotetype" }] },
             { k: "areaLabel", label: "Label for the area line" },
             { k: "area", label: "Where you shoot", type: "textarea", rich: true }] },
  quote: { name: "Get a quote",
    fields: [{ k: "label", label: "Section label" },
             { k: "aside", label: "Small text on the right" },
             { k: "heading", label: "Headline" },
             { k: "intro", label: "Intro", type: "textarea", rich: true },
             { k: "points", label: "Bullet points", type: "list", rich: true },
             { k: "options", label: "Booking types in the form's dropdown", type: "list" },
             { k: "button", label: "Send button text" },
             { k: "thanks", label: "Message after someone sends it", type: "textarea" }] },
  reviews: { name: "Reviews",
    about: "Reviews circle the Leave a review form: four or more slide past in two rows. " +
           "Add praise people have actually given you (a parent's text, a coach's DM), " +
           "with their OK. Made-up reviews break the FTC's fake-review rule. Reviews " +
           "visitors post join in once you approve them in Supabase (see SETUP.md).",
    fields: [{ k: "label", label: "Section label" },
             { k: "items", label: "Reviews you've received", type: "objects", item: "review",
               blank: { name: "", role: "", rating: 5, text: "" },
               sub: [{ k: "name", label: "Their name (first name and last initial is fine)" },
                     { k: "role", label: "Who they are (e.g. Parent, DCDS football)" },
                     { k: "rating", label: "Stars", type: "rating" },
                     { k: "text", label: "What they said", type: "textarea" }] }] },
  faq: { name: "Questions",
    fields: [{ k: "label", label: "Section label" },
             { k: "aside", label: "Small text on the right" },
             { k: "heading", label: "Headline" },
             { k: "items", label: "Questions", type: "objects", item: "question",
               blank: { q: "New question?", a: "" },
               sub: [{ k: "q", label: "Question" },
                     { k: "a", label: "Answer", type: "textarea", rich: true }] }] },
  contact: { name: "Contact",
    fields: [{ k: "label", label: "Section label" },
             { k: "aside", label: "Small text on the right" },
             { k: "email", label: "Email address" },
             { k: "instagram", label: "Instagram name (without the @)" }] },
  cta: { name: "Portfolio button", about: "The big link at the bottom of the page.",
    fields: [{ k: "text", label: "Big text" },
             { k: "link", label: "Goes to", type: "link" }] }
};

function heStatus(text, cls) {
  var s = document.getElementById("he-status");
  s.textContent = text;
  s.className = "he__status" + (cls ? " " + cls : "");
}

function heInit() {
  if (HE.ready) { heReload(); return; }
  fetch("/api/home").then(function (r) { return r.json(); }).then(function (data) {
    HE.home = data.home;
    HE.photos = data.photos;
    HE.photos.forEach(function (p) { HE.by[p.src] = p; });
    HE.quoteTypes = data.quoteTypes;
    HE.fonts = data.fonts;
    HE.defaultTheme = data.defaultTheme;
    HE.ready = true;
    var tags = {};
    HE.photos.forEach(function (p) { (p.tags || []).forEach(function (t) { tags[t] = 1; }); });
    var sel = document.getElementById("hep-tag");
    Object.keys(tags).sort().forEach(function (t) {
      var o = document.createElement("option"); o.value = t; o.textContent = t; sel.appendChild(o);
    });
    heStatus("Everything here is saved on this computer. It goes on the web when you Publish.", "ok");
    heRenderLists();
    heSelect("hero");
    heReload();
  }).catch(function (e) { heStatus("Couldn't load the home page: " + e.message, "bad"); });
}

function heSection(id) {
  return HE.home.sections.filter(function (s) { return s.id === id; })[0];
}

/* ---------- saving ---------- */

function heChanged() {
  heStatus("Saving…");
  clearTimeout(HE.timer);
  HE.timer = setTimeout(heSave, 450);
}

function heSave() {
  if (HE.saving) { HE.again = true; return; }
  HE.saving = true;
  api("/api/home", { home: HE.home }).then(function (res) {
    if (res.error) throw new Error(res.error);
    heStatus("Saved on this computer. Publish to put it on the web.", "ok");
    heReload();
  }).catch(function (e) {
    heStatus("Couldn't save: " + e.message, "bad");
  }).finally(function () {
    HE.saving = false;
    if (HE.again) { HE.again = false; heSave(); }
  });
}

/* ---------- left side: page settings + sections ---------- */

function heRenderLists() {
  var page = document.getElementById("he-page");
  page.innerHTML = "";
  [["settings", "Google title, description & share photo"],
   ["theme", "Colors, fonts & corners (whole site)"]].forEach(function (it) {
    var li = el("li", "he__item" + (HE.sel === it[0] ? " is-on" : ""));
    var b = el("button", "he__name", it[1]);
    b.type = "button";
    b.onclick = function () { heSelect(it[0]); };
    li.appendChild(b);
    page.appendChild(li);
  });

  var list = document.getElementById("he-sections");
  list.innerHTML = "";
  var secs = HE.home.sections;
  secs.forEach(function (s, i) {
    var info = SECTIONS[s.type] || { name: s.type };
    var li = el("li", "he__item" + (HE.sel === s.id ? " is-on" : "") +
                (s.visible ? "" : " is-off"));
    var name = el("button", "he__name", info.name);
    name.type = "button";
    name.onclick = function () { heSelect(s.id, true); };
    var eye = el("button", "he__icon", s.visible ? "👁" : "—");
    eye.type = "button";
    eye.title = s.visible ? "Showing. Click to hide this section." : "Hidden. Click to show it.";
    eye.onclick = function () { s.visible = !s.visible; heRenderLists(); heChanged(); };
    var up = el("button", "he__icon", "↑");
    up.type = "button"; up.title = "Move up"; up.disabled = i === 0;
    up.onclick = function () { heMove(secs, i, -1); heRenderLists(); heChanged(); };
    var down = el("button", "he__icon", "↓");
    down.type = "button"; down.title = "Move down"; down.disabled = i === secs.length - 1;
    down.onclick = function () { heMove(secs, i, 1); heRenderLists(); heChanged(); };
    li.appendChild(name); li.appendChild(eye); li.appendChild(up); li.appendChild(down);
    list.appendChild(li);
  });
}

function heMove(arr, i, dir) {
  var j = i + dir;
  if (j < 0 || j >= arr.length) return;
  var t = arr[i]; arr[i] = arr[j]; arr[j] = t;
}

function heSelect(id, scroll) {
  HE.sel = id;
  heRenderLists();
  heRenderEditor();
  heMarkPreview(scroll);
  /* bring the settings for what was picked into view in the side panel */
  var side = document.querySelector(".he__side");
  var bar = document.querySelector(".he__bar");
  side.scrollTo({ top: document.getElementById("he-editor").offsetTop - bar.offsetHeight - 12,
                  behavior: "smooth" });
}

/* ---------- field editors ---------- */

function heField(label, input, extra) {
  var w = el("div", "hf");
  var l = el("span", "mono");
  l.appendChild(document.createTextNode(label));
  if (extra) l.appendChild(extra);
  w.appendChild(l);
  w.appendChild(input);
  return w;
}

function heText(obj, k, label, opts) {
  opts = opts || {};
  var input;
  if (opts.type === "textarea") {
    input = el("textarea");
    input.rows = opts.rows || 3;
  } else {
    input = el("input");
    input.type = "text";
    if (opts.type === "link") input.setAttribute("list", "he-links");
  }
  input.value = obj[k] == null ? "" : obj[k];
  var count = null;
  if (opts.max) {
    count = el("span", "hf__count");
    var paint = function () {
      count.textContent = input.value.length + " / " + opts.max;
      count.classList.toggle("over", input.value.length > opts.max);
    };
    paint();
    input.addEventListener("input", paint);
  }
  input.addEventListener("input", function () { obj[k] = input.value; heChanged(); });
  var f = heField(label, input, count);
  if (opts.rich) f.appendChild(el("span", "note", RICH));
  return f;
}

function heSelectBox(obj, k, label, choices) {
  var s = el("select");
  choices.forEach(function (c) {
    var o = document.createElement("option");
    o.value = c[0]; o.textContent = c[1]; s.appendChild(o);
  });
  s.value = obj[k] == null ? "" : String(obj[k]);
  s.addEventListener("change", function () { obj[k] = s.value; heChanged(); });
  return heField(label, s);
}

function heRowTools(arr, i, onChange) {
  var box = el("div");
  box.style.display = "flex"; box.style.gap = ".25rem";
  [["↑", -1, "Move up"], ["↓", 1, "Move down"]].forEach(function (t) {
    var b = el("button", "he__icon", t[0]);
    b.type = "button"; b.title = t[2];
    b.disabled = (t[1] < 0 && i === 0) || (t[1] > 0 && i === arr.length - 1);
    b.onclick = function () { heMove(arr, i, t[1]); onChange(); };
    box.appendChild(b);
  });
  var x = el("button", "he__icon", "✕");
  x.type = "button"; x.title = "Remove";
  x.onclick = function () { arr.splice(i, 1); onChange(); };
  box.appendChild(x);
  return box;
}

function heList(obj, k, f) {
  var arr = obj[k] = obj[k] || [];
  var w = el("div", "hf");
  w.appendChild(el("span", "mono", f.label));
  var redo = function () { heRenderEditor(); heChanged(); };
  arr.forEach(function (v, i) {
    var row = el("div", "hf__row");
    var input = f.long ? el("textarea") : el("input");
    if (f.long) input.rows = 4; else input.type = "text";
    input.value = v;
    input.addEventListener("input", function () { arr[i] = input.value; heChanged(); });
    row.appendChild(input);
    row.appendChild(heRowTools(arr, i, redo));
    w.appendChild(row);
  });
  var add = el("button", "hf__add", "+ Add");
  add.type = "button";
  add.onclick = function () { arr.push(""); redo(); };
  w.appendChild(add);
  if (f.rich) w.appendChild(el("span", "note", RICH));
  return w;
}

function heObjects(obj, k, f) {
  var arr = obj[k] = obj[k] || [];
  var w = el("div", "hf");
  w.appendChild(el("span", "mono", f.label));
  var redo = function () { heRenderEditor(); heChanged(); };
  arr.forEach(function (item, i) {
    var box = el("div", "hf__obj");
    var head = el("div", "hf__objhead");
    head.appendChild(el("span", "mono", f.item + " " + (i + 1)));
    head.appendChild(heRowTools(arr, i, redo));
    box.appendChild(head);
    f.sub.forEach(function (sf) { box.appendChild(heFieldFor(item, sf)); });
    w.appendChild(box);
  });
  var add = el("button", "hf__add", "+ Add " + f.item);
  add.type = "button";
  add.onclick = function () { arr.push(JSON.parse(JSON.stringify(f.blank))); redo(); };
  w.appendChild(add);
  return w;
}

function hePhotos(obj, k, label) {
  var arr = obj[k] = obj[k] || [];
  var w = el("div", "hf");
  w.appendChild(el("span", "mono", label));
  var grid = el("div", "hf__photos");
  var redo = function () { heRenderEditor(); heChanged(); };
  arr.forEach(function (src, i) {
    var ph = el("div", "hf__ph");
    ph.title = "Click to swap this photo";
    ph.innerHTML = '<img loading="lazy" alt="" src="/' + heThumb(src) + '">';
    ph.querySelector("img").onclick = function () {
      hePick(function (pick) { arr[i] = pick; redo(); });
    };
    var tools = el("div", "tools");
    [["←", -1], ["→", 1]].forEach(function (t) {
      var b = el("button", "", t[0]); b.type = "button";
      b.onclick = function (e) { e.stopPropagation(); heMove(arr, i, t[1]); redo(); };
      tools.appendChild(b);
    });
    var x = el("button", "x", "✕"); x.type = "button"; x.title = "Remove";
    x.onclick = function (e) { e.stopPropagation(); arr.splice(i, 1); redo(); };
    tools.appendChild(x);
    ph.appendChild(tools);
    grid.appendChild(ph);
  });
  var add = el("button", "hf__new", "+ Add photo");
  add.type = "button";
  add.onclick = function () { hePick(function (pick) { arr.push(pick); redo(); }); };
  grid.appendChild(add);
  w.appendChild(grid);
  return w;
}

function heOnePhoto(obj, k, label, removable) {
  var w = el("div", "hf");
  w.appendChild(el("span", "mono", label));
  var grid = el("div", "hf__photos");
  var pick = function () {
    hePick(function (src) { obj[k] = src; heRenderEditor(); heChanged(); });
  };
  if (obj[k]) {
    var ph = el("div", "hf__ph");
    ph.title = "Click to swap this photo";
    ph.innerHTML = '<img loading="lazy" alt="" src="/' + heThumb(obj[k]) + '">';
    ph.querySelector("img").onclick = pick;
    if (removable) {
      var tools = el("div", "tools");
      tools.appendChild(el("span", "", ""));
      var x = el("button", "x", "✕"); x.type = "button"; x.title = "Remove";
      x.onclick = function (e) { e.stopPropagation(); obj[k] = ""; heRenderEditor(); heChanged(); };
      tools.appendChild(x);
      ph.appendChild(tools);
    }
    grid.appendChild(ph);
  }
  var b = el("button", "hf__new", obj[k] ? "Change" : "+ Pick photo");
  b.type = "button";
  b.onclick = pick;
  grid.appendChild(b);
  w.appendChild(grid);
  return w;
}

function heFieldFor(obj, f) {
  if (f.type === "photos") return hePhotos(obj, f.k, f.label);
  if (f.type === "photo") return heOnePhoto(obj, f.k, f.label, true);
  if (f.type === "rating") {
    return heSelectBox(obj, f.k, f.label, [5, 4, 3, 2, 1].map(function (n) {
      return [String(n), "★★★★★".slice(0, n) + "  (" + n + ")"];
    }));
  }
  if (f.type === "list") return heList(obj, f.k, f);
  if (f.type === "objects") return heObjects(obj, f.k, f);
  if (f.type === "quotetype") {
    return heSelectBox(obj, f.k, f.label, [["", "(none)"]].concat(
      HE.quoteTypes.map(function (t) { return [t, t]; })));
  }
  return heText(obj, f.k, f.label, f);
}

function heThumb(src) {
  return /^images\//.test(src) ? src.replace(/^images\//, "images/thumbs/") : src;
}

function heRenderEditor() {
  var box = document.getElementById("he-editor");
  box.innerHTML = "";
  if (!HE.sel) return;
  var form = el("div", "he__form");

  if (HE.sel === "settings") {
    var seo = HE.home.seo;
    form.appendChild(el("h3", "", "Google title, description & share photo"));
    form.appendChild(el("p", "note", "What shows in Google results and when the site is " +
      "shared in a text or on social media. Keep your main search words in both."));
    form.appendChild(heText(seo, "title", "Title (about 60 characters)", { max: 60 }));
    form.appendChild(heText(seo, "description", "Description (about 155 characters)",
                            { type: "textarea", max: 155 }));
    form.appendChild(heOnePhoto(seo, "shareImage", "Share photo (shown when the link is shared)"));
  } else if (HE.sel === "theme") {
    var th = HE.home.theme;
    form.appendChild(el("h3", "", "Colors, fonts & corners"));
    form.appendChild(el("p", "note", "These change every page of the site. Dark backgrounds " +
      "suit the photos best."));
    var colors = el("div", "hf__colors");
    [["bg", "Background"], ["bgRaise", "Cards & boxes"], ["ink", "Main text"],
     ["inkDim", "Small / grey text"], ["accent", "Accent"]].forEach(function (c) {
      var lab = el("label", "hf__color");
      var input = el("input"); input.type = "color"; input.value = th[c[0]];
      input.addEventListener("input", function () { th[c[0]] = input.value; heChanged(); });
      lab.appendChild(input); lab.appendChild(document.createTextNode(c[1]));
      colors.appendChild(lab);
    });
    form.appendChild(colors);
    var range = el("input"); range.type = "range"; range.min = 0; range.max = 40;
    range.value = th.radius;
    var rv = el("span", "", " " + th.radius + "px");
    range.addEventListener("input", function () {
      th.radius = Number(range.value); rv.textContent = " " + range.value + "px"; heChanged();
    });
    form.appendChild(heField("Corner roundness (0 = square)", range, rv));
    var fontNames = { oswald: "Oswald (tall, narrow)", archivo: "Archivo", helvetica: "Helvetica",
                      georgia: "Georgia (serif)", system: "System" };
    var fonts = HE.fonts.map(function (f) { return [f, fontNames[f] || f]; });
    form.appendChild(heSelectBox(th, "fontDisplay", "Font for your big name", fonts));
    form.appendChild(heSelectBox(th, "fontBody", "Font for paragraphs", fonts));
    form.appendChild(heSelectBox(th, "fontUi", "Font for labels and buttons", fonts));
    var reset = el("button", "ghost", "Reset colors, fonts & corners");
    reset.type = "button";
    reset.onclick = function () {
      HE.home.theme = JSON.parse(JSON.stringify(HE.defaultTheme));
      heRenderEditor(); heChanged();
    };
    form.appendChild(reset);
  } else {
    var s = heSection(HE.sel);
    if (!s) return;
    var info = SECTIONS[s.type];
    form.appendChild(el("h3", "", info.name));
    if (info.about) form.appendChild(el("p", "note", info.about));
    if (!s.visible) form.appendChild(el("p", "note", "This section is hidden. Click 👁 / — in the list to show it."));
    info.fields.forEach(function (f) { form.appendChild(heFieldFor(s, f)); });
  }
  box.appendChild(form);
}

/* ---------- photo picker ---------- */

var HE_PICK = null, HE_SHOWN = 0;

function hePick(cb) {
  HE_PICK = cb;
  document.getElementById("he-picker").hidden = false;
  var q = document.getElementById("hep-q");
  q.value = "";
  heFillPicker(true);
  q.focus();
}

function heClosePicker() {
  document.getElementById("he-picker").hidden = true;
  HE_PICK = null;
}

function heUsed() {
  var used = {};
  HE.home.sections.forEach(function (s) {
    (s.photos || []).forEach(function (p) { used[p] = 1; });
    if (s.photo) used[s.photo] = 1;
  });
  return used;
}

function heFillPicker(fresh) {
  var grid = document.getElementById("hep-grid");
  var q = document.getElementById("hep-q").value.trim().toLowerCase();
  var tag = document.getElementById("hep-tag").value;
  var hits = HE.photos.filter(function (p) {
    if (tag && (p.tags || []).indexOf(tag) === -1) return false;
    if (!q) return true;
    return [p.title, p.game, p.src, (p.tags || []).join(" ")].join(" ")
      .toLowerCase().indexOf(q) !== -1;
  });
  if (fresh) { grid.innerHTML = ""; HE_SHOWN = 0; grid.scrollTop = 0; }
  var more = grid.querySelector(".hep__more");
  if (more) more.remove();
  var used = heUsed();
  hits.slice(HE_SHOWN, HE_SHOWN + 240).forEach(function (p) {
    var b = el("button", used[p.src] ? "is-used" : "");
    b.type = "button";
    b.title = (p.game ? p.game + " — " : "") + p.title;
    b.innerHTML = '<img loading="lazy" alt="" src="/' + heThumb(p.src) + '">';
    b.onclick = function () { var cb = HE_PICK; heClosePicker(); if (cb) cb(p.src); };
    grid.appendChild(b);
  });
  HE_SHOWN += 240;
  if (HE_SHOWN < hits.length) {
    var m = el("button", "ghost hep__more", "Show more (" + (hits.length - HE_SHOWN) + " left)");
    m.type = "button";
    m.onclick = function () { heFillPicker(false); };
    grid.appendChild(m);
  }
  if (!hits.length) grid.innerHTML = '<p class="mono">No photos match that.</p>';
}

document.getElementById("hep-q").addEventListener("input", function () { heFillPicker(true); });
document.getElementById("hep-tag").addEventListener("change", function () { heFillPicker(true); });
document.getElementById("hep-close").onclick = heClosePicker;
document.getElementById("he-picker").addEventListener("click", function (e) {
  if (e.target.id === "he-picker") heClosePicker();
});
document.addEventListener("keydown", function (e) {
  if (e.key === "Escape" && !document.getElementById("he-picker").hidden) heClosePicker();
});

/* ---------- preview ---------- */

var heFrame = document.getElementById("he-frame");

function heReload() {
  var y = 0;
  try { y = heFrame.contentWindow.scrollY || 0; } catch (e) {}
  heFrame.dataset.y = y;
  heFrame.src = "/index.html?studio=" + Date.now();
}

function heMarkPreview(scroll) {
  var d;
  try { d = heFrame.contentDocument; } catch (e) { return; }
  if (!d || !d.body) return;
  d.querySelectorAll(".he-on").forEach(function (n) { n.classList.remove("he-on"); });
  var node = HE.sel && d.querySelector('[data-section="' + HE.sel + '"]');
  if (!node) return;
  node.classList.add("he-on");
  if (scroll) node.scrollIntoView({ block: "start" });
}

heFrame.addEventListener("load", function () {
  var d = heFrame.contentDocument, w = heFrame.contentWindow;
  if (!d || !d.body) return;
  d.documentElement.style.scrollBehavior = "auto";
  var st = d.createElement("style");
  st.textContent =
    "[data-section]{cursor:pointer}" +
    "[data-section]:hover{outline:2px dashed #6ee7a8;outline-offset:-2px}" +
    "[data-section].he-on{outline:2px solid #6ee7a8;outline-offset:-2px}" +
    "[data-slot-photo]{outline:2px dashed rgba(110,231,168,.6);outline-offset:-4px}" +
    "[data-slot-photo]:hover{outline:3px solid #6ee7a8}" +
    ".about__photo--empty{display:grid!important}" +
    ".he-tag{position:fixed;z-index:2147483647;pointer-events:none;background:#6ee7a8;" +
    "color:#000;font:600 11px/1 system-ui,sans-serif;padding:6px 9px;border-radius:5px}";
  d.head.appendChild(st);
  var tag = d.createElement("div");
  tag.className = "he-tag"; tag.hidden = true;
  d.body.appendChild(tag);

  d.addEventListener("mousemove", function (e) {
    var slot = e.target.closest("[data-slot-photo]");
    var sec = e.target.closest("[data-section]");
    if (!sec) { tag.hidden = true; return; }
    var info = SECTIONS[(heSection(sec.dataset.section) || {}).type] || {};
    tag.textContent = slot ? "Click to change this photo" : "Edit: " + (info.name || "section");
    tag.hidden = false;
    tag.style.left = Math.min(e.clientX + 14, w.innerWidth - 220) + "px";
    tag.style.top = (e.clientY + 16) + "px";
  });
  d.addEventListener("mouseleave", function () { tag.hidden = true; });

  /* in the preview a click picks what to edit; nothing navigates away */
  d.addEventListener("click", function (e) {
    var a = e.target.closest("a, button, summary");
    var sec = e.target.closest("[data-section]");
    var slot = e.target.closest("[data-slot-photo]");
    if (a || sec) { e.preventDefault(); e.stopPropagation(); }
    if (!sec) return;
    heSelect(sec.dataset.section, false);
    if (slot) {
      var parts = slot.dataset.slotPhoto.split(":");
      var s = heSection(sec.dataset.section);
      var i = Number(parts[1]);
      hePick(function (src) {
        if (parts[1] === "photo") {
          s.photo = src;          /* a single-photo spot, like About's */
        } else {
          s.photos = s.photos || [];
          if (i < s.photos.length) s.photos[i] = src; else s.photos.push(src);
        }
        heRenderEditor(); heChanged();
      });
    }
  }, true);

  w.scrollTo(0, Number(heFrame.dataset.y || 0));
  heMarkPreview(false);
});

document.querySelectorAll("[data-device]").forEach(function (b) {
  b.addEventListener("click", function () {
    document.querySelectorAll("[data-device]").forEach(function (x) {
      x.classList.toggle("is-on", x === b);
    });
    document.getElementById("he-frame-wrap").classList.toggle("is-phone",
      b.dataset.device === "phone");
  });
});

document.getElementById("he-revert").onclick = function () {
  if (!confirm("Put the home page back the way it is on the web right now?\n\n" +
               "Every change since your last Publish is undone.")) return;
  api("/api/home/revert", {}).then(function (res) {
    if (res.error) throw new Error(res.error);
    HE.home = res.home;
    heStatus("Back to the published version.", "ok");
    heRenderLists(); heRenderEditor(); heReload();
  }).catch(function (e) { heStatus(e.message, "bad"); });
};

document.getElementById("he-publish").onclick = function () {
  var wrap = document.getElementById("publish-wrap");
  document.getElementById("publish").click();
  wrap.scrollIntoView({ behavior: "smooth" });
  heStatus("Publishing… see the message at the bottom of the page.");
};

(function () {
  var dl = document.createElement("datalist");
  dl.id = "he-links";
  LINKS.forEach(function (l) {
    var o = document.createElement("option"); o.value = l; dl.appendChild(o);
  });
  document.body.appendChild(dl);
})();


loadLibrary();
</script>
</body>
</html>
"""


# ---------------- entry point ----------------

if __name__ == "__main__":
    import sys
    regenerate_photos_js(load_photos())
    regenerate_reviews_js()
    make_thumbs(load_photos())
    home_page.build(load_photos())
    stamp_assets()
    if "--regen" in sys.argv:
        print("js/photos.js + js/reviews.js + index.html regenerated from data/, "
              "thumbnails up to date, css/js links fingerprinted")
        sys.exit(0)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), StudioHandler)
    print("Site:   http://localhost:%d" % PORT)
    print("Studio: http://localhost:%d/studio" % PORT)
    server.serve_forever()
