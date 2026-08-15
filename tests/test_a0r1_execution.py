from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0r1_execution import A0R1ExecutionError, verify_a0r1_execution_contract


class A0R1ExecutionTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]
    implementation = root / "experiments/a0r1-independent-proxy/implementation.json"

    def _mutated_contract(self, mutator) -> Path:
        payload = json.loads(self.implementation.read_text(encoding="utf-8"))
        mutator(payload)
        directory = Path(tempfile.mkdtemp(prefix="a0r1-execution-"))
        path = directory / "implementation.json"
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        return path

    def test_tracked_execution_contract_passes_without_model_access(self) -> None:
        result = verify_a0r1_execution_contract(self.root)
        self.assertEqual("pass", result["status"])
        self.assertEqual(6, result["runtime_files_bound"])
        self.assertGreaterEqual(result["code_files_verified"], 5)
        self.assertFalse(result["model_output_accessed"])

    def test_input_hash_drift_fails_closed(self) -> None:
        path = self._mutated_contract(lambda value: value["protocol"].update({"cases_sha256": "0" * 64}))
        with self.assertRaises(A0R1ExecutionError):
            verify_a0r1_execution_contract(self.root, path)

    def test_code_hash_drift_fails_closed(self) -> None:
        path = self._mutated_contract(
            lambda value: value["implementation_code"]["bound_code_files"][0].update({"sha256": "0" * 64})
        )
        with self.assertRaises(A0R1ExecutionError):
            verify_a0r1_execution_contract(self.root, path)

    def test_pending_binding_never_passes(self) -> None:
        def mutate(value):
            value["implementation_code"] = {
                "binding_state": "pending",
                "bound_code_files": [],
                "pending_code_binding": ["src/latent_triz/a0r1_analysis.py"],
            }

        with self.assertRaises(A0R1ExecutionError):
            verify_a0r1_execution_contract(self.root, self._mutated_contract(mutate))


if __name__ == "__main__":
    unittest.main()
