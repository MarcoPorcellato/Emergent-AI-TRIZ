from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.lab04_runner import run_lab04_bundle


class Lab04RunnerTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def _write_json(self, path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")

    def test_bundle_uses_current_fixture_and_is_byte_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out1 = Path(directory) / "out1"
            out2 = Path(directory) / "out2"
            result1 = run_lab04_bundle(
                cases_path=self.ROOT / "data/pilot/cases.jsonl",
                representations_path=self.ROOT / "data/pilot/representations.jsonl",
                config_path=self.ROOT / "experiments/lab04-decodability/config.json",
                predecessor_lab01_summary=self.ROOT / "results/lab01/model-anatomy/parity_report.json",
                predecessor_lab02_summary=self.ROOT / "results/lab02/dataset-anatomy/summary.json",
                predecessor_lab03_summary=self.ROOT / "results/lab03/behavioral-baselines/summary.json",
                output_dir=out1,
            )
            result2 = run_lab04_bundle(
                cases_path=self.ROOT / "data/pilot/cases.jsonl",
                representations_path=self.ROOT / "data/pilot/representations.jsonl",
                config_path=self.ROOT / "experiments/lab04-decodability/config.json",
                predecessor_lab01_summary=self.ROOT / "results/lab01/model-anatomy/parity_report.json",
                predecessor_lab02_summary=self.ROOT / "results/lab02/dataset-anatomy/summary.json",
                predecessor_lab03_summary=self.ROOT / "results/lab03/behavioral-baselines/summary.json",
                output_dir=out2,
            )

            self.assertEqual(result1["status"], "fail")
            self.assertEqual(result1["status"], result2["status"])
            self.assertEqual(result1["empirical"], result2["empirical"])
            self.assertEqual(result1["evidence_eligible"], result2["evidence_eligible"])
            for rel in ("probe_result.json", "report.html", "summary.json"):
                self.assertEqual((out1 / rel).read_bytes(), (out2 / rel).read_bytes())
            summary = json.loads((out1 / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["empirical"], False)
            self.assertEqual(summary["evidence_eligible"], False)
            self.assertEqual(summary["claim_ids"], [])
            self.assertIn("correlational, not causal", summary["non_claim_boundary"])
            gates = {item["gate"]: item["status"] for item in summary["gates"]}
            self.assertEqual(gates["P2"], "pass")
            self.assertEqual(gates["P8"], "pass")
            self.assertTrue(all(gates[name] == "fail" for name in ("P1", "P3", "P4", "P5", "P6", "P7")))


if __name__ == "__main__":
    unittest.main()
