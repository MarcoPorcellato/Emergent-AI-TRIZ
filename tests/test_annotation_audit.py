from __future__ import annotations

import hashlib
import json
import tempfile
import math
import unittest
from pathlib import Path

from latent_triz.annotation_audit import AnnotationAuditError, audit_annotations
from latent_triz.validator import validate


ROOT = Path(__file__).resolve().parents[1]


def _case_hash(case: dict[str, object]) -> str:
    payload = json.dumps(
        {
            "case_id": case["case_id"],
            "domain": case["domain"],
            "problem": case["problem"],
            "constraints": case["constraints"],
            "initial_state": case["initial_state"],
            "desired_improvement": case["desired_improvement"],
            "worsening_consequence": case["worsening_consequence"],
            "transformation": case["transformation"],
            "resulting_state": case["resulting_state"],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AnnotationAuditTests(unittest.TestCase):
    def _write_jsonl(self, path: Path, records: list[dict]) -> None:
        path.write_text("\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n", encoding="utf-8")

    def _run(
        self, mutate=None, *, threshold: float = 0.8, max_abstention: float = 0.2,
        minimum_raters: int = 2, annotation_file_count: int = 2, case_count: int = 4
    ) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path, guide_path = root / "cases.jsonl", root / "guide.json"
            cases = [
                {
                    "case_id": f"case_{index:03d}",
                    "domain": "manufacturing",
                    "problem": "Problem statement",
                    "constraints": ["C1"],
                    "initial_state": "Start",
                    "desired_improvement": "Improve",
                    "worsening_consequence": "Worse",
                    "transformation": "Change",
                    "resulting_state": "End",
                    "labels": [],
                    "lexical_controls": [],
                    "near_miss_case_ids": [],
                    "alternative_solution_case_ids": [],
                    "provenance": [],
                    "split": "discovery",
                }
                for index in range(case_count)
            ]
            self._write_jsonl(cases_path, cases)
            case_hashes = {case["case_id"]: _case_hash(case) for case in cases}
            dataset_batch_sha256 = hashlib.sha256(
                json.dumps(
                    [case_hashes[case["case_id"]] for case in sorted(cases, key=lambda item: item["case_id"])],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            guide = {
                "revision": "v1.1.0",
                "labels": [
                    {"id": "segmentation", "name": "Segmentation", "definition": "..."},
                    {"id": "inversion", "name": "Inversion", "definition": "..."},
                    {"id": "both", "name": "Both", "definition": "..."},
                    {"id": "other", "name": "Other", "definition": "..."},
                ],
                "abstention": {
                    "id": "abstain",
                    "name": "Cannot determine",
                    "definition": "Use when the displayed case cannot support a reliable classification.",
                },
                "decision_rule": "...",
                "evidence_eligible": False,
                "agreement_policy": {
                    "minimum_distinct_raters": 2,
                    "raw_agreement_threshold": 0.8,
                    "nominal_alpha_threshold": 0.8,
                    "maximum_abstention_rate": 0.2,
                    "abstain_as_category": True,
                    "raw_agreement_metric": "pairwise_exact_percent_agreement",
                "ordinal_agreement_metric": "krippendorff_alpha_ordinal",
                "ordinal_gate": "descriptive_only",
                "confidence_interval_method": "case_bootstrap_percentile",
                "confidence_level": 0.95,
                "confidence_interval_resamples": 2000,
                "confidence_interval_seed": 1729,
                "confidence_interval_gate": "descriptive_only",
                "adjudication_rule": "Case-level unanimity on a substantive label required for freeze; disagreements and unanimous abstentions remain explicit for adjudication.",
                },
            }
            guide_path.write_text(json.dumps(guide, sort_keys=True), encoding="utf-8")
            guide_digest = hashlib.sha256(guide_path.read_bytes()).hexdigest()
            paths: list[Path] = []
            for rater in ("rater_1", "rater_2", "rater_3"):
                records = [
                    {
                        "annotation_id": f"{rater}_{case['case_id']}",
                        "case_id": case["case_id"],
                        "rater_id": rater,
                        "label": "segmentation",
                        "confidence": 0.8,
                        "rationale": "The selected transformation matches the definition.",
                        "non_empirical": False,
                        "annotated_at": "2026-08-13T00:00:00Z",
                        "guide_revision": "v1.1.0",
                        "guide_sha256": guide_digest,
                        "case_payload_sha256": case_hashes[case["case_id"]],
                        "dataset_batch_sha256": dataset_batch_sha256,
                        "display_view_version": "v1.1.0",
                        "session_id": "session-1",
                        "operator_presence": 2,
                        "operator_essentiality": 2,
                        "contradiction_resolution": 2,
                        "solution_feasibility": 2,
                    }
                    for case in cases
                ]
                path = root / f"{rater}.jsonl"
                self._write_jsonl(path, records)
                paths.append(path)
            if mutate is not None:
                mutate(paths, guide_digest, case_hashes, dataset_batch_sha256)
            return audit_annotations(
                cases_path=cases_path,
                guide_path=guide_path,
                annotation_schema_path=ROOT / "schemas/dataset-annotation.schema.json",
                annotation_paths=paths[:annotation_file_count],
                minimum_distinct_raters=minimum_raters,
                agreement_threshold=threshold,
                maximum_abstention_rate=max_abstention,
            )

    def test_complete_agreement_is_freeze_ready_but_not_evidence(self) -> None:
        report = self._run()
        self.assertTrue(report["ready_for_freeze"])
        self.assertTrue(report["ready_for_adjudication"])
        self.assertEqual(1.0, report["agreement"]["overall"])
        for name in (
            "operator_presence",
            "operator_essentiality",
            "contradiction_resolution",
            "solution_feasibility",
        ):
            self.assertEqual(1.0, report["ordinal_agreement"]["by_dimension"][name])
        self.assertIn("nominal_alpha", report["agreement"])
        self.assertFalse(report["evidence_eligible"])

    def test_unanimous_abstention_blocks_freeze_even_when_abstention_rate_is_allowed(self) -> None:
        def mutate(paths: list[Path], _digest: str, _case_hashes: dict[str, str], _dataset_batch_sha256: str) -> None:
            for path in paths:
                records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
                records[0]["label"] = "abstain"
                path.write_text(
                    "\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n",
                    encoding="utf-8",
                )

        report = self._run(mutate, case_count=5)
        self.assertFalse(report["ready_for_freeze"])
        self.assertTrue(report["ready_for_adjudication"])
        self.assertIn("unanimous_abstention", {issue["code"] for issue in report["issues"]})
        self.assertIn("case_000", report["agreement"]["unanimous_abstention_case_ids"])

    def test_disagreement_fails_threshold_but_is_ready_for_adjudication(self) -> None:
        def mutate(paths: list[Path], _digest: str, _case_hashes: dict[str, str], _dataset_batch_sha256: str) -> None:
            records = [json.loads(line) for line in paths[1].read_text(encoding="utf-8").splitlines()]
            records[0]["label"] = "inversion"
            self._write_jsonl(paths[1], records)

        report = self._run(mutate)
        self.assertFalse(report["ready_for_freeze"])
        self.assertTrue(report["ready_for_adjudication"])
        self.assertIn("agreement_threshold_not_met", {issue["code"] for issue in report["issues"]})

    def test_alpha_threshold_is_enforced(self) -> None:
        def mutate(paths: list[Path], _digest: str, _case_hashes: dict[str, str], _dataset_batch_sha256: str) -> None:
            records = [json.loads(line) for line in paths[1].read_text(encoding="utf-8").splitlines()]
            records[0]["label"] = "inversion"
            self._write_jsonl(paths[1], records)

        report = self._run(mutate, annotation_file_count=3)
        self.assertFalse(report["ready_for_freeze"])
        self.assertIn("nominal_alpha_threshold_not_met", {issue["code"] for issue in report["issues"]})
        self.assertTrue(report["ready_for_adjudication"])

    def test_report_schema_validation_succeeds(self) -> None:
        report = self._run()
        audit_schema = json.loads((ROOT / "schemas/blinded-annotation-audit.schema.json").read_text(encoding="utf-8"))
        self.assertEqual([], validate(report, audit_schema))

    def test_confidence_intervals_are_deterministic_and_schema_frozen_policy_metadata_present(self) -> None:
        report_one = self._run()
        report_two = self._run()
        intervals_one = report_one["agreement"]["confidence_intervals"]
        intervals_two = report_two["agreement"]["confidence_intervals"]
        self.assertEqual(intervals_one, intervals_two)
        for metric in ("raw_agreement", "nominal_alpha"):
            self.assertIn(metric, intervals_one)
            self.assertEqual(2, len(intervals_one[metric]))
            lower, upper = intervals_one[metric]
            self.assertLessEqual(lower, upper)
            self.assertTrue(math.isfinite(lower))
            self.assertTrue(math.isfinite(upper))
            self.assertGreaterEqual(lower, 0.0)
            self.assertLessEqual(upper, 1.0)

        policy = report_one["policy"]
        self.assertEqual(0.95, policy["confidence_level"])
        self.assertEqual(2000, policy["confidence_interval_resamples"])
        self.assertEqual(1729, policy["confidence_interval_seed"])
        self.assertEqual("case_bootstrap_percentile", policy["confidence_interval_method"])
        self.assertEqual("descriptive_only", policy["confidence_interval_gate"])

    def test_ordinal_alpha_finite_and_bounded_with_3rater_disagreement(self) -> None:
        def mutate(paths: list[Path], _digest: str, _case_hashes: dict[str, str], _dataset_batch_sha256: str) -> None:
            records = [json.loads(line) for line in paths[1].read_text(encoding="utf-8").splitlines()]
            records[0]["label"] = "inversion"
            records[0]["operator_presence"] = 0
            records[0]["operator_essentiality"] = 0
            records[0]["contradiction_resolution"] = 4
            records[0]["solution_feasibility"] = 4
            self._write_jsonl(paths[1], records)

        report = self._run(mutate, annotation_file_count=3)
        nominal_alpha = report["agreement"]["nominal_alpha"]
        self.assertTrue(math.isfinite(nominal_alpha))
        self.assertGreaterEqual(nominal_alpha, -1.0)
        self.assertLessEqual(nominal_alpha, 1.0)
        for value in report["ordinal_agreement"]["by_dimension"].values():
            self.assertTrue(math.isfinite(value))
            self.assertGreaterEqual(value, -1.0)
            self.assertLessEqual(value, 1.0)

    def test_guide_mismatch_fails_structural_readiness(self) -> None:
        def mutate(paths: list[Path], _digest: str, _case_hashes: dict[str, str], _dataset_batch_sha256: str) -> None:
            records = [json.loads(line) for line in paths[1].read_text(encoding="utf-8").splitlines()]
            records[0]["guide_sha256"] = "0" * 64
            self._write_jsonl(paths[1], records)

        report = self._run(mutate)
        self.assertFalse(report["ready_for_adjudication"])
        self.assertIn("guide_mismatch", {issue["code"] for issue in report["issues"]})

    def test_invalid_case_hash_is_rejected(self) -> None:
        def mutate(paths: list[Path], _digest: str, case_hashes: dict[str, str], _dataset_batch_sha256: str) -> None:
            records = [json.loads(line) for line in paths[0].read_text(encoding="utf-8").splitlines()]
            case_id = records[0]["case_id"]
            records[0]["case_payload_sha256"] = case_hashes[case_id][:-1] + "0"
            self._write_jsonl(paths[0], records)

        report = self._run(mutate)
        self.assertIn("invalid_case_hash", {issue["code"] for issue in report["issues"]})

    def test_wrong_batch_digest_is_rejected(self) -> None:
        def mutate(paths: list[Path], _digest: str, _case_hashes: dict[str, str], _dataset_batch_sha256: str) -> None:
            records = [json.loads(line) for line in paths[0].read_text(encoding="utf-8").splitlines()]
            records[0]["dataset_batch_sha256"] = "0" * 64
            self._write_jsonl(paths[0], records)

        report = self._run(mutate)
        self.assertIn("invalid_batch_hash", {issue["code"] for issue in report["issues"]})

    def test_invalid_label_is_rejected(self) -> None:
        def mutate(paths: list[Path], _digest: str, _case_hashes: dict[str, str], _dataset_batch_sha256: str) -> None:
            records = [json.loads(line) for line in paths[0].read_text(encoding="utf-8").splitlines()]
            records[0]["label"] = "invalid_label"
            self._write_jsonl(paths[0], records)

        report = self._run(mutate)
        self.assertTrue(
            any(issue["code"] in {"invalid_label", "schema_invalid"} for issue in report["issues"]),
            "invalid_label should be rejected",
        )

    def test_requires_separate_files_for_minimum_raters(self) -> None:
        with self.assertRaisesRegex(AnnotationAuditError, "independent annotation files"):
            audit_annotations(
                cases_path=ROOT / "data/candidates/wave1-model-generated.jsonl",
                guide_path=ROOT / "experiments/001-stage1-pilot/annotation-guide.json",
                annotation_schema_path=ROOT / "schemas/dataset-annotation.schema.json",
                annotation_paths=[],
            )


if __name__ == "__main__":
    unittest.main()
