#!/usr/bin/env python3
"""The scroll-film home page. tools/home_page.py renders the classic page from
data/home.json as before, then hands it here: this keeps its SEO head tags,
structured data, availability dates and quote options, and lays the copy from
data/home.json, photos from data/photos.json and links from games/ into the
new design. Nothing is invented here.

The film frames in revamp/film/ come from Higgsfield clips; the tools that make
them live outside the repo in ~/site-revamp (see its README).
"""
import html, json, re
from collections import OrderedDict
from pathlib import Path

ROOT = REPO = Path(__file__).resolve().parent.parent
FILM = ROOT / "revamp/film/film.json"

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
    """True once the film frames are in place."""
    return FILM.exists()


def page(old_index, photos, home):
    """The new index.html, given the classic page home_page.py rendered."""
    film = json.loads(FILM.read_text())
    sec = {s["id"]: s for s in home["sections"]}
    # ---- head: keep every SEO tag exactly as the live page has it ----
    head = old_index.split("<head>", 1)[1].split('<link rel="stylesheet"', 1)[0].strip()
    head = re.sub(r"<!--.*?-->", "", head, flags=re.S).strip()
    pixel = re.search(r'<script src="js/pixel\.js[^"]*"></script>', old_index)
    source_opts = re.search(r'<select[^>]*id="q-source"[^>]*>(.*?)</select>', old_index, re.S).group(1).strip()
    avail_json = re.search(r'<script type="application/json" data-availability-json>.*?</script>',
                           old_index, re.S).group(0)

    # ---- numbers for the camera callouts ----
    games = OrderedDict()            # newest first: imports land at the top of photos.json
    for p in photos:
        if p.get("game"):
            games.setdefault(p["game"], []).append(p)
    SPORTS = ["football", "hockey", "soccer", "tennis", "volleyball"]
    sports_shot = [s for s in SPORTS if any(s in p.get("tags", []) for p in photos)]
    stats = [
        (f"{len(photos):,}", "photographs on the site"),
        (str(len(games)), "games and shoots covered"),
        ("24 hr", "turnaround on individual sessions"),
        (str(len(sports_shot)), "sports and counting"),
    ]

    # ---- game pages: map each game to its page by the photos the page shows ----
    game_url = {}
    by_src = {p["src"]: p for p in photos}
    for page in sorted((REPO / "games").glob("*/index.html")):
        for src in re.findall(r'images/(?:thumbs/)?([\w.-]+\.jpg)', page.read_text()):
            p = by_src.get("images/" + src)
            if p and p.get("game"):
                game_url.setdefault(p["game"], f"games/{page.parent.name}/")
                break

    # ---- one chapter per sport, photos spread across games ----
    favourites = [sec["about"]["photo"]] + sec["work"]["photos"] + sec["hero"]["photos"]
    cards = {c["title"].lower(): c for c in sec["services"]["cards"]}
    CHAPTERS = [
        ("football", "Football", "under the lights.", cards["football"]["text"]),
        ("hockey", "Hockey", "on the glass.",
         "Varsity hockey from the boards: the rush up the ice, the save, and the bench when it goes in."),
        ("soccer", "Soccer", "in the box.", cards["soccer"]["text"]),
        ("tennis", "Tennis", "at the net.", cards["tennis"]["text"]),
    ]


    def picks(tag, n=4):
        pool = [p for p in photos if tag in p.get("tags", [])]
        fav = [p for p in pool if p["src"] in favourites]
        out, seen = list(fav), {p["src"] for p in fav}
        rounds = OrderedDict()
        for p in pool:
            if p["src"] not in seen and "detail" not in p.get("tags", []):
                rounds.setdefault(p.get("game"), []).append(p)
        i = 0
        while len(out) < n and any(i < len(v) for v in rounds.values()):
            for v in rounds.values():   # round-robin so every game gets a frame
                if i < len(v) and len(out) < n:
                    out.append(v[i * 7 % len(v)] if len(v) > 7 else v[i])
            i += 1
        # the lead frame is the tall one on the left; prefer a portrait
        out.sort(key=lambda p: p.get("orientation") != "portrait")
        return out[:n], len(pool)


    def alt(p):
        return esc(f'{p.get("title", "Sports photo")}, {p.get("location", "Michigan")}', quote=True)


    chap_html = []
    for i, (tag, title, tail, text) in enumerate(CHAPTERS, 1):
        ps, total = picks(tag)
        if not ps:
            continue
        lead, rest = ps[0], ps[1:]
        tiles = "".join(
            f'<a class="sport__tile reveal-img" href="portfolio.html?tag={tag}"><img src="{thumb(p["src"])}" '
            f'alt="{alt(p)}" loading="lazy" width="600" height="600"></a>' for p in rest)
        chap_html.append(f'''
        <article class="sport reveal" style="--hue:var(--{tag})">
          <div class="sport__text">
            <p class="kicker"><span>{i:02d}</span> {esc(title)} · {total:,} photos</p>
            <h3 class="combo"><span class="combo__sans">{esc(title)}</span><span class="combo__serif">{esc(tail)}</span></h3>
            <p class="sport__copy">{esc(text)}</p>
            <a class="link" href="portfolio.html?tag={tag}">See {esc(title.lower())} photos <i>→</i></a>
          </div>
          <a class="sport__lead reveal-img" data-parallax href="portfolio.html?tag={tag}">
            <img src="{lead["src"]}" alt="{alt(lead)}" loading="lazy" width="{lead["w"]}" height="{lead["h"]}">
          </a>
          <div class="sport__tiles">{tiles}</div>
        </article>''')

    # ---- recent games ----
    game_html = []
    for name, ps in list(games.items())[:8]:
        cover = next((p for p in ps if p["src"] in favourites), ps[len(ps) // 3])
        url = game_url.get(name, "games/")
        game_html.append(f'''
          <a class="game" href="{url}">
            <span class="game__img reveal-img"><img src="{thumb(cover["src"])}" alt="{alt(cover)}" loading="lazy" width="600" height="600"></span>
            <span class="game__name">{esc(name)}</span>
            <span class="game__meta mono">{len(ps)} photos · {esc(ps[0].get("location", "Michigan"))}</span>
          </a>''')

    about = sec["about"]
    quote = sec["quote"]
    faq = sec["faq"]
    contact = sec["contact"]
    svc = sec["services"]
    extra =[c for c in svc["cards"] if c["title"] in ("Teams & athletes", "Volleyball", "Any other sport")]

    stat_html = "".join(
        f'<li class="callout callout--{i}"><b data-count>{esc(v)}</b><span>{esc(l)}</span></li>'
        for i, (v, l) in enumerate(stats))
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

    film_cfg = json.dumps({k: film[k] for k in ("desktop", "mobile")}, separators=(",", ":"))

    page = f'''<!DOCTYPE html>
    <html lang="en">
    <head>
      {head}
      <link rel="preconnect" href="https://fonts.googleapis.com">
      <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
      <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter+Tight:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
      <link rel="preload" as="image" href="{film["poster"]}">
      <script>document.documentElement.classList.add("js")</script>
      <link rel="stylesheet" href="revamp/revamp.css">
      {pixel.group(0) if pixel else ""}
    </head>
    <body>
    <a class="skip" href="#main">Skip to content</a>

    <header class="nav" data-nav>
      <a class="nav__name" href="/">Garrett Erickson</a>
      <nav class="nav__links" aria-label="Main">
        <a href="portfolio.html">Portfolio</a>
        <a href="games/">Games</a>
        <a class="nav__cta" href="#quote">Get a quote</a>
      </nav>
    </header>

    <main id="main">
      <!-- Scroll film: Higgsfield frames scrubbed on a canvas, real text on top -->
      <section class="film" data-film='{film_cfg}' aria-label="Introduction">
        <div class="film__stage" aria-hidden="true">
          <img class="film__poster" src="{film["poster"]}" alt="">
          <canvas class="film__canvas"></canvas>
          <div class="film__shade"></div>
        </div>

        <div class="chap chap--hero" data-chap>
          <p class="kicker"><span class="dot"></span>Metro Detroit · Michigan</p>
          <h1 class="name"><span class="name__ink">Garrett Erickson</span></h1>
          <p class="hero__role">{esc(sec["intro"]["role"])}. Football, hockey, soccer and tennis, from the sideline.</p>
          <div class="hero__ctas">
            <a class="btn btn--solid" href="#quote">Get a quote</a>
            <a class="btn" href="portfolio.html">See the work</a>
          </div>
          <p class="scroll-cue mono">Scroll</p>
        </div>

        <div class="chap chap--stats" data-chap>
          <p class="kicker"><span class="dot"></span>Canon EOS R7 · RF 70–200mm f/2.8L</p>
          <ul class="callouts">{stat_html}</ul>
        </div>

        <div class="chap chap--lens" data-chap>
          <h2 class="combo combo--xl"><span class="combo__sans">Every frame</span><span class="combo__serif">from the sideline.</span></h2>
        </div>

        <div class="chap chap--tunnel" data-chap>
          <h2 class="combo combo--xl"><span class="combo__sans">Game day</span><span class="combo__serif">starts in the tunnel.</span></h2>
          <p class="chap__lead">{esc(about["heading"])}</p>
        </div>

        <div class="chap chap--field" data-chap>
          <h2 class="combo combo--xl"><span class="combo__sans">Friday nights,</span><span class="combo__serif">under the lights.</span></h2>
          <div class="hero__ctas">
            <a class="btn btn--solid" href="#quote" data-quote="Game or tournament coverage">Book game day</a>
            <a class="btn" href="#availability">See open dates</a>
          </div>
        </div>
      </section>

      <section class="about wrap reveal" id="about">
        <p class="kicker"><span>01</span> About</p>
        <div class="about__grid">
          <div class="about__copy">{about_html}</div>
          <figure class="about__photo reveal-img" data-parallax><img src="{about["photo"]}" alt="{alt(by_src.get(about["photo"], {}))}" loading="lazy"></figure>
        </div>
      </section>

      <section class="sports wrap" id="sports-photography" aria-label="Sports photography">
        {"".join(chap_html)}
        <div class="svcs reveal">{svc_html}</div>
        <p class="area reveal"><span class="mono">{esc(svc["areaLabel"])}</span>{esc(svc["area"])}</p>
      </section>

      <section class="games wrap reveal" id="games">
        <div class="head">
          <p class="kicker"><span>02</span> Recent games</p>
          <h2 class="combo"><span class="combo__sans">Find your game,</span><span class="combo__serif">find your shot.</span></h2>
          <a class="link" href="games/">Every game <i>→</i></a>
        </div>
        <div class="games__row">{"".join(game_html)}</div>
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
      <span><a href="portfolio.html">Portfolio</a> · <a href="games/">Games</a> · <a href="card/">Card</a></span>
    </footer>

    <script src="js/mailer.js"></script>
    <script>window.CONTACT = {{ email: {json.dumps(contact["email"])} }};</script>
    <script src="revamp/revamp.js"></script>
    </body>
    </html>
    '''
    return page
