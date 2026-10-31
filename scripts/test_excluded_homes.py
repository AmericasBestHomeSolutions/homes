"""python3 scripts/test_excluded_homes.py"""
import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import excluded_homes

JS = '''/* --- the homes (3 live, x) --- */
const HOMES = [
  {
    id: "a-1-keep",
    address:     "1 Keep St",
  },
  {
    id: "b-2-junk",
    address:     "Junk",
  },
  {
    id: "c-3-keep",
    address:     "3 Keep St",
  }
];
const SOLD_CARDS = [
];
'''

class T(unittest.TestCase):
    def test_apply(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d); (r / "data").mkdir(); (r / "images" / "sv").mkdir(parents=True)
            (r / "homes.js").write_text(JS)
            (r / "sitemap.xml").write_text('<urlset>\n  <url><loc>x/a-1-keep.html</loc></url>\n  <url><loc>x/b-2-junk.html</loc></url>\n</urlset>\n')
            (r / "b-2-junk.html").write_text("old page"); (r / "images" / "sv" / "b-2-junk.jpg").write_bytes(b"x")
            (r / "data" / "excluded-homes.json").write_text(json.dumps([{"id": "b-2-junk", "reason": "t"}]))
            self.assertEqual(excluded_homes.apply(r, "en"), ["b-2-junk"])
            js = (r / "homes.js").read_text()
            self.assertNotIn("b-2-junk", js); self.assertIn('"a-1-keep"', js); self.assertIn('"c-3-keep"', js)
            self.assertIn("(2 live,", js)
            self.assertNotIn("b-2-junk", (r / "sitemap.xml").read_text())
            self.assertIn('url=/"', (r / "b-2-junk.html").read_text())
            self.assertFalse((r / "images" / "sv" / "b-2-junk.jpg").exists())
            self.assertEqual(excluded_homes.apply(r, "en"), [])   # idempotent

    def test_no_list(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(excluded_homes.apply(Path(d), "en"), [])

if __name__ == "__main__":
    unittest.main()
