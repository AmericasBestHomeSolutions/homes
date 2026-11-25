"""A placeholder is not visible HTML unless the page is opened with ?preview=1.

    python3 scripts/test_placeholders.py
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def visible_placeholder(html: str) -> list[str]:
    """Placeholder sentences that are not inside a hidden joe-slot."""
    found = []
    for match in re.finditer(r"Placeholder: [^<]+", html):
        start = html.rfind("<", 0, match.start())
        window = html[max(0, match.start() - 400):match.start()]
        if 'class="joe-slot' not in window and "joe-slot" not in window:
            found.append(match.group(0))
            continue
        tag = html.rfind("<p", 0, match.start())
        art = html.rfind("<article", 0, match.start())
        sec = html.rfind("<section", 0, match.start())
        opener = max(tag, art, sec)
        element = html[opener:match.start()] if opener >= 0 else ""
        if "joe-slot" in element and "hidden" not in element.split(">", 1)[0]:
            found.append(match.group(0))
    return found


class Placeholders(unittest.TestCase):
    def test_templates_hide_placeholders(self):
        for name in ("index.html", "home.html", "about.html", "how-it-works.html"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertEqual(visible_placeholder(text), [], name)
            if "Placeholder:" in text:
                self.assertIn("preview=1", text, name)
                self.assertIn("joe-slot", text, name)

    def test_only_logans_published_story(self):
        reviews = json.loads((ROOT / "reviews.json").read_text(encoding="utf-8"))
        buyers = [row for row in reviews if row.get("kind") != "owner"]
        self.assertEqual([row.get("name") for row in buyers], ["Logan, Decatur"])
        self.assertFalse((ROOT / "data" / "stories.json").exists())


if __name__ == "__main__":
    unittest.main()
