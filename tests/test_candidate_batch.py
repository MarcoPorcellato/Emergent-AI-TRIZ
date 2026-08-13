from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from latent_triz.candidate_batch import audit_candidate_batch


class CandidateBatchTests(unittest.TestCase):
    def _case(self, case_id: str, domain: str, principle: str, pair: str) -> dict:
        return {
            "case_id": case_id,
            "domain": domain,
            "problem": "A process misses its target under load.",
            "constraints": ["low cost", "short downtime"],
            "initial_state": "One workflow handles the full load.",
            "desired_improvement": "Meet the target without more downtime.",
            "worsening_consequence": "Errors grow as load increases.",
            "transformation": "Reconfigure independently managed work units." if domain == "alpha" else "Modify the operating sequence.",
            "resulting_state": "The process meets its target under load.",
            "labels": [{"principle": principle, "annotator_id": "draft", "confidence": 0.3}],
            "lexical_controls": {"forbidden_terms": ["TRIZ"], "matched_case_ids": [pair]},
            "near_miss_case_ids": [pair],
            "alternative_solution_case_ids": [],
            "split": "discovery",
            "provenance": {
                "source_type": "model_generated", "source_uri": f"urn:test:{case_id}",
                "license": "Apache-2.0", "created_at": "2026-08-13",
            },
        }

    def _audit(self, mutate=None) -> dict:
        cases = [
            self._case("a1", "alpha", "segmentation", "a2"),
            self._case("a2", "alpha", "inversion", "a1"),
            self._case("b1", "beta", "segmentation", "b2"),
            self._case("b2", "beta", "inversion", "b1"),
        ]
        if mutate is not None:
            mutate(cases)
        manifest = {
            "batch_id": "test", "status": "draft", "non_empirical": True,
            "evidence_eligible": False, "expected_count": 4,
            "required_principles": ["segmentation", "inversion"],
            "required_domains": ["alpha", "beta"], "minimum_per_principle_domain": 1,
            "allowed_source_types": ["model_generated"],
            "forbidden_label_cues": ["split", "invert"],
            "require_opposite_label_pairs": True,
            "require_balanced_transformation_leads": True,
            "minimum_distinct_transformation_leads": 2,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path, cases_path = root / "manifest.json", root / "cases.jsonl"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            cases_path.write_text("\n".join(json.dumps(case) for case in cases) + "\n", encoding="utf-8")
            return audit_candidate_batch(manifest_path, cases_path)

    def test_balanced_opposite_pairs_pass(self) -> None:
        report = self._audit()
        self.assertEqual("pass", report["status"])
        self.assertTrue(report["ready_for_blinded_review"])
        self.assertFalse(report["evidence_eligible"])

    def test_label_cue_leakage_fails_closed(self) -> None:
        report = self._audit(lambda cases: cases[0].update(transformation="Split the workload."))
        self.assertFalse(report["ready_for_blinded_review"])
        self.assertIn("label_cue_leakage", {issue["code"] for issue in report["issues"]})

    def test_asymmetric_pair_fails_closed(self) -> None:
        def mutate(cases: list[dict]) -> None:
            cases[1]["lexical_controls"]["matched_case_ids"] = ["b1"]

        report = self._audit(mutate)
        self.assertFalse(report["ready_for_blinded_review"])
        self.assertIn("asymmetric_pair", {issue["code"] for issue in report["issues"]})

    def test_lead_word_template_imbalance_fails_closed(self) -> None:
        report = self._audit(lambda cases: cases[0].update(transformation="Arrange independent work units."))
        self.assertFalse(report["ready_for_blinded_review"])
        self.assertIn("transformation_lead_imbalance", {issue["code"] for issue in report["issues"]})


if __name__ == "__main__":
    unittest.main()
