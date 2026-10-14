# Garrett Erickson — Michigan Sports Photographer

Black, architectural portfolio for garrettphoto.store. Two pages:

- **index.html** (Home) — who I am, what I shoot, the **Get a quote**
  form, reviews, questions and contact. There are no set prices: the
  quote form emails Garrett and he replies with a price. Built from
  `data/home.json`, which Studio's Home page tab edits (see below).
- **portfolio.html** (Portfolio) — every photo, sports first, filterable,
  with a lightbox. `portfolio.html?tag=football` opens filtered to one tag.

`store.html`, `sports.html` and `archive.html` only redirect to the
portfolio, so old links and printed QR codes still land somewhere.
`account.html` is a leftover download page for past buyers — see SETUP.md.

## Search (SEO)

- Each page has its own title, description, canonical link and share
  image; the Home page carries structured data describing the business
  (`application/ld+json` in `index.html`).
- `sitemap.xml` and `robots.txt` sit at the root. Add any new page to the
  sitemap.
- Things that matter as much as the site itself, and only you can do:
  set up a **Google Business Profile** (sports photographer, service
  area Metro Detroit), add the site in **Google Search Console** and
  submit `https://garrettphoto.store/sitemap.xml`, put the link in your
  Instagram bio, and ask schools and teams you shoot for to link to it.

No build step, no dependencies. Plain HTML/CSS/JS.

## Adding photos — use Studio

```sh
cd ~/photography-portfolio
python3 studio.py
```

- Site: http://localhost:4173
- **Studio: http://localhost:4173/studio**

Drag photos into Studio (any size — it resizes them), give each a title
and tags, hit **Add to site**. Every upload goes to the **Portfolio** —
the home page's selected work stays curated and never changes when you
add photos. Studio files the image into `images/`, updates
`data/photos.json`, regenerates `js/photos.js`, and every page sorts
itself:

- new tags become filters on the Portfolio page, with live counts
- photos tagged `sports` lead the portfolio
- To put a photo on the home page, edit it in the **Library** section and
  set its **Placement** — "Home — gallery / parallax panel / hero". The
  hero is the big opening image; for a sports site, make it a sports
  photo.
- Remove keeps the image file in `images/_removed/` just in case

Studio is local-only (binds 127.0.0.1) and is never part of the
public site.

Prefer hand-editing? The source of truth is `data/photos.json` — edit
it, then run `python3 studio.py --regen`. Don't edit `js/photos.js`;
it's generated.

## Editing the home page — Studio's Home page tab

Open Studio (`python3 studio.py`, then http://localhost:4173/studio) and
click **Home page**. The real home page shows on the right; the left
lists every section from top to bottom.

- **Click anything in the preview** to edit it. Green dashed outlines
  are photo spots: click one to pick a different photo from the library
  (search by game, sport or title).
- **👁** shows or hides a section; **↑ ↓** move it.
- **Opening photo** takes several photos and fades between them.
- **About** can have a photo on the left; click the dashed "Add a photo"
  spot in the preview (it only shows in Studio while empty).
- **Reviews** has a list for praise people have actually given you (a
  parent's text, a coach's DM — ask first). Reviews circle the Leave a
  review form; four or more slide past in two rows. Approved reviews
  visitors post join them. Never add made-up reviews: it misleads
  clients and breaks the FTC's fake-review rule.
- **Colors, fonts & corners** changes the whole site;
  **Google title, description & share photo** is what search results
  and shared links show.
- In longer text, `**bold**` makes bold and `[words](link)` makes a link.
- Every change saves on your Mac straight away. Nothing goes online
  until **Publish to the web**; **Undo changes since last publish** puts
  the page back the way it is online.

Under the hood: `data/home.json` is the page, and `tools/home_page.py`
writes `index.html` and `css/theme.css` from it. Don't edit `index.html`
by hand — it is rebuilt from `data/home.json`.

## Putting it on the internet

**Permanent home (GitHub Pages, free):** one-time setup —

```sh
brew install gh
gh auth login
./deploy.sh
```

That creates a public repo and turns on GitHub Pages; the script prints
your URL (https://YOURNAME.github.io/photography-portfolio/). After
that, the **Publish to the web** button in Studio pushes updates live.

Every page links its css/ and js/ files with a fingerprint
(`js/main.js?v=3f9a1c2e`) so browsers can't mix a new page with old,
cached styles and script. Studio and `python3 studio.py --regen` update
the fingerprints; if you edit css/ or js/ by hand, run `--regen` before
pushing.

**Single-file share build:** `python3 build_artifact.py` bundles the
whole site (images inlined) into `dist/artifact.html` — one file you
can share as a Claude Artifact or send to anyone.

## Running just the site

Any static server works:

```sh
python3 -m http.server 4173
```
