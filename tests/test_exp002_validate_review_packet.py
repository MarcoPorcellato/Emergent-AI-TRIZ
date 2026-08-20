import json
from pathlib import Path
import tempfile
import unittest

from scripts.exp002_validate_review_packet import _question_ids, validate_file


ROOT = Path(__file__).resolve().parents[1]


class Exp002ValidateReviewPacketTests(unittest.TestCase):
    def test_valid_complete_packet_is_audited(self):
        question_ids, question_bank_sha256 = _question_ids(ROOT)
        packet = {
            "artifact_class": "exp002-expert-review-packet",
            "reviewer_id": "reviewer-cli",
            "question_bank_sha256": question_bank_sha256,
            "status": "submitted",
            "independence_attestation": True,
            "model_access": False,
            "sealed_target_access": False,
            "decisions": [
                {"question_id": question_id, "key_type": "exact", "decision": "reviewed", "answer": "A", "rationale_sha256": "a" * 64}
                for question_id in question_ids
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "packet.json"
            path.write_text(json.dumps(packet), encoding="utf-8")
            result = validate_file(path, root=ROOT)
        self.assertEqual(result["status"], "valid_packet")
        self.assertEqual(result["question_count"], 351)
        self.assertFalse(result["model_access"])
        self.assertFalse(result["sealed_target_access"])


if __name__ == "__main__":
    unittest.main()
