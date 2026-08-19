# CLAUDE.md — Americas Best Home Solutions

Static, no-build marketing site for owner-financed homes. Published at
**getownerfinancedhomes.com** (see `CNAME`) via GitHub Pages, served straight from
the repo root — no bundler, no CI, no `package.json`. Whatever is committed on the
default branch is what's live.

## The one thing to know first

`homes.js` is **auto-generated** by `scripts/refresh_listings.py`, and **that script
is not in this repo** — it lives on the owner's local machine (Mac mini) alongside the
master listing spreadsheet. Every commit titled "Refresh listings from master" is that
script's output.

Consequences:

- **Never hand-edit `homes.js` to change listing data.** It will be overwritten on the
  next refresh. Fix the master list / the script instead.
- The same goes for the 150 per-listing `*.html` files and `sitemap.xml` — the generator
  writes those too.
- Editing the *page template* (layout, styling, copy that applies to every home) means
  editing the generator's template, otherwise the change is wiped on the next refresh.
  If you only have the repo, say so rather than silently patching one page.
- A refresh commonly produces a large `sitemap.xml` diff (~150 lines moved) because the
  generator re-emits listings in master-list order. That churn is expected, not a bug.

## Layout

| Path | What it is |
| --- | --- |
| `homes.js` | **Generated.** `CONTACT` object + `HOMES` array (150 entries). The single source of listing data at runtime. |
| `<id>.html` | **Generated.** One static page per home (150 of them), e.g. `cahokia-il-107-judith.html`. |
| `home.html` | The shared property-page template, driven by `?home=<id>`. Duplicates the per-home pages, so it's `Disallow`ed in `robots.txt`. |
| `index.html` | Browse-all page. Builds cards and the state/city/price filters from `HOMES`. |
| `about.html`, `contact.html`, `how-it-works.html`, `privacy-policy.html`, `messaging-terms.html`, `404.html` | Hand-maintained static pages. |
| `pages.css` | Shared styles — used **only** by about / contact / privacy-policy / messaging-terms. Listing pages and `index.html` carry their own inline `<style>`. |
| `consent.js` | SMS/A2P 10DLC consent evidence capture for lead forms. |
| `features.json` | Generator **input**, not read by the site. 505 SHA1-keyed feature records; the generator bakes the relevant ones into each home's `features:` object. |
| `sitemap.xml` | **Generated.** 6 static URLs + 150 listings. |
| `images/` | Photos, ~3,500 files. See conventions below. |
| `email-signature/signature.html` | Standalone HTML email signature. |

## How a listing page works

Each generated page hardcodes its own ID, then reuses the shared template logic:

```html
<script>window.__HOME_ID__="cahokia-il-107-judith";</script>
<script src="homes.js"></script>
```

```js
const wantedId = window.__HOME_ID__ || new URLSearchParams(location.search).get("home");
```

So the page finds its record in the `HOMES` array at runtime. `home.html` omits
`__HOME_ID__` and falls back to the query string.

### Home record shape

Present on all 150: `id`, `address`, `city`, `state`, `beds`, `baths`, `sqft`,
`status`, `monthlyPayment`, `moveIn`, `lockedPrice`, `termText`, `heroPhoto`, `photos`.
Optional: `zip` (148), `description` (139), `features` (71).

Notes on the data as it actually is — the generator passes values through from the
master list, so don't assume clean types:

- `sqft` and `zip` are **strings**, often with a trailing `.0` (`"1453.0"`, `"62526.0"`).
  Rendering code does `Number(C.sqft).toLocaleString()`.
- `status` is `"Available"` (149) or `"Pending"` (1).
- `heroPhoto` is `""` on every current record; the hero image is resolved by convention.
- `id` is `<city>-<state>-<housenumber>-<street>`, lowercased, with spaces squashed out of
  the city (`eaststlouis-il-5617-warren`, `cahokiaheights-il-907-frontenac`). It is the
  join key for the page filename, the sitemap URL, and every image filename.

### Hero image fallback chain

`<id>.html` resolves the hero photo in three steps (`witt-il-529-2nd.html:431`):

1. `heroPhoto` if set, else `images/<id>.jpg` — the real seller photo.
2. On error, `images/sv/<id>.jpg` — a Google Street View curb shot, which shows a
   "Street View" badge when used. 21 homes currently have one.
3. On error again, a branded navy card with the city name. Never a broken image.

## Image conventions

- **Main/hero photo:** `images/<id>.jpg`
- **Gallery photos:** `images/<id>-1.jpg`, `-2.jpg`, … listed explicitly in the home's
  `photos` array. Counts vary widely — some homes have 50+.
- **Street View fallback:** `images/sv/<id>.jpg`
- **Brand assets:** `images/brand/` (logo mark and lockup PNGs)
- **Shared:** `images/_share-default.jpg` (OG fallback), `images/_placeholder-home.svg`

`images/README.md` is written for the non-technical owner dropping photos in by hand.
It's slightly stale — it says "up to four" gallery photos, but the generator emits as
many as exist. Trust the `photos` array over the README.

There are ~175 `images/<id>.jpg` files against 150 live homes; the extras are leftovers
from delisted properties. Harmless, but don't treat the images folder as a listing index.

## Contact and lead capture

All contact details are centralized in the `CONTACT` object at the top of `homes.js` —
phone, Formspree form ID, and a Make.com webhook. Every page reads from it, so a phone
number or form endpoint change belongs there (and therefore in the generator, not here).

`consent.js` attaches A2P 10DLC consent evidence to each lead submission: the verbatim
consent wording shown, a version string, ISO timestamp, page URL, and submitter IP
(via ipify, disclosed in the privacy policy).

**When the checkbox wording changes, bump `CONSENT_TEXT_VERSION` and `CONSENT_TEXT`
together.** Old records intentionally keep their old version string — that's the whole
point of the mechanism, so it can be proven later what a given person agreed to.

## Working on this repo

- No build, no tests, no lint. Verify by opening the HTML in a browser.
- Because pages load `homes.js` with a plain `<script src>`, `file://` works for the
  listing pages. If something behaves oddly, serve it: `python3 -m http.server 8000`.
- Safe to hand-edit: the static pages, `pages.css`, `consent.js`, `robots.txt`,
  `images/`, `email-signature/`.
- Regenerated, so hand edits are temporary: `homes.js`, `<id>.html`, `sitemap.xml`,
  and `features.json`.
- Changing something that must apply to all 150 listing pages is a generator change,
  not 150 edits.
