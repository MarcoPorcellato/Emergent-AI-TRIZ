from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from latent_triz.exp001_qwen_acquisition import (
    FILES,
    QwenAcquisitionError,
    _blob_sha1,
    _verify_file,
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


if __name__ == "__main__":
    unittest.main()
