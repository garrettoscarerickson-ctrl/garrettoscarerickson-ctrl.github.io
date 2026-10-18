#!/usr/bin/env python3
"""One page per team game, built from data/photos.json.

Parents search for the game itself ("country day cranbrook homecoming
photos"). The portfolio is a single page of every photograph, so it
answers no search in particular. Each team game gets its own page at
/games/<slug>/ with its photographs, a title and description written for
that search, and a way to book the next one. games/index.html lists them
all, and sitemap.xml is rewritten to include every page.

A game can also carry a short write-up (the score, a standout play, the
weather), typed in Studio's Games tab and kept in data/games.json. It goes
under the page's heading, because a page of photos alone gives a search
engine very little to read.

Only a game whose name starts with a school in SCHOOLS gets a page. A
private session ("Franco — Hockey") starts with an athlete's first name,
so it never does: its page would put a kid's name into Google. A game
from a school that isn't listed yet is reported and skipped until it is
added below.

    python3 tools/game_pages.py     # studio.py --regen runs this too
"""

import html
import json
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "photos.json")
NOTES = os.path.join(ROOT, "data", "games.json")
GAMES = os.path.join(ROOT, "games")
SITEMAP = os.path.join(ROOT, "sitemap.xml")
SITE = "https://garrettphoto.store"
EMAIL = "garrettoscarerickson@gmail.com"

# How each school is written at the start of a game name, and its full
# name, which is what parents type into Google.
SCHOOLS = {
    "DCDS": "Detroit Country Day",
    "Seaholm": "Seaholm",
    "Brother Rice": "Brother Rice",
    "Cass Tech": "Detroit Cass Tech",
    "Denby": "Detroit Denby",
}

SPORTS = ("football", "soccer", "tennis", "volleyball", "hockey",
          "basketball", "baseball", "softball", "lacrosse")

THUMB_EDGE = 600   # long edge of images/thumbs/, made by studio.py


def esc(s):
    return html.escape(str(s), quote=True)


def school_of(game):
    for short in sorted(SCHOOLS, key=len, reverse=True):
        if game == short or game.startswith(short + " "):
            return short
    return None


def full_name(game, short):
    """'DCDS Varsity Football vs Cranbrook — Homecoming' becomes
    'Detroit Country Day Varsity Football vs Cranbrook — Homecoming'."""
    return SCHOOLS[short] + game[len(short):]


def slugify(s):
    s = s.lower().replace("&", " and ").replace("#", " ")
    s = re.sub(r"[’'.]", "", s)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def sport_of(photos):
    tags = [t for p in photos for t in p.get("tags", [])]
    for sport in SPORTS:
        if sport in tags:
            return sport
    return None


def thumb_size(p):
    w, h = p.get("w") or THUMB_EDGE, p.get("h") or THUMB_EDGE
    scale = THUMB_EDGE / max(w, h)
    return round(w * scale), round(h * scale)


