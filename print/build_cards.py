#!/usr/bin/env python3
"""Build print/business-cards.html — double-sided, fonts + QR inlined."""
import base64, io, os, segno

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QR_TARGET = "https://garrettphoto.store/card"

PHONE = "248-225-4437"
EMAIL = "Garrettoscarerickson@gmail.com"
INSTA = "@shot_by_ge"
VENMO = "@Garrett-Erickson-31"
SITE  = "garrettphoto.store"


def font_uri(rel):
    with open(os.path.join(ROOT, rel), "rb") as f:
        return "data:font/woff2;base64," + base64.b64encode(f.read()).decode("ascii")


def qr_svg(data, scale=10):
    """QR as an inline SVG sized by CSS.

    Three things matter for a code that actually scans:
      * a viewBox, or the fixed width/height keeps the drawing at its
        natural size and CSS sizing just clips it
      * a real white background, not transparency
      * a 4-module quiet zone, which the spec requires
    Error level M keeps the module count down (fewer, bigger modules
    scan better at card size) while still carrying 15% redundancy.
    """
    qr = segno.make(data, error="m")
    buf = io.BytesIO()          # segno writes bytes, not text
    qr.save(buf, kind="svg", scale=scale, border=4,
            dark="#000000", light="#ffffff", xmldecl=False, svgns=True,
            svgclass=None, lineclass=None)
    svg = buf.getvalue().decode("utf-8")
    side = qr.symbol_size(scale=scale, border=4)[0]
    return svg.replace(
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"' % (side, side),
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d"' % (side, side),
        1)


ICON = {
 "phone": '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.2a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2Z"/>',
 "mail":  '<rect x="2" y="4" width="20" height="16" rx="2.5"/><path d="m2.5 6.5 9.5 6.5 9.5-6.5"/>',
 "insta": '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.2" cy="6.8" r="1.1" fill="currentColor" stroke="none"/>',
 "venmo": '<rect x="3" y="3" width="18" height="18" rx="5"/><path d="M8.4 7.8 11.3 16h1.6l3-8.2"/>',
 "globe": '<circle cx="12" cy="12" r="9"/><path d="M3.2 9.5h17.6M3.2 14.5h17.6"/><path d="M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18Z"/>',
}


def icon(name):
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
            + ICON[name] + "</svg>")


FRONT = """
<div class="c-top">
  <div class="name">Garrett<br>Erickson</div>
  <div class="role">Photographer</div>
</div>
<div class="rule"></div>
<div class="grid">
  <span class="ln">{p}<b>{PHONE}</b></span>
  <span class="ln">{i}<b>{INSTA}</b></span>
  <span class="ln">{m}<b>{EMAIL}</b></span>
  <span class="ln">{v}<b>{VENMO}</b></span>
</div>
""".format(p=icon("phone"), m=icon("mail"), i=icon("insta"), v=icon("venmo"),
           PHONE=PHONE, EMAIL=EMAIL, INSTA=INSTA, VENMO=VENMO)

BACK = """
<div class="qr-wrap">{qr}</div>
<div class="qr-side">
  <div class="qr-name">Garrett<br>Erickson</div>
  <div class="qr-tag">Scan for phone,<br>email, Instagram<br>&amp; booking</div>
  <div class="qr-site">{g}<b>{SITE}</b></div>
</div>
""".format(qr=qr_svg(QR_TARGET), g=icon("globe"), SITE=SITE)

HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Business cards — Garrett Erickson</title>
<style>
@font-face {{ font-family:"Oswald"; src:url({osw}) format("woff2");
  font-weight:200 500; font-display:block; }}
@font-face {{ font-family:"Archivo"; src:url({arc}) format("woff2");
  font-weight:400 700; font-display:block; }}
@page {{ size:8.5in 11in; margin:0; }}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#6b6b70;font-family:"Archivo",Arial,sans-serif;
  -webkit-print-color-adjust:exact;print-color-adjust:exact}}
.howto{{max-width:8.5in;margin:0 auto;padding:16px 22px;background:#111;color:#eee;
  font-size:13px;line-height:1.6}}
