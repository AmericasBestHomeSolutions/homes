"""The Springfield budget search is derived from homes.js, not hard-coded.

    python3 scripts/test_buyer_search.py
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Springfield(unittest.TestCase):
    def test_budget_groups(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        script = r"""
const fs = require("fs");
const vm = require("vm");
const root = process.cwd();
const ctx = { console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync("buyer-search.js", "utf8"), ctx);
const text = fs.readFileSync("homes.js", "utf8").split("const SOLD_CARDS")[0];
const homes = [];
for (const match of text.matchAll(/\n  \{\n    id: "([^"]+)",[\s\S]*?\n  \},/g)) {
  const block = match[0];
  const field = (key) => {
    const m = block.match(new RegExp("\\n    " + key + ":\\s*(\"(?:\\\\.|[^\"\\\\])*\"|[^,\\n]*),"));
    if (!m) return null;
    const raw = m[1].trim();
    if (raw.startsWith('"')) return JSON.parse(raw);
    if (raw === "null" || raw === "") return null;
    return raw;
  };
  homes.push({
    id: match[1], address: field("address"), city: field("city"), state: field("state"),
    zip: field("zip"), status: field("status"), moveIn: field("moveIn"),
    monthlyPayment: field("monthlyPayment"), lat: field("lat"), lng: field("lng"),
    hasPhoto: field("hasPhoto")
  });
}
const result = ctx.BuyerSearch.groups(homes, { q: "Springfield, IL", downMax: 2500, payMax: 1000 });
const ids = (rows) => rows.map(h => h.id);
process.stdout.write(JSON.stringify({
  primary: ids(result.primary),
  over: ids(result.over),
  nearby: result.nearby.map(h => ({ id: h.id, miles: h._miles, address: h.address }))
}));
"""
        out = subprocess.check_output([node, "-e", script], cwd=ROOT, text=True)
        data = json.loads(out)
        self.assertIn("springfield-il-1132-oak", data["primary"])
        self.assertEqual(data["over"], ["springfield-il-2949-foxbridge"])
        nearby_ids = [row["id"] for row in data["nearby"]]
        for hid in (
            "decatur-il-1096-green",
            "decatur-il-1373-university",
            "decatur-il-1527-oakland",
            "decatur-il-957-view",
            "decatur-il-515-boyd",
        ):
            self.assertIn(hid, nearby_ids, hid)
        for row in data["nearby"]:
            if row["id"].startswith("decatur-il-"):
                self.assertGreaterEqual(row["miles"], 30)
                self.assertLessEqual(row["miles"], 45)


if __name__ == "__main__":
    unittest.main()
