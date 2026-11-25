"""Fail the build when buyer-facing copy states a term, a rate, taxes, or insurance.

homes.js is the master listing file. The generator is what buyers read, so this
scan covers HTML, site scripts, and JSON other than homes.js.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALLOW = (
    "legal, tax, or financial advice",
    "asesoria legal, fiscal o financiera",
    "asesoría legal, fiscal o financiera",
    "What your monthly payment includes is confirmed in your paperwork.",
    "Lo que incluye su pago mensual se confirma en sus documentos.",
)

BANNED = re.compile(
    r"30[- ]years?|30 años|treinta años|fixed (?:price|rate|payment|monthly)|precio fijo|"
    r"no prepayment|tasa de inter[eé]s|interest rate|\binter[eé]s\b|property tax|\bimpuestos?\b|"
    r"\binsurance\b|seguro de casa|seguro del hogar|\bincome\b|\bingresos?\b|tax return|"
    r"declaraci[oó]n de impuestos|limited number|n[uú]mero limitado|worth more|vale más|"
    r"walked away|\btaxes\b|\bescrow\b",
    re.IGNORECASE,
)

SKIP = {"homes.js", "features.json", "zip-centroids.json"}


def _visible(text: str) -> str:
    for phrase in ALLOW:
        text = text.replace(phrase, "")
    return text


class BannedCopy(unittest.TestCase):
    def test_buyer_pages_do_not_claim_terms_taxes_or_insurance(self):
        hits = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".html", ".js", ".json"}:
                continue
            if path.name in SKIP or path.name.startswith("test_") or "node_modules" in path.parts or "__pycache__" in path.parts:
                continue
            if path.parts[:1] == ("images",):
                continue
            text = _visible(path.read_text(encoding="utf-8", errors="ignore"))
            found = BANNED.search(text)
            if found:
                hits.append(f"{path.relative_to(ROOT)}: {found.group(0)}")
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
