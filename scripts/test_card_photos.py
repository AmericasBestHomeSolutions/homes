"""Photo manifest, card thumbnails, and real-photo sort order.

    python3 scripts/test_card_photos.py
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import card_photos  # noqa: E402
import portal_sync as ps  # noqa: E402
import seo_pages as seo  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def jpeg(path: Path, color, size=(800, 600)) -> None:
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, "JPEG", quality=85)


HOMES = """
const HOMES = [
  {
    id: "decatur-il-9-zebra",
    address:     "9 Zebra St",
    city:  "Decatur",
    state: "IL",
    heroPhoto: "",
    photos:    ["images/decatur-il-9-zebra-1.jpg", "images/decatur-il-9-zebra-2.jpg"],
  },
  {
    id: "decatur-il-1-apple",
    address:     "1 Apple St",
    city:  "Decatur",
    state: "IL",
    heroPhoto: "",
    photos:    [],
  },
  {
    id: "decatur-il-2-birch",
    address:     "2 Birch St",
    city:  "Decatur",
    state: "IL",
    heroPhoto: "",
    photos:    [],
  },
];
const SOLD_CARDS = [
];
"""


def site(root: Path) -> None:
    (root / "images").mkdir()
    (root / "images" / "sv").mkdir()
    jpeg(root / "images" / "decatur-il-9-zebra.jpg", (180, 40, 40))
    jpeg(root / "images" / "decatur-il-9-zebra-1.jpg", (180, 40, 40), (640, 480))
    jpeg(root / "images" / "decatur-il-9-zebra-2.jpg", (20, 80, 140), (640, 400))
    jpeg(root / "images" / "sv" / "decatur-il-1-apple.jpg", (40, 80, 140), (900, 600))
    (root / "homes.js").write_text(HOMES, encoding="utf-8")


class Manifest(unittest.TestCase):
    def test_manifest_thumbs_and_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site(root)
            first = card_photos.sync(root)
            self.assertEqual(first["real"], 1)
            self.assertEqual(first["street"], 1)
            self.assertEqual(first["none"], 1)
            self.assertEqual(first["encoded"], 2)
            self.assertEqual(first["cached"], 0)
            text = (root / "homes.js").read_text(encoding="utf-8")
            self.assertIn('id: "decatur-il-9-zebra"', text)
            zebra = ps.blocks(text)["decatur-il-9-zebra"].group(0)
            self.assertIn("hasPhoto: true,", zebra)
            self.assertIn("photoCount: 3,", zebra)
            self.assertIn('cardPhoto: "images/cards/decatur-il-9-zebra.webp",', zebra)
            self.assertIn("cardWidth: 480,", zebra)
            apple = ps.blocks(text)["decatur-il-1-apple"].group(0)
            self.assertIn("hasPhoto: false,", apple)
            self.assertIn("photoCount: 0,", apple)
            self.assertIn('cardPhoto: "images/cards/decatur-il-1-apple.webp",', apple)
            birch = ps.blocks(text)["decatur-il-2-birch"].group(0)
            self.assertIn("hasPhoto: false,", birch)
            self.assertIn('cardPhoto: "",', birch)
            thumb = root / "images" / "cards" / "decatur-il-9-zebra.webp"
            self.assertTrue(thumb.is_file())
            from PIL import Image
            with Image.open(thumb) as image:
                self.assertEqual(image.size[0], 480)
            second = card_photos.sync(root)
            self.assertEqual(second["encoded"], 0)
            self.assertEqual(second["cached"], 2)
            self.assertEqual((root / "homes.js").read_text(encoding="utf-8"), text)
            jpeg(root / "images" / "decatur-il-9-zebra.jpg", (10, 10, 10))
            third = card_photos.sync(root)
            self.assertEqual(third["encoded"], 1)
            self.assertEqual(third["cached"], 1)

    def test_sort_puts_real_photos_before_street_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site(root)
            card_photos.sync(root)
            homes = seo.load_homes(root)
            self.assertTrue(card_photos.has_real_photo(next(h for h in homes if h["id"].endswith("zebra"))))
            self.assertFalse(card_photos.has_real_photo(next(h for h in homes if h["id"].endswith("apple"))))
            order = [h["id"] for h in seo.group_cities(homes)[0]["homes"]]
            self.assertEqual(order, [
                "decatur-il-9-zebra",
                "decatur-il-1-apple",
                "decatur-il-2-birch",
            ])

    def test_string_flag_still_sorts_first(self):
        homes = [
            {"id": "b", "address": "1 Apple", "city": "Decatur", "state": "IL", "hasPhoto": "false"},
            {"id": "a", "address": "9 Zebra", "city": "Decatur", "state": "IL", "hasPhoto": "true"},
        ]
        order = [h["id"] for h in seo.group_cities(homes)[0]["homes"]]
        self.assertEqual(order, ["a", "b"])


class Condition(unittest.TestCase):
    def test_feed_without_condition_does_not_invent_one(self):
        row = {"Address": "1 Oak", "City": "Decatur", "State": "IL", "Status": "Available"}
        self.assertEqual(ps.condition_of(row), "")
        kept = ps.whitelist([row])[0]
        self.assertNotIn("Condition", kept)

    def test_feed_condition_is_copied_and_not_mined_from_prose(self):
        row = {"Address": "1 Oak", "condition": " Average "}
        self.assertEqual(ps.condition_of(row), "Average")
        kept = ps.whitelist([row])[0]
        self.assertEqual(kept["Condition"], "Average")
        block = ps.new_block({
            "id": "decatur-il-1-oak", "address": "1 Oak", "city": "Decatur", "state": "IL",
            "zip": "", "beds": 2, "baths": 1, "sqft": None, "price": 50000, "down": 2000,
            "monthly": 600, "note": "ready to move into", "condition": "Average",
        }, "en", None)
        self.assertEqual(ps.field(block, "condition"), "Average")
        self.assertNotIn("ready to move", block.split('condition:   "Average"')[1])
        plain = ps.new_block({
            "id": "decatur-il-2-oak", "address": "2 Oak", "city": "Decatur", "state": "IL",
            "zip": "", "beds": 2, "baths": 1, "sqft": None, "price": 50000, "down": 2000,
            "monthly": 600, "note": "It is move-in ready.",
        }, "en", None)
        self.assertNotIn("condition:", plain)

    def test_listing_slot_stays_hidden_without_a_value(self):
        template = """<!DOCTYPE html>
