"""Short booking links: getownerfinancedhomes.com/book/<slug> and casasconfinanciamiento.com/agendar/<slug>.

Buyer texts and listing pages use these paths on the public site. Each page embeds the CRM
(owner.getownerfinancedhomes.com) in a full-height iframe with ``embed=1``, forwarding query
params (``lang``, ``t``, utm_*, …) without sending the browser to the staff host.

    /book/905-olive/          short slug: the home id without its "<city>-<state>-" prefix
    /book/decatur-il-905-olive/   the full home id always works too
    /feedback/<slug>  and  /account  work the same way (feedback keeps only t, prop, lang).

The Spanish site writes /agendar/... and /cuenta with lang=es. GitHub Pages answers
/book/905-olive with a 301 to /book/905-olive/ and keeps the query string.

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

CRM = "https://owner.getownerfinancedhomes.com"
BOOKING = f"{CRM}/book"
FEEDBACK = f"{CRM}/feedback/"
ACCOUNT = f"{CRM}/account"
# After-tour feedback links (Joe, 2026-11-01): getownerfinancedhomes.com/feedback/<slug> and
# casasconfinanciamiento.com/opinion/<slug> open the CRM's feedback form for that home (photo + address on top, tap to
# pick likes and what held them back). Unlike booking, a feedback link keeps working after a home leaves the site,
# because buyers answer after the tour.
# Since 2026-11-01 (CRM Auditor, Filling-CRM #132) a text carries ONE signed token, ?t=, minted by the CRM (staff route
# GET /api/tours/<tour id>/feedback-link, or feedback_link() below with a token from it). Never a phone or name: the
# redirect forwards only FEEDBACK_KEEP and drops anything else (old links' name=/phone=/tour= stay on this page).
# This repo never holds the signing secret.
FEEDBACK_KEEP = ("t", "prop", "lang")
FEEDBACK_SITES = {
    "en": {"dir": "feedback", "title": "How was your tour? {addr}", "go": "Open the feedback form",
           "wait": "Opening the feedback form…", "frame": "Tour feedback"},
    "es": {"dir": "opinion", "title": "¿Qué tal su visita? {addr}", "go": "Abrir el formulario",
           "wait": "Abriendo el formulario…", "frame": "Comentarios de la visita"},
}
ACCOUNT_SITES = {
    "en": {"dir": "account", "title": "My account", "go": "Open my account", "frame": "Buyer account"},
    "es": {"dir": "cuenta", "title": "Mi cuenta", "go": "Abrir mi cuenta", "frame": "Cuenta del comprador"},
}
SITES = {
    "en": {"domain": "https://getownerfinancedhomes.com", "dir": "book",
           "title": "Book a tour: {addr}", "gone": "This home is no longer available",
           "go": "Open the booking page", "all": "See the homes available now", "wait": "Opening the booking page…",
           "frame": "Book a tour"},
    "es": {"domain": "https://casasconfinanciamiento.com", "dir": "agendar",
           "title": "Agende una visita: {addr}", "gone": "Esta casa ya no está disponible",
           "go": "Abrir la página para agendar", "all": "Vea las casas disponibles", "wait": "Abriendo la página para agendar…",
           "frame": "Agendar una visita"},
}
STATE = Path("data") / "book-links.json"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,120}$")
_PREFIX = re.compile(r"^[a-z]+-[a-z]{2}-(?=[a-z0-9])")
MARK = "<!-- book-link:"   # every generated page carries this, so we only ever rewrite our own files
_EMBED_STYLE = "html,body{margin:0;height:100%;overflow:hidden}iframe{border:0;width:100%;height:100%;display:block;min-height:100dvh}"


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


def account_url(lang: str) -> str:
    return f"{ACCOUNT}?lang={lang}"


def _addr(rec: dict) -> str:
    parts = [p.strip() for p in (rec.get("address", ""), rec.get("city", "")) if p and p.strip()]
    line = ", ".join(parts)
    if rec.get("state"):
        line = f"{line}, {rec['state'].strip()}" if line else rec["state"].strip()
    return " ".join(line.split())[:120]


def _og_image(root: Path, domain: str, home_id: str | None) -> str:
    if home_id and (Path(root) / "images" / f"{home_id}.jpg").is_file():
        return f'<meta property="og:image" content="{domain}/images/{home_id}.jpg"/>\n'
    if (Path(root) / "images" / "_share-default.jpg").is_file():
        return f'<meta property="og:image" content="{domain}/images/_share-default.jpg"/>\n'
    return ""


def _embed_js(base: str, *, skip: tuple[str, ...] = (), keep: tuple[str, ...] | None = None) -> str:
    """Set iframe#crm src to the CRM URL with embed=1 and merged query params."""
    head = (
        "(function(){var u=new URL(" + json.dumps(base) + "),q=new URLSearchParams(location.search);"
        "u.searchParams.set('embed','1');"
    )
    if keep is not None:
        tail = (
            "var keep=" + json.dumps(list(keep)) + ";"
            "keep.forEach(function(k){if(q.has(k))u.searchParams.set(k,q.get(k))});"
        )
    else:
        tail = (
            "var skip=" + json.dumps(list(skip)) + ";"
            "q.forEach(function(v,k){if(skip.indexOf(k)<0)u.searchParams.set(k,v)});"
        )
    return head + tail + "u.hash=location.hash;document.getElementById('crm').src=u.toString();})();"


