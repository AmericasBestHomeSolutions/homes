"""Public sold-home policy for getownerfinancedhomes.com.

``scripts/refresh_listings.py`` and ``featured.py`` live on the owner's Mac
and are not in this repo. They own ``homes.js``, the per-home HTML files, and
``sitemap.xml``. This module is the policy they should call. ``--apply``
updates a checkout the same way, and is what the tests run against a
synthetic site.

Override file ``data/sold-overrides.json`` (Mac, not in this repo). Either a
dict keyed by home id or a list of records::

    { "decatur-il-1755-monroe": { "state": "pending", "soldOn": "2026-10-17" } }
    { "decatur-il-1755-monroe": "sold" }
    [ { "id": "decatur-il-1755-monroe", "state": "hold" } ]

States:

* ``sold`` and ``pending`` are publicly sold. A deposit (pending) is a sale.
  The home leaves ``HOMES``, search, and the map. It is not given a Pending tag.
* ``hold`` is not a sale. ``--apply`` leaves hold homes untouched so the Mac
  script can keep whatever it already does with hold.
* Removing the override relists the home, as long as the sheet row itself is
  not still marked pending or sold.

An old status of ``pending`` / ``Pending`` / ``sold`` with no override is
still publicly sold.

Sold cards (``SOLD_CARDS`` in homes.js) carry the street name and city only.
The photo is a copy under ``images/sold/<letters>.jpg``. The filename alphabet
has no digits, so a house number cannot appear in it. Cards do not link to
the old listing page.

Listing URLs that already exist are replaced with a noindex redirect to ``/``.
GitHub Pages cannot rewrite a URL without a file at that path, so the old
slug stays in the address bar for one hop and then leaves. The file body has
no address. New sales that never had a page do not get a new address URL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

_SUFFIXES = {
    "st", "street", "ave", "avenue", "rd", "road", "dr", "drive", "ln", "lane",
    "ct", "court", "blvd", "boulevard", "way", "pl", "place", "ter", "terrace",
    "pkwy", "parkway", "hwy", "highway", "cir", "circle", "trl", "trail",
}
_DIR = re.compile(
    r"^(?:N|S|E|W|NE|NW|SE|SW|North|South|East|West)\.?\s+(.+)$",
    re.IGNORECASE,
)
_HOUSE = re.compile(r"^#?\d+[A-Za-z]?(?:\s*-\s*\d+[A-Za-z]?)?\s+")
_HOUSE_TOKEN = re.compile(r"^(#?\d+[A-Za-z]?(?:\s*-\s*\d+[A-Za-z]?)?)")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PHOTO_ALPHABET = "abcdefghjkmnpqrstuvwxyz"


def street_name(address: str) -> str:
    """Street name only. Drops the house number and a leading compass point.

    ``1755 N Monroe St`` becomes ``Monroe St``. A leading compass word that
    is itself the street (``100 E St``, ``123 North St``) is kept.
    """
    if not address:
        return ""
    text = str(address).split(",")[0].strip()
    text = _HOUSE.sub("", text, count=1).strip()
    match = _DIR.match(text)
    if match:
        rest = match.group(1).strip()
        first = re.sub(r"[^A-Za-z]", "", (rest.split() or [""])[0]).lower()
        if first and first not in _SUFFIXES:
            text = rest
    words = []
    for word in text.strip().rstrip(".").split():
        if word[:1].islower():
            word = word[:1].upper() + word[1:]
        words.append(word)
    return " ".join(words).strip()


def house_number(address: str) -> str:
    text = str(address or "").split(",")[0].strip()
    match = _HOUSE_TOKEN.match(text)
    return match.group(1) if match else ""


def override_state(value) -> str | None:
    """Normalize one override to ``sold``, ``hold``, or None.

    ``pending`` becomes ``sold``.
    """
    if isinstance(value, dict):
        value = value.get("state", value.get("status", ""))
    text = str(value or "").strip().lower()
    if text in {"pending", "sold"}:
        return "sold"
    if text == "hold":
        return "hold"
    return None


def is_legacy_sold_status(status) -> bool:
    return str(status or "").strip().lower() in {"pending", "sold"}


def public_bucket(sheet_status, override) -> str:
    """Return ``active``, ``hold``, or ``sold`` for one Portal Mirror row."""
    state = override_state(override)
    if state == "sold" or is_legacy_sold_status(sheet_status):
        return "sold"
    if state == "hold":
        return "hold"
    return "active"


def sold_on_of(override) -> str:
    if not isinstance(override, dict):
        return ""
    raw = str(override.get("soldOn") or override.get("date") or "").strip()
    return raw if _DATE.fullmatch(raw) else ""


def load_overrides(path: Path) -> dict:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        homes = data.get("homes")
        if isinstance(homes, list):
            data = homes
        else:
            return {str(key): value for key, value in data.items()}
    out = {}
    if isinstance(data, list):
        for row in data:
            if isinstance(row, dict) and row.get("id"):
                out[str(row["id"])] = row
    return out


def public_photo_filename(home_id: str) -> str:
    """Letter-only filename. No digits, so a house number cannot show up."""
    digest = hashlib.sha256(
        b"abhs-sold-photo-v1\n" + str(home_id).encode("utf-8")
    ).digest()
    number = int.from_bytes(digest, "big")
    base = len(_PHOTO_ALPHABET)
    chars = []
    for _ in range(16):
        number, index = divmod(number, base)
        chars.append(_PHOTO_ALPHABET[index])
    return "".join(chars) + ".jpg"


def first_photo_path(home: dict, image_root: Path) -> Path | None:
    photos = home.get("photos") or []
    candidates = []
    if photos:
        candidates.append(str(photos[0]))
    hero = str(home.get("heroPhoto") or "").strip()
    if hero:
        candidates.append(hero)
    home_id = str(home.get("id") or "")
    if home_id:
        candidates.append(f"images/{home_id}.jpg")
    for rel in candidates:
        if not rel or rel.startswith(("/", "\\")) or ".." in Path(rel).parts:
            continue
        candidate = image_root / rel
        if candidate.is_file():
            return candidate
    return None


def build_sold_card(home: dict, *, override=None, image_root: Path, dest_dir: Path) -> dict | None:
    """Public card. Copies the front photo. Omits the card when there is no street."""
    street = street_name(home.get("address") or "")
    city = str(home.get("city") or "").strip()
    state = str(home.get("state") or "").strip()
    if not street or not city or not state:
        return None
    card = {"street": street, "city": city, "state": state}
    when = sold_on_of(override)
    if when:
        card["soldOn"] = when
    source = first_photo_path(home, image_root)
    home_id = str(home.get("id") or "")
    if source is not None and home_id:
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = public_photo_filename(home_id)
        shutil.copyfile(source, dest_dir / filename)
        card["photo"] = f"images/sold/{filename}"
    return card


def sold_redirect_html() -> str:
    """Listing stub. Intentionally takes no address arguments."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<meta name="robots" content="noindex, nofollow"/>
