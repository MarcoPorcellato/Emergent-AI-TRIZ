from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0_corpus import generate_a0_corpus
from latent_triz.a0_shortcuts import audit_a0_shortcuts


class A0ShortcutTests(unittest.TestCase):
    protocol_path = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "a0-automated-weak-proxy"
        / "protocol.json"
    )

    def test_real_generated_corpus_only_calibration_and_no_sealed_access(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "a0"
            manifest = generate_a0_corpus(self.protocol_path, output)
            result = audit_a0_shortcuts(
                output / "cases.jsonl",
                output / "procedural-targets" / "targets.jsonl",
                self.protocol_path,
            )
            self.assertEqual(result["artifact_class"], "a0-shortcut-audit")
            self.assertIn(result["status"], {"pass", "non_interpretable"})
            self.assertEqual(result["counts"]["calibration_cases"], 96)
            self.assertEqual(result["counts"]["sealed_cases"], 0)
            self.assertIn("overall", result["controls"])
            self.assertIn(result["controls"]["overall"]["status"], {"pass", "non_interpretable"})
            self.assertEqual(result["counts"]["total_cases"], 96)
            for control in (
                "bag_of_words_baselines",
                "character_ngram_baselines",
                "length_and_punctuation_baselines",
                "style_and_template_baselines",
                "provenance_classifiers",
                "problem_only_label_prediction",
                "leave_one_domain_out_surface_evaluation",
                "duplicate_and_near_duplicate_detection",
                "family_leakage_detection",
                "random_label_controls",
                "random_partition_controls",
                "generic_action_taxonomy_controls",
                "generic_transformation_taxonomy_controls",
                "adjacent_principle_proxy_controls",
            ):
                self.assertIn(control, result["controls"], msg=f"missing control {control}")
            self.assertEqual(manifest["counts"]["calibration_cases"], 96)

    def test_deliberately_leaky_fixture_reports_non_interpretable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            cases = [
                {
                    "case_id": "case_a_a",
                    "problem_family_id": "family_a",
                    "solution_variant_id": "variant_a",
                    "domain": "software",
                    "split": "calibration",
                    "problem": "Coordinate a parallel pipeline by splitting tasks into independent blocks.",
                    "constraints": ["keep legacy endpoints"],
                    "initial_state": "one central coordinator processes everything.",
                    "desired_improvement": "faster throughput",
                    "worsening_consequence": "delays",
                    "transformation": "Split the process into independent segments.",
                    "resulting_state": "segments finish independently.",
                    "solution": "A distributed split avoids overload.",
                },
                {
                    "case_id": "case_a_b",
                    "problem_family_id": "family_a",
                    "solution_variant_id": "variant_b",
                    "domain": "software",
                    "split": "calibration",
                    "problem": "Coordinate a pipeline where the global path drives each segment.",
                    "constraints": ["keep legacy endpoints"],
                    "initial_state": "many parallel tasks.",
                    "desired_improvement": "faster throughput",
                    "worsening_consequence": "errors",
                    "transformation": "Invert order so center acts first and branches later.",
                    "resulting_state": "the center now leads.",
                    "solution": "A single reverse flow controls each branch.",
                },
                {
                    "case_id": "case_b_a",
                    "problem_family_id": "family_b",
                    "solution_variant_id": "variant_a",
                    "domain": "transport",
                    "split": "calibration",
                    "problem": "Local units coordinate and report upstream.",
                    "constraints": ["keep legacy endpoints"],
                    "initial_state": "single route.",
                    "desired_improvement": "steadier flow",
                    "worsening_consequence": "jams",
                    "transformation": "Split the route by lane and distribute tasks.",
                    "resulting_state": "parallel lanes stabilize usage.",
                    "solution": "Local lanes are split first.",
                },
                {
                    "case_id": "case_b_b",
                    "problem_family_id": "family_b",
                    "solution_variant_id": "variant_b",
                    "domain": "transport",
                    "split": "calibration",
                    "problem": "A central scheduler should invert sequence.",
                    "constraints": ["keep legacy endpoints"],
                    "initial_state": "parallel lanes.",
                    "desired_improvement": "steadier flow",
                    "worsening_consequence": "jams",
                    "transformation": "Invert the signal so controller leads and lanes follow.",
                    "resulting_state": "the center assigns each lane.",
                    "solution": "A global reverse schedule directs all lanes.",
                },
            ]
            targets = [
                {
                    "target_record_id": "target_case_a_a",
                    "case_id": "case_a_a",
                    "problem_family_id": "family_a",
                    "solution_variant_id": "variant_a",
                    "operator_proxy_family": "segmentation_like",
                    "generator_rule": "tpl_seg_inv_001",
                    "split": "calibration",
                    "provenance": {
                        "template_id": "tpl_seg_inv_001",
                        "generator_id": "latent-triz-a0-corpus-v1",
                        "seed": 1,
                        "license": "Apache-2.0",
                    },
                },
                {
                    "target_record_id": "target_case_a_b",
                    "case_id": "case_a_b",
                    "problem_family_id": "family_a",
                    "solution_variant_id": "variant_b",
                    "operator_proxy_family": "inversion_like",
                    "generator_rule": "tpl_seg_inv_001",
                    "split": "calibration",
                    "provenance": {
                        "template_id": "tpl_seg_inv_001",
                        "generator_id": "latent-triz-a0-corpus-v1",
                        "seed": 1,
                        "license": "Apache-2.0",
                    },
                },
                {
                    "target_record_id": "target_case_b_a",
                    "case_id": "case_b_a",
                    "problem_family_id": "family_b",
                    "solution_variant_id": "variant_a",
                    "operator_proxy_family": "segmentation_like",
                    "generator_rule": "tpl_seg_inv_001",
                    "split": "calibration",
                    "provenance": {
                        "template_id": "tpl_seg_inv_001",
                        "generator_id": "latent-triz-a0-corpus-v1",
                        "seed": 1,
                        "license": "Apache-2.0",
                    },
                },
                {
                    "target_record_id": "target_case_b_b",
                    "case_id": "case_b_b",
                    "problem_family_id": "family_b",
                    "solution_variant_id": "variant_b",
                    "operator_proxy_family": "inversion_like",
                    "generator_rule": "tpl_seg_inv_001",
                    "split": "calibration",
                    "provenance": {
                        "template_id": "tpl_seg_inv_001",
                        "generator_id": "latent-triz-a0-corpus-v1",
                        "seed": 1,
                        "license": "Apache-2.0",
                    },
                },
            ]
            cases_path = workdir / "cases.jsonl"
            targets_path = workdir / "targets.jsonl"
            for row in cases:
                if "case_content_sha256" in row:
                    row.pop("case_content_sha256")
                if "target_content_sha256" in row:
                    row.pop("target_content_sha256")
            cases_path.write_text(
                "".join(json.dumps(row) + "\n" for row in cases), encoding="utf-8"
            )
            targets_path.write_text(
                "".join(json.dumps(row) + "\n" for row in targets), encoding="utf-8"
            )
            report = audit_a0_shortcuts(cases_path, targets_path, self.protocol_path)
            self.assertEqual(report["controls"]["overall"]["status"], "non_interpretable")
            self.assertEqual(report["status"], "non_interpretable")
            self.assertEqual(report["counts"]["calibration_cases"], 4)

    def test_integrity_failure_for_family_split_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            cases = [
                {
                    "case_id": "case_a_a",
                    "problem_family_id": "family_a",
                    "solution_variant_id": "variant_a",
                    "domain": "software",
                    "split": "calibration",
                    "problem": "A simple process change.",
                    "constraints": ["keep legacy endpoints"],
                    "initial_state": "baseline",
                    "desired_improvement": "improve throughput",
                    "worsening_consequence": "cost",
                    "transformation": "split tasks.",
                    "resulting_state": "more balance.",
                    "solution": "parallel split first.",
                },
                {
                    "case_id": "case_a_b",
                    "problem_family_id": "family_a",
                    "solution_variant_id": "variant_b",
                    "domain": "software",
                    "split": "sealed",
                    "problem": "A process that should reverse order.",
                    "constraints": ["keep legacy endpoints"],
                    "initial_state": "baseline",
                    "desired_improvement": "improve throughput",
                    "worsening_consequence": "cost",
                    "transformation": "reverse sequence.",
                    "resulting_state": "fewer collisions.",
                    "solution": "central controller leads.",
                },
            ]
            targets = [
                {
                    "target_record_id": "target_case_a_a",
                    "case_id": "case_a_a",
                    "problem_family_id": "family_a",
                    "solution_variant_id": "variant_a",
                    "operator_proxy_family": "segmentation_like",
                    "generator_rule": "tpl_seg_inv_001",
                    "split": "calibration",
                    "provenance": {
                        "template_id": "tpl_seg_inv_001",
                        "generator_id": "latent-triz-a0-corpus-v1",
                        "seed": 1,
                        "license": "Apache-2.0",
                    },
                },
                {
                    "target_record_id": "target_case_a_b",
                    "case_id": "case_a_b",
                    "problem_family_id": "family_a",
                    "solution_variant_id": "variant_b",
                    "operator_proxy_family": "inversion_like",
                    "generator_rule": "tpl_seg_inv_001",
                    "split": "sealed",
                    "provenance": {
                        "template_id": "tpl_seg_inv_001",
                        "generator_id": "latent-triz-a0-corpus-v1",
                        "seed": 1,
                        "license": "Apache-2.0",
                    },
                },
            ]
            cases_path = workdir / "cases.jsonl"
            targets_path = workdir / "targets.jsonl"
            cases_path.write_text(
                "".join(json.dumps(row) + "\n" for row in cases), encoding="utf-8"
            )
            targets_path.write_text(
                "".join(json.dumps(row) + "\n" for row in targets), encoding="utf-8"
            )
            report = audit_a0_shortcuts(cases_path, targets_path, self.protocol_path)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["controls"]["overall"]["status"], "failed")
            self.assertEqual(report["controls"]["integrity"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
