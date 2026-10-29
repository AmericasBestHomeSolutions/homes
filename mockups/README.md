# Layout mockups (for approval)

Static HTML/CSS only. These pages are **not** the live site. They are `noindex`, and nothing in the public nav links here. Do not merge this into the live pages until Joe approves the layout and the generators are updated.

Open `search.html`, `listing.html`, and `account.html` (serve the repo root so photos in `../images/` load).

The search uses a sample of **real** Metro East listings (photos, monthly payment, down payment / move-in, beds, baths, sqft, city). The listing screen is **107 Judith Ln, Cahokia**. The map is a schematic so the mockup does not depend on map tiles. A tour row marked “Sample” is layout only, not a booking. The apply form does not submit.

## What this layout is

Buyers already know a big city/ZIP search, filters, and a list beside a map. This keeps that shape and strips the rest.

- **Search:** city or ZIP bar, filters for monthly payment, price, beds, and baths. Desktop is list + map. Mobile is the list, with a Map / List toggle.
- **Card:** photo, monthly payment, down payment, beds / baths / sqft, city, heart to save.
- **Listing:** photo gallery first, then a box with monthly payment and down payment, and three large actions: Save, Book a Tour, Apply. Short facts, three steps, a map.
- **Account:** saved homes (heart), compare (up to 4), tour requests (up to 5), and the application. Header links on every screen.

Pins show the monthly payment, same as today.

## What would change in the generator

`homes.js`, each `<id>.html`, and the browse page are written by `scripts/refresh_listings.py` on the owner’s Mac (not in this repo). Hand-editing those files will be wiped on the next “Refresh listings from master.”

After approval, change the **templates** in that script (and the shared `home.html` template it emits):

1. **Browse / home template** — replace the long marketing hero and card grid with this shell: search bar, filter row, scrolling cards, map pane, and the mobile Map / List toggle. Keep reading `HOMES` for the cards and filters. Keep `homes-map.js` for the real map (Leaflet). The schematic here is only for the mockup.
2. **Card partial** — photo, `monthlyPayment`, down payment from `moveIn`, beds / baths / sqft, city, and the existing heart from `homes-cart.js`.
3. **Listing template** — gallery first, payment box (monthly + down payment), buttons Save / Book a Tour / Apply, a short fact row, three steps, then the map. Drop the long essay blocks from the default listing. How it works stays on its own page.
4. **Wiring that stays**
   - Save, compare (up to 4), and tour list (up to 5): `homes-cart.js` (hand-maintained, already language-aware).
   - Book a Tour: `https://owner.getownerfinancedhomes.com/book?home=<id>&lang=en` (or `es`).
   - Apply: the current lead form. Do not change consent wording without bumping `CONSENT_TEXT` and `CONSENT_TEXT_VERSION` in `consent.js`.
   - Account can be a new **hand-maintained** page (like `next-steps.html`), not a generated file. Today “My homes” is saved in the browser; this mockup puts that, plus tours and apply, under Account in the header.

Do not patch the generated listing HTML in this repo to ship the layout.

## Spanish site

`build_casas.py` in the casas repo should emit this **same layout**. Copy stays Spanish. `homes-cart.js`, `homes-map.js`, and `sold-cards.js` already follow `<html lang>` and are shared with casas — keep that, and pass `lang=es` on the tour link.

## Screenshots

| Screen | Desktop | Mobile |
| --- | --- | --- |
| Search (list + map; mobile list with Map toggle) | `screenshots/search-desktop.png` | `screenshots/search-mobile.png` |
| Search, map open | — | `screenshots/search-mobile-map.png` |
| Listing | `screenshots/listing-desktop.png` | `screenshots/listing-mobile.png` |
| Account (saved, tours, apply) | `screenshots/account-desktop.png` | `screenshots/account-mobile.png` |
