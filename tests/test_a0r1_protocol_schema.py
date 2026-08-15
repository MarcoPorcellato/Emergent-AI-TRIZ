from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.validator import validate


class A0R1ProtocolSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        schema_path = self.repo_root / "schemas/a0r1-protocol.schema.json"
        self.schema = json.loads(schema_path.read_text(encoding="utf-8"))

    def _valid_protocol(self) -> dict:
        return {
            "artifact_class": "a0-r1-protocol",
            "protocol_id": "a0-r1-tier-r1-v1.0",
            "protocol_status": "frozen",
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "protocol_type": "pre_output_replication",
            "independence_audit": {
                "source_protocol_id": "a0-automated-weak-proxy-v1.0.3",
                "source_protocol_merge_sha": "fc80976d3a256ed88e2d59f1a6f893e15154e3a0",
                "source_protocol_run_id": "a0-v1.0.3-e93a9faa",
                "a0_case_text_reused": False,
                "a0_template_ids_reused": False,
                "a0_seed_reused": False,
            },
            "model": {
                "name": "EleutherAI/pythia-70m-deduped",
                "revision": "e93a9faa9c77e5d09219f6c868bfc7a1bd65593c",
                "cached": True,
            },
            "tokenizer": {
                "name": "EleutherAI/pythia-70m-deduped",
                "revision": "e93a9faa9c77e5d09219f6c868bfc7a1bd65593c",
            },
            "runtime": {
                "requires_interactive_model_server": False,
                "runtime_device": "cpu",
            },
            "primary_endpoint": {
                "layer": 6,
                "token_site": "mean_transformation_span",
                "primary_view": "problem_plus_transformation",
                "surface_baseline_view": "problem_only",
                "is_max_statistic_selection": False,
                "multiplicity": 1,
            },
            "thresholds": {
                "critical_successes": 17,
                "primary_permutation_p_at_most": 0.05,
                "macro_f1_margin_at_least": 0.1,
                "family_successes_at_least": 17,
                "domain_direction_successes_minimum": 4,
            },
            "calibration": {
                "method": "exact_family_blocked_binomial_primary_endpoint",
                "selection_mode": "deterministic_predeclared",
                "deterministic_seed": 20260815,
                "power": 0.8,
                "maximum_false_positive_rate": 0.05,
                "target_effect_size": 0.3,
                "minimum_detectable_effect": 0.2597184664182352,
                "selected_families_per_domain": 4,
                "selected_family_count": 24,
                "selected_permutation_budget": 999,
                "critical_successes": 17,
                "family_successes_at_least": 17,
            },
            "outcome_rules": {
                "positive": "all gates pass and primary_permutation_p <= 0.05 and macro_f1_margin_over_surface >= 0.10 and family_successes >= 17",
                "null": "all gates pass and positive rule is false",
                "failed": "integrity, identity, execution, data, or receipt gate fails before a valid statistic",
                "non_interpretable": "shortcut controls reach or exceed refusal threshold",
            },
            "outcome_classes": {
                "positive": "positive",
                "null": "null",
                "failed": "failed",
                "non_interpretable": "non_interpretable",
            },
            "status": "frozen",
        }

    def test_a0r1_protocol_schema_valid(self) -> None:
        protocol = self._valid_protocol()
        issues = validate(protocol, self.schema)
        self.assertEqual([], issues)

    def test_a0r1_protocol_rejects_mutated_a0_dependencies(self) -> None:
        protocol = self._valid_protocol()
        protocol["independence_audit"]["a0_case_text_reused"] = True
        issues = validate(protocol, self.schema)
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("independence_audit.a0_case_text_reused") for issue in issues))

    def test_a0r1_protocol_rejects_wrong_model_identity(self) -> None:
        protocol = self._valid_protocol()
        protocol["model"]["revision"] = "0000000000000000000000000000000000000000000000"
        issues = validate(protocol, self.schema)
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("model.revision") for issue in issues))

    def test_a0r1_protocol_rejects_unknown_properties(self) -> None:
        protocol = self._valid_protocol()
        protocol["unrecognized_root_property"] = "forbidden"
        issues = validate(protocol, self.schema)
        self.assertTrue(issues)
        self.assertTrue(any("Additional property not allowed" in issue.message for issue in issues))

    def test_a0r1_protocol_rejects_bad_primary_endpoint_and_status(self) -> None:
        protocol = self._valid_protocol()
        protocol["primary_endpoint"]["layer"] = 4
        protocol["status"] = "positive"
        issues = validate(protocol, self.schema)
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("primary_endpoint.layer") for issue in issues))
        self.assertTrue(any(issue.path.endswith("status") for issue in issues))

    def test_a0r1_protocol_rejects_nonempty_claims(self) -> None:
        protocol = self._valid_protocol()
        protocol["claim_ids"] = ["CLM-001"]
        issues = validate(protocol, self.schema)
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("claim_ids") for issue in issues))
