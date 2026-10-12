#!/usr/bin/env python3
"""Import finished shoots from the Creator Pro drive, end to end.

Every final on the drive is tagged Green in Finder (on the folder, the
file, or both). This finds them by reading the tags, so there is no list
of folders to keep up to date - only the game each folder belongs to.

For every green photograph not already on the site:

  1. clean master   -> images/_originals/<name>.jpg   (gitignored)
  2. site copy      -> images/<name>.jpg              (2400px long edge)
  3. thumbnail      -> images/thumbs/<name>.jpg       (via studio.py --regen)
  4. manifest entry -> top of data/photos.json, newest game first

No watermark is burned in: the published copy is the clean photograph.

"Already on the site" is decided by looking at the pictures, not their
names - every final is called Erickson_Garrett-NNN.jpg, so names collide
across folders. A photograph matching anything in images/, _originals/ or
_removed/ is skipped, so a photo taken down for a parent never comes back.

    python3 tools/import_shoot.py --list   green folders and their games
    python3 tools/import_shoot.py          dry run: what would be imported
    python3 tools/import_shoot.py --run    import it
"""

import ctypes
import glob
import json
import os
import plistlib
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVE = "/Volumes/Creator Pro"
IMAGES = os.path.join(ROOT, "images")
ORIGINALS = os.path.join(IMAGES, "_originals")
REMOVED = os.path.join(IMAGES, "_removed")
DATA = os.path.join(ROOT, "data", "photos.json")

LONG_EDGE = 2400        # matches every site copy already in the manifest
SITE_QUALITY = 88
MASTER_QUALITY = 95

# Which game each green folder belongs to - worked out by looking at the
# photographs, not by trusting the folder names. Several folders can feed
# one game (per-athlete selects shot at the same game), and they share a
# slug so the numbering carries on. `date` is the game day; a run puts
# the newest game at the top of the portfolio.
#
# A green folder missing from here is reported and left alone until it
# gets a line.
FOOTBALL = ["sports", "football", "people"]
SOCCER = ["sports", "soccer", "people"]
TENNIS = ["sports", "tennis", "people"]
HOCKEY = ["sports", "hockey", "people"]
DCDS = "Detroit Country Day, Michigan"
MI = "Michigan"

HOCO = {"game": "DCDS Varsity Football vs Cranbrook — Homecoming",
        "slug": "hoco", "title": "Homecoming vs Cranbrook",
        "tags": FOOTBALL, "location": DCDS, "date": "2026-10-10"}
LOYOLA = {"game": "DCDS Varsity Football vs Loyola",
          "slug": "loyola", "title": "Varsity Football vs Loyola",
          "tags": FOOTBALL, "location": MI, "date": "2026-10-02"}
RICE = {"game": "Brother Rice vs Orchard Lake St. Mary's — Football",
        "slug": "riceolsm", "title": "Rice vs St. Mary's",
        "tags": FOOTBALL, "location": MI, "date": "2026-09-25"}

