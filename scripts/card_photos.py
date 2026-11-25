#!/usr/bin/env python3
"""Card thumbnails and a photo manifest, written at sync/build time.

The homepage used to download every full-size cover (and 404 the missing ones)
just to learn which homes have a seller photo. This pass records that in homes.js
and writes a ~480px card image under images/cards/<id>.webp.

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
import json
import re
from pathlib import Path

CARD_WIDTH = 480
WEBP_QUALITY = 74
CACHE_VERSION = 1
FIELDS = ("hasPhoto", "photoCount", "cardPhoto", "cardWidth", "cardHeight")


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


def _encode(src: Path, dest: Path) -> tuple[int, int]:
    from PIL import Image, ImageOps

    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        image.thumbnail((CARD_WIDTH, CARD_WIDTH * 4), Image.Resampling.LANCZOS)
        width, height = image.size
        image.save(dest, "WEBP", quality=WEBP_QUALITY, method=4)
    return width, height


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
    }
    if src is None:
        dest = root / "images" / "cards" / f"{hid}.webp"
        if dest.is_file():
            dest.unlink()
        return fields, "none"
    dest = root / "images" / "cards" / f"{hid}.webp"
    rel = str(src.resolve().relative_to(root.resolve())).replace("\\", "/")
    fp = _fingerprint(src)
    previous = incoming.get(rel) or {}
    if (previous.get("fp") == fp and previous.get("w") and previous.get("h")
            and dest.is_file() and previous.get("out") == f"images/cards/{hid}.webp"):
        fields["cardPhoto"] = f"images/cards/{hid}.webp"
        fields["cardWidth"] = int(previous["w"])
        fields["cardHeight"] = int(previous["h"])
        outgoing[rel] = previous
        return fields, "cached"
    width, height = _encode(src, dest)
    fields["cardPhoto"] = f"images/cards/{hid}.webp"
    fields["cardWidth"] = width
    fields["cardHeight"] = height
    outgoing[rel] = {"fp": fp, "out": fields["cardPhoto"], "w": width, "h": height}
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
        for path in cards.glob("*.webp"):
            if path.stem not in ids:
                path.unlink()
                counts["removed"] += 1
    # Drop cache rows whose source was not used this run (manifest_for copied live ones).
    _save_cache(cache_path, new_cache)
    return counts
