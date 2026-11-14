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
        ids, site = many(16)
        p = plan(feed(*[(i, "Sold") for i in ids]), portal=rows(ids), site=site)
        self.assertEqual(p["retire"], [])
        self.assertTrue(p["status_feed"]["refused"])
        self.assertTrue(any("STATUS FEED REFUSED" in h for h in p["hand"]))
        p = plan(feed(*[(i, "Sold") for i in ids[:15]]), portal=rows(ids), site=site)
        self.assertEqual(len(p["retire"]), 15)

    def test_no_double_count_with_crm_wins(self):
        p = plan(feed((K, "Sold")), crm=[{"Unique ID": K, "Property Status": "Sold"}])
        self.assertEqual([r["id"] for r in p["retire"]], [K])
        self.assertEqual(len(p["held"]), 1)

    def test_direct_rows_never_closed(self):
        p = plan(feed((K, "Sold")), portal=[prow("2207 K St", "Barling", "AR", prop="DIRECT")])
        self.assertEqual((p["retire"], p["held"]), ([], []))


def many(n, prefix="town-il-"):
    ids = [f"{prefix}{i}-a" for i in range(n)]
    site = "const HOMES = [\n" + "".join(
        f'  {{\n    id: "{i}",\n    address:     "{k} A St",\n    city:  "Town",\n    state: "IL",\n    status: "Available",\n    photos:    ["a.jpg"],\n  }},\n'
        for k, i in enumerate(ids)) + "];\nconst SOLD_CARDS = [];\n"
    return ids, site


def rows(ids, status="Available"):
    return [prow(f"{k} A St", "Town", "IL", status=status, prop=f"P-{k}") for k, _ in enumerate(ids)]


class Hardening(unittest.TestCase):
    def test_run_two_does_not_readd_a_feed_closed_home(self):
        site_after_run1 = HOMES_JS.replace('id: "barling-ar-2207-k"', 'id: "x"').replace("2207 K St", "9 Other St")   # K is gone from the site now
        p = plan(feed((K, "Sold")), site=site_after_run1)
        self.assertEqual((p["add"], p["retire"], p["relist"]), ([], [], []))
        self.assertTrue(any("status feed" in h for h in p["held"]))
        self.assertEqual(p.get("cards_dropped"), None)

    def test_feed_available_lets_a_portal_home_be_added(self):
        site = HOMES_JS.replace('id: "barling-ar-2207-k"', 'id: "x"').replace("2207 K St", "9 Other St")
        p = plan(feed((K, "Available")), site=site)
        self.assertEqual([a["id"] for a in p["add"]], [K])

    def test_direct_feed_down_protects_direct_home(self):
        # direct feed unreadable -> no DIRECT row this run -> the site home is not in the portal rows
        p = plan(feed((K, "Sold")), portal=[prow("100 Main St", "Peoria", "IL", prop="PROP-2")])
        self.assertEqual((p["retire"], p["held"]), ([], []))

    def test_total_retires_capped_by_max_retire(self):
        ids, site = many(27)
        portal = rows(ids[:12], "Sold") + rows(ids, "Available")[12:]
        p = plan(feed(*[(i, "Sold") for i in ids[12:]]), portal=portal, site=site)
        self.assertEqual(len(p["retire"]), 12)   # portal retires still run
        self.assertTrue(p["status_feed"]["refused"])
        ids, site = many(25)
        portal = rows(ids[:12], "Sold") + rows(ids, "Available")[12:]
        p = plan(feed(*[(i, "Sold") for i in ids[12:]]), portal=portal, site=site)
        self.assertEqual(len(p["retire"]), 25)
        self.assertFalse(p["status_feed"]["refused"])

    def test_as_of_age(self):
        from datetime import datetime, timezone
        now = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)
        h = [{"id": K, "status": "Sold"}]
        self.assertEqual(ps.read_status_feed(data={"homes": h, "as_of": "2026-11-14T06:00:00Z"}, now=now), {K: "Sold"})
        self.assertIsNone(ps.read_status_feed(data={"homes": h, "as_of": "2026-11-12T11:00:00Z"}, now=now))
        self.assertIsNone(ps.read_status_feed(data={"homes": h, "as_of": "yesterday"}, now=now))
        self.assertEqual(ps.read_status_feed(data={"homes": h}, now=now), {K: "Sold"})

    def test_duplicate_ids(self):
        f = ps.read_status_feed(data={"homes": [{"id": K, "status": "Sold"}, {"id": K, "status": "Available"},
                                                {"id": M, "status": "Sold"}, {"id": M, "status": "sold"}]})
        self.assertEqual(f, {M: "Sold"})
        self.assertIsNone(ps.read_status_feed(data={"homes": [{"id": K, "status": "Sold"}, {"id": K, "status": "Pending"}]}))

    def test_portal_pending_and_feed_pending_not_double_handled(self):
        p = plan(feed((K, "Pending")), portal=[prow("2207 K St", "Barling", "AR", status="Pending")])
        self.assertEqual(p["retire"], [])
        self.assertEqual([x["id"] for x in p["pending"]], [K])
        p = plan(feed((K, "Sold")), portal=[prow("2207 K St", "Barling", "AR", status="Pending")])
        self.assertEqual([r["id"] for r in p["retire"]], [K])

    def test_spanish_run(self):
        import io
        import json
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / "homes.js").write_text(HOMES_JS, encoding="utf-8")
            filler = [prow(f"{n} Z St", "Zed", "IL", prop=f"F-{n}") for n in range(120)]
            (t / "portal.json").write_text(json.dumps(PORTAL + filler))
            (t / "crm.json").write_text("[]")
            (t / "status.json").write_text(json.dumps({"homes": [{"id": K, "status": "Sold"}]}))
            (t / "direct.json").write_text(json.dumps({"homes": []}))
            out = t / "summary.txt"
            with redirect_stdout(io.StringIO()):
                rc = ps.main(["--site", str(t), "--lang", "es", "--dry-run", "--portal-json", str(t / "portal.json"),
                              "--crm-json", str(t / "crm.json"), "--status-json", str(t / "status.json"),
                              "--direct-json", str(t / "direct.json"), "--summary-out", str(out)])
            self.assertEqual(rc, 0)
            text = out.read_text()
            self.assertIn(f"- {K}  sold", text)
            self.assertIn("Status feed: 1 homes read, 1 closed on the site", text)


if __name__ == "__main__":
    unittest.main()
