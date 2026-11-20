#!/usr/bin/env python3
"""The cinematic home page. tools/home_page.py renders the classic page from
data/home.json as before, then hands it here: this keeps its SEO head tags,
structured data, availability dates and quote options, and lays the copy from
data/home.json, photos from data/photos.json and links from games/ into the
new design. Nothing is invented here.

The page opens on an intro that plays by itself (revamp/intro.js): an about-me
wall of the work, a look through the viewfinder, the tunnel and the field
(Higgsfield footage in revamp/intro/), then the shutter fires on the hero
photo. Scrolling on, each sport has its own colour and a shelf of game pods.
The tools that make the footage and the sound live outside the repo in
~/site-revamp (see its README).
"""
import html, json, re
from collections import OrderedDict
from pathlib import Path

ROOT = REPO = Path(__file__).resolve().parent.parent
INTRO = ROOT / "revamp/intro/intro.json"

# the intro's burst through the viewfinder, and the photo the shutter opens on
BURST = ["fgr-21", "dexter-76", "lnhs-78", "dexter-74", "loyola-57", "dexter-07"]
HERO_PHOTO = "lnhs-99"

# each sport's colour, its line, and the copy when home.json has none
SPORTS = [
    ("football", "Football", "under the lights.", "#e9c88a"),
    ("hockey", "Hockey", "on the glass.", "#a9cdea"),
    ("soccer", "Soccer", "in the box.", "#9ad5a8"),
    ("tennis", "Tennis", "at the net.", "#dbe57a"),
    ("volleyball", "Volleyball", "above the net.", "#f2a585"),
]
HOCKEY_COPY = "Varsity hockey from the boards: the rush up the ice, the save, and the bench when it goes in."

esc = html.escape


def md(text):
    """The tiny bit of markdown home.json uses: [links](url) and **bold**."""
    text = esc(text, quote=False)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)


def thumb(src):
    t = "images/thumbs/" + Path(src).name
    return t if (REPO / t).exists() else src


def ready():
    """True once the intro footage is in place."""
    return INTRO.exists()


def sport_of(ps):
    tags = [t for p in ps for t in p.get("tags", [])]
    return next((s for s, *_ in SPORTS if s in tags), None)


