#!/usr/bin/env python3
"""Build print/folder-sheets.html — three letter sheets for a pocket folder.

  1. Book again, save more   (the returning-client discount)
  2. How to get your photos  (ordering from the store)
  3. Rates and booking       (prices, add-ons, contact)

Printed white-on-paper rather than in the site's black. Two reasons, both
learned the hard way on the business cards: type on a heavy black ground
came out hard to read on a home printer, and a full-bleed black letter
sheet drains a cartridge. Heavy black type on white keeps the
architectural look, reads cleanly, and costs almost no ink.

    python3 print/build_folder.py
    then render the PDF with the command at the bottom of this file.
"""
import base64
import io
import os

import segno

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SITE = "garrettphoto.store"
STORE_URL = "https://garrettphoto.store/store.html"
CARD_URL = "https://garrettphoto.store/card"
PHONE = "248-225-4437"
EMAIL = "Garrettoscarerickson@gmail.com"
INSTA = "@shot_by_ge"


def font_uri(rel):
    with open(os.path.join(ROOT, rel), "rb") as f:
        return "data:font/woff2;base64," + base64.b64encode(f.read()).decode("ascii")


def qr_svg(data, scale=10):
    """QR as inline SVG. A viewBox is essential — without one the fixed
    width/height keep the drawing at natural size and CSS sizing just
    clips it, which is exactly how the first business-card QR failed to
    scan. White ground and a 4-module quiet zone are also required."""
    qr = segno.make(data, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=scale, border=4,
            dark="#000000", light="#ffffff", xmldecl=False, svgns=True,
            svgclass=None, lineclass=None)
    svg = buf.getvalue().decode("utf-8")
    side = qr.symbol_size(scale=scale, border=4)[0]
    return svg.replace(
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"' % (side, side),
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d"' % (side, side))


CSS = """
@font-face { font-family:"Oswald"; src:url(__OSW__) format("woff2");
             font-weight:200 500; font-style:normal; }
@font-face { font-family:"Archivo"; src:url(__ARC__) format("woff2");
             font-weight:400 700; font-style:normal; }

@page { size:8.5in 11in; margin:0; }

* { margin:0; padding:0; box-sizing:border-box; }

body {
  font-family:"Archivo", Arial, sans-serif;
  color:#111114;
  background:#fff;
  -webkit-print-color-adjust:exact;
  print-color-adjust:exact;
}

.sheet {
  width:8.5in; height:11in;
  padding:0.72in 0.78in 0.6in;
  display:flex; flex-direction:column;
  page-break-after:always;
  position:relative;
}
.sheet:last-child { page-break-after:auto; }

/* ---- masthead ---- */
.mast { display:flex; justify-content:space-between; align-items:baseline;
        border-bottom:1.5pt solid #111114; padding-bottom:7pt; }
.mast__name { font-family:"Oswald",sans-serif; font-weight:400;
              font-size:15pt; letter-spacing:.26em; text-transform:uppercase; }
.mast__kind { font-size:8.5pt; font-weight:600; letter-spacing:.17em;
              text-transform:uppercase; color:#55555c; }

/* ---- headline ---- */
.head { margin-top:0.42in; }
.head h1 { font-family:"Oswald",sans-serif; font-weight:500;
           font-size:47pt; line-height:.95; letter-spacing:-.005em;
           text-transform:uppercase; }
.head p { margin-top:11pt; font-size:12.5pt; line-height:1.5;
          max-width:5.9in; color:#33333a; }

/* ---- discount tiers ---- */
.tiers { margin-top:0.42in; display:flex; flex-direction:column; gap:11pt; }
.tier { display:flex; align-items:center; gap:16pt;
        border:1.2pt solid #111114; border-radius:9pt; padding:16pt 18pt; }
.tier--best { background:#111114; color:#fff; }
.tier__pct { font-family:"Oswald",sans-serif; font-weight:500; font-size:36pt;
             line-height:1; min-width:1.45in; }
.tier__body b { display:block; font-size:12.5pt; letter-spacing:.01em; }
.tier__body span { display:block; margin-top:3pt; font-size:10.5pt;
                   line-height:1.45; color:#55555c; }
.tier--best .tier__body span { color:#c9c9d2; }

/* ---- numbered steps ---- */
.steps { margin-top:0.34in; display:flex; flex-direction:column; gap:13pt; }
.step { display:flex; gap:14pt; align-items:flex-start; }
.step__n { flex:none; width:26pt; height:26pt; border-radius:50%;
           background:#111114; color:#fff; display:flex;
           align-items:center; justify-content:center;
           font-size:11.5pt; font-weight:700; }
.step__t b { display:block; font-size:13pt; }
.step__t span { display:block; margin-top:3pt; font-size:11pt; line-height:1.5;
                color:#3a3a42; max-width:4.5in; }

/* ---- rates ----
   Sheet 3 holds three cards, add-ons, a QR and four contact rows. It
   overflowed onto a fourth page at the sizes used on sheets 1 and 2, so
   this block runs tighter — still above the 10.5pt body minimum that
   made the business cards readable. */
.rates { margin-top:0.24in; display:flex; flex-direction:column; gap:6pt; }
.rate { border:1.2pt solid #111114; border-radius:9pt; padding:10pt 14pt; }
.rate--best { background:#111114; color:#fff; }
.rate__top { display:flex; justify-content:space-between; align-items:baseline;
             gap:12pt; }
.rate__name { font-family:"Oswald",sans-serif; font-weight:500; font-size:17pt;
              letter-spacing:.06em; text-transform:uppercase; }
.rate__price { font-family:"Oswald",sans-serif; font-weight:500; font-size:21pt; }
.rate__unit { font-size:9pt; color:#55555c; }
.rate--best .rate__unit { color:#c9c9d2; }
.rate__list { margin-top:6pt; font-size:10.5pt; line-height:1.42;
              column-count:2; column-gap:20pt; }
.rate__list span { display:block; }
.rate__list span::before { content:"— "; }

.addons { margin-top:9pt; border-top:1pt solid #c9c9d2; padding-top:8pt;
          font-size:10.5pt; line-height:1.55; }
.addons b { font-size:8.5pt; letter-spacing:.17em; text-transform:uppercase;
            color:#55555c; display:block; margin-bottom:5pt; }
.addons i { font-style:normal; float:right; }

/* ---- QR block ---- */
.qr-row { margin-top:auto; display:flex; align-items:center; gap:20pt;
          border-top:1.5pt solid #111114; padding-top:16pt; }
/* sheet 3 has no spare vertical room, so its QR block flows rather than
   being pushed to the bottom, and the code runs smaller */
.sheet--tight .head h1 { font-size:36pt; }
.sheet--tight .head { margin-top:0.26in; }

/* QR beside the contact grid, not above it */
.book { margin-top:auto; display:flex; gap:20pt; align-items:center;
        border-top:1.5pt solid #111114; padding-top:14pt; }
.book__side { flex:1; }
.book__t { display:block; font-family:"Oswald",sans-serif; font-weight:500;
           font-size:17pt; letter-spacing:.05em; text-transform:uppercase; }
.sheet--tight .qr { width:1.25in; height:1.25in; }
.sheet--tight .contact { margin-top:8pt; gap:7pt 20pt; }
.qr { width:1.5in; height:1.5in; flex:none; }
.qr svg { width:100%; height:100%; display:block; }
.qr-txt b { display:block; font-family:"Oswald",sans-serif; font-weight:500;
            font-size:19pt; letter-spacing:.03em; text-transform:uppercase; }
.qr-txt span { display:block; margin-top:5pt; font-size:11pt; line-height:1.5;
               color:#33333a; max-width:3.6in; }

/* ---- contact ---- */
.contact { margin-top:0.3in; display:grid; grid-template-columns:1fr 1fr;
           gap:10pt 22pt; }
.c { border-top:1pt solid #c9c9d2; padding-top:7pt; }
.c b { display:block; font-size:8.5pt; letter-spacing:.17em;
       text-transform:uppercase; color:#55555c; }
.c span { display:block; margin-top:3pt; font-size:11.5pt; font-weight:600; }

/* ---- foot ---- */
/* auto pushes the footer to the bottom of a short sheet. On the full
   sheets there is no free space, so this resolves to zero and the
   layout is unchanged. */
.foot { margin-top:auto; padding-top:0.26in; display:flex; justify-content:space-between;
        font-size:8.5pt; letter-spacing:.14em; text-transform:uppercase;
        color:#7a7a84; }

.note { margin-top:14pt; font-size:10pt; line-height:1.55; color:#55555c;
        border-left:2pt solid #111114; padding-left:11pt; max-width:5.6in; }
"""


def sheet(kind, body, page_no, cls=""):
    return """
<section class="sheet %s">
  <div class="mast">
    <span class="mast__name">Garrett Erickson</span>
    <span class="mast__kind">%s</span>
  </div>
  %s
  <div class="foot"><span>%s</span><span>%s</span></div>
</section>""" % (cls, kind, body, SITE, page_no)


# ---------------------------------------------------------------- sheet 1
SHEET1 = """
  <div class="head">
    <h1>Book again,<br>save more</h1>
    <p>Every time you come back, the rate drops. Nothing to sign up for and
       no code to remember — I keep track, and the discount is already
       applied when I quote you.</p>
  </div>

  <div class="tiers">
    <div class="tier">
      <span class="tier__pct">10%</span>
      <span class="tier__body"><b>Your second booking</b>
      <span>The first time you book me again, ten percent comes off.</span></span>
    </div>
    <div class="tier">
      <span class="tier__pct">20%</span>
      <span class="tier__body"><b>Your third booking</b>
      <span>Book a third time and it doubles.</span></span>
    </div>
    <div class="tier tier--best">
      <span class="tier__pct">30%</span>
      <span class="tier__body"><b>Your fourth booking</b>
      <span>Thirty percent off — the best rate I offer.</span></span>
    </div>
  </div>

  <div class="note">Discounts come off the session rates on the
    &ldquo;Rates &amp; booking&rdquo; sheet. Individual, team, and event
    bookings all count toward it.</div>
"""

# ---------------------------------------------------------------- sheet 2
SHEET2 = """
  <div class="head">
    <h1>How to get<br>your photos</h1>
    <p>Every photo I shoot goes up on my site the same week. Finding yours
       takes about a minute, and there is nothing to download or sign up for.</p>
  </div>

  <div class="steps">
    <div class="step"><span class="step__n">1</span><span class="step__t">
      <b>Open the store</b>
      <span>Scan the code below, or type __SITE__/store into any browser.</span>
    </span></div>
    <div class="step"><span class="step__n">2</span><span class="step__t">
      <b>Find your game and tap your photos</b>
      <span>Photos are grouped by game. Tap as many as you want — they cost
      $1 each and the total updates as you go.</span>
    </span></div>
    <div class="step"><span class="step__n">3</span><span class="step__t">
      <b>Send the order in one tap</b>
      <span>Type your name and email and press send. No account, no card
      details, and no email app opens.</span>
    </span></div>
    <div class="step"><span class="step__n">4</span><span class="step__t">
      <b>Keep your chat code</b>
      <span>You get a short code on screen. I message you there to sort out
      payment. Closed the window? Reopen it at __SITE__/chat.</span>
    </span></div>
    <div class="step"><span class="step__n">5</span><span class="step__t">
      <b>Get the clean files</b>
      <span>Photos on the site carry my watermark. Once you have paid I send
      the full-resolution originals with no watermark on them.</span>
    </span></div>
  </div>

  <div class="qr-row">
    <span class="qr">__QR_STORE__</span>
    <span class="qr-txt"><b>Scan to shop</b>
    <span>Opens the store straight on your phone. Photos stay up for the
    season, so there is no rush.</span></span>
  </div>
"""

# ---------------------------------------------------------------- sheet 3
SHEET3 = """
  <div class="head">
    <h1>Rates &amp; booking</h1>
  </div>

  <div class="rates">
    <div class="rate rate--best">
      <span class="rate__top">
        <span class="rate__name">Individual</span>
        <span><span class="rate__price">$20</span>
        <span class="rate__unit">per session</span></span>
      </span>
      <span class="rate__list">
        <span>10+ edited photographs</span>
        <span>Guaranteed 24-hour delivery</span>
        <span>Full-resolution files</span>
        <span>Personal and social use</span>
      </span>
    </div>
    <div class="rate">
      <span class="rate__top">
        <span class="rate__name">Team</span>
        <span><span class="rate__price">$10&ndash;15</span>
        <span class="rate__unit">per athlete</span></span>
      </span>
      <span class="rate__list">
        <span>30+ edited photographs</span>
        <span>One team photograph</span>
        <span>Action and individual frames</span>
        <span>Per-athlete galleries</span>
      </span>
    </div>
    <div class="rate">
      <span class="rate__top">
        <span class="rate__name">Events &amp; Meets</span>
        <span><span class="rate__price">From $75</span>
        <span class="rate__unit">up to 2 hours</span></span>
      </span>
      <span class="rate__list">
        <span>40+ edited photographs</span>
        <span>48-hour delivery</span>
        <span>Extra hours at $30</span>
        <span>Commercial use on request</span>
      </span>
    </div>
  </div>

  <div class="addons"><b>Add-ons</b>
    Same-day rush delivery <i>+$15</i><br>
    Additional edited photograph <i>$2 each</i><br>
    Travel beyond 30 miles <i>$0.30 / mile</i>
  </div>

  <div class="book">
    <span class="qr">__QR_CARD__</span>
    <div class="book__side">
      <b class="book__t">Book me</b>
      <div class="contact">
        <span class="c"><b>Phone</b><span>__PHONE__</span></span>
        <span class="c"><b>Instagram</b><span>__INSTA__</span></span>
        <span class="c"><b>Email</b><span>__EMAIL__</span></span>
        <span class="c"><b>Site</b><span>__SITE__</span></span>
      </div>
    </div>
  </div>
"""


def main():
    css = (CSS
           .replace("__OSW__", font_uri("fonts/oswald-var.woff2"))
           .replace("__ARC__", font_uri("fonts/archivo-var.woff2")))

    def fill(t):
        return (t.replace("__QR_STORE__", qr_svg(STORE_URL))
                 .replace("__QR_CARD__", qr_svg(CARD_URL))
                 .replace("__PHONE__", PHONE)
                 .replace("__EMAIL__", EMAIL)
                 .replace("__INSTA__", INSTA)
                 .replace("__SITE__", SITE))

    html = ("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\">"
            "<title>Garrett Erickson — Folder Sheets</title><style>%s</style>"
            "</head><body>%s%s%s</body></html>") % (
        css,
        sheet("Returning clients", fill(SHEET1), "1 of 3"),
        sheet("Ordering photos", fill(SHEET2), "2 of 3"),
        sheet("Rates", fill(SHEET3), "3 of 3", "sheet--tight"),
    )

    out = os.path.join(ROOT, "print", "folder-sheets.html")
    with open(out, "w") as f:
        f.write(html)
    print("wrote", out)
    print("QR ->", STORE_URL)
    print("QR ->", CARD_URL)


if __name__ == "__main__":
    main()

# To regenerate the PDF after editing this file:
#   python3 print/build_folder.py
#   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
#     --headless=new --disable-gpu --no-pdf-header-footer \
#     --print-to-pdf="$PWD/print/Erickson_Garrett_Folder_Sheets.pdf" \
#     "file://$PWD/print/folder-sheets.html"
