from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.validator import validate


class Lab01SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.schemas = {
            "manifest": self._load_schema("schemas/lab01-manifest.schema.json"),
            "receipt": self._load_schema("schemas/lab01-model-receipt.schema.json"),
            "run": self._load_schema("schemas/lab01-run.schema.json"),
        }

    def _load_schema(self, relpath: str) -> dict:
        path = self.repo_root / relpath
        return json.loads(path.read_text(encoding="utf-8"))

    def test_manifest_validates_and_is_didactic_only(self) -> None:
        manifest_path = self.repo_root / "experiments/lab01-model-anatomy/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(validate(manifest, self.schemas["manifest"]), [])
        self.assertEqual(manifest["artifact_class"], "model-instrumentation")
        self.assertTrue(manifest["empirical"])
        self.assertFalse(manifest["evidence_eligible"])
        self.assertEqual(manifest["claim_ids"], [])
        self.assertEqual(manifest["contract_state"], "selected")
        self.assertEqual(
            manifest["allowed_states"],
            [
                "unselected",
                "selected",
                "acquisition_planned",
                "acquired",
                "integrity_verified",
                "load_verified",
                "instrumentation_verified",
                "lab_ready",
            ],
        )

    def test_manifest_rejects_claim_ids_and_wrong_artifact_class(self) -> None:
        manifest = {
            "artifact_class": "model-instrumentation",
            "empirical": True,
            "evidence_eligible": False,
            "claim_ids": ["CLM-001"],
            "model": "EleutherAI/pythia-70m-deduped",
            "revision": "e93a9faa9c77e5d09219f6c868bfc7a1bd65593c",
            "license_id": "Apache-2.0",
            "contract_state": "selected",
            "allowed_states": [
                "unselected",
                "selected",
                "acquisition_planned",
                "acquired",
                "integrity_verified",
                "load_verified",
                "instrumentation_verified",
                "lab_ready",
            ],
            "gates": ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"],
            "byte_identical_structures": ["prompt_template.json"],
            "numeric_tolerance_by_backend_dtype": {"torch": {"float32": {"atol": 0.0, "rtol": 0.0}}},
        }
        issues = validate(manifest, self.schemas["manifest"])
        self.assertTrue(issues)
        self.assertTrue(any("maxItems" in issue.message for issue in issues))

    def test_receipt_validates_and_requires_state_transition_payload(self) -> None:
        receipt = {
            "artifact_class": "model-instrumentation",
            "empirical": True,
            "evidence_eligible": False,
            "claim_ids": [],
            "receipt_type": "selection",
            "state_before": "unselected",
            "state_after": "selected",
            "model": "EleutherAI/pythia-70m-deduped",
            "revision": "e93a9faa9c77e5d09219f6c868bfc7a1bd65593c",
            "receipt_time": "2026-08-13T10:00:00Z",
            "source_url": "https://huggingface.co/EleutherAI/pythia-70m-deduped/tree/e93a9faa9c77e5d09219f6c868bfc7a1bd65593c",
            "terms_url": "https://huggingface.co/EleutherAI/pythia-70m-deduped/blob/e93a9faa9c77e5d09219f6c868bfc7a1bd65593c/README.md",
            "license_id": "Apache-2.0",
            "runtime_files": [
                {"name": name, "sha256": "0" * 64, "size": 1}
                for name in (
                    "README.md",
                    "config.json",
                    "model.safetensors",
                    "special_tokens_map.json",
                    "tokenizer.json",
                    "tokenizer_config.json",
                )
            ],
            "notes": "selection receipt only",
        }
        self.assertEqual(validate(receipt, self.schemas["receipt"]), [])

    def test_receipt_rejects_claims_and_integrity_without_runtime_hashes(self) -> None:
        receipt = {
            "artifact_class": "model-instrumentation",
            "empirical": True,
            "evidence_eligible": False,
            "claim_ids": ["CLM-002"],
            "receipt_type": "integrity",
            "state_before": "acquired",
            "state_after": "integrity_verified",
            "model": "EleutherAI/pythia-70m-deduped",
            "revision": "e93a9faa9c77e5d09219f6c868bfc7a1bd65593c",
            "receipt_time": "2026-08-13T10:00:00Z",
            "source_url": "https://huggingface.co/EleutherAI/pythia-70m-deduped",
            "terms_url": "https://huggingface.co/EleutherAI/pythia-70m-deduped/blob/main/LICENSE",
            "notes": "integrity receipt without file hashes",
        }
        issues = validate(receipt, self.schemas["receipt"])
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("claim_ids") for issue in issues))
        self.assertTrue(any("runtime_files" in issue.message for issue in issues))

    def test_manifest_rejects_a_different_model_identity(self) -> None:
        manifest_path = self.repo_root / "experiments/lab01-model-anatomy/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["revision"] = "0" * 40
        issues = validate(manifest, self.schemas["manifest"])
        self.assertTrue(any(issue.path.endswith("revision") and "constant" in issue.message for issue in issues))

    def test_run_validates_and_distinguishes_structural_from_numeric_tolerance(self) -> None:
        run = {
            "artifact_class": "model-instrumentation",
            "empirical": True,
            "evidence_eligible": False,
            "claim_ids": [],
            "model": "EleutherAI/pythia-70m-deduped",
            "revision": "e93a9faa9c77e5d09219f6c868bfc7a1bd65593c",
            "license_id": "Apache-2.0",
            "backend": "torch",
            "dtype": "float32",
            "run_state": "instrumentation_verified",
            "structural_artifacts": [{"name": "prompt_template.json", "sha256": "3" * 64}],
            "byte_identical_structures": ["prompt_template.json"],
            "numeric_tolerance_by_backend_dtype": {"torch": {"float32": {"atol": 0.0, "rtol": 0.0}}},
            "notes": "structural and numeric boundary record",
        }
        self.assertEqual(validate(run, self.schemas["run"]), [])

    def test_prompts_are_small_frozen_and_non_triz(self) -> None:
        prompt_path = self.repo_root / "experiments/lab01-model-anatomy/prompts.jsonl"
        prompts = [json.loads(line) for line in prompt_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertGreaterEqual(len(prompts), 3)
        for prompt in prompts:
            self.assertEqual(prompt["prompt_kind"], "frozen")
            self.assertNotIn("TRIZ", prompt["prompt"].upper())
            self.assertLessEqual(len(prompt["prompt"].split()), 30)

    def test_schema_files_remain_dependency_free(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            copied = Path(workdir) / "manifest.json"
            copied.write_text((self.repo_root / "experiments/lab01-model-anatomy/manifest.json").read_text(encoding="utf-8"), encoding="utf-8")
            data = json.loads(copied.read_text(encoding="utf-8"))
            self.assertEqual(validate(data, self.schemas["manifest"]), [])
