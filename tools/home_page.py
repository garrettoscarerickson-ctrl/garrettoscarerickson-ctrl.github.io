#!/usr/bin/env python3
"""The home page, built from data/home.json.

Studio's Home tab edits data/home.json; this turns it into index.html
and css/theme.css. The page is written out as plain HTML rather than
assembled in the browser, so search engines read every word of it the
moment they load the page. js/main.js only adds behaviour on top: the
slideshow, the lightbox, the quote form and the reviews.

    python3 tools/home_page.py        # rebuild index.html + css/theme.css

Text fields are plain text. Paragraph-style fields also understand two
bits of shorthand: **bold** and [link text](address).
"""

import copy
import html
import json
import os
import re
from string import Template

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.join(ROOT, "data", "home.json")
INDEX = os.path.join(ROOT, "index.html")
THEME_CSS = os.path.join(ROOT, "css", "theme.css")

# Sections that carry a "01 — About" style number, counted in page order.
NUMBERED = ("about", "work", "services", "quote", "reviews", "faq", "contact")

FONTS = {
    "oswald": '"Oswald", "Helvetica Neue Condensed", "Arial Narrow", sans-serif',
    "archivo": '"Archivo", "Helvetica Neue", Arial, sans-serif',
    "helvetica": '"Helvetica Neue", Helvetica, Arial, sans-serif',
    "georgia": 'Georgia, "Times New Roman", serif',
    "system": 'system-ui, -apple-system, "Segoe UI", sans-serif',
}

DEFAULT_THEME = {
    "bg": "#0b0b0e", "bgRaise": "#15151a", "ink": "#f2f2f0",
    "inkDim": "#9b9ba4", "accent": "#ffffff", "radius": 18,
    "fontDisplay": "oswald", "fontBody": "helvetica", "fontUi": "archivo",
}

QUOTE_TYPES = ["Individual athlete session", "Team shoot",
               "Game or tournament coverage", "Senior or recruiting photos",
               "Car meet or other event", "Something else"]


# ---------------- defaults: the page exactly as it was ----------------

def _current_work(photos):
    """The six photographs the old script picked for Selected work."""
    pool = [p for p in photos if p.get("feature") or not p.get("archiveOnly")]
    if len(pool) < 6:
        pool = photos
    people = ("people", "portraits")
    pool = sorted(pool, key=lambda p: any(t in people for t in p.get("tags", [])))
    return [p["src"] for p in pool[:6]]