<html lang="en"><head><title>t</title>
<meta name="description" content="d"/>
</head><body>
<a class="nav-es" href="https://casasconfinanciamiento.com/">Español</a>
<p class="condition-line" id="conditionLine" hidden></p>
<h1 class="headline" id="headline"></h1>
<div class="num" id="dMonthly"></div><div class="num" id="dMoveIn"></div><div class="num" id="dPrice"></div>
<span class="status-tag" id="statusTag">Available</span>
<section id="aboutHomeSec" hidden><p class="about-desc" id="aboutDesc"></p></section>
<div class="terms" id="termsList"></div>
<script src="homes.js"></script>
<script>document.addEventListener("DOMContentLoaded", function(){});</script>
</body></html>
"""
        home = {"id": "decatur-il-1-oak", "address": "1 Oak St", "city": "Decatur", "state": "IL",
                "beds": 2, "baths": 1, "monthlyPayment": 600, "moveIn": 2000, "lockedPrice": 50000,
                "copy": "It is ready to move into."}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "images").mkdir()
            page = seo.write_listing(root, home, "en", template)
        self.assertIn('id="conditionLine" hidden', page)
        self.assertNotIn(">Condition<", page)
        home["condition"] = "Average"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "images").mkdir()
            shown = seo.write_listing(root, home, "en", template)
        self.assertIn('id="conditionLine"', shown)
        self.assertNotIn('id="conditionLine" hidden', shown)
        self.assertIn(">Condition<", shown)
        self.assertIn("Average", shown)


class Templates(unittest.TestCase):
    def test_homepage_does_not_probe_covers(self):
        text = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("Promise.allSettled(LISTINGS.map", text)
        self.assertNotIn("photoReady", text)
        self.assertIn("function hasRealPhoto", text)
        self.assertIn("h.cardPhoto", text)
        self.assertIn('loading="lazy"', text)
        self.assertIn("cardWidth", text)
        self.assertLess(text.find("hasRealPhoto(b)"), text.find("VisitorNear.compare"))
        cities = text.find('id="cities"')
        listings = text.find('id="listings"')
        self.assertGreater(cities, listings)

    def test_listing_template_has_hidden_condition_and_mobile_bar(self):
        text = (ROOT / "home.html").read_text(encoding="utf-8")
        self.assertIn('id="conditionLine" hidden', text)
        self.assertIn('id="stSms"', text)
        self.assertIn("max-width:899px", text)
        self.assertIn("--go:#d43333", text)


if __name__ == "__main__":
    unittest.main()