GAMES = {
    "Hoco Finals": HOCO,               # EXIF stripped; same game as Hoco Finals 2
    "Hoco Finals 2": HOCO,
    "DCDS_VSLOYOLA_FINALS": LOYOLA,
    "LOYOLA Part 2": LOYOLA,
    "JJ + CARSEN": LOYOLA,             # two players' selects from the Loyola game
    "FRANCO HOCKEY FINALS": {
        "game": "Franco — Hockey", "slug": "franco", "title": "Franco — Hockey",
        "tags": HOCKEY, "location": MI, "date": "2026-10-01"},
    "SEATENFINALS": {
        "game": "Seaholm Boys Varsity Tennis — Senior Team", "slug": "seaten",
        "title": "Seaholm Tennis", "tags": TENNIS, "location": MI,
        "date": "2026-09-29"},
    "dylan hockey finals": {
        "game": "Dylan — Hockey", "slug": "dylan", "title": "Dylan — Hockey",
        "tags": HOCKEY, "location": MI, "date": "2026-09-27"},
    "Rice Vs OLSM PreP Finals 1": RICE,
    "st. Marys #0": RICE,              # one St. Mary's player from that game

    # imported before - listed so new frames added to them land in the
    # right game
    "DCDVARSOC_FINALS": {
        "game": "DCDS Varsity Soccer", "slug": "varsoc",
        "title": "Varsity Soccer", "tags": SOCCER, "location": DCDS},
    "DCDSVSLIGGET_TEN": {
        "game": "DCDS vs Liggett — Tennis", "slug": "ligget",
        "title": "DCDS vs Liggett", "tags": TENNIS, "location": MI},
    "DCDVSOC_TOURNIMENTMATCH1_FINALS": {
        "game": "DCDS vs Cass Tech — Varsity Soccer", "slug": "casstech",
        "title": "DCDS vs Cass Tech", "tags": SOCCER, "location": MI},
    "TOURNIMENTMATCH2_FINALS": {
        "game": "DCDS Bartoshuk Tournament Match 2", "slug": "bartoshuk",
        "title": "Bartoshuk Match 2", "tags": SOCCER, "location": MI},
    "DCDSJVFOT_VSDCHS_FINALS": {
        "game": "DCDS JV Football vs DCHS", "slug": "jvfot",
        "title": "JV Football vs DCHS", "tags": FOOTBALL, "location": MI},
    "DCDSVARFOT_VSRED_FINALS": {
        "game": "DCDS Varsity Football vs Redford", "slug": "varfot",
        "title": "Varsity Football vs Redford", "tags": FOOTBALL, "location": MI},
    "DCDSVAR_FOTVSHOLT_FINALS": {
        "game": "DCDS Varsity Football vs Holt", "slug": "holt",
        "title": "Varsity Football vs Holt", "tags": FOOTBALL, "location": MI},
    "DCDSVARSOC_VSCRANB_FINALS": {
        "game": "DCDS Varsity Soccer vs Cranbrook", "slug": "cranb",
        "title": "Varsity Soccer vs Cranbrook", "tags": SOCCER, "location": MI},
    "Hunter Tennis_Finals": {
        "game": "Hunter — Tennis", "slug": "hunterten",
        "title": "Hunter — Tennis", "tags": TENNIS, "location": MI},
    "Landon#8": {
        "game": "Landon #8 — Varsity Football", "slug": "landon",
        "title": "Landon #8", "tags": FOOTBALL, "location": MI},
    "QBCarsen": {
        "game": "Carsen — Varsity Football", "slug": "carsen",
        "title": "Carsen — Quarterback", "tags": FOOTBALL, "location": MI},
    "DCD_JVFOT_PRC FINALS": {
        "game": "DCDS JV Football — Practice", "slug": "practice",
        "title": "Practice", "tags": FOOTBALL, "location": DCDS},
    "SEA_TEN_FINALS": {
        "game": "Seaholm Boys Varsity Tennis - Match Day", "slug": "court",
        "title": "Court", "tags": ["sports", "tennis"], "location": MI},
    # DCDVOL+JVSOC holds two sports (volleyball, then JV soccer) and is
    # fully imported; a new frame there has to be sorted by hand.
    "DCDVOL+JVSOC": None,
}

# Copies, not photographs: client proofs, Instagram crops, contact sheets.
SKIP_DIRS = ("watermarked", "preview", "previews", "instagram")
SKIP_FILES = ("_player_index",)
PHOTO_EXT = (".jpg", ".jpeg")


# ---------- finding green photographs ----------

_libc = ctypes.CDLL("/usr/lib/libc.dylib", use_errno=True)
_libc.getxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p,
                           ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
_libc.getxattr.restype = ctypes.c_ssize_t
_TAGS = b"com.apple.metadata:_kMDItemUserTags"


def finder_tags(path):
    """Finder tag names on a file or folder ("Green", "Red", ...)."""
    p = path.encode()
    n = _libc.getxattr(p, _TAGS, None, 0, 0, 1)        # 1 = XATTR_NOFOLLOW
    if n <= 0:
        return []
    buf = ctypes.create_string_buffer(n)
    n = _libc.getxattr(p, _TAGS, buf, n, 0, 1)
    if n <= 0:
        return []
    try:
        return [t.split("\n")[0] for t in plistlib.loads(buf.raw[:n])]
    except Exception:
        return []


def green_photos():
    """{top-level folder: [photo paths]} for every green photograph.
    A photograph counts if it, or any folder above it, is tagged Green."""
    found = {}

    def walk(path, inherited):
        try:
            names = sorted(os.listdir(path))
        except OSError:
            return
        for name in names:
            if name.startswith("."):
                continue
            full = os.path.join(path, name)
            if os.path.isdir(full):
                if name.lower() in SKIP_DIRS or name == "System Volume Information":
                    continue
                walk(full, inherited or "Green" in finder_tags(full))
            elif name.lower().endswith(PHOTO_EXT):
                if any(k in name.lower() for k in SKIP_FILES):
                    continue
                if inherited or "Green" in finder_tags(full):
                    top = os.path.relpath(full, DRIVE).split(os.sep)[0]
                    if top == name:
                        top = "."                 # loose at the drive root
                    found.setdefault(top, []).append(full)

    walk(DRIVE, False)
    return found


# ---------- telling photographs apart ----------