def load_notes():
    """{game name: {"about": text}} from data/games.json."""
    try:
        with open(NOTES, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_notes(notes):
    notes = {k: v for k, v in sorted(notes.items()) if (v.get("about") or "").strip()}
    with open(NOTES, "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2, ensure_ascii=False)
        f.write("\n")


def pages(photos):
    """{game name: slug} for every game that gets a page."""
    return {g["game"]: g["slug"] for g in collect(photos)[0]}


def collect(photos):
    """The team games, in manifest order (newest first), plus the names
    of any games skipped because their school isn't in SCHOOLS."""
    order, groups, skipped = [], {}, set()
    for p in photos:
        game = p.get("game")
        if not game:
            continue
        short = school_of(game)
        if not short:
            skipped.add(game)
            continue
        if game not in groups:
            groups[game] = []
            order.append(game)
        groups[game].append(p)

    notes = load_notes()
    games = []
    for game in order:
        ps = groups[game]
        name = full_name(game, school_of(game))
        games.append({
            "game": game,
            "name": name,
            "school": SCHOOLS[school_of(game)],
            "slug": slugify(name),
            "sport": sport_of(ps),
            "year": ps[0].get("year"),
            "about": (notes.get(game) or {}).get("about", "").strip(),
            "photos": ps,
        })
    return games, skipped


# ---------------- page parts ----------------

HEAD = """<!DOCTYPE html>
<!-- GENERATED FILE - do not edit by hand.
     Source: data/photos.json. Rebuild: python3 studio.py --regen -->
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>%(title)s</title>
  <meta name="description" content="%(desc)s">
  <link rel="canonical" href="%(url)s">

  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Garrett Erickson - Sports and Portrait Photography">
  <meta property="og:title" content="%(title)s">
  <meta property="og:description" content="%(desc)s">
  <meta property="og:url" content="%(url)s">
  <meta property="og:image" content="%(image)s">
  <meta name="twitter:card" content="summary_large_image">

  <script type="application/ld+json">
%(ld)s
  </script>

  <link rel="icon" href="/favicon.ico" sizes="48x48">
  <link rel="icon" href="/icon-192.png" type="image/png" sizes="192x192">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <link rel="stylesheet" href="/css/style.css">
  <link rel="stylesheet" href="/css/theme.css">
  <link rel="stylesheet" href="/css/games.css">
  <script src="/js/pixel.js"></script>
</head>
<body data-page="games">

  <nav class="nav">
    <a class="nav__name" href="/index.html">Garrett Erickson</a>
    <div class="nav__links">
      <a href="/index.html">Home</a>
      <a href="/portfolio.html">Portfolio</a>
      <a href="/games/"%(games_current)s>Games</a>
    </div>
  </nav>
"""

FOOT = """
  <footer class="footer">
    <span class="mono">© 2026 Garrett Erickson · Michigan Sports Photographer</span>
    <a class="mono" href="mailto:%s">%s</a>
    <span class="mono">Based in Metro Detroit, Michigan</span>
  </footer>

</body>
</html>
""" % (EMAIL, EMAIL)


def ld_json(page_type, name, url, desc, crumbs):
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": page_type,
                "name": name,
                "url": url,
                "description": desc,
                "author": {"@id": SITE + "/#garrett"},
                "isPartOf": {"@id": SITE + "/#website"},
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": i + 1, "name": n, "item": u}
                    for i, (n, u) in enumerate(crumbs)
                ],
            },
        ],
    }
    return "  " + json.dumps(data, indent=2, ensure_ascii=False).replace("\n", "\n  ")


def tile(p, alt):
    src = p["src"]
    tw, th = thumb_size(p)
    thumb = "images/thumbs/" + os.path.basename(src)
    return ('<a class="ph--tile" href="/%s"><div class="ph__img">'
            '<img src="/%s" width="%d" height="%d" alt="%s" loading="lazy" decoding="async">'
            '</div></a>' % (esc(src), esc(thumb), tw, th, esc(alt)))


def game_card(g):
    p = g["photos"][0]
    return ('<a class="game-card" href="/games/%s/">%s<span class="game-card__name">%s</span>'
            '<span class="mono">%d photos</span></a>'
            % (g["slug"], tile_img(p, g["name"]), esc(g["name"]), len(g["photos"])))


def tile_img(p, alt):
    tw, th = thumb_size(p)
    return ('<img src="/images/thumbs/%s" width="%d" height="%d" alt="%s" loading="lazy" decoding="async">'
            % (esc(os.path.basename(p["src"])), tw, th, esc(alt)))


# ---------------- pages ----------------

def game_page(g, games):
    n = len(g["photos"])
    sport = g["sport"] or "sports"
    year = g["year"] or ""
    url = "%s/games/%s/" % (SITE, g["slug"])
    title = "%s Photos%s | Garrett Erickson" % (g["name"], " (%s)" % year if year else "")
    desc = ("%d photos from %s%s, by Metro Detroit sports photographer Garrett "
            "Erickson. Book a shoot for your athlete's next game." % (n, g["name"], ", %s" % year if year else ""))
    crumbs = [("Home", SITE + "/"), ("Game photos", SITE + "/games/"), (g["name"], url)]

    about = "".join("<p>%s</p>" % esc(para.strip())
                    for para in re.split(r"\n\s*\n", g["about"]) if para.strip())
    tiles = "".join(tile(p, "%s, %s photo %d" % (g["name"], sport, i + 1))
                    for i, p in enumerate(g["photos"]))

    # same school and sport first, then the rest of the school, then everything else
    others = [o for o in games if o is not g]
    others.sort(key=lambda o: (o["school"] != g["school"] or o["sport"] != g["sport"],
                               o["school"] != g["school"]))
    more = "".join(game_card(o) for o in others[:6])

    body = """
  <header class="archive-head">
    <span class="mono"><a href="/games/">Game photos</a> / %(school)s %(sport)s</span>
    <h1 class="game-title">%(name)s</h1>
    <p class="archive-head__lead">%(n)d photos from %(name)s%(year)s, shot from the
    sideline by Garrett Erickson, a Metro Detroit sports photographer. Want photos like
    these of your athlete? <a href="/#quote">Get a free quote</a> and I'll shoot the next game.</p>%(about)s
    <a class="quote-btn game-cta" href="/#quote">Book the next game</a>
  </header>

  <main class="archive-grid">%(tiles)s</main>

  <section class="game-more">
    <p class="game-note">Want a photo taken down? Email
    <a href="mailto:%(email)s">%(email)s</a> with the photo and it comes down, no questions asked.</p>
    <h2 class="game-more__title">More games</h2>
    <div class="game-cards">%(more)s</div>
    <p class="game-note"><a href="/games/">All game photos</a> · <a href="/portfolio.html">Full portfolio</a></p>
  </section>
""" % {"school": esc(g["school"]), "sport": esc(sport), "name": esc(g["name"]), "n": n,
       "year": ", %s" % year if year else "", "tiles": tiles,
       "about": '\n    <div class="game-about">%s</div>' % about if about else "", "more": more, "email": EMAIL}

    head = HEAD % {"title": esc(title), "desc": esc(desc), "url": url, "games_current": "",
                   "image": SITE + "/" + g["photos"][0]["src"],
                   "ld": ld_json("ImageGallery", g["name"] + " photos", url, desc, crumbs)}
    return head + body + FOOT


