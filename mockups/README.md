# Layout mockups (for approval)

Static HTML/CSS only. These pages are **not** the live site. They are `noindex`, and nothing in the public nav links here. Do not merge this into the live pages until Joe approves the layout and the generators are updated.

Open `search.html`, `listing.html`, and `account.html` (serve the repo root so photos in `../images/` load).

The search uses a sample of **real** Metro East listings. The listing screen is **107 Judith Ln, Cahokia**. The map is a schematic. **Book a Tour** is the only call to action. It leaves this page for the scheduler the live site already uses:

`https://owner.getownerfinancedhomes.com/book?home=<id>&lang=en`

(Spanish: `lang=es`.) That flow is not redrawn here. Save (the heart) stays. There is no Apply button.

## Where the words come from

Buyer-facing sentences are copied from the live pages. Nothing below is a new mission draft.

| On the mockup | Source |
| --- | --- |
| Header and footer name | Live header: **Americas Best Home Solutions**. Domain **getownerfinancedhomes.com** is already on the About page and the footer. |
| “Who we are” | `about.html` lead (Spanish: `nosotros.html`, “Quiénes somos”). |
| “How we got here” | `about.html`, same heading (Spanish: `nosotros.html`, “Cómo llegamos aquí”). |
| “You're buying — not renting” and the four benefit lines | `how-it-works.html`, “Why people choose this” (Spanish: `como-funciona.html`). |
| “Your past doesn't have to decide your future…” | Home-page hero on `index.html`. |
| “When you rent, the money is gone…” | FAQ answer, “Is this the same as renting?” |
| FAQ questions and answers | `how-it-works.html`, “Straight answers” (Spanish: `como-funciona.html`, same questions). |
| Tour / photo ID line | Listing template: tours are in person; photo ID before a showing. |
| Judith facts (beds, payment, plumbing note) | That home’s record in `homes.js`. |
| “Why buy instead of rent” | Section label Joe asked for. The lines under it are the existing benefit headings, not new claims. |
| Button label “Book a Tour” | Joe’s label. The live button says “Schedule a tour” and already points at the same scheduler URL. |

## What this layout is

- **Search:** city or ZIP code, monthly and down-payment ranges (min and max), beds, baths, and Near me (browser location, then nearest first). Mobile is the list, with a Map / List toggle. “Get alerts for this search” opens the saved search on the account page. Under the results: who we are, why buy instead of rent, and the FAQ.
- **New badge:** sample only on 107 Judith Ln. `homes.js` has no per-home listing date. Keys on a home are address, beds, baths, sqft, monthlyPayment, moveIn, and the rest listed in that file — nothing like `listedOn`. The comment at the top of `homes.js` (“master published 2026-10-27”) is the whole refresh, not a date for one home. The generator would need a new date field before this badge can be real. Until then the badge is layout only.
- **Alerts:** `ALERTS_ENABLED` in `mockup.js` is `false`. The account switch stays off and this page does not email or text. When Joe turns that flag on, the messaging bot sends — not the website.
- **Card:** photo, monthly payment, down payment, beds / baths / sqft, city, heart.
- **Listing:** gallery first, monthly payment and down payment, Save and Book a Tour, a short version of the benefits, facts, three steps from How it works, map, and a short FAQ.
- **Account:** saved homes, Book a Tour for each one, and saved searches with alerts off.
- **EN / ES:** ES links to the matching page on casasconfinanciamiento.com. The account page has no Spanish twin yet, so its ES link goes to the Spanish home page.

Pins show the monthly payment, same as today.

## What would change in the generator

`homes.js`, each `<id>.html`, and the browse page are written by `scripts/refresh_listings.py` on the owner’s Mac (not in this repo). Hand-editing those files will be wiped on the next refresh.

After approval, change the **templates** in that script (and the shared `home.html` template it emits):

1. **Browse template** — this shell: full company name and domain, search, filters, cards, map, mobile Map / List toggle, then the company block, benefit row, and FAQ. Keep reading `HOMES`. Keep `homes-map.js` for the real map.
2. **Card partial** — photo, `monthlyPayment`, down payment from `moveIn`, beds / baths / sqft, city, heart from `homes-cart.js`.
3. **Listing template** — gallery, payment box, Save, and Book a Tour only (same `book?home=` URL). Short benefit lines, facts, the existing three steps, map, collapsed FAQ. Do not add an Apply action.
4. **Wiring that stays** — `homes-cart.js` (save, compare, language), `consent.js` on any form that still exists elsewhere. Account can be a hand-maintained page, like `next-steps.html`.

## Spanish site

`build_casas.py` should emit this same layout. Reuse the Spanish pages, do not translate the English mockup from scratch:

- Company and “how we got here”: `nosotros.html`
- Benefits and FAQ: `como-funciona.html`
- Tour link: `lang=es`
- `homes-cart.js`, `homes-map.js`, and `sold-cards.js` already follow `<html lang>`

## Screenshots

| Screen | Desktop | Mobile |
| --- | --- | --- |
| Search | `screenshots/search-desktop.png` | `screenshots/search-mobile.png` |
| Search, map open | — | `screenshots/search-mobile-map.png` |
| Listing | `screenshots/listing-desktop.png` | `screenshots/listing-mobile.png` |
| Account | `screenshots/account-desktop.png` | `screenshots/account-mobile.png` |
