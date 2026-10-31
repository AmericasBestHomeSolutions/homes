"""Homes that must never be on the site, whatever the Mac's master list or the portal says.

The list is data/excluded-homes.json (one entry per site id, with the reason). Every pass that
writes homes.js honors it: the Mac refresh's layout pass (scripts/refresh_listings.py here,
scripts/build_casas.py in casas) and the daily portal sync (scripts/portal_sync.py, on both
sites). Each run takes an excluded id out of homes.js and the sitemap, drops its Street View
image, and leaves <id>.html as a redirect to the home page, so old links still land somewhere.

To take a junk or duplicate id off both sites for good, add it to data/excluded-homes.json in
BOTH repos (homes and casas). To bring one back, delete its entry. This file is the same in both
repos; keep it that way.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

LIST = Path("data") / "excluded-homes.json"

REDIRECT = """<!DOCTYPE html>
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
TEXT = {
    "en": ("https://getownerfinancedhomes.com", "This home is no longer available", "See the homes available now"),
    "es": ("https://casasconfinanciamiento.com", "Esta casa ya no está disponible", "Vea las casas disponibles"),
}


def load(*roots: Path) -> dict[str, str]:
    """id -> reason, from data/excluded-homes.json under each root (missing files are fine)."""
    out: dict[str, str] = {}
    for root in roots:
        f = Path(root) / LIST
        if f.is_file():
            for e in json.loads(f.read_text(encoding="utf-8")):
                out[str(e["id"]).strip().lower()] = e.get("reason", "")
    return out


def _cut_blocks(text: str, ids: set[str]) -> tuple[str, list[str]]:
    removed = []
    for hid in sorted(ids):
        pat = re.compile(r"\n  \{\n    id: \"" + re.escape(hid) + r"\",[\s\S]*?\n  \},?(?=\n)")
        text, n = pat.subn("", text)
        if n:
            removed.append(hid)
    return text, removed


def _lang(root: Path) -> str:
    return "es" if (root / "como-funciona.html").is_file() else "en"


def apply(root: Path, lang: str | None = None, extra: tuple[Path, ...] = ()) -> list[str]:
    """Enforce the list on one site. Returns the ids taken out of homes.js this run."""
    root = Path(root)
    lang = lang or _lang(root)
    ids = set(load(root, *extra))
    if not ids:
        return []
    js = root / "homes.js"
    text = js.read_text(encoding="utf-8")
    text, removed = _cut_blocks(text, ids)
    if removed:
        count = len(re.findall(r'\n    id: "', text.split("const SOLD_CARDS")[0]))
        text = re.sub(r"\((\d+) live,", f"({count} live,", text, count=1)
        text = re.sub(r"\((\d+), generadas", f"({count}, generadas", text, count=1)
        js.write_text(text, encoding="utf-8")
    domain, title, link = TEXT[lang]
    page = REDIRECT.format(lang=lang, domain=domain, title=title, link=link)
    for hid in ids:
        f = root / f"{hid}.html"
        if not f.is_file() or f.read_text(encoding="utf-8") != page:
            f.write_text(page, encoding="utf-8")
        sv = root / "images" / "sv" / f"{hid}.jpg"
        if sv.is_file():
            sv.unlink()
    sm = root / "sitemap.xml"
    if sm.is_file():
        raw = sm.read_text(encoding="utf-8")
        kept = "".join(l for l in raw.splitlines(keepends=True) if not any(f"/{h}.html<" in l for h in ids))
        if kept != raw:
            sm.write_text(kept, encoding="utf-8")
    return removed


if __name__ == "__main__":
    import sys
    r = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    print("Excluded homes removed:", ", ".join(apply(r)) or "none")
