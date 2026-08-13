from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.blinding import BlindingError, build_evaluator_bundle, write_evaluator_bundle


class BlindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]

    def test_bundle_withholds_allocation_from_evaluator_packets(self) -> None:
        evaluator, key = build_evaluator_bundle(
            self.root / "data/pilot/packets.jsonl",
            self.root / "data/pilot/responses.jsonl",
        )
        evaluator_text = json.dumps(evaluator, sort_keys=True)
        self.assertNotIn("arms_by_blind", evaluator_text)
        self.assertNotIn('"control"', evaluator_text)
        self.assertNotIn('"treatment"', evaluator_text)
        self.assertEqual(key["status"], "sealed")
        self.assertEqual(len(evaluator), 2)
        self.assertEqual(len(key["allocations"]), 2)

    def test_outputs_must_be_separate(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            target = Path(workdir) / "bundle.json"
            with self.assertRaises(BlindingError):
                write_evaluator_bundle([], {}, target, target)

    def test_smoke_inputs_require_non_empirical_packets(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            packet = Path(workdir) / "packets.jsonl"
            response = Path(workdir) / "responses.jsonl"
            packet.write_text(
                json.dumps(
                    {
                        "packet_id": "p1",
                        "case_id": "c1",
                        "pair_id": "c1",
                        "blind_order": ["A", "B"],
                        "arms_by_blind": {"A": "control", "B": "treatment"},
                        "source": {"case_id": "c1"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            response.write_text("", encoding="utf-8")
            with self.assertRaises(BlindingError):
                build_evaluator_bundle(packet, response)


if __name__ == "__main__":
    unittest.main()
