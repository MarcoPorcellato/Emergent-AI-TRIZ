import json
from pathlib import Path
import unittest

from latent_triz.exp002_answer_key import Exp002AnswerKeyError, freeze_answer_key_from_packets, validate_answer_key


ROOT = Path(__file__).resolve().parents[1]
KEY = json.loads((ROOT / "results/exp002/preexecution/direct-answer-key-template.json").read_text())


class Exp002AnswerKeyTests(unittest.TestCase):
    def test_not_ready_template_is_closed(self):
        validate_answer_key(KEY, ["exp002-self-report-1"], question_bank_sha256=KEY["question_bank_sha256"])

    def test_hash_drift_fails_closed(self):
        with self.assertRaises(Exp002AnswerKeyError):
            validate_answer_key(KEY, [], question_bank_sha256="0" * 64)

    def test_frozen_requires_three_reviewers_and_full_coverage(self):
        frozen = dict(KEY)
        frozen["status"] = "frozen"
        frozen["records"] = [{"question_id": "exp002-self-report-1", "key_type": "non_evidential", "expert_status": "reviewed"}]
        frozen["expert_review"] = {"required": True, "status": "complete", "reviewer_count": 3}
        with self.assertRaises(Exp002AnswerKeyError):
            validate_answer_key(frozen, ["exp002-self-report-1", "exp002-self-report-2"], question_bank_sha256=KEY["question_bank_sha256"])

    def test_freeze_agreement_and_preserve_disagreement(self):
        def packet(reviewer, second_answer="Segmentation"):
            return {
                "artifact_class": "exp002-expert-review-packet", "reviewer_id": reviewer,
                "question_bank_sha256": "a" * 64, "status": "submitted",
                "independence_attestation": True, "model_access": False, "sealed_target_access": False,
                "decisions": [
                    {"question_id": "q1", "key_type": "exact", "decision": "reviewed", "answer": "Segmentation", "rationale_sha256": "b" * 64},
                    {"question_id": "q2", "key_type": "exact", "decision": "reviewed", "answer": second_answer, "rationale_sha256": "c" * 64},
                ],
            }
        agreed = freeze_answer_key_from_packets([packet("r1"), packet("r2"), packet("r3")], ["q1", "q2"], question_bank="experiments/exp002-qwen3-followup/question-bank-manifest.json", question_bank_sha256="a" * 64)
        self.assertEqual(agreed["status"], "frozen")
        self.assertEqual(agreed["records"][0]["expected"], "Segmentation")
        disagreed = freeze_answer_key_from_packets([packet("r1"), packet("r2", "Trimming"), packet("r3")], ["q1", "q2"], question_bank="experiments/exp002-qwen3-followup/question-bank-manifest.json", question_bank_sha256="a" * 64)
        self.assertEqual(disagreed["records"][1]["key_type"], "rubric_required")

    def test_freeze_rejects_missing_exact_answer(self):
        packet = {"artifact_class": "exp002-expert-review-packet", "reviewer_id": "r1", "question_bank_sha256": "a" * 64, "status": "submitted", "independence_attestation": True, "model_access": False, "sealed_target_access": False, "decisions": [{"question_id": "q1", "key_type": "exact", "decision": "reviewed", "rationale_sha256": "b" * 64}]}
        packets = [dict(packet, reviewer_id=reviewer) for reviewer in ("r1", "r2", "r3")]
        with self.assertRaises(Exp002AnswerKeyError):
            freeze_answer_key_from_packets(packets, ["q1"], question_bank="experiments/exp002-qwen3-followup/question-bank-manifest.json", question_bank_sha256="a" * 64)


if __name__ == "__main__":
    unittest.main()
