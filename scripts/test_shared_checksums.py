"""Shared files must match SHARED_SHA256SUMS.txt so the Spanish site can copy them."""
from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SharedChecksums(unittest.TestCase):
    def test_listed_files_match(self):
        lines = (ROOT / "SHARED_SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            digest, name = line.split(None, 1)
            path = ROOT / name
            got = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(got, digest, name)


if __name__ == "__main__":
    unittest.main()