def default_home(photos):
    hero = next((p["src"] for p in photos if p.get("feature") == "hero"),
                photos[0]["src"] if photos else "")
    return {
        "seo": {
            "title": "Michigan Sports Photographer | Garrett Erickson Photography",
            "description": "Garrett Erickson is a Michigan sports photographer covering "
                           "high school football, soccer, tennis and volleyball across "
                           "Metro Detroit. Team, individual and event shoots. Get a free quote.",
            "shareImage": "images/varsoc-02.jpg",
        },
        "theme": dict(DEFAULT_THEME),
        "sections": [
            {"id": "intro", "type": "intro", "visible": True,
             "name": "Garrett Erickson", "role": "Michigan Sports Photographer"},
            {"id": "hero", "type": "hero", "visible": True,
             "photos": [hero] if hero else [],
             "button": "Get a quote", "buttonLink": "#quote",
             "left": "Michigan sports photographer — booking now",
             "right": "Football · Soccer · Tennis · Volleyball"},
            {"id": "marquee", "type": "marquee", "visible": True,
             "words": ["Football", "Soccer", "Tennis", "Volleyball", "Teams", "Events"]},
            {"id": "about", "type": "about", "visible": True, "label": "About",
             "heading": "I'm Garrett Erickson, a Michigan sports photographer covering "
                        "high school football, soccer, tennis and volleyball across Metro Detroit.",
             "paragraphs": [
                 "Most of my work happens on the sideline: varsity and JV football under the "
                 "lights at Detroit Country Day, soccer against Cranbrook and Cass Tech, tennis "
                 "match days at Seaholm and Liggett, and volleyball in the gym. I shoot the play, "
                 "the huddle and the bench, so every athlete has photographs worth keeping.",
                 "Away from the field I shoot architecture and street, including car meets along "
                 "Woodward and a stretch of work made in New York. I care about light, structure, "
                 "and the moment a scene resolves into something worth keeping.",
                 "I shoot whole teams and individual athletes, and I turn work around fast: "
                 "individual sessions are guaranteed back within 24 hours.",
             ],
             "button": "Get a quote", "buttonLink": "#quote", "photo": ""},
            {"id": "work", "type": "work", "visible": True, "label": "Selected work",
             "photos": _current_work(photos)},
            {"id": "services", "type": "services", "visible": True,
             "label": "Sports photography", "aside": "Metro Detroit · all of Michigan",
             "heading": "Sports photography in Michigan",
             "cards": [
                 {"title": "Football", "text": "Varsity and JV games and practices: the snap, the "
                  "run after the catch, the sideline and the post-game huddle.",
                  "linkText": "See football photos →", "link": "portfolio.html?tag=football", "quote": ""},
                 {"title": "Soccer", "text": "Varsity and JV soccer: headers, saves, celebrations "
                  "and the team talk at half time.",
                  "linkText": "See soccer photos →", "link": "portfolio.html?tag=soccer", "quote": ""},
                 {"title": "Tennis", "text": "Match days and practices, singles and doubles: the "
                  "serve toss, the stretch for a wide ball, the handshake at the net.",
                  "linkText": "See tennis photos →", "link": "portfolio.html?tag=tennis", "quote": ""},
                 {"title": "Volleyball", "text": "Kills, digs, serves and the whole bench on its feet.",
                  "linkText": "See volleyball photos →", "link": "portfolio.html?tag=volleyball", "quote": ""},
                 {"title": "Teams & athletes", "text": "Whole-roster shoots with a team photo and a "
                  "gallery for every athlete, or a one-on-one session for senior posts, recruiting "
                  "profiles and social media.",
                  "linkText": "Get a quote →", "link": "#quote", "quote": "Team shoot"},
                 {"title": "Any other sport", "text": "Basketball, hockey, lacrosse, baseball, softball, "
                  "swimming, track and field, and cross country, plus car meets and other events. "
                  "If it happens in Michigan, ask.",
                  "linkText": "Get a quote →", "link": "#quote", "quote": "Something else"},
             ],
             "areaLabel": "Where I shoot",
             "area": "Based in Metro Detroit. I regularly shoot in Detroit, Birmingham, Bloomfield "
                     "Hills, Beverly Hills, Royal Oak, Troy, Southfield, Grosse Pointe and Dearborn, "
                     "across Oakland, Wayne and Macomb counties, and anywhere else in Michigan on request."},
            {"id": "quote", "type": "quote", "visible": True, "label": "Get a quote",
             "aside": "Free · no obligation", "heading": "Get a quote for your shoot",
             "intro": "There are no set prices. Every shoot is different, so tell me what you're "
                      "booking and I'll email you a quote.",
             "points": ["Individual athlete sessions, guaranteed back within 24 hours",
                        "Whole-team shoots with a team photo and a gallery for every athlete",
                        "Game, tournament and event coverage anywhere in Michigan",
                        "Edited, full-resolution photos, with personal and social use included"],
             "options": list(QUOTE_TYPES),
             "button": "Get a quote",
             "thanks": "Thanks. Garrett has your details and will email you a quote."},
            {"id": "reviews", "type": "reviews", "visible": True, "label": "Reviews",
             "items": []},
            {"id": "faq", "type": "faq", "visible": True, "label": "Questions",
             "aside": "Booking a sports photographer", "heading": "Questions about booking",
             "items": [
                 {"q": "How much does a sports photographer cost in Michigan?",
                  "a": "Every shoot is quoted to fit: the price depends on the sport, how many "
                       "athletes, how long, and where. Fill in the [quote form](#quote) and I'll "
                       "email you a price. Quotes are free, with no obligation."},
                 {"q": "How fast will I get my photos?",
                  "a": "Individual sessions are guaranteed back within 24 hours, and events within "
                       "48 hours. If you need photos the same day, say so in your quote request."},
                 {"q": "Which schools and areas do you cover?",
                  "a": "I'm based in Metro Detroit and have shot games at Detroit Country Day, "
                       "Seaholm, Cranbrook, Liggett, Cass Tech, Divine Child, Redford and Holt. "
                       "I'll travel anywhere in Michigan."},
                 {"q": "Do you photograph whole teams?",
                  "a": "Yes. A team shoot covers the whole roster in one session, includes a team "
                       "photograph, and gives every athlete their own gallery of action and "
                       "individual frames."},
                 {"q": "Can I post the photos on Instagram or use them for recruiting?",
                  "a": "Yes. Personal and social use is included with every session, which covers "
                       "Instagram, recruiting profiles and highlight reels. Commercial use is "
                       "available on request."},
                 {"q": "What if I want a photo of my child taken down?",
                  "a": "Open the photograph in the portfolio and press **Request removal**. You "
                       "don't have to explain why, and I'll take it down."},
                 {"q": "How do I book?",
                  "a": "Send a request through the [quote form](#quote) and I'll reply with a price "
                       "and to confirm the date. You can also email "
                       "[garrettoscarerickson@gmail.com](mailto:garrettoscarerickson@gmail.com) or "
                       "DM [@shot_by_ge](https://www.instagram.com/shot_by_ge) on Instagram."},
             ]},
            {"id": "contact", "type": "contact", "visible": True, "label": "Contact",
             "aside": "Michigan · booking now",
             "email": "garrettoscarerickson@gmail.com", "instagram": "shot_by_ge"},
            {"id": "cta", "type": "cta", "visible": True,
             "text": "See the Portfolio", "link": "portfolio.html"},
        ],
    }


