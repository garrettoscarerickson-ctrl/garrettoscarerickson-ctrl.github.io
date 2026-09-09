#!/usr/bin/env python3
"""Build the Divine Child game-day booking post (1080x1350), matching the
type system in social/rates-a.html."""
import base64, io, os, subprocess, sys
from PIL import Image

ROOT = "/Users/garre/photography-portfolio"
SCR  = "/private/tmp/claude-501/-Users-garre/614ccde3-2027-473c-be29-2b91dc03405a/scratchpad"
PHOTO = "/Volumes/Creator Pro/DCDSVARFOT_VSRED_FINALS/Erickson_Garrett-037.jpg"
BG_POS = sys.argv[1] if len(sys.argv) > 1 else "center 38%"

def font_uri(p):
    with open(os.path.join(ROOT, p), "rb") as f:
        return "data:font/woff2;base64," + base64.b64encode(f.read()).decode()

def logo_slot(rel, alt):
    """Renders a logo badge if the file is there, nothing if it isn't —
    so dropping social/logos/*.png in is the only step needed."""
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return ""
    im = Image.open(path).convert("RGBA")
    im.thumbnail((300, 300), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "PNG", optimize=True)
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return '<img class="mu__logo" src="%s" alt="%s">' % (uri, alt)

def photo_uri(p, w=1400):
    im = Image.open(p).convert("RGB")
    im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=90, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
@font-face{{font-family:"Oswald";src:url({osw}) format("woff2");font-weight:200 500}}
@font-face{{font-family:"Archivo";src:url({arc}) format("woff2");font-weight:400 700}}

*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0b0b0e}}
.post{{position:relative;width:1080px;height:1350px;background:#0b0b0e;color:#f2f2f0;
      overflow:hidden;font-family:"Archivo",Helvetica,Arial,sans-serif}}

.bg{{position:absolute;inset:0;background:url({photo}) {bgpos}/cover no-repeat}}
/* Open through the upper-middle band where the helmet sits, then close
   hard so the booking block below reads at full contrast. */
.veil{{position:absolute;inset:0;background:
  linear-gradient(180deg,rgba(8,8,10,.80) 0%,rgba(8,8,10,.66) 12%,
                  rgba(8,8,10,.46) 22%,rgba(8,8,10,.20) 34%,
                  rgba(8,8,10,.20) 44%,rgba(8,8,10,.58) 53%,
                  rgba(8,8,10,.90) 61%,rgba(8,8,10,.99) 70%,
                  rgba(8,8,10,1) 100%)}}

/* Local scrim so the headline keeps contrast over the helmet crown.
   Feathered on both axes — a hard bottom edge draws a visible seam
   straight across the helmet. */
.tscrim{{position:absolute;left:0;top:0;width:84%;height:44%;
        background:linear-gradient(103deg,rgba(8,8,10,.74) 0%,rgba(8,8,10,.58) 50%,
                                   rgba(8,8,10,.16) 84%,rgba(8,8,10,0) 100%);
        -webkit-mask-image:linear-gradient(180deg,#000 0%,#000 46%,rgba(0,0,0,.55) 66%,
                                           rgba(0,0,0,0) 100%)}}
.wrap{{position:absolute;inset:0;padding:72px 68px;display:flex;flex-direction:column}}

