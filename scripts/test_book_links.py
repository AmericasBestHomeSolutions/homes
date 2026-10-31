"""python3 scripts/test_book_links.py"""
import json, re, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import book_links as B


def homes_js(*homes):
    blocks = []
    for hid, addr, status in homes:
        blocks.append(f'''  {{
    id: "{hid}",
    address:     "{addr}",
    city:  "Decatur",
    state: "IL",
    status: "{status}",
    lockbox: "1234",
  }}''')
    return "/* --- the homes (x live, y) --- */\nconst HOMES = [\n" + ",\n".join(blocks) + "\n];\nconst SOLD_CARDS = [\n  {id: \"sold-xx-1-gone\"}\n];\n"


class T(unittest.TestCase):
    def site(self, d, *homes, es=False):
        r = Path(d); (r / "data").mkdir(exist_ok=True); (r / "images").mkdir(exist_ok=True)
        (r / "homes.js").write_text(homes_js(*homes), encoding="utf-8")
        if es:
            (r / "como-funciona.html").write_text("x")
        return r

    def test_short_slug(self):
        self.assertEqual(B.short_slug("decatur-il-905-olive"), "905-olive")
        self.assertEqual(B.short_slug("eaststlouis-il-6000-old"), "6000-old")
        self.assertEqual(B.short_slug("nolocation"), "")

    def test_pages_for_905_olive(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.site(d, ("decatur-il-905-olive", "905 W. Olive St.", "Available"))
            (r / "images" / "decatur-il-905-olive.jpg").write_bytes(b"x")
            res = B.build(r, "en")
            self.assertEqual((res["homes"], res["short"]), (1, 1))
            short = (r / "book" / "905-olive" / "index.html").read_text()
            full = (r / "book" / "decatur-il-905-olive" / "index.html").read_text()
            target = "https://owner.getownerfinancedhomes.com/book?home=decatur-il-905-olive&lang=en"
            for page in (short, full):
                self.assertIn(json.dumps(target), page)                       # JS redirect
                self.assertIn('content="0;url=' + target.replace("&", "&amp;"), page)   # no-JS fallback
                self.assertIn('rel="canonical" href="' + target.replace("&", "&amp;"), page)
                self.assertIn('name="robots" content="noindex, nofollow"', page)
                self.assertIn("location.search", page)                         # keeps ?lang / utm_*
                self.assertIn("905 W. Olive St., Decatur, IL", page)
                self.assertNotIn("1234", page)                                 # nothing but the address
                self.assertNotIn("lockbox", page.lower())
            self.assertIn("og:image", short)
            self.assertIn('"905-olive": "decatur-il-905-olive"', (r / "data" / "book-links.json").read_text())
            self.assertEqual(B.links(r), {"decatur-il-905-olive": "905-olive"})
            self.assertEqual(json.loads((r / "data" / "book-links.json").read_text())["live"], {"decatur-il-905-olive": "905-olive"})
            self.assertEqual(B.build(r, "en")["changed"], 0)                    # idempotent

    def test_spanish_site_uses_agendar_and_lang_es(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.site(d, ("decatur-il-905-olive", "905 W. Olive St.", "Available"), es=True)
            B.build(r)
            page = (r / "agendar" / "905-olive" / "index.html").read_text()
            self.assertIn("home=decatur-il-905-olive&lang=es", page)
            self.assertIn("Agende una visita", page)
            self.assertFalse((r / "book").exists())

    def test_collision_falls_back_to_full_id_and_slug_is_stable(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.site(d, ("decatur-il-905-olive", "905 Olive", "Available"),
                          ("peoria-il-905-olive", "905 Olive", "Available"))
            B.build(r, "en")
            self.assertFalse((r / "book" / "905-olive").exists())              # nobody gets an ambiguous slug
            self.assertTrue((r / "book" / "decatur-il-905-olive" / "index.html").is_file())
            self.assertTrue((r / "book" / "peoria-il-905-olive" / "index.html").is_file())
            self.assertEqual(B.links(r)["peoria-il-905-olive"], "peoria-il-905-olive")
            live = json.loads((r / "data" / "book-links.json").read_text())["live"]
            self.assertEqual(live["decatur-il-905-olive"], "decatur-il-905-olive")
        with tempfile.TemporaryDirectory() as d:
            r = self.site(d, ("decatur-il-905-olive", "905 Olive", "Available"))
            B.build(r, "en")
            # a later home that wants the same slug does not take it over
            (r / "homes.js").write_text(homes_js(("decatur-il-905-olive", "905 Olive", "Available"),
                                                 ("alton-il-905-olive", "905 Olive", "Available")))
            B.build(r, "en")
            self.assertIn("home=decatur-il-905-olive&", (r / "book" / "905-olive" / "index.html").read_text())
            self.assertEqual(B.links(r)["alton-il-905-olive"], "alton-il-905-olive")

    def test_removed_home_redirects_to_home_page(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.site(d, ("decatur-il-905-olive", "905 Olive", "Available"), ("decatur-il-1-a", "1 A", "Available"))
            (r / "book" / "keep-me").mkdir(parents=True); (r / "book" / "keep-me" / "index.html").write_text("hand made")
            B.build(r, "en")
            (r / "homes.js").write_text(homes_js(("decatur-il-1-a", "1 A", "Available"),
                                                 ("decatur-il-2-sold", "2 Sold", "Sold")))
            res = B.build(r, "en")
            for key in ("905-olive", "decatur-il-905-olive"):
                page = (r / "book" / key / "index.html").read_text()
                self.assertIn('location.replace("/")', page)
                self.assertNotIn("owner.getownerfinancedhomes.com", page)
            self.assertEqual(res["gone"], 2)
            self.assertFalse((r / "book" / "decatur-il-2-sold").exists())       # not Available: no page
            self.assertFalse((r / "book" / "sold-xx-1-gone").exists())          # SOLD_CARDS are not homes
            self.assertEqual((r / "book" / "keep-me" / "index.html").read_text(), "hand made")
            # it comes back: the same slug points at it again
            (r / "homes.js").write_text(homes_js(("decatur-il-905-olive", "905 Olive", "Available")))
            B.build(r, "en")
            self.assertIn("home=decatur-il-905-olive&", (r / "book" / "905-olive" / "index.html").read_text())

    def test_other_site_slugs_win(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            en = self.site(d1, ("decatur-il-905-olive", "905 Olive", "Available"))
            (en / "data" / "book-links.json").write_text(json.dumps({"slugs": {"905-olive": "peoria-il-905-olive"}, "held": []}))
            es = self.site(d2, ("decatur-il-905-olive", "905 Olive", "Available"), es=True)
            B.build(es, extra=(en,))
            self.assertIn('location.replace("/")', (es / "agendar" / "905-olive" / "index.html").read_text())
            self.assertTrue((es / "agendar" / "decatur-il-905-olive" / "index.html").is_file())

    def test_real_site_has_905_olive(self):
        root = Path(__file__).resolve().parents[1]
        lang = "es" if (root / "como-funciona.html").is_file() else "en"
        out = root / B.SITES[lang]["dir"]
        page = out / "905-olive" / "index.html"
        if not page.is_file():
            self.skipTest("booking links not generated in this checkout")
        self.assertIn(f"home=decatur-il-905-olive&lang={lang}", page.read_text())
        for hid in B.read_homes(root):
            self.assertTrue((out / hid / "index.html").is_file(), hid)
        for s in B.links(root).values():
            self.assertNotRegex((out / s / "index.html").read_text().lower(), r"lockbox|combo|\bcode\b")

if __name__ == "__main__":
    unittest.main()
