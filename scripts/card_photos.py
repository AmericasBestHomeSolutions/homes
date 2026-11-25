#!/usr/bin/env python3
"""Card thumbnails and a photo manifest, written at sync/build time.

The homepage used to download every full-size cover (and 404 the missing ones)
just to learn which homes have a seller photo. This pass records that in homes.js
and writes 320px and 480px card images (webp and jpeg) under images/cards/.

refresh_listings.py and portal_sync.py both call sync(), so the next portal run
reproduces the same fields and files. Unchanged sources are not re-encoded:
data/card-thumbs.json stores a content hash, not a timestamp, because git checkout
does not keep mtimes.

Street View files (images/sv/<id>.jpg) are not seller photos. They still get a
card thumbnail so the grid does not request a missing cover, and hasPhoto stays
false so those homes sort after homes with a real photo.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

CARD_WIDTHS = (320, 480)
CARD_WIDTH = 480
WEBP_QUALITY = 74
JPG_QUALITY = 76
CACHE_VERSION = 2
# Keep this string identical to CARD_SIZES in index.html.
CARD_SIZES = "(max-width: 860px) calc(100vw - 20px), 480px"
FIRST_SCREEN = 6
EAGER_CARDS = 2
FIELDS = ("hasPhoto", "photoCount", "cardPhoto", "cardWidth", "cardHeight", "cardW320")
FACES = (
    ("#15315e", "#2f5c96"), ("#15315e", "#24508a"), ("#1a4675", "#3a6bab"),
    ("#1c3f70", "#3f6db0"), ("#0f2444", "#24508a"), ("#1c4a7a", "#37639f"),
)
FEAT_ORDER = ("backyard", "fenced_yard", "basement", "garage", "central_air", "attic", "storage_shed", "off_street_parking")
FEAT_LABELS = {
    "backyard": "Backyard", "fenced_yard": "Fenced yard", "basement": "Basement", "garage": "Garage",
    "central_air": "Central air", "attic": "Attic", "storage_shed": "Storage", "off_street_parking": "Parking",
}


def truthy_flag(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def has_real_photo(home: dict) -> bool:
    """Seller photo on disk. Street View alone is not a real photo."""
    return truthy_flag(home.get("hasPhoto"))


def listing_sort_key(home: dict):
    """Default city-page order: real photos, then street view / none, then address."""
    return (0 if has_real_photo(home) else 1, (home.get("address") or "").lower(), home.get("id") or "")


def _split(text: str) -> tuple[str, str]:
    mark = "const SOLD_CARDS"
    if mark in text:
        head, tail = text.split(mark, 1)
        return head, mark + tail
    return text, ""


def _photos(block: str) -> list[str]:
    match = re.search(r"\n    photos:\s*(\[[\s\S]*?\])\s*,", block)
    if not match:
        return []
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return f"{path.stat().st_size}:{digest.hexdigest()}"


def _add(found: list[Path], seen: set[Path], path: Path) -> None:
    if not path.is_file():
        return
    resolved = path.resolve()
    if resolved in seen or resolved.parent.name == "sv":
        return
    seen.add(resolved)
    found.append(resolved)


def real_files(root: Path, hid: str, hero: str, photos: list[str]) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    if hero and not hero.startswith(("http://", "https://")):
        _add(found, seen, root / hero)
    _add(found, seen, root / "images" / f"{hid}.jpg")
    for rel in photos:
        if rel and not rel.startswith(("http://", "https://")):
            _add(found, seen, root / rel)
    number = 1
    while True:
        path = root / "images" / f"{hid}-{number}.jpg"
        if not path.is_file():
            break
        _add(found, seen, path)
        number += 1
    return found


def card_source(root: Path, hid: str, hero: str, photos: list[str], real: list[Path]) -> tuple[str, Path | None]:
    """('photo'|'street'|'none', file to shrink). Prefer the seller cover."""
    if hero and not hero.startswith(("http://", "https://")):
        hero_path = root / hero
        if hero_path.is_file() and hero_path.resolve().parent.name != "sv":
            return "photo", hero_path
    cover = root / "images" / f"{hid}.jpg"
    if cover.is_file():
        return "photo", cover
    if real:
        return "photo", real[0]
    street = root / "images" / "sv" / f"{hid}.jpg"
    if street.is_file():
        return "street", street
    return "none", None


def _card_names(hid: str) -> list[str]:
    names = [f"{hid}.webp"]
    for width in CARD_WIDTHS:
        names.append(f"{hid}-{width}.webp")
        names.append(f"{hid}-{width}.jpg")
    return names


def _remove_cards(root: Path, hid: str) -> None:
    folder = root / "images" / "cards"
    for name in _card_names(hid):
        path = folder / name
        if path.is_file():
            path.unlink()


def _encode(root: Path, hid: str, src: Path) -> dict:
    """Write each width as webp and jpeg. Skip a width that would duplicate a smaller one."""
    from PIL import Image, ImageOps

    folder = root / "images" / "cards"
    folder.mkdir(parents=True, exist_ok=True)
    made: dict[int, tuple[int, int]] = {}
    with Image.open(src) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode != "RGB":
            image = image.convert("RGB")
        large = image.copy()
        large.thumbnail((480, 480 * 4), Image.Resampling.LANCZOS)
        width, height = large.size
        large.save(folder / f"{hid}-480.webp", "WEBP", quality=WEBP_QUALITY, method=4)
        large.save(folder / f"{hid}-480.jpg", "JPEG", quality=JPG_QUALITY, optimize=True, progressive=True)
        made[480] = (width, height)
        # A second file only when it is actually smaller, so srcset widths stay distinct.
        if width > 320:
            small = image.copy()
            small.thumbnail((320, 320 * 4), Image.Resampling.LANCZOS)
            made[320] = small.size
            small.save(folder / f"{hid}-320.webp", "WEBP", quality=WEBP_QUALITY, method=4)
            small.save(folder / f"{hid}-320.jpg", "JPEG", quality=JPG_QUALITY, optimize=True, progressive=True)
    return made


def _literal(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value)
    return str(int(value))


def _strip_fields(block: str) -> str:
    for key in FIELDS:
        block = re.sub(rf"\n    {key}:\s*(?:\"(?:\\.|[^\"\\])*\"|[^,\n]*),", "", block, count=1)
    return block


def _insert_fields(block: str, fields: dict) -> str:
    block = _strip_fields(block)
    lines = [f"    {key}: {_literal(fields[key])}," for key in FIELDS]
    needle = "\n  },"
    index = block.rfind(needle)
    if index < 0:
        return block
    return block[:index] + "\n" + "\n".join(lines) + block[index:]


def _variants_ready(root: Path, hid: str, info: dict) -> bool:
    folder = root / "images" / "cards"
    if not (folder / f"{hid}-480.webp").is_file() or not (folder / f"{hid}-480.jpg").is_file():
        return False
    if info.get("w320") and not (folder / f"{hid}-320.webp").is_file():
        return False
    if info.get("w320") and not (folder / f"{hid}-320.jpg").is_file():
        return False
    return True


def _apply_cached(fields: dict, hid: str, info: dict) -> None:
    fields["cardPhoto"] = f"images/cards/{hid}-480.webp"
    fields["cardWidth"] = int(info["w"])
    fields["cardHeight"] = int(info["h"])
    fields["cardW320"] = int(info.get("w320") or 0)


def manifest_for(root: Path, hid: str, block: str, incoming: dict, outgoing: dict) -> tuple[dict, str]:
    """Return homes.js fields and 'encoded', 'cached', or 'none'."""
    import portal_sync as ps

    hero = ps.field(block, "heroPhoto") or ""
    if not isinstance(hero, str):
        hero = ""
    photos = _photos(block)
    real = real_files(root, hid, hero, photos)
    kind, src = card_source(root, hid, hero, photos, real)
    fields = {
        "hasPhoto": kind == "photo",
        "photoCount": len(real),
        "cardPhoto": "",
        "cardWidth": 0,
        "cardHeight": 0,
        "cardW320": 0,
    }
    if src is None:
        _remove_cards(root, hid)
        return fields, "none"
    rel = str(src.resolve().relative_to(root.resolve())).replace("\\", "/")
    fp = _fingerprint(src)
    previous = incoming.get(rel) or {}
    if previous.get("fp") == fp and previous.get("w") and _variants_ready(root, hid, previous):
        _apply_cached(fields, hid, previous)
        outgoing[rel] = previous
        return fields, "cached"
    made = _encode(root, hid, src)
    large = made.get(480) or made[max(made)]
    small = made.get(320)
    fields["cardPhoto"] = f"images/cards/{hid}-480.webp"
    fields["cardWidth"] = large[0]
    fields["cardHeight"] = large[1]
    fields["cardW320"] = small[0] if small else 0
    outgoing[rel] = {
        "fp": fp,
        "out": fields["cardPhoto"],
        "w": large[0],
        "h": large[1],
        "w320": fields["cardW320"],
    }
    # A source narrower than 320 only produces the 480-named file. Drop a stale 320 pair.
    if not small:
        for suffix in (".webp", ".jpg"):
            stale = root / "images" / "cards" / f"{hid}-320{suffix}"
            if stale.is_file():
                stale.unlink()
    return fields, "encoded"


def _load_cache(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if data.get("v") != CACHE_VERSION or data.get("width") != CARD_WIDTH or data.get("quality") != WEBP_QUALITY:
        return {}
    items = data.get("items")
    return dict(items) if isinstance(items, dict) else {}


def _save_cache(path: Path, items: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"v": CACHE_VERSION, "width": CARD_WIDTH, "quality": WEBP_QUALITY, "items": items}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sync(root: Path) -> dict:
    """Write images/cards/<id>.webp and hasPhoto / photoCount / cardPhoto on each home."""
    import portal_sync as ps

    root = Path(root)
    js = root / "homes.js"
    text = js.read_text(encoding="utf-8")
    head, tail = _split(text)
    blocks = ps.blocks(head)
    cache_path = root / "data" / "card-thumbs.json"
    old_cache = _load_cache(cache_path)
    new_cache: dict = {}
    counts = {"homes": 0, "real": 0, "street": 0, "none": 0, "encoded": 0, "cached": 0, "removed": 0}
    ids = set()
    for hid, match in blocks.items():
        ids.add(hid)
        fields, how = manifest_for(root, hid, match.group(0), old_cache, new_cache)
        counts["homes"] += 1
        if how == "encoded":
            counts["encoded"] += 1
        elif how == "cached":
            counts["cached"] += 1
        if fields["hasPhoto"]:
            counts["real"] += 1
        elif fields["cardPhoto"]:
            counts["street"] += 1
        else:
            counts["none"] += 1
        updated = _insert_fields(match.group(0), fields)
        if updated != match.group(0):
            head = head.replace(match.group(0), updated, 1)
    written = head + tail
    if written != text:
        js.write_text(written, encoding="utf-8")
    cards = root / "images" / "cards"
    if cards.is_dir():
        keep = {name for hid in ids for name in _card_names(hid) if name != f"{hid}.webp"}
        for path in cards.iterdir():
            if path.suffix.lower() in {".webp", ".jpg"} and path.name not in keep:
                path.unlink()
                counts["removed"] += 1
    # Drop cache rows whose source was not used this run (manifest_for copied live ones).
    _save_cache(cache_path, new_cache)
    return counts


def _features(block: str) -> dict:
    match = re.search(r"\n    features:\s*\{([^}]*)\}", block)
    if not match:
        return {}
    return dict(re.findall(r"([A-Za-z0-9_]+):\s*\"([^\"]*)\"", match.group(1)))


def _listed(root: Path) -> dict[str, str]:
    path = root / "listed-dates.js"
    if not path.is_file():
        return {}
    return dict(re.findall(r'"([^"]+)": "([^"]+)"', path.read_text(encoding="utf-8")))


def _listed_time(raw: str) -> float:
    if not raw:
        return 0.0
    try:
        return datetime.fromisoformat(raw).timestamp()
    except ValueError:
        return 0.0


def public_homes(root: Path) -> list[dict]:
    """Live homes in homes.js order, with the card fields the homepage sorts on."""
    import portal_sync as ps

    text = (root / "homes.js").read_text(encoding="utf-8")
    head, _tail = _split(text)
    homes = []
    for hid, match in ps.blocks(head).items():
        block = match.group(0)
        status = ps.field(block, "status") or "Available"
        if str(status).strip().lower() == "sold":
            continue

        def num(key, block=block):
            raw = ps.field(block, key)
            try:
                return int(float(raw))
            except (TypeError, ValueError):
                return 0

        homes.append({
            "id": hid,
            "address": ps.field(block, "address") or "",
            "city": ps.field(block, "city") or "",
            "state": ps.field(block, "state") or "",
            "beds": ps.field(block, "beds"),
            "baths": ps.field(block, "baths"),
            "sqft": ps.field(block, "sqft") or "",
            "status": status,
            "monthlyPayment": ps.field(block, "monthlyPayment"),
            "moveIn": ps.field(block, "moveIn"),
            "hasPhoto": ps.field(block, "hasPhoto"),
            "cardPhoto": ps.field(block, "cardPhoto") or "",
            "cardWidth": num("cardWidth"),
            "cardHeight": num("cardHeight"),
            "cardW320": num("cardW320"),
            "photos": _photos(block),
            "features": _features(block),
            "contractor": ps.field(block, "contractor"),
        })
    return homes


def default_order(root: Path, today: date | None = None) -> list[dict]:
    """Homepage order before a visitor location arrives: seller photos, then newest."""
    listed = _listed(root)
    homes = public_homes(root)

    def key(item):
        index, home = item
        photo = 0 if has_real_photo(home) else 1
        when = _listed_time(listed.get(home["id"]) or "")
        address = 1 if home.get("address") else 0
        return (photo, -when, -address, index)

    return [home for _index, home in sorted(enumerate(homes), key=key)]


def _srcset(home: dict) -> tuple[str, str, str]:
    hid = home["id"]
    webp, jpg = [], []
    if home.get("cardW320"):
        webp.append(f"images/cards/{hid}-320.webp {int(home['cardW320'])}w")
        jpg.append(f"images/cards/{hid}-320.jpg {int(home['cardW320'])}w")
    if home.get("cardWidth"):
        webp.append(f"images/cards/{hid}-480.webp {int(home['cardWidth'])}w")
        jpg.append(f"images/cards/{hid}-480.jpg {int(home['cardWidth'])}w")
    fallback = f"images/cards/{hid}-480.jpg" if home.get("cardPhoto") else ""
    return ", ".join(webp), ", ".join(jpg), fallback


def _face(seed: str) -> tuple[str, str]:
    value = 0
    for ch in seed or "":
        value = (value * 31 + ord(ch)) & 0xFFFFFFFF
    return FACES[value % len(FACES)]


def _money(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if not number:
        return ""
    return f"${round(number):,}"


def _sqft(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if not number:
        return ""
    return f"{int(number):,}" if number == int(number) else f"{number:,}"


def _tag(home: dict, listed: dict[str, str], today: date) -> str:
    raw = listed.get(home["id"]) or ""
    if raw:
        try:
            listed_on = date.fromisoformat(raw[:10])
        except ValueError:
            listed_on = None
        if listed_on and today - listed_on <= timedelta(days=7):
            return "New"
    if home.get("contractor"):
        return "Needs work"
    features = home.get("features") or {}
    for key in FEAT_ORDER:
        if features.get(key) == "yes":
            return FEAT_LABELS[key]
    return ""


def _card_html(home: dict, index: int, listed: dict[str, str], today: date) -> str:
    city, state = home.get("city") or "", home.get("state") or ""
    pending = str(home.get("status") or "").strip().lower() == "pending"
    classes = "card"
    if home.get("contractor"):
        classes += " is-cs"
    if pending:
        classes += " is-pending"
    a, b = _face(city + state)
    bits = []
    beds, baths = home.get("beds"), home.get("baths")
    if beds not in (None, "", 0, "0"):
        bits.append(f"{beds} bd" if str(beds) == "1" else f"{beds} bds")
    if baths not in (None, "", 0, "0"):
        bits.append(f"{baths} ba")
    sqft = _sqft(home.get("sqft"))
    if sqft:
        bits.append(f"{sqft} sqft")
    where = ", ".join(part for part in (home.get("address") or "", city, state) if part)
    webp, jpg, fallback = _srcset(home)
    eager = index < EAGER_CARDS and webp
    attrs = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
    picture = ""
    if webp and jpg and fallback:
        picture = (
            f'<picture><source type="image/webp" srcset="{html.escape(webp, quote=True)}" sizes="{CARD_SIZES}">'
            f'<img src="{html.escape(fallback, quote=True)}" srcset="{html.escape(jpg, quote=True)}" sizes="{CARD_SIZES}" '
            f'alt="Home in {html.escape(city, quote=True)}, {html.escape(state, quote=True)}" '
            f'width="{int(home.get("cardWidth") or 480)}" height="{int(home.get("cardHeight") or 360)}" {attrs}></picture>'
        )
    street = picture and not has_real_photo(home)
    badge = '<span class="sv-badge">Street view · © Google</span>' if street else '<span class="sv-badge" hidden>Street view · © Google</span>'
    dots = ""
    count = min(6, len(home.get("photos") or []))
    if count > 1:
        marks = "".join('<i class="on"></i>' if i == 0 else "<i></i>" for i in range(count))
        dots = f'<span class="pdots">{marks}</span>'
    tag = "" if pending else _tag(home, listed, today)
    flag = '<span class="status-tag pending">Pending</span>' if pending else (f'<span class="z-feat">{html.escape(tag)}</span>' if tag else "")
    heart = (
        f'<button type="button" class="hc-heart" data-save="{html.escape(home["id"], quote=True)}" '
        f'aria-pressed="false" aria-label="Save" title="Save"><span class="hc-ic">♡</span></button>'
    )
    price = _money(home.get("monthlyPayment"))
    down = _money(home.get("moveIn"))
    down_html = f'<div class="card-down">{down} down</div>' if down else ""
    return (
        f'<a class="{classes}" data-hid="{html.escape(home["id"], quote=True)}" data-static="1" href="{html.escape(home["id"], quote=True)}.html">'
        f'<div class="card-face" style="background:linear-gradient(135deg,{a},{b})">{picture}{badge}{dots}{flag}{heart}</div>'
        f'<div class="card-body"><div class="card-price"><span class="num">{price}</span><span class="per">/mo</span></div>'
        f'<div class="card-specs">{html.escape(" | ".join(bits))}</div>'
        f'<div class="card-where">{html.escape(where)}</div>{down_html}</div></a>'
    )


def _preload(home: dict) -> str:
    webp, _jpg, _fallback = _srcset(home)
    if not webp:
        return ""
    href = f"images/cards/{home['id']}-480.webp"
    return (
        f'<link rel="preload" as="image" type="image/webp" fetchpriority="high" href="{href}" '
        f'imagesrcset="{html.escape(webp, quote=True)}" imagesizes="{CARD_SIZES}">'
    )


def _replace_marked(text: str, start: str, end: str, block: str, anchor: str) -> str:
    pattern = re.compile(re.escape(start) + r"[\s\S]*?" + re.escape(end))
    wrapped = f"{start}\n{block}\n{end}" if block else f"{start}\n{end}"
    if pattern.search(text):
        return pattern.sub(lambda _m: wrapped, text, count=1)
    if anchor not in text:
        return text
    return text.replace(anchor, anchor + "\n" + wrapped, 1)


def stamp_first_screen(root: Path, limit: int = FIRST_SCREEN, today: date | None = None) -> int:
    """Write the first screen of homepage cards into index.html so they do not wait on homes.js."""
    root = Path(root)
    index = root / "index.html"
    if not index.is_file() or not (root / "homes.js").is_file():
        return 0
    today = today or date.today()
    homes = [home for home in default_order(root) if home.get("cardPhoto")][:limit]
    # A home with no card still belongs in the order; keep it so the static prefix matches JS.
    if len(homes) < limit:
        homes = default_order(root)[:limit]
    listed = _listed(root)
    cards = "\n".join(_card_html(home, i, listed, today) for i, home in enumerate(homes))
    preloads = "\n".join(link for link in (_preload(home) for home in homes[:EAGER_CARDS]) if link)
    text = index.read_text(encoding="utf-8")
    text = _replace_marked(text, "<!-- lcp-preload:start -->", "<!-- lcp-preload:end -->", preloads,
                           '<meta name="viewport" content="width=device-width, initial-scale=1.0"/>')
    # The viewport replace puts the marker AFTER the anchor line only if we prepend wrong.
    # _replace_marked inserts wrapped + anchor, so the marker lands before the viewport tag.
    # Move it to just after the viewport when it was newly inserted in front.
    text = _replace_marked(
        text, "<!-- first-cards:start -->", "<!-- first-cards:end -->", cards,
        '<div class="cards" id="cards">',
    )
    # _replace_marked inserts BEFORE the cards div. Put the cards inside it instead.
    text = text.replace(
        "<!-- first-cards:start -->\n" + cards + "\n<!-- first-cards:end -->\n" + '<div class="cards" id="cards">',
        '<div class="cards" id="cards">\n<!-- first-cards:start -->\n' + cards + "\n<!-- first-cards:end -->",
        1,
    )
    if text != index.read_text(encoding="utf-8"):
        index.write_text(text, encoding="utf-8")
    return len(homes)
