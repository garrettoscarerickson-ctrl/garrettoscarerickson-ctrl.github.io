#!/usr/bin/env python3
"""Watermark the archive copies of anything that is for sale.

The store served a burned-in, watermarked preview — but the same
photograph also sat in the archive as a clean 1600x2400 JPEG at a
guessable URL, larger AND cleaner than the paid version. Every
protection on the store was one URL away from being pointless.

Pointing the page at a different file would not have fixed it: the clean
file is published, so it is fetchable whether or not any page links to
it. The file itself has to change.

So for every photograph with a `game` — that is, everything for sale —
the clean copy moves to images/_originals/ (gitignored, stays on this
machine) and the published images/ copy is rewritten with the mark
burned in. Portfolio work that is not for sale is left completely alone.

Lighter than the store's mark: this is the portfolio, and it is a
deterrent rather than a paywall. Still blended rather than stamped, so
the pixels underneath are genuinely gone.

    python3 tools/protect_archive.py [--force]
"""

import hashlib
import json
import os
import sys

from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_shop_previews import build_layer          # same mark, same jitter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGINALS = os.path.join(ROOT, "images", "_originals")

OPACITY = 0.20      # store uses 0.30; this is the shop window, not the till
QUALITY = 86


def protect(rel, force=False):
    name = os.path.basename(rel)
    published = os.path.join(ROOT, rel)
    clean = os.path.join(ORIGINALS, name)

    if not os.path.exists(published) and not os.path.exists(clean):
        return "missing"

    # The clean copy is the source of truth once it exists. Re-running
    # must never watermark an already-watermarked file.
    if os.path.exists(clean) and not force:
        return "already protected"

    os.makedirs(ORIGINALS, exist_ok=True)
    if not os.path.exists(clean):
        Image.open(published).convert("RGB").save(
            clean, "JPEG", quality=95, optimize=True)

    im = Image.open(clean).convert("RGB")
    layer = build_layer(im.size, hashlib.md5(("arch" + name).encode()).hexdigest())
    layer = layer.filter(ImageFilter.GaussianBlur(0.4))
    a = layer.getchannel("A").point(lambda v: int(v * OPACITY))
    layer.putalpha(a)

    out = Image.alpha_composite(im.convert("RGBA"), layer).convert("RGB")
    out.save(published, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    return "protected"


def main():
    force = "--force" in sys.argv
    photos = json.load(open(os.path.join(ROOT, "data", "photos.json")))
    for_sale = [p for p in photos if p.get("game")]

    counts = {}
    for i, p in enumerate(for_sale, 1):
        r = protect(p["src"], force)
        counts[r] = counts.get(r, 0) + 1
        if i % 20 == 0:
            print("  %d/%d..." % (i, len(for_sale)))

    print("for sale: %d" % len(for_sale))
    for k, v in sorted(counts.items()):
        print("  %-18s %d" % (k, v))
    print("clean copies kept in images/_originals/ (gitignored)")


if __name__ == "__main__":
    main()
