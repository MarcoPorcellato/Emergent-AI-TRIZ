"""Synthetic-only tests for the C3 report package boundary."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from latent_triz.a0r2c3_report import (  # noqa: E402
    A0R2C3ReportError,
    generate_a0r2c3_report,
    verify_a0r2c3_publication,
)
import test_a0r2_report as report_fixtures  # noqa: E402


class A0R2C3ReportTests(unittest.TestCase):
    def _fixture(self) -> tuple[Path, Path, Path]:
        helper = report_fixtures.A0R2ReportTests()
        workspace, package, _unused = helper._fixture_paths(with_dense=False)
        source = workspace / "artifacts" / "a0r2" / "immutable-c2-source"
        source.mkdir(parents=True)
        dense_path = helper._write_dense(source)
        dense_hash = hashlib.sha256(dense_path.read_bytes()).hexdigest()
        index_path = helper._write_index(package)
        row = json.loads(index_path.read_text(encoding="utf-8"))
        row.pop("dtype")
        index_path.write_text(
            "".join(json.dumps({**row, "record_id": f"synthetic-{index}"}, sort_keys=True, separators=(",", ":")) + "\n" for index in range(1920)),
            encoding="utf-8",
        )
        index_hash = hashlib.sha256(index_path.read_bytes()).hexdigest()
        locator = "artifacts/a0r2/immutable-c2-source/activations.json"
        helper._write_activation_receipt(package, locator, index_hash, dense_hash)
        receipt_hash = hashlib.sha256((package / "activation-receipt.json").read_bytes()).hexdigest()
        helper._write_statistical_result(
            package,
            status="positive",
            activation_hash=receipt_hash,
            index_hash=index_hash,
            dense_hash=dense_hash,
            dense_locator=locator,
        )
        return workspace, package, source

    def test_generates_and_verifies_distinct_immutable_source_locator(self) -> None:
        workspace, package, source = self._fixture()
        index_hash = hashlib.sha256((package / "representations-index.jsonl").read_bytes()).hexdigest()
        old_cwd = os.getcwd()
        os.chdir(workspace)
        try:
            with patch("latent_triz.a0r2c3_report.EXPECTED_C2_INDEX_SHA256", index_hash):
                report_path, manifest_path = generate_a0r2c3_report(
                    package_dir=Path("results") / "a0r2" / package.name,
                    external_dense_dir=Path("artifacts") / "a0r2" / source.name,
                    created_at="2026-08-17T12:00:00Z",
                    allow_external_dense_reuse=True,
                )
                self.assertTrue(report_path.is_file())
                self.assertTrue(manifest_path.is_file())
                self.assertFalse((package / "activations.json").exists())
                report = report_path.read_text(encoding="utf-8")
                self.assertIn("## C3 recovery provenance", report)
                self.assertIn(source.name, report)
                manifest = verify_a0r2c3_publication(
                    package_dir=Path("results") / "a0r2" / package.name,
                    external_dense_dir=Path("artifacts") / "a0r2" / source.name,
                    allow_external_dense_reuse=True,
                )
                self.assertEqual("positive", manifest["terminal_status"])
                self.assertEqual("artifacts/a0r2/immutable-c2-source/activations.json", manifest["dense"]["path"])
        finally:
            os.chdir(old_cwd)

    def test_fails_closed_without_opt_in_or_for_non_direct_source(self) -> None:
        workspace, package, source = self._fixture()
        index_hash = hashlib.sha256((package / "representations-index.jsonl").read_bytes()).hexdigest()
        old_cwd = os.getcwd()
        os.chdir(workspace)
        try:
            with patch("latent_triz.a0r2c3_report.EXPECTED_C2_INDEX_SHA256", index_hash):
                with self.assertRaisesRegex(A0R2C3ReportError, "explicit external dense reuse"):
                    generate_a0r2c3_report(
                        package_dir=Path("results") / "a0r2" / package.name,
                        external_dense_dir=Path("artifacts") / "a0r2" / source.name,
                        created_at="2026-08-17T12:00:00Z",
                    )
                with self.assertRaisesRegex(A0R2C3ReportError, "direct artifacts/a0r2"):
                    generate_a0r2c3_report(
                        package_dir=Path("results") / "a0r2" / package.name,
                        external_dense_dir=Path("artifacts") / "a0r2" / source.name / "nested",
                        created_at="2026-08-17T12:00:00Z",
                        allow_external_dense_reuse=True,
                    )
        finally:
            os.chdir(old_cwd)

    def test_preserves_bound_c2_source_records_for_a_terminal_c3_failure(self) -> None:
        workspace, package, source = self._fixture()
        (package / "statistical-result.json").unlink()
        report_fixtures.A0R2ReportTests()._write_failure_result(package)
        index_hash = hashlib.sha256((package / "representations-index.jsonl").read_bytes()).hexdigest()
        old_cwd = os.getcwd()
        os.chdir(workspace)
        try:
            with patch("latent_triz.a0r2c3_report.EXPECTED_C2_INDEX_SHA256", index_hash):
                generate_a0r2c3_report(
                    package_dir=Path("results") / "a0r2" / package.name,
                    external_dense_dir=Path("artifacts") / "a0r2" / source.name,
                    created_at="2026-08-17T12:00:00Z",
                    allow_external_dense_reuse=True,
                )
                manifest = verify_a0r2c3_publication(
                    package_dir=Path("results") / "a0r2" / package.name,
                    external_dense_dir=Path("artifacts") / "a0r2" / source.name,
                    allow_external_dense_reuse=True,
                )
            self.assertEqual("failed", manifest["terminal_status"])
            self.assertIn("dense", manifest)
            self.assertTrue((package / "activation-receipt.json").is_file())
            self.assertTrue((package / "representations-index.jsonl").is_file())
        finally:
            os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
