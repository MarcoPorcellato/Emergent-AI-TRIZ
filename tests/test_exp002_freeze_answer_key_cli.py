import json
import tempfile
import unittest
from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("exp002_freeze_answer_key", ROOT / "scripts/exp002_freeze_answer_key.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Exp002FreezeAnswerKeyCliTests(unittest.TestCase):
    def _packet(self, reviewer, answer="Segmentation"):
        # The helper is tested with a reduced question-id list through the
        # production freeze function; file-level refusal is tested below.
        return {"artifact_class": "exp002-expert-review-packet", "reviewer_id": reviewer, "question_bank_sha256": "a" * 64, "status": "submitted", "independence_attestation": True, "model_access": False, "sealed_target_access": False, "decisions": [{"question_id": "q1", "key_type": "exact", "decision": "reviewed", "answer": answer, "rationale_sha256": "b" * 64}]}

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "answer-key.json"
            output.write_text("sentinel", encoding="utf-8")
            packets = Path(directory) / "packets.json"
            packets.write_text("[]", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                MODULE.freeze_from_files(packets_path=packets, output_path=output, root=ROOT)
            self.assertEqual(output.read_text(encoding="utf-8"), "sentinel")


if __name__ == "__main__":
    unittest.main()
