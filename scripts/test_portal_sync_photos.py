"""Offline tests for the photo sources in portal_sync.py (no network)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import portal_sync as ps  # noqa: E402


class PhotosColumn(unittest.TestCase):
    def test_found_by_header_name(self):
        head = ["Portal PROP id"] + [f"c{i}" for i in range(1, 21)] + ["Photos link"]
        self.assertEqual(ps.photos_column_range(head), "'Portal Backup'!V:V")

    def test_case_and_spaces(self):
        head = [f"c{i}" for i in range(25)] + ["  photos LINK "]
        self.assertEqual(ps.photos_column_range(head), "'Portal Backup'!Z:Z")

    def test_missing_column(self):
        self.assertIsNone(ps.photos_column_range(["Portal PROP id", "Address", "Lockbox code"]))

    def test_never_inside_a_to_m(self):
        self.assertIsNone(ps.photos_column_range(["Photos link", "Address"]))

    def test_col_letter(self):
        self.assertEqual([ps.col_letter(i) for i in (0, 21, 25, 26, 27)], ["A", "V", "Z", "AA", "AB"])


class Links(unittest.TestCase):
    def test_readable_kinds(self):
        for url in ("https://drive.google.com/drive/folders/abcDEF123",
                    "https://www.dropbox.com/scl/fo/x/y?rlkey=z&dl=0",
                    "https://photos.app.goo.gl/AbC123",
                    "https://photos.google.com/share/AF1Qip?key=k",
                    "https://share.icloud.com/photos/0a4nmaDyBTNFiPFmprj4Z5rQA",
                    "https://www.icloud.com/sharedalbum/#B0aGWZuqDGQ8Xy_-",
                    "https://www.icloud.com/photos/#/icloudlinks/02cVAr6TXcH5sr7O0gBJLeUFw"):
            self.assertTrue(ps.readable(url), url)

    def test_unreadable_kept_for_browser_pass(self):
        cell = "https://1drv.ms/f/s!abc and https://drive.google.com/drive/folders/abcDEF123."
        self.assertEqual(ps.photo_links(cell), ["https://drive.google.com/drive/folders/abcDEF123"])
        self.assertEqual(ps.album_links(cell), ["https://drive.google.com/drive/folders/abcDEF123", "https://1drv.ms/f/s!abc"])
        self.assertFalse(ps.readable("https://1drv.ms/f/s!abc"))

    def test_label_hides_token(self):
        label = ps.link_label("https://share.icloud.com/photos/0a4nmaDyBTNFiPFmprj4Z5rQA")
        self.assertTrue(label.startswith("[iCloud …"))
        self.assertNotIn("0a4nmaDy", label)


class Tiers(unittest.TestCase):
    def test_portal_link_first_then_note(self):
        item = ps.photo_item("x", {"Portal photos": "https://a", "Photo links": "https://b"})
        self.assertEqual(item["tiers"], [["https://a"], ["https://b"]])

    def test_first_source_with_photos_wins(self):
        import tempfile
        from io import BytesIO
        from PIL import Image
        buf = BytesIO()
        Image.new("RGB", (40, 30), "red").save(buf, "JPEG")
        jpg = buf.getvalue()
        calls = []

        def fetch(links):
            calls.append(links)
            return [] if links == ["https://dead"] else [jpg, jpg]

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "images").mkdir()
            (root / "homes.js").write_text('const HOMES = [\n  {\n    id: "h1",\n    photos:    [],\n  },\n];\n')
            p = {"photos": [{"id": "h1", "tiers": [["https://dead"], ["https://good"], ["https://wa"]],
                             "links": ["https://dead", "https://good", "https://wa"]}]}
            ps.photos_into(root, p, fetch=fetch)
            self.assertEqual(calls, [["https://dead"], ["https://good"]])
            self.assertEqual(p["photo_result"], {"h1": 2})
            self.assertTrue((root / "images" / "h1.jpg").is_file())
            self.assertIn('"images/h1-1.jpg"', (root / "homes.js").read_text())

    def test_dead_links_reported_and_cap(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "images").mkdir()
            homes = "".join(f'  {{\n    id: "h{i}",\n    photos:    [],\n  }},\n' for i in range(ps.MAX_PHOTO_HOMES + 2))
            (root / "homes.js").write_text("const HOMES = [\n" + homes + "];\n")
            p = {"photos": [{"id": f"h{i}", "tiers": [["https://dead"]], "links": ["https://dead"]}
                            for i in range(ps.MAX_PHOTO_HOMES + 2)]}
            ps.photos_into(root, p, fetch=lambda links: [])
            self.assertEqual(len(p["photo_failed"]), ps.MAX_PHOTO_HOMES)
            self.assertEqual(len(p["photo_waiting"]), 2)
            p.update({"add": [], "update": [], "retire": [], "hand": []})
            text = ps.summary(p)
            self.assertIn("gave no photos", text)
            self.assertIn("waiting for the next run (2)", text)

    def test_time_budget(self):
        import tempfile
        ticks = iter([0, 0, ps.PHOTO_BUDGET_S + 1, ps.PHOTO_BUDGET_S + 2])
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "images").mkdir()
            (root / "homes.js").write_text('const HOMES = [\n  {\n    id: "a",\n    photos:    [],\n  },\n'
                                           '  {\n    id: "b",\n    photos:    [],\n  },\n];\n')
            p = {"photos": [{"id": h, "tiers": [["https://x"]], "links": ["https://x"]} for h in ("a", "b")]}
            ps.photos_into(root, p, fetch=lambda links: [], clock=lambda: next(ticks))
            self.assertEqual(list(p["photo_failed"]), ["a"])
            self.assertEqual(p["photo_waiting"], ["b"])


class Whitelist(unittest.TestCase):
    def test_offline_photos_link_and_no_private_columns(self):
        rows = ps.whitelist([{"Portal PROP id": "PROP-1", "Photos link": "see https://photos.app.goo.gl/AbC",
                              "Lockbox code": "1234", "Seller phone": "555"}])
        self.assertEqual(rows[0]["Portal photos"], "https://photos.app.goo.gl/AbC")
        self.assertNotIn("Lockbox code", rows[0])
        self.assertNotIn("Seller phone", rows[0])


if __name__ == "__main__":
    unittest.main()
