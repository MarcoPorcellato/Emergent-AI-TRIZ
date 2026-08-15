from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0r2_report import A0R2ReportError, _primary_payload, generate_a0r2_report, verify_a0r2_publication
from latent_triz.validator import validate


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = json.loads((ROOT / "experiments/a0r2-independent-model/study-protocol.json").read_text(encoding="utf-8"))
PROTOCOL_HASH = hashlib.sha256((ROOT / "experiments/a0r2-independent-model/study-protocol.json").read_bytes()).hexdigest()
ACTIVATION_SCHEMA = json.loads((ROOT / "schemas/a0r2-activation-receipt.schema.json").read_text(encoding="utf-8"))
STATISTICAL_SCHEMA = json.loads((ROOT / "schemas/a0r2-statistical-result.schema.json").read_text(encoding="utf-8"))
FAILURE_SCHEMA = json.loads((ROOT / "schemas/a0r2-run-failure.schema.json").read_text(encoding="utf-8"))
PUBLICATION_SCHEMA = json.loads((ROOT / "schemas/a0r2-publication-manifest.schema.json").read_text(encoding="utf-8"))


def _json_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class A0R2ReportTests(unittest.TestCase):
    @staticmethod
    def _model_payload() -> dict:
        model = copy.deepcopy(PROTOCOL["model"])
        model.pop("integrity_receipt_sha256", None)
        model.pop("feasibility_receipt_sha256", None)
        return model

    def _fixture_paths(self, *, with_dense: bool = True) -> tuple[Path, Path, Path]:
        workspace = Path(tempfile.mkdtemp(prefix="a0r2-report-"))
        package = workspace / "results" / "a0r2" / "a0r2-report-run"
        dense_dir = workspace / "artifacts" / "a0r2" / "a0r2-report-run"
        package.mkdir(parents=True, exist_ok=True)
        if with_dense:
            dense_dir.mkdir(parents=True, exist_ok=True)
        return workspace, package, dense_dir

    def _write_activation_receipt(self, package: Path, dense_locator: str, index_hash: str, dense_hash: str) -> dict:
        activation = {
            "artifact_class": "a0r2-activation-receipt",
            "status": "pass",
            "created_at": "2026-08-15T19:00:00Z",
            "scientific_status": "exploratory",
            "empirical": True,
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "protocol_id": PROTOCOL["protocol_id"],
            "model": self._model_payload(),
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
                "protocol_sha256": PROTOCOL_HASH,
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
                "reports": ["activation-receipt.json"],
                "dense_locator": dense_locator,
                "exact_head": "1" * 40,
                "artifact_hashes": {
                    "summary_sha256": _json_hash({"summary": dense_locator}),
                    "index_sha256": index_hash,
                    "dense_sha256": dense_hash,
                },
                "records": 1920,
                "hidden_size": 960,
            },
        }
        receipt_path = package / "activation-receipt.json"
        receipt_path.write_text(json.dumps(activation, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        return activation

    def _write_statistical_result(
        self,
        package: Path,
        *,
        status: str,
        activation_hash: str,
        index_hash: str,
        dense_hash: str,
        dense_locator: str,
    ) -> dict:
        primary_endpoint = {
            "tuple_index": 32,
            "primary_semantics": "final_transformer_block_output",
            "token_site": "mean_transformation_span",
            "primary_view": "problem_plus_transformation",
            "surface_baseline_view": "problem_only",
            "surface_baseline_token_site": "sentinel",
        }
        statistics = {
            "primary_permutation_p": 0.04,
            "macro_f1_margin_over_surface": 0.12,
            "family_successes": 17,
            "successful_domain_directions": 4,
        }
        descriptive_primary = {
            "family_successes": 17,
            "family_success_rate": 0.68,
            "macro_f1": 0.74,
            "scores": [0.62, 0.71, 0.74],
            "per_domain_accuracy": {"smoke": 0.73, "toy": 0.75},
            "domain_direction_successes": {"smoke": 4, "toy": 3},
            "family_outcomes": {"fam-1": "success"},
        }
        descriptive_surface = {
            "family_successes": 11,
            "family_success_rate": 0.44,
            "macro_f1": 0.61,
            "scores": [0.52, 0.57, 0.61],
            "per_domain_accuracy": {"smoke": 0.61, "toy": 0.63},
            "domain_direction_successes": {"smoke": 2, "toy": 2},
            "family_outcomes": {"fam-1": "baseline"},
        }
        result = {
            "artifact_class": "a0r2-statistical-result",
            "status": status,
            "created_at": "2026-08-15T19:05:00Z",
            "scientific_status": "exploratory",
            "empirical": True,
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "protocol_id": PROTOCOL["protocol_id"],
            "model": self._model_payload(),
            "runtime": {
                "device": "cpu",
                "torch_dtype": "float32",
                "network_access": False,
                "local_files_only": True,
                "generation": False,
                "fast_offsets_required": True,
            },
            "primary_endpoint": primary_endpoint,
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
            "statistics": statistics,
            "descriptive_results": {
                "interpretation": "descriptive_only",
                "may_replace_primary": False,
                "primary": descriptive_primary,
                "surface_baseline": descriptive_surface,
                "sensitivity": {
                    "tuple_32": {
                        "combos": {
                            "primary": descriptive_primary,
                        },
                        "paired_direction_delta_mean": 0.05,
                        "rescues_primary": False,
                    }
                },
                "cross_model": {
                    "interpretation": "descriptive_only",
                    "may_affect_primary": False,
                    "case_order": "lexicographic_case_id_shared_with_r1",
                    "case_count": 48,
                    "pearson_score_correlation": 0.5,
                    "spearman_score_correlation": 0.4,
                    "score_sign_agreement": 0.75,
                    "family_outcome_agreement": 0.7,
                    "domain_direction_sign_agreement": 0.8,
                },
            },
            "input_hashes": {
                "protocol_sha256": PROTOCOL_HASH,
                "integrity_receipt_sha256": "4" * 64,
                "feasibility_receipt_sha256": "5" * 64,
                "activation_receipt_sha256": activation_hash,
                "representation_index_sha256": index_hash,
                "dense_vectors_sha256": dense_hash,
                "sealed_targets_sha256": "9" * 64,
                "r1_protocol_sha256": "a" * 64,
                "r1_freeze_manifest_sha256": "b" * 64,
                "corpus_manifest_sha256": "c" * 64,
                "cases_sha256": "d" * 64,
                "shortcuts_sha256": "e" * 64,
                "r1_result_sha256": "a2ad1ed0148a332fe85cb42ee2f3295e042d277d772353ebd84ccd2e255a6738",
            },
            "artifact_hashes": {
                "primary_sha256": _json_hash(descriptive_primary),
                "statistics_sha256": _json_hash(statistics),
            },
            "access": {
                "model_loaded": True,
                "model_output_accessed": True,
                "sealed_targets_accessed": True,
                "claim_promotion": False,
            },
            "result_bundle": {
                "reports": ["report.md"],
                "dense_locator": dense_locator,
                "dense_locator_sha256": _json_hash({"dense_locator": dense_locator}),
                "exact_head": "1" * 40,
            },
        }
        result_path = package / "statistical-result.json"
        result_path.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        return result

    def _write_failure_result(self, package: Path) -> dict:
        failure = {
            "artifact_class": "a0r2-run-failure",
            "status": "failed",
            "created_at": "2026-08-15T19:10:00Z",
            "scientific_status": "exploratory",
            "empirical": True,
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "protocol_id": PROTOCOL["protocol_id"],
            "model": self._model_payload(),
            "failure": {
                "stage": "execution",
                "failure_kind": "runtime_error",
                "failure_digest": "c" * 64,
            },
            "access": {
                "model_loaded": True,
                "model_output_accessed": "not_accessed",
                "sealed_targets_accessed": "not_accessed",
                "claim_promotion": False,
            },
            "reports": ["report.md"],
        }
        result_path = package / "run-failure.json"
        result_path.write_text(json.dumps(failure, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        return failure

    def test_primary_payload_prefers_descriptive_results(self) -> None:
        payload = {
            "primary_endpoint": {"tuple_index": 32},
            "descriptive_results": {"primary": {"tuple_index": 11, "surface": "preferred"}},
        }
        self.assertEqual({"tuple_index": 11, "surface": "preferred"}, _primary_payload(payload))

    def _write_index(self, package: Path) -> Path:
        index_path = package / "representations-index.jsonl"
        row = {
            "record_id": "case-1::problem_plus_transformation::mean_transformation_span::32",
            "case_id": "case-1",
            "problem_family_id": "fam-1",
            "domain": "smoke",
            "view": "problem_plus_transformation",
            "token_site": "mean_transformation_span",
            "tuple_index": 32,
            "hidden_size": 960,
            "dtype": "float32",
            "vector_sha256": "d" * 64,
            "token_count": 3,
        }
        index_path.write_text(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        return index_path

    def _write_dense(self, dense_dir: Path) -> Path:
        dense_path = dense_dir / "activations.json"
        dense_path.write_bytes(b'{"synthetic":true}\n')
        return dense_path

    def _assemble_fixture(self, *, status: str) -> tuple[Path, Path, Path, dict]:
        if status == "failed":
            workspace, package, dense_dir = self._fixture_paths(with_dense=False)
            activation = None
            result = self._write_failure_result(package)
        else:
            workspace, package, dense_dir = self._fixture_paths(with_dense=True)
            dense_locator = f"artifacts/a0r2/{package.name}/activations.json"
            dense_path = self._write_dense(dense_dir)
            dense_hash = hashlib.sha256(dense_path.read_bytes()).hexdigest()
            index_path = self._write_index(package)
            index_hash = hashlib.sha256(index_path.read_bytes()).hexdigest()
            activation = self._write_activation_receipt(package, dense_locator, index_hash, dense_hash)
            activation_hash = hashlib.sha256((package / "activation-receipt.json").read_bytes()).hexdigest()
            result = self._write_statistical_result(
                package,
                status=status,
                activation_hash=activation_hash,
                index_hash=index_hash,
                dense_hash=dense_hash,
                dense_locator=dense_locator,
            )
        return workspace, package, dense_dir, {"activation": activation, "result": result}

    def test_generate_and_verify_accept_every_terminal_status(self) -> None:
        for status in ("positive", "null", "non_interpretable", "incompatible", "failed"):
            with self.subTest(status=status):
                workspace, package, dense_dir, _payloads = self._assemble_fixture(status=status)
                old_cwd = os.getcwd()
                os.chdir(workspace)
                try:
                    report_path, manifest_path = generate_a0r2_report(
                        package_dir=Path("results") / "a0r2" / package.name,
                        external_dense_dir=Path("artifacts") / "a0r2" / package.name,
                        created_at="2026-08-15T20:00:00Z",
                    )
                    self.assertTrue(report_path.is_file())
                    self.assertTrue(manifest_path.is_file())
                    report_text = report_path.read_text(encoding="utf-8")
                    self.assertIn("Automated exploratory E0".lower(), report_text.lower())
                    self.assertIn("no human or expert validation", report_text.lower())
                    self.assertIn("Null and failed outcomes are published equally", report_text)
                    self.assertIn("does not claim TRIZ rediscovery", report_text)
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    self.assertEqual([], validate(manifest, PUBLICATION_SCHEMA))
                    self.assertEqual(status, manifest["terminal_status"])
                    if status == "failed":
                        self.assertIn("Failure summary", report_text)
                        self.assertNotIn("Activation bundle", report_text)
                        self.assertNotIn("receipt", manifest)
                        self.assertNotIn("index", manifest)
                        self.assertNotIn("dense", manifest)
                    else:
                        self.assertIn("Activation bundle", report_text)
                        self.assertIn("External dense bytes", report_text)
                        self.assertIn("receipt", manifest)
                        self.assertIn("index", manifest)
                        self.assertIn("dense", manifest)
                    verified = verify_a0r2_publication(
                        package_dir=Path("results") / "a0r2" / package.name,
                        external_dense_dir=Path("artifacts") / "a0r2" / package.name,
                    )
                    self.assertEqual(status, verified["terminal_status"])
                finally:
                    os.chdir(old_cwd)

    def test_generate_rejects_status_mismatch_for_statistical_result(self) -> None:
        workspace, package, dense_dir, _payloads = self._assemble_fixture(status="positive")
        payload = json.loads((package / "statistical-result.json").read_text(encoding="utf-8"))
        payload["status"] = "failed"
        (package / "statistical-result.json").write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        old_cwd = os.getcwd()
        os.chdir(workspace)
        try:
            with self.assertRaisesRegex(A0R2ReportError, "status mismatch"):
                generate_a0r2_report(
                    package_dir=Path("results") / "a0r2" / package.name,
                    external_dense_dir=Path("artifacts") / "a0r2" / package.name,
                    created_at="2026-08-15T20:00:00Z",
                )
        finally:
            os.chdir(old_cwd)

    def test_generate_rejects_overwrite_and_traversal(self) -> None:
        workspace, package, dense_dir, _payloads = self._assemble_fixture(status="positive")
        old_cwd = os.getcwd()
        os.chdir(workspace)
        try:
            (package / "report.md").write_text("existing\n", encoding="utf-8")
            with self.assertRaisesRegex(A0R2ReportError, "refuse overwrite"):
                generate_a0r2_report(
                    package_dir=Path("results") / "a0r2" / package.name,
                    external_dense_dir=Path("artifacts") / "a0r2" / package.name,
                    created_at="2026-08-15T20:00:00Z",
                )
        finally:
            os.chdir(old_cwd)

        with self.assertRaisesRegex(A0R2ReportError, "relative path"):
            generate_a0r2_report(
                package_dir=package.resolve(),
                external_dense_dir=Path("artifacts") / "a0r2" / package.name,
                created_at="2026-08-15T20:00:00Z",
            )

    def test_generate_rejects_missing_or_tampered_dense(self) -> None:
        workspace, package, dense_dir, _payloads = self._assemble_fixture(status="positive")
        (dense_dir / "activations.json").unlink()
        old_cwd = os.getcwd()
        os.chdir(workspace)
        try:
            with self.assertRaisesRegex(A0R2ReportError, "missing dense artifact"):
                generate_a0r2_report(
                    package_dir=Path("results") / "a0r2" / package.name,
                    external_dense_dir=Path("artifacts") / "a0r2" / package.name,
                    created_at="2026-08-15T20:00:00Z",
                )
        finally:
            os.chdir(old_cwd)

    def test_verify_does_not_touch_model_or_sealed_targets(self) -> None:
        workspace, package, dense_dir, _payloads = self._assemble_fixture(status="positive")
        old_cwd = os.getcwd()
        os.chdir(workspace)
        try:
            generate_a0r2_report(
                package_dir=Path("results") / "a0r2" / package.name,
                external_dense_dir=Path("artifacts") / "a0r2" / package.name,
                created_at="2026-08-15T20:00:00Z",
            )
            allowed_paths = {
                str(Path("results") / "a0r2" / package.name / "statistical-result.json"),
                str(Path("results") / "a0r2" / package.name / "activation-receipt.json"),
                str(Path("results") / "a0r2" / package.name / "representations-index.jsonl"),
                str(Path("results") / "a0r2" / package.name / "report.md"),
                str(Path("results") / "a0r2" / package.name / "publication-manifest.json"),
                str(Path("artifacts") / "a0r2" / package.name / "activations.json"),
                str(ROOT / "experiments/a0r2-independent-model/study-protocol.json"),
                str(ROOT / "schemas/a0r2-study-protocol.schema.json"),
                str(ROOT / "schemas/a0r2-statistical-result.schema.json"),
                str(ROOT / "schemas/a0r2-run-failure.schema.json"),
                str(ROOT / "schemas/a0r2-activation-receipt.schema.json"),
                str(ROOT / "schemas/a0r2-publication-manifest.schema.json"),
            }
            original_read_text = Path.read_text
            original_read_bytes = Path.read_bytes

            def safe_read_text(self: Path, *args, **kwargs):  # type: ignore[override]
                if str(self) not in allowed_paths:
                    raise A0R2ReportError(f"unexpected read_text path: {self}")
                return original_read_text(self, *args, **kwargs)

            def safe_read_bytes(self: Path, *args, **kwargs):  # type: ignore[override]
                if str(self) not in allowed_paths:
                    raise A0R2ReportError(f"unexpected read_bytes path: {self}")
                return original_read_bytes(self, *args, **kwargs)

            with patch.object(Path, "read_text", safe_read_text), patch.object(Path, "read_bytes", safe_read_bytes):
                verified = verify_a0r2_publication(
                    package_dir=Path("results") / "a0r2" / package.name,
                    external_dense_dir=Path("artifacts") / "a0r2" / package.name,
                )
                self.assertEqual("positive", verified["terminal_status"])
        finally:
            os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
