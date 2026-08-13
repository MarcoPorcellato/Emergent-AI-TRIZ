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
                "source_type": "model_generated",
                "source_uri": f"urn:test:{case_id}",
                "license": "Apache-2.0",
                "created_at": "2026-08-13",
            },
        }

    def _audit(
        self,
        cases_mutator: callable | None = None,
        manifest_mutator: callable | None = None,
    ) -> dict:
        cases = [
            self._case("a1", "alpha", "segmentation", "a2"),
            self._case("a2", "alpha", "inversion", "a1"),
            self._case("b1", "beta", "segmentation", "b2"),
            self._case("b2", "beta", "inversion", "b1"),
        ]
        if cases_mutator is not None:
            cases_mutator(cases)

        manifest = {
            "batch_id": "test",
            "status": "draft",
            "non_empirical": True,
            "evidence_eligible": False,
            "expected_count": 4,
            "required_principles": ["segmentation", "inversion"],
            "required_domains": ["alpha", "beta"],
            "minimum_per_principle_domain": 1,
            "allowed_source_types": ["model_generated"],
            "forbidden_label_cues": ["split", "invert"],
            "require_opposite_label_pairs": True,
            "require_balanced_transformation_leads": True,
            "minimum_distinct_transformation_leads": 2,
        }
        if manifest_mutator is not None:
            manifest_mutator(manifest)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            cases_path = root / "cases.jsonl"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            cases_path.write_text("\n".join(json.dumps(case) for case in cases) + "\n", encoding="utf-8")
            return audit_candidate_batch(manifest_path, cases_path)

    def test_balanced_opposite_pairs_pass(self) -> None:
        report = self._audit()
        self.assertEqual("pass", report["status"])
        self.assertTrue(report["ready_for_blinded_review"])
        self.assertFalse(report["evidence_eligible"])

    def test_current_wave1_style_manifest_is_blinded_ready_not_freeze_ready(self) -> None:
        def with_semantic_policy(manifest: dict) -> None:
            manifest["semantic_leakage_policy"] = {
                "pair_similarity_threshold": 0.72,
                "lodo_similarity_threshold": 0.64,
                "word_ngrams": [2, 3],
                "char_ngrams": [3, 5],
                "require_pair_semantic_review": True,
                "freeze_only_with_pair_review": True,
            }
            manifest["pair_semantic_review"] = []

        report = self._audit(manifest_mutator=with_semantic_policy)
        self.assertTrue(report["ready_for_blinded_review"])
        self.assertFalse(report["ready_for_freeze"])
        self.assertTrue(report["semantic_leakage"]["enabled"])

    def test_label_cue_leakage_fails_closed(self) -> None:
        report = self._audit(lambda cases: cases[0].update(transformation="Split the workload."))
        self.assertFalse(report["ready_for_blinded_review"])
        self.assertIn("label_cue_leakage", {issue["code"] for issue in report["issues"]})

    def test_asymmetric_pair_fails_closed(self) -> None:
        def mutate(cases: list[dict]) -> None:
            cases[1]["lexical_controls"]["matched_case_ids"] = ["b1"]

        report = self._audit(cases_mutator=mutate)
        self.assertFalse(report["ready_for_blinded_review"])
        self.assertIn("asymmetric_pair", {issue["code"] for issue in report["issues"]})

    def test_lead_word_template_imbalance_fails_closed(self) -> None:
        report = self._audit(lambda cases: cases[0].update(transformation="Arrange independent work units."))
        self.assertFalse(report["ready_for_blinded_review"])
        self.assertIn("transformation_lead_imbalance", {issue["code"] for issue in report["issues"]})

    def test_semantic_pair_similarity_records_diagnostics(self) -> None:
        def with_semantic_policy(manifest: dict) -> None:
            manifest["semantic_leakage_policy"] = {
                "pair_similarity_threshold": 0.0,
                "lodo_similarity_threshold": 0.0,
                "word_ngrams": [2],
                "char_ngrams": [3],
                "require_pair_semantic_review": False,
            }

        report = self._audit(manifest_mutator=with_semantic_policy)
        self.assertTrue(report["semantic_leakage"]["enabled"])
        self.assertEqual(
            report["semantic_leakage"]["embedding_backend"]["status"],
            "not_run",
        )
        diagnostics = report["semantic_leakage"]["pair_diagnostics"]
        self.assertGreaterEqual(len(diagnostics), 2)
        field_names = {field for d in diagnostics for field in d.get("field_similarities", {})}
        for field_name in ("problem", "transformation", "resulting_state", "problem_plus_solution"):
            self.assertIn(field_name, field_names)
        lodo = report["semantic_leakage"]["lodo"]
        self.assertGreaterEqual(lodo["pairs_evaluated"], 0)

    def test_missing_pair_review_blocks_freeze(self) -> None:
        def with_semantic_policy(manifest: dict) -> None:
            manifest["semantic_leakage_policy"] = {
                "pair_similarity_threshold": 0.99,
                "lodo_similarity_threshold": 0.99,
                "word_ngrams": [2],
                "char_ngrams": [3],
                "require_pair_semantic_review": True,
            }
            manifest["pair_semantic_review"] = []

        report = self._audit(manifest_mutator=with_semantic_policy)
        self.assertTrue(report["ready_for_blinded_review"])
        self.assertFalse(report["ready_for_freeze"])
        issues = {issue["code"] for issue in report["semantic_leakage"]["issues"]}
        self.assertIn("missing_semantic_pair_review", issues)

    def test_reviewed_pairs_enable_freeze(self) -> None:
        def with_semantic_policy_and_review(manifest: dict) -> None:
            manifest["semantic_leakage_policy"] = {
                "pair_similarity_threshold": 0.0,
                "lodo_similarity_threshold": 0.0,
                "word_ngrams": [2],
                "char_ngrams": [3],
                "require_pair_semantic_review": True,
            }
            checks = {name: True for name in (
                "same_problem", "same_constraints", "same_desired_improvement",
                "same_worsening_consequence", "comparable_length", "comparable_syntax",
                "comparable_feasibility", "only_dominant_operator_differs",
            )}
            manifest["pair_semantic_review"] = [
                {"pair_id": pair_id, "status": "reviewed", "reviewer_id": "r1", "reviewed_at": "2026-08-13", "pair_class": "minimal_pair", "checks": checks, "rationale": "Only the dominant operator differs."}
                for pair_id in ("a1|a2", "b1|b2")
            ]

        report = self._audit(manifest_mutator=with_semantic_policy_and_review)
        self.assertTrue(report["ready_for_blinded_review"])
        self.assertTrue(report["ready_for_freeze"])

    def test_review_status_without_matched_pair_rubric_fails_closed(self) -> None:
        def with_inadequate_review(manifest: dict) -> None:
            manifest["semantic_leakage_policy"] = {
                "pair_similarity_threshold": 0.0,
                "lodo_similarity_threshold": 0.0,
                "word_ngrams": [2],
                "char_ngrams": [3],
                "require_pair_semantic_review": True,
            }
            manifest["pair_semantic_review"] = [
                {"pair_id": "a1|a2", "status": "reviewed", "reviewer_id": "r1", "reviewed_at": "2026-08-13", "pair_class": "closely_matched_pair", "checks": {name: name != "same_problem" for name in (
                    "same_problem", "same_constraints", "same_desired_improvement",
                    "same_worsening_consequence", "comparable_length", "comparable_syntax",
                    "comparable_feasibility", "only_dominant_operator_differs",
                )}, "rationale": "The underlying problems are not the same."},
            ]

        report = self._audit(manifest_mutator=with_inadequate_review)
        self.assertFalse(report["ready_for_freeze"])
        codes = {item["code"] for item in report["semantic_leakage"]["issues"]}
        self.assertIn("pair_review_rubric_failed", codes)

    def test_tracked_wave1_is_reviewable_but_shortcut_and_pair_gates_block_freeze(self) -> None:
        root = Path(__file__).resolve().parents[1]
        report = audit_candidate_batch(
            root / "data/candidates/wave1-manifest.json",
            root / "data/candidates/wave1-model-generated.jsonl",
        )
        self.assertTrue(report["ready_for_blinded_review"])
        self.assertFalse(report["ready_for_freeze"])
        evaluability = report["semantic_leakage"]["shortcut_evaluability"]
        self.assertTrue(evaluability["domain"]["evaluable"])
        self.assertFalse(evaluability["source"]["evaluable"])
        self.assertFalse(evaluability["template"]["evaluable"])
        codes = {issue["code"] for issue in report["semantic_leakage"]["issues"]}
        self.assertIn("missing_semantic_pair_review", codes)
        self.assertIn("source_shortcut_not_evaluable", codes)
        self.assertIn("template_shortcut_not_evaluable", codes)


if __name__ == "__main__":
    unittest.main()
