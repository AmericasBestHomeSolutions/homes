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

Cameron's portal is the master for status (Joe's rule): a home the portal shows Available is
listed even when CRM_Properties says SOLD / PENDING, and that home's "recently sold" card is
taken down (only when no other closed home shares its street and city). Those relists are
listed in the summary so the CRM row can be corrected. It never adds a home with no price or
monthly payment; those are listed under "check by hand".

Columns: only Portal Backup A:M (Portal PROP id .. Date listed), its 'Photos link' column (found by
header name; Grok Bot's daily portal backup copies the portal's per-home photos link there), the photo links in R,
CRM_Properties A:F (Unique ID .. Property Status), and WhatsApp Intel B:D (address) plus the
album links in J (Photos) are requested from Google, so lockbox, seller and phone columns are
never downloaded, let alone written.

Photos: a home with no seller photos gets them from, in order, the portal's 'Photos link', a link
in the portal note (R), or a WhatsApp Intel album link for the same address. The first source that
yields photos wins. Readable without any login: public Google Drive folders, Dropbox, bit.ly to
any of these, public Google Photos albums, iCloud shared albums and iCloud photo links (share.icloud.com), public OneDrive folders,
viewthehomeonline.com listing pages, and a Google Doc that is only photos (no text).
A link that yields nothing (album no longer shared, a map pin, a CRM dashboard) is listed in the summary for a
browser pass or a new link. At most MAX_PHOTO_HOMES albums (and PHOTO_BUDGET_S seconds) per run; the
rest are picked up on later runs. Real photos replace the Street View fallback image.

Credentials: env GOOGLE_SERVICE_ACCOUNT_JSON (the key JSON, a GitHub Actions secret).
Offline: --portal-json / --crm-json (lists of row dicts) instead of the Sheets API.

    python3 scripts/portal_sync.py --dry-run            # print the change summary, write nothing
    python3 scripts/portal_sync.py --summary-out /tmp/s # apply, write the commit message
    python3 <homes>/scripts/portal_sync.py --site . --lang es   # the Spanish site (casas)

Afterwards run the site's own post-pass (scripts/refresh_listings.py or
scripts/build_casas.py) so pages are rebuilt from home.html and dates are stamped.

Homes listed in data/excluded-homes.json (junk or duplicate ids) are taken off the site on
every run and never added back; see scripts/excluded_homes.py.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import excluded_homes  # noqa: E402  data/excluded-homes.json: ids never put on either site

SHEET_ID = "1QDLFUiBFDrKdTnhnRUHUr_pErOpNsDhnZD9AA7vRBQs"
PORTAL_RANGE = "'Portal Backup'!A:M"     # stops before Lockbox code (N)
HEADER_RANGE = "'Portal Backup'!1:1"     # header names only, to find the 'Photos link' column
PHOTOS_HEADER = "photos link"             # Grok Bot's portal backup writes the portal's photos link here
NOTE_RANGE = "'Portal Backup'!R:R"       # Listing note: only photo links are taken from it, the text is never published
CRM_RANGE = "'CRM_Properties'!A:F"        # Unique ID .. Property Status only
WA_ADDR_RANGE = "'WhatsApp Intel'!B:D"    # Address, City, ST
WA_PHOTO_RANGE = "'WhatsApp Intel'!J:J"   # Photos: album links posted in the group (only links are kept)
MAX_PHOTO_HOMES = 15   # homes whose albums are downloaded per run; the rest wait for the next run
PHOTO_BUDGET_S = 600   # stop starting new album downloads after 10 minutes (workflow timeout is 20)
PORTAL_COLUMNS = ("Portal PROP id", "Address", "City", "State", "Zip", "Status", "Beds", "Baths", "Sqft",
                  "Price", "Down payment", "Monthly payment", "Date listed", "Portal photos", "Photo links")
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


