"""No-model tests for C2 corrective-contract authorization gates."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0r2c2_authorization import (  # noqa: E402
    A0R2C2AuthorizationError,
    verify_a0r2c2_authorization,
    verify_a0r2c2_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class A0R2C2AuthorizationTests(unittest.TestCase):
    def test_preoutput_contract_verifies_without_model_or_targets(self) -> None:
        self.assertEqual("pass", verify_a0r2c2_contract(ROOT)["status"])

    def test_missing_operator_receipt_fails_before_material_access(self) -> None:
        with self.assertRaisesRegex(A0R2C2AuthorizationError, "cannot read C2 authorization receipt"):
            verify_a0r2c2_authorization(
                ROOT,
                "results/a0r2c2/preexecution/intentionally-missing-authorization.json",
            )


if __name__ == "__main__":
    unittest.main()
