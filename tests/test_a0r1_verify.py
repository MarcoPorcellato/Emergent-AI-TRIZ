from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0r1_verify import A0R1VerifyError, _require_equal, verify_a0r1_foundation


class A0R1VerifyTests(unittest.TestCase):
    def test_tracked_foundation_reproduces_byte_for_byte(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = verify_a0r1_foundation(root)
        self.assertEqual("pass", result["status"])
        self.assertFalse(result["model_output_accessed"])
        self.assertEqual(4, result["corpus_files_verified"])
        self.assertEqual(4, result["preoutput_files_verified"])

    def test_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "expected"
            actual = root / "actual"
            expected.mkdir()
            actual.mkdir()
            (expected / "artifact.json").write_text("expected", encoding="utf-8")
            (actual / "artifact.json").write_text("changed", encoding="utf-8")
            with self.assertRaises(A0R1VerifyError):
                _require_equal(expected, actual, ("artifact.json",))
