"""python3 scripts/test_book_links.py"""
import json, re, sys, tempfile, unittest
from html.parser import HTMLParser
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


class HeadParser(HTMLParser):
    """Collect meta tags and inline script text from generated redirect pages."""

    def __init__(self):
        super().__init__()
        self.scripts: list[str] = []
        self.metas: list[tuple[str, str, str]] = []
        self._in_script = False
        self._buf = ""

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if tag == "meta":
            self.metas.append((ad.get("name", ""), ad.get("property", ""), ad.get("content", "")))
        if tag == "script" and "src" not in ad:
            self._in_script = True
            self._buf = ""

    def handle_data(self, data):
        if self._in_script:
            self._buf += data

    def handle_endtag(self, tag):
        if tag == "script" and self._in_script:
            self.scripts.append(self._buf)
            self._in_script = False


def parse_page(html: str) -> HeadParser:
    p = HeadParser()
    p.feed(html)
    return p


class T(unittest.TestCase):
    def site(self, d, *homes, es=False):
        r = Path(d); (r / "data").mkdir(exist_ok=True); (r / "images").mkdir(exist_ok=True)
        (r / "homes.js").write_text(homes_js(*homes), encoding="utf-8")
        (r / "images" / "_share-default.jpg").write_bytes(b"x")
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
            for page, slug in ((short, "905-olive"), (full, "decatur-il-905-olive")):
                self.assertNotIn("<iframe", page)
                self.assertIn("location.replace", parse_page(page).scripts[0])
                self.assertEqual(B.redirect_target_from_page(page), target)
                self.assertEqual(B.meta_property(page, "og:url"),
                                 f"https://getownerfinancedhomes.com/book/{slug}")
                self.assertIn("og:image", page)
                self.assertEqual(B.meta_property(page, "og:image"),
                                 "https://getownerfinancedhomes.com/images/decatur-il-905-olive.jpg")
                self.assertIn('name="robots" content="noindex, nofollow"', page)
                self.assertIn("905 W. Olive St., Decatur, IL", page)
                self.assertNotIn("1234", page)
                self.assertNotIn("lockbox", page.lower())
            fb = (r / "feedback" / "905-olive" / "index.html").read_text()
            self.assertNotIn("<iframe", fb)
            self.assertEqual(B.redirect_target_from_page(fb),
                             "https://owner.getownerfinancedhomes.com/feedback/decatur-il-905-olive?lang=en")
            self.assertNotIn("og:image", fb)
            acct = (r / "account" / "index.html").read_text()
            self.assertNotIn("<iframe", acct)
            self.assertEqual(B.redirect_target_from_page(acct), "https://owner.getownerfinancedhomes.com/account?lang=en")
            self.assertIn('"lang", "home"', acct)
            self.assertNotIn("next", acct)
            self.assertIn("og:image", acct)
            self.assertIn('"905-olive": "decatur-il-905-olive"', (r / "data" / "book-links.json").read_text())
            self.assertEqual(B.build(r, "en")["changed"], 0)

    def test_book_href_falls_back_to_crm_not_404(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.site(d, ("decatur-il-905-olive", "905 W. Olive St.", "Available"))
            B.build(r, "en")
            js = (r / "book-links.js").read_text()
            self.assertIn("function bookHref", js)
            self.assertIn("BOOK_CRM", js)
            self.assertNotIn("/agendar/", js)
            self.assertNotIn("/cuenta/", js)
            self.assertIn('if(BOOK_HREF[homeId]) return BOOK_HREF[homeId]', js.replace("\n", " "))
            self.assertIn("encodeURIComponent(homeId)", js)
            self.assertIn("decatur-il-905-olive", js)
            self.assertIn("/book/905-olive", js)

    def test_spanish_site_uses_agendar_and_lang_es(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.site(d, ("decatur-il-905-olive", "905 W. Olive St.", "Available"), es=True)
            B.build(r)
            page = (r / "agendar" / "905-olive" / "index.html").read_text()
            self.assertEqual(B.redirect_target_from_page(page),
                             "https://owner.getownerfinancedhomes.com/book?home=decatur-il-905-olive&lang=es")
            self.assertIn("Agende una visita", page)
            self.assertFalse((r / "book").exists())
            self.assertTrue((r / "cuenta" / "index.html").is_file())

    def test_collision_falls_back_to_full_id_and_slug_is_stable(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.site(d, ("decatur-il-905-olive", "905 Olive", "Available"),
                          ("peoria-il-905-olive", "905 Olive", "Available"))
            B.build(r, "en")
            self.assertFalse((r / "book" / "905-olive").exists())
            self.assertTrue((r / "book" / "decatur-il-905-olive" / "index.html").is_file())
            self.assertTrue((r / "book" / "peoria-il-905-olive" / "index.html").is_file())
            self.assertEqual(B.links(r)["peoria-il-905-olive"], "peoria-il-905-olive")
            live = json.loads((r / "data" / "book-links.json").read_text())["live"]
            self.assertEqual(live["decatur-il-905-olive"], "decatur-il-905-olive")
        with tempfile.TemporaryDirectory() as d:
            r = self.site(d, ("decatur-il-905-olive", "905 Olive", "Available"))
            B.build(r, "en")
            (r / "homes.js").write_text(homes_js(("decatur-il-905-olive", "905 Olive", "Available"),
                                                 ("alton-il-905-olive", "905 Olive", "Available")))
            B.build(r, "en")
            self.assertIn("home=decatur-il-905-olive&", (r / "book" / "905-olive" / "index.html").read_text())
            self.assertEqual(B.links(r)["alton-il-905-olive"], "alton-il-905-olive")

    def test_pending_home_blocks_booking(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.site(d, ("granitecity-il-2539-28th", "2539 E. 28th St.", "Available"))
            B.build(r, "en")
            (r / "homes.js").write_text(homes_js(("granitecity-il-2539-28th", "2539 E. 28th St.", "Pending")))
            B.build(r, "en")
            for key in ("2539-28th", "granitecity-il-2539-28th"):
                page = (r / "book" / key / "index.html").read_text()
                self.assertIn("This home is pending", page)
                self.assertIn("new tours are not open", page)
                self.assertNotIn("owner.getownerfinancedhomes.com", page)
                self.assertNotIn("location.replace", page)
            js = (r / "book-links.js").read_text()
            self.assertIn("granitecity-il-2539-28th", js)
            self.assertIn("BOOK_CLOSED", js)
            self.assertNotIn('"/book/2539-28th"', js)
            live = json.loads((r / "data" / "book-links.json").read_text())["live"]
            self.assertNotIn("granitecity-il-2539-28th", live)

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
            self.assertFalse((r / "book" / "decatur-il-2-sold").exists())
            self.assertFalse((r / "book" / "sold-xx-1-gone").exists())
            self.assertEqual((r / "book" / "keep-me" / "index.html").read_text(), "hand made")
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

    def test_feedback_links_keep_working_after_a_home_leaves(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.site(d, ("decatur-il-905-olive", "905 W. Olive St.", "Available"))
            B.build(r, "en")
            page = (r / "feedback" / "905-olive" / "index.html").read_text()
            self.assertEqual(B.redirect_target_from_page(page),
                             "https://owner.getownerfinancedhomes.com/feedback/decatur-il-905-olive?lang=en")
            self.assertIn("905 W. Olive St., Decatur, IL", page)
            self.assertNotIn("1234", page)
            self.assertTrue((r / "feedback" / "decatur-il-905-olive" / "index.html").is_file())
            r2 = self.site(d, ("decatur-il-1-other", "1 Other St", "Available"))
            B.build(r2, "en")
            page = (r / "feedback" / "905-olive" / "index.html").read_text()
            self.assertIn("/feedback/decatur-il-905-olive?lang=en", page)
            self.assertTrue((r / "feedback" / "decatur-il-905-olive" / "index.html").is_file())

    def test_feedback_redirect_forwards_only_the_token_prop_and_lang(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.site(d, ("decatur-il-905-olive", "905 W. Olive St.", "Available"))
            B.build(r, "en")
            page = (r / "feedback" / "905-olive" / "index.html").read_text()
            self.assertIn('["t", "prop", "lang"]', page)
            self.assertNotIn("q.forEach", page)
            self.assertNotIn("phone", page)

    def test_feedback_link_needs_a_crm_token(self):
        token = "eyJ0IjoiVGFiY2RlZjAxMjM0NSJ9.aaaaaa.bbbbbbbbbbbbbbbbbbbbbbbbbbb"
        self.assertEqual(B.feedback_link("905-olive", token),
                         f"{B.SITES['en']['domain']}/feedback/905-olive?t={token}")
        for bad in ("", "3095550148", "Tabcdef012345", "a b c d e f g h i j k l m n o p"):
            with self.assertRaises(ValueError):
                B.feedback_link("905-olive", bad)

    def test_spanish_feedback_is_opinion(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.site(d, ("decatur-il-905-olive", "905 W. Olive St.", "Available"), es=True)
            B.build(r)
            page = (r / "opinion" / "905-olive" / "index.html").read_text()
            self.assertIn("/feedback/decatur-il-905-olive?lang=es", page)

    def test_real_site_has_905_olive(self):
        root = Path(__file__).resolve().parents[1]
        lang = "es" if (root / "como-funciona.html").is_file() else "en"
        out = root / B.SITES[lang]["dir"]
        page = out / "905-olive" / "index.html"
        if not page.is_file():
            self.skipTest("booking links not generated in this checkout")
        text = page.read_text()
        if "no longer available" in text:   # 905 Olive sold; the page is now a redirect stub. Check the other live homes below.
            pass
        else:
            self.assertIn(f"home=decatur-il-905-olive&lang={lang}", text)
        for hid in B.read_homes(root):
            self.assertTrue((out / hid / "index.html").is_file(), hid)
        for s in B.links(root).values():
            self.assertNotRegex((out / s / "index.html").read_text().lower(), r"lockbox|combo|\bcode\b")

if __name__ == "__main__":
    unittest.main()
