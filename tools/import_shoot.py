#!/usr/bin/env python3
"""Import a shoot from the Creator Pro drive, end to end.

Bringing in a game used to be four separate steps, and forgetting the
third one — watermarking — publishes the whole batch free and unmarked
with nothing to tell you. So this does all of it in one pass:

  1. site copy      -> images/<name>.jpg     (2400px long edge)
  2. clean master   -> images/_originals/    (gitignored, never published)
  3. watermark      -> burned into the published copy, since it is for sale
  4. store preview  -> images/shop/<name>.jpg
  5. manifest entry -> data/photos.json + regenerated js/photos.js

Idempotent. A photograph already in the manifest is skipped, and nothing
is ever watermarked twice — the clean master in _originals/ is always the
source, so re-running is safe.

    python3 tools/import_shoot.py --list
    python3 tools/import_shoot.py --plan
    python3 tools/import_shoot.py --run
"""

import json
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from build_shop_previews import build_layer, process as build_preview

DRIVE = "/Volumes/Creator Pro"
IMAGES = os.path.join(ROOT, "images")
ORIGINALS = os.path.join(IMAGES, "_originals")
DATA = os.path.join(ROOT, "data", "photos.json")

LONG_EDGE = 2400        # matches every site copy already in the manifest
SITE_QUALITY = 88
ARCHIVE_OPACITY = 0.20  # same as tools/protect_archive.py

# What to bring in, and what it actually is — verified by looking at the
# photographs, not by trusting the folder names. DCDVOL+JVSOC holds two
# different sports, and SEA_TEN_FINALS/_PLAYER_INDEX.jpg is a contact
# sheet rather than a photograph, so neither is imported wholesale.
SHOOTS = [
    {
        "folder": "DCDVARSOC_FINALS",
        "game": "DCDS Varsity Soccer",
        "slug": "varsoc",
        "title": "Varsity Soccer",
        "tags": ["sports", "soccer", "people"],
        "location": "Detroit Country Day, Michigan",
    },
    {
        "folder": "DCDSVSLIGGET_TEN",
        "game": "DCDS vs Liggett — Tennis",
        "slug": "ligget",
        "title": "DCDS vs Liggett",
        "tags": ["sports", "tennis", "people"],
        "location": "Michigan",
    },
    {
        "folder": "DCDVOL+JVSOC",
        "game": "DCDS Volleyball",
        "slug": "vol",
        "title": "Volleyball",
        "tags": ["sports", "volleyball", "people"],
        "location": "Detroit Country Day, Michigan",
        "only": [1, 2, 3, 4, 5, 6, 7, 8, 9],      # by sorted position
    },
    {
        "folder": "DCDVOL+JVSOC",
        "game": "DCDS JV Soccer",
        "slug": "jvsoc",
        "title": "JV Soccer",
        "tags": ["sports", "soccer", "people"],
        "location": "Detroit Country Day, Michigan",
        "only": [10, 11, 12, 13],
    },
    {
        "folder": "DCDVSOC_TOURNIMENTMATCH1_FINALS",
        "game": "DCDS vs Cass Tech — Varsity Soccer",
        "slug": "casstech",
        "title": "DCDS vs Cass Tech",
        "tags": ["sports", "soccer", "people"],
        "location": "Michigan",
    },
    {
        "folder": "DCD_JVFOT_PRC FINALS/Owen",
        "game": "DCDS JV Football — Practice",   # joins the existing group
        "slug": "practice",
        "title": "Practice",
        "tags": ["sports", "football", "people"],
        "location": "Detroit Country Day, Michigan",
    },
]


def files_in(folder):
    root = os.path.join(DRIVE, folder)
    out = []
    for dp, _, fs in os.walk(root):
        for f in sorted(fs):
            if f.lower().endswith((".jpg", ".jpeg")) and not f.startswith("."):
                out.append(os.path.join(dp, f))
    return sorted(out)


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


