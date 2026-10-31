"""Checks for the buyer-copy sanitizer in refresh_listings.py.

Run from the repo root:  python3 scripts/test_copy_sanitizer.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import refresh_listings as refresh

ROOT = Path(__file__).resolve().parents[1]


class SanitizerTests(unittest.TestCase):
    def test_keeps_the_sentences_around_the_invitation(self):
        src = (
            "Homes at this payment don't stay available for long. "
            "Send us a text or a message now and let's get you on the showing schedule."
        )
        got, n = refresh.sanitize_prose(src)
        self.assertEqual(n, 1)
        self.assertEqual(
            got,
            "Homes at this payment don't stay available for long. "
            "Book a Tour now and let's get you on the showing schedule.",
        )

    def test_mid_sentence_invitation_keeps_the_clause(self):
        src = "Homes at this price don't wait around, so send us a text now and let's get you on the schedule."
        got, n = refresh.sanitize_prose(src)
        self.assertEqual(n, 1)
        self.assertEqual(
            got,
            "Homes at this price don't wait around, so book a Tour now and let's get you on the schedule.",
        )

    def test_while_available_and_message_us(self):
        a, n = refresh.sanitize_prose(
            "Send us a text while this one is still available, and we'll find you a time to come by."
        )
        self.assertEqual(n, 1)
        self.assertEqual(
            a,
            "Book a Tour while this one is still available, and we'll find you a time to come by.",
        )
        b, n = refresh.sanitize_prose("Homes like this don't sit long, so message us now to get on the showing list.")
        self.assertEqual(n, 1)
        self.assertIn("so book a Tour now to get on the showing list.", b)

    def test_reach_out_and_text_or_message_us(self):
        got, n = refresh.sanitize_prose(
            "Reach out by text or message now to grab a showing time while this one is still available."
        )
        self.assertEqual(n, 1)
        self.assertEqual(
            got,
            "Book a Tour now to grab a showing time while this one is still available.",
        )
        got, n = refresh.sanitize_prose("Text or message us now to set up your showing.")
        self.assertEqual(got, "Book a Tour now to set up your showing.")
        self.assertEqual(n, 1)

    def test_email_call_text_me(self):
        got, n = refresh.sanitize_prose(
            "Let me know if you have any question, email/call/text me."
        )
        self.assertEqual(n, 1)
        self.assertEqual(
            got,
            "Let me know if you have any question, book a Tour.",
        )

    def test_does_not_touch_ordinary_call_wording(self):
        src = "Come walk through every room in person and make your own call. A place to call their own."
        got, n = refresh.sanitize_prose(src)
        self.assertEqual(n, 0)
        self.assertEqual(got, src)

    def test_homes_js_fields_only(self):
        src = (
            'copy:        "Send us a text now and grab a showing time.",\n'
            '    description: "The wires are gone. Call us.",\n'
            '    termText:       "30-year owner financing",\n'
        )
        got, fields, phrases = refresh.sanitize_homes_js(src)
        self.assertEqual(fields, 2)
        self.assertEqual(phrases, 2)
        self.assertIn('Book a Tour now and grab a showing time.', got)
        self.assertIn('The wires are gone. Book a Tour.', got)
        self.assertIn('30-year owner financing', got)

    def test_meta_descriptions(self):
        html = (
            '<meta name="description" content="Send us a text now."/>'
            '<meta property="og:description" content="Price only. No invitation."/>'
            '<meta name="twitter:description" content="Call or text us today."/>'
            '<p>Send us a text now.</p>'
        )
        got, n = refresh.sanitize_meta_html(html)
        self.assertEqual(n, 2)
        self.assertIn('content="Book a Tour now."', got)
        self.assertIn('content="Book a Tour today."', got)
        self.assertIn("<p>Send us a text now.</p>", got)


class InclusiveCopyTests(unittest.TestCase):
    def test_family_and_kid_phrases_become_what_the_home_offers(self):
        cases = {
            "Fully fenced yard, perfect for pets, kids, or simply relaxing in privacy.":
                "Fully fenced yard, perfect for pets, gardening, or simply relaxing in privacy.",
            "A functional layout perfect for a small family or savvy investor":
                "A functional layout perfect for a first-time owner or savvy investor",
            "Next to the library. Perfect for families!": "Next to the library. Room to spread out!",
            "Bonus room (perfect for office, kids, or flex space).":
                "Bonus room (perfect for an office, hobbies, or flex space).",
            "Separately fenced area for dogs and rest of family.": "Separately fenced area for pets.",
            "This longtime family home has been well loved.": "This longtime home has been well loved.",
            "Great for families. Big yard.": "Great for anyone who wants room to spread out. Big yard.",
        }
        for src, want in cases.items():
            got, n = refresh.inclusive_prose(src)
            self.assertEqual(got, want)
            self.assertGreaterEqual(n, 1)
            self.assertEqual(refresh.family_words_left(got), [])

    def test_property_types_are_left_alone(self):
        src = "Brick single-family home with a family room. Multi-family zoning."
        self.assertEqual(refresh.inclusive_prose(src), (src, 0))
        self.assertEqual(refresh.family_words_left(src), [])

    def test_homes_js_fields_get_both_passes(self):
        src = 'description: "Perfect for families! Send us a text today."'
        got, fields, n = refresh.sanitize_homes_js(src)
        self.assertEqual(got, 'description: "Room to spread out! Book a Tour today."')
        self.assertEqual((fields, n), (1, 2))


if __name__ == "__main__":
    unittest.main()
