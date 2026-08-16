from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.a0r2_execution import A0R2ExecutionError, verify_a0r2_execution_contract


class A0R2ExecutionTests(unittest.TestCase):
    def test_frozen_contract_verifies_without_model_or_target_access(self) -> None:
        result = verify_a0r2_execution_contract(ROOT)
        self.assertEqual("pass", result["status"])
        self.assertEqual(12, result["code_files_verified"])
        self.assertEqual(9, result["runtime_files_bound"])
        self.assertEqual(0, result["runtime_files_verified"])
        self.assertFalse(result["model_output_accessed"])
        self.assertFalse(result["sealed_targets_accessed"])

    def test_binding_mutation_fails_closed(self) -> None:
        implementation = json.loads(
            (ROOT / "experiments/a0r2-independent-model/implementation.json").read_text(encoding="utf-8")
        )
        implementation["bindings"]["study_protocol_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "implementation.json"
            path.write_text(json.dumps(implementation), encoding="utf-8")
            with self.assertRaisesRegex(A0R2ExecutionError, "binding mismatch"):
                verify_a0r2_execution_contract(ROOT, path)

    def test_runtime_snapshot_mismatch_fails_before_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model_root = Path(directory)
            with self.assertRaisesRegex(A0R2ExecutionError, "runtime file missing"):
                verify_a0r2_execution_contract(ROOT, model_root=model_root)


if __name__ == "__main__":
    unittest.main()
