"""Offline tests: the CRM's Sold / Pending beats the portal's Available (Joe, 2026-11-13). Synthetic rows only."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import portal_sync as ps  # noqa: E402

HOMES_JS = ('const HOMES = [\n  {\n    id: "barling-ar-2207-k",\n    address:     "2207 K St",\n'
            '    city:  "Barling",\n    state: "AR",\n    status: "Available",\n    photos:    ["a.jpg"],\n  },\n'
            '  {\n    id: "peoria-il-100-main",\n    address:     "100 Main St",\n'
            '    city:  "Peoria",\n    state: "IL",\n    status: "Available",\n    photos:    ["a.jpg"],\n  },\n];\n'
            'const SOLD_CARDS = [];\n')


def prow(address, city, state, status="Available", prop="PROP-1"):
    return {"Portal PROP id": prop, "Address": address, "City": city, "State": state, "Zip": "72921", "Beds": "3",
            "Baths": "1", "Sqft": "1200", "Price": "60000", "Down payment": "3000", "Monthly payment": "700",
            "Status": status, "Photos link": "", "Direct note": "", "Direct note es": ""}


def plan(portal, crm, site=HOMES_JS):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "homes.js").write_text(site, encoding="utf-8")
        return ps.plan(root, portal, crm, [])


class CrmWins(unittest.TestCase):
    def test_site_home_is_retired_when_crm_says_sold(self):
        p = plan([prow("2207 K St", "Barling", "AR")], [{"Unique ID": "barling-ar-2207-k", "Property Status": "Sold"}])
        self.assertEqual([(r["id"], r["why"]) for r in p["retire"]], [("barling-ar-2207-k", "sold")])
        self.assertEqual(len(p["held"]), 1)

    def test_pending_and_deposit(self):
        p = plan([prow("2207 K St", "Barling", "AR")], [{"Unique ID": "barling-ar-2207-k", "Property Status": "Pending"}])
        self.assertEqual(p["retire"][0]["why"], "pending")
        p = plan([prow("2207 K St", "Barling", "AR")], [{"Unique ID": "barling-ar-2207-k", "Property Status": "Deposit received"}])
        self.assertEqual(p["retire"][0]["why"], "sold")

    def test_new_portal_home_closed_in_crm_is_not_added(self):
        p = plan([prow("55 New St", "Peoria", "IL", prop="PROP-9")], [{"Unique ID": "peoria-il-55-new", "Property Status": "SOLD"}])
        self.assertEqual((p["add"], p["retire"], p["relist"]), ([], [], []))
        self.assertEqual(len(p["held"]), 1)

    def test_crm_available_or_missing_changes_nothing(self):
        for crm in ([], [{"Unique ID": "barling-ar-2207-k", "Property Status": "Available"}]):
            p = plan([prow("2207 K St", "Barling", "AR")], crm)
            self.assertEqual((p["retire"], p["held"]), ([], []))

    def test_not_listed_still_relists_as_before(self):
        p = plan([prow("55 New St", "Peoria", "IL", prop="PROP-9")], [{"Unique ID": "peoria-il-55-new", "Property Status": "Not listed"}])
        self.assertEqual((len(p["add"]), len(p["relist"]), p["held"]), (1, 1, []))

    def test_direct_listings_are_left_to_staff(self):
        p = plan([prow("2207 K St", "Barling", "AR", prop="DIRECT")], [{"Unique ID": "barling-ar-2207-k", "Property Status": "Sold"}])
        self.assertEqual((p["retire"], p["held"]), ([], []))

    def test_summary_names_the_held_homes(self):
        p = plan([prow("2207 K St", "Barling", "AR")], [{"Unique ID": "barling-ar-2207-k", "Property Status": "Sold"}])
        p.setdefault("hand", [])
        self.assertIn("Held by the CRM", ps.summary(p))


if __name__ == "__main__":
    unittest.main()
