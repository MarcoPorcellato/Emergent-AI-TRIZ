from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz import a0r2c1_authorization as authorization_module  # noqa: E402
from latent_triz.a0r2c1_authorization import (  # noqa: E402
    A0R2C1AuthorizationError,
    verify_a0r2c1_authorization,
    verify_a0r2c1_contract,
)


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_RECEIPT = ROOT / "results/a0r2c1/preexecution/synthetic-authorization.json"


def _valid_authorization_payload() -> dict[str, object]:
    contract = ROOT / "experiments/a0r2c1-tokenizer-correction/contract.json"
    return {
        "artifact_class": "a0r2c1-sealed-execution-authorization",
        "receipt_id": "a0r2c1-sealed-execution-authorization-v1",
        "receipt_status": "authorized",
        "recorded_at": "2026-08-16T18:00:00Z",
        "source": "explicit_operator_authorization",
        "bindings": {"contract_sha256": hashlib.sha256(contract.read_bytes()).hexdigest()},
        "scope": {"run_id": "a0r2c1-v1.0.0-f8027fd0-r1", "maximum_material_runs": 1, "analysis_target_content_reads": 1, "maximum_wall_seconds": 1800, "maximum_peak_rss_bytes": 8589934592, "maximum_new_dense_output_bytes": 67108864, "local_only": True, "network_access": False, "generation_allowed": False, "no_tuning": True, "no_model_substitution": True, "no_protocol_change": True, "publish_every_terminal_outcome": True},
        "access": {"model_loaded": False, "model_output_accessed": False, "sealed_targets_accessed": False},
    }


def _verify_payload(payload: dict[str, object]) -> dict[str, object]:
    original_json = authorization_module._json

    def synthetic_json(path: Path, label: str) -> dict[str, object]:
        if path == SYNTHETIC_RECEIPT:
            return payload
        return original_json(path, label)

    with patch.object(authorization_module, "_json", side_effect=synthetic_json):
        return verify_a0r2c1_authorization(ROOT, SYNTHETIC_RECEIPT)


class A0R2C1AuthorizationTests(unittest.TestCase):
    def test_public_c1_contract_and_authorization_verify(self) -> None:
        contract = verify_a0r2c1_contract(ROOT)
        receipt = _verify_payload(_valid_authorization_payload())
        self.assertEqual("pass", contract["status"])
        self.assertEqual("pass", receipt["status"])
        self.assertFalse(receipt["model_output_accessed"])
        self.assertFalse(receipt["sealed_targets_accessed"])

    def test_missing_authorization_fails_closed(self) -> None:
        with self.assertRaisesRegex(A0R2C1AuthorizationError, "cannot read corrective authorization"):
            verify_a0r2c1_authorization(ROOT, ROOT / "results/a0r2c1/missing.json")

    def test_mutated_authorization_fails_schema_before_material_access(self) -> None:
        payload = _valid_authorization_payload()
        payload["scope"]["run_id"] = "not-the-frozen-run"
        with self.assertRaisesRegex(A0R2C1AuthorizationError, "schema validation"):
            _verify_payload(payload)

    def test_contract_does_not_open_sealed_targets(self) -> None:
        with patch("latent_triz.a0r2c1_authorization._sha256") as digest:
            digest.side_effect = lambda path: "0" * 64 if "sealed_targets" in str(path) else __import__("hashlib").sha256(path.read_bytes()).hexdigest()
            result = verify_a0r2c1_contract(ROOT)
        self.assertEqual("pass", result["status"])
        self.assertNotIn("sealed_targets", " ".join(str(call.args[0]) for call in digest.call_args_list))


if __name__ == "__main__":
    unittest.main()
