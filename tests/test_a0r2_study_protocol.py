from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.validator import validate


class A0R2StudyProtocolSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = ROOT
        self.schema = json.loads((self.root / "schemas/a0r2-study-protocol.schema.json").read_text(encoding="utf-8"))
        self.protocol = json.loads(
            (self.root / "experiments/a0r2-independent-model/study-protocol.json").read_text(encoding="utf-8")
        )

    def test_study_protocol_is_schema_valid(self) -> None:
        self.assertEqual([], validate(self.protocol, self.schema))

    def test_primary_tuple_drift_is_rejected(self) -> None:
        protocol = copy.deepcopy(self.protocol)
        protocol["primary_endpoint"]["tuple_index"] = 6
        errors = validate(protocol, self.schema)
        self.assertTrue(errors)
        self.assertTrue(any(issue.path.endswith("primary_endpoint.tuple_index") for issue in errors))

    def test_multiplicity_drift_is_rejected(self) -> None:
        protocol = copy.deepcopy(self.protocol)
        protocol["primary_endpoint"]["multiplicity"] = 2
        errors = validate(protocol, self.schema)
        self.assertTrue(errors)
        self.assertTrue(any(issue.path.endswith("primary_endpoint.multiplicity") for issue in errors))

    def test_outcome_drift_is_rejected(self) -> None:
        protocol = copy.deepcopy(self.protocol)
        protocol["outcomes"]["outcome_map"]["positive"] = "pass"
        errors = validate(protocol, self.schema)
        self.assertTrue(errors)
        self.assertTrue(any(issue.path.endswith("outcomes.outcome_map.positive") for issue in errors))

        protocol = copy.deepcopy(self.protocol)
        protocol["outcomes"]["rules"]["positive"] = "support if anything looks promising"
        self.assertTrue(validate(protocol, self.schema))

    def test_approval_required_drift_is_rejected(self) -> None:
        protocol = copy.deepcopy(self.protocol)
        protocol["approval_required"] = False
        errors = validate(protocol, self.schema)
        self.assertTrue(errors)
        self.assertTrue(any(issue.path.endswith("approval_required") for issue in errors))

    def test_negative_control_count_is_fixed_to_fourteen(self) -> None:
        protocol = copy.deepcopy(self.protocol)
        protocol["negative_controls"] = protocol["negative_controls"][:13]
        errors = validate(protocol, self.schema)
        self.assertTrue(errors)
        self.assertTrue(any(issue.path.endswith("negative_controls") for issue in errors))

    def test_negative_control_substitution_is_rejected(self) -> None:
        protocol = copy.deepcopy(self.protocol)
        protocol["negative_controls"][0] = "support_seeking_control"
        self.assertTrue(validate(protocol, self.schema))

    def test_sealed_target_hash_drift_is_rejected(self) -> None:
        protocol = copy.deepcopy(self.protocol)
        protocol["inputs"]["sealed_targets_sha256"] = "0" * 64
        self.assertTrue(validate(protocol, self.schema))

    def test_sensitivity_cannot_rescue_primary(self) -> None:
        protocol = copy.deepcopy(self.protocol)
        protocol["publication"]["sensitivity_may_rescue_primary"] = True
        self.assertTrue(validate(protocol, self.schema))

    def test_shortcut_refusal_threshold_drift_is_rejected(self) -> None:
        protocol = copy.deepcopy(self.protocol)
        protocol["shortcut_refusal"]["macro_f1_at_or_above"] = 0.75
        self.assertTrue(validate(protocol, self.schema))

    def test_every_terminal_outcome_must_be_published(self) -> None:
        protocol = copy.deepcopy(self.protocol)
        protocol["publication"]["publish_every_terminal_outcome"] = False
        self.assertTrue(validate(protocol, self.schema))

    def test_claim_promotion_is_rejected(self) -> None:
        protocol = copy.deepcopy(self.protocol)
        protocol["publication"]["claim_promotion"] = True
        self.assertTrue(validate(protocol, self.schema))

    def test_sealed_target_access_cannot_be_preapproved(self) -> None:
        protocol = copy.deepcopy(self.protocol)
        protocol["sealed_execution"]["sealed_targets_access"] = "authorized"
        self.assertTrue(validate(protocol, self.schema))

    def test_second_sealed_run_is_rejected(self) -> None:
        protocol = copy.deepcopy(self.protocol)
        protocol["sealed_execution"]["max_runs"] = 2
        self.assertTrue(validate(protocol, self.schema))

    def test_human_or_llm_judging_is_rejected(self) -> None:
        for key in ("annotators", "experts", "llm_judges", "manual_adjudication"):
            with self.subTest(key=key):
                protocol = copy.deepcopy(self.protocol)
                protocol["human_review"][key] = True
                self.assertTrue(validate(protocol, self.schema))


if __name__ == "__main__":
    unittest.main()
