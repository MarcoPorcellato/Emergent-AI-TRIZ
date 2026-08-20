import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from latent_triz.exp002_auto_material import (
    Exp002AutoMaterialError,
    prepare_auto_shard,
    run_authorized_auto_shard,
    verify_runtime_receipt,
)
from latent_triz.exp002_followup import EXPECTED_MODELS


class Exp002AutoMaterialTests(unittest.TestCase):
    def setUp(self):
        self.model_id = "Qwen/Qwen3-0.6B-Base"
        self.revision = EXPECTED_MODELS[self.model_id]
        self.protocol_sha = "a" * 64
        self.schedule_sha = "b" * 64
        self.manifest_sha = "c" * 64
        models = [{"model_id": key, "revision": value} for key, value in EXPECTED_MODELS.items()]
        self.dossier = {
            "artifact_class": "exp002-auto-approval-dossier", "protocol_id": "exp002-auto-v1.0.0",
            "protocol_sha256": self.protocol_sha, "schedule_sha256": self.schedule_sha,
            "input_manifest_sha256": self.manifest_sha, "status": "authorized", "claim_ids": [],
            "exact_models": models,
            "material_bindings": {key: "e" * 64 for key in ("runner_sha256", "adapter_sha256", "analysis_sha256", "sealed_key_schema_sha256", "model_registry_sha256", "public_key_template_sha256")},
            "permissions": {"model_load": True, "network": False, "generation": False, "sealed_target_read": "exactly_one_at_analysis_boundary"},
            "limits": {"wall_time_seconds_per_shard": 1800, "peak_rss_bytes_per_shard": 8589934592, "new_score_output_bytes_per_model": 134217728},
            "operator_approval": {"granted": True, "operator_id": "MarcoPorcellato", "approval_text_sha256": "d" * 64},
            "shards": [{"stage_id": "AUTO-2", "shard_id": "auto-2-factual-01"}],
        }
        self.gate = {"resource_decision": "admit", "admission_active": False, "queue_count": 0}

    def _receipt_and_root(self, root: Path):
        payload = b"synthetic-runtime"
        (root / "config.json").write_bytes(payload)
        return {"status": "integrity_verified", "model": {"id": self.model_id, "revision": self.revision}, "runtime_files": [{"path": "config.json", "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}]}

    def test_preflight_refuses_before_adapter_on_unapproved_or_busy_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = self._receipt_and_root(root)
            calls = []
            unapproved = copy.deepcopy(self.dossier)
            unapproved["status"] = "approval_requested"
            unapproved["operator_approval"]["granted"] = False
            with self.assertRaises(Exp002AutoMaterialError):
                run_authorized_auto_shard(
                    root=root, run_id="exp002-auto-test", dossier=unapproved, protocol_sha256=self.protocol_sha,
                    schedule_sha256=self.schedule_sha, input_manifest_sha256=self.manifest_sha, gate=self.gate,
                    model_id=self.model_id, stage_id="AUTO-2", shard_id="auto-2-factual-01", runtime_receipt=receipt,
                    model_root=root, public_rows=[], adapter_factory=lambda: calls.append("load"),
                    analysis=lambda *_: {"status": "null"}, key_reader=lambda: {},
                )
            self.assertEqual(calls, [])
            with self.assertRaises(Exp002AutoMaterialError):
                prepare_auto_shard(
                    dossier=self.dossier, protocol_sha256=self.protocol_sha, schedule_sha256=self.schedule_sha,
                    input_manifest_sha256=self.manifest_sha, gate={"resource_decision": "admit", "admission_active": True, "queue_count": 0},
                    model_id=self.model_id, stage_id="AUTO-2", shard_id="auto-2-factual-01", runtime_receipt=receipt, model_root=root,
                )

    def test_runtime_hash_is_streamed_and_mutation_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = self._receipt_and_root(root)
            checked = verify_runtime_receipt(receipt=receipt, model_id=self.model_id, revision=self.revision, model_root=root)
            self.assertEqual(checked["runtime_files_checked"], 1)
            (root / "config.json").write_bytes(b"mutated")
            with self.assertRaises(Exp002AutoMaterialError):
                verify_runtime_receipt(receipt=receipt, model_id=self.model_id, revision=self.revision, model_root=root)

    def test_fake_execution_reads_key_once_and_publishes_terminal_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = self._receipt_and_root(root)
            rows = [{"record_id": "exp002-auto-factual-number-01", "prompt": "public", "candidate_descriptions": ["a", "b", "c", "d"], "family": "principle_number_to_name"}]
            reads = []
            class FakeAdapter:
                model_loaded = True
                def score_candidate_description(self, prompt, candidate):
                    return float(len(candidate))
            def analysis(scored, reader):
                key = reader()
                self.assertEqual(key["status"], "sealed")
                return {"status": "null", "record_count": len(scored)}
            result = run_authorized_auto_shard(
                root=root, run_id="exp002-auto-test", dossier=self.dossier, protocol_sha256=self.protocol_sha,
                schedule_sha256=self.schedule_sha, input_manifest_sha256=self.manifest_sha, gate=self.gate,
                model_id=self.model_id, stage_id="AUTO-2", shard_id="auto-2-factual-01", runtime_receipt=receipt,
                model_root=root, public_rows=rows, adapter_factory=FakeAdapter,
                analysis=analysis, key_reader=lambda: reads.append(1) or {"status": "sealed"},
            )
            self.assertEqual(result["status"], "null")
            self.assertEqual(reads, [1])
            package = root / result["package"]
            self.assertTrue((package / "publication-manifest.json").is_file())
            envelope = json.loads((package / "execution-receipt.json").read_text())
            self.assertEqual(envelope["access"]["target_reads"], 1)
            self.assertFalse(envelope["evidence_eligible"])


if __name__ == "__main__":
    unittest.main()
