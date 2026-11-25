#!/usr/bin/env python3
"""Server-rendered SEO for listing pages, city pages, hreflang, and the sitemap.

portal_sync.py calls rebuild() at the end of every apply(), and
refresh_listings.py calls it after rewriting pages from home.html, so the next
sync reproduces the tags. The Spanish site (casas) runs the same file:

    python3 scripts/portal_sync.py --site . --lang es
    # and, after build_casas.py rewrites pages from home.html:
    python3 scripts/seo_pages.py --site . --lang es

build_casas.py should call seo_pages.rebuild(root, "es") after emit_pages, or
that layout pass leaves the new head on disk only until the next rebuild.

Offline from the current homes.js (no portal, no network):

    python3 scripts/seo_pages.py
    python3 scripts/seo_pages.py --check

City pages are written only for cities that have at least one home in HOMES.
Sold stubs (noindex, not in HOMES) are left alone and kept out of the sitemap.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote

# Keep these in step with scripts/portal_sync.py SITES.
DOMAINS = {
    "en": "https://getownerfinancedhomes.com",
    "es": "https://casasconfinanciamiento.com",
}
TERMS = {
    "en": "30-year owner financing (contract for deed)",
    "es": "Financiamiento del dueño a 30 años (contrato de compraventa)",
}
OTHER = {"en": "es", "es": "en"}
BRAND = "Americas Best Home Solutions"
CITY_MARK = "data-city-landing="
BLOCK_RE = re.compile(r"\n  \{\n    id: \"([^\"]+)\",[\s\S]*?\n  \},")

# filename, canonical path on this site, canonical path on the other site, priority, homepage OG
STATIC = {
    "en": [
        ("index.html", "/", "/", "1.0", True),
        ("how-it-works.html", "/how-it-works.html", "/como-funciona.html", "0.8", False),
        ("about.html", "/about", "/nosotros", "0.7", False),
        ("contact.html", "/contact", "/contacto", "0.7", False),
        ("privacy-policy.html", "/privacy-policy", "/politica-de-privacidad", "0.4", False),
        ("messaging-terms.html", "/messaging-terms", "/terminos-de-mensajes", "0.4", False),
    ],
    "es": [
        ("index.html", "/", "/", "1.0", True),
        ("como-funciona.html", "/como-funciona.html", "/how-it-works.html", "0.8", False),
        ("nosotros.html", "/nosotros", "/about", "0.7", False),
        ("contacto.html", "/contacto", "/contact", "0.7", False),
        ("politica-de-privacidad.html", "/politica-de-privacidad", "/privacy-policy", "0.4", False),
        ("terminos-de-mensajes.html", "/terminos-de-mensajes", "/messaging-terms", "0.4", False),
    ],
}

FACTS_CSS = """
.headline{font-size:clamp(24px,5.2vw,34px);line-height:1.15;letter-spacing:-.5px}
.seo-facts{font-size:17px;line-height:1.55;color:var(--ink,#16213a);margin:0 0 8px;max-width:52ch}
.seo-city{margin:0 0 12px}
.seo-city a{color:var(--pine,#15315e);font-weight:700}
""".strip()

PILL_CSS = """
.city-pills{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.city-pills a{display:inline-flex;align-items:center;gap:6px;background:#fff;border:1px solid var(--line,#e2e8f2);border-radius:999px;padding:8px 14px;font-weight:700;font-size:14.5px;color:var(--pine,#15315e);text-decoration:none}
.city-pills a:hover{border-color:var(--pine,#15315e);background:var(--honey-soft,#eaf1fb)}
.city-pills .n{font-weight:600;color:var(--ink-soft,#5b6577)}
body.page-search #cities{margin:28px 0 0;padding:14px 16px 28px;background:#fff;border-top:1px solid var(--line,#e2e8f2);border-bottom:1px solid var(--line,#e2e8f2)}
body.page-search #cities .sec-title{font-size:clamp(22px,3vw,28px)}
body.page-search #cities .sec-sub{margin:4px 0 0;max-width:62ch}
""".strip()

RESTORE_JS = """<script id="seo-restore">
document.addEventListener("DOMContentLoaded", function () {
  var root = document.documentElement;
  if (root.getAttribute("data-seo") !== "1") return;
  var title = root.getAttribute("data-seo-title");
  if (title) document.title = title;
  var h1 = root.getAttribute("data-seo-h1");
  var headline = document.getElementById("headline");
  if (headline && h1) headline.textContent = h1;
  [["dMonthly", "data-seo-monthly"], ["dMoveIn", "data-seo-down"], ["dPrice", "data-seo-price"]].forEach(function (pair) {
    if (!root.hasAttribute(pair[1])) return;
    var node = document.getElementById(pair[0]);
    if (node) node.textContent = root.getAttribute(pair[1]);
  });
  var raw = document.getElementById("seo-terms");
  var box = document.getElementById("termsList");
  if (!raw || !box) return;
  var rows = JSON.parse(raw.textContent);
  var esc = function (s) { return String(s).replace(/[&<>]/g, function (c) { return {"&":"&amp;","<":"&lt;",">":"&gt;"}[c]; }); };
  box.innerHTML = rows.map(function (r) {
    return '<div class="term-row' + (r.big ? " big" : "") + '"><span class="k">' + esc(r.k) + '</span><span class="v">' + esc(r.v) + '</span></div>';
  }).join("");
});
</script>
"""


def city_slug(city: str) -> str:
    city = (city or "").lower().replace("saint ", "st").replace("st. ", "st")
    return re.sub(r"[^a-z0-9]", "", city)


def city_file(city: str, state: str) -> str:
    return f"{city_slug(city)}-{(state or '').strip().lower()}.html"


def num(value):
    text = str(value if value is not None else "").replace(",", "").replace("$", "").strip()
    if not text or text.lower() in {"none", "null"}:
        return None
    try:
        f = float(text)
    except ValueError:
        return None
    if f == 0:
        return None
    return int(f) if f == int(f) else f


def money(value) -> str:
    n = num(value)
    if n is None:
        return ""
    if isinstance(n, float) and n == int(n):
        n = int(n)
    if isinstance(n, float):
        return f"${n:,.2f}"
    return f"${n:,}"


def clean_zip(value) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text if re.fullmatch(r"\d{5}(?:-\d{4})?", text) else ""


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def json_ld(obj) -> str:
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return raw


def place(home: dict) -> str:
    city = (home.get("city") or "").strip()
    state = (home.get("state") or "").strip().upper()
    loc = ", ".join(p for p in (city, state) if p)
    addr = (home.get("address") or "").strip()
    return ", ".join(p for p in (addr, loc) if p)


def bed_bath(home: dict, lang: str) -> str:
    beds, baths = num(home.get("beds")), num(home.get("baths"))
    bits = []
    if beds:
        n = int(beds) if isinstance(beds, float) and beds == int(beds) else beds
        if lang == "es":
            bits.append(f"{n:g} recámara" if n == 1 else f"{n:g} recámaras")
        else:
            bits.append(f"{n:g} bed" if n == 1 else f"{n:g} beds")
    if baths:
        n = int(baths) if isinstance(baths, float) and baths == int(baths) else baths
        if lang == "es":
            bits.append(f"{n:g} baño" if n == 1 else f"{n:g} baños")
        else:
            bits.append(f"{n:g} bath" if n == 1 else f"{n:g} baths")
    return ", ".join(bits)


def sqft_of(home: dict):
    return num(home.get("sqft"))


def money_bits(home: dict, lang: str) -> list[str]:
    price, down, monthly = money(home.get("lockedPrice")), money(home.get("moveIn")), money(home.get("monthlyPayment"))
    bits = []
    if price:
        bits.append(price)
    if down:
        bits.append(f"{down} de enganche" if lang == "es" else f"{down} down")
    if monthly:
        bits.append(f"{monthly}/mes" if lang == "es" else f"{monthly}/mo")
    return bits


def page_title(home: dict, lang: str) -> str:
    bits = money_bits(home, lang)
    brand = "Financiamiento del dueño" if lang == "es" else "Owner Financed"
    tail = (" — " + " · ".join(bits)) if bits else ""
    title = f"{place(home)}{tail} | {brand}"
    if home.get("_seo_suffix"):
        title += f" ({home['_seo_suffix']})"
    return title


def page_h1(home: dict, lang: str) -> str:
    bits = money_bits(home, lang)
    tail = (" — " + ", ".join(bits)) if bits else ""
    return f"{place(home)}{tail}"


def facts_text(home: dict, lang: str) -> str:
    where = place(home)
    price, down, monthly = money(home.get("lockedPrice")), money(home.get("moveIn")), money(home.get("monthlyPayment"))
    size, sq = bed_bath(home, lang), sqft_of(home)
    pending = str(home.get("status") or "").strip().lower() == "pending"
    if lang == "es":
        parts = [f"Casa con financiamiento del dueño en {where}."]
        if price:
            parts.append(f"Precio de compra {price}.")
        if down:
            parts.append(f"Enganche {down}.")
        if monthly:
            parts.append(f"Pago mensual {monthly}.")
        if size:
            parts.append(size + ".")
        if sq:
            parts.append(f"{sq:,} pies cuadrados.")
        if pending:
            parts.append("Esta casa está pendiente.")
        return " ".join(parts)
    parts = [f"Owner-financed home at {where}."]
    if price:
        parts.append(f"Purchase price {price}.")
    if down:
        parts.append(f"Down payment {down}.")
    if monthly:
        parts.append(f"Monthly payment {monthly}.")
    if size:
        parts.append(size + ".")
    if sq:
        parts.append(f"{sq:,} square feet.")
    if pending:
        parts.append("This home is pending.")
    return " ".join(parts)


def page_description(home: dict, lang: str) -> str:
    return facts_text(home, lang)


# Sentences that state a term, a rate, taxes, or insurance are not shown.
# The written agreement is where those points are confirmed.
_SENSITIVE_COPY = re.compile(
    r"30\s*-?\s*years?|30\s*años|treinta\s+años|fixed[\s-]*price|precio\s+fijo|"
    r"(?:the\s+)?price\s+is\s+fixed|interest\s+rate|tasa\s+de\s+inter[eé]s|"
    r"property\s+tax(?:es)?|\btaxes\b|\bimpuestos?\b|\binsurance\b|\bseguro\b",
    re.IGNORECASE,
)


def scrub_public_copy(text: str) -> str:
    """Drop sentences that mention a loan term, interest, taxes, or insurance."""
    parts = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
    kept = [part.strip() for part in parts if part.strip() and not _SENSITIVE_COPY.search(part)]
    return re.sub(r"\s{2,}", " ", " ".join(kept)).strip()


def prose(home: dict) -> str:
    for key in ("copy", "description"):
        text = home.get(key)
        if isinstance(text, str) and text.strip():
            return scrub_public_copy(text)
    return ""


def organization(lang: str) -> dict:
    domain = DOMAINS[lang]
    return {
        "@type": "Organization",
        "@id": domain + "/#organization",
        "name": BRAND,
        "legalName": "Americas Best Home Solutions LLC",
        "url": domain + "/",
        "logo": domain + "/images/brand/logo-mark-480.png",
        "email": "admin@americasbesthomesolutions.com",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "30 N Gould St, Ste R",
            "addressLocality": "Sheridan",
            "addressRegion": "WY",
            "postalCode": "82801",
            "addressCountry": "US",
        },
    }


def hreflang_links(here: str, there: str) -> str:
    en = here if "getownerfinancedhomes.com" in here else there
    es = there if en == here else here
    # x-default is the English URL.
    pairs = (("en", en), ("es", es), ("x-default", en))
    return "\n".join(f'<link rel="alternate" hreflang="{code}" href="{esc(url)}"/>' for code, url in pairs)


def share_image(root: Path, home: dict, lang: str) -> str:
    domain = DOMAINS[lang]
    hero = str(home.get("heroPhoto") or "").strip()
    if hero:
        if hero.startswith("http://") or hero.startswith("https://"):
            return hero
        return domain + "/" + hero.lstrip("/")
    hid = home.get("id") or ""
    cover = root / "images" / f"{hid}.jpg"
    if hid and cover.is_file():
        return f"{domain}/images/{hid}.jpg"
    for rel in home.get("photos") or []:
        rel = str(rel).lstrip("/")
        if rel and (root / rel).is_file():
            return domain + "/" + rel
    return f"{domain}/images/_share-default.jpg"


def listing_graph(home: dict, lang: str, image: str) -> dict:
    domain = DOMAINS[lang]
    url = f"{domain}/{home['id']}.html"
    city, state = (home.get("city") or "").strip(), (home.get("state") or "").strip().upper()
    graph = [organization(lang)]
    listing = {
        "@type": "RealEstateListing",
        "@id": url + "#listing",
        "name": page_h1(home, lang),
        "url": url,
        "description": page_description(home, lang),
        "mainEntity": {"@id": url + "#home"},
    }
    if image:
        listing["image"] = image
    residence = {
        "@type": "House",
        "@id": url + "#home",
        "name": place(home),
        "address": {"@type": "PostalAddress", "addressCountry": "US"},
    }
    addr = residence["address"]
    if home.get("address"):
        addr["streetAddress"] = home["address"]
    if city:
        addr["addressLocality"] = city
    if state:
        addr["addressRegion"] = state
    zipc = clean_zip(home.get("zip"))
    if zipc:
        addr["postalCode"] = zipc
    beds, baths, sq = num(home.get("beds")), num(home.get("baths")), sqft_of(home)
    if beds:
        residence["numberOfBedrooms"] = beds
    if baths:
        residence["numberOfBathroomsTotal"] = baths
    if sq:
        residence["floorSize"] = {"@type": "QuantitativeValue", "value": sq, "unitCode": "FTK"}
    try:
        lat, lng = float(home["lat"]), float(home["lng"])
    except (KeyError, TypeError, ValueError):
        lat = lng = None
    if lat is not None and lng is not None:
        residence["geo"] = {"@type": "GeoCoordinates", "latitude": lat, "longitude": lng}
    price = num(home.get("lockedPrice"))
    if price is not None:
        pending = str(home.get("status") or "").strip().lower() == "pending"
        offer = {
            "@type": "Offer",
            "@id": url + "#offer",
            "url": url,
            "priceCurrency": "USD",
            "price": str(int(price) if isinstance(price, float) and price == int(price) else price),
            "availability": "https://schema.org/LimitedAvailability" if pending else "https://schema.org/InStock",
            "itemOffered": {"@id": url + "#home"},
            "seller": {"@id": domain + "/#organization"},
        }
        extra = []
        down, monthly = money(home.get("moveIn")), money(home.get("monthlyPayment"))
        term = (home.get("termText") or "").strip()
        if lang == "es":
            if down:
                extra.append(f"Enganche {down}")
        if monthly:
            extra.append(f"Pago mensual {monthly}")
        else:
            if down:
                extra.append(f"Down payment {down}")
            if monthly:
                extra.append(f"Monthly payment {monthly}")
        if extra:
            offer["description"] = ". ".join(extra)
        listing["offers"] = {"@id": url + "#offer"}
        graph.append(offer)
    crumbs = [
        {"@type": "ListItem", "position": 1, "name": "Casas" if lang == "es" else "Homes", "item": domain + "/"},
    ]
    if city and state:
        label = f"{city}, {state}"
        name = (f"Casas con financiamiento del dueño en {label}" if lang == "es"
                else f"Owner Financed Homes in {label}")
        crumbs.append({"@type": "ListItem", "position": 2, "name": name, "item": domain + "/" + city_file(city, state)})
    crumbs.append({"@type": "ListItem", "position": len(crumbs) + 1, "name": home.get("address") or place(home), "item": url})
    graph.extend([listing, residence, {
        "@type": "BreadcrumbList",
        "@id": url + "#breadcrumb",
        "itemListElement": crumbs,
    }])
    return {"@context": "https://schema.org", "@graph": graph}


def head_tags(home: dict, lang: str, root: Path) -> str:
    domain = DOMAINS[lang]
    other = DOMAINS[OTHER[lang]]
    url = f"{domain}/{home['id']}.html"
    image = share_image(root, home, lang)
    title, desc = page_title(home, lang), page_description(home, lang)
    locale = "es_US" if lang == "es" else "en_US"
    return "\n".join([
        f'<link rel="canonical" href="{esc(url)}"/>',
        hreflang_links(url, f"{other}/{home['id']}.html"),
        '<meta property="og:type" content="website"/>',
        f'<meta property="og:site_name" content="{BRAND}"/>',
        f'<meta property="og:locale" content="{locale}"/>',
        f'<meta property="og:title" content="{esc(title)}"/>',
        f'<meta property="og:description" content="{esc(desc)}"/>',
        f'<meta property="og:image" content="{esc(image)}"/>',
        f'<meta property="og:url" content="{esc(url)}"/>',
        '<meta name="twitter:card" content="summary_large_image"/>',
        f'<meta name="twitter:title" content="{esc(title)}"/>',
        f'<meta name="twitter:description" content="{esc(desc)}"/>',
        f'<meta name="twitter:image" content="{esc(image)}"/>',
        f'<script type="application/ld+json" id="seo-jsonld">{json_ld(listing_graph(home, lang, image))}</script>',
    ])


def term_rows(home: dict, lang: str) -> list[dict]:
    price, down, monthly = money(home.get("lockedPrice")), money(home.get("moveIn")), money(home.get("monthlyPayment"))
    size, sq = bed_bath(home, lang), sqft_of(home)
    home_bits = [size] if size else []
    if sq:
        home_bits.append(f"{sq:,} sqft" if lang == "en" else f"{sq:,} pies cuadrados")
    zipc = clean_zip(home.get("zip"))
    loc = place(home) + (f" {zipc}" if zipc else "")
    term = (home.get("termText") or "").strip()
    if lang == "es":
        rows = [
            ("Pago mensual", monthly, True),
            ("Enganche", down, False),
            ("Precio de compra", price, False),
            ("La casa", " · ".join(home_bits), False),
            ("Ubicación", loc, False),
        ]
    else:
        rows = [
            ("Your monthly payment", monthly, True),
            ("Down payment", down, False),
            ("Purchase price", price, False),
            ("The home", " · ".join(home_bits), False),
            ("Location", loc, False),
        ]
    return [{"k": k, "v": v, "big": big} for k, v, big in rows if v]


def _replace_once(page: str, pattern: str, repl: str, flags=0) -> str:
    new, n = re.subn(pattern, repl, page, count=1, flags=flags)
    return new if n else page


def _book_path(root: Path, home_id: str, lang: str) -> str:
    """Public /book/<slug> (or /agendar/) so the tour button works before homes.js loads."""
    directory = "agendar" if lang == "es" else "book"
    slug = home_id
    path = root / "data" / "book-links.json"
    if path.is_file():
        slugs = json.loads(path.read_text(encoding="utf-8")).get("slugs") or {}
        for short, hid in slugs.items():
            if hid == home_id:
                slug = short
                break
    return f"/{directory}/{slug}"


def write_listing(root: Path, home: dict, lang: str, template: str | None = None) -> str:
    """Fill home.html with this home's title, H1, facts, and tags. Returns the HTML."""
    template = template if template is not None else (root / "home.html").read_text(encoding="utf-8")
    title, h1, facts = page_title(home, lang), page_h1(home, lang), facts_text(home, lang)
    desc = page_description(home, lang)
    city, state = (home.get("city") or "").strip(), (home.get("state") or "").strip().upper()
    html_open = (f'<html lang="{lang}" data-seo="1"'
                 f' data-seo-title="{esc(title)}" data-seo-h1="{esc(h1)}"'
                 f' data-seo-monthly="{esc(money(home.get("monthlyPayment")))}"'
                 f' data-seo-down="{esc(money(home.get("moveIn")))}"'
                 f' data-seo-price="{esc(money(home.get("lockedPrice")))}"')
    page = _replace_once(template, r'<html lang="[^"]*"', lambda _m: html_open)
    page = _replace_once(page, r"<title>.*?</title>", lambda _m: f"<title>{esc(title)}</title>", re.S)
    page = _replace_once(page, r'<meta name="description" content="[^"]*"/>',
                         lambda _m: f'<meta name="description" content="{esc(desc)}"/>')
    page = re.sub(r'\n?<link rel="canonical"[\s\S]*?<meta name="twitter:image"[^>]*>', "", page, count=1)
    page = re.sub(r'\n?<link rel="alternate" hreflang="[^"]+" href="[^"]+"/>', "", page)
    page = re.sub(r'\n?<script type="application/ld\+json" id="seo-jsonld">.*?</script>', "", page, count=1, flags=re.S)
    tags = head_tags(home, lang, root)
    page = _replace_once(page, r'(<meta name="description" content="[^"]*"/>)',
                         lambda m: m.group(1) + "\n" + tags)
    other = DOMAINS[OTHER[lang]]
    counterpart = f"{other}/{home['id']}.html"
    page = _replace_once(page, r'(<a class="nav-es[^"]*" href=")[^"]*(")',
                         lambda m: m.group(1) + counterpart + m.group(2))
    if ".seo-facts{" not in page and "</style>" in page:
        page = page.replace("</style>", FACTS_CSS + "\n</style>", 1)
    page = re.sub(r'\n?<p class="seo-facts" id="seoFacts"[^>]*>.*?</p>', "", page, count=1, flags=re.S)
    page = re.sub(r'\n?<p class="seo-city" id="seoCity"[^>]*>.*?</p>', "", page, count=1, flags=re.S)
    city_html = ""
    if city and state:
        label = (f"Casas con financiamiento del dueño en {city}, {state}" if lang == "es"
                 else f"Owner financed homes in {city}, {state}")
        city_html = f'\n<p class="seo-city" id="seoCity"><a href="/{city_file(city, state)}">{esc(label)}</a></p>'
    block = (f'<h1 class="headline" id="headline">{esc(h1)}</h1>'
             f'\n<p class="seo-facts" id="seoFacts">{esc(facts)}</p>{city_html}')
    page = _replace_once(page, r'<h1 class="headline" id="headline">.*?</h1>', lambda _m: block, re.S)
    status = "Pendiente" if lang == "es" else "Pending"
    available = "Disponible" if lang == "es" else "Available"
    pending = str(home.get("status") or "").strip().lower() == "pending"
    label = status if pending else available
    if pending:
        page = page.replace('class="status-tag" id="statusTag"', 'class="status-tag pending" id="statusTag"', 1)
        page = page.replace('id="toursOpen"', 'id="toursOpen" hidden', 1)
        closed = "Visitas cerradas: ver casas parecidas" if lang == "es" else "Tours closed: see similar homes"
        page = page.replace(">Book a tour</a>", ">" + closed + "</a>")
        similar = "/" + "?q=" + html.escape(f"{city}, {state}", quote=True) + "#nearby" if city and state else "/#nearby"
        page = page.replace('id="ctaText" href="#"', f'id="ctaText" href="{similar}"', 1)
        page = page.replace('id="ctaText2" href="#"', f'id="ctaText2" href="{similar}"', 1)
        page = page.replace('id="stBtn" class="st-go" href="#"', f'id="stBtn" class="st-go" href="{similar}"', 1)
    else:
        href = _book_path(root, home["id"], lang)
        page = page.replace('id="ctaText" href="#"', f'id="ctaText" href="{href}"', 1)
        page = page.replace('id="ctaText2" href="#"', f'id="ctaText2" href="{href}"', 1)
        page = page.replace('id="stBtn" class="st-go" href="#"', f'id="stBtn" class="st-go" href="{href}"', 1)
    page = _replace_once(page, r'(id="statusTag"[^>]*>)[^<]*', lambda m: m.group(1) + label)
    page = _replace_once(page, r'(<div class="num" id="dMonthly">)[^<]*',
                         lambda m: m.group(1) + esc(money(home.get("monthlyPayment"))))
    page = _replace_once(page, r'(<div class="num" id="dMoveIn">)[^<]*',
                         lambda m: m.group(1) + esc(money(home.get("moveIn"))))
    page = _replace_once(page, r'(<div class="num" id="dPrice">)[^<]*',
                         lambda m: m.group(1) + esc(money(home.get("lockedPrice"))))
    # Address, beds, and the tour note are on the first screen. Bake them so
    # filling them in after load does not push the price row down.
    zipc = clean_zip(home.get("zip"))
    loc = ", ".join(p for p in (city, state) if p)
    if zipc:
        loc = (loc + " " + zipc).strip()
    addr_text = ", ".join(p for p in ((home.get("address") or "").strip(), loc) if p)
    if addr_text and 'id="propAddr"' in page:
        map_label = "Ver en el mapa" if lang == "es" else "View on map"
        addr_html = (esc(addr_text) + ' <a href="https://www.google.com/maps/search/?api=1&amp;query='
                     + esc(quote(addr_text)) + '" target="_blank" rel="noopener" '
                     'style="font-weight:500;font-size:14px;color:var(--go,#e23b3b);text-decoration:none;white-space:nowrap;margin-left:6px">'
                     + esc(map_label) + " &#8599;</a>")
        page = _replace_once(page, r'(<p class="prop-addr" id="propAddr"[^>]*>).*?</p>',
                             lambda m: m.group(1) + addr_html + "</p>", re.S)
    if 'id="propSpecs"' in page:
        size = bed_bath(home, lang)
        sq = sqft_of(home)
        parts = []
        if size:
            parts.append(f"<span>{esc(size)}</span>")
        if sq:
            unit = "pies cuadrados" if lang == "es" else "sqft"
            parts.append(f'<span style="font-weight:500;color:var(--ink-soft)">{sq:,.0f} {unit}</span>')
        if parts:
            specs = '<span style="color:var(--line)">·</span>'.join(parts)
            page = _replace_once(page, r'(<p class="prop-specs" id="propSpecs"[^>]*>).*?</p>',
                                 lambda m: m.group(1) + specs + "</p>", re.S)
    if pending and 'id="ctaNote"' in page:
        note = ("Esta casa está pendiente. Ya hay un depósito, así que no hay visitas nuevas."
                if lang == "es" else
                "This home is pending. A deposit has been placed, so new tours are not open.")
        page = _replace_once(page, r'(<p class="cta-note" id="ctaNote">).*?</p>',
                             lambda m: m.group(1) + esc(note) + "</p>", re.S)
    if 'id="conditionLine"' in page:
        cond = str(home.get("condition") or "").strip()
        if cond:
            slot = f'<p class="condition-line" id="conditionLine"><span class="k">Condition</span> {esc(cond)}</p>'
        else:
            slot = '<p class="condition-line" id="conditionLine" hidden></p>'
        page = _replace_once(page, r'<p class="condition-line" id="conditionLine"[^>]*>.*?</p>',
                             lambda _m, slot=slot: slot, re.S)
    blurb = prose(home)
    if blurb:
        page = page.replace('id="aboutHomeSec" hidden', 'id="aboutHomeSec"', 1)
        page = _replace_once(page, r'(<p class="about-desc" id="aboutDesc"[^>]*>)[^<]*',
                             lambda m: m.group(1) + esc(blurb))
    rows = term_rows(home, lang)
    rows_html = "".join(
        f'<div class="term-row{" big" if r["big"] else ""}"><span class="k">{esc(r["k"])}</span><span class="v">{esc(r["v"])}</span></div>'
        for r in rows)
    page = _replace_once(page, r'<div class="terms" id="termsList">.*?</div>',
                         lambda _m, rows_html=rows_html: f'<div class="terms" id="termsList">{rows_html}</div>', re.S)
    terms_tag = f'<script type="application/json" id="seo-terms">{json_ld(rows)}</script>'
    page = re.sub(r'\n?<script type="application/json" id="seo-terms">.*?</script>', "", page, count=1, flags=re.S)
    page = page.replace('<div class="terms" id="termsList">', terms_tag + '\n<div class="terms" id="termsList">', 1)
    photo_flag = str(home.get("hasPhoto") or "").strip().lower()
    hid = home["id"]
    cards = root / "images" / "cards"
    sizes = "(max-width: 860px) calc(100vw - 40px), 680px"
    webp_parts, jpg_parts = [], []
    if (cards / f"{hid}-320.webp").is_file():
        webp_parts.append(f"images/cards/{hid}-320.webp 320w")
    if (cards / f"{hid}-480.webp").is_file():
        webp_parts.append(f"images/cards/{hid}-480.webp 480w")
    if (cards / f"{hid}-320.jpg").is_file():
        jpg_parts.append(f"images/cards/{hid}-320.jpg 320w")
    if (cards / f"{hid}-480.jpg").is_file():
        jpg_parts.append(f"images/cards/{hid}-480.jpg 480w")
    hero_src = ""
    if webp_parts:
        hero_src = webp_parts[-1].split(" ")[0]
    elif photo_flag in {"true", "1", "yes"} and (root / "images" / f"{hid}.jpg").is_file():
        hero_src = f"images/{hid}.jpg"
    elif photo_flag in {"false", "0"} and (root / "images" / "sv" / f"{hid}.jpg").is_file():
        hero_src = f"images/sv/{hid}.jpg"
    if hero_src:
        try:
            width = int(float(home.get("cardWidth") or 480))
            height = int(float(home.get("cardHeight") or 360))
        except (TypeError, ValueError):
            width, height = 480, 360
        if width <= 0:
            width = 480
        if height <= 0:
            height = 360
        alt = esc(f"Home for sale in {home.get('city') or ''}, {home.get('state') or ''}")
        chosen = webp_parts or jpg_parts
        srcset = f' srcset="{esc(", ".join(chosen))}" sizes="{sizes}"' if chosen else ""
        source = ""
        if webp_parts:
            source = f'<source type="image/webp" srcset="{esc(", ".join(webp_parts))}" sizes="{sizes}">'
        img = (f'<picture>{source}<img id="heroImg" alt="{alt}" src="{esc(hero_src)}"{srcset} '
               f'width="{width}" height="{height}" fetchpriority="high"></picture>')
        page = _replace_once(page, r'<img id="heroImg"[^>]*>', lambda _m, img=img: img)
        if photo_flag in {"false", "0"}:
            page = page.replace('id="heroSvBadge" hidden', 'id="heroSvBadge"', 1)
        page = re.sub(r'\n?<link rel="preload" as="image"[^>]*>', "", page)
        if webp_parts:
            preload = (f'<link rel="preload" as="image" type="image/webp" fetchpriority="high" '
                       f'href="{esc(hero_src)}" imagesrcset="{esc(", ".join(webp_parts))}" imagesizes="{sizes}"/>')
        else:
            preload = f'<link rel="preload" as="image" fetchpriority="high" href="{esc(hero_src)}"/>'
        page = page.replace(
            '<meta name="viewport" content="width=device-width, initial-scale=1.0"/>',
            '<meta name="viewport" content="width=device-width, initial-scale=1.0"/>\n' + preload,
            1,
        )
    if "<!-- buyer-eval:start -->" in page:
        import listing_facts
        baked = dict(home)
        baked["_down_text"] = money(home.get("moveIn"))
        baked["_monthly_text"] = money(home.get("monthlyPayment"))
        baked["_price_text"] = money(home.get("lockedPrice"))
        block_html = listing_facts.eval_html(baked, listing_facts.load(root), lang)
        page = re.sub(
            r"<!-- buyer-eval:start -->[\s\S]*?<!-- buyer-eval:end -->",
            "<!-- buyer-eval:start -->\n" + block_html + "\n<!-- buyer-eval:end -->",
            page,
            count=1,
        )
    if "DOMContentLoaded" in page:
        for src in ("listed-dates.js", "book-links.js", "homes.js", "homes-map.js", "homes-cart.js", "site-chrome.js"):
            page = page.replace(f'<script src="{src}"></script>', f'<script src="{src}" defer></script>')
    marker = '<script src="homes.js" defer></script>' if '<script src="homes.js" defer></script>' in page else '<script src="homes.js"></script>'
    if 'window.__HOME_ID__="' not in page and "<!-- home-id -->" in page:
        page = page.replace("<!-- home-id -->", f'<script>window.__HOME_ID__="{esc(home["id"])}";</script>', 1)
    elif 'window.__HOME_ID__="' not in page and marker in page:
        page = page.replace(marker, f'<script>window.__HOME_ID__="{esc(home["id"])}";</script>\n' + marker, 1)
    page = re.sub(r'\n?<script id="seo-restore">.*?</script>', "", page, count=1, flags=re.S)
    if "</body>" in page:
        page = page.replace("</body>", RESTORE_JS + "</body>", 1)
    return page


def _field(block: str, key: str):
    m = re.search(rf"\n    {key}:\s*(\"(?:\\.|[^\"\\])*\"|[^,\n]*),", block)
    if not m:
        return None
    raw = m.group(1).strip()
    if raw.startswith('"'):
        return json.loads(raw)
    if raw in {"", "null"}:
        return None
    return raw


def _features_of(block: str) -> dict:
    match = re.search(r"\n    features:\s*\{([^}]*)\}", block)
    if not match:
        return {}
    return {key: value for key, value in re.findall(r"([A-Za-z0-9_]+)\s*:\s*\"([^\"]*)\"", match.group(1))}


def _photos(block: str) -> list[str]:
    m = re.search(r"\n    photos:\s*(\[[\s\S]*?\])\s*,", block)
    if not m:
        return []
    try:
        value = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    return [str(x) for x in value] if isinstance(value, list) else []


def load_homes(root: Path) -> list[dict]:
    text = (root / "homes.js").read_text(encoding="utf-8")
    text = text.split("const SOLD_CARDS", 1)[0]
    homes = []
    for match in BLOCK_RE.finditer(text):
        block = match.group(0)
        home = {
            "id": match.group(1),
            "address": _field(block, "address") or "",
            "city": _field(block, "city") or "",
            "state": (_field(block, "state") or "").strip().upper(),
            "zip": _field(block, "zip") or "",
            "beds": _field(block, "beds"),
            "baths": _field(block, "baths"),
            "sqft": _field(block, "sqft") or "",
            "status": _field(block, "status") or "Available",
            "monthlyPayment": _field(block, "monthlyPayment"),
            "moveIn": _field(block, "moveIn"),
            "lockedPrice": _field(block, "lockedPrice"),
            "termText": _field(block, "termText") or "",
            "heroPhoto": _field(block, "heroPhoto") or "",
            "hasPhoto": _field(block, "hasPhoto"),
            "condition": _field(block, "condition") or "",
            "copy": _field(block, "copy") or "",
            "description": _field(block, "description") or "",
            "lat": _field(block, "lat"),
            "lng": _field(block, "lng"),
            "photos": _photos(block),
            "contractor": _field(block, "contractor") or "",
            "features": _features_of(block),
            "hasPhoto": _field(block, "hasPhoto"),
            "cardPhoto": _field(block, "cardPhoto") or "",
            "cardWidth": _field(block, "cardWidth"),
            "cardHeight": _field(block, "cardHeight"),
        }
        homes.append(home)
    return homes


def normalize(row: dict, lang: str) -> dict:
    """A portal add-row or a homes.js record, shaped for write_listing."""
    def pick(*keys):
        for key in keys:
            if key in row and row[key] not in (None, ""):
                return row[key]
        return None
    state = pick("state", "State") or ""
    return {
        "id": pick("id") or "",
        "address": pick("address", "Address") or "",
        "city": pick("city", "City") or "",
        "state": str(state).strip().upper(),
        "zip": pick("zip", "Zip") or "",
        "beds": pick("beds", "Beds"),
        "baths": pick("baths", "Baths"),
        "sqft": pick("sqft", "Sqft") or "",
        "status": pick("status", "Status") or "Available",
        "monthlyPayment": pick("monthlyPayment", "monthly", "Monthly payment"),
        "moveIn": pick("moveIn", "down", "Down payment"),
        "lockedPrice": pick("lockedPrice", "price", "Price"),
        "termText": pick("termText") or TERMS[lang],
        "heroPhoto": pick("heroPhoto") or "",
        "hasPhoto": pick("hasPhoto"),
        "condition": pick("condition", "Condition") or "",
        "copy": pick("copy") or "",
        "description": pick("description") or "",
        "lat": pick("lat"),
        "lng": pick("lng"),
        "photos": row.get("photos") or [],
        "contractor": pick("contractor") or "",
        "features": row.get("features") if isinstance(row.get("features"), dict) else {},
        "hasPhoto": pick("hasPhoto"),
    }


def group_cities(homes: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], dict] = {}
    for home in homes:
        city, state = (home.get("city") or "").strip(), (home.get("state") or "").strip().upper()
        if not city or not state:
            continue
        key = (city_slug(city), state.lower())
        bucket = groups.setdefault(key, {"city": city, "state": state, "homes": []})
        bucket["homes"].append(home)
    out = [g for g in groups.values() if g["homes"]]
    out.sort(key=lambda g: (-len(g["homes"]), g["city"].lower(), g["state"]))
    from card_photos import listing_sort_key
    for g in out:
        # Real seller photos first, then Street View-only homes, then address.
        g["homes"].sort(key=listing_sort_key)
    return out


def _city_page(group: dict, lang: str) -> str:
    domain = DOMAINS[lang]
    other = DOMAINS[OTHER[lang]]
    city, state = group["city"], group["state"]
    slug = city_file(city, state)
    url = f"{domain}/{slug}"
    n = len(group["homes"])
    if lang == "es":
        title = f"Casas con Financiamiento del Dueño en {city}, {state}"
        h1 = title
        noun = "casa" if n == 1 else "casas"
        desc = (f"{n} {noun} con financiamiento del dueño en {city}, {state}. "
                f"Cada anuncio muestra la dirección, el precio, el enganche y el pago mensual. Sin banco.")
        lead = (f"{n} {'casa' if n == 1 else 'casas'} en {city}, {state} que puede comprar con financiamiento del dueño. "
                f"El precio, el enganche y el pago mensual están en cada anuncio. No hay banco ni solicitud hipotecaria.")
        eyebrow = "Financiamiento del dueño"
        browse = "Ver todas las casas"
        nav = [(" /#listings".replace(" ", ""), "Casas"), ("/como-funciona.html", "Cómo funciona"),
               ("/nosotros", "Nosotros"), ("/contacto", "Contacto")]
        pending_word = "Pendiente"
    else:
        title = f"Owner Financed Homes in {city}, {state}"
        h1 = title
        noun = "home" if n == 1 else "homes"
        desc = (f"{n} owner-financed {noun} in {city}, {state}. "
                f"Each listing shows the address, purchase price, down payment, and monthly payment. No bank.")
        lead = (f"{n} owner-financed {'home' if n == 1 else 'homes'} in {city}, {state}. "
                f"Every listing below shows the address, purchase price, down payment, and monthly payment. "
                f"No bank and no mortgage application.")
        eyebrow = "Owner financing"
        browse = "Browse all homes"
        nav = [("/#listings", "Homes"), ("/how-it-works", "How it works"),
               ("/about", "About"), ("/contact", "Contact")]
        pending_word = "Pending"
    items = []
    for i, home in enumerate(group["homes"], 1):
        bits = [f"{home.get('city')}, {home.get('state')}"]
        price, down, monthly = money(home.get("lockedPrice")), money(home.get("moveIn")), money(home.get("monthlyPayment"))
        if price:
            bits.append(price if lang == "es" else f"{price} price")
        if down:
            bits.append(f"{down} de enganche" if lang == "es" else f"{down} down")
        if monthly:
            bits.append(f"{monthly}/mes" if lang == "es" else f"{monthly}/mo")
        size = bed_bath(home, lang)
        if size:
            bits.append(size)
        pending = str(home.get("status") or "").strip().lower() == "pending"
        href = f"/{home['id']}.html"
        down_n = num(home.get("moveIn"))
        pay_n = num(home.get("monthlyPayment"))
        beds_n = num(home.get("beds"))
        photo = "1" if str(home.get("hasPhoto") or "").strip().lower() in {"1", "true", "yes"} else "0"
        if beds_n:
            bed_label = f"{int(beds_n) if float(beds_n) == int(float(beds_n)) else beds_n} " + ("recámaras" if lang == "es" else "beds")
        else:
            bed_label = "recámaras no indicadas" if lang == "es" else "beds not listed"
        avail = pending_word if pending else ("Disponible ahora" if lang == "es" else "Available now")
        img = (f'<img src="/images/cards/{esc(home["id"])}-480.webp" alt="" width="480" height="360" loading="lazy" decoding="async">'
               if photo == "1" else "")
        items.append(
            f'<article class="swipe-card" data-id="{esc(home["id"])}" data-down="{"" if down_n is None else down_n}" '
            f'data-pay="{"" if pay_n is None else pay_n}" data-beds="{"" if not beds_n else beds_n}" '
            f'data-status="{esc(str(home.get("status") or "Available"))}" data-photo="{photo}">'
            f'<a href="{esc(href)}">{img}<p class="where">{esc(home.get("address") or home["id"])}</p>'
            f'<p class="meta">{esc(" · ".join(bits))}</p><p class="meta">{esc(bed_label)}</p>'
            f'<p class="avail">{esc(avail)}</p></a></article>')
    list_items = []
    for i, home in enumerate(group["homes"], 1):
        list_items.append({
            "@type": "ListItem",
            "position": i,
            "url": f"{domain}/{home['id']}.html",
            "name": home.get("address") or home["id"],
        })
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            organization(lang),
            {
                "@type": "CollectionPage",
                "@id": url + "#page",
                "name": h1,
                "url": url,
                "description": desc,
                "isPartOf": {"@id": domain + "/#website"},
                "mainEntity": {"@id": url + "#list"},
            },
            {
                "@type": "ItemList",
                "@id": url + "#list",
                "numberOfItems": n,
                "itemListElement": list_items,
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Casas" if lang == "es" else "Homes", "item": domain + "/"},
                    {"@type": "ListItem", "position": 2, "name": h1, "item": url},
                ],
            },
        ],
    }
    nav_html = "\n        ".join(f'<a href="{esc(href)}">{esc(label)}</a>' for href, label in nav)
    lang_label = "English" if lang == "es" else "Español"
    rows = "\n      ".join(items)
    return f"""<!DOCTYPE html>
<html lang="{lang}" data-city-landing="{city_slug(city)}-{state.lower()}">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{esc(title)} | {BRAND}</title>
<meta name="description" content="{esc(desc)}"/>
<link rel="canonical" href="{esc(url)}"/>
{hreflang_links(url, other + "/" + slug)}
<meta property="og:type" content="website"/>
<meta property="og:site_name" content="{BRAND}"/>
<meta property="og:locale" content="{'es_US' if lang == 'es' else 'en_US'}"/>
<meta property="og:title" content="{esc(title)}"/>
<meta property="og:description" content="{esc(desc)}"/>
<meta property="og:url" content="{esc(url)}"/>
<meta property="og:image" content="{domain}/images/_share-default.jpg"/>
<link rel="stylesheet" href="/pages.css">
<link rel="stylesheet" href="/nav.css">
<style>
.city-list{{list-style:none;margin:18px 0;padding:0;display:flex;flex-direction:column;gap:10px}}
.city-list li{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px 16px}}
.city-list a{{color:var(--pine);font-weight:700;text-decoration:none;font-size:17px}}
.city-list a:hover{{text-decoration:underline}}
.city-list .meta{{display:block;color:var(--ink-soft);font-size:15px;margin-top:3px}}
.city-list .pending{{display:inline-block;margin-left:8px;background:#c2410c;color:#fff;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;border-radius:999px;padding:2px 8px;vertical-align:2px}}
.city-back{{margin:8px 0 28px}}
.buyer-panel{{display:grid;gap:10px;margin:0 0 18px}}
.buyer-panel label{{display:grid;gap:4px;font-size:13px;font-weight:700;color:var(--ink-soft,#5b6577)}}
.buyer-panel input,.buyer-panel select{{font:600 16px "DM Sans",system-ui,sans-serif;padding:12px;border-radius:12px;border:1.5px solid var(--line);min-height:48px;background:#fff;color:var(--ink,#16213a)}}
.buyer-budgets{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.range-chips{{display:flex;gap:8px;overflow-x:auto;padding:2px 0 8px}}
.range-chips button{{flex:0 0 auto;min-height:44px;padding:0 14px;border-radius:999px;border:1.5px solid var(--line,#d5dbe6);background:#fff;font:700 14px system-ui,sans-serif;color:#15315e;cursor:pointer}}
.range-chips button[aria-pressed="true"]{{background:#15315e;color:#fff}}
.row-scroller{{display:flex;gap:12px;overflow-x:auto;scroll-snap-type:x mandatory;padding:8px 0 16px}}
.swipe-card{{flex:0 0 min(78vw,280px);scroll-snap-align:start;background:#fff;border:1px solid var(--line);border-radius:16px;overflow:hidden}}
.swipe-card a{{color:inherit;text-decoration:none;display:block}}
.swipe-card img{{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;background:#e6eef8}}
.swipe-card .where{{font-weight:800;margin:10px 12px 4px}}
.swipe-card .meta,.swipe-card .avail{{margin:0 12px 8px;font-size:14px}}
.chip-clear{{min-height:44px;border:0;background:transparent;color:#15315e;font-weight:800;text-decoration:underline;cursor:pointer}}
#cityHomes{{list-style:none;margin:0;padding:0}}
.buyer-group{{margin:18px 0}}
.buyer-group h2{{font-size:20px;margin:0 0 8px}}
.joe-slot[hidden]{{display:none !important}}
html.preview .joe-slot[hidden]{{display:block !important;border:1.5px dashed var(--brand-primary,#15315e);border-radius:12px;padding:12px 14px;margin:10px 0}}
</style>
<script>(function(){{if(/[?&]preview=1(?:&|$)/.test(location.search))document.documentElement.classList.add("preview");}})();</script>
<script type="application/ld+json" id="seo-jsonld">{json_ld(graph)}</script>
</head>
<body>
<div class="wrap narrow">
  <header class="topbar">
    <a class="brand" href="/" aria-label="{BRAND}">
      <svg class="mark" viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <path d="M24 3 41 9V23C41 33 33 41 24 45 15 41 7 33 7 23V9Z" fill="#15315e"/>
        <path d="M15 26 24 18 33 26Z" fill="#e23b3b"/>
        <rect x="17.5" y="26" width="13" height="9" fill="#ffffff"/>
        <rect x="22" y="30" width="4" height="5" fill="#15315e"/>
      </svg>
      <span class="bn">{BRAND}<small>{'casasconfinanciamiento.com' if lang == 'es' else 'getownerfinancedhomes.com'}</small></span>
    </a>
    <nav class="topnav" aria-label="Site">
      <a class="nav-account" href="/account/?lang={lang}">{'Mi cuenta: visitas y documentos' if lang == 'es' else 'My account: tours and paperwork'}</a>
      <button type="button" class="nav-toggle" aria-expanded="false" aria-controls="siteMenu"><span class="nav-bars" aria-hidden="true"></span><span class="nav-word">{'Menú' if lang == 'es' else 'Menu'}</span></button>
      <div class="site-menu" id="siteMenu">
        {nav_html}
        <a class="nav-es" href="{esc(other + '/' + slug)}" hreflang="{'en' if lang == 'es' else 'es'}">{lang_label}</a>
      </div>
    </nav>
  </header>
  <form class="buyer-panel" id="buyerSearch" action="/" method="get" data-city="{esc(city)}" data-state="{esc(state)}">
    <label>{'Ciudad o código postal' if lang == 'es' else 'City or ZIP'}
      <input id="fQ" name="q" type="search" value="{esc(city)}, {esc(state)}" autocomplete="off" enterkeyhint="search">
    </label>
    <input type="hidden" id="chipDownMin" value=""><input type="hidden" id="chipDownMax" value="">
    <input type="hidden" id="chipPayMin" value=""><input type="hidden" id="chipPayMax" value="">
    <input type="hidden" id="bedsMin" value="">
    <div class="range-chips" data-min="chipDownMin" data-max="chipDownMax" role="radiogroup" aria-label="{'Enganche' if lang == 'es' else 'Down payment'}">
      <button type="button" data-min="" data-max="" aria-pressed="true">{'Cualquiera' if lang == 'es' else 'Any'}</button>
      <button type="button" data-min="" data-max="1999">{'Menos de $2,000' if lang == 'es' else 'Under $2,000'}</button>
      <button type="button" data-min="2000" data-max="4000">$2,000–$4,000</button>
      <button type="button" data-min="4000" data-max="">$4,000+</button>
    </div>
    <div class="range-chips" data-min="chipPayMin" data-max="chipPayMax" role="radiogroup" aria-label="{'Mensualidad' if lang == 'es' else 'Monthly payment'}">
      <button type="button" data-min="" data-max="" aria-pressed="true">{'Cualquiera' if lang == 'es' else 'Any'}</button>
      <button type="button" data-min="" data-max="799">{'Menos de $800' if lang == 'es' else 'Under $800'}</button>
      <button type="button" data-min="800" data-max="1000">$800–$1,000</button>
      <button type="button" data-min="1000" data-max="1300">$1,000–$1,300</button>
      <button type="button" data-min="1300" data-max="">$1,300+</button>
    </div>
    <div class="range-chips" id="bedChips" data-min="bedsMin" role="radiogroup" aria-label="{'Recámaras' if lang == 'es' else 'Bedrooms'}">
      <button type="button" data-min="" aria-pressed="true">{'Cualquiera' if lang == 'es' else 'Any'}</button>
      <button type="button" data-min="1">1+</button>
      <button type="button" data-min="2">2+</button>
      <button type="button" data-min="3">3+</button>
      <button type="button" data-min="4">4+</button>
    </div>
    <button type="button" class="chip-clear" id="clearBuyer">{'Quitar filtros' if lang == 'es' else 'Clear filters'}</button>
  </form>
  <section class="phead">
    <span class="eyebrow">{esc(eyebrow)}</span>
    <h1>{esc(h1)}</h1>
    <p class="lead">{esc(lead)}</p>
  </section>
  <div class="row-scroller" id="cityHomes">
      {rows}
  </div>
  <p id="cityEmpty" hidden>{'Nada en ese rango. Pruebe un rango más amplio o menos recámaras.' if lang == 'es' else 'Nothing in that range. Try a wider payment range or fewer bedrooms. Nearby homes show below when we have them.'}</p>
  <div id="buyerExtra"></div>
  <p class="city-back"><a href="/">{esc(browse)}</a></p>
</div>
<script src="/buyer-search.js" defer></script>
<script src="/site-chrome.js"></script>
</body>
</html>
"""


def _prev_lastmod(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in re.finditer(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", text)}


def _write_if_changed(path: Path, text: str) -> bool:
    old = path.read_text(encoding="utf-8") if path.is_file() else None
    if old == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def _sitemap(entries: list[tuple[str, str, str, str, str]]) -> str:
    """entries: loc, lastmod, priority, en href, es href."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    for loc, lastmod, priority, en, es in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{esc(loc)}</loc>")
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append(f'    <xhtml:link rel="alternate" hreflang="en" href="{esc(en)}"/>')
        lines.append(f'    <xhtml:link rel="alternate" hreflang="es" href="{esc(es)}"/>')
        lines.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{esc(en)}"/>')
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def _stamp_static(root: Path, lang: str, today: str, prev: dict[str, str]) -> list[tuple[str, str, str, str, str]]:
    domain = DOMAINS[lang]
    other = DOMAINS[OTHER[lang]]
    entries = []
    for filename, path, other_path, priority, is_home in STATIC[lang]:
        file = root / filename
        if not file.is_file():
            continue
        text = file.read_text(encoding="utf-8")
        here, there = domain + path, other + other_path
        text = re.sub(r'\n?<link rel="alternate" hreflang="[^"]+" href="[^"]+"/>', "", text)
        text = re.sub(r"\n?<!-- seo-social:start -->[\s\S]*?<!-- seo-social:end -->", "", text, count=1)
        text = re.sub(r'\n?<script type="application/ld\+json" id="seo-org">.*?</script>', "", text, count=1, flags=re.S)
        if is_home:
            title_m = re.search(r"<title>(.*?)</title>", text, re.S)
            desc_m = re.search(r'<meta name="description" content="([^"]*)"', text)
            og_title = html.unescape(title_m.group(1)) if title_m else BRAND
            og_desc = html.unescape(desc_m.group(1)) if desc_m else ""
            locale = "es_US" if lang == "es" else "en_US"
            og = "\n".join([
                "<!-- seo-social:start -->",
                '<meta property="og:type" content="website"/>',
                f'<meta property="og:site_name" content="{BRAND}"/>',
                f'<meta property="og:locale" content="{locale}"/>',
                f'<meta property="og:title" content="{esc(og_title)}"/>',
                f'<meta property="og:description" content="{esc(og_desc)}"/>',
                f'<meta property="og:url" content="{esc(here)}"/>',
                f'<meta property="og:image" content="{domain}/images/_share-default.jpg"/>',
                '<meta name="twitter:card" content="summary_large_image"/>',
                f'<meta name="twitter:title" content="{esc(og_title)}"/>',
                f'<meta name="twitter:description" content="{esc(og_desc)}"/>',
                f'<meta name="twitter:image" content="{domain}/images/_share-default.jpg"/>',
                "<!-- seo-social:end -->",
            ])
            text = _replace_once(text, r'(<link rel="canonical" href="[^"]+"/>)', r"\1\n" + og)
        block = hreflang_links(here, there)
        if "<!-- seo-social:end -->" in text:
            text = text.replace("<!-- seo-social:end -->", "<!-- seo-social:end -->\n" + block, 1)
        elif 'rel="canonical"' in text:
            text = _replace_once(text, r'(<link rel="canonical" href="[^"]+"/>)', r"\1\n" + block)
        else:
            text = _replace_once(text, r'(<meta name="description" content="[^"]*"/>)', r"\1\n" + block)
        org = f'<script type="application/ld+json" id="seo-org">{json_ld({"@context": "https://schema.org", **organization(lang)})}</script>'
        text = _replace_once(text, r'(<link rel="alternate" hreflang="x-default" href="[^"]+"/>)', r"\1\n" + org)
        text = _replace_once(text, r'(<a class="nav-es" href=")[^"]*(")', rf'\1{there}\2')
        changed = _write_if_changed(file, text)
        loc = domain + path
        lastmod = today if changed else prev.get(loc, today)
        entries.append((loc, lastmod, priority, here if lang == "en" else there, there if lang == "en" else here))
        # here/there depend on lang. en href must always be the English URL.
        en_href = here if lang == "en" else there
        es_href = there if lang == "en" else here
        entries[-1] = (loc, lastmod, priority, en_href, es_href)
    return entries


def _city_section(groups: list[dict], lang: str) -> str:
    if lang == "es":
        label, heading = "Por ciudad", "Casas con financiamiento del dueño por ciudad"
        sub = "Cada ciudad tiene su página con la dirección, el precio, el enganche y el pago mensual."
    else:
        label, heading = "By city", "Owner financed homes by city"
        sub = "Each city page lists the homes there with the address, purchase price, down payment, and monthly payment."
    pills = []
    for g in groups:
        n = len(g["homes"])
        pills.append(f'<a href="/{city_file(g["city"], g["state"])}">{esc(g["city"])}, {esc(g["state"])} <span class="n">{n}</span></a>')
    inner = "\n      ".join(pills)
    return (
        "<!-- city-landings:start -->\n"
        '  <section class="section" id="cities">\n'
        f'    <div class="sec-label">{label}</div>\n'
        f'    <h2 class="sec-title">{heading}</h2>\n'
        f'    <p class="sec-sub">{sub}</p>\n'
        f'    <div class="city-pills">\n      {inner}\n    </div>\n'
        "  </section>\n"
        "<!-- city-landings:end -->"
    )


def _stamp_cities_on_index(root: Path, groups: list[dict], lang: str) -> bool:
    index = root / "index.html"
    if not index.is_file():
        return
    text = index.read_text(encoding="utf-8")
    if ".city-pills{" not in text and "</style>" in text:
        text = text.replace("</style>", PILL_CSS + "\n</style>", 1)
    section = _city_section(groups, lang)
    if "<!-- city-landings:start -->" in text:
        text = re.sub(r"<!-- city-landings:start -->[\s\S]*?<!-- city-landings:end -->", lambda _m: section, text, count=1)
    else:
        placed = False
        for anchor in ('<section class="section" id="soldSec"', '<footer class="foot">', "</body>"):
            if anchor in text:
                text = text.replace(anchor, section + "\n\n  " + anchor, 1)
                placed = True
                break
        if not placed:
            text = text.replace("</body>", section + "\n</body>", 1)
    return _write_if_changed(index, text)


def _drop_stale_cities(root: Path, keep: set[str]) -> list[str]:
    removed = []
    for path in root.glob("*.html"):
        if path.name in keep:
            continue
        try:
            with path.open(encoding="utf-8") as fh:
                head = fh.read(600)
        except OSError:
            continue
        if CITY_MARK in head:
            path.unlink()
            removed.append(path.name)
    return removed


def _write_buyer_index(root: Path, homes: list[dict]) -> bool:
    """Compact catalog for city-page search. Fetched only after the visitor changes the search."""
    rows = []
    for home in homes:
        try:
            lat, lng = float(home.get("lat")), float(home.get("lng"))
        except (TypeError, ValueError):
            lat, lng = None, None
        rows.append({
            "id": home.get("id") or "",
            "address": home.get("address") or "",
            "city": home.get("city") or "",
            "state": home.get("state") or "",
            "zip": clean_zip(home.get("zip")),
            "moveIn": num(home.get("moveIn")),
            "monthlyPayment": num(home.get("monthlyPayment")),
            "lockedPrice": num(home.get("lockedPrice")),
            "status": home.get("status") or "Available",
            "lat": lat,
            "lng": lng,
            "hasPhoto": str(home.get("hasPhoto") or "").strip().lower() in {"1", "true", "yes"},
            "beds": num(home.get("beds")),
        })
    path = Path(root) / "data" / "buyer-index.json"
    path.parent.mkdir(exist_ok=True)
    return _write_if_changed(path, json.dumps({"homes": rows}, separators=(",", ":")))


def _stamp_finance(root: Path, homes: list[dict], lang: str) -> bool:
    import listing_facts
    _lowest, _count, line = listing_facts.finance_line(homes, lang)
    if not line:
        return False
    changed = False
    names = ("index.html", "how-it-works.html") if lang == "en" else ("index.html", "como-funciona.html")
    for name in names:
        path = Path(root) / name
        if not path.is_file() or "<!-- finance-stats:start -->" not in path.read_text(encoding="utf-8"):
            continue
        text = path.read_text(encoding="utf-8")
        new = re.sub(
            r"<!-- finance-stats:start -->[\s\S]*?<!-- finance-stats:end -->",
            "<!-- finance-stats:start -->" + esc(line) + "<!-- finance-stats:end -->",
            text,
            count=1,
        )
        if _write_if_changed(path, new):
            changed = True
    return changed


def rebuild(root: Path, lang: str = "en") -> str:
    root = Path(root)
    if not (root / "home.html").is_file() or not (root / "homes.js").is_file():
        return "seo: skipped (home.html or homes.js missing)"
    homes = load_homes(root)
    template = (root / "home.html").read_text(encoding="utf-8")
    today = date.today().isoformat()
    sm = root / "sitemap.xml"
    prev = _prev_lastmod(sm.read_text(encoding="utf-8")) if sm.is_file() else {}
    domain, other = DOMAINS[lang], DOMAINS[OTHER[lang]]
    seen_titles: dict[str, str] = {}
    for home in homes:
        home.pop("_seo_suffix", None)
        title = page_title(home, lang)
        if title in seen_titles:
            home["_seo_suffix"] = home["id"]
        else:
            seen_titles[title] = home["id"]
    written = 0
    entries = _stamp_static(root, lang, today, prev)
    groups = group_cities(homes)
    home_ids = {h["id"] for h in homes}
    city_names = []
    for group in groups:
        slug = city_file(group["city"], group["state"])
        if Path(slug).stem in home_ids:
            continue
        text = _city_page(group, lang)
        changed = _write_if_changed(root / slug, text)
        loc = f"{domain}/{slug}"
        lastmod = today if changed else prev.get(loc, today)
        en = loc if lang == "en" else f"{other}/{slug}"
        es = f"{other}/{slug}" if lang == "en" else loc
        entries.append((loc, lastmod, "0.7", en, es))
        city_names.append(slug)
    _drop_stale_cities(root, set(city_names))
    _write_buyer_index(root, homes)
    index_changed = bool(_stamp_cities_on_index(root, groups, lang))
    index_changed = _stamp_finance(root, homes, lang) or index_changed
    if index_changed:
        index_loc = domain + "/"
        entries = [(loc, today if loc == index_loc else last, pri, en, es) for loc, last, pri, en, es in entries]
    for home in homes:
        page = write_listing(root, home, lang, template)
        changed = _write_if_changed(root / f"{home['id']}.html", page)
        loc = f"{domain}/{home['id']}.html"
        lastmod = today if changed else prev.get(loc, today)
        en = loc if lang == "en" else f"{other}/{home['id']}.html"
        es = f"{other}/{home['id']}.html" if lang == "en" else loc
        entries.append((loc, lastmod, "0.6", en, es))
        written += 1
    sm.write_text(_sitemap(entries), encoding="utf-8")
    return f"seo: {written} listing pages, {len(groups)} city pages, sitemap {len(entries)} urls"


def _ld_types(html_text: str) -> list[dict]:
    blobs = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html_text, re.S)
    out = []
    for blob in blobs:
        out.append(json.loads(blob))
    return out


def _graph_types(doc: dict) -> set[str]:
    types = set()
    nodes = doc.get("@graph") or [doc]
    for node in nodes:
        if not isinstance(node, dict):
            continue
        kind = node.get("@type")
        if isinstance(kind, list):
            types.update(kind)
        elif kind:
            types.add(kind)
    return types


def validate(root: Path, lang: str = "en") -> list[str]:
    """Return a list of problems. Empty means the generated SEO holds together."""
    root = Path(root)
    errors: list[str] = []
    homes = load_homes(root)
    if not homes:
        return ["no homes in homes.js"]
    domain = DOMAINS[lang]
    other = DOMAINS[OTHER[lang]]
    titles: dict[str, str] = {}
    descriptions: dict[str, str] = {}
    for home in homes:
        path = root / f"{home['id']}.html"
        if not path.is_file():
            errors.append(f"missing page {path.name}")
            continue
        text = path.read_text(encoding="utf-8")
        title_m = re.search(r"<title>(.*?)</title>", text, re.S)
        title = html.unescape(title_m.group(1)) if title_m else ""
        if not title or title in titles:
            errors.append(f"title not unique for {home['id']}: {title!r}")
        titles[title] = home["id"]
        for part in (home.get("address") or "", home.get("city") or "", (home.get("state") or "").upper()):
            if part and part not in title:
                errors.append(f"title missing {part!r} on {home['id']}")
        h1_m = re.search(r'<h1 class="headline" id="headline">(.*?)</h1>', text, re.S)
        h1 = html.unescape(re.sub(r"<[^>]+>", "", h1_m.group(1))) if h1_m else ""
        if not h1.strip():
            errors.append(f"empty h1 on {home['id']}")
        facts_m = re.search(r'<p class="seo-facts" id="seoFacts">(.*?)</p>', text, re.S)
        facts = html.unescape(facts_m.group(1)) if facts_m else ""
        visible = h1 + " " + facts
        for label, value in (("price", money(home.get("lockedPrice"))),
                             ("down", money(home.get("moveIn"))),
                             ("monthly", money(home.get("monthlyPayment")))):
            if value and value not in visible:
                errors.append(f"{home['id']} visible text missing {label} {value}")
        if "$0" in visible:
            errors.append(f"{home['id']} shows $0")
        desc_m = re.search(r'<meta name="description" content="([^"]*)"', text)
        desc = html.unescape(desc_m.group(1)) if desc_m else ""
        if not desc or desc in descriptions:
            errors.append(f"description not unique for {home['id']}")
        descriptions[desc] = home["id"]
        for code, href in re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', text):
            pass
        hrefs = dict(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', text))
        en_url, es_url = f"{DOMAINS['en']}/{home['id']}.html", f"{DOMAINS['es']}/{home['id']}.html"
        if hrefs.get("en") != en_url or hrefs.get("es") != es_url or hrefs.get("x-default") != en_url:
            errors.append(f"hreflang mismatch on {home['id']}: {hrefs}")
        if f'{other}/{home["id"]}.html' not in text:
            errors.append(f"language switcher missing counterpart on {home['id']}")
        boots_late = '"homes.js"' in text and ('addEventListener("load"' in text or "setTimeout(" in text)
        if 'src="homes.js" defer' not in text and not boots_late and "DOMContentLoaded" in (root / "home.html").read_text(encoding="utf-8"):
            errors.append(f"homes.js is not deferred on {home['id']}")
        try:
            docs = _ld_types(text)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON-LD on {home['id']}: {exc}")
            docs = []
        kinds = set().union(*(_graph_types(d) for d in docs)) if docs else set()
        for need in ("RealEstateListing", "BreadcrumbList", "Organization"):
            if need not in kinds:
                errors.append(f"{home['id']} JSON-LD missing {need}")
        if num(home.get("lockedPrice")) is not None and "Offer" not in kinds:
            errors.append(f"{home['id']} JSON-LD missing Offer")
        if 'name="robots" content="noindex' in text:
            errors.append(f"live home {home['id']} is noindex")
    groups = group_cities(homes)
    for group in groups:
        slug = city_file(group["city"], group["state"])
        path = root / slug
        if not path.is_file():
            errors.append(f"missing city page {slug}")
            continue
        text = path.read_text(encoding="utf-8")
        if "homes.js" in text:
            errors.append(f"{slug} loads homes.js")
        if f"in {group['city']}, {group['state']}" not in text and f"en {group['city']}, {group['state']}" not in text:
            errors.append(f"{slug} missing city name")
        for home in group["homes"]:
            if f'/{home["id"]}.html' not in text:
                errors.append(f"{slug} missing link to {home['id']}")
        hrefs = dict(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', text))
        if hrefs.get("es") != f"{DOMAINS['es']}/{slug}" or hrefs.get("en") != f"{DOMAINS['en']}/{slug}":
            errors.append(f"city hreflang mismatch {slug}")
    for path in root.glob("*.html"):
        try:
            with path.open(encoding="utf-8") as fh:
                head = fh.read(800)
        except OSError:
            continue
        if CITY_MARK in head and path.name not in {city_file(g["city"], g["state"]) for g in groups}:
            errors.append(f"city page with no homes: {path.name}")
    sm_path = root / "sitemap.xml"
    if not sm_path.is_file():
        errors.append("missing sitemap.xml")
        sitemap = ""
    else:
        sitemap = sm_path.read_text(encoding="utf-8")
        if "xmlns:xhtml" not in sitemap:
            errors.append("sitemap missing xhtml namespace")
        for home in homes:
            loc = f"{domain}/{home['id']}.html"
            if f"<loc>{loc}</loc>" not in sitemap:
                errors.append(f"sitemap missing {home['id']}")
            if f'hreflang="es" href="{DOMAINS["es"]}/{home["id"]}.html"' not in sitemap:
                errors.append(f"sitemap missing es alternate for {home['id']}")
        for group in groups:
            slug = city_file(group["city"], group["state"])
            if f"<loc>{domain}/{slug}</loc>" not in sitemap:
                errors.append(f"sitemap missing {slug}")
    for path in root.glob("*.html"):
        try:
            head = path.read_text(encoding="utf-8")[:1200]
        except OSError:
            continue
        if 'noindex' in head and path.stem in {h["id"] for h in homes}:
            continue
        if 'noindex' in head and f"/{path.name}<" in sitemap:
            errors.append(f"noindex page in sitemap: {path.name}")
    robots = root / "robots.txt"
    if robots.is_file():
        robots_text = robots.read_text(encoding="utf-8")
        for needle in ("User-agent:", "Allow: /", "Disallow: /home.html", "Sitemap:"):
            if needle not in robots_text:
                errors.append(f"robots.txt missing {needle}")
    else:
        errors.append("missing robots.txt")
    if (root / "images" / "_share-default.jpg").is_file() and not (root / ".nojekyll").is_file():
        errors.append(".nojekyll missing while images/_share-default.jpg is the share image")
    index = root / "index.html"
    if index.is_file():
        index_text = index.read_text(encoding="utf-8")
        if 'property="og:image"' not in index_text:
            errors.append("homepage missing og:image")
        if 'hreflang="es"' not in index_text or 'hreflang="x-default"' not in index_text:
            errors.append("homepage missing hreflang")
        if 'id="seo-org"' not in index_text and '"Organization"' not in index_text:
            errors.append("homepage missing Organization JSON-LD")
        if groups and 'class="city-pills"' not in index_text:
            errors.append("homepage missing city links")
    nxt = root / "next-steps.html"
    if nxt.is_file():
        nxt_text = nxt.read_text(encoding="utf-8")[:800]
        if "noindex" not in nxt_text:
            errors.append("next-steps.html lost noindex")
        if "/next-steps.html<" in sitemap:
            errors.append("next-steps.html is in the sitemap")
    return errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--site", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--lang", choices=("en", "es"), default="en")
    ap.add_argument("--check", action="store_true", help="validate only; write nothing")
    args = ap.parse_args(argv)
    if not args.check:
        print(rebuild(args.site, args.lang))
    errors = validate(args.site, args.lang)
    if errors:
        print(f"{len(errors)} SEO check problem(s):")
        print("\n".join(errors[:40]))
        return 1
    print(f"SEO check ok ({args.lang})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