def load(photos):
    """data/home.json, created from the current page the first time."""
    if os.path.exists(HOME):
        with open(HOME, encoding="utf-8") as f:
            home = json.load(f)
    else:
        home = default_home(photos)
        save(home)
    theme = dict(DEFAULT_THEME)
    theme.update(home.get("theme") or {})
    home["theme"] = theme
    return home


def save(home):
    with open(HOME, "w", encoding="utf-8") as f:
        json.dump(home, f, indent=2, ensure_ascii=False)
        f.write("\n")


def clean(home, photos):
    """Keep only what the page knows how to show, so a bad save from the
    editor can never write a broken page. Unknown photos are dropped."""
    known = {p["src"] for p in photos}
    base = default_home(photos)
    out = {"seo": {}, "theme": dict(DEFAULT_THEME), "sections": []}
    for k in ("title", "description", "shareImage"):
        out["seo"][k] = str((home.get("seo") or {}).get(k, base["seo"][k]) or "")
    for k, v in (home.get("theme") or {}).items():
        if k in DEFAULT_THEME:
            out["theme"][k] = v
    try:
        out["theme"]["radius"] = max(0, min(40, int(out["theme"]["radius"])))
    except (TypeError, ValueError):
        out["theme"]["radius"] = DEFAULT_THEME["radius"]
    for k in ("bg", "bgRaise", "ink", "inkDim", "accent"):
        if not re.match(r"^#[0-9a-fA-F]{6}$", str(out["theme"][k])):
            out["theme"][k] = DEFAULT_THEME[k]
    for k in ("fontDisplay", "fontBody", "fontUi"):
        if out["theme"][k] not in FONTS:
            out["theme"][k] = DEFAULT_THEME[k]

    defaults = {s["type"]: s for s in base["sections"]}
    seen = set()
    for s in home.get("sections") or []:
        t = s.get("type")
        if t not in defaults or t in seen:
            continue
        seen.add(t)
        d = copy.deepcopy(defaults[t])
        for k, v in s.items():
            if k not in d:
                continue
            if isinstance(d[k], bool):
                d[k] = bool(v)
            elif isinstance(d[k], str):
                d[k] = str(v or "")
            elif isinstance(d[k], list):
                d[k] = v if isinstance(v, list) else d[k]
        if "photos" in d:
            d["photos"] = [p for p in d["photos"] if isinstance(p, str) and p in known]
        if "photo" in d and d["photo"] not in known:
            d["photo"] = ""
        for k in ("paragraphs", "words", "points", "options"):
            if k in d:
                d[k] = [str(x) for x in d[k] if str(x).strip()]
        if t == "services":
            d["cards"] = [{k: str(c.get(k, "") or "") for k in ("title", "text", "linkText", "link", "quote")}
                          for c in d["cards"] if isinstance(c, dict)]
        if t == "reviews":
            items = []
            for r in d["items"]:
                if not isinstance(r, dict) or not str(r.get("text", "")).strip():
                    continue
                try:
                    rating = max(1, min(5, int(r.get("rating", 5))))
                except (TypeError, ValueError):
                    rating = 5
                items.append({"name": str(r.get("name", "") or "").strip(),
                              "role": str(r.get("role", "") or "").strip(),
                              "rating": rating, "text": str(r.get("text", "")).strip()})
            d["items"] = items
        if t == "faq":
            d["items"] = [{"q": str(i.get("q", "") or ""), "a": str(i.get("a", "") or "")}
                          for i in d["items"] if isinstance(i, dict)]
        out["sections"].append(d)
    # a section missing from the save comes back hidden rather than vanishing
    for t, d in defaults.items():
        if t not in seen:
            d = copy.deepcopy(d)
            d["visible"] = False
            out["sections"].append(d)
    return out


