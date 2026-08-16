from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.validator import validate


class A0R2OutputSchemaTests(unittest.TestCase):
    DENSE_LOCATOR = "artifacts/a0r2/sha256-43fe93262d397cfb1b26843f0c33e5cc381e876a92e2f27e2fb315a585eaa376/activations.json"

    def setUp(self) -> None:
        self.root = ROOT
        self.activation_schema = json.loads((self.root / "schemas/a0r2-activation-receipt.schema.json").read_text(encoding="utf-8"))
        self.statistics_schema = json.loads((self.root / "schemas/a0r2-statistical-result.schema.json").read_text(encoding="utf-8"))
        self.failure_schema = json.loads((self.root / "schemas/a0r2-run-failure.schema.json").read_text(encoding="utf-8"))
        self.publication_schema = json.loads((self.root / "schemas/a0r2-publication-manifest.schema.json").read_text(encoding="utf-8"))

        self.activation = {
            "artifact_class": "a0r2-activation-receipt",
            "status": "pass",
            "created_at": "2026-08-15T19:00:00Z",
            "scientific_status": "exploratory",
            "empirical": True,
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "protocol_id": "a0r2-independent-model-v1.0.0",
            "model": {
                "id": "HuggingFaceTB/SmolLM2-360M",
                "revision": "f8027fd0eaeea54caa13c31d31b9fdc459c38b49",
                "license_id": "Apache-2.0",
                "model_type": "llama",
                "architecture": "LlamaForCausalLM",
                "num_hidden_layers": 32,
                "hidden_size": 960,
                "local_locator": "artifacts/models/smollm2-360m-f8027fd0",
            },
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
                "reports": ["results/a0r2/activation/report.md"],
                "dense_locator": self.DENSE_LOCATOR,
                "artifact_hashes": {
                    "summary_sha256": "0" * 64,
                    "index_sha256": "1" * 64,
                    "dense_sha256": "2" * 64,
                },
                "records": 1920,
                "hidden_size": 960,
                "exact_head": "1" * 40,
            },
        }

        self.statistics = {
            "artifact_class": "a0r2-statistical-result",
            "status": "positive",
            "created_at": "2026-08-15T19:05:00Z",
            "scientific_status": "exploratory",
            "empirical": True,
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "protocol_id": "a0r2-independent-model-v1.0.0",
            "model": self.activation["model"],
            "runtime": self.activation["runtime"],
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
            "descriptive_results": {
                "interpretation": "descriptive_only",
                "may_replace_primary": False,
                "primary": {
                    "family_successes": 17,
                    "family_success_rate": 0.68,
                    "macro_f1": 0.74,
                    "scores": [0.62, 0.71, 0.74],
                    "per_domain_accuracy": {"smoke": 0.73, "toy": 0.75},
                    "domain_direction_successes": {"smoke": 4, "toy": 3},
                    "family_outcomes": {"fam-1": "success"},
                },
                "surface_baseline": {
                    "family_successes": 11,
                    "family_success_rate": 0.44,
                    "macro_f1": 0.61,
                    "scores": [0.52, 0.57, 0.61],
                    "per_domain_accuracy": {"smoke": 0.61, "toy": 0.63},
                    "domain_direction_successes": {"smoke": 2, "toy": 2},
                    "family_outcomes": {"fam-1": "baseline"},
                },
                "sensitivity": {
                    "tuple_32": {
                        "combos": {
                            "primary": {
                                "family_successes": 17,
                                "family_success_rate": 0.68,
                                "macro_f1": 0.74,
                                "scores": [0.62, 0.71, 0.74],
                                "per_domain_accuracy": {"smoke": 0.73},
                                "domain_direction_successes": {"smoke": 4},
                                "family_outcomes": {"fam-1": "success"},
                            }
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
                "protocol_sha256": "3" * 64,
                "integrity_receipt_sha256": "4" * 64,
                "feasibility_receipt_sha256": "5" * 64,
                "activation_receipt_sha256": "6" * 64,
                "representation_index_sha256": "7" * 64,
                "dense_vectors_sha256": "8" * 64,
                "sealed_targets_sha256": "9" * 64,
                "r1_protocol_sha256": "a" * 64,
                "r1_freeze_manifest_sha256": "b" * 64,
                "corpus_manifest_sha256": "c" * 64,
                "cases_sha256": "d" * 64,
                "shortcuts_sha256": "e" * 64,
                "r1_result_sha256": "a2ad1ed0148a332fe85cb42ee2f3295e042d277d772353ebd84ccd2e255a6738",
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
                "reports": ["results/a0r2/statistics/report.md"],
                "dense_locator": self.DENSE_LOCATOR,
                "dense_locator_sha256": "0" * 64,
                "exact_head": "1" * 40,
            },
        }

        self.failure = {
            "artifact_class": "a0r2-run-failure",
            "status": "failed",
            "created_at": "2026-08-15T19:10:00Z",
            "scientific_status": "exploratory",
            "empirical": True,
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "protocol_id": "a0r2-independent-model-v1.0.0",
            "model": self.activation["model"],
            "failure": {
                "stage": "execution",
                "failure_kind": "runtime_error",
                "failure_digest": "4" * 64,
            },
            "access": {
                "model_loaded": False,
                "model_output_accessed": "not_accessed",
                "sealed_targets_accessed": "not_accessed",
                "claim_promotion": False,
            },
            "reports": ["results/a0r2/failure/report.md"],
        }

        self.publication = {
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
            "protocol": {
                "path": "experiments/a0r2-independent-model/study-protocol.json",
                "sha256": "f" * 64,
            },
            "publication": {
                "publish_every_terminal_outcome": True,
                "sensitivity_may_rescue_primary": False,
                "model_substitution_after_output": False,
                "claim_promotion": False,
            },
            "result": {"path": "results/a0r2/statistics/statistical-result.json", "sha256": "5" * 64},
            "receipt": {"path": "results/a0r2/activation/activation-receipt.json", "sha256": "6" * 64},
            "index": {"path": "results/a0r2/statistics/representations-index.jsonl", "sha256": "7" * 64},
            "report": {"path": "results/a0r2/statistics/report.md", "sha256": "8" * 64},
            "dense": {
                "path": self.DENSE_LOCATOR,
                "sha256": "9" * 64,
                "records": 1920,
                "hidden_size": 960,
            },
        }

        self.failure_publication = {
            "artifact_class": "a0r2-publication-manifest",
            "created_at": "2026-08-15T19:16:00Z",
            "protocol_id": "a0r2-independent-model-v1.0.0",
            "status": "failed",
            "scientific_status": "exploratory",
            "empirical": True,
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "terminal_status": "failed",
            "protocol": {
                "path": "experiments/a0r2-independent-model/study-protocol.json",
                "sha256": "f" * 64,
            },
            "publication": {
                "publish_every_terminal_outcome": True,
                "sensitivity_may_rescue_primary": False,
                "model_substitution_after_output": False,
                "claim_promotion": False,
            },
            "result": {"path": "results/a0r2/failure/run-failure.json", "sha256": "5" * 64},
            "report": {"path": "results/a0r2/failure/report.md", "sha256": "8" * 64},
        }

    def test_activation_schema_accepts_baseline(self) -> None:
        self.assertEqual([], validate(self.activation, self.activation_schema))

    def test_statistics_schema_accepts_baseline(self) -> None:
        self.assertEqual([], validate(self.statistics, self.statistics_schema))

    def test_failure_schema_accepts_baseline(self) -> None:
        self.assertEqual([], validate(self.failure, self.failure_schema))

    def test_publication_schema_accepts_baseline(self) -> None:
        self.assertEqual([], validate(self.publication, self.publication_schema))

    def test_publication_schema_accepts_failure_without_activation_bundle(self) -> None:
        self.assertEqual([], validate(self.failure_publication, self.publication_schema))

    def test_activation_rejects_wrong_tuple(self) -> None:
        bad = copy.deepcopy(self.activation)
        bad["activation"]["tuple_index"] = 11
        self.assertTrue(validate(bad, self.activation_schema))

    def test_activation_rejects_non_pass_status(self) -> None:
        bad = copy.deepcopy(self.activation)
        bad["status"] = "null"
        self.assertTrue(validate(bad, self.activation_schema))

    def test_activation_rejects_model_output_not_accessed(self) -> None:
        bad = copy.deepcopy(self.activation)
        bad["access"]["model_output_accessed"] = False
        self.assertTrue(validate(bad, self.activation_schema))

    def test_activation_rejects_model_directory_locator(self) -> None:
        bad = copy.deepcopy(self.activation)
        bad["output_bundle"]["dense_locator"] = "artifacts/models/smollm2-360m-f8027fd0"
        self.assertTrue(validate(bad, self.activation_schema))

    def test_activation_rejects_absolute_report_path(self) -> None:
        bad = copy.deepcopy(self.activation)
        bad["output_bundle"]["reports"] = ["/tmp/escape.md"]
        self.assertTrue(validate(bad, self.activation_schema))

    def test_statistics_rejects_primary_drift(self) -> None:
        bad = copy.deepcopy(self.statistics)
        bad["primary_endpoint"]["primary_semantics"] = "sentinel_output"
        self.assertTrue(validate(bad, self.statistics_schema))

    def test_statistics_rejects_sealed_targets_not_accessed(self) -> None:
        bad = copy.deepcopy(self.statistics)
        bad["access"]["sealed_targets_accessed"] = False
        self.assertTrue(validate(bad, self.statistics_schema))

    def test_statistics_rejects_traversal_in_reports(self) -> None:
        bad = copy.deepcopy(self.statistics)
        bad["result_bundle"]["reports"] = ["../escape.md"]
        self.assertTrue(validate(bad, self.statistics_schema))

    def test_statistics_rejects_shortcut_drift(self) -> None:
        bad = copy.deepcopy(self.statistics)
        bad["controls"]["shortcut_refusal"]["required_control_count"] = 13
        self.assertTrue(validate(bad, self.statistics_schema))

    def test_failure_rejects_sealed_access(self) -> None:
        bad = copy.deepcopy(self.failure)
        bad["access"]["sealed_targets_accessed"] = True
        self.assertTrue(validate(bad, self.failure_schema))

    def test_failure_allows_possibly_accessed(self) -> None:
        bad = copy.deepcopy(self.failure)
        bad["access"]["model_output_accessed"] = "possibly_accessed"
        bad["access"]["sealed_targets_accessed"] = "possibly_accessed"
        self.assertEqual([], validate(bad, self.failure_schema))

    def test_publication_rejects_terminal_status_drift(self) -> None:
        bad = copy.deepcopy(self.publication)
        bad["terminal_status"] = "cancelled"
        self.assertTrue(validate(bad, self.publication_schema))

    def test_publication_rejects_claim_promotion(self) -> None:
        bad = copy.deepcopy(self.publication)
        bad["publication"]["claim_promotion"] = True
        self.assertTrue(validate(bad, self.publication_schema))

    def test_publication_rejects_absolute_result_path(self) -> None:
        bad = copy.deepcopy(self.publication)
        bad["result"]["path"] = "/abs/path/statistical-result.json"
        self.assertTrue(validate(bad, self.publication_schema))

    def test_publication_rejects_absolute_dense_path(self) -> None:
        bad = copy.deepcopy(self.publication)
        bad["dense"]["path"] = "/abs/path/activations.json"
        self.assertTrue(validate(bad, self.publication_schema))

    def test_publication_rejects_publish_every_terminal_outcome_false(self) -> None:
        bad = copy.deepcopy(self.publication)
        bad["publication"]["publish_every_terminal_outcome"] = False
        self.assertTrue(validate(bad, self.publication_schema))


if __name__ == "__main__":
    unittest.main()