.howto b{{color:#fff}}
.sheet{{position:relative;width:8.5in;height:11in;margin:0 auto;background:#fff;
  padding:.5in .75in;display:grid;grid-template-columns:repeat(2,3.5in);
  grid-template-rows:repeat(5,2in);page-break-after:always}}
.card{{width:3.5in;height:2in;position:relative;overflow:hidden;
  outline:.3pt solid #c9c9c9;outline-offset:-.15pt}}

/* ---------- front ---------- */
.card--front{{background:#0d0d10;color:#f2f2f0;display:flex;flex-direction:column;
  justify-content:space-between;padding:.22in .24in}}
.name{{font-family:"Oswald",sans-serif;font-weight:300;font-size:19pt;line-height:.97;
  letter-spacing:.055em;text-transform:uppercase}}
.role{{margin-top:.05in;font-size:6.2pt;font-weight:500;letter-spacing:.34em;
  text-transform:uppercase;color:#9b9ba4}}
.rule{{border-top:.4pt solid rgba(255,255,255,.26);margin:.05in 0 .06in}}
.grid{{display:grid;grid-template-columns:1fr;gap:.055in}}
.ln{{display:flex;align-items:center;gap:.07in;font-size:7.2pt;font-weight:500;
  letter-spacing:.01em;color:#f4f4f6;min-width:0}}
.ln svg{{width:9.5pt;height:9.5pt;flex:none;color:#b9b9c2}}
.ln b{{font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}

/* ---------- back ---------- */
.card--back{{background:#fff;color:#101014;display:flex;align-items:center;
  gap:.14in;padding:.18in .2in}}
.qr-wrap{{flex:none;width:1.55in;height:1.55in;display:flex}}
.qr-wrap svg{{width:100%;height:100%;display:block;shape-rendering:crispEdges}}
.qr-side{{display:flex;flex-direction:column;justify-content:center;gap:.07in;min-width:0}}
.qr-name{{font-family:"Oswald",sans-serif;font-weight:300;font-size:15pt;line-height:.97;
  letter-spacing:.05em;text-transform:uppercase}}
.qr-tag{{font-size:6.4pt;font-weight:500;letter-spacing:.05em;line-height:1.5;color:#5c5c63;
  text-transform:uppercase}}
.qr-site{{display:flex;align-items:center;gap:.06in;font-size:6.8pt;font-weight:600;
  letter-spacing:.04em;text-transform:uppercase}}
.qr-site svg{{width:9pt;height:9pt;flex:none;color:#5c5c63}}

@media print{{ body{{background:#fff}} .howto{{display:none}} .sheet{{margin:0}} }}
</style></head><body>

<div class="howto">
  <b>Double-sided printing.</b> Print <b>page 1</b> (fronts), then put the same
  sheet back in and print <b>page 2</b> (backs) — check your printer's feed
  direction first with one plain sheet marked “TOP”.
  Set <b>Scale 100% / Actual size</b> (never “Fit to page”),
  <b>Margins: None</b>, and turn on <b>Background graphics</b> or the dark
  fronts print blank. All 10 cards are identical, so the sheet lines up
  whichever way you flip it.
  <br><b>QR points to</b> garrettphoto.store/card — phone, email, Instagram,
  Venmo and the portfolio, all tappable.
</div>

<section class="sheet" id="s-front"></section>
<section class="sheet" id="s-back"></section>

<script>
var FRONT = {front!r};
var BACK  = {back!r};
function fill(id, cls, html) {{
  var host = document.getElementById(id);
  for (var i = 0; i < 10; i++) {{
    var d = document.createElement("div");
    d.className = "card " + cls;
    d.innerHTML = html;
    host.appendChild(d);
  }}
}}
fill("s-front", "card--front", FRONT);
fill("s-back",  "card--back",  BACK);
</script>
</body></html>
""".format(osw=font_uri("fonts/oswald-var.woff2"),
           arc=font_uri("fonts/archivo-var.woff2"),
           front=FRONT, back=BACK)

out = os.path.join(ROOT, "print", "business-cards.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(HTML)
print("wrote %s (%.0f KB)" % (out, os.path.getsize(out) / 1024))
print("QR ->", QR_TARGET)

# To regenerate the PDF after editing this file:
#   python3 print/build_cards.py
#   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
#     --headless=new --disable-gpu --no-pdf-header-footer \
#     --print-to-pdf="$PWD/print/Erickson_Garrett_Business_Cards.pdf" \
#     "file://$PWD/print/business-cards.html"
