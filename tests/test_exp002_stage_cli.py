"""No-model tests for the EXP-002A material CLI boundary."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("run_exp002_stage", ROOT / "scripts/run_exp002_stage.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Exp002StageCliTests(unittest.TestCase):
    def test_runtime_receipt_is_stream_verified_without_model_import(self) -> None:
        model_id = "Qwen/Qwen2.5-0.5B"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model_root = root / "model"
            model_root.mkdir()
            payload = b"runtime-fixture"
            (model_root / "config.json").write_bytes(payload)
            receipt = root / "receipt.json"
            receipt.write_text(json.dumps({
                "model_id": model_id,
                "revision": MODULE.EXPECTED_MODELS[model_id],
                "status": "integrity_verified",
                "runtime_files": [{"path": "config.json", "sha256": hashlib.sha256(payload).hexdigest()}],
            }), encoding="utf-8")
            old_receipt = MODULE.MODEL_RECEIPTS[model_id]
            old_root = MODULE.MODEL_ROOTS[model_id]
            MODULE.MODEL_RECEIPTS[model_id] = receipt
            MODULE.MODEL_ROOTS[model_id] = model_root
            try:
                result = MODULE.verify_runtime(model_id)
            finally:
                MODULE.MODEL_RECEIPTS[model_id] = old_receipt
                MODULE.MODEL_ROOTS[model_id] = old_root
            self.assertEqual(result["runtime_files_checked"], 1)

    def test_runtime_receipt_rejects_path_traversal_before_read(self) -> None:
        model_id = "Qwen/Qwen2.5-0.5B"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt = root / "receipt.json"
            receipt.write_text(json.dumps({
                "model_id": model_id,
                "revision": MODULE.EXPECTED_MODELS[model_id],
                "status": "integrity_verified",
                "runtime_files": [{"path": "../outside", "sha256": "0" * 64}],
            }), encoding="utf-8")
            old_receipt = MODULE.MODEL_RECEIPTS[model_id]
            old_root = MODULE.MODEL_ROOTS[model_id]
            MODULE.MODEL_RECEIPTS[model_id] = receipt
            MODULE.MODEL_ROOTS[model_id] = root / "model"
            try:
                with self.assertRaises(RuntimeError):
                    MODULE.verify_runtime(model_id)
            finally:
                MODULE.MODEL_RECEIPTS[model_id] = old_receipt
                MODULE.MODEL_ROOTS[model_id] = old_root


if __name__ == "__main__":
    unittest.main()