# ---------------- rendering ----------------

def esc(s):
    return html.escape(str(s or ""), quote=True)


SAFE_LINK = re.compile(r"^(https?://|mailto:|tel:|#|[\w./?=&%-]+$)")


def rich(s):
    """Escape, then allow **bold** and [text](link)."""
    out = esc(s)
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)

    def link(m):
        text, href = m.group(1), html.unescape(m.group(2))
        if not SAFE_LINK.match(href):
            return m.group(0)
        ext = href.startswith("http")
        return '<a href="%s"%s>%s</a>' % (
            esc(href), ' target="_blank" rel="noopener noreferrer"' if ext else "", text)
    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, out)


def href(link):
    link = str(link or "").strip()
    return link if SAFE_LINK.match(link) else "#"


NOT_A_SPORT = ("sports", "people", "detail", "portraits")


def alt_of(p):
    if not p:
        return ""
    if p.get("game"):
        sport = next((t for t in p.get("tags", []) if t not in NOT_A_SPORT), None)
        return "%s from %s, %s" % ((sport.capitalize() + " photo") if sport else "Photo",
                                   p["game"], p.get("location", ""))
    return "%s — %s" % (p.get("title", ""), p.get("location", ""))


def thumb(src):
    return src.replace("images/", "images/thumbs/", 1) if src.startswith("images/") else src


def head_html(label, num, aside="", aside_attr=""):
    return ('<div class="section__head"><span class="mono">%s — %s</span>'
            '<span class="mono"%s>%s</span></div>' % (num, esc(label), aside_attr, esc(aside)))


def r_intro(s, ctx):
    words = s["name"].split()
    first, rest = (words[0], " ".join(words[1:])) if words else ("", "")
    return ('<div class="intro-wrap" data-section="intro"><section class="intro">'
            '<h1 class="intro__title"><span class="intro__name"><span>%s</span> <span>%s</span></span>'
            '<span class="intro__role">%s</span></h1>'
            '<span class="intro__scroll mono">Scroll</span></section></div>'
            % (esc(first), esc(rest), esc(s["role"])))


def r_hero(s, ctx):
    imgs = []
    for i, src in enumerate(s["photos"]):
        p = ctx["by_src"].get(src)
        imgs.append('<img src="%s" alt="%s" data-slot-photo="hero:%d"%s%s>' % (
            esc(src), esc(alt_of(p)), i,
            ' class="is-active" fetchpriority="high"' if i == 0 else ' loading="lazy"',
            ""))
    if not imgs:
        imgs.append('<span class="hero__empty" data-slot-photo="hero:0"></span>')
    btn = ('<a class="quote-btn hero__cta" href="%s">%s</a>' % (esc(href(s["buttonLink"])), esc(s["button"]))
           if s["button"].strip() else "")
    meta = ""
    if s["left"].strip() or s["right"].strip():
        meta = ('<div class="hero__meta"><span class="mono">%s</span><span class="mono">%s</span></div>'
                % (esc(s["left"]), esc(s["right"])))
    return ('<section class="hero" data-section="hero"><div class="hero__img-wrap" data-parallax>%s</div>'
            '<div class="hero__content">%s%s</div></section>' % ("".join(imgs), btn, meta))


