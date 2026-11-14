"""Offline tests: the CRM status feed may only CLOSE live site homes. Synthetic rows only."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import portal_sync as ps  # noqa: E402
from test_portal_sync_crm_wins import HOMES_JS, prow  # noqa: E402

K, M = "barling-ar-2207-k", "peoria-il-100-main"
PORTAL = [prow("2207 K St", "Barling", "AR"), prow("100 Main St", "Peoria", "IL", prop="PROP-2")]


def plan(feed, portal=PORTAL, crm=(), site=HOMES_JS):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "homes.js").write_text(site, encoding="utf-8")
        return ps.plan(root, list(portal), list(crm), [], feed)


def feed(*items):
    return ps.read_status_feed(data={"homes": [{"id": i, "status": s} for i, s in items]})


class StatusFeed(unittest.TestCase):
    def test_feed_closes_live_home(self):
        p = plan(feed((K, "Sold"), (M, "Pending")))
        self.assertEqual({(r["id"], r["why"]) for r in p["retire"]}, {(K, "sold"), (M, "pending")})
        self.assertEqual(len(p["held"]), 2)
        self.assertIn("Status feed: 2 homes read, 2 closed on the site", ps.summary(p))

    def test_available_changes_nothing(self):
        p = plan(feed((K, "Available")))
        self.assertEqual((p["retire"], p["held"]), ([], []))

    def test_feed_never_adds_or_relists(self):
        site = HOMES_JS.replace("peoria-il-100-main", "other-il-1-x")
        p = plan(feed(("peoria-il-100-main", "Sold"), ("ghost-xx-1-a", "Sold")), site=site)
        self.assertEqual((p["retire"], p["held"]), ([], []))
        p = plan(feed((M, "Available")), portal=[prow("55 New St", "Peoria", "IL", prop="P9")])
        self.assertEqual(p["relist"], [])

    def test_unreadable_changes_nothing(self):
        def boom(url):
            raise OSError("HTTP 503")
        cases = [None, ps.read_status_feed(url="https://x.test/a", fetch=boom),
                 ps.read_status_feed(data={"homes": []}), ps.read_status_feed(data="not json"),
                 ps.read_status_feed(data={"homes": [{"id": K, "status": "Weird"}]}),
                 ps.read_status_feed(data={"homes": [{"id": "Bad Id!", "status": "Sold"}]}),
                 ps.read_status_feed(url="http://x.test/a", fetch=lambda u: {"homes": [{"id": K, "status": "Sold"}]})]
        for f in cases:
            self.assertIsNone(f)
            p = plan(f)
            self.assertEqual((p["retire"], p["held"]), ([], []))
            self.assertIn("Status feed: not read; using CRM_Properties only", ps.summary(p))

    def test_malformed_items_ignored(self):
        f = ps.read_status_feed(data={"homes": ["x", {"id": 5, "status": "Sold"}, {"id": K, "status": "sold"}]})
        self.assertEqual(f, {K: "Sold"})

    def test_guard_of_15(self):
        ids = [f"town-il-{i}-a" for i in range(16)]
        site = "const HOMES = [\n" + "".join(
            f'  {{\n    id: "{i}",\n    address:     "{n} A St",\n    city:  "Town",\n    state: "IL",\n    status: "Available",\n    photos:    ["a.jpg"],\n  }},\n'
            for n, i in enumerate(ids)) + "];\nconst SOLD_CARDS = [];\n"
        p = plan(feed(*[(i, "Sold") for i in ids]), portal=[], site=site)
        self.assertEqual(p["retire"], [])
        self.assertTrue(p["status_feed"]["refused"])
        self.assertTrue(any("STATUS FEED REFUSED" in h for h in p["hand"]))
        p = plan(feed(*[(i, "Sold") for i in ids[:15]]), portal=[], site=site)
        self.assertEqual(len(p["retire"]), 15)

    def test_no_double_count_with_crm_wins(self):
        p = plan(feed((K, "Sold")), crm=[{"Unique ID": K, "Property Status": "Sold"}])
        self.assertEqual([r["id"] for r in p["retire"]], [K])
        self.assertEqual(len(p["held"]), 1)

    def test_direct_rows_never_closed(self):
        p = plan(feed((K, "Sold")), portal=[prow("2207 K St", "Barling", "AR", prop="DIRECT")])
        self.assertEqual((p["retire"], p["held"]), ([], []))


if __name__ == "__main__":
    unittest.main()
