import unittest

from latent_triz.exp002_followup import EXPECTED_MODELS
from latent_triz.exp002_stage_gate import Exp002StageGateError, authorize_stage, validate_stage_dossier


def _dossier(stage="EXP-002B", status="approval_requested"):
    return {
        "artifact_class": "exp002-study-approval-dossier",
        "dossier_id": f"exp002-{stage.lower()}-approval-v1",
        "protocol_id": "exp002-qwen3-followup-v1.0.0",
        "stage_id": stage,
        "status": status,
        "exact_models": [
            {"model_id": model, "revision": revision, "local_root": f"artifacts/models/model-{index}"}
            for index, (model, revision) in enumerate(EXPECTED_MODELS.items())
        ],
        "prerequisites": {
            "answer_key_status": "frozen" if stage == "EXP-002B" else "not_applicable",
            "transfer_corpus_status": "frozen_no_model" if stage == "EXP-002C" else "not_applicable",
            "source_proximity_status": "pass",
            "power_calibration_status": "pass" if stage == "EXP-002C" else "not_applicable",
        },
        "permissions": {
            "model_load": True,
            "generation": False,
            "network": False,
            "sealed_target_read": "exactly_one_at_analysis_boundary",
            "ccp_material_run": True,
            "publish_every_terminal_outcome": True,
        },
        "limits": {"wall_time_seconds_per_model": 1800, "peak_rss_bytes_per_model": 8589934592, "new_dense_output_bytes_per_model": 134217728},
        "prohibitions": ["no tuning", "no substitution", "no retry", "no protocol change", "no generation", "no network"],
        "operator_approval": {"granted": status == "authorized", "operator_id": "MarcoPorcellato", "approved_at": "2026-08-20" if status == "authorized" else None, "approval_text_sha256": "a" * 64 if status == "authorized" else None},
        "scientific_status": "exploratory",
        "claim_ids": [],
    }


class Exp002StageGateTests(unittest.TestCase):
    def test_requested_dossier_is_closed_before_material_authorization(self):
        validate_stage_dossier(_dossier(), "EXP-002B")
        with self.assertRaises(Exp002StageGateError):
            authorize_stage(_dossier(), "EXP-002B", {"decision": "admit", "active": False, "queue_count": 0})

    def test_authorized_dossier_requires_fresh_ccp_gate(self):
        dossier = _dossier(status="authorized")
        with self.assertRaises(Exp002StageGateError):
            authorize_stage(dossier, "EXP-002B", {"decision": "deny", "active": False, "queue_count": 0})
        authorize_stage(dossier, "EXP-002B", {"decision": "admit", "active": False, "queue_count": 0})

    def test_stage_prerequisite_drift_fails_closed(self):
        dossier = _dossier(stage="EXP-002C")
        dossier["prerequisites"]["transfer_corpus_status"] = "design_ready_no_model"
        with self.assertRaises(Exp002StageGateError):
            validate_stage_dossier(dossier, "EXP-002C")

    def test_model_identity_and_permissions_are_exact(self):
        dossier = _dossier()
        dossier["exact_models"][0]["revision"] = "0" * 40
        with self.assertRaises(Exp002StageGateError):
            validate_stage_dossier(dossier, "EXP-002B")
        dossier = _dossier()
        dossier["permissions"]["generation"] = True
        with self.assertRaises(Exp002StageGateError):
            validate_stage_dossier(dossier, "EXP-002B")


if __name__ == "__main__":
    unittest.main()
