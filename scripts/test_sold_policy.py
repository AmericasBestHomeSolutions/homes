"""Synthetic checks for the sold-home policy and the sold-card renderer.

Run from the repo root:  python3 scripts/test_sold_policy.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sold_policy as policy

ROOT = Path(__file__).resolve().parents[1]

STREETS = [
    ("1755 N Monroe St", "Monroe St", "1755"),
    ("809 S Don Ryan Street", "Don Ryan Street", "809"),
    ("1510 23rd St", "23rd St", "1510"),
    ("3 Pohlman Lane", "Pohlman Lane", "3"),
    ("210-409 N 17th St", "17th St", "210-409"),
    ("610R Fremont St", "Fremont St", "610R"),
    ("1746 N Woodford St, Decatur, IL 62526", "Woodford St", "1746"),
    ("1729 N woodford St.", "Woodford St", "1729"),
    ("2120 St. Louis Ave.", "St. Louis Ave", "2120"),
    ("725 N 39th Street", "39th Street", "725"),
    ("100 E St", "E St", "100"),
    ("123 North St", "North St", "123"),
]


class PolicyTests(unittest.TestCase):
    def test_street_names(self):
        for address, street, number in STREETS:
            self.assertEqual(policy.street_name(address), street, address)
            self.assertEqual(policy.house_number(address), number, address)
            self.assertNotIn(number, street)

    def test_pending_override_is_sold_and_relist_removes_it(self):
        home = {"id": "decatur-il-1755-monroe", "status": "Available", "address": "1755 N Monroe St"}
        self.assertEqual(policy.public_bucket(home["status"], {"state": "pending"}), "sold")
        self.assertEqual(policy.public_bucket(home["status"], "pending"), "sold")
        self.assertEqual(policy.public_bucket(home["status"], "PENDING"), "sold")
        self.assertEqual(policy.public_bucket(home["status"], None), "active")
        self.assertEqual(policy.public_bucket("Pending", None), "sold")
        self.assertEqual(policy.public_bucket("pending", None), "sold")
        self.assertEqual(policy.public_bucket("Sold", None), "sold")
        self.assertEqual(policy.public_bucket("Available", "hold"), "hold")
        self.assertEqual(policy.public_bucket("Available", {"state": "sold", "soldOn": "2026-10-02"}), "sold")

    def test_photo_filename_has_no_digits_or_address(self):
        name = policy.public_photo_filename("decatur-il-1755-monroe")
        self.assertTrue(name.endswith(".jpg"))
        self.assertRegex(name, r"^[a-z]{16}\.jpg$")
        self.assertNotIn("1755", name)
        self.assertNotIn("monroe", name)
        self.assertNotIn("decatur", name)

    def test_card_from_synthetic_home_hides_the_house_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photo = root / "images" / "decatur-il-1755-monroe-1.jpg"
            photo.parent.mkdir(parents=True)
            photo.write_bytes(b"\xff\xd8\xff\xd9")
            home = {
                "id": "decatur-il-1755-monroe",
                "address": "1755 N Monroe St",
                "city": "Decatur",
                "state": "IL",
                "status": "Pending",
                "photos": ["images/decatur-il-1755-monroe-1.jpg"],
            }
            card = policy.build_sold_card(
                home,
                override={"state": "pending", "soldOn": "2026-10-17"},
                image_root=root,
                dest_dir=root / "images" / "sold",
            )
            self.assertEqual(card["street"], "Monroe St")
            self.assertEqual(card["soldOn"], "2026-10-17")
            leaks = policy.card_leaks(
                card,
                house="1755",
                address="1755 N Monroe St",
                home_id=home["id"],
                source_photo=home["photos"][0],
            )
            self.assertEqual(leaks, [], card)
            copied = root / card["photo"]
            self.assertTrue(copied.is_file())
            self.assertEqual(copied.read_bytes(), photo.read_bytes())

    def test_apply_on_a_synthetic_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "images").mkdir()
            (root / "images" / "decatur-il-1755-monroe-1.jpg").write_bytes(b"\xff\xd8\xff\xd9")
            (root / "homes.js").write_text(
                """const CONTACT = { phone: "1" };