def r_marquee(s, ctx):
    run = "".join('<span%s>%s</span><span>—</span>' % (' class="on"' if i % 2 else "", esc(w))
                  for i, w in enumerate(s["words"]))
    return ('<section class="marquee" aria-hidden="true" data-section="marquee">'
            '<div class="marquee__track">%s%s</div></section>' % (run, run))


def r_about(s, ctx):
    paras = "".join("<p>%s</p>" % rich(p) for p in s["paragraphs"])
    btn = ('<a class="quote-btn about__cta" href="%s">%s</a>' % (esc(href(s["buttonLink"])), esc(s["button"]))
           if s["button"].strip() else "")
    # The empty spot is hidden on the live site; Studio shows it so there
    # is something to click to add a photo.
    if s["photo"]:
        photo = ('<figure class="about__photo" data-slot-photo="about:photo">'
                 '<img src="%s" alt="%s" loading="lazy"></figure>'
                 % (esc(s["photo"]), esc(alt_of(ctx["by_src"].get(s["photo"])))))
    else:
        photo = ('<figure class="about__photo about__photo--empty" data-slot-photo="about:photo">'
                 '<span>Add a photo</span></figure>')
    return ('<section class="about reveal" id="about" data-section="about">'
            '<div class="about__side"><span class="mono about__eyebrow">%s — %s</span>%s</div>'
            '<div class="about__body"><h2 class="about__lead">%s</h2>%s%s</div></section>'
            % (ctx["num"], esc(s["label"]), photo, esc(s["heading"]), paras, btn))


def r_work(s, ctx):
    cards = []
    for i, src in enumerate(s["photos"]):
        p = ctx["by_src"].get(src) or {}
        cards.append(
            '<button class="ph%s" type="button" data-photo-src="%s" data-slot-photo="work:%d" '
            'aria-label="View %s"><figure><span class="ph__img wm"><span class="ph__par">'
            '<img loading="lazy" src="%s" alt="%s"></span></span><figcaption>'
            '<span class="ph__title">%s</span><span class="mono">%s</span></figcaption></figure></button>'
            % (" ph--portrait" if p.get("orientation") == "portrait" else "", esc(src), i,
               esc(p.get("title", "")), esc(thumb(src)), esc(alt_of(p)), esc(p.get("title", "")),
               esc(" / ".join(p.get("tags", [])))))
    if not cards:
        cards.append('<span class="selected__empty" data-slot-photo="work:0">Add photos in Studio</span>')
    n = ctx["count"]
    return ('<section class="selected reveal" data-section="work"><div class="section__head">'
            '<span class="mono">%s — %s</span><a class="mono selected__all" href="portfolio.html">'
            'All <span data-photo-count>%d photographs</span> →</a></div>'
            '<div class="selected__grid">%s</div></section>'
            % (ctx["num"], esc(s["label"]), n, "".join(cards)))


def r_services(s, ctx):
    cards = []
    for c in s["cards"]:
        link = href(c["link"])
        inner = '<h3 class="service__name">%s</h3><p>%s</p>' % (esc(c["title"]), rich(c["text"]))
        if c["linkText"].strip() and c["link"].strip():
            inner += '<span class="service__go">%s</span>' % esc(c["linkText"])
            dq = ' data-quote="%s"' % esc(c["quote"]) if c.get("quote") else ""
            cards.append('<a class="service" href="%s"%s>%s</a>' % (esc(link), dq, inner))
        else:
            cards.append('<div class="service">%s</div>' % inner)
    area = ""
    if s["area"].strip():
        area = ('<p class="services__area"><span class="mono">%s</span> %s</p>'
                % (esc(s["areaLabel"]), rich(s["area"])))
    return ('<section class="services reveal" id="sports-photography" data-section="services">%s'
            '<h2 class="section__title">%s</h2><div class="services__grid">%s</div>%s</section>'
            % (head_html(s["label"], ctx["num"], s["aside"]), esc(s["heading"]), "".join(cards), area))


