import unittest

from latent_triz.exp002_auto_stage_gate import build_preexecution_receipt, preflight_auto_shard


class Exp002AutoStageGateTests(unittest.TestCase):
    def test_unapproved_shard_is_explicitly_approval_required_without_model_or_key_access(self):
        result = preflight_auto_shard(
            dossier={"status": "approval_requested"},
            stage_id="AUTO-2", shard_id="factual-01", model_id="openai-community/gpt2",
        )
        self.assertEqual(result["status"], "approval_required")
        self.assertFalse(result["model_accessed"])
        self.assertFalse(result["sealed_target_accessed"])

    def test_receipt_is_no_model_template_only(self):
        receipt = build_preexecution_receipt()
        self.assertEqual(receipt["status"], "not_started")
        self.assertEqual(receipt["access"]["target_reads"], 0)
        self.assertFalse(receipt["access"]["model_loaded"])


if __name__ == "__main__":
    unittest.main()