def sig(path):
    """48x48 normalized grayscale — enough to tell two photographs apart
    when their filenames collide across folders, which these do."""
    try:
        im = Image.open(path).convert("L").resize((48, 48), Image.LANCZOS)
        a = np.asarray(im, dtype=np.float32)
        a -= a.mean()
        s = a.std()
        return a / s if s > 1e-6 else a
    except Exception:
        return None


def same_photo(s, sigs):
    return bool(sigs) and min(float(np.mean((s - t) ** 2)) for t in sigs) < 0.08


def site_signatures():
    """Everything the site has or had: published copies, clean masters,
    and photographs taken down."""
    paths = []
    for d in (IMAGES, ORIGINALS, REMOVED):
        paths += sorted(glob.glob(os.path.join(d, "*.jpg")))
    return [s for s in map(sig, paths) if s is not None]


def next_index(photos, slug):
    n = 0
    for p in photos:
        m = re.match(re.escape(slug) + r"-(\d+)\.jpg$", os.path.basename(p["src"]))
        if m:
            n = max(n, int(m.group(1)))
    return n + 1


# ---------- plan + run ----------

def plan():
    photos = json.load(open(DATA))
    sigs = site_signatures()
    found = green_photos()
    jobs, unknown, counters = [], {}, {}

    for folder in sorted(found):
        shoot = GAMES.get(folder)
        fresh = []
        for src in found[folder]:
            s = sig(src)
            if s is None or same_photo(s, sigs):
                continue                       # already on the site
            sigs.append(s)                     # guard against dupes inside a run
            fresh.append(src)
        if not fresh:
            continue
        if not shoot:
            unknown[folder] = len(fresh)
            continue
        slug = shoot["slug"]
        counters.setdefault(slug, next_index(photos, slug))
        for src in fresh:
            i = counters[slug]
            counters[slug] += 1
            jobs.append({
                "src": src,
                "folder": folder,
                "name": "%s-%02d.jpg" % (slug, i),
                "title": "%s %02d" % (shoot["title"], i),
                "game": shoot["game"],
                "tags": shoot["tags"],
                "location": shoot["location"],
                "date": shoot.get("date", ""),
            })
    # newest game first; within a game, the order the frames were numbered
    jobs.sort(key=lambda j: j["date"], reverse=True)
    return jobs, unknown


def run(jobs):
    photos = json.load(open(DATA))
    os.makedirs(ORIGINALS, exist_ok=True)
    added = []

    for n, j in enumerate(jobs, 1):
        im = ImageOps.exif_transpose(Image.open(j["src"])).convert("RGB")
        scale = LONG_EDGE / max(im.size)
        if scale < 1:
            im = im.resize((round(im.width * scale), round(im.height * scale)),
                           Image.LANCZOS)

        im.save(os.path.join(ORIGINALS, j["name"]), "JPEG",
                quality=MASTER_QUALITY, optimize=True)
        im.save(os.path.join(IMAGES, j["name"]), "JPEG",
                quality=SITE_QUALITY, optimize=True, progressive=True)

        added.append({
            "src": "images/" + j["name"],
            "title": j["title"],
            "location": j["location"],
            "year": 2026,
            "orientation": "portrait" if im.height > im.width else "landscape",
            "tags": sorted(set(j["tags"])),
            "w": im.width,
            "h": im.height,
            "archiveOnly": True,
            "game": j["game"],
        })
        if n % 25 == 0:
            print("  %d/%d..." % (n, len(jobs)))

    # new work leads the portfolio
    photos = added + photos
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(photos, f, indent=2, ensure_ascii=False)
        f.write("\n")
    subprocess.run([sys.executable, "studio.py", "--regen"], cwd=ROOT, check=True)
    print("imported %d photographs" % len(jobs))


def main():
    if not os.path.isdir(DRIVE):
        sys.exit("Creator Pro is not mounted at %s" % DRIVE)

    if "--list" in sys.argv:
        found = green_photos()
        for folder in sorted(found):
            shoot = GAMES.get(folder)
            game = shoot["game"] if shoot else (
                "(sort by hand)" if folder in GAMES else "(no game yet - add to GAMES)")
            print("%-34s %3d photos -> %s" % (folder, len(found[folder]), game))
        return

    jobs, unknown = plan()
    by_game = {}
    for j in jobs:
        key = (j["game"], j["folder"])
        by_game[key] = by_game.get(key, 0) + 1
    print("to import: %d photographs" % len(jobs))
    for (game, folder), n in by_game.items():
        print("  %3d  %-50s <- %s" % (n, game, folder))
    for folder, n in sorted(unknown.items()):
        print("  %3d  NOT IMPORTED - %s has no game in GAMES" % (n, folder))

    if "--run" in sys.argv:
        if jobs:
            run(jobs)
    else:
        print("\n(dry run — pass --run to actually import)")


if __name__ == "__main__":
    main()