def read_sheets() -> tuple[list[dict], list[dict], list[dict]]:
    info = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not info:
        raise SystemExit("GOOGLE_SERVICE_ACCOUNT_JSON is not set (GitHub secret). Use --portal-json for offline runs.")
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    creds = service_account.Credentials.from_service_account_info(
        json.loads(info), scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    creds.refresh(Request())

    def batch(ranges):
        query = urllib.parse.urlencode([("ranges", r) for r in ranges] + [("majorDimension", "ROWS")])
        req = urllib.request.Request(f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values:batchGet?{query}",
                                     headers={"Authorization": f"Bearer {creds.token}"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return [r.get("values") or [] for r in json.load(resp)["valueRanges"]]

    # Find 'Photos link' by its header name, then request that one column (never the lockbox/seller ones).
    header = (batch([HEADER_RANGE])[0] or [[]])[0]
    photos_range = photos_column_range(header)
    ranges = [PORTAL_RANGE, CRM_RANGE, NOTE_RANGE, WA_ADDR_RANGE, WA_PHOTO_RANGE] + ([photos_range] if photos_range else [])
    got = batch(ranges)
    portal_v, crm_v, note_v, wa_addr_v, wa_photo_v = got[:5]
    photo_v = got[5] if photos_range else []
    portal, crm = _rows(portal_v), _rows(crm_v)
    # Same row order as A:M (all ranges start at row 1); keep only the links from each cell.
    notes = [(row[0] if row else "") for row in note_v[1:]]
    plinks = [(row[0] if row else "") for row in photo_v[1:]]
    by_row = {}
    for i, v in enumerate(portal_v[1:]):
        if any(str(c).strip() for c in v):
            by_row[len(by_row)] = (" ".join(album_links(plinks[i] if i < len(plinks) else "")),
                                   " ".join(photo_links(notes[i] if i < len(notes) else "")))
    for i, row in enumerate(portal):
        row["Portal photos"], row["Photo links"] = by_row.get(i, ("", ""))
    return portal, crm, wa_rows(wa_addr_v, wa_photo_v)


def col_letter(i: int) -> str:
    out = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        out = chr(65 + r) + out
    return out


def photos_column_range(header: list) -> str | None:
    """'Portal Backup'!V:V (or wherever the 'Photos link' header is), or None before the column exists."""
    for i, h in enumerate(header):
        if str(h).strip().lower() == PHOTOS_HEADER and i > 12:   # never one of A:M's own columns
            return f"'Portal Backup'!{col_letter(i)}:{col_letter(i)}"
    return None


def wa_rows(addr_v, photo_v) -> list[dict]:
    """WhatsApp Intel rows that carry a usable album link: address, city, state and the links only."""
    out = []
    for i, row in enumerate(addr_v[1:], 1):
        cell = photo_v[i][0] if i < len(photo_v) and photo_v[i] else ""
        links = photo_links(cell)
        if links and row and str(row[0]).strip():
            out.append({"Address": str(row[0]).strip(), "City": str(row[1]).strip() if len(row) > 1 else "",
                        "State": str(row[2]).strip() if len(row) > 2 else "", "links": links})
    return out


def load_json(path: str | None) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else []


def whitelist(rows: list[dict]) -> list[dict]:
    out = [{k: str(r.get(k) or "").strip() for k in PORTAL_COLUMNS} for r in rows]
    for r, src in zip(out, rows):   # offline JSON may carry the raw note / link cell; keep only links
        if not r["Photo links"] and src.get("Listing note"):
            r["Photo links"] = " ".join(photo_links(src["Listing note"]))
        if not r["Portal photos"] and src.get("Photos link"):
            r["Portal photos"] = " ".join(album_links(src["Photos link"]))
    return out


# ---------- photos ----------
# Sellers put a photo link in the portal's Listing note: a public Google Drive folder, a Dropbox
# file or zip (dl=1), or a direct image URL. iCloud shared albums are not supported (no plain URL).
SHORT_HOSTS = {"bit.ly", "www.bit.ly"}   # resolved at download time; used only if it lands on Drive/Dropbox
LINK_RE = re.compile(r"https?://[^\s\"'<>]+")
MAX_PHOTOS = 30
MAX_SIDE = 1280        # same as the existing images/ files (960x1280 portrait, progressive JPEG)
UA = {"User-Agent": "Mozilla/5.0 (portal-sync; +https://getownerfinancedhomes.com)"}


def photo_links(note: str) -> list[str]:
    """Album links we can read without a login, in the order they appear."""
    links = []
    for url in LINK_RE.findall(note or ""):
        url = url.rstrip(".,);>")
        host = urllib.parse.urlparse(url).netloc.lower()
        if ("drive.google.com" in host and "/folders/" in url) or "dropbox.com" in host or host in SHORT_HOSTS \
                or _is_gphotos(url) or _is_icloud(url) or _is_onedrive(url) or _is_tour(url) or _is_gdoc(url) \
                or re.search(r"\.(jpe?g|png|webp)(\?|$)", url, re.I):
            if url not in links:
                links.append(url)
    return links


def album_links(cell: str) -> list[str]:
    """The portal's 'Photos link' cell: readable links as above, plus any other link (OneDrive, a doc,
    a tour site) so it can be listed for a browser pass instead of silently dropped."""
    links = photo_links(cell)
    for url in LINK_RE.findall(cell or ""):
        url = url.rstrip(".,);>")
        if url not in links:
            links.append(url)
    return links


def _is_gphotos(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return host == "photos.app.goo.gl" or (host == "photos.google.com" and "/share/" in url)


def _is_icloud(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return host == "share.icloud.com" or (host.endswith("icloud.com") and ("sharedalbum" in url or "icloudlinks" in url))


def _is_onedrive(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return host == "1drv.ms" or host.endswith("onedrive.live.com")


def _is_tour(url: str) -> bool:
    """viewthehomeonline.com listing page (the seller's own tour site)."""
    return urllib.parse.urlparse(url).netloc.lower().endswith("viewthehomeonline.com") and bool(re.search(r"/(\d{5,})", url))


def _is_gdoc(url: str) -> bool:
    return "docs.google.com" in urllib.parse.urlparse(url).netloc.lower() and "/document/d/" in url


def readable(url: str) -> bool:
    return bool(photo_links(url))


def _get(url: str, timeout=60) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as resp:
        return resp.read()


def _drive_folder(url: str, depth: int = 0) -> list[bytes]:
    folder = re.search(r"/folders/([A-Za-z0-9_-]+)", url).group(1)
    page = _get(f"https://drive.google.com/drive/folders/{folder}").decode("utf-8", "replace")
    ids, subfolders = [], []
    for m in re.finditer(r'data-id="([A-Za-z0-9_-]{25,})"', page):
        nxt = page.find('data-id="', m.end())
        chunk = page[m.end():nxt if nxt > 0 else m.end() + 4000]
        label = re.search(r'aria-label="([^"]*)"', chunk)
        label = label.group(1) if label else ""
        if m.group(1) in ids or m.group(1) in (f for f, _ in subfolders):
            continue
        if re.search(r"\.(?:jpe?g|png|webp|heic)\b", label, re.I):
            ids.append(m.group(1))
        elif label.endswith("folder") and m.group(1) != folder:
            subfolders.append((m.group(1), label))
    if not ids and subfolders and depth == 0:
        # e.g. "New Pictures" / "Old Pictures+Video": newest first
        subfolders.sort(key=lambda f: (0 if re.search(r"(?i)\bnew\b", f[1]) else 1))
        for sub, _label in subfolders:
            got = _drive_folder(f"https://drive.google.com/drive/folders/{sub}", depth + 1)
            if got:
                return got
        return []
    return [_get(f"https://drive.usercontent.google.com/download?id={i}&export=download") for i in ids[:MAX_PHOTOS]]


def _dropbox(url: str) -> list[bytes]:
    import io
    import zipfile
    parts = urllib.parse.urlparse(url)
    q = dict(urllib.parse.parse_qsl(parts.query))
    q["dl"] = "1"
    data = _get(urllib.parse.urlunparse(parts._replace(query=urllib.parse.urlencode(q))), timeout=180)
    if data.startswith(b"[InternetShortcut]"):   # a .url file pointing at the real album
        m = re.search(rb"URL=(\S+)", data)
        inner = m.group(1).decode("utf-8", "replace") if m else ""
        return download_photos([inner]) if inner and "dropbox.com" not in inner and readable(inner) else []
    if data[:2] != b"PK":
        return [data]
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = sorted(n for n in z.namelist() if re.search(r"\.(jpe?g|png|webp)$", n, re.I) and "__MACOSX" not in n)
        return [z.read(n) for n in names[:MAX_PHOTOS]]


# Google Photos: a public shared album is a plain web page that lists every photo as
# lh3.googleusercontent.com/pw/<id>; "=w2048" returns that photo as a JPEG. The photos.app.goo.gl
# short link only redirects for a mobile browser, so it is resolved with an iPhone user agent.
# Private, deleted or invite-only albums simply yield nothing. (Same method as the Mac's google_photos.py.)
MOBILE_UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                           "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"}
DESKTOP_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
GPHOTO_RE = re.compile(r"https://lh3\.googleusercontent\.com/pw/[A-Za-z0-9_-]+")


def _google_photos(url: str) -> list[bytes]:
    if "photos.app.goo.gl" in url:
        with urllib.request.urlopen(urllib.request.Request(url, headers=MOBILE_UA), timeout=60) as resp:
            url = resp.geturl()
        if "photos.google.com" not in url:
            return []
    with urllib.request.urlopen(urllib.request.Request(url, headers=DESKTOP_UA), timeout=60) as resp:
        page = resp.read().decode("utf-8", "replace")
    seen = []
    for u in GPHOTO_RE.findall(page):
        if u not in seen:
            seen.append(u)
    out = []
    for u in seen[:MAX_PHOTOS + 5]:   # a few spare for videos / broken files
        try:
            out.append(_get(f"{u}=w2048"))
        except Exception:
            continue
    return out


def _post_json(url: str, body: dict, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "text/plain", "Origin": "https://www.icloud.com", **DESKTOP_UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, dict(resp.headers), json.load(resp)


# iCloud, two kinds of public link, both read the way icloud.com's own viewer reads them (no Apple ID):
#  * share.icloud.com/photos/<id> ("iCloud link"): CloudKit resolves the id to an anonymous access token,
#    then one records query lists the photos with a ready-made JPEG download URL each.
#  * www.icloud.com/sharedalbum/#<token> (Shared Album): the sharedstreams "webstream" lists the photos,
#    "webasseturls" gives their download URLs. The first host answers 330 with the album's real host.
CK = "https://ckdatabasews.icloud.com/database/1/com.apple.photos.cloud/production"


def _icloud_link(short_id: str) -> list[bytes]:
    _s, _h, res = _post_json(f"{CK}/public/records/resolve", {"shortGUIDs": [{"value": short_id}]})
    r = (res.get("results") or [{}])[0]
    access = r.get("anonymousPublicAccess") or {}
    if not access.get("token") or not r.get("zoneID"):
        return []   # "Share not found": the seller stopped sharing it
    zone = {k: r["zoneID"][k] for k in ("zoneName", "ownerRecordName")}
    url = (access.get("databasePartition") or "https://ckdatabasews.icloud.com").rstrip("/") + \
        "/database/1/com.apple.photos.cloud/production/shared/records/query?" + \
        urllib.parse.urlencode({"publicAccessAuthToken": access["token"]})
    _s, _h, q = _post_json(url, {"query": {"recordType": "CPLAssetAndMasterByAssetDateWithoutHiddenOrDeleted"},
                                 "zoneID": zone, "resultsLimit": 200})
    out = []
    for rec in q.get("records", []):
        f = rec.get("fields", {})
        if rec.get("recordType") != "CPLMaster" or "movie" in str(f.get("itemType", {}).get("value", "")).lower():
            continue
        res_ = (f.get("resJPEGFullRes") or f.get("resJPEGMedRes") or {}).get("value") or {}
        if res_.get("downloadURL"):
            try:
                out.append(_get(res_["downloadURL"].replace("${f}", "photo.jpg")))
            except Exception:
                continue
        if len(out) >= MAX_PHOTOS:
            break
    return out


def _icloud_album(token: str) -> list[bytes]:
    b62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    n = b62.index(token[1]) * 62 + b62.index(token[2]) if token[0] == "B" else b62.index(token[1])
    host = f"p{n:02d}-sharedstreams.icloud.com"
    for _ in range(2):
        try:
            _s, _h, data = _post_json(f"https://{host}/{token}/sharedstreams/webstream", {"streamCtag": None})
        except urllib.error.HTTPError as e:
            if e.code == 330:
                host = json.loads(e.read() or b"{}").get("X-Apple-MMe-Host") or e.headers.get("X-Apple-MMe-Host")
                if host:
                    continue
            raise
        if "X-Apple-MMe-Host" in data and not data.get("photos"):
            host = data["X-Apple-MMe-Host"]
            continue
        break
    else:
        return []
    photos = [p for p in data.get("photos", []) if p.get("mediaAssetType") != "video"][:MAX_PHOTOS]
    if not photos:
        return []
    best = {}
    for p in photos:
        ders = sorted((p.get("derivatives") or {}).values(), key=lambda d: int(d.get("width") or 0))
        fit = [d for d in ders if int(d.get("width") or 0) <= 2048] or ders
        if fit:
            best[p["photoGuid"]] = fit[-1]["checksum"]
    _s, _h, urls = _post_json(f"https://{host}/{token}/sharedstreams/webasseturls", {"photoGuids": list(best)})
    items = urls.get("items", {})
    out = []
    for guid in best:
        it = items.get(best[guid])
        if it:
            try:
                out.append(_get(f"https://{it['url_location']}{it['url_path']}"))
            except Exception:
                continue
    return out


def _icloud(url: str) -> list[bytes]:
    m = re.search(r"sharedalbum/#([A-Za-z0-9_-]+)", url)
    if m:
        return _icloud_album(m.group(1))
    m = re.search(r"(?:share\.icloud\.com/photos/|icloudlinks/)([A-Za-z0-9_-]+)", url)
    return _icloud_link(m.group(1)) if m else []


# OneDrive: a public "anyone with the link" folder is read through OneDrive's own anonymous web
# token (the same one onedrive.live.com uses for a signed-out visitor); no account is involved.
# JPEG/PNG are taken first; HEIC copies only when a folder has nothing else. Videos are skipped.
OD_TOKEN = "https://api-badgerp.svc.ms/v1.0/token"
OD_APP = "5cbed6ac-a083-4e14-b191-b4ba07653de2"
OD_API = "https://my.microsoftpersonalcontent.com/_api/v2.0/shares/{}/driveItem?$expand=children"


def _onedrive(url: str) -> list[bytes]:
    import base64
    treq = urllib.request.Request(OD_TOKEN, data=json.dumps({"appId": OD_APP}).encode(), method="POST",
                                  headers={"Content-Type": "application/json", **DESKTOP_UA})
    with urllib.request.urlopen(treq, timeout=60) as resp:
        tok = json.load(resp)
    enc = "u!" + base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
    req = urllib.request.Request(OD_API.format(enc), headers={**DESKTOP_UA, "Authorization": "Badger " + tok["token"],
                                                             "Prefer": "autoredeem"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        item = json.loads(resp.read())
    kids = item.get("children") or ([item] if item.get("file") else [])
    def kind(c):
        name, mime = c.get("name", "").lower(), (c.get("file") or {}).get("mimeType", "")
        if re.search(r"\.(jpe?g|png|webp)$", name) or mime in ("image/jpeg", "image/png", "image/webp"):
            return 0
        if re.search(r"\.(heic|heif)$", name) or "heic" in mime or "heif" in mime:
            return 1
        return None
    files = [c for c in sorted(kids, key=lambda c: c.get("name", "")) if kind(c) is not None]
    jpgs = [c for c in files if kind(c) == 0]
    out = []
    for c in (jpgs or files)[:MAX_PHOTOS]:
        dl = c.get("@content.downloadUrl") or c.get("@content.downloadUrlNoAuth")
        if dl:
            try:
                out.append(_get(dl, timeout=120))
            except Exception:
                continue
    return out


# viewthehomeonline.com: the listing's /p2/photos/<id> page lists every photo as a public S3 JPEG.
def _tour(url: str) -> list[bytes]:
    pid = re.search(r"/(\d{5,})", url).group(1)
    page = urllib.request.urlopen(urllib.request.Request(f"https://www.viewthehomeonline.com/p2/photos/{pid}",
                                                         headers=DESKTOP_UA), timeout=60).read().decode("utf-8", "replace")
    urls = list(dict.fromkeys(re.findall(rf"https://s3\.amazonaws\.com/property-documents/\d+/{pid}/[0-9a-f]+\.jpe?g", page)))
    return [_get(u) for u in urls[:MAX_PHOTOS]]


# A Google Doc shared as "anyone with the link" that is just a page of photos: its HTML export carries
# the images inline. A doc with real text (a contract, a disclosure) is never mined for images.
GDOC_MAX_TEXT = 300


def _gdoc(url: str) -> list[bytes]:
    import base64
    did = re.search(r"/document/d/([A-Za-z0-9_-]+)", url).group(1)
    page = _get(f"https://docs.google.com/document/d/{did}/export?format=html", timeout=120).decode("utf-8", "replace")
    text = re.sub(r"\s+", "", html.unescape(re.sub(r"<style.*?</style>|<[^>]+>", " ", page, flags=re.S)))
    if len(text) > GDOC_MAX_TEXT:
        return []
    out, seen = [], set()
    for src in re.findall(r'<img[^>]+src="([^"]+)"', page):
        try:
            blob = base64.b64decode(src.split(",", 1)[1]) if src.startswith("data:") else _get(html.unescape(src))
        except Exception:
            continue
        if blob not in seen:
            seen.add(blob)
            out.append(blob)
    return out[:MAX_PHOTOS]


def download_photos(links: list[str]) -> list[bytes]:
    blobs: list[bytes] = []
    for url in links:
        try:
            if urllib.parse.urlparse(url).netloc.lower() in SHORT_HOSTS:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as resp:
                    url = resp.geturl()
                if not (("drive.google.com" in url and "/folders/" in url) or "dropbox.com" in url
                        or _is_gphotos(url) or _is_icloud(url) or _is_onedrive(url)):
                    continue
            if not readable(url):
                continue   # OneDrive, a doc, a tour site: left for a browser pass
            if _is_gphotos(url):
                blobs += _google_photos(url)
            elif _is_icloud(url):
                blobs += _icloud(url)
            elif _is_onedrive(url):
                blobs += _onedrive(url)
            elif _is_tour(url):
                blobs += _tour(url)
            elif _is_gdoc(url):
                blobs += _gdoc(url)
            elif "drive.google.com" in url:
                blobs += _drive_folder(url)
            elif "dropbox.com" in url:
                blobs += _dropbox(url)
            else:
                blobs.append(_get(url))
        except Exception as exc:  # one bad link must not stop the run
            print(f"photo link failed: {urllib.parse.urlparse(url).netloc}: {exc.__class__.__name__}")
    return blobs[:MAX_PHOTOS]


def save_photos(root: Path, hid: str, blobs: list[bytes]) -> list[str]:
    """images/<id>.jpg (hero) + images/<id>-1..N.jpg (gallery), resized like the existing files."""
    import io
    from PIL import Image, ImageOps
    try:
        import pillow_heif   # iPhone HEIC photos
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    saved = []
    for blob in blobs:
        try:
            with Image.open(io.BytesIO(blob)) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((MAX_SIDE, MAX_SIDE))
                n = len(saved) + 1
                im.save(root / "images" / f"{hid}-{n}.jpg", "JPEG", quality=80, optimize=True, progressive=True)
                if n == 1 and not (root / "images" / f"{hid}.jpg").is_file():
                    im.save(root / "images" / f"{hid}.jpg", "JPEG", quality=82, optimize=True, progressive=True)
                saved.append(f"images/{hid}-{n}.jpg")
        except Exception:
            continue   # HEIC, video or a broken file
    return saved


def gallery_on_disk(root: Path, hid: str) -> list[str]:
    files, n = [], 1
    while (root / "images" / f"{hid}-{n}.jpg").is_file():
        files.append(f"images/{hid}-{n}.jpg")
        n += 1
    return files


# ---------- Street View fallback ----------
# A home with no seller cover (images/<id>.jpg) shows images/sv/<id>.jpg instead: index.html and
# home.html already fall back to it, with the "Street view · © Google" badge. The Mac's
# fetch_streetview.py does the same with its own key; this lets the GitHub sync do it too, for
# homes the Mac never sees. Key: env GOOGLE_MAPS_API_KEY (a GitHub secret; never in git). No key,
# no fetch. The free metadata call is checked first; no imagery -> the page keeps its fallback.
SV_META = "https://maps.googleapis.com/maps/api/streetview/metadata"
SV_IMG = "https://maps.googleapis.com/maps/api/streetview"
MAX_SV = 40   # Street View fetches per run


def streetview_into(root: Path, key: str | None = None, get=None) -> dict:
    """Fetch images/sv/<id>.jpg for live homes with no cover; drop it once a real cover exists."""
    key = key if key is not None else os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    text = (root / "homes.js").read_text(encoding="utf-8")
    sv_dir = root / "images" / "sv"
    res = {"fetched": [], "none": [], "pruned": [], "skipped": 0}
    for hid, m in blocks(text).items():
        block = m.group(0)
        hero = (field(block, "heroPhoto") or "").strip()
        has_cover = (root / "images" / f"{hid}.jpg").is_file() or (hero and (root / hero).is_file())
        sv = sv_dir / f"{hid}.jpg"
        if has_cover:
            if sv.is_file():
                sv.unlink()
                res["pruned"].append(hid)
            continue
        if sv.is_file():
            continue
        address = (field(block, "address") or "").split(",")[0].strip()
        if not key or not re.match(r"\d", address) or len(res["fetched"]) + len(res["none"]) >= MAX_SV:
            res["skipped"] += 1
            continue
        loc = f"{address}, {field(block, 'city') or ''}, {field(block, 'state') or ''} {field(block, 'zip') or ''}".strip()
        try:
            q = urllib.parse.urlencode({"location": loc, "key": key})
            meta = json.loads((get or _get)(f"{SV_META}?{q}", 20))
            if meta.get("status") != "OK":
                res["none"].append(f"{hid} ({meta.get('status')})")
                continue
            q = urllib.parse.urlencode({"size": "640x640", "location": loc, "source": "outdoor",
                                        "return_error_code": "true", "key": key})
            data = (get or _get)(f"{SV_IMG}?{q}", 30)
            if data[:2] == b"\xff\xd8":
                sv_dir.mkdir(parents=True, exist_ok=True)
                sv.write_bytes(data)
                res["fetched"].append(hid)
        except Exception as exc:   # never log the URL (it carries the key)
            res["none"].append(f"{hid} ({exc.__class__.__name__})")
    return res


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
def _street_city(address: str, city: str, state: str) -> tuple[str, str, str]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import sold_policy
    return (sold_policy.street_name(address).lower(), city_slug(city), (state or "").strip().lower())


def closed_streets(portal_rows: list[dict], crm_rows: list[dict]) -> dict[tuple, set]:
    """(street, city, state) -> ids of homes that are really closed (portal Pending/Sold, or CRM
    closed with no Available portal row). A sold card on that street stays up while one exists."""
    available = {home_id(r.get("Address", ""), r.get("City", ""), r.get("State", ""))
                 for r in portal_rows if str(r.get("Status", "")).strip().lower() == "available"}
    out: dict[tuple, set] = {}
    for r in portal_rows:
        if str(r.get("Status", "")).strip().lower() in ("pending", "sold"):
            hid = home_id(r.get("Address", ""), r.get("City", ""), r.get("State", ""))
            out.setdefault(_street_city(r.get("Address", ""), r.get("City", ""), r.get("State", "")), set()).add(hid)
    for r in crm_rows:
        hid = str(r.get("Unique ID") or "").strip().lower()
        if CLOSED.search(str(r.get("Property Status") or "")) and hid not in available:
            key = _street_city(r.get("Street Address", ""), r.get("City", ""), r.get("State", ""))
            out.setdefault(key, set()).add(hid)
    return out


def drop_sold_cards(text: str, adds: list[dict], closed: dict) -> tuple[str, list[str]]:
    """Take down the sold card of a home that is being relisted (street + city + state match)."""
    keys = {_street_city(r["address"], r["city"], r["state"]): r["id"] for r in adds}
    m = re.search(r"const SOLD_CARDS = \[\n(.*?)\n\];", text, re.S)
    if not m or not keys:
        return text, []
    kept, dropped = [], []
    for line in m.group(1).split("\n"):
        try:
            card = json.loads(line.strip().rstrip(","))
        except ValueError:
            kept.append(line)
            continue
        key = (str(card.get("street", "")).lower(), city_slug(card.get("city", "")), str(card.get("state", "")).lower())
        hid = keys.get(key)
        if hid and not (closed.get(key, set()) - {hid}):
            dropped.append(f"{card.get('street')}, {card.get('city')}")
            continue
        kept.append(line)
    return text[:m.start(1)] + "\n".join(kept) + text[m.end(1):], dropped


def plan(root: Path, portal_rows: list[dict], crm_rows: list[dict], wa: list[dict] | None = None) -> dict:
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
    excluded = excluded_homes.load(root, Path(__file__).resolve().parents[1])
    out = {"add": [], "update": [], "retire": [], "hand": [], "photos": [], "relist": [],
           "closed_streets": closed_streets(portal_rows, crm_rows)}
    for hid, row in portal.items():
        sid = match_site_id(hid, row, site_keys)
        status = row["Status"].strip()
        price, down, monthly = num(row["Price"]), num(row["Down payment"]), num(row["Monthly payment"])
        if sid in site:
            block = site[sid].group(0)
            if status.lower() == "available" and (field(block, "photos") or "[]").strip() == "[]":
                out["photos"].append(photo_item(sid, row))
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
        if hid in excluded or sid in excluded:
            out["hand"].append(f"{row['Address']}, {row['City']} ({hid}): portal Available but in data/excluded-homes.json; not added")
            continue
        if not price or not monthly:
            out["hand"].append(f"{row['Address']}, {row['City']} ({row['Portal PROP id']}): no price or monthly payment; skipped")
            continue
        if hid in crm_closed:
            out["relist"].append(f"{hid}  portal Available, CRM_Properties says {crm_closed[hid]}")
        out["add"].append({"id": hid, "pid": row["Portal PROP id"], "address": row["Address"], "city": row["City"],
                           "state": row["State"].strip().upper(), "zip": row["Zip"], "beds": num(row["Beds"]) or 0,
                           "baths": num(row["Baths"]) or 0, "sqft": num(row["Sqft"]), "price": price,
                           "down": down or 0, "monthly": monthly})
        out["photos"].append(photo_item(hid, row))
    out["add"].sort(key=lambda r: r["id"])
    wa_photos(out, site, wa or [], {r["id"]: r for r in out["add"]})
    return out


def photo_item(hid: str, row: dict) -> dict:
    """Photo sources for one home, best first: the portal's Photos link, then links in its note."""
    tiers = [t for t in (row.get("Portal photos", "").split(), row.get("Photo links", "").split()) if t]
    return {"id": hid, "tiers": tiers, "links": [u for t in tiers for u in t]}


def wa_photos(out: dict, site: dict, wa: list[dict], added: dict) -> None:
    """Add WhatsApp Intel album links for site homes that still have no seller photos.

    A group post matches a home by house number + street word, and by city when the post names
    one; a post with no city is used only if exactly one site home has that number + street."""
    homes = {}   # id -> (number, street, city slug)
    for sid, m in site.items():
        if (field(m.group(0), "photos") or "[]").strip() == "[]":
            number, street = address_key(field(m.group(0), "address") or "")
            homes[sid] = (number, street, city_slug(field(m.group(0), "city") or ""))
    for hid, r in added.items():
        number, street = address_key(r["address"])
        homes[hid] = (number, street, city_slug(r["city"]))
    by_ns: dict[tuple, list[str]] = {}
    for hid, (number, street, _c) in homes.items():
        if number and street:
            by_ns.setdefault((number, street), []).append(hid)
    found: dict[str, list[str]] = {}
    for row in wa:
        number, street = address_key(row["Address"])
        ids = by_ns.get((number, street), [])
        city = city_slug(row.get("City", ""))
        ids = [h for h in ids if homes[h][2] == city] if city else (ids if len(ids) == 1 else [])
        for h in ids:
            found.setdefault(h, [])
            found[h] += [u for u in row["links"] if u not in found[h]]
    items = {x["id"]: x for x in out["photos"]}
    for hid, links in sorted(found.items()):
        item = items.get(hid)
        if item is None:
            item = items[hid] = {"id": hid, "tiers": [], "links": []}
            out["photos"].append(item)
        extra = [u for u in links if u not in item["links"]]
        if extra:
            item.setdefault("tiers", []).append(extra)   # WhatsApp is the last resort
            item["links"] += extra


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
    text, p["cards_dropped"] = drop_sold_cards(text, p["add"], p.get("closed_streets", {}))
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
    photos_into(root, p)
    text = js.read_text(encoding="utf-8")
    count = len(re.findall(r'\n    id: "', text.split("const SOLD_CARDS")[0]))
    text = re.sub(r"\((\d+) live,", f"({count} live,", text, count=1)
    text = re.sub(r"\((\d+), generadas", f"({count}, generadas", text, count=1)
    js.write_text(text, encoding="utf-8")


def photos_into(root: Path, p: dict, fetch=download_photos, clock=None) -> None:
    """Fill the photos array of homes that have none: files already in images/ first, else the
    portal's Photos link, else the note link, else WhatsApp (first source with photos wins)."""
    import time
    clock = clock or time.monotonic
    start = clock()
    js = root / "homes.js"
    text = js.read_text(encoding="utf-8")
    site = blocks(text)
    p.setdefault("photo_result", {})
    p.setdefault("photo_failed", {})
    p.setdefault("photo_waiting", [])
    fetched = 0
    for item in p.get("photos", []):
        hid = item["id"]
        if hid not in site:
            continue
        files = gallery_on_disk(root, hid)
        tiers = item.get("tiers") or ([item["links"]] if item.get("links") else [])
        if not files and tiers:
            if fetched >= MAX_PHOTO_HOMES or clock() - start > PHOTO_BUDGET_S:
                p["photo_waiting"].append(hid)
                continue
            fetched += 1
            for tier in tiers:
                files = save_photos(root, hid, fetch(tier))
                if files:
                    break
            if not files:
                p["photo_failed"][hid] = item.get("links") or [u for t in tiers for u in t]
        if not files:
            continue
        block = site[hid].group(0)
        new = re.sub(r"\n    photos:\s*\[\s*\],", "\n    photos:    " + json.dumps(files) + ",", block, count=1)
        if new != block:
            text = text.replace(block, new, 1)
            p["photo_result"][hid] = len(files)
    js.write_text(text, encoding="utf-8")


def summary(p: dict) -> str:
    n = lambda k: len(p[k])
    sv = p.get("streetview") or {}
    ph = len(p.get("photo_result", {}))
    lines = [f"Portal sync: {n('add')} new, {n('update')} terms changed, {n('retire')} retired"
             + (f", photos for {ph}" if ph else ""), ""]
    for r in p["add"]:
        lines.append(f"+ {r['id']}  {r['address']}, {r['city']} {r['state']}  {money(r['price'])} / "
                     f"{money(r['down'])} down / {money(r['monthly'])}/mo  ({r['pid']})")
    for u in p["update"]:
        lines.append(f"~ {u['id']}  " + ", ".join(f"{k} {o}→{nv}" for k, (o, nv) in u["diffs"].items()))
    for r in p["retire"]:
        lines.append(f"- {r['id']}  {r['why']}")
    for hid, n in p.get("photo_result", {}).items():
        lines.append(f"* {hid}  {n} photos")
    if p.get("photo_failed"):
        lines += ["", "Photo links that gave no photos (browser pass or ask for a new link):"]
        for hid, links in p["photo_failed"].items():
            lines.append(f"  {hid}  " + " ".join(link_label(u) for u in links))
    if p.get("photo_waiting"):
        lines += ["", f"Albums waiting for the next run ({len(p['photo_waiting'])}): " + ", ".join(p["photo_waiting"])]
    if sv.get("fetched") or sv.get("pruned"):
        lines += ["", f"Street View: {len(sv.get('fetched', []))} fetched, {len(sv.get('pruned', []))} replaced by seller photos"]
    if sv.get("none"):
        lines += ["", "No Street View imagery (page keeps its fallback): " + ", ".join(sv["none"])]
    if p.get("relist"):
        lines += ["", "Relisted (portal is the master; fix the CRM_Properties status):"] + [f"  {h}" for h in p["relist"]]
    if p.get("cards_dropped"):
        lines += ["", "Sold cards taken down: " + "; ".join(p["cards_dropped"])]
    if p["hand"]:
        lines += ["", "Check by hand:"] + [f"  {h}" for h in p["hand"]]
    return "\n".join(lines) + "\n"


def link_label(url: str) -> str:
    """Host plus a short tail: enough to find the album, without pasting a full share token into git."""
    parts = urllib.parse.urlparse(url)
    kind = ("Google Photos" if _is_gphotos(url) else "iCloud" if _is_icloud(url) else
            "Drive" if "drive.google.com" in parts.netloc else "Dropbox" if "dropbox.com" in parts.netloc else parts.netloc)
    return f"[{kind} …{(parts.path + parts.fragment).rstrip('/')[-6:]}]"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--site", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--lang", choices=("en", "es"), default="en")
    ap.add_argument("--portal-json")
    ap.add_argument("--crm-json")
    ap.add_argument("--wa-json", help="offline WhatsApp Intel rows: [{Address, City, State, Photos}]")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--summary-out", type=Path)
    ap.add_argument("--force", action="store_true", help="allow more than MAX_RETIRE retirements")
    a = ap.parse_args(argv)
    # data/excluded-homes.json first: needs no Google key, so it holds even if the sheet read fails
    homes_repo = Path(__file__).resolve().parents[1]
    if a.dry_run:
        ex = sorted(i for i in excluded_homes.load(a.site, homes_repo) if f'id: "{i}"' in (a.site / "homes.js").read_text(encoding="utf-8"))
    else:
        ex = excluded_homes.apply(a.site, a.lang, extra=(homes_repo,))
    if ex:
        print("Excluded (data/excluded-homes.json), taken off the site: " + ", ".join(ex))
    if a.portal_json:
        portal, crm = load_json(a.portal_json), load_json(a.crm_json)
        wa = [{"Address": r.get("Address", ""), "City": r.get("City", ""), "State": r.get("State", ""),
               "links": photo_links(r.get("Photos", ""))} for r in load_json(a.wa_json)]
        wa = [r for r in wa if r["links"]]
    else:
        portal, crm, wa = read_sheets()
    portal = whitelist(portal)
    if len(portal) < MIN_PORTAL_ROWS:
        raise SystemExit(f"Portal Backup returned {len(portal)} rows (< {MIN_PORTAL_ROWS}); refusing to sync.")
    p = plan(a.site, portal, crm, wa)
    if len(p["retire"]) > MAX_RETIRE and not a.force:
        raise SystemExit(f"{len(p['retire'])} homes would be retired (> {MAX_RETIRE}); refusing without --force.")
    pending = [x for x in p["photos"] if x["links"] or gallery_on_disk(a.site, x["id"])]
    if not a.dry_run and (p["add"] or p["update"] or p["retire"] or pending):
        apply(a.site, p, a.lang)
    if not a.dry_run:
        p["streetview"] = streetview_into(a.site)
    elif a.dry_run:
        for x in pending:
            print(f"* {x['id']}  photos from {len(x['links'])} link(s)")
    text = summary(p)
    print(text)
    if a.summary_out:
        a.summary_out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
