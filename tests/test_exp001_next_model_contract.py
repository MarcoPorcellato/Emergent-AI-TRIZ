import json
import tempfile
import unittest
from pathlib import Path

from latent_triz.exp001_next_model_contract import (
    NEXT_MODELS,
    NextModelContractError,
    validate_next_model_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class NextModelContractTests(unittest.TestCase):
    def test_refuses_material_execution_without_receipts(self):
        for model_id in NEXT_MODELS:
            with self.assertRaises(NextModelContractError):
                validate_next_model_contract(ROOT, model_id, material_execution=True)

    def test_target_free_audit_accepts_unapproved_checkpoint(self):
        for model_id in NEXT_MODELS:
            audit = validate_next_model_contract(ROOT, model_id, material_execution=False)
            self.assertFalse(audit["model_accessed"])
            self.assertFalse(audit["sealed_targets_accessed"])

    def test_refuses_unknown_model_without_model_or_target_access(self):
        with self.assertRaises(NextModelContractError):
            validate_next_model_contract(ROOT, "unknown/model")

    def test_contract_records_complementary_architecture_and_context(self):
        self.assertEqual(NEXT_MODELS["EleutherAI/gpt-neo-125m"]["model_type"], "gpt_neo")
        self.assertEqual(NEXT_MODELS["Qwen/Qwen2.5-0.5B"]["model_type"], "qwen2")
        self.assertEqual(NEXT_MODELS["Qwen/Qwen2.5-0.5B"]["tokenizer_max_length"], 131072)
        self.assertEqual(NEXT_MODELS["Qwen/Qwen2.5-0.5B"]["model_context"], 32768)


if __name__ == "__main__":
    unittest.main()