QUOTE_FORM = Template("""
        <form class="quote__form" id="quote-form" novalidate>
          <div class="quote__fields">
            <label class="quote__wide"><span class="mono">What are you booking?</span>
              <select id="q-type" required>
                <option value="">Choose one</option>
$options
              </select>
            </label>
            <label><span class="mono">Sport</span>
              <input type="text" id="q-sport" list="q-sports" placeholder="Football, soccer…">
            </label>
            <datalist id="q-sports">
              <option value="Football"></option><option value="Soccer"></option>
              <option value="Tennis"></option><option value="Volleyball"></option>
              <option value="Basketball"></option><option value="Hockey"></option>
              <option value="Lacrosse"></option><option value="Baseball"></option>
              <option value="Softball"></option><option value="Track and field"></option>
            </datalist>
            <label><span class="mono">School or team</span>
              <input type="text" id="q-team" placeholder="e.g. Country Day varsity">
            </label>
            <label><span class="mono">Number of athletes</span>
              <input type="number" id="q-count" min="1" inputmode="numeric" placeholder="1">
            </label>
            <label><span class="mono">Date</span>
              <input type="text" id="q-date" placeholder="e.g. Fri Oct 17, or flexible">
            </label>
            <label class="quote__wide"><span class="mono">Location</span>
              <input type="text" id="q-where" placeholder="Field, gym or city">
            </label>
            <label class="quote__wide"><span class="mono">Tell me about it</span>
              <textarea id="q-details" rows="4" placeholder="What you'd like photographed, for how long, and anything else I should know"></textarea>
            </label>
            <label><span class="mono">Your name</span>
              <input type="text" id="q-name" autocomplete="name" required>
            </label>
            <label><span class="mono">Email</span>
              <input type="email" id="q-email" autocomplete="email" required>
            </label>
            <label class="quote__wide"><span class="mono">Phone (optional)</span>
              <input type="tel" id="q-phone" autocomplete="tel">
            </label>
          </div>
          <button class="quote__send" type="submit">$button</button>
          <p class="quote__status mono" id="q-status" role="status"></p>
          <div class="quote__done">
            <span class="checkout__tick"><svg viewBox="0 0 52 52" aria-hidden="true"><circle class="tick-ring" cx="26" cy="26" r="23" fill="none"/><path class="tick-mark" fill="none" d="M14 27l8 8 16-17"/></svg></span>
            <h3>Sent</h3>
            <p>$thanks</p>
            <button class="quote__again" type="button">Send another request</button>
          </div>
        </form>""")


def r_quote(s, ctx):
    options = "\n".join("                <option>%s</option>" % esc(o) for o in s["options"])
    points = "".join("<li>%s</li>" % rich(p) for p in s["points"])
    form = QUOTE_FORM.substitute(options=options, button=esc(s["button"] or "Get a quote"),
                                 thanks=esc(s["thanks"]))
    return ('<section class="quote reveal" id="quote" data-section="quote">%s'
            '<div class="quote__grid"><div class="quote__intro">'
            '<h2 class="section__title">%s</h2><p>%s</p><ul class="quote__list">%s</ul></div>%s'
            '</div></section>'
            % (head_html(s["label"], ctx["num"], s["aside"]), esc(s["heading"]), rich(s["intro"]),
               points, form))


def review_card(r):
    stars = "".join('<span class="star%s">★</span>' % (" is-on" if i <= r["rating"] else "")
                    for i in range(1, 6))
    who = esc(r["name"]) + (" · " + esc(r["role"]) if r["role"] else "")
    return ('<article class="review"><span class="stars" aria-label="%d out of 5">%s</span>'
            '<p>%s</p><footer class="mono">%s</footer></article>'
            % (r["rating"], stars, esc(r["text"]), who))


def r_reviews(s, ctx):
    """Reviews slide past in rows above and below the Leave a review form.
    The ones written here are in the page for search engines; js/main.js
    adds the ones visitors post and sets the rows moving."""
    items = s["items"]
    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    return ('<section class="reviews reveal" id="reviews" data-section="reviews">%s'
            '<div class="reviews__ring%s">'
            '<div class="reviews__row" data-row="0"><div class="reviews__track">%s</div></div>'
            '<div class="reviews__center" data-reviews></div>'
            '<div class="reviews__row" data-row="1" hidden><div class="reviews__track"></div></div>'
            '</div><script type="application/json" data-reviews-json>%s</script></section>'
            % (head_html(s["label"], ctx["num"], "Be the first", ' data-reviews-score'),
               "" if items else " is-empty", "".join(review_card(r) for r in items), data))