def site_signatures(photos):
    out = []
    for p in photos:
        name = os.path.basename(p["src"])
        clean = os.path.join(ORIGINALS, name)
        src = clean if os.path.exists(clean) else os.path.join(ROOT, p["src"])
        s = sig(src)
        if s is not None:
            out.append(s)
    return out


def next_index(photos, slug):
    n = 0
    for p in photos:
        m = re.match(re.escape(slug) + r"-(\d+)\.jpg$", os.path.basename(p["src"]))
        if m:
            n = max(n, int(m.group(1)))
    return n + 1


def plan():
    photos = json.load(open(DATA))
    sigs = site_signatures(photos)
    jobs = []
    counters = {}

    for shoot in SHOOTS:
        picked = files_in(shoot["folder"])
        if shoot.get("only"):
            picked = [picked[i - 1] for i in shoot["only"] if i <= len(picked)]

        slug = shoot["slug"]
        counters.setdefault(slug, next_index(photos, slug))

        for src in picked:
            s = sig(src)
            if s is None:
                continue
            if sigs and min(float(np.mean((s - t) ** 2)) for t in sigs) < 0.08:
                continue                       # already on the site
            i = counters[slug]
            counters[slug] += 1
            jobs.append({
                "src": src,
                "name": "%s-%02d.jpg" % (slug, i),
                "title": "%s %02d" % (shoot["title"], i),
                "game": shoot["game"],
                "tags": shoot["tags"],
                "location": shoot["location"],
            })
            sigs.append(s)                     # guard against dupes inside a run
    return jobs


def run(jobs):
    photos = json.load(open(DATA))
    os.makedirs(ORIGINALS, exist_ok=True)
    os.makedirs(os.path.join(IMAGES, "shop"), exist_ok=True)

    for n, j in enumerate(jobs, 1):
        im = Image.open(j["src"]).convert("RGB")
        scale = LONG_EDGE / max(im.size)
        if scale < 1:
            im = im.resize((round(im.width * scale), round(im.height * scale)),
                           Image.LANCZOS)

        clean = os.path.join(ORIGINALS, j["name"])
        im.save(clean, "JPEG", quality=95, optimize=True)

        layer = build_layer(im.size, j["name"])
        layer = layer.filter(ImageFilter.GaussianBlur(0.4))
        a = layer.getchannel("A").point(lambda v: int(v * ARCHIVE_OPACITY))
        layer.putalpha(a)
        marked = Image.alpha_composite(im.convert("RGBA"), layer).convert("RGB")

        published = os.path.join(IMAGES, j["name"])
        marked.save(published, "JPEG", quality=SITE_QUALITY,
                    optimize=True, progressive=True)

        rel = "images/" + j["name"]
        build_preview(rel, force=True)          # sources the clean master

        photos.append({
            "src": rel,
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
        if n % 10 == 0:
            print("  %d/%d..." % (n, len(jobs)))

    json.dump(photos, open(DATA, "w"), indent=2, ensure_ascii=False)
    open(DATA, "a").write("\n")
    subprocess.run([sys.executable, "studio.py", "--regen"], cwd=ROOT, check=True)
    print("imported %d photographs" % len(jobs))


def main():
    if "--list" in sys.argv:
        for s in SHOOTS:
            fs = files_in(s["folder"])
            if s.get("only"):
                fs = [fs[i - 1] for i in s["only"] if i <= len(fs)]
            print("%-34s %3d files -> %s" % (s["folder"], len(fs), s["game"]))
        return

    jobs = plan()
    by_game = {}
    for j in jobs:
        by_game[j["game"]] = by_game.get(j["game"], 0) + 1
    print("to import: %d photographs" % len(jobs))
    for g, n in sorted(by_game.items()):
        print("  %-38s %3d" % (g, n))

    if "--run" in sys.argv:
        if jobs:
            run(jobs)
    else:
        print("\n(dry run — pass --run to actually import)")


if __name__ == "__main__":
    main()
