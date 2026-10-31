#!/usr/bin/env python3
"""Keep the site in step with the seller portal ('Portal Backup' tab), every day.

Joe's rule: the site matches Portal Backup. This pass runs after the Mac's
"Refresh listings from master" (GitHub Actions, .github/workflows/portal-sync.yml)
and on its own each morning after the 7 AM portal backup. For one site checkout it:

* adds a home (homes.js entry, <id>.html page, sitemap line) for every Available
  portal home the site does not have yet,
* updates price, down payment, monthly payment, beds, baths and square feet when
  the portal changed them (and the dollar amounts in that home's copy and page tags),
* retires a home the portal marks Pending or Sold (sold card + redirect, via
  scripts/sold_policy.py) or Not in portal (redirect, no sold card).

It never relists a home CRM_Properties marks SOLD / PENDING / not listed, and never
adds one with no price or monthly payment. Those are listed under "check by hand".

Columns: only Portal Backup A:M (Portal PROP id .. Date listed) and CRM_Properties
A:F (Unique ID .. Property Status) are requested from Google, so lockbox, seller
and phone columns are never downloaded, let alone written.

Credentials: env GOOGLE_SERVICE_ACCOUNT_JSON (the key JSON, a GitHub Actions secret).
Offline: --portal-json / --crm-json (lists of row dicts) instead of the Sheets API.

    python3 scripts/portal_sync.py --dry-run            # print the change summary, write nothing
    python3 scripts/portal_sync.py --summary-out /tmp/s # apply, write the commit message
    python3 <homes>/scripts/portal_sync.py --site . --lang es   # the Spanish site (casas)

Afterwards run the site's own post-pass (scripts/refresh_listings.py or
scripts/build_casas.py) so pages are rebuilt from home.html and dates are stamped.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

SHEET_ID = "1QDLFUiBFDrKdTnhnRUHUr_pErOpNsDhnZD9AA7vRBQs"
PORTAL_RANGE = "'Portal Backup'!A:M"     # stops before Lockbox code (N)
CRM_RANGE = "'CRM_Properties'!A:F"        # Unique ID .. Property Status only
PORTAL_COLUMNS = ("Portal PROP id", "Address", "City", "State", "Zip", "Status", "Beds", "Baths", "Sqft",
                  "Price", "Down payment", "Monthly payment", "Date listed")
CLOSED = re.compile(r"(?i)\b(sold|pending|not listed|deposit)\b")
DIRS = {"n", "s", "e", "w", "ne", "nw", "se", "sw", "north", "south", "east", "west"}
MAX_RETIRE = 25        # a bad read must not empty the site
MIN_PORTAL_ROWS = 100

SITES = {
    "en": {"domain": "https://getownerfinancedhomes.com",
           "terms": "30-year owner financing (contract for deed)"},
    "es": {"domain": "https://casasconfinanciamiento.com",
           "terms": "Financiamiento del dueño a 30 años (contrato de compraventa)"},
}


# ---------- ids ----------
def city_slug(city: str) -> str:
    city = (city or "").lower().replace("saint ", "st").replace("st. ", "st")
    return re.sub(r"[^a-z0-9]", "", city)


def address_key(address: str) -> tuple[str, str]:
    tokens = re.findall(r"[a-z0-9]+", (address or "").split(",")[0].lower())
    number, i = "", 0
    while i < len(tokens) and re.fullmatch(r"\d+[a-z]?", tokens[i]):
        number += tokens[i]
        i += 1
    while i < len(tokens) - 1 and tokens[i] in DIRS:
        i += 1
    return number, (tokens[i] if i < len(tokens) else "")


def home_id(address: str, city: str, state: str) -> str:
    number, street = address_key(address)
    if not number or not street or not state:
        return ""
    return f"{city_slug(city)}-{state.strip().lower()}-{number}-{street}"


def num(value):
    text = str(value if value is not None else "").replace(",", "").replace("$", "").strip()
    if not text:
        return None
    try:
        f = float(text)
    except ValueError:
        return None
    return int(f) if f == int(f) else f


def money(n) -> str:
    return f"${n:,}"


# ---------- sources ----------
def _rows(values) -> list[dict]:
    if not values:
        return []
    head = [str(h).strip() for h in values[0]]
    return [{h: str(r[i]).strip() if i < len(r) else "" for i, h in enumerate(head) if h} for r in values[1:]
            if any(str(c).strip() for c in r)]


def read_sheets() -> tuple[list[dict], list[dict]]:
    info = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not info:
        raise SystemExit("GOOGLE_SERVICE_ACCOUNT_JSON is not set (GitHub secret). Use --portal-json for offline runs.")
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    creds = service_account.Credentials.from_service_account_info(
        json.loads(info), scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    creds.refresh(Request())
    query = urllib.parse.urlencode([("ranges", PORTAL_RANGE), ("ranges", CRM_RANGE), ("majorDimension", "ROWS")])
    req = urllib.request.Request(f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values:batchGet?{query}",
                                 headers={"Authorization": f"Bearer {creds.token}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    portal, crm = (_rows(r.get("values")) for r in payload["valueRanges"])
    return portal, crm


def load_json(path: str | None) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else []


def whitelist(rows: list[dict]) -> list[dict]:
    return [{k: str(r.get(k) or "").strip() for k in PORTAL_COLUMNS} for r in rows]


# ---------- homes.js ----------
BLOCK_RE = re.compile(r"\n  \{\n    id: \"([^\"]+)\",[\s\S]*?\n  \},")


def blocks(text: str) -> dict[str, re.Match]:
    return {m.group(1): m for m in BLOCK_RE.finditer(text)}


def field(block: str, key: str):
    m = re.search(rf"\n    {key}:\s*(\"(?:\\.|[^\"\\])*\"|[^,\n]*),", block)
    if not m:
        return None
    raw = m.group(1).strip()
    return json.loads(raw) if raw.startswith('"') else raw


def set_field(block: str, key: str, value) -> str:
    rendered = json.dumps(value) if isinstance(value, str) else str(value)
    return re.sub(rf"(\n    {key}:\s*)(\"(?:\\.|[^\"\\])*\"|[^,\n]*)(,)",
                  lambda m: m.group(1) + rendered + m.group(3), block, count=1)


def reprice_text(text: str, swaps: dict[int, int]) -> str:
    """Swap old dollar amounts for new ones in one pass, so $2,000->$3,000 and $3,000->$1,000 don't collide."""
    if not swaps:
        return text
    pattern = re.compile(r"\$(" + "|".join(re.escape(f"{o:,}") for o in swaps) + r")(?![\d,]*\d)")
    lookup = {f"{o:,}": n for o, n in swaps.items()}
    return pattern.sub(lambda m: money(lookup[m.group(1)]), text)


