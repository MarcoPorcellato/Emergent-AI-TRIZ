from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.validator import validate


def _sha(value: int) -> str:
    return f"{value:064x}"[:64]


class A0R1OutputSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.activation_schema = json.loads(
            (root / "schemas/a0r1-activation-receipt.schema.json").read_text(encoding="utf-8")
        )
        self.statistical_schema = json.loads(
            (root / "schemas/a0r1-statistical-result.schema.json").read_text(encoding="utf-8")
        )

    def _valid_activation(self) -> dict:
        return {
            "artifact_class": "a0r1-activation-receipt",
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "status": "pass",
            "created_at": "2026-08-15T01:00:00Z",
            "protocol": {
                "id": "a0-r1-tier-r1-v1.0",
                "protocol_status": "frozen",
                "hash": _sha(1),
                "snapshot_hash": _sha(2),
            },
            "implementation": {
                "protocol_status": "frozen",
                "status": "frozen_before_model_output",
                "hash": _sha(3),
            },
            "freeze": {
                "protocol_status": "frozen",
                "status": "frozen",
                "protocol_id": "a0-r1-tier-r1-v1.0",
                "hash": _sha(4),
            },
            "corpus": {
                "manifest_sha256": _sha(5),
                "cases_sha256": _sha(6),
                "sealed_targets_sha256": _sha(7),
                "sealed_targets_accessed": False,
                "selected_cases": 48,
            },
            "runtime": {
                "model": "EleutherAI/pythia-70m-deduped",
                "revision": "e93a9faa9c77e5d09219f6c868bfc7a1bd65593c",
                "files": [
                    {"name": "README.md", "sha256": _sha(8), "size": 10},
                    {"name": "config.json", "sha256": _sha(9), "size": 12},
                    {"name": "model.safetensors", "sha256": _sha(10), "size": 15},
                    {"name": "special_tokens_map.json", "sha256": _sha(11), "size": 6},
                    {"name": "tokenizer.json", "sha256": _sha(12), "size": 17},
                    {"name": "tokenizer_config.json", "sha256": _sha(13), "size": 14},
                ],
                "binding_hash": _sha(14),
            },
            "primary_contract": {
                "primary_view": "problem_plus_transformation",
                "primary_token_site": "mean_transformation_span",
                "primary_layer": 6,
                "baseline_view": "problem_only",
                "baseline_token_sites": ["sentinel"],
                "multiplicity": 1,
            },
            "sealed_target_semantics_accessed": False,
            "model_output_accessed": True,
            "sealed_model_output_accessed": True,
            "records": 96,
            "dense_vectors": {
                "path": "activations.json",
                "sha256": _sha(15),
                "format": "json-vectors",
                "bytes": 1024,
            },
            "representation_index": {
                "path": "representations-index.jsonl",
                "sha256": _sha(16),
            },
        }

    def _valid_positive_result(self, status: str) -> dict:
        assert status in ("positive", "null")
        base_scores = [1.0, -1.0]
        return {
            "artifact_class": "a0r1-analytical-result",
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "status": status,
            "protocol_id": "a0-r1-tier-r1-v1.0",
            "protocol_status": "frozen",
            "analysis_type": "fixed_primary",
            "sealing_rule": "sealed_targets_opened_once_at_boundary",
            "shortcut_status": "pass",
            "input_hashes": {
                "protocol": _sha(1),
                "implementation": _sha(2),
                "shortcut": _sha(3),
                "activation_receipt": _sha(4),
                "representation_index": _sha(5),
                "dense_vectors": _sha(6),
                "sealed_targets": _sha(7),
            },
            "design": {
                "cases": 48,
                "families": 24,
                "domains": 6,
                "layer": 6,
                "token_site": "mean_transformation_span",
                "primary_view": "problem_plus_transformation",
                "surface_view": "problem_only",
                "surface_site": "sentinel",
                "permutation_budget": 999,
                "seed": 20260815,
                "critical_successes": 17,
                "required_domain_directions": 4,
            },
            "primary": {
                "family_successes": 17 if status == "positive" else 16,
                "scores": [1.0, -1.0],
                "macro_f1": 0.8,
                "family_success_rate": 0.708333333333,
                "per_domain_accuracy": {
                    "agriculture": 0.5,
                    "energy": 0.5,
                    "manufacturing": 0.5,
                    "medicine": 0.5,
                    "software": 0.5,
                    "transport": 0.5,
                },
                "domain_direction_successes": {"agriculture": 1.0},
            },
            "surface_baseline": {
                "family_successes": 0,
                "family_success_rate": 0.0,
                "macro_f1": 0.5,
                "scores": [0.2, 0.1],
                "per_domain_accuracy": {
                    "agriculture": 0.5,
                    "energy": 0.5,
                    "manufacturing": 0.5,
                    "medicine": 0.5,
                    "software": 0.5,
                    "transport": 0.5,
                },
                "domain_direction_successes": {"agriculture": 0.0},
            },
            "macro_f1_margin_over_surface": 0.1 if status == "positive" else -0.1,
            "max_family_successes_observed": 24 if status == "positive" else 12,
            "domain_direction_successes": {"agriculture": 1.0},
            "domain_direction_success_count": 4 if status == "positive" else 2,
            "primary_permutation_p": 0.01 if status == "positive" else 0.11,
            "permutation_seed": 20260815,
            "permutation_budget": 999,
            "null_maxima": {
                "minimum": 9,
                "median": 16,
                "maximum": 20,
                "sha256": _sha(8),
            },
            "sensitivity": {
                "problem_plus_transformation": {
                    "combos": {
                        "6": {
                            "mean_transformation_span": {
                                "family_successes": 17,
                                "macro_f1": 0.8,
                                "family_success_rate": 0.7,
                            }
                        }
                    },
                    "paired_direction_delta_mean": 0.0,
                    "rescues_primary": False,
                }
            },
            "outcome_rule": {
                "max_statistic_p_at_most": 0.05,
                "macro_f1_margin_at_least": 0.1,
                "family_successes_at_least": 17,
                "domain_direction_successes_minimum": 4,
            },
            "outcome_deterministic": True,
            "model_output_accessed": True,
            "sealed_model_output_accessed": True,
            "sealed_targets_accessed": True,
            "primary_is_max_statistic_selection": False,
            "outcome_description": "Exploratory fixed-primary signal exceeds the frozen R1 thresholds on sealed corpus.",
            "non_interpretable_reason": None,
        }

    def _valid_failure_result(self, status: str) -> dict:
        assert status in ("failed", "non_interpretable")
        return {
            "artifact_class": "a0r1-analytical-result",
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "status": status,
            "protocol_id": "a0-r1-tier-r1-v1.0",
            "protocol_status": "unknown",
            "analysis_type": "fixed_primary",
            "sealing_rule": "sealed_targets_opened_once_at_boundary",
            "shortcut_status": "pass",
            "input_hashes": {
                "protocol": _sha(1),
                "implementation": _sha(2),
                "shortcut": _sha(3),
                "activation_receipt": _sha(4),
                "representation_index": _sha(5),
                "dense_vectors": "",
                "sealed_targets": _sha(6),
            },
            "design": {
                "cases": 0,
                "families": 0,
                "domains": 0,
                "layer": 6,
                "token_site": "mean_transformation_span",
                "primary_view": "problem_plus_transformation",
                "surface_view": "problem_only",
                "surface_site": "sentinel",
                "permutation_budget": 999,
                "seed": 20260815,
                "critical_successes": 17,
                "required_domain_directions": 4,
            },
            "primary": {},
            "surface_baseline": {},
            "macro_f1_margin_over_surface": 0.0,
            "max_family_successes_observed": 0,
            "domain_direction_successes": {},
            "domain_direction_success_count": 0,
            "primary_permutation_p": 1.0,
            "permutation_seed": 20260815,
            "permutation_budget": 999,
            "null_maxima": {
                "minimum": None,
                "median": None,
                "maximum": None,
                "sha256": None,
            },
            "sensitivity": {},
            "outcome_rule": {
                "max_statistic_p_at_most": 0.05,
                "macro_f1_margin_at_least": 0.1,
                "family_successes_at_least": 17,
                "domain_direction_successes_minimum": 4,
            },
            "outcome_deterministic": True,
            "model_output_accessed": False,
            "sealed_model_output_accessed": False,
            "sealed_targets_accessed": False,
            "primary_is_max_statistic_selection": False,
            "outcome_description": "Analysis aborted by integrity or execution gate failure.",
            "non_interpretable_reason": "shortcut gate is not pass" if status == "non_interpretable" else "activation receipt is not pass",
        }

    def test_activation_schema_validates(self) -> None:
        self.assertEqual([], validate(self._valid_activation(), self.activation_schema))

    def test_activation_rejects_mutations(self) -> None:
        payload = self._valid_activation()
        payload["corpus"]["selected_cases"] = 47
        self.assertTrue(validate(payload, self.activation_schema))

        payload = self._valid_activation()
        payload["records"] = 95
        self.assertTrue(validate(payload, self.activation_schema))

        payload = self._valid_activation()
        payload["primary_contract"]["primary_layer"] = 4
        self.assertTrue(validate(payload, self.activation_schema))

        payload = self._valid_activation()
        payload["sealed_target_semantics_accessed"] = True
        self.assertTrue(validate(payload, self.activation_schema))

        payload = self._valid_activation()
        payload["sealed_model_output_accessed"] = False
        self.assertTrue(validate(payload, self.activation_schema))

    def test_statistical_schema_validates_statuses(self) -> None:
        self.assertEqual([], validate(self._valid_positive_result("positive"), self.statistical_schema))
        self.assertEqual([], validate(self._valid_positive_result("null"), self.statistical_schema))
        self.assertEqual([], validate(self._valid_failure_result("failed"), self.statistical_schema))
        self.assertEqual([], validate(self._valid_failure_result("non_interpretable"), self.statistical_schema))

    def test_statistical_rejects_mutations(self) -> None:
        positive = self._valid_positive_result("positive")
        positive["model_output_accessed"] = False
        self.assertTrue(validate(positive, self.statistical_schema))

        null = self._valid_positive_result("null")
        null["design"]["cases"] = 47
        self.assertTrue(validate(null, self.statistical_schema))

        failed = self._valid_failure_result("failed")
        failed["max_family_successes_observed"] = 1
        self.assertTrue(validate(failed, self.statistical_schema))

        mutated = copy.deepcopy(self._valid_failure_result("failed"))
        mutated["primary"] = {
            "family_successes": 1,
            "scores": [1.0],
            "macro_f1": 0.5,
            "per_domain_accuracy": {},
            "domain_direction_successes": {},
        }
        self.assertTrue(validate(mutated, self.statistical_schema))

        mutated = copy.deepcopy(self._valid_positive_result("positive"))
        del mutated["input_hashes"]["protocol"]
        self.assertTrue(validate(mutated, self.statistical_schema))

        mutated = copy.deepcopy(self._valid_positive_result("positive"))
        mutated["status"] = "invalid"
        self.assertTrue(validate(mutated, self.statistical_schema))

    def test_unknown_properties_rejected(self) -> None:
        payload = self._valid_activation()
        payload["unexpected_root_property"] = "forbidden"
        issues = validate(payload, self.activation_schema)
        self.assertTrue(issues)

        payload = self._valid_positive_result("positive")
        payload["primary"]["unexpected_nested"] = "forbidden"
        issues = validate(payload, self.statistical_schema)
        self.assertTrue(issues)


if __name__ == "__main__":
    unittest.main()
