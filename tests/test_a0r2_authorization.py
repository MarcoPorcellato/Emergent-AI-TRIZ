from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz import a0r2_authorization as authorization  # noqa: E402
from latent_triz.a0r2_authorization import (
    A0R2AuthorizationError,
    verify_a0r2_sealed_execution_authorization,
)


class A0R2AuthorizationTests(unittest.TestCase):
    def test_receipt_verifies_without_model_or_target_access(self) -> None:
        result = verify_a0r2_sealed_execution_authorization(ROOT)
        self.assertEqual("pass", result["status"])
        self.assertFalse(result["model_output_accessed"])
        self.assertFalse(result["sealed_targets_accessed"])

    def test_binding_mutation_fails_closed(self) -> None:
        receipt_path = ROOT / "results/a0r2/preexecution/smollm2-360m-f8027fd0/sealed-execution-authorization.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["bindings"]["study_protocol_sha256"] = "0" * 64
        original_read_json = authorization._read_json

        def read_json(path: Path, label: str):
            if path.resolve() == receipt_path.resolve():
                return receipt
            return original_read_json(path, label)

        with patch.object(authorization, "_read_json", side_effect=read_json):
            with self.assertRaisesRegex(A0R2AuthorizationError, "binding mismatch"):
                verify_a0r2_sealed_execution_authorization(ROOT)

    def test_scope_mutation_fails_closed(self) -> None:
        receipt_path = ROOT / "results/a0r2/preexecution/smollm2-360m-f8027fd0/sealed-execution-authorization.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["scope"]["generation_allowed"] = True
        original_read_json = authorization._read_json

        def read_json(path: Path, label: str):
            if path.resolve() == receipt_path.resolve():
                return receipt
            return original_read_json(path, label)

        with patch.object(authorization, "_read_json", side_effect=read_json):
            with self.assertRaisesRegex(A0R2AuthorizationError, "schema validation"):
                verify_a0r2_sealed_execution_authorization(ROOT)


if __name__ == "__main__":
    unittest.main()
