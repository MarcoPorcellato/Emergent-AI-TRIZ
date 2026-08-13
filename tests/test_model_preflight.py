from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.model_preflight import ModelPreflightError, run_model_preflight


class ModelPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.manifest = self.repo_root / "experiments/001-stage1-pilot/model-candidates.jsonl"

    def test_preflight_reports_provisional_candidates(self) -> None:
        report = run_model_preflight(self.manifest)
        self.assertEqual(report["status"], "decision_recorded")
        self.assertTrue(report["manifest_valid"])
        self.assertFalse(report["acquisition_ready"])
        self.assertFalse(report["experiment_ready"])
        self.assertFalse(report["ready"])
        self.assertEqual(report["candidate_count"], 3)
        self.assertEqual(report["roles"], ["fallback", "primary", "replication"])
        self.assertEqual(report["issues"], [])

    def test_invalid_revision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            path = Path(workdir) / "bad.json"
            path.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "role": "primary",
                                "model_id": "google/gemma-3-270m",
                                "revision": "not-a-revision",
                                "license_id": "Gemma",
                                "model_card_url": "https://example.invalid",
                                "terms_url": "https://example.invalid",
                                "evidence_url": "https://example.invalid",
                                "acquisition_status": "not_acquired",
                                "weights_present": False,
                                "required_capabilities": ["hidden-state access"],
                            },
                            {
                                "role": "replication",
                                "model_id": "HuggingFaceTB/SmolLM2-360M",
                                "revision": "f8027fd0eaeea54caa13c31d31b9fdc459c38b49",
                                "license_id": "Apache-2.0",
                                "model_card_url": "https://example.invalid",
                                "terms_url": "https://example.invalid",
                                "evidence_url": "https://example.invalid",
                                "acquisition_status": "not_acquired",
                                "weights_present": False,
                                "required_capabilities": ["hidden-state access"],
                            },
                            {
                                "role": "fallback",
                                "model_id": "Qwen/Qwen3-0.6B-Base",
                                "revision": "da87bfb608c14b7cf20ba1ce41287e8de496c0cd",
                                "license_id": "Apache-2.0",
                                "model_card_url": "https://example.invalid",
                                "terms_url": "https://example.invalid",
                                "evidence_url": "https://example.invalid",
                                "acquisition_status": "not_acquired",
                                "weights_present": False,
                                "required_capabilities": ["hidden-state access"],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            report = run_model_preflight(path)
            self.assertEqual(report["status"], "pass_with_blockers")
            self.assertFalse(report["ready"])
            self.assertTrue(any(issue["code"] == "invalid_revision" for issue in report["issues"]))

    def test_missing_roles_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            path = Path(workdir) / "missing.json"
            path.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {
                                "role": "primary",
                                "model_id": "google/gemma-3-270m",
                                "revision": "9b0cfec892e2bc2afd938c98eabe4e4a7b1e0ca1",
                                "license_id": "Gemma",
                                "model_card_url": "https://example.invalid",
                                "terms_url": "https://example.invalid",
                                "evidence_url": "https://example.invalid",
                                "acquisition_status": "not_acquired",
                                "weights_present": False,
                                "required_capabilities": ["hidden-state access"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            report = run_model_preflight(path)
            self.assertEqual(report["status"], "pass_with_blockers")
            codes = {item["code"] for item in report["issues"]}
            self.assertIn("missing_role", codes)

    def test_invalid_manifest_shape_raises(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            path = Path(workdir) / "bad.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ModelPreflightError):
                run_model_preflight(path)

    def test_schema_validation_catches_role_and_status_drift(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            path = Path(workdir) / "bad.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "role": "primary",
                                "model_id": "google/gemma-3-270m",
                                "revision": "9b0cfec892e2bc2afd938c98eabe4e4a7b1e0ca1",
                                "license_id": "Gemma",
                                "model_card_url": "https://huggingface.co/google/gemma-3-270m",
                                "terms_url": "https://ai.google.dev/gemma/terms",
                                "evidence_url": "https://ai.google.dev/gemma/docs/core/model_card_3",
                                "acquisition_status": "downloaded",
                                "weights_present": True,
                                "required_capabilities": ["hidden-state access"],
                            }
                        )
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            report = run_model_preflight(path)
            codes = {issue["code"] for issue in report["issues"]}
            self.assertIn("schema_validation_error", codes)
            self.assertIn("invalid_acquisition_status", codes)
            self.assertIn("invalid_weights_state", codes)
