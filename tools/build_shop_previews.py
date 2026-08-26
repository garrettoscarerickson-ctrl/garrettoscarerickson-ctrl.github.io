#!/usr/bin/env python3
"""
Build the store's preview images.

The portfolio's watermark is a CSS overlay — nothing is burned into those
files, exactly as asked. The STORE is different: a preview is being shown
to someone who has not paid yet, so the mark has to survive devtools, a
direct request for the .jpg, and an AI inpainting pass.

What makes a watermark hard for an AI to remove:

  1. It covers the WHOLE frame, not a corner. Inpainting a corner is easy;
     reconstructing every square inch of a photo is not — the model has
     nothing clean to copy from.
  2. Every tile is jittered — position, angle, size, opacity — and the
     jitter is seeded per file. A clean repeating lattice can be solved
     for and subtracted (that is the classic stock-photo attack: average
     lots of images sharing one watermark and the pattern falls out).
     No two of these images share a pattern.
  3. It is drawn light AND dark. A single-tone mark can be pulled out by
     thresholding one direction; this one moves pixels both ways.
  4. It is blended semi-transparently, which destroys the original pixel
     values underneath. Removal cannot recover them — only hallucinate.
  5. The preview is downscaled and saved at moderate JPEG quality, so the
     mark and the photo share compression artifacts and cannot be cleanly
     separated — and a perfect removal still only yields a small file.

Honest limit: nothing is 100% removal-proof. This moves it from "right
click, save" to "more work than paying $1."

    python3 tools/build_shop_previews.py [--force]
"""

import hashlib
import json
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "images", "shop")
MARK = "GARRETT ERICKSON"

LONG_EDGE = 1100     # small enough that a stolen copy has no print value
QUALITY = 72         # artifacts fuse the mark into the photo
SS = 2               # supersample factor for clean rotated type

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
]


def load_font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def text_img(text, size, rng):
    """One watermark tile, rotated, as its own transparent image."""
    font = load_font(size)
    pad = size * 2
    probe = Image.new("L", (10, 10))
    box = ImageDraw.Draw(probe).textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0], box[3] - box[1]

    tile = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    x, y = pad - box[0], pad - box[1]

    # dark component first, offset — the mark moves pixels in BOTH
    # directions so it can't be thresholded out of one channel
    d.text((x + max(1, size // 14), y + max(1, size // 14)), text,
           font=font, fill=(0, 0, 0, 96))
    d.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    angle = rng.uniform(-34, -26)
    return tile.rotate(angle, resample=Image.BICUBIC, expand=True)


def build_layer(size, seed):
    """Full-frame jittered watermark layer at supersampled resolution."""
    W, H = size[0] * SS, size[1] * SS
    rng = random.Random(seed)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    base = int(min(W, H) * 0.052)          # tile type size
    step_x = int(base * 12.5)
    step_y = int(base * 5.2)

    row = 0
    y = -step_y
    while y < H + step_y:
        # every other row offset — breaks the grid into a brick pattern
        offset = (step_x // 2) if row % 2 else 0
        x = -step_x + offset - rng.randint(0, step_x // 3)
        while x < W + step_x:
            size_jit = int(base * rng.uniform(0.86, 1.14))
            tile = text_img(MARK, size_jit, rng)
            # per-tile opacity so the field is uneven and can't be modelled
            alpha = rng.uniform(0.72, 1.0)
            if alpha < 1.0:
                a = tile.getchannel("A").point(lambda v: int(v * alpha))
                tile.putalpha(a)
            layer.alpha_composite(
                tile,
                (x + rng.randint(-base, base), y + rng.randint(-base // 2, base // 2)),
            )
            x += step_x + rng.randint(-base * 2, base * 2)
        y += step_y
        row += 1

    # one large mark straight across the subject
    big = text_img(MARK, int(min(W, H) * 0.135), rng)
    big = big.resize((int(W * 0.94), int(big.height * (W * 0.94) / big.width)),
                     Image.LANCZOS)
    a = big.getchannel("A").point(lambda v: int(v * 0.62))
    big.putalpha(a)
    layer.alpha_composite(big, ((W - big.width) // 2, (H - big.height) // 2))

    return layer.resize(size, Image.LANCZOS)


def process(src_rel, force=False):
    src = os.path.join(ROOT, src_rel)
    name = os.path.basename(src_rel)
    dst = os.path.join(OUT_DIR, name)
    if os.path.exists(dst) and not force:
        return dst, False

    im = Image.open(src).convert("RGB")
    scale = LONG_EDGE / max(im.size)
    if scale < 1:
        im = im.resize((round(im.width * scale), round(im.height * scale)),
                       Image.LANCZOS)

    seed = hashlib.md5(name.encode()).hexdigest()
    layer = build_layer(im.size, seed)

    # soften a hair so the mark shares the photo's focus characteristics
    # instead of sitting on top as a crisp, easily-segmented graphic
    layer = layer.filter(ImageFilter.GaussianBlur(0.4))

    # blend at partial strength — readable through, but the original
    # pixel values underneath are gone for good
    a = layer.getchannel("A").point(lambda v: int(v * 0.30))
    layer.putalpha(a)

    out = Image.alpha_composite(im.convert("RGBA"), layer).convert("RGB")
    os.makedirs(OUT_DIR, exist_ok=True)
    out.save(dst, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    return dst, True


def main():
    force = "--force" in sys.argv
    photos = json.load(open(os.path.join(ROOT, "data", "photos.json")))
    shop = [p for p in photos if p.get("game")]

    made = skipped = 0
    for i, p in enumerate(shop, 1):
        _, did = process(p["src"], force)
        made += did
        skipped += not did
        if did and made % 10 == 0:
            print("  %d/%d..." % (i, len(shop)))

    total = sum(
        os.path.getsize(os.path.join(OUT_DIR, f))
        for f in os.listdir(OUT_DIR) if f.endswith(".jpg")
    )
    print("built %d, reused %d — %.1f MB in images/shop/"
          % (made, skipped, total / 1e6))


if __name__ == "__main__":
    main()
