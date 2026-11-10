#!/usr/bin/env python3
"""Build the DCDS vs Loyola "color trail" graphic (1080x1350).

Layout: light grain background, the Country Day ball carrier in full
color with navy and gold stripes trailing off the right edge, the Loyola
tackler turned into a pale gray ghost, and the DC logo small at the
bottom.

Inputs (all in social/):
  cutouts/dcds-tackle-runner.png   #2, cut out of the photo (RGBA)
  cutouts/dcds-tackle-tackler.png  Loyola #5, same canvas as the runner
  logos/country-day.png, fonts/oswald.woff2

The two cutouts share one canvas, so they stay lined up; its right edge
is the photo's right edge (the tackler's foot is cut there), which is
why the cutouts sit flush against the post's right edge.

Run:  python3 social/build_dcds_tackle.py
Out:  social/dcds-tackle.html, social/dcds-tackle.png (1080x1350)
      and social/dcds-tackle@2x.png (2160x2700, git-ignored)
"""
import base64, io, os, shutil, subprocess, tempfile
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = "dcds-tackle"
W, H = 1080, 1350

# Navy from the DC logo; the gold sits between the logo's khaki and
# the helmet so it holds up on the light background.
NAVY = "#14264a"
GOLD = "#bda466"
BG = "#dcdde2"

# Where the cutout canvas lands on the post (CSS px). Its right edge
# is flush with the post's right edge.
SCALE = 0.54
TOP = 292

# Stripes, in cutout-canvas pixels (y0, y1) and where each starts (x),
# so they stay pinned to the runner if SCALE/TOP change.
STRIPES = [  # colour, y0, y1, x start
    (GOLD, 222, 398, 500),
    (NAVY, 432, 604, 470),
]


def rel(p):
    return os.path.join(HERE, p)


def b64(data, mime):
    return "data:%s;base64,%s" % (mime, base64.b64encode(data).decode())


def png_uri(im):
    buf = io.BytesIO(); im.save(buf, "PNG", optimize=True)
    return b64(buf.getvalue(), "image/png")


def font_uri(p):
    with open(rel(p), "rb") as f:
        return b64(f.read(), "font/woff2")


def runner_layer():
    """Take the warm cast off the photo so the white pants read white
    against the cool background; the helmet stays gold."""
    a = np.asarray(Image.open(rel("cutouts/dcds-tackle-runner.png")).convert("RGBA")).astype(float)
    rgb = a[..., :3] * np.array([1.06, 1.15, 1.24])
    rgb = 255 * (np.clip(rgb, 0, 255) / 255) ** 0.94          # small lift
    a[..., :3] = np.clip(rgb, 0, 255)
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def tackler_layer():
    """Solid white, like a mannequin: one flat colour, so no numbers,
    lettering or gray shading show. Only the outline is kept."""
    a = np.asarray(Image.open(rel("cutouts/dcds-tackle-tackler.png")).convert("RGBA")).copy()
    a[..., 0], a[..., 1], a[..., 2] = 252, 252, 253
    return Image.fromarray(a, "RGBA")


def grain_tile(n=320, seed=7):
    rng = np.random.default_rng(seed)
    v = np.clip(128 + rng.normal(0, 38, (n, n)), 0, 255).astype(np.uint8)
    return Image.fromarray(v, "L").convert("RGB")


def logo_uri():
    im = Image.open(rel("logos/country-day.png")).convert("RGBA")
    im.thumbnail((240, 240), Image.LANCZOS)
    return png_uri(im)


