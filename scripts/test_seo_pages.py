"""python3 scripts/test_seo_pages.py

Synthetic catalog plus, when run from the repo, the generated pages on disk.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import portal_sync as ps  # noqa: E402
import seo_pages as seo  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Own a Home — Owner Financing | Americas Best Home Solutions</title>
<meta name="description" content="Own a home with owner financing — a monthly payment close to rent, no bank needed."/>
</head>
<body>
<a class="nav-es" href="https://casasconfinanciamiento.com/">Español</a>
<span class="status-tag" id="statusTag">Available</span>
<h1 class="headline" id="headline"></h1>
<p class="seo-facts" id="seoFacts"></p>
<p class="seo-city" id="seoCity"></p>
<div class="num" id="dMonthly"></div>
<div class="num" id="dMoveIn"></div>
<div class="num" id="dPrice"></div>
<section id="aboutHomeSec" hidden><p class="about-desc" id="aboutDesc"></p></section>
<div class="terms" id="termsList"></div>
<script src="homes.js"></script>
<script>
document.addEventListener("DOMContentLoaded", function(){});
</script>
</body>
</html>
"""

INDEX = """<!DOCTYPE html>
<html lang="en">
<head>
<title>Owner-Financed Homes | Americas Best Home Solutions</title>
<meta name="description" content="Browse available homes."/>
<link rel="canonical" href="https://getownerfinancedhomes.com/"/>
<style>
.sec-title{font-weight:800}
</style>
</head>
<body>
<a class="nav-es" href="https://casasconfinanciamiento.com/">Español</a>
<section class="section" id="listings"></section>
</body>
</html>
"""

HOMES = r"""
const HOMES = [
  {
    id: "decatur-il-1527-decatur",
    address:     "1527 E Decatur St",
    copy:        "A clean two-bedroom ranch in Decatur.",
    city:  "Decatur",
    state: "IL",
    beds:  2,
    baths: 1,
    sqft:  "900",
    status: "Available",
    monthlyPayment: 725,
    moveIn:         2000,
    lockedPrice:    71000,
    termText:       "30-year owner financing (contract for deed)",
    heroPhoto: "",
    photos:    [],
  },
  {
    id: "lewistown-il-714-adams",
    address:     "714 Adams St",
    city:  "Lewistown",
    state: "IL",
    beds:  3,
    baths: 1,
    sqft:  "",
    status: "Pending",
    monthlyPayment: 600,
    moveIn:         0,
    lockedPrice:    48000,
    termText:       "30-year owner financing (contract for deed)",
    heroPhoto: "",
    photos:    [],
  },
];
const SOLD_CARDS = [
];
"""


def site(tmp: Path) -> None:
    (tmp / "home.html").write_text(TEMPLATE, encoding="utf-8")
    (tmp / "index.html").write_text(INDEX, encoding="utf-8")
    (tmp / "homes.js").write_text(HOMES, encoding="utf-8")
    (tmp / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nDisallow: /home.html\nDisallow: /next-steps.html\n\nSitemap: https://getownerfinancedhomes.com/sitemap.xml\n",
        encoding="utf-8")
    (tmp / "next-steps.html").write_text('<html><head><meta name="robots" content="noindex,nofollow"/></head></html>', encoding="utf-8")
    (tmp / "gone-il-1-oak.html").write_text(
        '<html><head><meta name="robots" content="noindex, nofollow"/><title>This home is no longer available</title></head><body></body></html>',
        encoding="utf-8")
    (tmp / "empty-il.html").write_text('<html data-city-landing="empty-il"><head><title>old</title></head></html>', encoding="utf-8")
    (tmp / "about.html").write_text(
        '<html lang="en"><head><title>About</title><meta name="description" content="About the company."/>'
        '<link rel="canonical" href="https://getownerfinancedhomes.com/about"/></head>'
        '<body><a class="nav-es" href="https://casasconfinanciamiento.com/">Español</a></body></html>',
        encoding="utf-8")
    (tmp / ".nojekyll").write_text("", encoding="utf-8")
    (tmp / "images").mkdir()
    (tmp / "images" / "_share-default.jpg").write_bytes(b"jpg")
    (tmp / "images" / "decatur-il-1527-decatur.jpg").write_bytes(b"jpg")