def r_faq(s, ctx):
    items = "".join('<details class="faq__item"><summary>%s</summary><p>%s</p></details>'
                    % (esc(i["q"]), rich(i["a"])) for i in s["items"])
    return ('<section class="faq reveal" id="faq" data-section="faq">%s'
            '<h2 class="section__title">%s</h2><div class="faq__list">%s</div></section>'
            % (head_html(s["label"], ctx["num"], s["aside"]), esc(s["heading"]), items))


def r_contact(s, ctx):
    cards = ""
    if s["email"].strip():
        cards += ('<a class="contact__card" href="mailto:%s"><span class="mono">Email</span>'
                  '<strong>%s</strong><span class="contact__go">Send a message →</span></a>'
                  % (esc(s["email"]), esc(s["email"])))
    ig = s["instagram"].strip().lstrip("@")
    if ig:
        cards += ('<a class="contact__card" href="https://www.instagram.com/%s" target="_blank" '
                  'rel="noopener noreferrer"><span class="mono">Instagram</span><strong>@%s</strong>'
                  '<span class="contact__go">See the feed →</span></a>' % (esc(ig), esc(ig)))
    return ('<section class="contact reveal" id="contact" data-section="contact">%s'
            '<div class="contact__grid">%s</div></section>'
            % (head_html(s["label"], ctx["num"], s["aside"]), cards))


def r_cta(s, ctx):
    return ('<a class="cta reveal" href="%s" data-section="cta"><span class="cta__big">%s</span>'
            '<span class="mono"><span data-photo-count>%d photographs</span>, filterable →</span></a>'
            % (esc(href(s["link"])), esc(s["text"]), ctx["count"]))


RENDER = {"intro": r_intro, "hero": r_hero, "marquee": r_marquee, "about": r_about,
          "work": r_work, "services": r_services, "quote": r_quote, "reviews": r_reviews,
          "faq": r_faq, "contact": r_contact, "cta": r_cta}


PAGE = Template("""<!DOCTYPE html>
<!-- GENERATED FILE - do not edit by hand.
     Source: data/home.json, edited in Studio's Home tab.
     Rebuild: python3 studio.py --regen -->
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>$title</title>
  <meta name="description" content="$description">
  <link rel="canonical" href="https://garrettphoto.store/">

  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Garrett Erickson Photography">
  <meta property="og:title" content="$title">
  <meta property="og:description" content="$description">
  <meta property="og:url" content="https://garrettphoto.store/">
  <meta property="og:image" content="https://garrettphoto.store/$share">
  <meta property="og:image:alt" content="$share_alt">
  <meta property="og:locale" content="en_US">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="geo.region" content="US-MI">
  <meta name="geo.placename" content="Metro Detroit, Michigan">

  <script type="application/ld+json">
$ld
  </script>

  <link rel="stylesheet" href="css/style.css">
  <link rel="stylesheet" href="css/theme.css">
  <script src="js/pixel.js"></script>
</head>
<body data-page="about">

  <nav class="nav">
    <a class="nav__name" href="index.html">Garrett Erickson</a>
    <div class="nav__links">
      <a href="index.html" aria-current="page">Home</a>
      <a href="portfolio.html">Portfolio</a>
    </div>
  </nav>

  <main id="about-root">
$sections
  </main>

  <footer class="footer">
    <span class="mono">© 2026 Garrett Erickson · Michigan Sports Photographer</span>
    <a class="mono" href="mailto:garrettoscarerickson@gmail.com">garrettoscarerickson@gmail.com</a>
    <span class="mono">Based in Metro Detroit, Michigan</span>
  </footer>

  <script>window.SITE = $site;</script>
  <script src="js/reviews-store.js"></script>
  <script src="js/mailer.js"></script>
  <script src="js/photos.js"></script>
  <script src="js/reviews.js"></script>
  <script src="js/main.js"></script>
</body>
</html>
""")


