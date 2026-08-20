import json
import unittest
from pathlib import Path

from latent_triz.exp002_execution import Exp002ExecutionError, authorize_material_run, score_injected_direct_questions, score_injected_surface


ROOT = Path(__file__).resolve().parents[1]


class Exp002ExecutionTests(unittest.TestCase):
    def test_unapproved_dossier_fails_before_adapter(self):
        dossier = json.loads((ROOT / "experiments/exp002-qwen3-followup/approval-dossier.json").read_text(encoding="utf-8"))
        dossier["status"] = "approval_requested"
        dossier["operator_approval"] = {"granted": False, "operator_id": "MarcoPorcellato", "approved_at": None, "approval_text_sha256": None}
        gate = {"resource_decision": "admit", "admission_active": False, "queue_count": 0}
        with self.assertRaises(Exp002ExecutionError):
            authorize_material_run(dossier, gate, "Qwen/Qwen3-0.6B-Base")

    def test_ccp_gate_is_fail_closed(self):
        dossier = {"artifact_class": "exp002-approval-dossier", "protocol_id": "exp002-qwen3-followup-v1.0.0", "status": "approval_requested"}
        with self.assertRaises(Exp002ExecutionError):
            authorize_material_run(dossier, {"resource_decision": "unknown", "admission_active": False, "queue_count": 0}, "Qwen/Qwen3-0.6B-Base")

    def test_injected_surface_has_no_target_capability(self):
        rows = [{"record_id": "synthetic-1", "prompt": "prompt"}]
        output = score_injected_surface(rows, lambda _: {"A": 1, "B": 0, "C": -1, "D": -2})
        self.assertEqual(output[0]["scores"]["A"], 1.0)

    def test_injected_direct_questions_preserve_only_public_identity(self):
        rows = [{"question_id": "exp002-q1", "module": "foundational_concepts", "prompt": "What is a resource?", "scientific_role": "knowledge_endpoint", "response_mode": "structured_completion"}]
        output = score_injected_direct_questions(rows, lambda row: {"prediction": "resource", "abstained": False})
        self.assertEqual(output[0]["prediction"], "resource")
        self.assertNotIn("expected_answer", output[0])

    def test_bounded_completion_requires_separate_generation_authorization(self):
        rows = [{"question_id": "exp002-q1", "module": "foundational_concepts", "prompt": "What is a resource?", "response_mode": "bounded_completion"}]
        with self.assertRaises(Exp002ExecutionError):
            score_injected_direct_questions(rows, lambda row: {"prediction": "resource", "abstained": False})
        output = score_injected_direct_questions(rows, lambda row: {"prediction": "resource", "abstained": False}, allow_generation=True)
        self.assertEqual(output[0]["prediction"], "resource")

    def test_injected_direct_questions_reject_malformed_outcome(self):
        rows = [{"question_id": "exp002-q1", "module": "foundational_concepts", "prompt": "What is a resource?"}]
        with self.assertRaises(Exp002ExecutionError):
            score_injected_direct_questions(rows, lambda row: {"prediction": "resource"})


if __name__ == "__main__":
    unittest.main()