def build_html():
    runner, tackler = runner_layer(), tackler_layer()
    cw, ch = runner.size
    lw, lh = cw * SCALE, ch * SCALE
    left = W - lw

    stripes = []
    for colour, y0, y1, x0 in STRIPES:
        x = left + x0 * SCALE
        stripes.append(
            '<div class="stripe" style="left:%.1fpx;top:%.1fpx;width:%.1fpx;'
            'height:%.1fpx;background:%s"></div>'
            % (x, TOP + y0 * SCALE, W - x + 4, (y1 - y0) * SCALE, colour))

    css = """
@font-face{font-family:"Oswald";src:url(%(osw)s) format("woff2");font-weight:200 700}
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:%(bg)s}
.post{position:relative;width:%(W)dpx;height:%(H)dpx;overflow:hidden;background:%(bg)s}
/* very soft light falloff so the flat gray has some air */
.post::before{content:"";position:absolute;inset:0;
  background:radial-gradient(ellipse 70%% 55%% at 50%% 46%%,rgba(255,255,255,.35),rgba(255,255,255,0) 70%%),
             linear-gradient(180deg,rgba(0,0,0,0) 60%%,rgba(30,34,48,.06) 100%%)}

.top{position:absolute;left:0;right:0;top:34px;text-align:center;
  font-family:"Oswald",sans-serif;font-weight:500;font-size:30px;letter-spacing:.38em;
  text-transform:uppercase;color:#fff;opacity:.72;padding-left:.38em}

/* stripes start soft behind the runner, then run off the edge */
.stripe{position:absolute;
  -webkit-mask-image:linear-gradient(90deg,transparent 0,#000 80px);
          mask-image:linear-gradient(90deg,transparent 0,#000 80px);
  filter:blur(.6px)}
.stripe::after{content:"";position:absolute;inset:0;
  background:linear-gradient(180deg,rgba(255,255,255,.10),rgba(255,255,255,0) 45%%,rgba(0,0,0,.10))}

.layer{position:absolute;left:%(left).1fpx;top:%(top)dpx;width:%(lw).1fpx;height:%(lh).1fpx}
.tackler{filter:drop-shadow(0 6px 16px rgba(40,44,60,.16))}
.runner{filter:drop-shadow(0 10px 22px rgba(10,16,32,.28))}

.logo{position:absolute;left:50%%;bottom:92px;width:62px;transform:translateX(-50%%)}

.grain{position:absolute;inset:0;background:url(%(grain)s) repeat;background-size:160px 160px;
  mix-blend-mode:overlay;opacity:.22;pointer-events:none}
""" % dict(osw=font_uri("fonts/oswald.woff2"), bg=BG, W=W, H=H,
           left=left, top=TOP, lw=lw, lh=lh, grain=png_uri(grain_tile()))

    return """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>DCDS vs Loyola</title><style>%s</style></head><body>
<div class="post">
  <div class="top">Yellowjackets</div>
  %s
  <img class="layer tackler" src="%s" alt="">
  <img class="layer runner" src="%s" alt="Country Day #2 breaking a tackle against Loyola">
  <img class="logo" src="%s" alt="Detroit Country Day">
  <div class="grain"></div>
</div></body></html>
""" % (css, "\n  ".join(stripes), png_uri(tackler), png_uri(runner), logo_uri())


def find_chrome():
    for p in (os.environ.get("CHROME"),
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              shutil.which("google-chrome"), shutil.which("chromium"),
              "/opt/pw-browsers/chromium"):
        if p and os.path.exists(p):
            return p
    raise SystemExit("No Chrome found; set CHROME=/path/to/chrome")


PLAYWRIGHT_JS = """
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: %d, height: %d }, deviceScaleFactor: 2 });
  await p.goto('file://' + process.argv[1]);
  await p.evaluate(() => document.fonts.ready);
  await p.locator('.post').screenshot({ path: process.argv[2] });
  await b.close();
})();
"""


def screenshot(html_path, png_path):
    """Playwright when it's installed (cloud sessions), else Chrome's own
    headless screenshot (fine on the Mac)."""
    node = shutil.which("node")
    if node and subprocess.run([node, "-e", "require('playwright')"],
                               capture_output=True).returncode == 0:
        subprocess.run([node, "-e", PLAYWRIGHT_JS % (W, H), html_path, png_path],
                       check=True)
        return
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([find_chrome(), "--headless=new", "--disable-gpu",
                        "--hide-scrollbars", "--user-data-dir=" + prof,
                        "--force-device-scale-factor=2", "--window-size=%d,%d" % (W, H),
                        "--screenshot=" + png_path, "file://" + html_path],
                       check=True, capture_output=True)


def main():
    html_path = rel(OUT + ".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_html())

    big = rel(OUT + "@2x.png")
    screenshot(html_path, big)
    im = Image.open(big).convert("RGB")
    im.resize((W, H), Image.LANCZOS).save(rel(OUT + ".png"), optimize=True)
    print(html_path, "->", rel(OUT + ".png"), (W, H), "+ @2x", im.size)


if __name__ == "__main__":
    main()
