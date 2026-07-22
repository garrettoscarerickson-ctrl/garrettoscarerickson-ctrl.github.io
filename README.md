# Garrett Erickson — Photographs

Black, architectural portfolio. Three pages:

- **index.html** — parallax feature panels alternating with gallery strips
- **archive.html** — every photo, filterable, with a lightbox
- **sports.html** — shows "coming soon" until any photo has the `sports`
  tag, then it turns into a real gallery automatically

No build step, no dependencies. Plain HTML/CSS/JS.

## Adding photos — use Studio

```sh
cd ~/photography-portfolio
python3 studio.py
```

- Site: http://localhost:4173
- **Studio: http://localhost:4173/studio**

Drag photos into Studio (any size — it resizes them), give each a title
and tags, hit **Add to site**. Studio files the image into `images/`,
updates `data/photos.json`, regenerates `js/photos.js`, and every page
sorts itself:

- new tags become filter buttons on the Archive page, with live counts
- a photo tagged `sports` makes the Sports page a real gallery
- "Feature: hero" swaps the big home-page opener (the old hero returns
  to the gallery); "panel" adds a full-screen parallax section
- Remove keeps the image file in `images/_removed/` just in case

Studio is local-only (binds 127.0.0.1) and is never part of the
public site.

Prefer hand-editing? The source of truth is `data/photos.json` — edit
it, then run `python3 studio.py --regen`. Don't edit `js/photos.js`;
it's generated.

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

**Single-file share build:** `python3 build_artifact.py` bundles the
whole site (images inlined) into `dist/artifact.html` — one file you
can share as a Claude Artifact or send to anyone.

## Running just the site

Any static server works:

```sh
python3 -m http.server 4173
```
