import json
from pathlib import Path
import unittest

from latent_triz.exp002_answer_key import Exp002AnswerKeyError, validate_answer_key


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


if __name__ == "__main__":
    unittest.main()
