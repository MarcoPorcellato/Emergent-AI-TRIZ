from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz import lab01_acquisition as acquisition


class Lab01AcquisitionTests(unittest.TestCase):
    def _write_required_files(self, directory: Path, marker: str = "ok") -> None:
        for filename in acquisition.LAB01_REQUIRED_FILES:
            target = directory / filename
            target.write_text(f"{filename}:{marker}", encoding="utf-8")

    def _selection_receipt(self, before: str, after: str) -> dict[str, Any]:
        return {
            "artifact_class": "model-instrumentation",
            "empirical": True,
            "evidence_eligible": False,
            "claim_ids": [],
            "receipt_type": "selection",
            "state_before": before,
            "state_after": after,
            "model": acquisition.LAB01_MODEL_ID,
            "revision": acquisition.LAB01_MODEL_REVISION,
            "receipt_time": "2026-08-13T00:00:00Z",
            "source_url": acquisition.LAB01_SOURCE_URL,
            "terms_url": acquisition.LAB01_TERMS_URL,
            "hashes": {"receipt_sha256": "0" * 64},
            "notes": "test",
        }

    def _generic_receipt(self, kind: str, before: str, after: str) -> dict[str, Any]:
        return {
            **self._selection_receipt(before, after),
            "receipt_type": kind,
        }

    def test_authorization_required_to_download_model(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            model_dir = Path(workdir) / "pythia"
            with self.assertRaisesRegex(
                acquisition.Lab01AcquisitionError,
                "operator authorization is required",
            ):
                acquisition.ensure_lab01_model(model_dir, allow_download=False)

    def test_snapshot_download_called_with_allowlist_and_no_symlink_if_supported(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            model_dir = Path(workdir) / "pythia"

            called = {}

            def fake_snapshot_download(
                *,
                repo_id: str,
                revision: str,
                local_dir: str,
                allow_patterns: list[str],
                local_dir_use_symlinks: bool | None = None,
            ) -> str:
                called.update(
                    {
                        "repo_id": repo_id,
                        "revision": revision,
                        "local_dir": local_dir,
                        "allow_patterns": allow_patterns,
                        "local_dir_use_symlinks": local_dir_use_symlinks,
                    }
                )
                model_dir.mkdir(parents=True, exist_ok=True)
                for filename in acquisition.LAB01_REQUIRED_FILES:
                    target = model_dir / filename
                    target.write_text("downloaded", encoding="utf-8")
                return str(model_dir)

            acquisition.ensure_lab01_model(
                model_dir,
                allow_download=True,
                call_snapshot_download=fake_snapshot_download,
                identity_verifier=lambda _path: (True, []),
            )
            self.assertEqual(called["repo_id"], acquisition.LAB01_MODEL_ID)
            self.assertEqual(called["revision"], acquisition.LAB01_MODEL_REVISION)
            self.assertEqual(sorted(called["allow_patterns"]), sorted(acquisition.LAB01_REQUIRED_FILES))
            self.assertFalse(called["local_dir_use_symlinks"])

    def test_snapshot_download_without_symlink_parameter_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            model_dir = Path(workdir) / "pythia"

            def fake_snapshot_download(**kwargs: Any) -> str:
                self.assertNotIn("local_dir_use_symlinks", kwargs)
                model_dir.mkdir(parents=True, exist_ok=True)
                for filename in acquisition.LAB01_REQUIRED_FILES:
                    (model_dir / filename).write_text("downloaded", encoding="utf-8")
                return str(model_dir)

            capture = inspect.signature(fake_snapshot_download)
            self.assertFalse("local_dir_use_symlinks" in capture.parameters)
            acquisition.ensure_lab01_model(
                model_dir,
                allow_download=True,
                call_snapshot_download=fake_snapshot_download,
                identity_verifier=lambda _path: (True, []),
            )

    def test_runtime_file_receipts_and_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            model_dir = Path(workdir) / "pythia"
            model_dir.mkdir()
            self._write_required_files(model_dir)

            receipts = acquisition.build_runtime_file_receipts(model_dir)
            ok, errors = acquisition.verify_runtime_file_receipts(
                model_dir,
                {name: {"sha256": data.sha256, "size": data.size} for name, data in receipts.items()},
            )
            self.assertTrue(ok)
            self.assertEqual(errors, [])

            json_bytes = json.dumps(
                {name: {"sha256": data.sha256, "size": data.size} for name, data in receipts.items()},
                sort_keys=True,
            ).encode("utf-8")
            intact = acquisition._sha256_bytes(json_bytes)
            self.assertEqual(len(intact), 64)

    def test_offline_integrity_rejects_mutated_file(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            model_dir = Path(workdir) / "pythia"
            model_dir.mkdir()
            self._write_required_files(model_dir)

            receipts = acquisition.build_runtime_file_receipts(model_dir)
            mutated = {name: {"sha256": data.sha256, "size": data.size} for name, data in receipts.items()}
            (model_dir / "config.json").write_text("mutated", encoding="utf-8")

            ok, errors = acquisition.verify_runtime_file_receipts(model_dir, mutated)
            self.assertFalse(ok)
            self.assertTrue(any("sha mismatch for config.json" in error for error in errors))

    def test_state_is_derived_only_from_valid_receipts_and_files(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            model_dir = Path(workdir) / "pythia"
            model_dir.mkdir()
            self._write_required_files(model_dir)

            selected = self._selection_receipt("unselected", "selected")
            acquired = self._generic_receipt("acquisition", "selected", "acquisition_planned")
            payload = acquisition.build_integrity_receipt(model_dir=model_dir, state_before="acquired")
            load = self._generic_receipt("load", "integrity_verified", "load_verified")
            instrument = self._generic_receipt("instrumentation", "load_verified", "instrumentation_verified")

            state = acquisition.derive_lab01_state(
                model_dir,
                selection_receipt=selected,
                acquisition_receipt=acquired,
                integrity_receipt=payload,
                load_receipt=load,
                instrumentation_receipt=instrument,
            )
            self.assertEqual(state, "lab_ready")

            tampered_payload = dict(payload)
            tampered_payload["runtime_files"] = [
                {"name": key, "sha256": value.sha256, "size": value.size}
                for key, value in acquisition.build_runtime_file_receipts(model_dir).items()
            ]
            tampered_payload["runtime_files"][0]["size"] = -1

            state_with_bad_receipt = acquisition.derive_lab01_state(
                model_dir,
                selection_receipt=selected,
                acquisition_receipt=acquired,
                integrity_receipt=tampered_payload,
                load_receipt=load,
                instrumentation_receipt=instrument,
            )
            self.assertEqual(state_with_bad_receipt, "acquired")

    def test_build_integrity_receipt_uses_fixed_revision_and_model(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            model_dir = Path(workdir) / "pythia"
            model_dir.mkdir()
            self._write_required_files(model_dir)
            payload = acquisition.build_integrity_receipt(model_dir=model_dir, state_before="acquired")
            self.assertEqual(payload["model"], acquisition.LAB01_MODEL_ID)
            self.assertEqual(payload["revision"], acquisition.LAB01_MODEL_REVISION)


if __name__ == "__main__":
    unittest.main()
