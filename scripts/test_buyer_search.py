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

    def test_address_search_opens_one_listing(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        script = r"""
const fs = require("fs");
const vm = require("vm");
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
    return raw;
  };
  homes.push({ id: match[1], address: field("address"), city: field("city"), state: field("state"), zip: field("zip") });
}
const one = (q) => {
  const hit = ctx.BuyerSearch.uniqueListing(q, homes);
  return hit ? hit.id : "";
};
process.stdout.write(JSON.stringify({
  fox: one("2949 Foxbridge Rd"),
  street: one("Foxbridge"),
  city: one("Springfield, IL"),
  oak: one("Oak")
}));
"""
        out = subprocess.check_output([node, "-e", script], cwd=ROOT, text=True)
        data = json.loads(out)
        self.assertEqual(data["fox"], "springfield-il-2949-foxbridge")
        self.assertEqual(data["street"], "springfield-il-2949-foxbridge")
        self.assertEqual(data["city"], "")
        self.assertEqual(data["oak"], "")

    def test_address_typeahead_matches(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        script = r"""
const fs = require("fs");
const vm = require("vm");
const ctx = { console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync("buyer-search.js", "utf8"), ctx);
const homes = [
  { id: "oblong-il-807-illinois", address: "807 W Illinois St,", city: "Oblong", state: "IL", zip: "62449", status: "Available" },
  { id: "eastalton-il-136-illinois", address: "136 Illinois St", city: "East Alton", state: "IL", zip: "62024", status: "Available" },
  { id: "eaststlouis-il-541-27th", address: "541 North 27th Street", city: "East St. Louis", state: "IL", status: "Available" },
  { id: "springfield-il-1132-oak", address: "1132 E Oak St", city: "Springfield", state: "IL", status: "Pending" },
  { id: "decatur-il-1-main", address: "1 Main St", city: "Decatur", state: "IL", zip: "62526", status: "Available" },
  { id: "duquoin-il-322-cole", address: "322 S Cole St", city: "Du Quoin", state: "IL", status: "Available" }
];
const ids = (q) => ctx.BuyerSearch.matchAddresses(q, homes).map(h => h.id);
process.stdout.write(JSON.stringify({
  partial: ids("807 W Illinois"),
  mixed: ids("807 illinois oblong"),
  abbrev: ids("541 N 27th"),
  long: ids("541 north 27th st"),
  city: ids("Decatur"),
  zip: ids("62526"),
  none: ids("zzzz-not-a-home"),
  excluded: ids("322 cole"),
  pending: ids("1132 oak")
}));
"""
        out = subprocess.check_output([node, "-e", script], cwd=ROOT, text=True)
        data = json.loads(out)
        self.assertEqual(data["partial"], ["oblong-il-807-illinois"])
        self.assertEqual(data["mixed"], ["oblong-il-807-illinois"])
        self.assertEqual(data["abbrev"], ["eaststlouis-il-541-27th"])
        self.assertEqual(data["long"], ["eaststlouis-il-541-27th"])
        self.assertEqual(data["city"], [])
        self.assertEqual(data["zip"], [])
        self.assertEqual(data["none"], [])
        self.assertEqual(data["excluded"], [])
        self.assertEqual(data["pending"], ["springfield-il-1132-oak"])


if __name__ == "__main__":
    unittest.main()
