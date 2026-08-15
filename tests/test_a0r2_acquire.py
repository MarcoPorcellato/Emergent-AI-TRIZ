from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz import a0r2_acquire
from latent_triz.a0r2_acquisition import A0R2AcquisitionError


class A0R2AcquireCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract_path = ROOT / "experiments/a0r2-independent-model/acquisition-contract.json"

    def test_tracked_contract_matches_executable_identity(self) -> None:
        payload = a0r2_acquire._load_and_verify_contract(self.contract_path)
        self.assertEqual(payload["expected_total_bytes"], 727058433)

    def test_contract_identity_mutation_fails_closed(self) -> None:
        payload = json.loads(self.contract_path.read_text(encoding="utf-8"))
        payload["model"]["revision"] = "0" * 40
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contract.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(A0R2AcquisitionError, "identity mismatch"):
                a0r2_acquire._load_and_verify_contract(path)

    def test_exclusive_receipt_writer_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            a0r2_acquire._write_exclusive(path, {"status": "first"})
            with self.assertRaisesRegex(A0R2AcquisitionError, "refusing to overwrite"):
                a0r2_acquire._write_exclusive(path, {"status": "second"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"status": "first"})

    def test_receipt_contract_hash_mutation_fails_before_external_access(self) -> None:
        receipt = {
            "artifact_class": "a0r2-acquisition-receipt",
            "status": "pass",
            "integrity_status": "integrity_verified",
            "contract_sha256": "0" * 64,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(A0R2AcquisitionError, "contract hash mismatch"):
                a0r2_acquire._verify_receipt(self.contract_path, path)


if __name__ == "__main__":
    unittest.main()
