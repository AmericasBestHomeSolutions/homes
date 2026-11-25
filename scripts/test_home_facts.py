"""home-facts.json matches the contractor notes and the documented schema.

    python3 scripts/test_home_facts.py
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import listing_facts as lf  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SYSTEMS = {"furnace", "plumbing", "electrical", "roof", "foundation"}


def homes():
    text = (ROOT / "homes.js").read_text(encoding="utf-8").split("const SOLD_CARDS")[0]
    rows = []
    for match in re.finditer(r'\n  \{\n    id: "([^"]+)",[\s\S]*?\n  \},', text):
        note = re.search(r'\n    contractor:\s*("(?:\\.|[^"\\])*"),', match.group(0))
        rows.append({"id": match.group(1), "contractor": json.loads(note.group(1)) if note else ""})
    return rows


class Facts(unittest.TestCase):
    def test_schema_and_seed(self):
        doc = json.loads((ROOT / "data" / "home-facts.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["version"], 1)
        self.assertRegex(doc["updated"], r"^\d{4}-\d{2}-\d{2}$")
        seeded = lf.seed_document(homes(), doc["updated"])
        self.assertEqual(doc["homes"], seeded["homes"])
        blob = json.dumps(doc)
        for banned in ("lockedPrice", "monthlyPayment", "moveIn", '"price"', '"down"'):
            self.assertNotIn(banned, blob)
        for hid, rec in doc["homes"].items():
            self.assertEqual(set(rec), {"condition", "fit"})
            for key, row in rec["condition"].items():
                self.assertIn(key, SYSTEMS)
                self.assertEqual(row["status"], "reported")
                self.assertTrue(row["en"] and row["es"] and row["source"])
                self.assertRegex(row["as_of"], r"^\d{4}-\d{2}-\d{2}$")
            blob_home = json.dumps(rec)
            for banned in ("rate", "monthly_covers", "deed_transfer", "cash_before_keys", "interest"):
                self.assertNotIn(banned, blob_home)

    def test_unnamed_systems_are_skipped(self):
        self.assertEqual(lf.notes_to_systems("full gut rehab; not livable as it stands"), {})
        mapped = lf.notes_to_systems("no electrical (copper wiring taken); furnace needs work")
        self.assertEqual(set(mapped), {"electrical", "furnace"})


if __name__ == "__main__":
    unittest.main()
