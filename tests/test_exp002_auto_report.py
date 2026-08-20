import hashlib
import unittest

from latent_triz.exp002_auto_report import Exp002AutoPublicationError, verify_auto_publication


class Exp002AutoReportTests(unittest.TestCase):
    def setUp(self):
        self.asset = b"immutable score bytes"
        self.digest = hashlib.sha256(self.asset).hexdigest()
        self.result = {
            "artifact_class": "exp002-auto-result",
            "protocol_id": "exp002-auto-v1.0.0",
            "model_id": "openai-community/gpt2",
            "revision": "607a30d783dfa663caf39e06633721c8d4cfcd7e",
            "status": "null",
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
        }

    def test_accepts_claim_free_package_with_exact_external_score_hash(self):
        manifest = {
            "artifact_class": "exp002-auto-publication-manifest",
            "protocol_id": "exp002-auto-v1.0.0",
            "status": "ready",
            "packages": [{
                "model_id": self.result["model_id"],
                "revision": self.result["revision"],
                "terminal_status": "null",
                "result_sha256": hashlib.sha256(b"result").hexdigest(),
            }],
            "external_score_assets": [{"locator": "artifacts/exp002-auto/gpt2/scores.json", "sha256": self.digest}],
            "scientific_status": "exploratory", "claim_ids": [],
            "evidence_eligible": False,
            "expert_validated": False,
        }
        verify_auto_publication(
            manifest=manifest, results=[self.result],
            read_external_asset=lambda locator: self.asset,
        )

    def test_rejects_mutated_asset_or_promoted_claim(self):
        manifest = {
            "artifact_class": "exp002-auto-publication-manifest",
            "protocol_id": "exp002-auto-v1.0.0", "status": "ready", "packages": [],
            "external_score_assets": [{"locator": "artifacts/exp002-auto/gpt2/scores.json", "sha256": self.digest}],
            "scientific_status": "exploratory", "claim_ids": [], "evidence_eligible": False, "expert_validated": False,
        }
        with self.assertRaises(Exp002AutoPublicationError):
            verify_auto_publication(manifest=manifest, results=[{**self.result, "claim_ids": ["H1"]}], read_external_asset=lambda locator: self.asset)
        with self.assertRaises(Exp002AutoPublicationError):
            verify_auto_publication(manifest=manifest, results=[self.result], read_external_asset=lambda locator: b"mutated")


if __name__ == "__main__":
    unittest.main()
