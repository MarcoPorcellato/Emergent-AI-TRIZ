import copy
import unittest

from latent_triz.exp002_auto_contract import build_no_model_protocol
from latent_triz.exp002_auto_execution import (
    Exp002AutoExecutionError,
    authorize_auto_shard,
    score_auto_candidates,
    score_auto_surface,
)


class Exp002AutoExecutionTests(unittest.TestCase):
    def setUp(self):
        self.protocol = build_no_model_protocol()
        self.protocol_sha256 = "a" * 64
        self.dossier = {
            "artifact_class": "exp002-auto-approval-dossier",
            "protocol_id": "exp002-auto-v1.0.0",
            "protocol_sha256": self.protocol_sha256,
            "schedule_sha256": "c" * 64,
            "input_manifest_sha256": "d" * 64,
            "status": "authorized",
            "operator_approval": {"granted": True, "operator_id": "MarcoPorcellato", "approval_text_sha256": "b" * 64},
            "exact_models": copy.deepcopy(self.protocol["models"]),
            "permissions": {"model_load": True, "network": False, "generation": False, "sealed_target_read": "exactly_one_at_analysis_boundary"},
            "limits": {"wall_time_seconds_per_shard": 1800, "peak_rss_bytes_per_shard": 8589934592, "new_score_output_bytes_per_model": 134217728},
            "shards": [{"stage_id": "AUTO-1", "shard_id": "auto-1-cyclic-and-label-free"}],
            "claim_ids": [],
        }
        self.gate = {"resource_decision": "admit", "admission_active": False, "queue_count": 0}

    def test_unapproved_or_busy_boundary_rejects_before_scorer(self):
        calls = []
        unapproved = copy.deepcopy(self.dossier)
        unapproved["status"] = "approval_requested"
        unapproved["operator_approval"]["granted"] = False
        with self.assertRaises(Exp002AutoExecutionError):
            authorize_auto_shard(unapproved, self.protocol_sha256, self.gate, "Qwen/Qwen3-0.6B-Base", "AUTO-1", "auto-1-cyclic-and-label-free")
        with self.assertRaises(Exp002AutoExecutionError):
            authorize_auto_shard(self.dossier, self.protocol_sha256, {"resource_decision": "admit", "admission_active": True, "queue_count": 0}, "Qwen/Qwen3-0.6B-Base", "AUTO-1", "auto-1-cyclic-and-label-free")
        self.assertEqual(calls, [])

    def test_authorized_shard_requires_exact_model_and_frozen_shard(self):
        authorization = authorize_auto_shard(self.dossier, self.protocol_sha256, self.gate, "Qwen/Qwen3-0.6B-Base", "AUTO-1", "auto-1-cyclic-and-label-free")
        self.assertEqual(authorization["model_id"], "Qwen/Qwen3-0.6B-Base")
        with self.assertRaises(Exp002AutoExecutionError):
            authorize_auto_shard(self.dossier, self.protocol_sha256, self.gate, "Qwen/Qwen3-0.6B-Base", "AUTO-5", "auto-5-permutations-01")

    def test_public_surface_scoring_preserves_no_target_boundary(self):
        rows = [{"record_id": "transfer-01", "condition": "cyclic", "prompt": "public"}]
        scored = score_auto_surface(rows, lambda _: {"A": 1, "B": 0, "C": -1, "D": -2})
        self.assertEqual(scored[0]["scores"]["A"], 1.0)
        with self.assertRaises(Exp002AutoExecutionError):
            score_auto_surface([{**rows[0], "target": 0}], lambda _: {"A": 0, "B": 0, "C": 0, "D": 0})

    def test_label_free_candidate_scoring_rejects_nonfinite_or_target_fields(self):
        rows = [{"record_id": "auto-factual-01", "candidate_descriptions": ["a", "bb", "ccc", "dddd"]}]
        scored = score_auto_candidates(rows, len)
        self.assertEqual(scored[0]["candidate_scores"], [1.0, 2.0, 3.0, 4.0])
        with self.assertRaises(Exp002AutoExecutionError):
            score_auto_candidates([{**rows[0], "expected_candidate_index": 0}], len)


if __name__ == "__main__":
    unittest.main()
