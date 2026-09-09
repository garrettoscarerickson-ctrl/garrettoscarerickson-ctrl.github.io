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

The Bookings tab is the one part of Studio that never touches the site:
it is a private diary of who is booked, kept in data/bookings.json.
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


SHOP = os.path.join(ROOT, "data", "shop.json")


def load_shop():
    try:
        with open(SHOP, "r", encoding="utf-8") as f:
            return json.load(f)
    except (IOError, ValueError):
        return {"photoPrice": 1, "tiers": [], "addOns": [], "games": {}}


def save_shop(cfg):
    """Prices -> data/shop.json -> js/shop-config.js, the same
    manifest-then-generate shape the photos already use."""
    with open(SHOP, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    header = ("/* GENERATED FILE - do not edit by hand.\n"
              "   Source of truth: data/shop.json\n"
              "   Change prices in Studio (Store tab), or edit the JSON and run:\n"
              "     python3 studio.py --regen\n"
              "*/\n\n")
    with open(os.path.join(ROOT, "js", "shop-config.js"), "w",
              encoding="utf-8") as f:
        f.write(header + "window.SHOP_CONFIG = " +
                json.dumps(cfg, indent=2, ensure_ascii=False) + ";\n")


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
    # stays "05", and match what the store's jersey filter stores.
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
    """Approved reviews -> js/reviews.js for the About page."""
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
    # Jersey numbers, so a parent can filter a game down to their kid.
    # Free text rather than a picker: numbers vary by sport and season,
    # and a wrong-but-fixed list is worse than none.
    if "players" in body:
        nums = []
        for n in (body.get("players") or []):
            n = re.sub(r"[^0-9]", "", str(n))
            if n and n not in nums:
                nums.append(n)
        if nums:
            entry["players"] = sorted(nums, key=int)
        else:
            entry.pop("players", None)
    # placement decides where a photo lives:
    #   archive  -> archive only, never on the home page (all Studio uploads)
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
            self.send_json({"photos": photos, "tags": all_tags(photos),
                            "shop": load_shop(),
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
            elif self.path == "/api/shop":
                self.api_shop()
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
        # Studio uploads always go to the archive only — never the home page.
        body["placement"] = "archive"
        entry = clean_entry(body, photos)
        src = unique_src(slugify(entry["title"]), photos)
        with open(os.path.join(ROOT, src), "wb") as f:
            f.write(raw)
        entry["src"] = src
        # record pixel dimensions so the archive can reserve exact space
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

        # The store serves its own watermarked copy under images/shop/. Taking
        # a photo out of the manifest hides it from every page but leaves that
        # file sitting at a guessable public URL — so a takedown looked done
        # while the picture was still downloadable. Remove it too.
        preview = os.path.join(IMAGES, "shop", os.path.basename(body["src"]))
        if os.path.exists(preview):
            shutil.move(preview, os.path.join(REMOVED, stamp + "shop-" +
                                              os.path.basename(preview)))

        save_photos(keep)
        self.send_json({"ok": True, "removedPreview": os.path.exists(preview) is False})

    def api_shop(self):
        body = self.read_body()
        cfg = load_shop()
        if "photoPrice" in body:
            try:
                price = float(body["photoPrice"])
            except (TypeError, ValueError):
                raise ValueError("Price must be a number.")
            if price < 0:
                raise ValueError("Price cannot be negative.")
            cfg["photoPrice"] = int(price) if price == int(price) else price
        if "tiers" in body:
            cfg["tiers"] = body["tiers"]
        if "addOns" in body:
            cfg["addOns"] = body["addOns"]
        if "games" in body:
            cfg["games"] = body["games"]
        save_shop(cfg)
        self.send_json({"ok": True, "shop": cfg})

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
        """Rename a group, or clear it so its photographs leave the store."""
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
                # dropping the game takes them off the store but leaves them
                # in the archive - removing a photograph is a separate act
                p.pop("game", None)
        save_photos(photos)

        cfg = load_shop()
        games = cfg.get("games") or {}
        if old_name in games:
            entry = games.pop(old_name)
            if new_name:
                games[new_name] = entry
            cfg["games"] = games
            save_shop(cfg)

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
.pricebox{border:1px solid var(--line);border-radius:14px;padding:1.25rem;
          display:flex;flex-direction:column;gap:.9rem;max-width:52rem}
.pricerow{display:flex;justify-content:space-between;align-items:center;
          gap:1rem;padding:.5rem 0}
.dollar{display:inline-flex;align-items:center;gap:.25rem;color:var(--dim)}
.pricerow input,.tierrow input{background:#111;border:1px solid var(--line);
  border-radius:8px;color:var(--ink);font:inherit;padding:.45rem .6rem}
.pricerow input[type=number]{width:6rem;text-align:right}
.tierrow{display:grid;grid-template-columns:1fr 7rem 10rem;gap:.5rem;
         align-items:center;padding:.35rem 0}
.tierrow .mono{color:var(--dim)}
.gcard{border:1px solid var(--line);border-radius:14px;padding:1rem 1.15rem;
       margin-bottom:.9rem}
.ghead{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap}
.ghead input{flex:1;min-width:14rem;background:#111;border:1px solid var(--line);
             border-radius:8px;color:var(--ink);font:inherit;padding:.5rem .7rem}
.delivrow{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;
          margin-top:.75rem;padding-top:.75rem;border-top:1px solid var(--line)}
.delivrow input{flex:1;min-width:18rem;background:#111;border:1px solid var(--line);
                border-radius:8px;color:var(--ink);font:inherit;padding:.45rem .6rem}
.dstatus{color:var(--dim)}
.gthumbs{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.9rem}
.gthumb{position:relative;width:78px;height:78px;border-radius:8px;
        overflow:hidden;border:1px solid var(--line)}
.gthumb img{width:100%;height:100%;object-fit:cover;display:block}
.gthumb button{position:absolute;top:2px;right:2px;width:20px;height:20px;
  border-radius:50%;border:0;background:rgba(0,0,0,.72);color:#f87171;
  cursor:pointer;font-size:12px;line-height:1;padding:0}
.gthumb button:hover{background:#f87171;color:#000}
.gthumb{height:auto;width:78px}
.gthumb img{height:78px}
.jersey{width:100%;box-sizing:border-box;background:#111;border:1px solid var(--line);
        border-top:0;border-radius:0 0 8px 8px;color:var(--ink);font:inherit;
        font-size:11px;text-align:center;padding:3px 2px}
.jersey:focus{outline:none;border-color:var(--ink)}
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

<div class="tabs mono" id="tabs">
  <button class="tab is-on" data-panel="panel-photos">Photos</button>
  <button class="tab" data-panel="panel-store">Store</button>
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

<section id="panel-store" hidden>
  <h2>Prices</h2>
  <div class="pricebox">
    <label class="pricerow">
      <span class="mono">Per photograph in the store</span>
      <span class="dollar">$<input type="number" id="sh-price" min="0" step="1"></span>
    </label>
    <div id="sh-tiers"></div>
    <h3 class="mono">Add-ons</h3>
    <div id="sh-addons"></div>
    <button class="primary" id="sh-save">Save prices</button>
    <span class="status" id="sh-status"></span>
  </div>

  <h2>Groups <span class="mono" id="sh-gcount"></span></h2>
  <p class="mono hint">A group is one game or shoot. Renaming one renames it on
    every photograph in it. Removing a photograph here takes it off the whole
    site — store, archive and sports page.<br>
    The box under each photograph is its jersey numbers — type them separated
    by spaces (<b>7 12</b> for two players) and they become filters buyers can
    search by. Leave it blank if no number is visible.</p>
  <div id="sh-games"></div>
</section>

<section id="panel-bookings" hidden>
  <h2>Add a booking</h2>
  <p class="mono hint">Private. This never goes on the site and never leaves
    this machine &mdash; Publish refuses to run if the file is not gitignored.
    The jersey number is the same one you type under a photograph in the Store
    tab, so once you have shot the game the buyer can filter to it.</p>
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
    <label><span class="mono">Package</span><select id="bk-tier"></select></label>
    <label><span class="mono">Rate</span><input type="number" id="bk-rate"
      min="0" step="1" placeholder="20"></label>
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
   mode "add"     -> new uploads, always go to the Archive (no placement UI)
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
    var note = el("div", "mono", "Adds to the Archive →");
    note.style.marginTop = ".7rem";
    note.style.opacity = ".7";
    f.appendChild(note);
  } else {
    var current = photo.feature || (photo.archiveOnly ? "archive" : "gallery");
    var lab = el("label");
    lab.style.marginTop = ".6rem";
    lab.innerHTML = '<span class="mono">Placement</span>' +
      '<select data-f="placement">' +
      '<option value="archive">Archive only</option>' +
      '<option value="gallery">Home — gallery</option>' +
      '<option value="panel">Home — parallax panel</option>' +
      '<option value="hero">Home — hero (replaces current)</option></select>';
    place = lab.querySelector("select");
    place.value = current;
    f.appendChild(lab);
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
    renderShop(data);
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
      else if (photo.archiveOnly) meta.appendChild(el("span", "mono", "archive"));
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
          "The original and the store copy both move to images/_removed/, " +
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
   the jersey number written down here is the one typed under the frames
   afterwards, and because the shoot and the delivery are the same job. */

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

function tierOptions(sel, current) {
  sel.innerHTML = '<option value=""></option>';
  ((SHOP && SHOP.tiers) || []).forEach(function (t) {
    var o = document.createElement("option");
    o.value = t.name; o.textContent = t.name + " · " + t.price;
    sel.appendChild(o);
  });
  sel.value = current || "";
}

/* Picking a package fills the rate with that tier's price, so the common
   case is two clicks. A range like "$5-10" fills in its lower number and
   waits to be corrected rather than guessing which end applies. */
function rateFromTier(name) {
  var t = ((SHOP && SHOP.tiers) || []).filter(function (x) {
    return x.name === name;
  })[0];
  if (!t) return "";
  var m = String(t.price).match(/\d+(\.\d+)?/);
  return m ? m[0] : "";
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

document.getElementById("bk-tier").onchange = function () {
  var r = document.getElementById("bk-rate");
  if (!r.value) r.value = rateFromTier(this.value);
};

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
  ["panel-photos", "panel-store", "panel-bookings"].forEach(function (id) {
    document.getElementById(id).hidden = (id !== b.dataset.panel);
  });
});

/* ---------- store: prices ---------- */

var SHOP = null;

function q(v) { return String(v == null ? "" : v).replace(/"/g, "&quot;"); }

function renderShop(data) {
  SHOP = data.shop || { photoPrice: 1, tiers: [], addOns: [] };
  document.getElementById("sh-price").value = SHOP.photoPrice;

  var tw = document.getElementById("sh-tiers");
  tw.innerHTML = "<h3 class='mono'>Booking packages</h3>";
  (SHOP.tiers || []).forEach(function (t, i) {
    var row = el("div", "tierrow");
    row.innerHTML =
      '<input value="' + q(t.name)  + '" data-k="name"  data-i="' + i + '">' +
      '<input value="' + q(t.price) + '" data-k="price" data-i="' + i + '">' +
      '<input value="' + q(t.unit)  + '" data-k="unit"  data-i="' + i + '">';
    tw.appendChild(row);
  });

  var aw = document.getElementById("sh-addons");
  aw.innerHTML = "";
  (SHOP.addOns || []).forEach(function (a, i) {
    var row = el("div", "tierrow");
    row.innerHTML =
      '<input value="' + q(a[0]) + '" data-a="0" data-i="' + i + '">' +
      '<input value="' + q(a[1]) + '" data-a="1" data-i="' + i + '">' +
      '<span class="mono">on the About page</span>';
    aw.appendChild(row);
  });
}

document.getElementById("sh-save").onclick = function () {
  var st = document.getElementById("sh-status");
  var tiers = JSON.parse(JSON.stringify(SHOP.tiers || []));
  document.querySelectorAll("#sh-tiers input").forEach(function (inp) {
    tiers[Number(inp.dataset.i)][inp.dataset.k] = inp.value.trim();
  });
  var addOns = (SHOP.addOns || []).map(function (a) { return a.slice(); });
  document.querySelectorAll("#sh-addons input").forEach(function (inp) {
    addOns[Number(inp.dataset.i)][Number(inp.dataset.a)] = inp.value.trim();
  });

  st.textContent = "Saving...";
  api("/api/shop", {
    photoPrice: document.getElementById("sh-price").value,
    tiers: tiers, addOns: addOns
  }).then(function () {
    st.textContent = "Saved. Hit Publish to put it on the live site.";
    loadLibrary();
  }).catch(function (e) { st.textContent = e.message; });
};

/* ---------- store: groups ---------- */

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
      "in the Photos tab and it shows up in the store.</p>";
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

    var deliv = el("div", "delivrow");
    var url = ((SHOP.games || {})[game] || {}).deliveryUrl || "";
    deliv.innerHTML =
      "<span class='mono'>Delivery folder</span>" +
      '<input placeholder="Paste the Google Drive share link for this game" ' +
        'value="' + q(url) + '">' +
      "<button class='ghost'>Save link</button>" +
      "<span class='mono dstatus'></span>";
    card.appendChild(deliv);

    var durl = deliv.querySelector("input");
    var dstat = deliv.querySelector(".dstatus");
    deliv.querySelector("button").onclick = function () {
      var games = JSON.parse(JSON.stringify(SHOP.games || {}));
      games[game] = games[game] || {};
      games[game].deliveryUrl = durl.value.trim();
      dstat.textContent = "Saving...";
      api("/api/shop", { games: games })
        .then(function (r) { SHOP.games = r.shop.games; dstat.textContent = "Saved"; })
        .catch(function (e) { dstat.textContent = e.message; });
    };

    var thumbs = el("div", "gthumbs");
    list.forEach(function (p) {
      var t = el("div", "gthumb");
      t.innerHTML = '<img src="/' + p.src + '" alt="" loading="lazy">' +
                    "<button title='Remove'>x</button>" +
                    '<input class="jersey" value="' +
                      q((p.players || []).join(" ")) +
                      '" placeholder="#" title="Jersey numbers, space separated">';
      var jin = t.querySelector(".jersey");
      jin.onclick = function (e) { e.stopPropagation(); };
      jin.onchange = function () {
        api("/api/update", {
          src: p.src, title: p.title, tags: p.tags,
          location: p.location, year: p.year, orientation: p.orientation,
          players: jin.value.split(/[\s,]+/).filter(Boolean)
        }).then(function () {
          jin.style.borderColor = "#6ee7a8";
          setTimeout(function () { jin.style.borderColor = ""; }, 900);
        }).catch(function (e) { alert(e.message); });
      };

      t.querySelector("button").onclick = function () {
        if (!confirm('Remove "' + p.title + '" from the site?\n\n' +
          "It comes off the store, the archive and the sports page. The " +
          "original and the store copy both move to images/_removed/.")) return;
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
    save_shop(load_shop())
    if "--regen" in sys.argv:
        print("js/photos.js + js/reviews.js regenerated from data/")
        sys.exit(0)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), StudioHandler)
    print("Site:   http://localhost:%d" % PORT)
    print("Studio: http://localhost:%d/studio" % PORT)
    server.serve_forever()
