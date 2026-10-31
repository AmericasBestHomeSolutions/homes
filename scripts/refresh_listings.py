#!/usr/bin/env python3
"""Layout pass for getownerfinancedhomes.com.

The master spreadsheet still lives on the owner's Mac and is what rebuilds
homes.js. This script does three things that pass must keep doing:

1. Rewrite buyer-facing copy that asks people to text, call, or message us
   into a Book a Tour line, and remove seller-to-team notes ("Hi Team, ...
   Thank you so much!", a seller's preference about who lives there, requests
   for occupants' social security numbers). Those stay internal in the master
   list. The Mac refresh puts them back every day, so this post-pass has to
   remove them again. Legal pages and the SMS
   consent checkbox are not touched.

2. Record a listed date the first time a home id appears
   (data/listed-dates.json + listed-dates.js). Homes already in the catalog
   when dating started are stored as null, so they do not get a New badge.
   A real ISO date within the last 7 days is the only thing that badges a home.

3. Rewrite each <id>.html from home.html, keeping that page's canonical / Open
   Graph block and window.__HOME_ID__, then sanitize description meta tags.

Run from the repo root:  python3 scripts/refresh_listings.py
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATES = ROOT / "data" / "listed-dates.json"
JS_OUT = ROOT / "listed-dates.js"
HOMES_JS = ROOT / "homes.js"
HOME = ROOT / "home.html"
TODAY = date.today().isoformat()

# Longest first so "send us a text or a message" is not partly eaten by
# "send us a text". These are the buyer-facing invitations to text, call,
# or message the company. "Make your own call" does not match.
_PHRASES = (
    "send us a text or a message",
    "send us a text or message",
    "send a text or a message",
    "send a text or message",
    "send us a text",
    "send us a message",
    "send a text",
    "send a message",
    "reach out by text or message",
    "reach out by text or phone",
    "reach out by phone or text",
    "reach out by text",
    "reach out by phone",
    "text or message us",
    "message or text us",
    "call or text us",
    "text or call us",
    "give us a call or a text",
    "give us a call or text",
    "give us a text or a call",
    "give us a text or call",
    "give us a call",
    "give us a text",
    "give us a ring",
    "shoot us a text",
    "shoot us a message",
    "drop us a text",
    "drop us a message",
    "drop us a line",
    "email/call/text me",
    "call/text me",
    "text/call me",
    "call or text",
    "text or call",
    "text us",
    "call us",
    "message us",
)
_PHRASE_RE = re.compile(r"\b(?:" + "|".join(re.escape(p) for p in _PHRASES) + r")\b", re.I)
_FIELD_RE = re.compile(r'(\b(?:copy|description):\s*")((?:\\.|[^"\\])*)(")')
_META_RE = re.compile(r"<meta\b[^>]*>", re.I)
_META_NAME_RE = re.compile(
    r'\b(?:name|property)\s*=\s*"(?:description|og:description|twitter:description)"',
    re.I,
)
_META_CONTENT_RE = re.compile(r'(content=")([^"]*)(")')

# Seller-to-team notes that reach the public description through the master list.
# They stay internal in the master sheet but must never show on the site: a note to
# "Hi Team" with its sign-off, a seller's preference about who lives there, or a
# request for occupants' social security numbers. Only those pieces are removed;
# the rest of the description stays word for word.
_TEAM_NOTE = re.compile(
    r"(?is)\b(?:hi|hello|hey|dear)\s+team\b[\s,.!:]*.{0,600}?"
    r"\b(?:thank you so much|thank you|thanks so much|thanks)\b[\s.!,]*"
    r"(?-i:[A-Z][a-z'-]{0,20}(?:\s+[A-Z][a-z'-]{0,20})?\.(?=\s|$)\s*)?"
)
_TEAM_GREETING = re.compile(r"(?i)\b(?:hi|hello|hey|dear)\s+team\b[\s,.!:]*|\bhola\s+equipo\b[\s,.!:]*")
_INTERNAL = re.compile(
    r"(?i)prefer to put (?:in )?a family in this house|social security|seguro social|\bSSN\b|\d{3}-\d{2}-\d{4}"
    r"|please ask for (?:these|this|them) from the buyer|\bI require answering\b"
)
_SEGMENT = re.compile(r"[^.!?\n*•]*(?:[.!?]+|\n|\*|•|$)")


def strip_internal_notes(text: str) -> tuple[str, int]:
    """Remove seller-to-team notes. Returns the text and how many pieces were removed."""
    if not text:
        return text, 0
    count = 0

    def drop(_match: re.Match) -> str:
        nonlocal count
        count += 1
        return ""

    out = _TEAM_NOTE.sub(drop, text)
    out = _TEAM_GREETING.sub(drop, out)
    kept = []
    for match in _SEGMENT.finditer(out):
        piece = match.group(0)
        if piece and _INTERNAL.search(piece):
            count += 1
            continue
        kept.append(piece)
    out = "".join(kept)
    if count:
        out = re.sub(r"[ \t]{2,}", " ", out).strip()
        out = re.sub(r"^[\s.,;:*•-]+", "", out)
        out = re.sub(r"[\s,;:*•-]+$", "", out)
    return out, count


def sanitize_prose(text: str) -> tuple[str, int]:
    """Replace each text/call/message invitation with Book a Tour.

    The words around the invitation stay, so the rest of the description
    reads the same. A capitalized invitation, or one that starts a sentence,
    becomes "Book a Tour". One in the middle of a sentence becomes
    "book a Tour".
    """
    count = 0

    def repl(match: re.Match) -> str:
        nonlocal count
        count += 1
        raw = match.group(0)
        before = text[: match.start()]
        stripped = before.rstrip()
        sentence_start = stripped == "" or stripped[-1] in ".!?"
        if sentence_start or raw[:1].isupper():
            return "Book a Tour"
        return "book a Tour"

    return _PHRASE_RE.sub(repl, text), count


def sanitize_homes_js(text: str) -> tuple[str, int, int]:
    """Sanitize copy and description strings. Returns text, fields, phrases."""
    fields = 0
    phrases = 0

    def repl(match: re.Match) -> str:
        nonlocal fields, phrases
        body, n = sanitize_prose(match.group(2))
        body, notes = strip_internal_notes(body)
        if n or notes:
            fields += 1
            phrases += n + notes
        return match.group(1) + body + match.group(3)

    return _FIELD_RE.sub(repl, text), fields, phrases


def sanitize_meta_html(html: str) -> tuple[str, int]:
    """Sanitize description, og:description, and twitter:description."""
    phrases = 0

    def repl_tag(match: re.Match) -> str:
        nonlocal phrases
        tag = match.group(0)
        if not _META_NAME_RE.search(tag):
            return tag

        def repl_content(content: re.Match) -> str:
            nonlocal phrases
            body, n = sanitize_prose(content.group(2))
            body, notes = strip_internal_notes(body)
            n += notes
            if not n:
                return content.group(0)
            phrases += n
            return content.group(1) + body + content.group(3)

        return _META_CONTENT_RE.sub(repl_content, tag, count=1)

    return _META_RE.sub(repl_tag, html), phrases


def rewrite_homes_copy() -> tuple[int, int]:
    raw = HOMES_JS.read_text(encoding="utf-8")
    cleaned, fields, phrases = sanitize_homes_js(raw)
    if cleaned != raw:
        HOMES_JS.write_text(cleaned, encoding="utf-8")
    return fields, phrases


def home_ids() -> list[str]:
    text = (ROOT / "homes.js").read_text(encoding="utf-8")
    return re.findall(r'\bid:\s*"([^"]+)"', text)


def stamp_dates(ids: list[str]) -> dict:
    DATES.parent.mkdir(exist_ok=True)
    current: dict = {}
    if DATES.exists():
        current = json.loads(DATES.read_text(encoding="utf-8"))
    first_run = not DATES.exists()
    for hid in ids:
        if hid not in current:
            # First time we see the catalog: unknown dates, no New badges.
            # After that, a brand-new id is stamped today.
            current[hid] = None if first_run else TODAY
    # Drop ids that left the catalog so the file does not grow forever.
    for hid in list(current):
        if hid not in ids:
            current.pop(hid)
    DATES.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    lines = ["/* Generated by scripts/refresh_listings.py — do not hand-edit. */",
             "const LISTED_ON = " + json.dumps({k: v for k, v in current.items() if v}, indent=2) + ";"]
    # null dates are omitted; a missing key means no badge.
    JS_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return current


def emit_pages() -> int:
    template = HOME.read_text(encoding="utf-8")
    ids = set(home_ids())
    n = 0
    for path in sorted(ROOT.glob("*.html")):
        hid = path.stem
        if hid not in ids or path.name == "home.html":
            continue
        raw = path.read_text(encoding="utf-8")
        head = ""
        block = re.search(r'(<link rel="canonical"[\s\S]*?<meta name="twitter:image"[^>]*>)', raw)
        if block:
            head = "\n" + block.group(1)
        page = template
        desc = re.search(r'<meta name="description" content="[^"]*"/>', page)
        if desc and head and 'rel="canonical"' not in page:
            page = page.replace(desc.group(0), desc.group(0) + head, 1)
        marker = '<script src="homes.js"></script>'
        if 'window.__HOME_ID__="' not in page and marker in page:
            page = page.replace(marker, f'<script>window.__HOME_ID__="{hid}";</script>\n' + marker, 1)
        page, _meta_hits = sanitize_meta_html(page)
        path.write_text(page, encoding="utf-8")
        n += 1
    return n


def main() -> None:
    fields, phrases = rewrite_homes_copy()
    ids = home_ids()
    stamp_dates(ids)
    n = emit_pages()
    print(
        f"sanitized {phrases} text/call lines in {fields} home descriptions, "
        f"recorded {len(ids)} homes, rewrote {n} listing pages"
    )


if __name__ == "__main__":
    main()
