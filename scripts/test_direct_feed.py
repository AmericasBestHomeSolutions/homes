"""Offline tests for direct listings in portal_sync.py: the CRM feed becomes portal-shaped rows, only staff retire."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import portal_sync as ps  # noqa: E402

FEED = {"homes": [
    {"id": "stlouis-mo-100-example", "address": "100 Example Ave", "city": "St. Louis", "state": "MO", "zip": "63115",
     "beds": "2", "baths": "1", "sqft": "", "price": "79000", "down": "3000", "monthly": "910", "status": "available",
     "listed": "2026-11-01", "photos": ["https://drive.google.com/drive/folders/abcdefghijk"],
     "note": "Needs a gas meter set before the occupancy inspection", "note_es": ""},
    {"id": "stlouis-mo-200-sample", "address": "200 Sample St", "city": "St. Louis", "state": "MO", "zip": "",
     "beds": "", "baths": "", "sqft": "", "price": "50000", "down": "2000", "monthly": "700", "status": "withdrawn",
     "listed": "2026-10-01", "photos": [], "note": "", "note_es": ""},
    {"id": "bad", "address": "", "state": "MO", "status": "available"},
    "not a row",
]}


class Feed(unittest.TestCase):
    def test_rows_and_statuses(self):
        rows = ps.direct_rows(FEED["homes"])
        self.assertEqual([r["Status"] for r in rows], ["Available", "Not in portal"])
        self.assertEqual(rows[0]["Portal PROP id"], "DIRECT")
        self.assertEqual(rows[0]["Portal photos"], "https://drive.google.com/drive/folders/abcdefghijk")
        for r in rows:
            self.assertFalse({"seller", "Lockbox code", "contact"} & set(r))

    def test_unreadable_feed_is_none(self):
        def boom(_url):
            raise OSError("down")
        self.assertIsNone(ps.read_direct("https://crm.example/api/public/direct-homes", fetch=boom))
        self.assertIsNone(ps.read_direct("http://crm.example/x", fetch=lambda u: FEED))
        self.assertEqual(len(ps.read_direct("https://crm.example/x", fetch=lambda u: FEED)), 4)

    def test_plan_adds_available_and_retires_only_by_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "homes.js").write_text(
                'const HOMES = [\n  {\n    id: "stlouis-mo-200-sample",\n    address:     "200 Sample St",\n'
                '    city:  "St. Louis",\n    state: "MO",\n    photos:    [],\n  },\n];\nconst SOLD_CARDS = [];\n',
                encoding="utf-8")
            p = ps.plan(root, ps.direct_rows(FEED["homes"]), [], [])
            self.assertEqual([r["id"] for r in p["add"]], ["stlouis-mo-100-example"])
            self.assertEqual([(r["id"], r["why"]) for r in p["retire"]], [("stlouis-mo-200-sample", "gone")])
            # A direct home simply missing from the feed is never retired.
            p2 = ps.plan(root, ps.direct_rows(FEED["homes"][:1]), [], [])
            self.assertEqual(p2["retire"], [])


class Copy(unittest.TestCase):
    base = {"monthly": 910, "down": 3000, "price": 79000, "city": "St. Louis", "state": "MO", "sqft": None}

    def test_portal_copy_unchanged_when_beds_known(self):
        r = {**self.base, "beds": 3, "baths": 1}
        self.assertIn("This 3-bedroom, 1-bath home in St. Louis, MO gives you", ps.copy_en(r))
        self.assertIn("Esta casa de 3 recámaras y 1 baño en St. Louis, MO le da", ps.copy_es(r))

    def test_unknown_size_and_note(self):
        r = {**self.base, "beds": 0, "baths": 0, "note": "Needs a gas meter set before the occupancy inspection"}
        en = ps.copy_en(r)
        self.assertIn("This home in St. Louis", en)
        self.assertNotIn("0-bedroom", en)
        self.assertTrue(en.endswith("Needs a gas meter set before the occupancy inspection."))
        self.assertIn("Esta casa en St. Louis", ps.copy_es(r))


if __name__ == "__main__":
    unittest.main()