.kicker{{font-size:17px;font-weight:600;letter-spacing:.34em;text-transform:uppercase;
        color:#c8c8d0}}
.title{{font-family:"Oswald",sans-serif;font-weight:500;font-size:104px;line-height:.92;
       letter-spacing:-.01em;text-transform:uppercase;margin-top:14px}}
.title em{{font-style:normal;color:#e0bc4e;text-shadow:0 2px 30px rgba(8,8,10,.75)}}
.matchup{{margin-top:26px;display:flex;align-items:center;gap:22px}}
.mu__side{{display:flex;align-items:center;gap:16px}}
.mu__logo{{width:74px;height:74px;object-fit:contain;flex:none;
          filter:drop-shadow(0 2px 14px rgba(8,8,10,.9))}}
.mu__team{{font-family:"Oswald",sans-serif;font-weight:500;font-size:46px;line-height:1;
          letter-spacing:.03em;text-transform:uppercase;white-space:nowrap}}
.mu__x{{font-family:"Oswald",sans-serif;font-weight:500;font-size:30px;color:#e0bc4e;
       letter-spacing:.1em}}

.when{{margin-top:20px;display:inline-flex;align-self:flex-start;align-items:center;gap:14px;
      padding:11px 20px;border:1px solid rgba(255,255,255,.32);border-radius:999px;
      font-size:18px;font-weight:600;letter-spacing:.16em;text-transform:uppercase}}
.when i{{font-style:normal;width:7px;height:7px;border-radius:50%;background:#d8b64a}}

.lower{{margin-top:auto}}
.sub{{font-size:25px;line-height:1.44;color:#e4e4e6;max-width:800px}}
.sub b{{font-weight:700}}

.rows{{margin-top:34px}}
.row{{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;
     padding:22px 0;border-top:1px solid rgba(255,255,255,.15)}}
.row:last-child{{border-bottom:1px solid rgba(255,255,255,.15)}}
.row__name{{font-family:"Oswald",sans-serif;font-weight:500;font-size:40px;
           letter-spacing:.05em;line-height:1}}
.row__lead{{margin-top:8px;font-size:18px;color:#a8a8b2}}
.row__r{{text-align:right;flex:none}}
.row__price{{font-family:"Oswald",sans-serif;font-weight:500;font-size:48px;line-height:1}}
.row__unit{{margin-top:6px;font-size:16px;color:#a8a8b2}}

.store{{margin-top:26px;display:flex;align-items:center;gap:18px;padding:20px 26px;
       border-radius:16px;background:#f2f2f0;color:#0b0b0e}}
.store__big{{font-family:"Oswald",sans-serif;font-weight:500;font-size:52px;line-height:1;flex:none}}
.store__t{{font-size:20px;font-weight:700;line-height:1.3}}
.store__s{{margin-top:4px;font-size:17px;color:#55555c}}

.foot{{margin-top:26px;padding-top:24px;border-top:1px solid rgba(255,255,255,.15);
      display:flex;justify-content:space-between;align-items:baseline;
      font-size:20px;letter-spacing:.1em;text-transform:uppercase}}
.foot b{{font-weight:700}}.foot span{{color:#a8a8b2}}
</style></head><body>
<div class="post"><div class="bg"></div><div class="veil"></div><div class="tscrim"></div>
  <div class="wrap">
    <div class="kicker">Garrett Erickson · Sports Photography</div>
    <div class="title">Book a<br>Photographer<br><em>Now</em></div>
    <div class="matchup">
      <div class="mu__side">{dclogo}<span class="mu__team">Divine Child</span></div>
      <span class="mu__x">VS</span>
      <div class="mu__side">{cdlogo}<span class="mu__team">Country Day</span></div>
    </div>
    <div class="when"><i></i>JV Football · Wed Sept 9</div>

    <div class="lower">
      <div class="sub">I'm shooting this one. <b>Book a photographer before kickoff</b>
      and I'll follow your athlete all night — edited and delivered within 24 hours.</div>

      <div class="rows">
        <div class="row">
          <div><div class="row__name">YOUR ATHLETE</div>
            <div class="row__lead">10+ edited photographs · 24-hour delivery</div></div>
          <div class="row__r"><div class="row__price">$15</div>
            <div class="row__unit">per session</div></div>
        </div>
        <div class="row">
          <div><div class="row__name">WHOLE TEAM</div>
            <div class="row__lead">30+ photographs · per-athlete galleries</div></div>
          <div class="row__r"><div class="row__price">$5–10</div>
            <div class="row__unit">per athlete</div></div>
        </div>
      </div>

      <div class="store"><div class="store__big">$1</div><div>
        <div class="store__t">Or grab single photos after the game</div>
        <div class="store__s">Browse by game, find your number, download in minutes.</div>
      </div></div>

      <div class="foot"><b>DM @shot_by_ge to book now</b><span>garrettphoto.store</span></div>
    </div>
  </div>
</div></body></html>
""".format(osw=font_uri("social/fonts/oswald.woff2"),
           arc=font_uri("social/fonts/archivo.woff2"),
           photo=photo_uri(PHOTO), bgpos=BG_POS,
           dclogo=logo_slot("social/logos/divine-child.png", "Divine Child"),
           cdlogo=logo_slot("social/logos/country-day.png", "Country Day"))

html = os.path.join(ROOT, "social", os.environ.get("OUTNAME","divine-child")+".html")
open(html, "w", encoding="utf-8").write(HTML)

png = os.path.join(ROOT, "social", os.environ.get("OUTNAME","divine-child")+".png")
subprocess.run(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "--headless=new", "--disable-gpu", "--hide-scrollbars",
                "--force-device-scale-factor=1", "--window-size=1080,1350",
                "--screenshot=" + png, "file://" + html], check=True,
               capture_output=True)
print(html, "->", png, Image.open(png).size)