<title>This home has sold | Americas Best Home Solutions</title>
<link rel="canonical" href="https://getownerfinancedhomes.com/"/>
<meta http-equiv="refresh" content="0;url=/"/>
<script>location.replace("/");</script>
</head>
<body>
<p>This home has sold. <a href="/">See the homes available now</a>.</p>
</body>
</html>
"""


def _match_brace(text: str, open_at: int) -> int:
    depth = 0
    in_string = False
    escape = False
    quote = ""
    i = open_at
    while i < len(text):
        char = text[i]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                in_string = False
        else:
            if char in ('"', "'"):
                in_string = True
                quote = char
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise ValueError("unclosed object in homes.js")


def excise_homes(text: str, home_ids: set[str]) -> str:
    """Drop home objects from a homes.js source listing. Other homes stay put."""
    for home_id in sorted(home_ids):
        token = f'id: "{home_id}"'
        while True:
            found = text.find(token)
            if found < 0:
                break
            start = text.rfind("\n  {", 0, found)
            if start < 0:
                raise ValueError(f"could not find object start for {home_id}")
            brace = text.find("{", start)
            end = _match_brace(text, brace)
            cut = end + 1
            if cut < len(text) and text[cut] == ",":
                cut += 1
            if cut < len(text) and text[cut] == "\n":
                cut += 1
            text = text[: start + 1] + text[cut:]
    return text


def _js_card(card: dict) -> str:
    ordered = {"street": card["street"], "city": card["city"], "state": card["state"]}
    if card.get("soldOn"):
        ordered["soldOn"] = card["soldOn"]
    if card.get("photo"):
        ordered["photo"] = card["photo"]
    return json.dumps(ordered, ensure_ascii=False, separators=(", ", ": "))


def upsert_sold_cards(text: str, cards: list[dict]) -> str:
    body = "[\n" + "".join(f"  {_js_card(card)},\n" for card in cards) + "]"
    block = (
        "/* --- recently sold: street name and city only, never a house number --- */\n"
        f"const SOLD_CARDS = {body};\n"
    )
    existing = re.search(r"/\* --- recently sold:.*?\*/\nconst SOLD_CARDS = \[.*?\];\n", text, re.S)
    if existing:
        return text[: existing.start()] + block + text[existing.end() :]
    bare = re.search(r"const SOLD_CARDS = \[.*?\];\n", text, re.S)
    if bare:
        return text[: bare.start()] + block + text[bare.end() :]
    marker = "const RECENTLY_SOLD = "
    at = text.find(marker)
    if at < 0:
        return text + "\n" + block
    line_end = text.find("\n", at)
    if line_end < 0:
        line_end = len(text)
    return text[: line_end + 1] + "\n" + block + text[line_end + 1 :]


def read_catalog(homes_js: Path) -> dict:
    wrapper = r"""
