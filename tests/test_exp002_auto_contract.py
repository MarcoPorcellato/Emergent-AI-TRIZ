import copy
import unittest

from latent_triz.exp002_auto_contract import (
    AUTO_STAGES,
    Exp002AutoContractError,
    build_no_model_protocol,
    validate_auto_dossier,
    validate_auto_protocol,
)
from latent_triz.exp002_followup import EXPECTED_MODELS


class Exp002AutoContractTests(unittest.TestCase):
    def test_no_model_protocol_covers_exact_seven_models_and_all_auto_stages(self):
        protocol = build_no_model_protocol()
        validate_auto_protocol(protocol)
        self.assertEqual(tuple(stage["stage_id"] for stage in protocol["stages"]), AUTO_STAGES)
        self.assertEqual({entry["model_id"]: entry["revision"] for entry in protocol["models"]}, EXPECTED_MODELS)

    def test_protocol_rejects_model_revision_drift(self):
        protocol = build_no_model_protocol()
        protocol["models"][0]["revision"] = "0" * 40
        with self.assertRaises(Exp002AutoContractError):
            validate_auto_protocol(protocol)

    def test_protocol_rejects_any_no_model_access_capability(self):
        protocol = build_no_model_protocol()
        protocol["approval_boundary"]["model_load"] = True
        with self.assertRaises(Exp002AutoContractError):
            validate_auto_protocol(protocol)

    def test_dossier_requires_exact_protocol_hash_before_authorization(self):
        protocol = build_no_model_protocol()
        dossier = {
            "artifact_class": "exp002-auto-approval-dossier",
            "protocol_id": protocol["protocol_id"],
            "protocol_sha256": "0" * 64,
            "status": "authorized",
            "operator_approval": {"granted": True, "operator_id": "MarcoPorcellato", "approval_text_sha256": "1" * 64},
            "exact_models": copy.deepcopy(protocol["models"]),
            "permissions": {"model_load": True, "network": False, "generation": False, "sealed_target_read": "exactly_one_at_analysis_boundary"},
            "limits": {"wall_time_seconds_per_shard": 1800, "peak_rss_bytes_per_shard": 8589934592, "new_score_output_bytes_per_model": 134217728},
            "shards": [],
            "claim_ids": [],
        }
        with self.assertRaises(Exp002AutoContractError):
            validate_auto_dossier(dossier, protocol_sha256="2" * 64)

    def test_dossier_rejects_missing_schedule_or_input_manifest_hash(self):
        protocol = build_no_model_protocol()
        dossier = {
            "artifact_class": "exp002-auto-approval-dossier",
            "protocol_id": protocol["protocol_id"],
            "protocol_sha256": "2" * 64,
            "status": "approval_requested",
            "operator_approval": {"granted": False, "operator_id": "MarcoPorcellato", "approval_text_sha256": None},
            "exact_models": copy.deepcopy(protocol["models"]),
            "permissions": {"model_load": True, "network": False, "generation": False, "sealed_target_read": "exactly_one_at_analysis_boundary"},
            "limits": {"wall_time_seconds_per_shard": 1800, "peak_rss_bytes_per_shard": 8589934592, "new_score_output_bytes_per_model": 134217728},
            "shards": [],
            "claim_ids": [],
        }
        with self.assertRaises(Exp002AutoContractError):
            validate_auto_dossier(dossier, protocol_sha256="2" * 64)


if __name__ == "__main__":
    unittest.main()
