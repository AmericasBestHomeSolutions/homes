"""python3 scripts/test_consistency.py"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_consistency as cc  # noqa: E402

JS = """const HOMES = [
  {{
    id: "springfield-il-2949-foxbridge",
    lockedPrice: {price},
    moveIn: {down},
    monthlyPayment: {monthly},
    status: "{status}",
  }},
];
const SOLD_CARDS = [];
"""


def write_site(root: Path, price, down, monthly, status, facts):
    root.mkdir(parents=True, exist_ok=True)
    (root / "homes.js").write_text(JS.format(price=price, down=down, monthly=monthly, status=status), encoding="utf-8")
    data = root / "data"
    data.mkdir(exist_ok=True)
    (data / "home-facts.json").write_text(facts, encoding="utf-8")


class Consistency(unittest.TestCase):
    def test_match_and_mismatch(self):
        facts = json.dumps({"version": 1, "homes": {}})
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            en, es = base / "homes", base / "casas"
            write_site(en, 90000, 3000, 892, "Available", facts)
            write_site(es, 90000, 3000, 892, "Available", facts)
            self.assertEqual(cc.compare(en, es), [])
            write_site(es, 90000, 2500, 892, "Available", facts)
            self.assertTrue(any("moveIn" in line for line in cc.compare(en, es)))
            write_site(es, 90000, 3000, 892, "Available", facts + "\n")
            self.assertTrue(any("home-facts" in line for line in cc.compare(en, es)))


if __name__ == "__main__":
    unittest.main()