const fs = require("fs");
const vm = require("vm");
const src = fs.readFileSync(process.argv[1], "utf8");
const out = vm.runInNewContext(
  "(function(){\n" + src + "\nreturn {HOMES, RECENTLY_SOLD: typeof RECENTLY_SOLD==='undefined'?[]:RECENTLY_SOLD, SOLD_CARDS: typeof SOLD_CARDS==='undefined'?[]:SOLD_CARDS};\n})()"
);
process.stdout.write(JSON.stringify(out));
"""
    result = subprocess.run(
        ["node", "-e", wrapper, str(homes_js)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def card_text(card: dict) -> str:
    return json.dumps(card, ensure_ascii=False)


def card_leaks(card: dict, *, house: str, address: str, home_id: str, source_photo: str = "") -> list[str]:
    """Return human-readable leaks. Empty means the card is safe to publish."""
    blob = card_text(card)
    leaks = []
    if address and address in blob:
        leaks.append("full address")
    if home_id and home_id in blob:
        leaks.append("home id")
    if source_photo and Path(source_photo).name in blob:
        leaks.append("source photo filename")
    photo = str(card.get("photo") or "")
    if photo and not re.fullmatch(r"images/sold/[a-z]{8,32}\.jpg", photo):
        leaks.append("photo path")
    if any(ch.isdigit() for ch in Path(photo).stem):
        leaks.append("digit in photo filename")
    if house and len(re.sub(r"\D", "", house)) >= 2 and house in blob:
        leaks.append("house number")
    allowed = {"street", "city", "state", "soldOn", "photo"}
    extra = set(card) - allowed
    if extra:
        leaks.append("extra fields " + ",".join(sorted(extra)))
    return leaks


def _merge_cards(existing: list[dict], fresh: list[dict]) -> list[dict]:
    merged = []
    seen = set()
    for card in list(existing) + list(fresh):
        if not isinstance(card, dict):
            continue
        key = (card.get("street"), card.get("city"), card.get("state"), card.get("photo") or "")
        if not card.get("street") or key in seen:
            continue
        seen.add(key)
        merged.append({k: card[k] for k in ("street", "city", "state", "soldOn", "photo") if card.get(k)})
    merged.sort(key=lambda card: (0 if card.get("photo") else 1, card.get("city") or "", card.get("street") or ""))
    return merged


def apply_site(root: Path, overrides_path: Path | None = None) -> dict:
    """Retire publicly sold homes in one checkout. Returns a small report.

    Hold homes are left as they are. Running again does not drop cards that
    were already published and does not rebuild listing pages that are gone.
    """
    root = root.resolve()
    homes_js = root / "homes.js"
    catalog = read_catalog(homes_js)
    overrides = load_overrides(overrides_path or (root / "data" / "sold-overrides.json"))
    sold_homes = [
        home for home in catalog["HOMES"]
        if public_bucket(home.get("status"), overrides.get(home["id"])) == "sold"
    ]
    fresh = []
    retired = []
    for home in sold_homes:
        card = build_sold_card(
            home,
            override=overrides.get(home["id"]),
            image_root=root,
            dest_dir=root / "images" / "sold",
        )
        if card:
            leaks = card_leaks(
                card,
                house=house_number(home.get("address") or ""),
                address=str(home.get("address") or ""),
                home_id=home["id"],
                source_photo=str((home.get("photos") or [""])[0]),
            )
            if leaks:
                raise SystemExit(f"refusing to publish a sold card: {', '.join(leaks)}")
            fresh.append(card)
        page = root / f"{home['id']}.html"
        if page.is_file():
            page.write_text(sold_redirect_html(), encoding="utf-8")
        retired.append(home["id"])
    if not retired:
        return {"retired": [], "cards": len(catalog.get("SOLD_CARDS") or [])}
    text = excise_homes(homes_js.read_text(encoding="utf-8"), set(retired))
    cards = _merge_cards(catalog.get("SOLD_CARDS") or [], fresh)
    text = upsert_sold_cards(text, cards)
    count = len(re.findall(r'\n    id: "', text))
    text = re.sub(
        r"/\* --- the homes \(\d+ live,",
        f"/* --- the homes ({count} live,",
        text,
        count=1,
    )
    homes_js.write_text(text, encoding="utf-8")
    sitemap = root / "sitemap.xml"
    if sitemap.is_file():
        lines = sitemap.read_text(encoding="utf-8").splitlines(keepends=True)
        kept = [line for line in lines if not any(f"/{home_id}.html" in line for home_id in retired)]
        sitemap.write_text("".join(kept), encoding="utf-8")
    return {"retired": retired, "cards": len(cards)}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Apply the public sold-home policy to a site checkout.")
    parser.add_argument("--apply", type=Path, help="Site root that contains homes.js")
    parser.add_argument("--overrides", type=Path, default=None)
    args = parser.parse_args(argv)
    if not args.apply:
        parser.error("pass --apply ROOT (tests import the functions directly)")
    report = apply_site(args.apply, args.overrides)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
