from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz import a0r2_runner as runner
from latent_triz.validator import validate


class A0R2RunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = ROOT
        self.failure_schema = json.loads((self.root / "schemas/a0r2-run-failure.schema.json").read_text(encoding="utf-8"))
        authorization_patch = patch.object(
            runner, "verify_a0r2_sealed_execution_authorization", return_value={"status": "pass"}
        )
        authorization_patch.start()
        self.addCleanup(authorization_patch.stop)

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    def _fixture(self, tmp: Path, *, shortcut_status: str = "pass") -> dict[str, Path]:
        run_id = "a0r2-run"
        activation_dir = tmp / "artifacts" / "a0r2" / run_id
        package_dir = tmp / "results" / "a0r2" / run_id
        shortcut_path = tmp / "results" / "a0r1" / "preoutput" / "shortcuts.json"
        schema_dir = tmp / "schemas"
        shortcuts = {"artifact_class": "a0r2-shortcut-audit", "status": shortcut_status}
        self._write_json(shortcut_path, shortcuts)
        schema_dir.mkdir(parents=True, exist_ok=True)
        (schema_dir / "a0r2-run-failure.schema.json").write_text(
            (self.root / "schemas" / "a0r2-run-failure.schema.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        target_dir = tmp / "data" / "a0r1"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / "sealed_targets.jsonl"
        target_path.write_text(
            json.dumps(
                {
                    "case_id": "case-1",
                    "domain": "alpha",
                    "problem_family_id": "fam-1",
                    "operator_proxy_family": "segmentation_like",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        self._write_json(
            target_dir / "manifest.json",
            {
                "files": {
                    "sealed_targets_jsonl": {
                        "path": "sealed_targets.jsonl",
                        "sha256": "0" * 64,
                    }
                }
            },
        )

        model_root = tmp / "models" / "smollm2-360m-f8027fd0"
        model_root.mkdir(parents=True, exist_ok=True)
        self._write_json(
            tmp / runner.PROTOCOL_PATH,
            {
                "resource_envelope": {
                    "maximum_peak_rss_bytes": 8589934592,
                    "maximum_wall_seconds": 1800,
                    "maximum_new_dense_output_bytes": 67108864,
                }
            },
        )
        return {
            "run_id": Path(run_id),
            "activation_dir": activation_dir,
            "package_dir": package_dir,
            "shortcut_path": shortcut_path,
            "target_path": target_path,
            "model_root": model_root,
        }

    def _write_activation_artifacts(self, activation_dir: Path) -> SimpleNamespace:
        activation_dir.mkdir(parents=True, exist_ok=True)
        dense_path = activation_dir / "activations.json"
        index_path = activation_dir / "representations-index.jsonl"
        summary_path = activation_dir / "activation-summary.json"
        receipt_path = activation_dir / "activation-receipt.json"

        dense_path.write_text("{\"dense\":true}\n", encoding="utf-8")
        index_path.write_text("{\"record_id\":\"r-1\"}\n", encoding="utf-8")
        summary_path.write_text("{\"summary\":true}\n", encoding="utf-8")
        receipt_path.write_text(
            json.dumps(
                {
                    "artifact_class": "a0r2-activation-receipt",
                    "status": "pass",
                    "created_at": "2026-08-15T19:00:00Z",
                    "scientific_status": "exploratory",
                    "empirical": True,
                    "evidence_eligible": False,
                    "expert_validated": False,
                    "claim_ids": [],
                    "protocol_id": "a0r2-independent-model-v1.0.0",
                    "model": dict(runner._MODEL),
                    "runtime": {
                        "device": "cpu",
                        "torch_dtype": "float32",
                        "network_access": False,
                        "local_files_only": True,
                        "generation": False,
                        "fast_offsets_required": True,
                    },
                    "activation": {
                        "tuple_index": 32,
                        "primary_semantics": "final_transformer_block_output",
                        "token_site": "mean_transformation_span",
                        "primary_view": "problem_plus_transformation",
                        "surface_baseline_view": "problem_only",
                        "surface_baseline_token_site": "sentinel",
                        "hidden_states_count": 33,
                        "hidden_size": 960,
                        "output_content_retained": True,
                    },
                    "access": {
                        "model_loaded": True,
                        "model_output_accessed": True,
                        "sealed_targets_accessed": False,
                        "claim_promotion": False,
                    },
                    "input_hashes": {
                        "protocol_sha256": "a" * 64,
                        "r1_protocol_sha256": "b" * 64,
                        "r1_freeze_manifest_sha256": "c" * 64,
                        "corpus_manifest_sha256": "d" * 64,
                        "cases_sha256": "e" * 64,
                        "sealed_targets_sha256": "f" * 64,
                        "shortcuts_sha256": "1" * 64,
                        "integrity_receipt_sha256": "2" * 64,
                        "feasibility_receipt_sha256": "3" * 64,
                    },
                    "output_bundle": {
                        "reports": [
                            "activation-receipt.json",
                            "activation-summary.json",
                            "representations-index.jsonl",
                        ],
                        "dense_locator": f"artifacts/a0r2/{activation_dir.name}/activations.json",
                        "artifact_hashes": {
                            "summary_sha256": "1" * 64,
                            "index_sha256": "2" * 64,
                            "dense_sha256": "3" * 64,
                        },
                        "records": 1920,
                        "hidden_size": 960,
                        "exact_head": "4" * 40,
                    },
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return SimpleNamespace(
            dense_path=dense_path,
            index_path=index_path,
            summary_path=summary_path,
            receipt_path=receipt_path,
        )

    @staticmethod
    def _write_result_artifact(package_dir: Path) -> Path:
        result_path = package_dir / runner.RESULT_STATISTICAL_FILE
        result_path.write_text(
            json.dumps(
                {
                    "artifact_class": "a0r2-statistical-result",
                    "status": "positive",
                    "created_at": "2026-08-15T19:05:00Z",
                    "scientific_status": "exploratory",
                    "empirical": True,
                    "evidence_eligible": False,
                    "expert_validated": False,
                    "claim_ids": [],
                    "protocol_id": "a0r2-independent-model-v1.0.0",
                    "model": dict(runner._MODEL),
                    "runtime": {
                        "device": "cpu",
                        "torch_dtype": "float32",
                        "network_access": False,
                        "local_files_only": True,
                        "generation": False,
                        "fast_offsets_required": True,
                    },
                    "primary_endpoint": {
                        "tuple_index": 32,
                        "primary_semantics": "final_transformer_block_output",
                        "token_site": "mean_transformation_span",
                        "primary_view": "problem_plus_transformation",
                        "surface_baseline_view": "problem_only",
                        "surface_baseline_token_site": "sentinel",
                    },
                    "sensitivity_endpoints": {
                        "tuple_indices": [0, 11, 21, 32],
                        "token_sites": ["sentinel", "final_transformation_token", "mean_transformation_span"],
                        "views": ["problem_only", "transformation_only", "problem_plus_transformation", "problem_plus_solution"],
                        "descriptive_only": True,
                        "may_replace_primary": False,
                    },
                    "controls": {
                        "negative_controls": [
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
                        ],
                        "shortcut_refusal": {
                            "predictive_control_scope": "aggregate",
                            "macro_f1_at_or_above": 0.65,
                            "margin_over_majority_at_or_above": 0.1,
                            "predictive_rule": "non_interpretable_if_both_thresholds_reached",
                            "structural_rule": "non_interpretable_if_any_required_control_status_is_not_pass",
                            "required_control_count": 14,
                        },
                    },
                    "statistics": {
                        "primary_permutation_p": 0.04,
                        "macro_f1_margin_over_surface": 0.12,
                        "family_successes": 17,
                        "successful_domain_directions": 4,
                    },
                    "input_hashes": {
                        "protocol_sha256": "3" * 64,
                        "integrity_receipt_sha256": "4" * 64,
                        "feasibility_receipt_sha256": "5" * 64,
                        "activation_receipt_sha256": "6" * 64,
                        "representation_index_sha256": "7" * 64,
                        "dense_vectors_sha256": "8" * 64,
                        "sealed_targets_sha256": "9" * 64,
                    },
                    "artifact_hashes": {
                        "primary_sha256": "a" * 64,
                        "statistics_sha256": "b" * 64,
                    },
                    "access": {
                        "model_loaded": True,
                        "model_output_accessed": True,
                        "sealed_targets_accessed": True,
                        "claim_promotion": False,
                    },
                    "result_bundle": {
                        "reports": [runner.REPORT_FILE],
                        "dense_locator": "artifacts/a0r2/a0r2-run/activations.json",
                        "dense_locator_sha256": "0" * 64,
                        "exact_head": "1" * 40,
                    },
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return result_path

    def _write_publication_artifacts(self, package_dir: Path, dense_locator: str) -> tuple[Path, Path]:
        report_path = package_dir / runner.REPORT_FILE
        manifest_path = package_dir / runner.MANIFEST_FILE
        report_path.write_text("# report\n", encoding="utf-8")
        manifest_path.write_text(
            json.dumps(
                {
                    "artifact_class": "a0r2-publication-manifest",
                    "created_at": "2026-08-15T19:15:00Z",
                    "protocol_id": "a0r2-independent-model-v1.0.0",
                    "status": "positive",
                    "scientific_status": "exploratory",
                    "empirical": True,
                    "evidence_eligible": False,
                    "expert_validated": False,
                    "claim_ids": [],
                    "terminal_status": "positive",
                    "publication": {
                        "publish_every_terminal_outcome": True,
                        "sensitivity_may_rescue_primary": False,
                        "model_substitution_after_output": False,
                        "claim_promotion": False,
                    },
                    "result": {"path": runner.RESULT_STATISTICAL_FILE, "sha256": "5" * 64},
                    "receipt": {"path": runner.ACTIVATION_RECEIPT_FILE, "sha256": "6" * 64},
                    "index": {"path": runner.REPRESENTATION_INDEX_FILE, "sha256": "7" * 64},
                    "report": {"path": runner.REPORT_FILE, "sha256": "8" * 64},
                    "dense": {
                        "path": dense_locator,
                        "sha256": "9" * 64,
                        "records": 1920,
                        "hidden_size": 960,
                    },
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return report_path, manifest_path

    def test_all_stage_orders_activate_analyze_report_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(root)
            calls: list[str] = []

            def contract_stub(*_args, **_kwargs):
                calls.append("contract")
                self.assertEqual(fixture["model_root"].resolve(), Path(_kwargs["model_root"]).resolve())
                return {"status": "pass"}

            def activation_stub(*_args, **kwargs):
                calls.append("activate")
                self.assertEqual(fixture["model_root"].resolve(), Path(kwargs["model_root"]).resolve())
                return self._write_activation_artifacts(Path(kwargs["output_dir"]).resolve())

            def analyze_stub(*_args, **kwargs):
                calls.append("analyze")
                self.assertEqual(fixture["target_path"].resolve(), Path(kwargs["targets_path"]).resolve())
                self.assertEqual(fixture["shortcut_path"].resolve(), Path(kwargs["shortcut_path"]).resolve())
                self._write_result_artifact(Path(kwargs["output_path"]).resolve().parent)

            def report_stub(*_args, **kwargs):
                calls.append("report")
                return self._write_publication_artifacts(
                    (root / "results" / "a0r2" / fixture["run_id"].name).resolve(),
                    f"artifacts/a0r2/{fixture['run_id'].name}/activations.json",
                )

            def verify_stub(*_args, **_kwargs):
                calls.append("verify")
                return {"status": "verified"}

            with (
                patch.object(runner, "verify_a0r2_execution_contract", side_effect=contract_stub),
                patch.object(runner, "run_a0r2_activations", side_effect=activation_stub),
                patch.object(runner, "analyze_a0r2", side_effect=analyze_stub),
                patch.object(runner, "generate_a0r2_report", side_effect=report_stub),
                patch.object(runner, "verify_a0r2_publication", side_effect=verify_stub),
            ):
                status = runner.main(
                    [
                        "--root",
                        str(root),
                        "--run-id",
                        fixture["run_id"].name,
                        "--created-at",
                        "2026-08-15T19:00:00Z",
                        "--model-root",
                        str(fixture["model_root"]),
                        "--stage",
                        "all",
                    ]
                )

            self.assertEqual(0, status)
            self.assertEqual(["contract", "activate", "analyze", "report", "verify"], calls)
            self.assertTrue((root / "results" / "a0r2" / fixture["run_id"].name / runner.ACTIVATION_RECEIPT_FILE).is_file())
            self.assertTrue((root / "results" / "a0r2" / fixture["run_id"].name / runner.REPRESENTATION_INDEX_FILE).is_file())
            self.assertTrue((root / "results" / "a0r2" / fixture["run_id"].name / runner.RESULT_STATISTICAL_FILE).is_file())
            self.assertTrue((root / "results" / "a0r2" / fixture["run_id"].name / runner.REPORT_FILE).is_file())

    def test_shortcut_preflight_failure_skips_activation_and_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(root, shortcut_status="failed")

            with (
                patch.object(runner, "verify_a0r2_execution_contract", return_value={"status": "pass"}),
                patch.object(runner, "run_a0r2_activations") as mock_activation,
                patch.object(runner, "analyze_a0r2") as mock_analyze,
                patch.object(runner, "generate_a0r2_report") as mock_report,
                patch.object(runner, "verify_a0r2_publication") as mock_verify,
                patch.object(runner, "_discover_targets_path") as mock_targets,
            ):
                status = runner.main(
                    [
                        "--root",
                        str(root),
                        "--run-id",
                        fixture["run_id"].name,
                        "--created-at",
                        "2026-08-15T19:00:00Z",
                        "--model-root",
                        str(fixture["model_root"]),
                        "--stage",
                        "all",
                    ]
                )

            self.assertNotEqual(0, status)
            mock_activation.assert_not_called()
            mock_analyze.assert_not_called()
            mock_report.assert_called_once()
            mock_verify.assert_called_once()
            mock_targets.assert_not_called()
            failure = json.loads((root / "results" / "a0r2" / fixture["run_id"].name / runner.RESULT_FAILURE_FILE).read_text(encoding="utf-8"))
            self.assertEqual([], validate(failure, self.failure_schema))
            self.assertEqual("compatibility", failure["failure"]["stage"])
            self.assertEqual("not_accessed", failure["access"]["model_output_accessed"])
            self.assertEqual("not_accessed", failure["access"]["sealed_targets_accessed"])

    def test_authorization_failure_skips_contract_activation_and_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(root)
            with (
                patch.object(
                    runner,
                    "verify_a0r2_sealed_execution_authorization",
                    side_effect=RuntimeError("authorization absent"),
                ),
                patch.object(runner, "verify_a0r2_execution_contract") as mock_contract,
                patch.object(runner, "run_a0r2_activations") as mock_activation,
                patch.object(runner, "_discover_targets_path") as mock_targets,
            ):
                status = runner.main(
                    [
                        "--root", str(root), "--run-id", fixture["run_id"].name,
                        "--created-at", "2026-08-15T19:00:00Z",
                        "--model-root", str(fixture["model_root"]), "--stage", "activate",
                    ]
                )

            self.assertNotEqual(0, status)
            mock_contract.assert_not_called()
            mock_activation.assert_not_called()
            mock_targets.assert_not_called()

    def test_activation_failure_reports_possibly_accessed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(root)

            def activation_stub(*_args, **_kwargs):
                raise RuntimeError("activation boom")

            with (
                patch.object(runner, "verify_a0r2_execution_contract", return_value={"status": "pass"}),
                patch.object(runner, "run_a0r2_activations", side_effect=activation_stub),
            ):
                status = runner.main(
                    [
                        "--root",
                        str(root),
                        "--run-id",
                        fixture["run_id"].name,
                        "--created-at",
                        "2026-08-15T19:00:00Z",
                        "--model-root",
                        str(fixture["model_root"]),
                        "--stage",
                        "activate",
                    ]
                )

            self.assertNotEqual(0, status)
            failure = json.loads((root / "results" / "a0r2" / fixture["run_id"].name / runner.RESULT_FAILURE_FILE).read_text(encoding="utf-8"))
            self.assertEqual([], validate(failure, self.failure_schema))
            self.assertEqual("execution", failure["failure"]["stage"])
            self.assertEqual("possibly_accessed", failure["access"]["model_output_accessed"])
            self.assertEqual("not_accessed", failure["access"]["sealed_targets_accessed"])

    def test_resource_envelope_violation_is_terminal_incompatible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(root)
            self._write_activation_artifacts(fixture["activation_dir"])
            with patch.object(runner, "_peak_rss_bytes", return_value=8589934593):
                with self.assertRaisesRegex(runner.A0R2IncompatibleError, "peak-RSS"):
                    runner._enforce_resource_envelope(root, runner._artifacts(root, fixture["run_id"].name), started_at=runner.time.monotonic())
            payload = runner._failure_payload(
                stage="execution",
                created_at="2026-08-15T19:00:00Z",
                exc=runner.A0R2IncompatibleError("peak-RSS envelope exceeded"),
            )
            self.assertEqual("incompatible", payload["status"])
            self.assertEqual([], validate(payload, self.failure_schema))

    def test_compatibility_failure_attempts_failure_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(root, shortcut_status="failed")
            report_calls: list[str] = []

            def report_stub(*_args, **kwargs):
                report_calls.append("report")
                return self._write_publication_artifacts(
                    (root / "results" / "a0r2" / fixture["run_id"].name).resolve(),
                    f"artifacts/a0r2/{fixture['run_id'].name}/activations.json",
                )

            def verify_stub(*_args, **_kwargs):
                report_calls.append("verify")
                return {"status": "verified"}

            with (
                patch.object(runner, "verify_a0r2_execution_contract", return_value={"status": "pass"}),
                patch.object(runner, "generate_a0r2_report", side_effect=report_stub),
                patch.object(runner, "verify_a0r2_publication", side_effect=verify_stub),
            ):
                status = runner.main(
                    [
                        "--root",
                        str(root),
                        "--run-id",
                        fixture["run_id"].name,
                        "--created-at",
                        "2026-08-15T19:00:00Z",
                        "--model-root",
                        str(fixture["model_root"]),
                        "--stage",
                        "activate",
                    ]
                )

            self.assertNotEqual(0, status)
            self.assertEqual(["report", "verify"], report_calls)
            failure = json.loads((root / "results" / "a0r2" / fixture["run_id"].name / runner.RESULT_FAILURE_FILE).read_text(encoding="utf-8"))
            self.assertEqual([], validate(failure, self.failure_schema))
            self.assertEqual("compatibility", failure["failure"]["stage"])
            self.assertFalse(failure["access"]["model_loaded"])

    def test_analysis_failure_discovers_targets_only_at_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(root)
            activation_calls = 0
            target_calls = 0
            original_targets = runner._discover_targets_path

            def activation_stub(*_args, **kwargs):
                nonlocal activation_calls
                activation_calls += 1
                return self._write_activation_artifacts(Path(kwargs["output_dir"]).resolve())

            def targets_stub(root_path: Path):
                nonlocal target_calls
                target_calls += 1
                return original_targets(root_path)

            def analyze_stub(*_args, **kwargs):
                self.assertEqual(fixture["target_path"].resolve(), Path(kwargs["targets_path"]).resolve())
                raise RuntimeError("analysis boom")

            with (
                patch.object(runner, "verify_a0r2_execution_contract", return_value={"status": "pass"}),
                patch.object(runner, "run_a0r2_activations", side_effect=activation_stub),
                patch.object(runner, "_discover_targets_path", side_effect=targets_stub),
                patch.object(runner, "analyze_a0r2", side_effect=analyze_stub),
            ):
                status = runner.main(
                    [
                        "--root",
                        str(root),
                        "--run-id",
                        fixture["run_id"].name,
                        "--created-at",
                        "2026-08-15T19:00:00Z",
                        "--model-root",
                        str(fixture["model_root"]),
                        "--stage",
                        "all",
                    ]
                )

            self.assertNotEqual(0, status)
            self.assertEqual(1, activation_calls)
            self.assertEqual(1, target_calls)
            failure = json.loads((root / "results" / "a0r2" / fixture["run_id"].name / runner.RESULT_FAILURE_FILE).read_text(encoding="utf-8"))
            self.assertEqual([], validate(failure, self.failure_schema))
            self.assertEqual("data", failure["failure"]["stage"])
            self.assertEqual("possibly_accessed", failure["access"]["model_output_accessed"])
            self.assertEqual("possibly_accessed", failure["access"]["sealed_targets_accessed"])

    def test_verify_stage_does_not_call_model_or_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._fixture(root)
            self._write_activation_artifacts(fixture["activation_dir"])
            package_dir = fixture["package_dir"]
            package_dir.mkdir(parents=True, exist_ok=True)
            self._write_result_artifact(package_dir)
            self._write_publication_artifacts(package_dir, f"artifacts/a0r2/{fixture['run_id'].name}/activations.json")

            with (
                patch.object(runner, "verify_a0r2_execution_contract", return_value={"status": "pass"}),
                patch.object(runner, "run_a0r2_activations") as mock_activation,
                patch.object(runner, "analyze_a0r2") as mock_analyze,
                patch.object(runner, "_discover_targets_path") as mock_targets,
                patch.object(runner, "generate_a0r2_report") as mock_report,
                patch.object(runner, "verify_a0r2_publication", return_value={"status": "verified"}) as mock_verify,
            ):
                status = runner.main(
                    [
                        "--root",
                        str(root),
                        "--run-id",
                        fixture["run_id"].name,
                        "--created-at",
                        "2026-08-15T19:00:00Z",
                        "--stage",
                        "verify",
                    ]
                )

            self.assertEqual(0, status)
            mock_activation.assert_not_called()
            mock_analyze.assert_not_called()
            mock_targets.assert_not_called()
            mock_report.assert_not_called()
            mock_verify.assert_called_once()
            self.assertTrue((package_dir / runner.REPORT_FILE).is_file())
            self.assertTrue((package_dir / runner.MANIFEST_FILE).is_file())
            self.assertTrue((package_dir / runner.ACTIVATION_RECEIPT_FILE).is_file())
            self.assertTrue((package_dir / runner.REPRESENTATION_INDEX_FILE).is_file())

    def test_invalid_run_id_rejected_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._fixture(root)

            with (
                patch.object(runner, "verify_a0r2_execution_contract") as mock_contract,
                patch.object(runner, "run_a0r2_activations") as mock_activation,
            ):
                status = runner.main(
                    [
                        "--root",
                        str(root),
                        "--run-id",
                        "BadID",
                        "--created-at",
                        "2026-08-15T19:00:00Z",
                        "--model-root",
                        str(root / "models"),
                        "--stage",
                        "activate",
                    ]
                )

            self.assertNotEqual(0, status)
            mock_contract.assert_not_called()
            mock_activation.assert_not_called()
            self.assertFalse((root / "results" / "a0r2" / "BadID" / runner.RESULT_FAILURE_FILE).exists())


if __name__ == "__main__":
    unittest.main()
