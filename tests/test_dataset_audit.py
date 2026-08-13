from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.dataset_audit import DatasetAuditError, run_dataset_audit


class DatasetAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.plan = self.repo_root / "experiments/001-stage1-pilot/dataset-plan.json"

    def _write_cases(self, workdir: Path, records) -> Path:
        path = workdir / "cases.jsonl"
        lines = [json.dumps(item) for item in records]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_development_mode_reports_gaps_and_keeps_go(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            cases = [
                {
                    "case_id": "case_a",
                    "domain": "manufacturing",
                    "problem": "Machine oscillates under load.",
                    "constraints": ["budget"],
                    "initial_state": "High vibration",
                    "desired_improvement": "Increase stability",
                    "worsening_consequence": "Misalignment",
                    "transformation": "Add damping mounts",
                    "resulting_state": "Stable output",
                    "labels": [{"principle": "segmentation", "annotator_id": "a1"}],
                    "split": "discovery",
                    "provenance": {"source_type": "human_authored", "license": "CC0", "created_at": "2026-08-12"},
                },
                {
                    "case_id": "case_b",
                    "domain": "packaging",
                    "problem": "Shock damage during shipping.",
                    "constraints": ["low_cost"],
                    "initial_state": "Vulnerable box",
                    "desired_improvement": "Protect items",
                    "worsening_consequence": "Scratches",
                    "transformation": "Segment compartments",
                    "resulting_state": "Reduced motion",
                    "labels": [{"principle": "segmentation", "annotator_id": "a2"}],
                    "split": "validation",
                    "provenance": {"source_type": "human_authored", "license": "CC0", "created_at": "2026-08-12"},
                },
            ]
            case_path = self._write_cases(Path(workdir), cases)
            report = run_dataset_audit(self.plan, case_path, mode="development")
            self.assertEqual(report["mode"], "development")
            self.assertTrue(report["structural_ok"])
            self.assertFalse(report["ready"])
            self.assertFalse(report["freeze_ready"])
            self.assertTrue(any(item["metric"] == "target_size_exact" for item in report["target_gaps"]))
            self.assertEqual(report["status"], "pass_with_gaps")

    def test_freeze_mode_fails_if_targets_not_met(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            case_path = self._write_cases(
                Path(workdir),
                [
                    {
                        "case_id": "case_a",
                        "domain": "manufacturing",
                        "problem": "Machine oscillates under load.",
                        "constraints": ["budget"],
                        "initial_state": "High vibration",
                        "desired_improvement": "Increase stability",
                        "worsening_consequence": "Misalignment",
                        "transformation": "Add damping mounts",
                        "resulting_state": "Stable output",
                        "labels": [{"principle": "segmentation", "annotator_id": "a1"}],
                        "split": "discovery",
                        "provenance": {"source_type": "human_authored", "license": "CC0", "created_at": "2026-08-12"},
                    }
                ],
            )
            report = run_dataset_audit(self.plan, case_path, mode="freeze")
            self.assertEqual(report["mode"], "freeze")
            self.assertFalse(report["ready"])
            self.assertEqual(report["status"], "fail")
            self.assertIn("target_size_exact", {gap["metric"] for gap in report["target_gaps"]})

    def test_duplicate_content_flags_cross_split_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            case_path = self._write_cases(
                Path(workdir),
                [
                    {
                        "case_id": "case_a",
                        "domain": "manufacturing",
                        "problem": "A machine overheats at load.",
                        "constraints": ["low_cost"],
                        "initial_state": "A motor heats quickly",
                        "desired_improvement": "Maintain temperature",
                        "worsening_consequence": "Tool drift",
                        "transformation": "Add cooling fins",
                        "resulting_state": "Stable run",
                        "labels": [{"principle": "segmentation", "annotator_id": "a1"}],
                        "split": "discovery",
                        "provenance": {"source_type": "human_authored", "license": "CC0", "created_at": "2026-08-12"},
                    },
                    {
                        "case_id": "case_b",
                        "domain": "manufacturing",
                        "problem": "A machine overheats at load.",
                        "constraints": ["low_cost"],
                        "initial_state": "A motor heats quickly",
                        "desired_improvement": "Maintain temperature",
                        "worsening_consequence": "Tool drift",
                        "transformation": "Add cooling fins",
                        "resulting_state": "Stable run",
                        "labels": [{"principle": "segmentation", "annotator_id": "a2"}],
                        "split": "validation",
                        "provenance": {"source_type": "human_authored", "license": "CC0", "created_at": "2026-08-12"},
                    },
                ],
            )
            report = run_dataset_audit(self.plan, case_path, mode="development")
            codes = {item["code"] for item in report["issues"]}
            self.assertIn("cross_split_leakage", codes)

    def test_forbidden_terms_and_references(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            case_path = self._write_cases(
                Path(workdir),
                [
                    {
                        "case_id": "case_bad",
                        "domain": "transport",
                        "problem": "TRIZ-based solution is needed.",
                        "constraints": ["test"],
                        "initial_state": "A system fails",
                        "desired_improvement": "Reduce failures",
                        "worsening_consequence": "downtime",
                        "transformation": "Balance load",
                        "resulting_state": "Reliable output",
                        "labels": [{"principle": "segmentation", "annotator_id": "a1"}],
                        "near_miss_case_ids": ["case_bad", "case_missing"],
                        "split": "discovery",
                        "provenance": {"source_type": "human_authored", "license": "CC0", "created_at": "2026-08-12"},
                    }
                ],
            )
            report = run_dataset_audit(self.plan, case_path, mode="development")
            codes = {item["code"] for item in report["issues"]}
            self.assertIn("forbidden_term", codes)
            self.assertIn("self_reference", codes)
            self.assertIn("missing_reference", codes)

    def test_duplicate_reference_values_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            case_path = self._write_cases(
                Path(workdir),
                [
                    {
                        "case_id": "case_a",
                        "domain": "manufacturing",
                        "problem": "A device overheats.",
                        "constraints": ["safety"],
                        "initial_state": "Heat accumulates.",
                        "desired_improvement": "Reduce heat",
                        "worsening_consequence": "Failure",
                        "transformation": "Add cooling fan.",
                        "resulting_state": "Stable run",
                        "labels": [{"principle": "segmentation", "annotator_id": "a1"}],
                        "near_miss_case_ids": ["case_b", "case_b"],
                        "split": "discovery",
                        "provenance": {"source_type": "human_authored", "license": "CC0", "created_at": "2026-08-12"},
                    },
                    {
                        "case_id": "case_b",
                        "domain": "manufacturing",
                        "problem": "Different problem text.",
                        "constraints": ["safety"],
                        "initial_state": "Stable baseline.",
                        "desired_improvement": "Protect parts",
                        "worsening_consequence": "Delay",
                        "transformation": "Add cover.",
                        "resulting_state": "More stable",
                        "labels": [{"principle": "segmentation", "annotator_id": "a2"}],
                        "split": "validation",
                        "provenance": {"source_type": "human_authored", "license": "CC0", "created_at": "2026-08-12"},
                    },
                ],
            )
            report = run_dataset_audit(self.plan, case_path, mode="development")
            self.assertIn("duplicate_reference_value", {item["code"] for item in report["issues"]})

    def test_matched_case_id_symmetry_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            case_path = self._write_cases(
                Path(workdir),
                [
                    {
                        "case_id": "case_a",
                        "domain": "manufacturing",
                        "problem": "Machine is noisy.",
                        "constraints": ["safety"],
                        "initial_state": "High frequency noise.",
                        "desired_improvement": "Reduce noise",
                        "worsening_consequence": "Fatigue",
                        "transformation": "Add insulation.",
                        "resulting_state": "Quieter",
                        "labels": [{"principle": "segmentation", "annotator_id": "a1"}],
                        "lexical_controls": {"matched_case_ids": ["case_b"]},
                        "split": "discovery",
                        "provenance": {"source_type": "human_authored", "license": "CC0", "created_at": "2026-08-12"},
                    },
                    {
                        "case_id": "case_b",
                        "domain": "transport",
                        "problem": "Machine is hotter.",
                        "constraints": ["safety"],
                        "initial_state": "A machine overheats.",
                        "desired_improvement": "Reduce heat",
                        "worsening_consequence": "Failure",
                        "transformation": "Add cooling fins.",
                        "resulting_state": "Cooler",
                        "labels": [{"principle": "segmentation", "annotator_id": "a2"}],
                        "split": "validation",
                        "provenance": {"source_type": "human_authored", "license": "CC0", "created_at": "2026-08-12"},
                    },
                ],
            )
            report = run_dataset_audit(self.plan, case_path, mode="development")
            self.assertIn("asymmetric_matched_reference", {item["code"] for item in report["issues"]})

    def test_max_model_generated_ratio_is_audited(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            case_path = self._write_cases(
                Path(workdir),
                [
                    {
                        "case_id": "case_a",
                        "domain": "manufacturing",
                        "problem": "Machine is noisy.",
                        "constraints": ["safety"],
                        "initial_state": "High frequency noise.",
                        "desired_improvement": "Reduce noise",
                        "worsening_consequence": "Fatigue",
                        "transformation": "Add insulation.",
                        "resulting_state": "Quieter",
                        "labels": [{"principle": "segmentation", "annotator_id": "a1"}],
                        "split": "discovery",
                        "provenance": {"source_type": "model_generated", "license": "CC0", "created_at": "2026-08-12"},
                    },
                    {
                        "case_id": "case_b",
                        "domain": "transport",
                        "problem": "Machine is hotter.",
                        "constraints": ["safety"],
                        "initial_state": "A machine overheats.",
                        "desired_improvement": "Reduce heat",
                        "worsening_consequence": "Failure",
                        "transformation": "Add cooling fins.",
                        "resulting_state": "Cooler",
                        "labels": [{"principle": "segmentation", "annotator_id": "a2"}],
                        "split": "validation",
                        "provenance": {"source_type": "model_generated", "license": "CC0", "created_at": "2026-08-12"},
                    },
                ],
            )
            report = run_dataset_audit(self.plan, case_path, mode="development")
            self.assertIn("max_model_generated_ratio_exceeded", {item["code"] for item in report["issues"]})

    def test_invalid_mode_raises_error(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            case_path = self._write_cases(
                Path(workdir),
                [
                    {
                        "case_id": "case_a",
                        "domain": "manufacturing",
                        "problem": "Machine oscillates under load.",
                        "constraints": ["budget"],
                        "initial_state": "High vibration",
                        "desired_improvement": "Increase stability",
                        "worsening_consequence": "Misalignment",
                        "transformation": "Add damping mounts",
                        "resulting_state": "Stable output",
                        "labels": [{"principle": "segmentation", "annotator_id": "a1"}],
                        "split": "discovery",
                        "provenance": {"source_type": "human_authored", "license": "CC0", "created_at": "2026-08-12"},
                    }
                ],
            )
            with self.assertRaises(DatasetAuditError):
                run_dataset_audit(self.plan, case_path, mode="audit")


if __name__ == "__main__":
    unittest.main()