def embed_page(
    *,
    lang: str,
    title: str,
    public_path: str,
    mark: str,
    frame_title: str,
    crm_base: str,
    skip: tuple[str, ...] = (),
    keep: tuple[str, ...] | None = None,
    og_image: str,
    noscript_href: str,
    link_text: str,
) -> str:
    t = SITES[lang]
    public_url = f"{t['domain']}/{public_path.lstrip('/')}"
    e = lambda s: html.escape(s, quote=True)  # noqa: E731
    js = _embed_js(crm_base, skip=skip, keep=keep)
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8"/>
{mark}
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<meta name="robots" content="noindex, nofollow"/>
<title>{e(title)} | Americas Best Home Solutions</title>
<link rel="canonical" href="{e(public_url)}"/>
<meta property="og:title" content="{e(title)}"/>
<meta property="og:url" content="{e(public_url)}"/>
{og_image}<style>{_EMBED_STYLE}</style>
<script>{js}</script>
<noscript><meta http-equiv="refresh" content="0;url={e(noscript_href)}"/></noscript>
</head>
<body>
<iframe id="crm" title="{e(frame_title)}"></iframe>
<p><a href="{e(noscript_href)}">{e(link_text)}</a></p>
</body>
</html>
"""


def page_for(root: Path, home_id: str, rec: dict, lang: str, path: str) -> str:
    t = SITES[lang]
    addr = _addr(rec) or home_id
    title = t["title"].format(addr=addr)
    return embed_page(
        lang=lang,
        title=title,
        public_path=f"{t['dir']}/{path}",
        mark=f"{MARK}{home_id} -->",
        frame_title=t["frame"],
        crm_base=booking_url(home_id, lang),
        skip=("home",),
        og_image=_og_image(root, t["domain"], home_id),
        noscript_href=booking_url(home_id, lang),
        link_text=t["go"],
    )


def feedback_url(home_id: str, lang: str) -> str:
    return f"{FEEDBACK}{home_id}?lang={lang}"


_TOKEN_RE = re.compile(r"[A-Za-z0-9_.-]{20,400}")


def feedback_link(slug: str, token: str, lang: str = "en") -> str:
    """The short public link to text a buyer: <site>/feedback/<slug>?t=<token>. ``token`` comes from the CRM (staff
    route GET /api/tours/<tour id>/feedback-link); a phone, name or tour id is never put in the link."""
    if not _TOKEN_RE.fullmatch(str(token or "")):
        raise ValueError("feedback token must come from the CRM")
    return f"{SITES[lang]['domain']}/{FEEDBACK_SITES[lang]['dir']}/{slug}?t={token}"


def feedback_page_for(root: Path, home_id: str, rec: dict, lang: str, path: str) -> str:
    t, f = SITES[lang], FEEDBACK_SITES[lang]
    addr = _addr(rec or {}) or home_id
    title = f["title"].format(addr=addr)
    return embed_page(
        lang=lang,
        title=title,
        public_path=f"{f['dir']}/{path}",
        mark=f"{MARK}{home_id} feedback -->",
        frame_title=f["frame"],
        crm_base=feedback_url(home_id, lang),
        keep=FEEDBACK_KEEP,
        og_image=_og_image(root, t["domain"], home_id),
        noscript_href=feedback_url(home_id, lang),
        link_text=f["go"],
    )


def account_page_for(root: Path, lang: str) -> str:
    a, t = ACCOUNT_SITES[lang], SITES[lang]
    return embed_page(
        lang=lang,
        title=a["title"],
        public_path=f"{a['dir']}/",
        mark=f"{MARK}account -->",
        frame_title=a["frame"],
        crm_base=account_url(lang),
        og_image=_og_image(root, t["domain"], None),
        noscript_href=account_url(lang),
        link_text=a["go"],
    )


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


def write_book_links_js(root: Path, lang: str, live: dict[str, str]) -> bool:
    t = SITES[lang]
    mapping = {hid: f"/{t['dir']}/{slug}" for hid, slug in sorted(live.items())}
    body = (
        "/* Generated by scripts/book_links.py — do not hand-edit. */\n"
        "const BOOK_HREF = " + json.dumps(mapping, indent=2) + ";\n"
        f"function bookHref(homeId){{return BOOK_HREF[homeId]||('/{t['dir']}/'+encodeURIComponent(homeId));}}\n"
    )
    return _write(root / "book-links.js", body)


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
    write_book_links_js(root, lang, published["live"])

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

    # Feedback links: every live id, every short slug ever issued (live or not), and any full id that already has a
    # booking or feedback page, so a text sent before a home went pending still opens the form.
    fdir = root / FEEDBACK_SITES[lang]["dir"]
    targets: dict[str, str] = {hid: hid for hid in ids}
    targets.update({s: hid for s, hid in state["slugs"].items()})
    for d in (out, fdir):
        if d.is_dir():
            for sub in d.iterdir():
                if sub.is_dir() and sub.name not in targets and short_slug(sub.name) and ID_RE.match(sub.name):
                    targets[sub.name] = sub.name
    changed += sum(_write(fdir / key / "index.html", feedback_page_for(root, hid, homes.get(hid, {}), lang, key))
                   for key, hid in targets.items())
    _write(fdir / "index.html", gone_page(lang, "index").replace(t["gone"], t["all"]))

    adir = root / ACCOUNT_SITES[lang]["dir"]
    changed += int(_write(adir / "index.html", account_page_for(root, lang)))

    live_short = sum(1 for hid in state["slugs"].values() if hid in homes)
    return {"homes": len(ids), "short": live_short, "gone": sum(1 for p in pages.values() if " gone -->" in p),
            "feedback": len(targets), "changed": changed}


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
    print(f"booking links: {r['homes']} homes, {r['short']} short slugs, {r['gone']} retired, "
          f"{r['feedback']} feedback links, {r['changed']} pages written")
