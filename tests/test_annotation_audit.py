from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from latent_triz.annotation_audit import AnnotationAuditError, audit_annotations
from latent_triz.validator import validate


ROOT = Path(__file__).resolve().parents[1]


class AnnotationAuditTests(unittest.TestCase):
    def _write_jsonl(self, path: Path, records: list[dict]) -> None:
        path.write_text("\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n", encoding="utf-8")

    def _run(self, mutate=None, *, threshold: float = 0.8, max_abstention: float = 0.2) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path, guide_path = root / "cases.jsonl", root / "guide.json"
            cases = [{"case_id": f"case_{index:03d}"} for index in range(4)]
            self._write_jsonl(cases_path, cases)
            guide = {
                "revision": "v1.0.0",
                "labels": [{"id": "segmentation"}, {"id": "inversion"}],
                "abstention": {"id": "abstain"},
            }
            guide_path.write_text(json.dumps(guide, sort_keys=True), encoding="utf-8")
            guide_digest = hashlib.sha256(guide_path.read_bytes()).hexdigest()
            paths: list[Path] = []
            for rater in ("rater_1", "rater_2"):
                records = [
                    {
                        "annotation_id": f"{rater}_{case['case_id']}",
                        "case_id": case["case_id"],
                        "rater_id": rater,
                        "label": "segmentation" if index < 2 else "inversion",
                        "confidence": 0.8,
                        "rationale": "The described operation matches the selected definition.",
                        "non_empirical": False,
                        "annotated_at": "2026-08-13T00:00:00Z",
                        "guide_revision": "v1.0.0",
                        "guide_sha256": guide_digest,
                    }
                    for index, case in enumerate(cases)
                ]
                path = root / f"{rater}.jsonl"
                self._write_jsonl(path, records)
                paths.append(path)
            if mutate is not None:
                mutate(paths, guide_digest)
            return audit_annotations(
                cases_path=cases_path,
                guide_path=guide_path,
                annotation_schema_path=ROOT / "schemas/dataset-annotation.schema.json",
                annotation_paths=paths,
                agreement_threshold=threshold,
                maximum_abstention_rate=max_abstention,
            )

    def test_complete_agreement_is_freeze_ready_but_not_evidence(self) -> None:
        report = self._run()
        self.assertTrue(report["ready_for_freeze"])
        self.assertEqual(1.0, report["agreement"]["overall"])
        self.assertTrue(report["empirical"])
        self.assertFalse(report["evidence_eligible"])
        schema = json.loads((ROOT / "schemas/blinded-annotation-audit.schema.json").read_text(encoding="utf-8"))
        self.assertEqual([], validate(report, schema))

    def test_disagreement_fails_threshold_but_is_ready_for_adjudication(self) -> None:
        def mutate(paths: list[Path], _digest: str) -> None:
            records = [json.loads(line) for line in paths[1].read_text(encoding="utf-8").splitlines()]
            records[0]["label"] = "inversion"
            self._write_jsonl(paths[1], records)

        report = self._run(mutate)
        self.assertFalse(report["ready_for_freeze"])
        self.assertTrue(report["ready_for_adjudication"])
        self.assertIn("agreement_threshold_not_met", {issue["code"] for issue in report["issues"]})

    def test_aggregate_threshold_cannot_hide_unresolved_case(self) -> None:
        def mutate(paths: list[Path], _digest: str) -> None:
            records = [json.loads(line) for line in paths[1].read_text(encoding="utf-8").splitlines()]
            records[0]["label"] = "inversion"
            self._write_jsonl(paths[1], records)

        report = self._run(mutate, threshold=0.7)
        self.assertGreaterEqual(report["agreement"]["overall"], 0.7)
        self.assertFalse(report["ready_for_freeze"])
        self.assertTrue(report["ready_for_adjudication"])
        self.assertIn("unresolved_case", {issue["code"] for issue in report["issues"]})

    def test_guide_mismatch_fails_structural_readiness(self) -> None:
        def mutate(paths: list[Path], _digest: str) -> None:
            records = [json.loads(line) for line in paths[1].read_text(encoding="utf-8").splitlines()]
            records[0]["guide_sha256"] = "0" * 64
            self._write_jsonl(paths[1], records)

        report = self._run(mutate)
        self.assertFalse(report["ready_for_adjudication"])
        self.assertIn("guide_mismatch", {issue["code"] for issue in report["issues"]})

    def test_abstentions_are_retained_and_bounded(self) -> None:
        def mutate(paths: list[Path], _digest: str) -> None:
            for path in paths:
                records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
                records[0]["label"] = "abstain"
                records[0]["confidence"] = 0
                self._write_jsonl(path, records)

        report = self._run(mutate, max_abstention=0.1)
        self.assertEqual(2, report["counts"]["abstentions"])
        self.assertIn("abstention_rate_exceeded", {issue["code"] for issue in report["issues"]})

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
