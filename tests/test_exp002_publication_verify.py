import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from exp002_publication_verify import PublicationVerificationError, verify_publication_manifest  # noqa: E402


class Exp002PublicationVerifyTests(unittest.TestCase):
    def test_published_manifest_passes(self):
        result = verify_publication_manifest("results/exp002/preexecution/publication-manifest.json", root=ROOT)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["packages"], 7)
        self.assertEqual(len(result["verified_external_assets"]), 7)

    def test_missing_and_mutated_external_assets_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "schemas").mkdir()
            (root / "results").mkdir()
            (root / "schemas/exp002-publication-manifest.schema.json").write_text((ROOT / "schemas/exp002-publication-manifest.schema.json").read_text(encoding="utf-8"), encoding="utf-8")
            asset = root / "asset.bin"
            asset.write_bytes(b"stable")
            digest = hashlib.sha256(b"stable").hexdigest()
            manifest = {"artifact_class": "exp002-publication-manifest", "protocol_id": "exp002-qwen3-followup-v1.0.0", "status": "published", "packages": [], "external_dense_assets": [{"locator": "asset.bin", "sha256": digest}], "claim_ids": [], "evidence_eligible": False, "expert_validated": False}
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(verify_publication_manifest(path, root=root)["status"], "pass")
            asset.write_bytes(b"mutated")
            with self.assertRaises(PublicationVerificationError):
                verify_publication_manifest(path, root=root)
            asset.unlink()
            with self.assertRaises(PublicationVerificationError):
                verify_publication_manifest(path, root=root)

    def test_missing_or_mutated_package_binding_fails_closed(self):
        manifest_path = ROOT / "results/exp002/preexecution/publication-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        package = manifest["packages"][0]
        package_path = ROOT / package["package_locator"]
        artifact = package_path / "report.md"
        original = artifact.read_bytes()
        try:
            artifact.write_bytes(original + b"\nmutation")
            with self.assertRaises(PublicationVerificationError):
                verify_publication_manifest(manifest_path, root=ROOT)
        finally:
            artifact.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
