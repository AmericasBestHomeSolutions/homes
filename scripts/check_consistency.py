#!/usr/bin/env python3
"""Fail when the English and Spanish sites disagree on price, down, monthly, status, or facts.

    python3 scripts/check_consistency.py --casas /path/to/casas

Reads homes.js on both sites. Compares lockedPrice, moveIn, monthlyPayment, and status
for every id that is on both. Also compares data/home-facts.json byte for byte.
Prices are never copied by this script. It only reports differences.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

KEYS = ("lockedPrice", "moveIn", "monthlyPayment", "status")


def catalog(root: Path) -> dict[str, dict]:
    text = (root / "homes.js").read_text(encoding="utf-8").split("const SOLD_CARDS")[0]
    homes = {}
    for match in re.finditer(r'\n  \{\n    id: "([^"]+)",[\s\S]*?\n  \},', text):
        block, hid = match.group(0), match.group(1)
        row = {}
        for key in KEYS:
            found = re.search(rf'\n    {key}:\s*("(?:\\.|[^"\\])*"|[^,\n]*),', block)
            row[key] = found.group(1).strip().strip('"') if found else ""
        homes[hid] = row
    return homes


def compare(homes_root: Path, casas_root: Path) -> list[str]:
    errors = []
    en, es = catalog(homes_root), catalog(casas_root)
    for hid in sorted(set(en) & set(es)):
        for key in KEYS:
            if en[hid][key] != es[hid][key]:
                errors.append(f"{hid} {key}: en={en[hid][key]!r} es={es[hid][key]!r}")
    facts_en = homes_root / "data" / "home-facts.json"
    facts_es = casas_root / "data" / "home-facts.json"
    if facts_en.read_bytes() != facts_es.read_bytes():
        errors.append("data/home-facts.json differs between homes and casas")
    return errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--homes", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--casas", type=Path, required=True)
    args = ap.parse_args(argv)
    errors = compare(args.homes, args.casas)
    if errors:
        print("\n".join(errors))
        return 1
    print("English and Spanish price, down, monthly, status, and home-facts match.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
