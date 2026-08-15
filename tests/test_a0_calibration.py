from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0_calibration import A0CalibrationError, run_a0_calibration
from latent_triz.a0_corpus import generate_a0_corpus


class A0CalibrationTests(unittest.TestCase):
    protocol = Path(__file__).resolve().parents[1] / "experiments/a0-automated-weak-proxy/protocol.json"

    def test_real_calibration_passes_without_sealed_target_access(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus"
            output = root / "calibration"
            generate_a0_corpus(self.protocol, corpus)
            summary = run_a0_calibration(self.protocol, corpus, output)
            self.assertEqual(summary["status"], "pass")
            self.assertFalse(summary["sealed_targets_accessed"])
            freeze = json.loads((output / "freeze-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(freeze["status"], "frozen")
            self.assertFalse(freeze["sealed_targets_accessed"])
            self.assertTrue(freeze["sealed_targets_sha256"])

    def test_tampered_calibration_targets_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus"
            generate_a0_corpus(self.protocol, corpus)
            target = corpus / "procedural-targets" / "calibration-targets.jsonl"
            target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaises(A0CalibrationError):
                run_a0_calibration(self.protocol, corpus, root / "calibration")


if __name__ == "__main__":
    unittest.main()
