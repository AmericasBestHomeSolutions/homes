"""Short booking links: getownerfinancedhomes.com/book/<slug> and casasconfinanciamiento.com/agendar/<slug>.

Buyer texts used to carry the booking app's own address (owner.getownerfinancedhomes.com/book?home=<id>&lang=en).
The site is static (GitHub Pages), so each live home gets a tiny redirect page that sends the buyer to that same
booking page. Any query string the link carries (lang, utm_*, ...) and the #fragment are kept; home= is always the
page's own home.

    /book/905-olive/          short slug: the home id without its "<city>-<state>-" prefix
    /book/decatur-il-905-olive/   the full home id always works too

The Spanish site writes /agendar/... with lang=es (a ?lang=en on the link still wins). GitHub Pages answers
/book/905-olive with a 301 to /book/905-olive/ and keeps the query string, so the link in a text has no slash.

Short slugs are kept in data/book-links.json ("slugs"; "live" lists what a text should carry for each live home,
and the CRM reads it from the published site) so a slug, once given, always means the same home: a later home whose
short slug is taken uses its full id instead. Two new homes that want the same free slug both use their full ids
and the slug stays unissued. When a home leaves the site (sold, retired, excluded) its pages stay as a redirect to
the home page, so old texts still land somewhere. The page shows only the street address, city and state; never
anything from the seller or lockbox columns.

Called by scripts/refresh_listings.py (homes) and scripts/build_casas.py (casas) after homes.js is written, so the
daily portal sync and the Mac refresh both keep the pages current. Same file in both repos; keep it that way.

    python3 scripts/book_links.py [--site DIR] [--lang en|es]
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

BOOKING = "https://owner.getownerfinancedhomes.com/book"
SITES = {
    "en": {"domain": "https://getownerfinancedhomes.com", "dir": "book",
           "title": "Book a tour: {addr}", "gone": "This home is no longer available",
           "go": "Open the booking page", "all": "See the homes available now", "wait": "Opening the booking page…"},
    "es": {"domain": "https://casasconfinanciamiento.com", "dir": "agendar",
           "title": "Agende una visita: {addr}", "gone": "Esta casa ya no está disponible",
           "go": "Abrir la página para agendar", "all": "Vea las casas disponibles", "wait": "Abriendo la página para agendar…"},
}
STATE = Path("data") / "book-links.json"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,120}$")
_PREFIX = re.compile(r"^[a-z]+-[a-z]{2}-(?=[a-z0-9])")
MARK = "<!-- book-link:"   # every generated page carries this, so we only ever rewrite our own files


def short_slug(home_id: str) -> str:
    """decatur-il-905-olive -> 905-olive. "" when the id has no <city>-<state>- prefix."""
    m = _PREFIX.match(home_id)
    return home_id[m.end():] if m else ""


def read_homes(root: Path) -> dict[str, dict]:
    """id -> {address, city, state} for every home in HOMES (not SOLD_CARDS)."""
    text = (Path(root) / "homes.js").read_text(encoding="utf-8")
    text = text.split("const SOLD_CARDS")[0]
    out: dict[str, dict] = {}
    for block in re.split(r"\n  \{\n", text)[1:]:
        m = re.search(r'^\s*id:\s*"([^"]+)"', block, re.M)
        if not m:
            continue
        hid = m.group(1).strip().lower()
        status = re.search(r'^\s*status:\s*"([^"]*)"', block, re.M)
        if status and status.group(1).strip().lower() not in ("", "available"):
            continue
        rec = {}
        for key in ("address", "city", "state"):
            v = re.search(r"^\s*" + key + r':\s*"((?:\\.|[^"\\])*)"', block, re.M)
            rec[key] = json.loads('"' + v.group(1) + '"') if v else ""
        if ID_RE.match(hid):
            out[hid] = rec
    return out


def load_state(root: Path) -> dict:
    f = Path(root) / STATE
    if f.is_file():
        data = json.loads(f.read_text(encoding="utf-8"))
        return {"slugs": dict(data.get("slugs", {})), "held": sorted(set(data.get("held", [])))}
    return {"slugs": {}, "held": []}


def assign(state: dict, ids: list[str], extra: tuple[dict, ...] = ()) -> dict:
    """Give each live id a short slug if it can have one. Mutates and returns state.

    state["slugs"]: short slug -> home id, never reassigned. state["held"]: short slugs two homes wanted at once."""
    slugs, held = state["slugs"], set(state["held"])
    # Slugs the other site already gave out win, so both sites agree on what /book/905-olive means.
    for other in extra:
        for s, hid in other.get("slugs", {}).items():
            if s not in slugs and s not in held:
                slugs[s] = hid
        held |= set(other.get("held", [])) - set(slugs)
    full = set(ids)
    has = set(slugs.values())
    want: dict[str, list[str]] = {}
    for hid in sorted(ids):
        if hid in has:
            continue
        s = short_slug(hid)
        if not s or s in slugs or s in held or s in full or not ID_RE.match(s):
            continue
        want.setdefault(s, []).append(hid)
    for s, who in want.items():
        if len(who) == 1:
            slugs[s] = who[0]
        else:
            held.add(s)
    state["slugs"] = dict(sorted(slugs.items()))
    state["held"] = sorted(held)
    return state


def booking_url(home_id: str, lang: str) -> str:
    return f"{BOOKING}?home={home_id}&lang={lang}"


def _addr(rec: dict) -> str:
    parts = [p.strip() for p in (rec.get("address", ""), rec.get("city", "")) if p and p.strip()]
    line = ", ".join(parts)
    if rec.get("state"):
        line = f"{line}, {rec['state'].strip()}" if line else rec["state"].strip()
    return " ".join(line.split())[:120]


def page_for(root: Path, home_id: str, rec: dict, lang: str, path: str) -> str:
    t = SITES[lang]
    target = booking_url(home_id, lang)
    addr = _addr(rec) or home_id
    title = t["title"].format(addr=addr)
    img = ""
    if (Path(root) / "images" / f"{home_id}.jpg").is_file():
        img = f'<meta property="og:image" content="{t["domain"]}/images/{home_id}.jpg"/>\n'
    e = lambda s: html.escape(s, quote=True)  # noqa: E731
    # JS keeps the link's own query (lang, utm_*, ...) and #fragment; home= is always this page's home.
    js = ("(function(){var u=new URL(%s),q=new URLSearchParams(location.search);"
          "q.forEach(function(v,k){if(k!=='home')u.searchParams.set(k,v)});"
          "u.hash=location.hash;location.replace(u.toString())})();") % json.dumps(target)
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8"/>
{MARK}{home_id} -->
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<meta name="robots" content="noindex, nofollow"/>
<title>{e(title)} | Americas Best Home Solutions</title>
<link rel="canonical" href="{e(target)}"/>
<meta property="og:title" content="{e(title)}"/>
<meta property="og:url" content="{t["domain"]}/{t["dir"]}/{e(path)}"/>
{img}<script>{js}</script>
<noscript><meta http-equiv="refresh" content="0;url={e(target)}"/></noscript>
</head>
<body>
<p>{e(t["wait"])} <a href="{e(target)}">{e(t["go"])}</a></p>
</body>
</html>
"""