def structured_data(home, share):
    contact = next((s for s in home["sections"] if s["type"] == "contact"), {})
    email = contact.get("email", "")
    ig = (contact.get("instagram") or "").lstrip("@")
    same = ["https://www.instagram.com/" + ig] if ig else []
    business = {
        "@type": "ProfessionalService",
        "@id": "https://garrettphoto.store/#business",
        "name": "Garrett Erickson Photography",
        "alternateName": "Garrett Erickson — Michigan Sports Photographer",
        "description": home["seo"]["description"],
        "url": "https://garrettphoto.store/",
        "image": "https://garrettphoto.store/" + share,
        "address": {"@type": "PostalAddress", "addressRegion": "MI", "addressCountry": "US"},
        "areaServed": [{"@type": "State", "name": "Michigan"}] + [
            {"@type": "City", "name": c} for c in
            ("Detroit", "Birmingham", "Bloomfield Hills", "Beverly Hills", "Royal Oak",
             "Troy", "Southfield", "Grosse Pointe", "Dearborn")],
        "knowsAbout": ["Sports photography", "High school football photography",
                       "Soccer photography", "Tennis photography", "Volleyball photography",
                       "Team photos", "Athlete portraits", "Event photography"],
        "founder": {"@id": "https://garrettphoto.store/#garrett"},
        "sameAs": same,
    }
    if email:
        business["email"] = email
    graph = [business,
             {"@type": "Person", "@id": "https://garrettphoto.store/#garrett",
              "name": "Garrett Erickson", "jobTitle": "Sports Photographer",
              "url": "https://garrettphoto.store/", "sameAs": same},
             {"@type": "WebSite", "@id": "https://garrettphoto.store/#website",
              "url": "https://garrettphoto.store/",
              "name": "Garrett Erickson — Michigan Sports Photographer",
              "publisher": {"@id": "https://garrettphoto.store/#business"}}]
    text = json.dumps({"@context": "https://schema.org", "@graph": graph},
                      indent=2, ensure_ascii=False)
    # keep "</script>" in any text from closing the tag early
    return "\n".join("  " + line for line in text.replace("</", "<\\/").split("\n"))


def render(home, photos):
    by_src = {p["src"]: p for p in photos}
    parts, n = [], 0
    for s in home["sections"]:
        if not s.get("visible", True):
            continue
        num = ""
        if s["type"] in NUMBERED:
            n += 1
            num = "%02d" % n
        parts.append("    " + RENDER[s["type"]](s, {"num": num, "by_src": by_src,
                                                    "count": len(photos)}))
    share = home["seo"]["shareImage"] or "images/varsoc-02.jpg"
    contact = next((s for s in home["sections"] if s["type"] == "contact"), {})
    site = json.dumps({"email": contact.get("email", ""),
                       "instagram": (contact.get("instagram") or "").lstrip("@")}).replace("</", "<\\/")
    return PAGE.substitute(
        title=esc(home["seo"]["title"]), description=esc(home["seo"]["description"]),
        share=esc(share), share_alt=esc(alt_of(by_src.get(share)) or "Photograph by Garrett Erickson"),
        ld=structured_data(home, share), sections="\n\n".join(parts), site=site)


def theme_css(theme):
    r = int(theme["radius"])
    return (
        "/* GENERATED FILE - do not edit by hand.\n"
        "   Source: data/home.json (\"theme\"), edited in Studio's Home tab,\n"
        "   under Colors & style. Loaded after style.css on every page. */\n\n"
        ":root {\n"
        "  --bg: %s;\n  --bg-raise: %s;\n  --ink: %s;\n  --ink-dim: %s;\n  --accent: %s;\n"
        "  --r-sm: %dpx;\n  --r-md: %dpx;\n  --r-lg: %dpx;\n"
        "  --font-display: %s;\n  --font-sans: %s;\n  --font-ui: %s;\n"
        "}\n" % (theme["bg"], theme["bgRaise"], theme["ink"], theme["inkDim"], theme["accent"],
                 round(r * 10 / 18), r, round(r * 26 / 18),
                 FONTS[theme["fontDisplay"]], FONTS[theme["fontBody"]], FONTS[theme["fontUi"]]))


def build(photos, home=None):
    """Write index.html and css/theme.css. Returns the cleaned home."""
    home = clean(home if home is not None else load(photos), photos)
    save(home)
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(render(home, photos))
    with open(THEME_CSS, "w", encoding="utf-8") as f:
        f.write(theme_css(home["theme"]))
    return home


if __name__ == "__main__":
    with open(os.path.join(ROOT, "data", "photos.json"), encoding="utf-8") as f:
        build(json.load(f))
    print("index.html + css/theme.css rebuilt from data/home.json "
          "(run python3 studio.py --regen to fingerprint the links)")
