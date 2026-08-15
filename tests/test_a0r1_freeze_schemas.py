from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.validator import validate


class A0R1FreezeSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.power_schema = json.loads((self.repo_root / "schemas/a0r1-power.schema.json").read_text(encoding="utf-8"))
        self.freeze_schema = json.loads(
            (self.repo_root / "schemas/a0r1-freeze-manifest.schema.json").read_text(encoding="utf-8")
        )

    def _valid_power_receipt(self) -> dict:
        return {
            "artifact_class": "a0r1-power-calibration",
            "protocol_id": "a0-r1-tier-r1-v1.0",
            "protocol_status": "planned",
            "method": "exact_primary_endpoint",
            "selection_mode": "deterministic_simulation",
            "multiplicity": {"layers": 1, "token_sites": 1, "total": 1},
            "targets": {
                "families_per_domain": 4,
                "family_level_critical_successes": 17,
                "family_success_probability_under_null": 0.5,
                "family_success_probability_under_target": 0.8,
            },
            "simulation": {
                "seed": 20260815,
                "trials": 100000,
                "empirical_resolution": 0.00001,
                "minimum_resolvable_p": 0.001,
                "passes_empirical_check": True,
                "min_attainable_p": 0.001,
            },
            "selected": {
                "families_per_domain": 4,
                "family_count": 24,
                "permutation_budget": 999,
                "critical_successes": 17,
                "minimum_attainable_p": 0.001,
                "exact_false_positive_rate": 0.03195732831954956,
                "exact_power_at_target_success_probability": 0.9108287412264922,
                "minimum_detectable_effect": 0.2597184664182352,
                "empirical_null_fpr": 0.0324,
                "empirical_target_power": 0.9104,
                "exact_vs_empirical_tolerance": 0.01,
            },
            "status": "pass",
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "model_output_accessed": False,
            "sealed_targets_accessed": False,
        }

    def _valid_freeze_manifest(self) -> dict:
        return {
            "artifact_class": "a0-r1-protocol-freeze-manifest",
            "protocol_id": "a0-r1-tier-r1-v1.0",
            "protocol_status": "frozen",
            "planned_protocol_snapshot_hash": "a" * 64,
            "frozen_protocol_hash": "b" * 64,
            "corpus_manifest_hash": "c" * 64,
            "preoutput_manifest_hash": "d" * 64,
            "power_hash": "e" * 64,
            "cases_sha256": "f" * 64,
            "calibration_targets_sha256": "0" * 64,
            "sealed_targets_sha256": "1" * 64,
            "independence_audit_sha256": "2" * 64,
            "shortcuts_sha256": "3" * 64,
            "summary_sha256": "4" * 64,
            "primary_endpoint": {
                "layer": 6,
                "token_site": "mean_transformation_span",
                "primary_view": "problem_plus_transformation",
                "surface_baseline_view": "problem_only",
                "is_max_statistic_selection": False,
                "multiplicity": 1,
            },
            "status": "frozen",
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "model_output_accessed": False,
            "sealed_model_output_accessed": False,
        }

    def test_a0r1_power_and_freeze_manifest_validate(self) -> None:
        issues = validate(self._valid_power_receipt(), self.power_schema)
        self.assertEqual([], issues)

        issues = validate(self._valid_freeze_manifest(), self.freeze_schema)
        self.assertEqual([], issues)

    def test_a0r1_power_rejects_mutations_envelope_and_access(self) -> None:
        power = self._valid_power_receipt()
        power["status"] = "invalid"
        issues = validate(power, self.power_schema)
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("status") for issue in issues))

        power = self._valid_power_receipt()
        power["model_output_accessed"] = True
        issues = validate(power, self.power_schema)
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("model_output_accessed") for issue in issues))

    def test_a0r1_freeze_manifest_rejects_bad_status_hashes_access(self) -> None:
        freeze = self._valid_freeze_manifest()
        freeze["protocol_status"] = "planned"
        issues = validate(freeze, self.freeze_schema)
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("protocol_status") for issue in issues))

        freeze = self._valid_freeze_manifest()
        freeze["preoutput_manifest_hash"] = "xyz"
        issues = validate(freeze, self.freeze_schema)
        self.assertTrue(issues)
        self.assertTrue(any("preoutput_manifest_hash" in issue.path for issue in issues))

        freeze = self._valid_freeze_manifest()
        freeze["status"] = "invalid"
        issues = validate(freeze, self.freeze_schema)
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("status") for issue in issues))

        freeze = self._valid_freeze_manifest()
        freeze["sealed_model_output_accessed"] = True
        issues = validate(freeze, self.freeze_schema)
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("sealed_model_output_accessed") for issue in issues))

    def test_a0r1_schema_rejects_unknown_properties(self) -> None:
        power = self._valid_power_receipt()
        power["unexpected_field"] = "forbidden"
        issues = validate(power, self.power_schema)
        self.assertTrue(issues)
        self.assertTrue(any("Additional property not allowed" in issue.message for issue in issues))

        freeze = self._valid_freeze_manifest()
        freeze["unexpected_property"] = "forbidden"
        issues = validate(freeze, self.freeze_schema)
        self.assertTrue(issues)
        self.assertTrue(any("Additional property not allowed" in issue.message for issue in issues))