def gone_page(lang: str, key: str) -> str:
    t = SITES[lang]
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8"/>
{MARK}{key} gone -->
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<meta name="robots" content="noindex, nofollow"/>
<title>{t["gone"]} | Americas Best Home Solutions</title>
<link rel="canonical" href="{t["domain"]}/"/>
<meta http-equiv="refresh" content="0;url=/"/>
<script>location.replace("/");</script>
</head>
<body>
<p>{t["gone"]}. <a href="/">{t["all"]}</a>.</p>
</body>
</html>
"""


def _write(f: Path, text: str) -> bool:
    if f.is_file() and f.read_text(encoding="utf-8") == text:
        return False
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    return True


def build(root: Path, lang: str | None = None, extra: tuple[Path, ...] = ()) -> dict:
    """Write <dir>/<slug>/index.html for every live home. Returns counts for the log line."""
    root = Path(root)
    lang = lang or ("es" if (root / "como-funciona.html").is_file() else "en")
    t = SITES[lang]
    homes = read_homes(root)
    ids = sorted(homes)
    others = tuple(load_state(Path(p)) for p in extra if (Path(p) / STATE).is_file())
    state = assign(load_state(root), ids, others)
    (root / STATE).parent.mkdir(parents=True, exist_ok=True)
    by_id = {hid: s for s, hid in state["slugs"].items()}
    # "live": what a text should carry for each home on the site right now (the CRM reads this file from the site).
    published = {**state, "live": {hid: by_id.get(hid, hid) for hid in ids}}
    _write(root / STATE, json.dumps(published, indent=2) + "\n")

    out = root / t["dir"]
    pages: dict[str, str] = {}
    for hid in ids:
        pages[hid] = page_for(root, hid, homes[hid], lang, hid)
    for s, hid in state["slugs"].items():
        pages[s] = page_for(root, hid, homes[hid], lang, s) if hid in homes else gone_page(lang, s)
    # A home that left the site: its old pages stay, as a redirect to the home page.
    if out.is_dir():
        for d in out.iterdir():
            if d.is_dir() and d.name not in pages and (d / "index.html").is_file():
                if MARK in (d / "index.html").read_text(encoding="utf-8"):
                    pages[d.name] = gone_page(lang, d.name)
    changed = sum(_write(out / key / "index.html", text) for key, text in pages.items())
    _write(out / "index.html", gone_page(lang, "index").replace(t["gone"], t["all"]))
    live_short = sum(1 for hid in state["slugs"].values() if hid in homes)
    return {"homes": len(ids), "short": live_short, "gone": sum(1 for p in pages.values() if " gone -->" in p),
            "changed": changed}


def links(root: Path) -> dict[str, str]:
    """home id -> short slug (or the full id) for live homes. What a text should carry."""
    root = Path(root)
    homes = read_homes(root)
    by_id = {hid: s for s, hid in load_state(root)["slugs"].items()}
    return {hid: by_id.get(hid, hid) for hid in sorted(homes)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--site", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--lang", choices=("en", "es"))
    a = ap.parse_args()
    r = build(Path(a.site), a.lang)
    print(f"booking links: {r['homes']} homes, {r['short']} short slugs, {r['gone']} retired, {r['changed']} pages written")
