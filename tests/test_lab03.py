from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.lab03 import build_lab03_report
from latent_triz.lab03_baselines import (
    Lab03Error,
    _categorical_shortcut_diagnostic,
    run_behavioral_baselines,
)


class Lab03Tests(unittest.TestCase):
    def _write_json(self, path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")

    def _cases(self) -> list[dict]:
        rows = []
        for domain_index, domain in enumerate(("mechanical", "software", "medical", "logistics")):
            for label in ("segmentation", "inversion"):
                token = "divide" if label == "segmentation" else "reverse"
                rows.append({
                    "case_id": f"case_{domain_index}_{label}",
                    "domain": domain,
                    "problem": f"{domain} neutral problem {domain_index}",
                    "constraints": ["bounded"],
                    "initial_state": "initial",
                    "desired_improvement": "improve",
                    "worsening_consequence": "tradeoff",
                    "transformation": f"{token} operation",
                    "resulting_state": "result",
                    "labels": [{"principle": label, "annotator_id": "r1"}],
                })
        return rows

    def _cases_with_provenance(
        self,
        *,
        with_template: bool = False,
        with_generator_variants: bool = False,
    ) -> list[dict]:
        rows = self._cases()
        for idx, row in enumerate(rows):
            row["provenance"] = {
                "source_type": "model_generated",
                "generator_id": f"generator_{idx % 2}",
            }
            if with_template:
                row["provenance"]["template_id"] = f"template_{idx}"
            if with_generator_variants:
                row["provenance"]["generator_id"] = (
                    "generator_a" if idx % 2 else "generator_b"
                )
        return rows

    def _provenance_classifier(self, result: dict, key: str) -> dict:
        provenance = result["shortcuts"]["provenance"]
        if "classifiers" in provenance:
            return provenance["classifiers"][key]
        return provenance[key]

    def _snapshot(self, status: str = "pass") -> dict:
        return {
            "status": status,
            "immutable_revision": "sha256:" + "a" * 64,
            "split_membership_digest": "sha256:" + "b" * 64,
        }

    def _config(self) -> dict:
        return {
            "config_version": "v1",
            "status": "fail",
            "seed": 1729,
            "random_permutations": 5,
            "minimum_labels": 2,
            "minimum_domains": 4,
            "minimum_cases_per_label": 2,
            "minimum_training_cases_per_label": 3,
            "minimum_cases_per_held_out_domain": 2,
            "minimum_cases_per_label_per_domain": 1,
            "shortcut_macro_f1_threshold": 0.8,
            "shortcut_margin_over_majority": 0.1,
            "evaluation_views": [
                "problem_only", "transformation_only", "resulting_state_only", "problem_plus_solution",
            ],
            "method_families": [
                "majority", "keyword_matching", "bag_of_words",
                "conventional_sentence_embeddings", "topic_classification",
                "output_only_llm", "random_label",
            ],
            "allow_local_diagnostics": ["char_ngram", "length_punctuation"],
            "families": {},
            "non_claim_boundary": {"empirical": False, "evidence_eligible": False, "claim_ids": []},
        }

    def _run(self, root: Path, *, snapshot_status: str = "pass", config: dict | None = None) -> dict:
        cases = root / "cases.jsonl"
        snapshot = root / "snapshot.json"
        config_path = root / "config.json"
        self._write_jsonl(cases, self._cases())
        self._write_json(snapshot, self._snapshot(snapshot_status))
        self._write_json(config_path, config or self._config())
        return run_behavioral_baselines(cases, snapshot, config_path)

    def _run_with_cases(self, root: Path, *, cases: list[dict], config: dict | None = None, snapshot_status: str = "pass") -> dict:
        snapshot = root / "snapshot.json"
        config_path = root / "config.json"
        self._write_jsonl(root / "cases.jsonl", cases)
        self._write_json(snapshot, self._snapshot(snapshot_status))
        self._write_json(config_path, config or self._config())
        return run_behavioral_baselines(root / "cases.jsonl", snapshot, config_path)

    def test_adequate_local_fixture_runs_complete_lodo_and_random_control(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run(Path(directory))
        gates = {row["gate"]: row["status"] for row in result["gates"]}
        self.assertEqual(gates["B1"], "pass")
        self.assertEqual(gates["B2"], "pass")
        self.assertEqual(gates["B3"], "pass")
        self.assertEqual(gates["B5"], "pass")
        self.assertEqual(gates["B6"], "pass")
        self.assertEqual(gates["B4"], "fail")
        for view_name in ("problem_only", "transformation_only", "resulting_state_only", "problem_plus_solution"):
            self.assertEqual(len(result["methods"]["bag_of_words"]["views"][view_name]["folds"]), 4)

    def test_transformation_only_shows_stronger_signal_than_problem_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run(Path(directory))
        bow = result["methods"]["bag_of_words"]["views"]
        self.assertGreater(
            bow["transformation_only"]["aggregate"]["macro_f1"],
            bow["problem_only"]["aggregate"]["macro_f1"],
        )
        self.assertGreaterEqual(
            bow["transformation_only"]["aggregate"]["macro_f1"],
            bow["resulting_state_only"]["aggregate"]["macro_f1"],
        )

    def test_tracked_wave1_reports_shortcut_risk_in_every_frozen_view(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = run_behavioral_baselines(
            root / "data/candidates/wave1-model-generated.jsonl",
            root / "results/lab02/dataset-anatomy/snapshot_manifest.json",
            root / "experiments/wave1-surface-audit/config.json",
        )
        gate = next(row for row in result["gates"] if row["gate"] == "B7")
        self.assertEqual("fail", gate["status"])
        for view_name in (
            "problem_only", "transformation_only", "resulting_state_only", "problem_plus_solution",
        ):
            self.assertIn(view_name, gate["details"])
        self.assertFalse(result["empirical"])
        self.assertFalse(result["evidence_eligible"])
        self.assertEqual([], result["claim_ids"])

    def test_all_local_methods_cover_four_lodo_views(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run(Path(directory))
        for method_name in ("majority", "keyword_matching", "bag_of_words", "char_ngram", "length_punctuation"):
            views = result["methods"][method_name]["views"]
            self.assertEqual(
                set(views.keys()),
                {"problem_only", "transformation_only", "resulting_state_only", "problem_plus_solution"},
            )
            for view_name, view in views.items():
                self.assertEqual(len(view["folds"]), 4)
                self.assertEqual(
                    {fold["domain"] for fold in view["folds"]},
                    {"mechanical", "software", "medical", "logistics"},
                )

    def test_behavioral_result_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self._run(root)
            second = self._run(root)
        self.assertEqual(first, second)

    def test_lodo_fails_when_a_domain_lacks_a_label(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = [row for row in self._cases() if not (
                row["domain"] == "mechanical"
                and row["labels"][0]["principle"] == "inversion"
            )]
            self._write_jsonl(root / "cases.jsonl", cases)
            self._write_json(root / "snapshot.json", self._snapshot())
            self._write_json(root / "config.json", self._config())
            result = run_behavioral_baselines(root / "cases.jsonl", root / "snapshot.json", root / "config.json")
        gates = {row["gate"]: row["status"] for row in result["gates"]}
        self.assertEqual(gates["B2"], "fail")
        self.assertEqual(gates["B5"], "fail")

    def test_external_family_receipts_are_hash_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._config()
            for family in ("conventional_sentence_embeddings", "topic_classification", "output_only_llm"):
                receipt_path = root / f"{family}.json"
                self._write_json(receipt_path, {
                    "artifact_class": "behavioral-baseline-adapter-receipt",
                    "family": family,
                    "status": "completed",
                    "empirical": False,
                    "evidence_eligible": False,
                    "claim_ids": [],
                })
                config["families"][family] = {
                    "status": "completed",
                    "receipt_path": receipt_path.name,
                    "sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
                }
            result = self._run(root, config=config)
        gate_b4 = next(row for row in result["gates"] if row["gate"] == "B4")
        self.assertEqual(gate_b4["status"], "pass")

    def test_provenance_shortcuts_mark_not_evaluable_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self._run(Path(directory))
        source = self._provenance_classifier(result, "source_type")
        template = self._provenance_classifier(result, "template_id")
        self.assertEqual(source["status"], "not_evaluable")
        self.assertFalse(source["evaluable"])
        self.assertEqual(template["status"], "not_evaluable")
        self.assertFalse(template["evaluable"])

    def test_unique_templates_and_single_source_are_not_evaluable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = self._cases_with_provenance(with_template=True)
            result = self._run_with_cases(root, cases=cases)
        source = self._provenance_classifier(result, "source_type")
        template = self._provenance_classifier(result, "template_id")
        self.assertEqual(source["status"], "not_evaluable")
        self.assertFalse(source["evaluable"])
        self.assertEqual(template["status"], "not_evaluable")
        self.assertFalse(template["evaluable"])

    def test_repeated_diverse_provenance_categories_are_evaluable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = self._cases_with_provenance(
                with_template=True,
                with_generator_variants=True,
            )
            for index, case in enumerate(cases):
                case["provenance"]["source_type"] = "model_generated" if index % 2 else "human_authored"
                case["provenance"]["template_id"] = f"template_{index % 2}"
            result = self._run_with_cases(root, cases=cases)
        source = self._provenance_classifier(result, "source_type")
        template = self._provenance_classifier(result, "template_id")
        generator = self._provenance_classifier(result, "generator_identity")
        self.assertTrue(source["evaluable"])
        self.assertTrue(template["evaluable"])
        self.assertTrue(generator["evaluable"])
        self.assertIn("folds", source)
        self.assertEqual(len(source["folds"]), 4)
        self.assertTrue(source["shortcut_detected"] in (True, False))

    def test_categorical_shortcut_majority_baseline_uses_train_labels(self) -> None:
        cases = [
            {"case_id": "1", "domain": "domain_a", "label": "segmentation", "source_type": "alpha"},
            {"case_id": "2", "domain": "domain_a", "label": "segmentation", "source_type": "beta"},
            {"case_id": "3", "domain": "domain_b", "label": "inversion", "source_type": "alpha"},
            {"case_id": "4", "domain": "domain_b", "label": "inversion", "source_type": "beta"},
            {"case_id": "5", "domain": "domain_c", "label": "inversion", "source_type": "alpha"},
            {"case_id": "6", "domain": "domain_c", "label": "inversion", "source_type": "beta"},
        ]
        result = _categorical_shortcut_diagnostic(
            cases=cases,
            labels=("segmentation", "inversion"),
            field="source_type",
            shortcut_threshold=0.5,
            shortcut_margin=0.0,
            minimum_category_count=1,
        )
        self.assertEqual(result["status"], "pass")
        fold_lookup = {row["domain"]: row for row in result["folds"]}
        self.assertEqual(len(fold_lookup), 3)
        self.assertAlmostEqual(fold_lookup["domain_a"]["majority_baseline_metrics"]["accuracy"], 0.0)
        self.assertAlmostEqual(fold_lookup["domain_a"]["metrics"]["accuracy"], 0.0)

    def test_wave1_fixture_single_source_is_not_evaluable_for_metadata_shortcuts(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = run_behavioral_baselines(
            root / "data/candidates/wave1-model-generated.jsonl",
            root / "results/lab02/dataset-anatomy/snapshot_manifest.json",
            root / "experiments/wave1-surface-audit/config.json",
        )
        source = self._provenance_classifier(result, "source_type")
        generator = self._provenance_classifier(result, "generator_identity")
        template = self._provenance_classifier(result, "template_id")
        self.assertEqual(source["status"], "not_evaluable")
        self.assertFalse(source["evaluable"])
        self.assertEqual(generator["status"], "not_evaluable")
        self.assertFalse(generator["evaluable"])
        self.assertEqual(template["status"], "not_evaluable")
        self.assertFalse(template["evaluable"])
        self.assertEqual(result["shortcuts"]["provenance"]["predictor_type"], "metadata")

    def test_unfrozen_evaluation_view_set_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._config()
            config["evaluation_views"] = ["problem_only"]
            with self.assertRaisesRegex(Lab03Error, "evaluation_views must be exactly"):
                self._run(Path(directory), config=config)

    def test_snapshot_failure_and_boundary_violation_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._config()
            config["non_claim_boundary"]["empirical"] = True
            result = self._run(root, snapshot_status="fail", config=config)
        gates = {row["gate"]: row["status"] for row in result["gates"]}
        self.assertEqual(gates["B1"], "fail")
        self.assertEqual(gates["B8"], "fail")

    def test_malformed_jsonl_raises(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cases.jsonl").write_text("not-json\n", encoding="utf-8")
            self._write_json(root / "snapshot.json", self._snapshot())
            self._write_json(root / "config.json", self._config())
            with self.assertRaises(Lab03Error):
                run_behavioral_baselines(root / "cases.jsonl", root / "snapshot.json", root / "config.json")

    def test_report_is_deterministic_and_prominent_about_no_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = self._run(root, snapshot_status="fail")
            first_html = root / "first/report.html"
            first_json = root / "first/summary.json"
            second_html = root / "second/report.html"
            second_json = root / "second/summary.json"
            first = build_lab03_report(baseline, output_html=first_html, output_summary=first_json)
            second = build_lab03_report(baseline, output_html=second_html, output_summary=second_json)
            self.assertEqual(first, second)
            self.assertEqual(first_html.read_bytes(), second_html.read_bytes())
            self.assertIn("No Latent TRIZ claim", first_html.read_text(encoding="utf-8"))
            self.assertIn("Provenance shortcut diagnostics", first_html.read_text(encoding="utf-8"))
            self.assertEqual(first["shortcuts"], baseline["shortcuts"])
            self.assertFalse(first["empirical"])
            self.assertFalse(first["evidence_eligible"])
            self.assertEqual(first["claim_ids"], [])


if __name__ == "__main__":
    unittest.main()