def portal_index(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        hid = home_id(row["Address"], row["City"], row["State"])
        if not hid:
            continue
        if hid not in out or (row["Status"].lower() == "available" and out[hid]["Status"].lower() != "available"):
            out[hid] = row
    return out


def match_site_id(hid: str, row: dict, site_keys: dict) -> str:
    """The site's id for a portal row: exact id, else same house number + street + state (city typos)."""
    if hid in site_keys["ids"]:
        return hid
    number, street = address_key(row["Address"])
    return site_keys["by_addr"].get((number, street, row["State"].strip().lower()), hid)


# ---------- new home text ----------
def baths_word(b) -> str:
    return f"{b:g}" if isinstance(b, float) else str(b)


def copy_en(r: dict) -> str:
    sq = f" with about {r['sqft']:,} square feet" if r["sqft"] else ""
    return (f"{money(r['monthly'])} a month and {money(r['down'])} to move in. This {r['beds']}-bedroom, "
            f"{baths_word(r['baths'])}-bath home in {r['city']}, {r['state']}{sq} gives you room to spread out and a "
            f"place that's truly yours, with no landlord deciding whether you stay. The purchase price is "
            f"{money(r['price'])}, fixed in writing when you sign, with owner financing and no bank in the middle. "
            f"It's sold as-is, so come walk through every room and judge it with your own eyes. Homes at this payment "
            f"don't sit long, so book a Tour and claim a showing time.")


def copy_es(r: dict) -> str:
    sq = f" con unos {r['sqft']:,} pies cuadrados" if r["sqft"] else ""
    rec = "recámara" if r["beds"] == 1 else "recámaras"
    ban = "baño" if r["baths"] == 1 else "baños"
    return (f"{money(r['monthly'])} al mes y {money(r['down'])} para mudarse. Esta casa de {r['beds']} {rec} y "
            f"{baths_word(r['baths'])} {ban} en {r['city']}, {r['state']}{sq} le da espacio de sobra y un lugar que "
            f"de verdad es suyo, sin un casero que decida si se queda. El precio de compra es {money(r['price'])}, "
            f"fijado por escrito cuando firma, con financiamiento del dueño y ningún banco en el medio. Se vende tal "
            f"como está, así que venga a recorrer cada cuarto y júzguela con sus propios ojos. Casas a este pago no se "
            f"quedan mucho tiempo, así que agende una visita y reserve su horario.")


def geocode(address: str, city: str, state: str, zipc: str):
    """Free US Census geocoder (no key). Returns (lat, lng) or None; the map skips homes without a pin."""
    q = urllib.parse.urlencode({"address": f"{address}, {city}, {state} {zipc}".strip(),
                                "benchmark": "Public_AR_Current", "format": "json"})
    try:
        with urllib.request.urlopen(f"https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?{q}",
                                    timeout=20) as resp:
            matches = json.load(resp)["result"]["addressMatches"]
        if matches:
            c = matches[0]["coordinates"]
            return round(c["y"], 6), round(c["x"], 6)
    except Exception:
        pass
    return None


def new_block(r: dict, lang: str, coords) -> str:
    lines = ["", "  {", f"    id: {json.dumps(r['id'])},", f"    address:     {json.dumps(r['address'])},"]
    if r["zip"]:
        lines.append(f"    zip:         {json.dumps(r['zip'])},")
    if lang == "es":
        lines += [f"    description: {json.dumps(copy_es(r), ensure_ascii=False)},", '    descriptionLang: "es",']
    else:
        lines.append(f"    copy:        {json.dumps(copy_en(r))},")
    lines += [f"    city:  {json.dumps(r['city'])},", f"    state: {json.dumps(r['state'])},",
              f"    beds:  {r['beds']},", f"    baths: {r['baths']},",
              f"    sqft:  {json.dumps(str(r['sqft']) if r['sqft'] else '')},"]
    if coords:
        lines += [f"    lat:   {coords[0]},", f"    lng:   {coords[1]},", '    geo:   "exact",']
    lines += ['    status: "Available",', "", f"    monthlyPayment: {r['monthly']},", f"    moveIn:         {r['down']},",
              f"    lockedPrice:    {r['price']},", f"    termText:       {json.dumps(SITES[lang]['terms'], ensure_ascii=False)},",
              "", '    heroPhoto: "",', "    photos:    [],", "  },"]
    return "\n".join(lines)


def head_block(r: dict, lang: str) -> str:
    d = SITES[lang]["domain"]
    if lang == "es":
        title = f"{r['beds']} rec {baths_word(r['baths'])} baño en {r['city']}, {r['state']} — {money(r['monthly'])}/mes"
        desc = (f"{r['address']} · {money(r['monthly'])}/mes · {money(r['down'])} para mudarse · {money(r['price'])} "
                f"precio fijo. Financiamiento del dueño — sin banco, sin solicitud hipotecaria.")
        locale = '\n<meta property="og:locale" content="es_US"/>'
    else:
        title = f"{r['beds']} bed {baths_word(r['baths'])} bath in {r['city']}, {r['state']} — {money(r['monthly'])}/mo"
        desc = (f"{r['address']} · {money(r['monthly'])}/month · {money(r['down'])} to move in · {money(r['price'])} "
                f"purchase price. Owner financing — no bank, no mortgage application.")
        locale = ""
    t, s, url, img = (html.escape(title), html.escape(desc), f"{d}/{r['id']}.html", f"{d}/images/_share-default.jpg")
    return (f'<link rel="canonical" href="{url}"/>\n<meta property="og:type" content="website"/>\n'
            f'<meta property="og:site_name" content="Americas Best Home Solutions"/>{locale}\n'
            f'<meta property="og:title" content="{t}"/>\n<meta property="og:description" content="{s}"/>\n'
            f'<meta property="og:image" content="{img}"/>\n<meta property="og:url" content="{url}"/>\n'
            f'<meta name="twitter:card" content="summary_large_image"/>\n<meta name="twitter:title" content="{t}"/>\n'
            f'<meta name="twitter:description" content="{s}"/>\n<meta name="twitter:image" content="{img}"/>')


def write_page(root: Path, r: dict, lang: str) -> None:
    page = (root / "home.html").read_text(encoding="utf-8")
    desc = re.search(r'<meta name="description" content="[^"]*"/>', page)
    page = re.sub(r'<link rel="canonical"[\s\S]*?<meta name="twitter:image"[^>]*>\n?', "", page)
    if desc:
        page = page.replace(desc.group(0), desc.group(0) + "\n" + head_block(r, lang), 1)
    marker = '<script src="homes.js"></script>'
    page = page.replace(marker, f'<script>window.__HOME_ID__="{r["id"]}";</script>\n' + marker, 1)
    (root / f"{r['id']}.html").write_text(page, encoding="utf-8")


GONE_HTML = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<meta name="robots" content="noindex, nofollow"/>
<title>{title} | Americas Best Home Solutions</title>
<link rel="canonical" href="{domain}/"/>
<meta http-equiv="refresh" content="0;url=/"/>
<script>location.replace("/");</script>
</head>
<body>
<p>{title}. <a href="/">{link}</a>.</p>
</body>
</html>
"""


# ---------- the pass ----------
def plan(root: Path, portal_rows: list[dict], crm_rows: list[dict]) -> dict:
    text = (root / "homes.js").read_text(encoding="utf-8")
    site = blocks(text)
    site_keys = {"ids": set(site), "by_addr": {}}
    for sid, m in site.items():
        number, street = address_key(field(m.group(0), "address") or "")
        st = (field(m.group(0), "state") or "").lower()
        site_keys["by_addr"].setdefault((number, street, st), sid)
    crm_closed = {str(r.get("Unique ID") or "").strip().lower(): r.get("Property Status", "")
                  for r in crm_rows if CLOSED.search(str(r.get("Property Status") or ""))}
    portal = portal_index(portal_rows)
    out = {"add": [], "update": [], "retire": [], "hand": []}
    for hid, row in portal.items():
        sid = match_site_id(hid, row, site_keys)
        status = row["Status"].strip()
        price, down, monthly = num(row["Price"]), num(row["Down payment"]), num(row["Monthly payment"])
        if sid in site:
            block = site[sid].group(0)
            if status.lower() in ("pending", "sold"):
                out["retire"].append({"id": sid, "why": status.lower(), "address": row["Address"]})
            elif status.lower() == "not in portal":
                out["retire"].append({"id": sid, "why": "gone", "address": row["Address"]})
            elif status.lower() == "available":
                diffs = {}
                for key, value in (("lockedPrice", price), ("moveIn", down), ("monthlyPayment", monthly),
                                   ("beds", num(row["Beds"])), ("baths", num(row["Baths"])), ("sqft", num(row["Sqft"]))):
                    if value in (None, 0):
                        continue
                    old = field(block, key)
                    if num(old) != value:
                        diffs[key] = (num(old), value)
                if diffs:
                    out["update"].append({"id": sid, "address": row["Address"], "diffs": diffs})
            continue
        if status.lower() != "available":
            continue
        if hid in crm_closed:
            out["hand"].append(f"{row['Address']}, {row['City']} ({row['Portal PROP id']}): portal says Available, "
                               f"CRM_Properties says {crm_closed[hid]}; not relisted")
            continue
        if not price or not monthly:
            out["hand"].append(f"{row['Address']}, {row['City']} ({row['Portal PROP id']}): no price or monthly payment; skipped")
            continue
        out["add"].append({"id": hid, "pid": row["Portal PROP id"], "address": row["Address"], "city": row["City"],
                           "state": row["State"].strip().upper(), "zip": row["Zip"], "beds": num(row["Beds"]) or 0,
                           "baths": num(row["Baths"]) or 0, "sqft": num(row["Sqft"]), "price": price,
                           "down": down or 0, "monthly": monthly})
    out["add"].sort(key=lambda r: r["id"])
    return out


def apply(root: Path, p: dict, lang: str, geocoder=geocode) -> None:
    js = root / "homes.js"
    text = js.read_text(encoding="utf-8")
    site = blocks(text)
    for u in p["update"]:
        m = site[u["id"]]
        block = m.group(0)
        swaps = {o: n for k, (o, n) in u["diffs"].items() if k in ("lockedPrice", "moveIn", "monthlyPayment") and o}
        for key, (_old, new) in u["diffs"].items():
            block = set_field(block, key, str(new) if key == "sqft" else new)
        block = re.sub(r'(\n    (?:copy|description):\s*)("(?:\\.|[^"\\])*")',
                       lambda mm: mm.group(1) + json.dumps(reprice_text(json.loads(mm.group(2)), swaps), ensure_ascii=False),
                       block)
        text = text.replace(m.group(0), block, 1)
        page = root / f"{u['id']}.html"
        if page.is_file() and swaps:
            raw = page.read_text(encoding="utf-8")
            page.write_text(re.sub(r'(<meta (?:property|name)="(?:og|twitter):(?:title|description)" content=")([^"]*)',
                                   lambda mm: mm.group(1) + reprice_text(mm.group(2), swaps), raw), encoding="utf-8")
    if p["add"]:
        start = text.index("const HOMES = [")
        end = text.index("\n];", start)
        added = "".join(new_block(r, lang, geocoder(r["address"], r["city"], r["state"], r["zip"])) for r in p["add"])
        if not text[:end].rstrip().endswith(","):
            added = "," + added
        text = text[:end] + added + text[end:]
        for r in p["add"]:
            write_page(root, r, lang)
        sm = root / "sitemap.xml"
        if sm.is_file():
            d = SITES[lang]["domain"]
            lines = "".join(f"  <url><loc>{d}/{r['id']}.html</loc><lastmod>{date.today().isoformat()}</lastmod>"
                            f"<priority>0.6</priority></url>\n" for r in p["add"]
                            if f"/{r['id']}.html<" not in sm.read_text(encoding="utf-8"))
            sm.write_text(sm.read_text(encoding="utf-8").replace("</urlset>", lines + "</urlset>", 1), encoding="utf-8")
    js.write_text(text, encoding="utf-8")
    # Retire: pending/sold through the sold policy (sold card, redirect, sitemap); gone = redirect only.
    sold = {r["id"]: r["why"] for r in p["retire"] if r["why"] in ("pending", "sold")}
    gone = [r["id"] for r in p["retire"] if r["why"] == "gone"]
    if sold:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import sold_policy
        tmp = root / "data" / ".portal-sold-overrides.json"
        tmp.parent.mkdir(exist_ok=True)
        tmp.write_text(json.dumps({k: {"state": v, "sold_on": date.today().isoformat()} for k, v in sold.items()}))
        try:
            sold_policy.apply_site(root, tmp)
        finally:
            tmp.unlink()
    if gone:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import sold_policy
        text = sold_policy.excise_homes(js.read_text(encoding="utf-8"), set(gone))
        js.write_text(text, encoding="utf-8")
        es = lang == "es"
        for hid in gone:
            page = root / f"{hid}.html"
            if page.is_file():
                page.write_text(GONE_HTML.format(lang=lang, domain=SITES[lang]["domain"],
                                                 title="Esta casa ya no está disponible" if es else "This home is no longer available",
                                                 link="Vea las casas disponibles" if es else "See the homes available now"),
                                encoding="utf-8")
        sm = root / "sitemap.xml"
        if sm.is_file():
            kept = [l for l in sm.read_text(encoding="utf-8").splitlines(keepends=True)
                    if not any(f"/{h}.html<" in l for h in gone)]
            sm.write_text("".join(kept), encoding="utf-8")
    text = js.read_text(encoding="utf-8")
    count = len(re.findall(r'\n    id: "', text.split("const SOLD_CARDS")[0]))
    text = re.sub(r"\((\d+) live,", f"({count} live,", text, count=1)
    text = re.sub(r"\((\d+), generadas", f"({count}, generadas", text, count=1)
    js.write_text(text, encoding="utf-8")


def summary(p: dict) -> str:
    n = lambda k: len(p[k])
    lines = [f"Portal sync: {n('add')} new, {n('update')} terms changed, {n('retire')} retired", ""]
    for r in p["add"]:
        lines.append(f"+ {r['id']}  {r['address']}, {r['city']} {r['state']}  {money(r['price'])} / "
                     f"{money(r['down'])} down / {money(r['monthly'])}/mo  ({r['pid']})")
    for u in p["update"]:
        lines.append(f"~ {u['id']}  " + ", ".join(f"{k} {o}→{nv}" for k, (o, nv) in u["diffs"].items()))
    for r in p["retire"]:
        lines.append(f"- {r['id']}  {r['why']}")
    if p["hand"]:
        lines += ["", "Check by hand:"] + [f"  {h}" for h in p["hand"]]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--site", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--lang", choices=("en", "es"), default="en")
    ap.add_argument("--portal-json")
    ap.add_argument("--crm-json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--summary-out", type=Path)
    ap.add_argument("--force", action="store_true", help="allow more than MAX_RETIRE retirements")
    a = ap.parse_args(argv)
    if a.portal_json:
        portal, crm = load_json(a.portal_json), load_json(a.crm_json)
    else:
        portal, crm = read_sheets()
    portal = whitelist(portal)
    if len(portal) < MIN_PORTAL_ROWS:
        raise SystemExit(f"Portal Backup returned {len(portal)} rows (< {MIN_PORTAL_ROWS}); refusing to sync.")
    p = plan(a.site, portal, crm)
    if len(p["retire"]) > MAX_RETIRE and not a.force:
        raise SystemExit(f"{len(p['retire'])} homes would be retired (> {MAX_RETIRE}); refusing without --force.")
    text = summary(p)
    print(text)
    if a.summary_out:
        a.summary_out.write_text(text, encoding="utf-8")
    if not a.dry_run and (p["add"] or p["update"] or p["retire"]):
        apply(a.site, p, a.lang)
    return 0


if __name__ == "__main__":
    sys.exit(main())
