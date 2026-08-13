from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.lab03_runner import run_lab03_bundle


class Lab03RunnerTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_current_fixture_is_observable_not_ready_and_portable(self) -> None:
        outputs = []
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            for directory in (first_dir, second_dir):
                result = run_lab03_bundle(
                    cases_path=self.ROOT / "data/pilot/cases.jsonl",
                    snapshot_path=self.ROOT / "results/lab02/dataset-anatomy/snapshot_manifest.json",
                    config_path=self.ROOT / "experiments/lab03-behavioral-baselines/config.json",
                    output_dir=directory,
                )
                self.assertEqual(result["status"], "fail")
                self.assertFalse(result["empirical"])
                self.assertFalse(result["evidence_eligible"])
                self.assertEqual(result["claim_ids"], [])
                payloads = {
                    name: (Path(directory) / name).read_bytes()
                    for name in ("baseline_result.json", "report.html", "summary.json")
                }
                for content in payloads.values():
                    self.assertNotIn(b"/private/tmp", content)
                    self.assertNotIn(b"/Users/", content)
                summary = json.loads(payloads["summary.json"])
                self.assertEqual(summary["interpretation"], "diagnostic_only_not_scientifically_interpretable")
                outputs.append(payloads)
        self.assertEqual(outputs[0], outputs[1])


if __name__ == "__main__":
    unittest.main()