const HOMES = [
  {
    id: "decatur-il-1755-monroe",
    address: "1755 N Monroe St",
    city: "Decatur",
    state: "IL",
    status: "Pending",
    photos: ["images/decatur-il-1755-monroe-1.jpg"],
  },
  {
    id: "keep-il-10-oak",
    address: "10 Oak St",
    city: "Keep",
    state: "IL",
    status: "Available",
    photos: [],
  },
];
const RECENTLY_SOLD = [{"city": "Flint", "state": "MI", "soldOn": "2026-10-17"}];
""",
                encoding="utf-8",
            )
            (root / "decatur-il-1755-monroe.html").write_text(
                "<title>1755 N Monroe St</title><p>1755 N Monroe St, Decatur, IL</p>",
                encoding="utf-8",
            )
            (root / "keep-il-10-oak.html").write_text("<p>still listed</p>", encoding="utf-8")
            (root / "sitemap.xml").write_text(
                "<urlset>\n"
                "  <url><loc>https://getownerfinancedhomes.com/decatur-il-1755-monroe.html</loc></url>\n"
                "  <url><loc>https://getownerfinancedhomes.com/keep-il-10-oak.html</loc></url>\n"
                "</urlset>\n",
                encoding="utf-8",
            )
            overrides = root / "overrides.json"
            overrides.write_text(json.dumps({
                "decatur-il-1755-monroe": {"state": "pending", "soldOn": "2026-10-17"},
                "keep-il-10-oak": "hold",
            }), encoding="utf-8")
            # Hold must not retire the available home. Pending status still does.
            report = policy.apply_site(root, overrides)
            self.assertEqual(report["retired"], ["decatur-il-1755-monroe"])
            catalog = policy.read_catalog(root / "homes.js")
            self.assertEqual([home["id"] for home in catalog["HOMES"]], ["keep-il-10-oak"])
            self.assertEqual(catalog["SOLD_CARDS"][0]["street"], "Monroe St")
            blob = (root / "homes.js").read_text(encoding="utf-8")
            sold_at = blob.index("const SOLD_CARDS")
            self.assertNotIn("1755", blob[sold_at:])
            self.assertNotIn("decatur-il-1755-monroe", blob[sold_at:])
            page = (root / "decatur-il-1755-monroe.html").read_text(encoding="utf-8")
            self.assertNotIn("1755", page)
            self.assertNotIn("Monroe", page)
            self.assertIn('content="0;url=/"', page)
            self.assertIn("noindex", page)
            self.assertIn("still listed", (root / "keep-il-10-oak.html").read_text(encoding="utf-8"))
            sitemap = (root / "sitemap.xml").read_text(encoding="utf-8")
            self.assertNotIn("decatur-il-1755-monroe", sitemap)
            self.assertIn("keep-il-10-oak", sitemap)
            again = policy.apply_site(root, overrides)
            self.assertEqual(again["retired"], [])
            self.assertEqual(policy.read_catalog(root / "homes.js")["SOLD_CARDS"][0]["street"], "Monroe St")


class RenderTests(unittest.TestCase):
    def test_page_renderer_omits_house_numbers(self):
        script = r"""
const fs = require("fs");
const vm = require("vm");
const src = fs.readFileSync(process.argv[1], "utf8");
const context = { window: null, globalThis: {} };
context.globalThis = context;
vm.runInNewContext(src, context);
const SoldCards = context.SoldCards;
const cases = JSON.parse(process.argv[2]);
const bad = [];
for (const row of cases) {
  const got = SoldCards.streetName(row[0]);
  if (got !== row[1]) bad.push(row[0] + " => " + got + " expected " + row[1]);
}
const malicious = {
  street: "1755 N Monroe St",
  city: "Decatur",
  state: "IL",
  soldOn: "2026-10-17",
  photo: "images/decatur-il-1755-monroe-1.jpg",
  address: "1755 N Monroe St",
  id: "decatur-il-1755-monroe"
};
const html = SoldCards.renderSection([malicious], "en");
const es = SoldCards.renderSection([{
  street: "Monroe St", city: "Decatur", state: "IL", soldOn: "2026-10-17",
  photo: "images/sold/abcdefghijklmnop.jpg"
}], "es");
const forbidden = ["1755", "decatur-il-1755-monroe", "N Monroe", "images/decatur"];
for (const token of forbidden) {
  if (html.includes(token)) bad.push("english card contains " + token);
}
if (/<a[\s>]/.test(html)) bad.push("card is a link");
if (!html.includes("Monroe St")) bad.push("missing street");
if (!html.includes("Decatur, IL")) bad.push("missing city");
if (!html.includes(">Sold<")) bad.push("missing badge");
if (html.includes("images/decatur") || /src="[^"]*\d/.test(html)) bad.push("photo src leaked");
if (!es.includes("Vendida")) bad.push("spanish badge missing: " + es);
if (!es.includes("Vendida en")) bad.push("spanish date missing: " + es);
if (SoldCards.safePhoto("images/decatur-il-1755-monroe-1.jpg")) bad.push("unsafe photo accepted");
process.stdout.write(bad.join("\n"));
process.exit(bad.length ? 1 : 0);
"""
        result = subprocess.run(
            ["node", "-e", script, str(ROOT / "sold-cards.js"), json.dumps(STREETS)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