class Synthetic(unittest.TestCase):
    def test_pages_schema_hreflang_and_omissions(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            site(root)
            seo.rebuild(root, "en")
            errors = seo.validate(root, "en")
            self.assertEqual(errors, [], "\n".join(errors))
            decatur = (root / "decatur-il-1527-decatur.html").read_text(encoding="utf-8")
            self.assertIn("1527 E Decatur St, Decatur, IL", decatur)
            self.assertIn("$71,000", decatur)
            self.assertIn("$2,000", decatur)
            self.assertIn("$725", decatur)
            self.assertIn("Down payment", decatur)
            self.assertIn("Monthly payment", decatur)
            self.assertIn('src="homes.js" defer', decatur)
            self.assertIn("https://casasconfinanciamiento.com/decatur-il-1527-decatur.html", decatur)
            self.assertIn("images/decatur-il-1527-decatur.jpg", decatur)
            self.assertNotIn("$0", decatur.split('id="seoFacts"')[1][:500])
            docs = seo._ld_types(decatur)
            kinds = set().union(*(seo._graph_types(doc) for doc in docs))
            self.assertIn("Offer", kinds)
            offer = next(n for doc in docs for n in (doc.get("@graph") or []) if n.get("@type") == "Offer")
            self.assertEqual(offer["price"], "71000")
            self.assertNotIn("interest", json.dumps(docs).lower())
            lewi = (root / "lewistown-il-714-adams.html").read_text(encoding="utf-8")
            self.assertNotIn("$0", lewi)
            self.assertNotIn("down", lewi.split("<h1")[1].split("</h1>")[0].lower())
            self.assertIn("Pending", lewi)
            city = (root / "decatur-il.html").read_text(encoding="utf-8")
            self.assertIn("Owner Financed Homes in Decatur, IL", city)
            self.assertIn("/decatur-il-1527-decatur.html", city)
            self.assertNotIn("homes.js", city)
            self.assertFalse((root / "empty-il.html").exists())
            self.assertIn("noindex", (root / "gone-il-1-oak.html").read_text(encoding="utf-8"))
            sitemap = (root / "sitemap.xml").read_text(encoding="utf-8")
            self.assertNotIn("gone-il-1-oak", sitemap)
            self.assertNotIn("next-steps", sitemap)
            self.assertIn("decatur-il.html", sitemap)
            self.assertIn('hreflang="es"', sitemap)
            index = (root / "index.html").read_text(encoding="utf-8")
            self.assertIn('property="og:image"', index)
            self.assertIn("/decatur-il.html", index)
            self.assertIn("/lewistown-il.html", index)
            about = (root / "about.html").read_text(encoding="utf-8")
            self.assertIn("https://casasconfinanciamiento.com/nosotros", about)
            first = (root / "decatur-il-1527-decatur.html").read_bytes()
            seo.rebuild(root, "en")
            self.assertEqual(first, (root / "decatur-il-1527-decatur.html").read_bytes())

    def test_spanish_copy_and_portal_row(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            site(root)
            row = {"id": "peoria-il-422-louisa", "address": "422 Louisa St", "city": "Peoria", "state": "IL",
                   "beds": 2, "baths": 1, "price": 55000, "down": None, "monthly": 640}
            ps.write_page(root, row, "es")
            text = (root / "peoria-il-422-louisa.html").read_text(encoding="utf-8")
            self.assertIn("Financiamiento del dueño", text)
            self.assertIn("422 Louisa St, Peoria, IL", text)
            self.assertIn("https://getownerfinancedhomes.com/peoria-il-422-louisa.html", text)
            self.assertNotIn("$0", text)
            self.assertIn('lang="es"', text)


class Live(unittest.TestCase):
    def test_repo_pages(self):
        if not (ROOT / "decatur-il.html").is_file():
            self.skipTest("run scripts/seo_pages.py first")
        errors = seo.validate(ROOT, "en")
        self.assertEqual(errors, [], "\n".join(errors[:30]))


if __name__ == "__main__":
    unittest.main()
