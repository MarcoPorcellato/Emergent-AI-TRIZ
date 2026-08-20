import json
import tempfile
import unittest
from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("exp002_validate_transfer_corpus", ROOT / "scripts/exp002_validate_transfer_corpus.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Exp002TransferCorpusCliTests(unittest.TestCase):
    def test_empty_design_template_is_reported_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corpus.json"
            path.write_text(json.dumps({"artifact_class": "exp002-transfer-corpus", "status": "design_ready_no_model", "records": [], "model_access": False, "sealed_target_access": False}), encoding="utf-8")
            result = MODULE.audit_corpus(path, root=ROOT)
            self.assertEqual(result["status"], "design_incomplete")

    def test_answer_fields_and_model_access_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corpus.json"
            path.write_text(json.dumps({"artifact_class": "exp002-transfer-corpus", "status": "design_ready_no_model", "records": [{"expected_answer": "A"}], "model_access": False, "sealed_target_access": False}), encoding="utf-8")
            with self.assertRaises(ValueError):
                MODULE.audit_corpus(path, root=ROOT)
            path.write_text(json.dumps({"artifact_class": "exp002-transfer-corpus", "status": "design_ready_no_model", "records": [], "model_access": True, "sealed_target_access": False}), encoding="utf-8")
            with self.assertRaises(ValueError):
                MODULE.audit_corpus(path, root=ROOT)


if __name__ == "__main__":
    unittest.main()
