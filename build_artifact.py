#!/usr/bin/env python3
"""
Build dist/artifact.html — a single self-contained file of the whole
site (Home and Portfolio, images inlined as data URIs) for sharing as a
Claude Artifact or sending to anyone as one file.

Run: python3 build_artifact.py
Requires macOS `sips` for image downscaling.
"""

import base64
import json
import os
import re
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "dist", "artifact.html")
MAX_EDGE = "1400"
JPEG_QUALITY = "55"


def read(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as f:
        return f.read()


def image_data_uri(src):
    """Downscale + recompress via sips, return data URI."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        subprocess.run(
            ["sips", "-Z", MAX_EDGE, "-s", "format", "jpeg",
             "-s", "formatOptions", JPEG_QUALITY,
             os.path.join(ROOT, src), "--out", tmp_path],
            check=True, capture_output=True)
        with open(tmp_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return "data:image/jpeg;base64," + b64
    finally:
        os.unlink(tmp_path)


def build():
    photos = json.loads(read("data/photos.json"))
    for p in photos:
        p["src"] = image_data_uri(p["src"])

    css = read("css/style.css")
    main_js = read("js/main.js")
    # reviews and the mailer, which the home page reads
    support_js = "\n".join(read(p) for p in (
        "js/reviews-store.js", "js/mailer.js", "js/reviews.js"))

    # The home page's words live in index.html, not in the script, so take
    # its <main> as-is. Links to the portfolio become in-page view switches.
    home_main = re.search(r'<main id="about-root">.*?</main>',
                          read("index.html"), re.S).group(0)
    home_main = re.sub(r'href="portfolio\.html[^"]*"',
                       'href="#" data-goto="portfolio"', home_main)

    # Inline the webfont as a data URI — the artifact CSP blocks external
    # files, so the ../fonts path would fall back to Helvetica otherwise.
    with open(os.path.join(ROOT, "fonts", "archivo-var.woff2"), "rb") as fh:
        font_b64 = base64.b64encode(fh.read()).decode("ascii")
    css = css.replace(
        'url("../fonts/archivo-var.woff2") format("woff2")',
        'url(data:font/woff2;base64,%s) format("woff2")' % font_b64)

    html = """<meta charset="utf-8">
<title>Garrett Erickson — Michigan Sports Photographer</title>
<style>
{css}
[data-view][hidden] {{ display: none; }}
</style>

<nav class="nav">
  <a class="nav__name" href="#" data-goto="home">Garrett Erickson</a>
  <div class="nav__links">
    <a href="#" data-goto="home">Home</a>
    <a href="#" data-goto="portfolio">Portfolio</a>
  </div>
</nav>

<div data-view="home">
  {home_main}
</div>

<div data-view="portfolio" hidden>
  <header class="archive-head">
    <h1>Portfolio</h1>
    <span class="mono" id="portfolio-count"></span>
  </header>
  <div class="filters" id="filters" role="toolbar" aria-label="Filter photographs"></div>
  <main class="archive-grid" id="portfolio-grid"></main>
</div>

<footer class="footer">
  <span class="mono">© 2026 Garrett Erickson · Michigan Sports Photographer</span>
  <a class="mono" href="mailto:garrettoscarerickson@gmail.com">garrettoscarerickson@gmail.com</a>
  <span class="mono">Based in Metro Detroit, Michigan</span>
</footer>

<script>
window.PHOTOS = {photos_json};
document.body.dataset.page = "spa";
</script>
<script>
{support_js}
</script>
<script>
{main_js}
</script>
""".format(css=css,
           home_main=home_main,
           photos_json=json.dumps(photos),
           support_js=support_js,
           main_js=main_js)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("Built %s (%.1f MB)" % (OUT, os.path.getsize(OUT) / 1e6))


if __name__ == "__main__":
    build()
