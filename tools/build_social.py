#!/usr/bin/env python3
"""Build the Instagram rates post.

Prices come from data/shop.json, never from anything typed in here — a
post that quietly disagrees with the website is worse than no post, and
that is exactly what happens when the numbers live in two places.

Sized 1080x1350: Instagram's 4:5 feed post. Square works, but 4:5 is the
tallest a feed post is allowed to be, so it occupies more of the screen
for the same scroll — and the photographs are mostly portrait anyway.

    python3 tools/build_social.py --variant a --photo bartoshuk-01
    python3 tools/build_social.py --all
"""

import argparse
import base64
import json
import os
import subprocess
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOCIAL = os.path.join(ROOT, "social")
ORIGINALS = os.path.join(ROOT, "images", "_originals")

W, H = 1080, 1350
SCALE = 2               # render big, downsample: gives clean type edges
CHROME = ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def b64(path, mime):
    return "data:%s;base64,%s" % (
        mime, base64.b64encode(open(path, "rb").read()).decode())


def photo_uri(name):
    """The clean master, not the published copy — the published one carries
    a watermark, and watermarking his own advertisement would be absurd."""
    p = os.path.join(ORIGINALS, name + ".jpg")
    if not os.path.exists(p):
        sys.exit("no such photograph: " + p)
    return b64(p, "image/jpeg")


def shop():
    return json.load(open(os.path.join(ROOT, "data", "shop.json")))


def rows_html(cfg):
    out = []
    for t in cfg["tiers"]:
        out.append("""
      <div class="row">
        <div><div class="row__name">%s</div><div class="row__lead">%s</div></div>
        <div class="row__r"><div class="row__price">%s</div>
          <div class="row__unit">%s</div></div>
      </div>""" % (t["name"].upper(), t.get("lead", ""), t["price"], t["unit"]))
    return "".join(out)


BASE_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0b0b0e}
.post{position:relative;width:%(W)dpx;height:%(H)dpx;background:#0b0b0e;color:#f2f2f0;
      overflow:hidden;font-family:"Archivo",Helvetica,Arial,sans-serif}
