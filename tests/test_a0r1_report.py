from __future__ import annotations

import json
import hashlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0r1_report import (
    A0R1ReportError,
    generate_a0r1_report,
    verify_a0r1_publication,
)
from latent_triz.validator import validate


ROOT = Path(__file__).resolve().parents[1]
BASE_PACKAGE = ROOT / "results" / "a0r1" / "a0r1-v1.0.0-e93a9faa-r1"
SCHEMA_PATH = ROOT / "schemas" / "a0r1-publication-manifest.schema.json"
CREATED_AT = "2026-08-15T08:00:00Z"
RUN_ID = BASE_PACKAGE.name


class A0R1ReportTests(unittest.TestCase):
    def _make_package(self) -> tuple[Path, Path]:
        workspace = Path(tempfile.mkdtemp(prefix="a0r1-report-"))
        package = workspace / "results" / "a0r1" / RUN_ID
        artifact = workspace / "artifacts" / "a0r1" / RUN_ID
        package.mkdir(parents=True, exist_ok=True)
        artifact.mkdir(parents=True, exist_ok=True)
        shutil.copytree(BASE_PACKAGE, package, dirs_exist_ok=True)
        (package / "report.md").unlink(missing_ok=True)
        (package / "publication-manifest.json").unlink(missing_ok=True)
        dense_path = artifact / "activations.json"
        dense_path.write_bytes(b"deterministic-a0r1-dense-fixture\n")
        dense_hash = hashlib.sha256(dense_path.read_bytes()).hexdigest()

        activation_path = package / "activation-receipt.json"
        activation = json.loads(activation_path.read_text(encoding="utf-8"))
        activation["dense_vectors"]["sha256"] = dense_hash
        activation["dense_vectors"]["bytes"] = dense_path.stat().st_size
        activation_path.write_text(
            json.dumps(activation, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        activation_hash = hashlib.sha256(activation_path.read_bytes()).hexdigest()

        for name in ("statistical-result.raw.json", "statistical-result.json"):
            result_path = package / name
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["input_hashes"]["dense_vectors"] = dense_hash
            result["input_hashes"]["activation_receipt"] = activation_hash
            result_path.write_text(
                json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )

        receipt_path = package / "recovery-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["raw_result"]["sha256"] = hashlib.sha256(
            (package / "statistical-result.raw.json").read_bytes()
        ).hexdigest()
        receipt["recovered_result"]["sha256"] = hashlib.sha256(
            (package / "statistical-result.json").read_bytes()
        ).hexdigest()
        receipt_path.write_text(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return package, artifact

    def _schema(self) -> dict:
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_report_success_generates_e0_manifest_and_markdown(self) -> None:
        package, artifact = self._make_package()
        old_cwd = os.getcwd()
        os.chdir(package.parents[2])  # workspace/results/a0r1/<run> -> workspace
        try:
            report_path, manifest_path = generate_a0r1_report(
                package_dir=Path("results") / "a0r1" / RUN_ID,
                external_activation_dir=Path("artifacts") / "a0r1" / RUN_ID,
                created_at=CREATED_AT,
            )
            self.assertTrue(report_path.exists())
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("a0r1-publication-manifest", manifest["artifact_class"])
            self.assertEqual("positive", manifest["result_status"])
            self.assertEqual("pass", manifest["status"])
            self.assertEqual("pass", manifest["verification"]["status"])
            self.assertEqual("pass", manifest["verification"]["recovery"])
            self.assertEqual(True, manifest["verification"]["required"])
            self.assertEqual("not_accessed", manifest["publication_access"]["model_output"])
            self.assertEqual("accessed", manifest["run_access"]["model_output"])
            report_text = report_path.read_text(encoding="utf-8")
            self.assertIn("54 labels", report_text)
            self.assertIn("Metric values are unchanged by recovery", report_text)
            self.assertIn("No TRIZ expert validation", report_text)
            self.assertEqual([], validate(manifest, self._schema()))
            verification = verify_a0r1_publication(
                package_dir=Path("results") / "a0r1" / RUN_ID,
                external_activation_dir=Path("artifacts") / "a0r1" / RUN_ID,
            )
            self.assertEqual("pass", verification["status"])
        finally:
            os.chdir(old_cwd)

    def test_report_rejects_raw_recovered_hash_drift(self) -> None:
        package, artifact = self._make_package()
        raw_path = package / "statistical-result.raw.json"
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        payload["artifact_class"] = "tampered"
        raw_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        old_cwd = os.getcwd()
        os.chdir(package.parents[2])
        try:
            with self.assertRaises(A0R1ReportError):
                generate_a0r1_report(
                    package_dir=Path("results") / "a0r1" / RUN_ID,
                    external_activation_dir=Path("artifacts") / "a0r1" / RUN_ID,
                    created_at=CREATED_AT,
                )
        finally:
            os.chdir(old_cwd)

    def test_report_rejects_hash_mismatch_with_result_input_hashes(self) -> None:
        package, artifact = self._make_package()
        result_path = package / "statistical-result.json"
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        payload["input_hashes"]["dense_vectors"] = "0" * 64
        result_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        old_cwd = os.getcwd()
        os.chdir(package.parents[2])
        try:
            with self.assertRaises(A0R1ReportError):
                generate_a0r1_report(
                    package_dir=Path("results") / "a0r1" / RUN_ID,
                    external_activation_dir=Path("artifacts") / "a0r1" / RUN_ID,
                    created_at=CREATED_AT,
                )
        finally:
            os.chdir(old_cwd)

    def test_report_rejects_traversal_and_absolute_paths(self) -> None:
        package, artifact = self._make_package()
        with self.assertRaises(A0R1ReportError):
            generate_a0r1_report(
                package_dir=package.resolve(),
                external_activation_dir=Path("artifacts") / "a0r1" / RUN_ID,
                created_at=CREATED_AT,
            )

        old_cwd = os.getcwd()
        os.chdir(package.parents[2])
        with self.assertRaises(A0R1ReportError):
            generate_a0r1_report(
                package_dir=Path("results") / ".." / "a0r1",
                external_activation_dir=Path("artifacts") / "a0r1" / RUN_ID,
                created_at=CREATED_AT,
            )
        os.chdir(old_cwd)

    def test_report_missing_external_dense_is_rejected(self) -> None:
        package, artifact = self._make_package()
        (artifact / "activations.json").unlink()
        old_cwd = os.getcwd()
        os.chdir(package.parents[2])
        try:
            with self.assertRaises(A0R1ReportError):
                generate_a0r1_report(
                    package_dir=Path("results") / "a0r1" / RUN_ID,
                    external_activation_dir=Path("artifacts") / "a0r1" / RUN_ID,
                    created_at=CREATED_AT,
                )
        finally:
            os.chdir(old_cwd)

    def test_report_refuses_overwrite(self) -> None:
        package, artifact = self._make_package()
        old_cwd = os.getcwd()
        os.chdir(package.parents[2])
        report_rel = Path("results") / "a0r1" / RUN_ID / "report.md"
        report_rel.write_text("existing", encoding="utf-8")
        try:
            with self.assertRaises(A0R1ReportError):
                generate_a0r1_report(
                    package_dir=Path("results") / "a0r1" / RUN_ID,
                    external_activation_dir=Path("artifacts") / "a0r1" / RUN_ID,
                    created_at=CREATED_AT,
                )
        finally:
            os.chdir(old_cwd)

    def test_verifier_rejects_tracked_report_drift(self) -> None:
        package, artifact = self._make_package()
        old_cwd = os.getcwd()
        os.chdir(package.parents[2])
        try:
            report_path, _ = generate_a0r1_report(
                package_dir=Path("results") / "a0r1" / RUN_ID,
                external_activation_dir=Path("artifacts") / "a0r1" / RUN_ID,
                created_at=CREATED_AT,
            )
            report_path.write_text("tampered\n", encoding="utf-8")
            with self.assertRaises(A0R1ReportError):
                verify_a0r1_publication(
                    package_dir=Path("results") / "a0r1" / RUN_ID,
                    external_activation_dir=Path("artifacts") / "a0r1" / RUN_ID,
                )
        finally:
            os.chdir(old_cwd)

    def test_report_rejects_overclaim_fields(self) -> None:
        package, artifact = self._make_package()
        old_cwd = os.getcwd()
        os.chdir(package.parents[3])
        result_path = package / "statistical-result.json"
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        payload["evidence_eligible"] = True
        result_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        try:
            with self.assertRaises(A0R1ReportError):
                generate_a0r1_report(
                    package_dir=Path("results") / "a0r1" / RUN_ID,
                    external_activation_dir=Path("artifacts") / "a0r1" / RUN_ID,
                    created_at=CREATED_AT,
                )
        finally:
            os.chdir(old_cwd)

    def test_report_no_model_or_target_files_read(self) -> None:
        package, artifact = self._make_package()
        old_cwd = os.getcwd()
        os.chdir(package.parents[2])
        allowed_paths = {
            f"results/a0r1/{RUN_ID}/statistical-result.raw.json",
            f"results/a0r1/{RUN_ID}/statistical-result.json",
            f"results/a0r1/{RUN_ID}/recovery-receipt.json",
            f"results/a0r1/{RUN_ID}/activation-receipt.json",
            f"results/a0r1/{RUN_ID}/representations-index.jsonl",
            f"artifacts/a0r1/{RUN_ID}/activations.json",
            str(ROOT / "schemas/a0r1-recovery-receipt.schema.json"),
            str(ROOT / "schemas/a0r1-statistical-result.schema.json"),
            str(ROOT / "schemas/a0r1-activation-receipt.schema.json"),
            str(ROOT / "schemas/a0r1-publication-manifest.schema.json"),
        }

        original_read_text = Path.read_text
        original_read_bytes = Path.read_bytes

        def safe_read_text(self: Path, *args, **kwargs):  # type: ignore[override]
            if str(self) not in allowed_paths:
                raise A0R1ReportError(f"unexpected read_text path: {self}")
            return original_read_text(self, *args, **kwargs)

        def safe_read_bytes(self: Path, *args, **kwargs):  # type: ignore[override]
            if str(self) not in allowed_paths:
                raise A0R1ReportError(f"unexpected read_bytes path: {self}")
            return original_read_bytes(self, *args, **kwargs)

        try:
            with (
                patch.object(Path, "read_text", safe_read_text),
                patch.object(Path, "read_bytes", safe_read_bytes),
            ):
                report_path, manifest_path = generate_a0r1_report(
                    package_dir=Path("results") / "a0r1" / RUN_ID,
                    external_activation_dir=Path("artifacts") / "a0r1" / RUN_ID,
                    created_at=CREATED_AT,
                )
                self.assertTrue(report_path.exists())
                self.assertTrue(manifest_path.exists())
        finally:
            os.chdir(old_cwd)
