from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request

from latent_triz.exp001_qwen_acquisition import (
    _BoundedRedirect,
    FILES,
    QwenAcquisitionError,
    _blob_sha1,
    _verify_file,
    validate_authorization,
)


class QwenAcquisitionTests(unittest.TestCase):
    def test_exact_allowlist_and_total_are_bounded(self):
        self.assertEqual(list(FILES), [
            "config.json", "generation_config.json", "merges.txt",
            "model.safetensors", "tokenizer.json", "tokenizer_config.json", "vocab.json",
        ])
        self.assertLess(sum(size for size, _oid, _kind in FILES.values()), 1_610_612_736)

    def test_verification_uses_streaming_hashes_and_rejects_wrong_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = b"wrong"
            path = root / "config.json"
            path.write_bytes(payload)
            with self.assertRaises(QwenAcquisitionError):
                _verify_file(path, "config.json")

    def test_git_blob_digest_matches_reference_formula(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x"
            path.write_bytes(b"abc")
            expected = hashlib.sha1(b"blob 3\x00abc").hexdigest()
            self.assertEqual(_blob_sha1(path, 3), expected)

    def test_unknown_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(QwenAcquisitionError):
                _verify_file(Path(tmp) / "x", "README.md")

    def test_authorization_must_bind_every_runtime_file_and_permission(self):
        payload = {
            "status": "operator_authorized",
            "model_id": "Qwen/Qwen3-0.6B-Base",
            "revision": "da87bfb608c14b7cf20ba1ce41287e8de496c0cd",
            "license_id": "Apache-2.0",
            "disk_budget_bytes": 1610612736,
            "runtime_files": [
                {"path": name, "size_bytes": size, "source_oid": oid, "source_kind": kind}
                for name, (size, oid, kind) in FILES.items()
            ],
            "permissions": {
                "download_runtime_files_only": True,
                "integrity_receipt": True,
                "model_load": False,
                "feasibility": False,
                "sealed_execution": False,
                "sealed_targets": False,
            },
        }
        validate_authorization(payload)
        payload["runtime_files"][0]["size_bytes"] += 1
        with self.assertRaises(QwenAcquisitionError):
            validate_authorization(payload)

    def test_redirect_handler_rejects_untrusted_host(self):
        handler = _BoundedRedirect()
        self.assertIsNone(handler.redirect_request(Request("https://huggingface.co/source"), None, 302, "Found", {}, "https://evil.example/x"))


if __name__ == "__main__":
    unittest.main()