def index_page(games):
    url = SITE + "/games/"
    title = "High School Game Photos, Metro Detroit | Garrett Erickson"
    desc = ("Photos from Detroit Country Day, Seaholm and Brother Rice games: football, "
            "soccer, tennis, volleyball and more, by Michigan sports photographer Garrett Erickson.")
    crumbs = [("Home", SITE + "/"), ("Game photos", url)]

    sections = []
    for school in dict.fromkeys(g["school"] for g in games):
        cards = "".join(game_card(g) for g in games if g["school"] == school)
        sections.append('<h2 class="game-more__title">%s</h2><div class="game-cards">%s</div>'
                        % (esc(school), cards))

    body = """
  <header class="archive-head">
    <h1>Game photos</h1>
    <p class="archive-head__lead">Every team game I've shot, by school. Find your athlete's
    game, or <a href="/#quote">get a free quote</a> to book the next one.</p>
  </header>

  <section class="game-more game-index">%s
    <p class="game-note">Want a photo taken down? Email
    <a href="mailto:%s">%s</a> and it comes down, no questions asked.</p>
  </section>
""" % ("".join(sections), EMAIL, EMAIL)

    head = HEAD % {"title": esc(title), "desc": esc(desc), "url": url,
                   "games_current": ' aria-current="page"',
                   "image": SITE + "/" + games[0]["photos"][0]["src"],
                   "ld": ld_json("CollectionPage", "Game photos", url, desc, crumbs)}
    return head + body + FOOT


def sitemap(games):
    """Every page, and on each game page its photographs, so they can
    turn up in Google Images when someone searches the school or game."""
    entries = [(u, []) for u in (SITE + "/", SITE + "/portfolio.html", SITE + "/games/")]
    entries += [("%s/games/%s/" % (SITE, g["slug"]), [SITE + "/" + p["src"] for p in g["photos"]])
                for g in games]

    def entry(url, images):
        imgs = "".join("    <image:image><image:loc>%s</image:loc></image:image>\n" % esc(i)
                       for i in images)
        return "  <url>\n    <loc>%s</loc>\n%s  </url>\n" % (url, imgs)

    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
            '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n%s</urlset>\n'
            % "".join(entry(u, imgs) for u, imgs in entries))


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build(photos=None):
    if photos is None:
        with open(DATA, encoding="utf-8") as f:
            photos = json.load(f)
    games, skipped = collect(photos)

    # pages for games that no longer exist are removed
    wanted = {g["slug"] for g in games}
    if os.path.isdir(GAMES):
        for name in os.listdir(GAMES):
            path = os.path.join(GAMES, name)
            if os.path.isdir(path) and name not in wanted:
                shutil.rmtree(path)

    for g in games:
        write(os.path.join(GAMES, g["slug"], "index.html"), game_page(g, games))
    if games:
        write(os.path.join(GAMES, "index.html"), index_page(games))
    write(SITEMAP, sitemap(games))

    print("games/: %d game pages + index, sitemap.xml rewritten" % len(games))
    for game in sorted(skipped):
        print("  no page (not a team game, or school not in SCHOOLS): %s" % game)
    return games


if __name__ == "__main__":
    build()
