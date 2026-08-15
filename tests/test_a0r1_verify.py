from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path
from shutil import copytree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0r1_verify import A0R1VerifyError, _require_equal, verify_a0r1_foundation


class A0R1VerifyTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]
    protocol = root / "experiments/a0r1-independent-proxy/protocol.json"

    def test_tracked_foundation_reproduces_byte_for_byte(self) -> None:
        result = verify_a0r1_foundation(self.root)
        self.assertEqual("pass", result["status"])
        self.assertFalse(result["model_output_accessed"])
        self.assertEqual(4, result["corpus_files_verified"])
        self.assertEqual(4, result["preoutput_files_verified"])
        self.assertEqual("frozen", result["protocol_status"])
        self.assertTrue(result["protocol_file_matches_frozen"])
        self.assertEqual("frozen", result["freeze_status"])
        self.assertGreater(result["freeze_files_verified"], 5)

    def test_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "expected"
            actual = root / "actual"
            expected.mkdir()
            actual.mkdir()
            (expected / "artifact.json").write_text("expected", encoding="utf-8")
            (actual / "artifact.json").write_text("changed", encoding="utf-8")
            with self.assertRaises(A0R1VerifyError):
                _require_equal(expected, actual, ("artifact.json",))

    def test_frozen_protocol_requires_frozen_snapshot_match(self) -> None:
        original = self.protocol.read_bytes()
        frozen = (self.root / "results/a0r1/freeze/protocol-frozen.json").read_text(encoding="utf-8")
        protocol = json.loads(frozen)
        protocol["protocol_status"] = "frozen"
        protocol["status"] = "frozen"
        protocol["protocol_id"] = protocol["protocol_id"] + "-tamper"
        try:
            self.protocol.write_text(json.dumps(protocol, sort_keys=True), encoding="utf-8")
            with self.assertRaises(A0R1VerifyError):
                verify_a0r1_foundation(self.root)
        finally:
            self.protocol.write_bytes(original)

    def test_planned_protocol_paths_skip_freeze_artifact_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real_root = self.root
            planned_protocol = real_root / "results/a0r1/freeze/protocol-planned.json"
            copytree(real_root / "data", root / "data")
            copytree(real_root / "results", root / "results")
            copytree(real_root / "experiments", root / "experiments")

            (root / "experiments/a0r1-independent-proxy/protocol.json").write_bytes(
                planned_protocol.read_bytes()
            )
            summary = verify_a0r1_foundation(root)
            self.assertEqual("pass", summary["status"])
            self.assertEqual("planned", summary["protocol_status"])
            self.assertEqual("not_applicable", summary["freeze_status"])
            self.assertEqual(0, summary["freeze_files_verified"])

    def test_frozen_manifest_hash_mismatch_fails(self) -> None:
        freeze_manifest = self.root / "results/a0r1/freeze/freeze-manifest.json"
        original = freeze_manifest.read_text(encoding="utf-8")
        payload = json.loads(original)
        payload["planned_protocol_snapshot_hash"] = "0" * 64
        try:
            freeze_manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            with self.assertRaises(A0R1VerifyError):
                verify_a0r1_foundation(self.root)
        finally:
            freeze_manifest.write_text(original, encoding="utf-8")

    def test_failed_freeze_manifest_never_verifies_as_pass(self) -> None:
        freeze_manifest = self.root / "results/a0r1/freeze/freeze-manifest.json"
        original = freeze_manifest.read_text(encoding="utf-8")
        payload = json.loads(original)
        payload["status"] = "failed"
        try:
            freeze_manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            with self.assertRaises(A0R1VerifyError):
                verify_a0r1_foundation(self.root)
        finally:
            freeze_manifest.write_text(original, encoding="utf-8")
