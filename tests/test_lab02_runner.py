from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.lab02_runner import run_lab02_bundle


class Lab02RunnerTests(unittest.TestCase):
    def test_runner_preserves_not_ready_as_observable_result(self) -> None:
        audit = {"status": "pass_with_gaps", "counts": {"by_split": {}}, "target_gaps": [{}], "issues": []}
        snapshot = {
            "artifact_class": "dataset-instrumentation",
            "empirical": False,
            "evidence_eligible": False,
            "claim_ids": [],
            "status": "fail",
            "counts": {"total_cases": 0, "by_split": {}, "by_domain": {}, "by_principle": {}},
            "artifacts": {},
            "split_membership_digest": "sha256:" + "0" * 64,
            "rater_coverage": {"minimum_distinct_raters": 2, "response_counts": {}, "distinct_raters": []},
            "agreement": {"metric": "exact_percent_agreement", "threshold": 0.8, "overall": 0.0, "minimum_met": False, "per_case": {}},
            "issues": [],
        }
        with tempfile.TemporaryDirectory() as workdir, patch(
            "latent_triz.lab02_runner.run_dataset_audit", return_value=audit
        ), patch(
            "latent_triz.lab02_runner.build_dataset_snapshot_manifest", return_value=snapshot
        ):
            result = run_lab02_bundle(
                plan_path="plan.json",
                cases_path="cases.jsonl",
                annotations_path="annotations.jsonl",
                registry_entry_path="entry.json",
                registry_manifest_path="registry.json",
                output_dir=workdir,
            )
            self.assertFalse(result["dataset_ready"])
            self.assertTrue(Path(result["report"]).is_file())
            summary = json.loads(Path(result["summary"]).read_text(encoding="utf-8"))
            self.assertFalse(summary["evidence_eligible"])
            self.assertEqual(summary["claim_ids"], [])


if __name__ == "__main__":
    unittest.main()
