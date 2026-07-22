#!/usr/bin/env python3
"""
Stamp "© GARRETT ERICKSON" into the bottom-right corner of every image
in the manifest. Originals are backed up to images/_originals/ first
(kept out of git), and already-stamped images are skipped on re-runs.

Run: python3 watermark.py
New uploads via Studio are watermarked automatically in the browser —
this script exists for the back catalog or externally added files.
"""

import json
import os
import shutil

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
ORIGINALS = os.path.join(ROOT, "images", "_originals")
CREDIT = "© GARRETT ERICKSON"

FONT_CANDIDATES = [
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
]


def load_font(px):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, px)
        except OSError:
            continue
    return ImageFont.load_default()


def stamp(path):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    size = max(13, int(w * 0.016))
    pad = int(w * 0.018)
    font = load_font(size)

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    bbox = draw.textbbox((0, 0), CREDIT, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = w - tw - pad, h - th - pad - bbox[1]
    # soft shadow for legibility on bright skies
    draw.text((x + 1, y + 1), CREDIT, font=font, fill=(0, 0, 0, 110))
    draw.text((x, y), CREDIT, font=font, fill=(255, 255, 255, 150))

    out = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    out.save(path, "JPEG", quality=88)


def main():
    os.makedirs(ORIGINALS, exist_ok=True)
    with open(os.path.join(ROOT, "data", "photos.json")) as f:
        photos = json.load(f)
    for p in photos:
        src = os.path.join(ROOT, p["src"])
        name = os.path.basename(src)
        backup = os.path.join(ORIGINALS, name)
        if os.path.exists(backup):
            print("skip (already stamped):", name)
            continue
        shutil.copy2(src, backup)
        stamp(src)
        print("stamped:", name)


if __name__ == "__main__":
    main()
