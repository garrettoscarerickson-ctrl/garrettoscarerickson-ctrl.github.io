#!/usr/bin/env python3
"""The burned-in "GARRETT ERICKSON" watermark used on game photographs.

tools/import_shoot.py lays this over every photograph it brings in, at
low opacity, so a published copy carries the mark in its pixels rather
than only as a CSS overlay a browser can switch off.

Why it looks the way it does:

  1. It covers the WHOLE frame, not a corner. Inpainting a corner is easy;
     reconstructing every square inch of a photo is not.
  2. Every tile is jittered — position, angle, size, opacity — and the
     jitter is seeded per file, so no two images share a pattern that
     could be averaged out.
  3. It is drawn light AND dark, so it can't be thresholded out of one
     direction.
"""

import os
import random

from PIL import Image, ImageDraw, ImageFont

MARK = "GARRETT ERICKSON"
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
