import unittest

from latent_triz.exp002_expert_review import Exp002ExpertReviewError, summarize_review_packets, validate_review_packets


def _packet(reviewer_id, question_ids=("q1", "q2")):
    return {
        "artifact_class": "exp002-expert-review-packet",
        "reviewer_id": reviewer_id,
        "question_bank_sha256": "a" * 64,
        "status": "submitted",
        "independence_attestation": True,
        "model_access": False,
        "sealed_target_access": False,
        "decisions": [{"question_id": qid, "key_type": "exact", "decision": "reviewed", "rationale_sha256": "b" * 64} for qid in question_ids],
    }


class Exp002ExpertReviewTests(unittest.TestCase):
    def test_three_independent_packets_cover_the_bank(self):
        packets = [_packet(f"reviewer-{index}") for index in range(3)]
        summary = validate_review_packets(packets, ["q1", "q2"], question_bank_sha256="a" * 64)
        self.assertEqual(summary["reviewer_count"], 3)
        self.assertTrue(summary["full_coverage"])
        self.assertEqual(summarize_review_packets(packets, ["q1", "q2"])["status"], "ready_for_answer_key_freeze")

    def test_duplicate_reviewer_and_missing_coverage_fail_closed(self):
        with self.assertRaises(Exp002ExpertReviewError):
            validate_review_packets([_packet("same"), _packet("same"), _packet("third")], ["q1", "q2"], question_bank_sha256="a" * 64)
        with self.assertRaises(Exp002ExpertReviewError):
            validate_review_packets([_packet(f"reviewer-{index}", ("q1",)) for index in range(3)], ["q1", "q2"], question_bank_sha256="a" * 64)

    def test_model_or_target_access_is_forbidden(self):
        packets = [_packet(f"reviewer-{index}") for index in range(3)]
        packets[0]["model_access"] = True
        with self.assertRaises(Exp002ExpertReviewError):
            validate_review_packets(packets, ["q1", "q2"], question_bank_sha256="a" * 64)


if __name__ == "__main__":
    unittest.main()
