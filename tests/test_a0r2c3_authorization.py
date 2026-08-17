"""No-model, no-target tests for the C3 analysis-only authorization gate."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.a0r2c3_authorization import (  # noqa: E402
    A0R2C3AuthorizationError,
    verify_a0r2c3_authorization,
    verify_a0r2c3_contract,
)


class A0R2C3AuthorizationTests(unittest.TestCase):
    def test_contract_verifies_without_model_or_target_access(self) -> None:
        self.assertEqual("pass", verify_a0r2c3_contract(ROOT)["status"])

    def test_missing_operator_receipt_fails_before_target_access(self) -> None:
        with self.assertRaisesRegex(A0R2C3AuthorizationError, "cannot read C3 authorization receipt"):
            verify_a0r2c3_authorization(ROOT, "results/a0r2c3/preexecution/intentionally-missing.json")


if __name__ == "__main__":
    unittest.main()