.kicker{font-size:17px;font-weight:600;letter-spacing:.34em;text-transform:uppercase;color:#c8c8d0}
.title{font-family:"Oswald",sans-serif;font-weight:500;line-height:.88;
       letter-spacing:-.01em;text-transform:uppercase}
.row{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;
     padding:22px 0;border-top:1px solid rgba(255,255,255,.15)}
.row:last-child{border-bottom:1px solid rgba(255,255,255,.15)}
.row__name{font-family:"Oswald",sans-serif;font-weight:500;font-size:40px;
           letter-spacing:.05em;line-height:1}
.row__lead{margin-top:8px;font-size:18px;color:#a8a8b2}
.row__r{text-align:right;flex:none}
.row__price{font-family:"Oswald",sans-serif;font-weight:500;font-size:48px;line-height:1}
.row__unit{margin-top:6px;font-size:16px;color:#a8a8b2}
.foot{display:flex;justify-content:space-between;align-items:baseline;
      font-size:20px;letter-spacing:.1em;text-transform:uppercase}
.foot b{font-weight:700}.foot span{color:#a8a8b2}
.store{display:flex;align-items:center;gap:18px;padding:22px 26px;border-radius:16px;
       background:#f2f2f0;color:#0b0b0e}
.store__big{font-family:"Oswald",sans-serif;font-weight:500;font-size:52px;line-height:1;flex:none}
.store__t{font-size:20px;font-weight:700;line-height:1.3}
.store__s{margin-top:4px;font-size:17px;color:#55555c}
""" % {"W": W, "H": H}

# Full bleed. The veil is directional rather than flat: the picture stays
# open at the top where the action is and goes solid under the type. A
# uniform scrim would read as a grey filter over a good photograph.
CSS_A = """
.bg{position:absolute;inset:0;background:url(%(photo)s) center 26%%/cover no-repeat}
/* Held open through the middle band, because that is where the subject
   is. The earlier curve started closing at 22%% and put the keeper's face
   under the darkest part of the wash — the picture was there and unreadable. */
.veil{position:absolute;inset:0;background:
  linear-gradient(180deg,rgba(8,8,10,.44) 0%%,rgba(8,8,10,.12) 18%%,
                  rgba(8,8,10,.20) 40%%,rgba(8,8,10,.74) 55%%,
                  rgba(8,8,10,.96) 68%%,rgba(8,8,10,.99) 100%%)}
.wrap{position:absolute;inset:0;padding:72px 68px;display:flex;flex-direction:column}
.title{font-size:124px;margin-top:16px}
.rows{margin-top:auto}
.store{margin-top:28px}
.foot{margin-top:28px;padding-top:24px;border-top:1px solid rgba(255,255,255,.15)}
"""

# Photograph as a band, type on solid black. Less dramatic than A, but
# every price sits at full contrast, and it survives any photograph
# dropped into it rather than only a dark one.
CSS_B = """
.hero{position:relative;height:%(hero)dpx;background:url(%(photo)s) center 34%%/cover no-repeat}
.hero:after{content:"";position:absolute;inset:0;background:
  linear-gradient(180deg,rgba(8,8,10,.42) 0%%,rgba(8,8,10,0) 34%%,
                  rgba(8,8,10,.55) 82%%,#0b0b0e 100%%)}
.hero__t{position:absolute;left:64px;right:64px;top:56px;z-index:2}
.title{font-size:104px;margin-top:14px}
.wrap{padding:34px 64px 64px;display:flex;flex-direction:column;height:%(rest)dpx}
.rows{margin-top:4px}
.store{margin-top:auto}
.foot{margin-top:26px;padding-top:24px;border-top:1px solid rgba(255,255,255,.15)}
"""

HERO = 600


def build(variant, photo, out):
    cfg = shop()
    fonts = "".join(
        '@font-face{font-family:"%s";src:url(%s) format("woff2");font-weight:%s}\n'
        % (fam, b64(os.path.join(SOCIAL, "fonts", f), "font/woff2"), wt)
        for fam, f, wt in [("Oswald", "oswald.woff2", "200 500"),
                           ("Archivo", "archivo.woff2", "400 700")])

    uri = photo_uri(photo)
    head = "Garrett Erickson · Sports Photography"
    store = ("""<div class="store"><div class="store__big">$%s</div><div>
      <div class="store__t">Single photos from any game</div>
      <div class="store__s">Browse by game, find your number, download in minutes.</div>
    </div></div>""" % cfg["photoPrice"])
    foot = '<div class="foot"><b>garrettphoto.store</b><span>@shot_by_ge</span></div>'

    if variant == "a":
        css = BASE_CSS + CSS_A % {"photo": uri}
        body = """
<div class="post"><div class="bg"></div><div class="veil"></div>
  <div class="wrap">
    <div class="kicker">%s</div>
    <div class="title">Rates</div>
    <div class="rows">%s</div>
    %s
    %s
  </div>
</div>""" % (head, rows_html(cfg), store, foot)
    else:
        css = BASE_CSS + CSS_B % {"photo": uri, "hero": HERO, "rest": H - HERO}
        body = """
<div class="post">
  <div class="hero"><div class="hero__t">
    <div class="kicker">%s</div>
    <div class="title">Rates</div>
  </div></div>
  <div class="wrap">
    <div class="rows">%s</div>
    %s
    %s
  </div>
</div>""" % (head, rows_html(cfg), store, foot)

    html = ('<!DOCTYPE html><html><head><meta charset="UTF-8"><style>\n'
            + fonts + css + "</style></head><body>" + body + "</body></html>")

    hp = os.path.join(SOCIAL, "rates-%s.html" % variant)
    open(hp, "w").write(html)

    subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=%d" % SCALE,
                    "--window-size=%d,%d" % (W, H),
                    "--screenshot=" + out, "--default-background-color=0b0b0eff",
                    "file://" + hp],
                   check=True, capture_output=True)

    im = Image.open(out).convert("RGB")
    if im.size != (W, H):
        im = im.resize((W, H), Image.LANCZOS)
    im.save(out, "PNG", optimize=True)
    print("%s  %s  %s  %.0f KB"
          % (variant.upper(), photo, "x".join(map(str, im.size)),
             os.path.getsize(out) / 1024))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["a", "b"], default="a")
    ap.add_argument("--photo", default="bartoshuk-01")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()

    if a.all:
        build("a", "bartoshuk-01", os.path.join(SOCIAL, "rates-a.png"))
        build("b", "casstech-05", os.path.join(SOCIAL, "rates-b.png"))
    else:
        build(a.variant, a.photo, os.path.join(SOCIAL, "rates-%s.png" % a.variant))


if __name__ == "__main__":
    main()