def page(old_index, photos, home):
    """The new index.html, given the classic page home_page.py rendered."""
    sec = {s["id"]: s for s in home["sections"]}
    # ---- head: keep every SEO tag exactly as the live page has it ----
    head = old_index.split("<head>", 1)[1].split('<link rel="stylesheet"', 1)[0].strip()
    head = re.sub(r"<!--.*?-->", "", head, flags=re.S).strip()
    pixel = re.search(r'<script src="js/pixel\.js[^"]*"></script>', old_index)
    source_opts = re.search(r'<select[^>]*id="q-source"[^>]*>(.*?)</select>', old_index, re.S).group(1).strip()
    avail_json = re.search(r'<script type="application/json" data-availability-json>.*?</script>',
                           old_index, re.S).group(0)

    games = OrderedDict()            # newest first: imports land at the top of photos.json
    for p in photos:
        if p.get("game"):
            games.setdefault(p["game"], []).append(p)
    by_src = {p["src"]: p for p in photos}
    favourites = [sec["about"]["photo"]] + sec["work"]["photos"] + sec["hero"]["photos"]

    # ---- game pages: map each game to its page by the photos the page shows ----
    game_url = {}
    for gp in sorted((REPO / "games").glob("*/index.html")):
        for src in re.findall(r'images/(?:thumbs/)?([\w.-]+\.jpg)', gp.read_text()):
            p = by_src.get("images/" + src)
            if p and p.get("game"):
                game_url.setdefault(p["game"], f"games/{gp.parent.name}/")
                break

    def alt(p):
        return esc(f'{p.get("title", "Sports photo")}, {p.get("location", "Michigan")}', quote=True)

    def cover(ps):
        return next((p for p in ps if p["src"] in favourites), ps[len(ps) // 3])

    # ---- the about-me wall: two frames from every game ----
    wall = []
    for ps in games.values():
        step = max(1, len(ps) // 3)
        wall += [ps[min(len(ps) - 1, step // 2)], ps[min(len(ps) - 1, step + step // 2)]]
    wall_html = "".join(f'<img src="{thumb(p["src"])}" alt="" decoding="async">' for p in wall[:45])

    # ---- one section per sport, a pod per game ----
    cards = {c["title"].lower(): c for c in sec["services"]["cards"]}
    sport_games = OrderedDict((s, []) for s, *_ in SPORTS)
    for name, ps in games.items():
        s = sport_of(ps)
        if s:
            sport_games[s].append((name, ps))
    sport_html, jump_html, n = [], [], 0
    for tag, title, tail, hue in SPORTS:
        gs = sport_games[tag]
        if not gs:
            continue
        n += 1
        total = sum(1 for p in photos if tag in p.get("tags", []))
        copy = cards[tag]["text"] if tag in cards else HOCKEY_COPY if tag == "hockey" else ""
        pods = "".join(f'''
            <a class="pod" href="{game_url.get(name, f"portfolio.html?tag={tag}")}">
              <img src="{thumb(cover(ps)["src"])}" alt="{alt(cover(ps))}" loading="lazy" width="600" height="600">
              <span class="pod__info"><b>{esc(name)}</b><small class="mono">{len(ps)} photos · {esc(ps[0].get("location", "Michigan"))}</small></span>
            </a>''' for name, ps in gs[:12])
        pods += f'''
            <a class="pod pod--all" href="portfolio.html?tag={tag}">
              <span class="pod__count">{total:,}</span><span class="mono">All {esc(title.lower())} photos →</span>
            </a>'''
        jump_html.append(f'<a href="#{tag}" style="--hue:{hue}"><i></i>{esc(title)}</a>')
        sport_html.append(f'''
        <article class="sport reveal" id="{tag}" style="--hue:{hue}">
          <div class="sport__head">
            <p class="kicker"><span>{n:02d}</span> {esc(title)} · {total:,} photos · {len(gs)} {"game" if len(gs) == 1 else "games"}</p>
            <h3 class="combo"><span class="combo__sans">{esc(title)}</span><span class="combo__serif">{esc(tail)}</span></h3>
            {f'<p class="sport__copy">{esc(copy)}</p>' if copy else ''}
          </div>
          <div class="pods" data-pods>{pods}
          </div>
        </article>''')

    about = sec["about"]
    quote = sec["quote"]
    faq = sec["faq"]
    contact = sec["contact"]
    svc = sec["services"]
    extra = [c for c in svc["cards"] if c["title"] in ("Teams & athletes", "Volleyball", "Any other sport")]
    svc_html = "".join(
        f'''<div class="svc"><h4>{esc(c["title"])}</h4><p>{esc(c["text"])}</p>
            <a class="link" href="{c["link"]}"{f' data-quote="{esc(c["quote"])}"' if c.get("quote") else ""}>{esc(c["linkText"].rstrip(" →"))} <i>→</i></a></div>'''
        for c in extra)
    faq_html = "".join(
        f'<details class="faq__item"><summary>{esc(q["q"])}<i aria-hidden="true">+</i></summary><p>{md(q["a"])}</p></details>'
        for q in faq["items"])
    opt_html = "".join(f"<option>{esc(o)}</option>" for o in quote["options"])
    point_html = "".join(f"<li>{esc(p)}</li>" for p in quote["points"])
    about_html = "".join(f"<p>{esc(p)}</p>" for p in about["paragraphs"])
    sports_list = [t for t, *_ in SPORTS if sport_games[t]]
    intro_cfg = json.dumps({
        "burst": [f"revamp/intro/ph/{p}.jpg" for p in BURST],
        "shots": len(photos), "games": len(games), "sports": len(sports_list),
    }, separators=(",", ":"))
    hero_alt = alt(by_src.get(f"images/{HERO_PHOTO}.jpg", {}))

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  {head}
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter+Tight:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
  <link rel="preload" as="image" href="revamp/intro/ph/{HERO_PHOTO}.jpg">
  <script>document.documentElement.classList.add("js")</script>
  <link rel="stylesheet" href="revamp/revamp.css">
  <link rel="stylesheet" href="revamp/intro.css">
  {pixel.group(0) if pixel else ""}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>

<header class="nav" data-nav>
  <a class="nav__name" href="/">Garrett Erickson</a>
  <nav class="nav__links" aria-label="Main">
    <a href="portfolio.html">Portfolio</a>
    <a href="games/">Games</a>
    <button class="nav__sound" type="button" data-sound aria-pressed="false" aria-label="Sound" hidden><i></i><i></i><i></i></button>
    <a class="nav__cta" href="#quote">Get a quote</a>
  </nav>
</header>

<main id="main">
  <section class="hero" id="top" aria-label="Garrett Erickson, Michigan sports photographer">
    <img class="hero__photo" src="revamp/intro/ph/{HERO_PHOTO}.jpg" alt="{hero_alt}" data-hero-photo>
    <div class="hero__shade" data-hero-shade></div>

    <div class="intro" data-intro='{intro_cfg}' aria-hidden="true">
      <div class="i-layer i-film"><canvas></canvas></div>
      <div class="i-layer i-flash"></div>
      <div class="i-layer i-flare"></div>
      <div class="i-layer i-about">
        <div class="i-wall">{wall_html}</div>
        <div class="i-about__dim"></div>
        <div class="i-slam"><span>Football.</span><span>Hockey.</span><span>Soccer.</span><span>Tennis.</span><small class="mono">01 / 04</small></div>
        <div class="i-about__copy">
          <p class="kicker"><span class="dot"></span>About · Metro Detroit, Michigan</p>
          <p class="combo"><span class="combo__sans">Shot from the sideline,</span><span class="combo__serif">all over Michigan.</span></p>
          <p class="i-about__line">The play, the huddle and the bench, so every athlete has photographs worth keeping.</p>
        </div>
      </div>
      <div class="i-layer i-vf">
        <div class="i-vf__imgs"></div>
        <div class="i-layer i-vf__flash"></div>
        <div class="i-layer i-vf__black"></div>
        <div class="i-hud">
          <i class="br tl"></i><i class="br tr"></i><i class="br bl"></i><i class="br bR"></i>
          <div class="i-hud__row i-hud__row--top"><span><i class="tag">M</i> RAW <span class="i-rec"><i></i>AF-C</span></span><span>1/2000 &nbsp; F2.8 &nbsp; ISO 3200 <i class="bat"></i></span></div>
          <div class="i-af"></div>
          <div class="i-hud__row i-hud__row--bot">
            <div class="i-shots"><small>SHOTS</small><b>0</b></div>
            <div class="i-meter">−3 <i class="big"></i><i></i><i></i><i class="big"></i><i></i><i></i><i class="big"></i> +3</div>
            <div class="i-stats"><div><small>GAMES</small><b>{len(games)}</b></div><div><small>TURNAROUND</small><b>24 hr</b></div><div><small>SPORTS</small><b>{len(sports_list)}</b></div></div>
          </div>
        </div>
      </div>
      <div class="i-layer i-beat" data-beat="12.5,15.4"><p class="combo"><span class="combo__sans">Game day</span><span class="combo__serif">starts in the tunnel.</span></p></div>
      <div class="i-layer i-beat" data-beat="20,26.4"><p class="combo"><span class="combo__sans">Friday nights,</span><span class="combo__serif">under the lights.</span></p></div>
      <div class="i-bar i-bar--top"></div><div class="i-bar i-bar--bot"></div>
      <svg class="i-shutter" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice"><path fill="#000" fill-rule="evenodd"/><g stroke="rgba(255,255,255,.14)" stroke-width="1.5" fill="none"></g></svg>
      <div class="i-layer i-loader">
        <div class="i-loader__name">Garrett Erickson</div>
        <div class="i-loader__row"><div class="i-loader__line"><i></i></div><div class="i-loader__num mono">000</div></div>
        <p class="kicker i-loader__label">Loading the lights</p>
        <div class="i-enter">
          <button type="button" class="btn btn--solid" data-enter="sound">Enter with sound</button>
          <button type="button" class="btn" data-enter="muted">Enter muted</button>
        </div>
      </div>
      <button type="button" class="i-skip mono">Skip intro →</button>
    </div>

    <div class="hero__copy" data-hero-copy>
      <p class="kicker"><span class="dot"></span>Metro Detroit · Michigan</p>
      <h1 class="name"><span>Garrett Erickson</span></h1>
      <p class="hero__role">{esc(sec["intro"]["role"])}. Football, hockey, soccer and tennis, from the sideline.</p>
      <div class="hero__ctas">
        <a class="btn btn--solid" href="#work">See the work</a>
        <a class="btn" href="portfolio.html">Full portfolio</a>
      </div>
    </div>
    <a class="scroll-cue mono" href="#work" data-hero-cue>Scroll</a>
  </section>

  <section class="work" id="work" aria-label="Sports photography">
    <div class="wrap work__head reveal">
      <p class="kicker"><span>01</span> The work · {len(photos):,} photos · {len(games)} games</p>
      <h2 class="combo"><span class="combo__sans">Sport by sport,</span><span class="combo__serif">game by game.</span></h2>
      <nav class="jump" aria-label="Sports">{"".join(jump_html)}</nav>
    </div>
    {"".join(sport_html)}
  </section>

  <section class="about wrap reveal" id="about">
    <p class="kicker"><span>02</span> About</p>
    <div class="about__grid">
      <div class="about__copy">{about_html}</div>
      <figure class="about__photo reveal-img" data-parallax><img src="{about["photo"]}" alt="{alt(by_src.get(about["photo"], {}))}" loading="lazy"></figure>
    </div>
    <div class="svcs reveal">{svc_html}</div>
    <p class="area reveal"><span class="mono">{esc(svc["areaLabel"])}</span>{esc(svc["area"])}</p>
  </section>

  <section class="avail wrap reveal" id="availability">
    <div class="head">
      <p class="kicker"><span>03</span> {esc(sec["availability"]["label"])} · {esc(sec["availability"]["aside"])}</p>
      <h2 class="combo"><span class="combo__sans">{esc(sec["availability"]["heading"])}</span></h2>
      <p class="head__lead">{esc(sec["availability"]["lead"])}</p>
    </div>
    <div class="avail__legend mono"><span class="is-open">{esc(sec["availability"]["openLabel"])}</span><span class="is-booked">{esc(sec["availability"]["bookedLabel"])}</span></div>
    <div class="avail__grid" data-availability><p class="mono">Dates load in a moment — or just ask for the date you want.</p></div>
    {avail_json}
  </section>

  <section class="quote wrap reveal" id="quote">
    <div class="quote__intro">
      <p class="kicker"><span>04</span> {esc(quote["label"])} · {esc(quote["aside"])}</p>
      <h2 class="combo"><span class="combo__sans">Get a quote</span><span class="combo__serif">for your shoot.</span></h2>
      <p class="head__lead">{esc(quote["intro"])}</p>
      <ul class="quote__points">{point_html}</ul>
    </div>
    <form class="quote__form" id="quote-form" novalidate>
      <label class="f f--wide">What are you booking?
        <select id="q-type" required><option value="">Choose one</option>{opt_html}</select></label>
      <label class="f">Sport <input type="text" id="q-sport" placeholder="Football, soccer…"></label>
      <label class="f">School or team <input type="text" id="q-team" placeholder="e.g. Country Day varsity"></label>
      <label class="f">Number of athletes <input type="number" id="q-count" min="1" inputmode="numeric" placeholder="1"></label>
      <label class="f">Date <input type="text" id="q-date" placeholder="e.g. Fri Oct 17, or flexible"></label>
      <label class="f f--wide">Location <input type="text" id="q-where" placeholder="Field, gym or city"></label>
      <label class="f f--wide">Tell me about it <textarea id="q-details" rows="4" placeholder="What you'd like photographed, for how long, and anything else I should know"></textarea></label>
      <label class="f">Your name <input type="text" id="q-name" autocomplete="name" required></label>
      <label class="f">Email <input type="email" id="q-email" autocomplete="email" required></label>
      <label class="f">Phone (optional) <input type="tel" id="q-phone" autocomplete="tel"></label>
      <label class="f">How did you hear about me?
        <select id="q-source">{source_opts}</select></label>
      <div class="f f--wide quote__actions">
        <button class="btn btn--solid quote__send" type="submit">{esc(quote["button"])}</button>
        <p class="quote__status mono" id="q-status" role="status"></p>
      </div>
      <div class="quote__sent"><p>{esc(quote["thanks"])}</p><button type="button" class="btn quote__again">Send another</button></div>
    </form>
  </section>

  <section class="faq wrap reveal" id="faq">
    <div class="head">
      <p class="kicker"><span>05</span> {esc(faq["label"])}</p>
      <h2 class="combo"><span class="combo__sans">Questions</span><span class="combo__serif">about booking.</span></h2>
    </div>
    <div class="faq__list">{faq_html}</div>
  </section>

  <section class="contact wrap reveal" id="contact">
    <p class="kicker"><span class="dot"></span>{esc(contact["aside"])}</p>
    <h2 class="name name--sm">Garrett Erickson</h2>
    <div class="contact__links">
      <a class="btn btn--solid" href="#quote">Get a quote</a>
      <a class="btn" href="mailto:{esc(contact["email"])}">{esc(contact["email"])}</a>
      <a class="btn" href="https://www.instagram.com/{esc(contact["instagram"])}" rel="noopener">@{esc(contact["instagram"])}</a>
    </div>
  </section>
</main>

<footer class="foot wrap mono">
  <span>© <span data-year>2026</span> Garrett Erickson · Michigan sports photographer</span>
  <span><a href="portfolio.html">Portfolio</a> · <a href="games/">Games</a> · <a href="card/">Card</a> · <a href="#top" data-replay>Replay intro</a></span>
</footer>

<script src="js/mailer.js"></script>
<script>window.CONTACT = {{ email: {json.dumps(contact["email"])} }};</script>
<script src="revamp/revamp.js"></script>
<script src="revamp/intro.js"></script>
</body>
</html>
'''
