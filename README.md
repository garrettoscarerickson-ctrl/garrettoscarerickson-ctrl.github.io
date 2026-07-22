# Garrett Erickson — Photographs

Black, architectural portfolio. Two pages:

- **index.html** — parallax feature panels alternating with gallery strips
- **archive.html** — every photo, filterable, with a lightbox
- **sports.html** — shows "coming soon" until any photo has the `sports`
  tag, then it turns into a real gallery automatically

No build step, no dependencies. Plain HTML/CSS/JS.

## Adding photos (the only workflow you need)

1. Export the JPG (~2000px on the long edge is plenty) into `images/`
2. Open `js/photos.js` and add an entry near the top:

```js
{
  src: "images/my-new-photo.jpg",
  title: "My New Photo",
  location: "Brooklyn, NYC",
  year: 2026,
  orientation: "landscape",   // or "portrait"
  tags: ["architecture", "night"],
  // feature: "panel"         // optional: promote to a home-page parallax panel
}
```

That's it. Everything downstream is generated:

- **New tags automatically become filter buttons** on the Archive page,
  with live counts. Use lowercase tags and reuse existing ones where they
  fit (`architecture`, `street`, `nature`, `wildlife`, `transit`, `skyline`)
  so filters stay meaningful.
- The archive count, year range, home-page gallery strips and lightbox
  ordering all update themselves.
- One photo has `feature: "hero"` (the big opening image). Move that flag
  to change the hero. Any photo with `feature: "panel"` becomes a
  full-screen parallax section on the home page — 2–4 panels feels right.

## Running locally

Any static server works:

```sh
cd ~/photography-portfolio
python3 -m http.server 4173
# open http://localhost:4173
```

## Deploying

The folder is 100% static — drag it into Netlify/Vercel, or push to
GitHub and enable Pages.
