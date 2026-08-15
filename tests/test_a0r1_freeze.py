from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0r1_freeze import A0R1FreezeError, run_a0r1_freeze


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class A0R1FreezeTests(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: int, *, prefix: str) -> None:
        records = [json.dumps({"case_id": f"{prefix}_{idx}", "split": "calibration"}) for idx in range(rows)]
        path.write_text("\n".join(records) + "\n", encoding="utf-8")

    def _manifest(self, root: Path, protocol_id: str, protocol_hash: str, rows: int) -> dict:
        cases = root / "cases.jsonl"
        cal = root / "calibration.jsonl"
        sealed = root / "sealed.jsonl"
        self._write_jsonl(cases, rows, prefix=f"{protocol_id}-case")
        self._write_jsonl(cal, rows, prefix=f"{protocol_id}-cal")
        self._write_jsonl(sealed, rows, prefix=f"{protocol_id}-sealed")
        manifest = {
            "protocol_id": protocol_id,
            "protocol_hash": protocol_hash,
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "files": {
                "cases_jsonl": {"path": "cases.jsonl", "sha256": _sha256(cases), "size": cases.stat().st_size},
                "calibration_targets_jsonl": {"path": "calibration.jsonl", "sha256": _sha256(cal), "size": cal.stat().st_size},
                "sealed_targets_jsonl": {"path": "sealed.jsonl", "sha256": _sha256(sealed), "size": sealed.stat().st_size},
            },
        }
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    def _write_preoutput(self, root: Path, protocol: Path, candidate_manifest_path: Path, source_manifest_path: Path) -> None:
        independence = {"artifact_class": "a0-r1-independence-audit", "status": "pass"}
        shortcuts = {"artifact_class": "a0-r1-shortcuts", "status": "pass"}
        summary = {"artifact_class": "a0-r1-preoutput-summary", "status": "pass"}
        for name, payload in (("independence.json", independence), ("shortcuts.json", shortcuts), ("summary.json", summary)):
            (root / name).write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

        manifest = {
            "artifact_class": "a0-r1-preoutput-manifest",
            "protocol_id": "a0-r1-tier-r1-v1.0",
            "protocol_status": "planned",
            "protocol_hash": _sha256(protocol),
            "status": "pass",
            "candidate_corpus_manifest_sha256": _sha256(candidate_manifest_path),
            "source_corpus_manifest_sha256": _sha256(source_manifest_path),
            "artifacts": {
                "independence.json": {"sha256": _sha256(root / "independence.json")},
                "shortcuts.json": {"sha256": _sha256(root / "shortcuts.json")},
                "summary.json": {"sha256": _sha256(root / "summary.json")},
            },
        }
        (root / "preoutput-manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    def test_freeze_pass_writes_expected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = root / "protocol.json"
            protocol_payload = {
                "protocol_id": "a0-r1-tier-r1-v1.0",
                "protocol_status": "planned",
                "status": "planned",
                "primary_endpoint": {
                    "layer": 6,
                    "token_site": "mean_transformation_span",
                    "primary_view": "problem_plus_transformation",
                    "surface_baseline_view": "problem_only",
                    "is_max_statistic_selection": False,
                    "multiplicity": 1,
                },
            }
            protocol.write_text(json.dumps(protocol_payload, indent=2), encoding="utf-8")

            candidate = root / "candidate"
            source = root / "source"
            preoutput_root = root / "preoutput"
            candidate.mkdir()
            source.mkdir()
            preoutput_root.mkdir()
            candidate_manifest = self._manifest(candidate, "a0-r1-tier-r1-v1.0", _sha256(protocol), 3)
            _ = self._manifest(source, "a0-source", "000000000000", 2)

            source_manifest_path = source / "manifest.json"
            self._write_preoutput(preoutput_root, protocol, candidate / "manifest.json", source_manifest_path)

            with patch("latent_triz.a0r1_freeze.calibrate_a0r1_power", return_value={"status": "pass", "artifact_class": "x"}) as p:
                summary = run_a0r1_freeze(protocol, candidate, source, preoutput_root, root / "freeze")
                self.assertEqual("frozen", summary["status"])
                self.assertFalse(summary["model_output_accessed"])
                self.assertFalse(summary["sealed_model_output_accessed"])
                self.assertTrue((root / "freeze" / "protocol-planned.json").is_file())
                self.assertTrue((root / "freeze" / "protocol-frozen.json").is_file())
                self.assertTrue((root / "freeze" / "power.json").is_file())
                self.assertTrue((root / "freeze" / "freeze-manifest.json").is_file())

                p.assert_called_once()

                planned = (root / "freeze" / "protocol-planned.json").read_bytes()
                frozen_payload = json.loads((root / "freeze" / "protocol-frozen.json").read_text(encoding="utf-8"))
                freeze_manifest = json.loads((root / "freeze" / "freeze-manifest.json").read_text(encoding="utf-8"))
                power_payload = json.loads((root / "freeze" / "power.json").read_text(encoding="utf-8"))
                self.assertEqual(planned, protocol.read_bytes())
                self.assertEqual("frozen", frozen_payload["protocol_status"])
                self.assertEqual("frozen", frozen_payload["status"])
                self.assertNotIn("protocol_frozen", frozen_payload)
                self.assertEqual("pass", power_payload["status"])
                self.assertEqual("frozen", freeze_manifest["status"])
                self.assertEqual(_sha256(protocol), freeze_manifest["planned_protocol_snapshot_hash"])
                self.assertEqual(_sha256((root / "candidate" / "manifest.json")), freeze_manifest["corpus_manifest_hash"])
                self.assertEqual(_sha256(preoutput_root / "preoutput-manifest.json"), freeze_manifest["preoutput_manifest_hash"])
                self.assertEqual(candidate_manifest["files"]["cases_jsonl"]["sha256"], freeze_manifest["cases_sha256"])

    def test_freeze_rejects_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = root / "protocol.json"
            protocol_payload = {
                "protocol_id": "a0-r1-tier-r1-v1.0",
                "protocol_status": "planned",
                "status": "planned",
                "primary_endpoint": {"layer": 6, "token_site": "mean_transformation_span", "primary_view": "problem_plus_transformation", "surface_baseline_view": "problem_only", "is_max_statistic_selection": False, "multiplicity": 1},
            }
            protocol.write_text(json.dumps(protocol_payload), encoding="utf-8")

            candidate = root / "candidate"
            source = root / "source"
            preoutput_root = root / "preoutput"
            candidate.mkdir()
            source.mkdir()
            preoutput_root.mkdir()
            self._manifest(candidate, "a0-r1-tier-r1-v1.0", _sha256(protocol), 3)
            self._manifest(source, "a0-source", "0000", 2)
            (candidate / "cases.jsonl").write_text("corrupted", encoding="utf-8")
            self._write_preoutput(preoutput_root, protocol, candidate / "manifest.json", source / "manifest.json")

            with self.assertRaises(A0R1FreezeError):
                run_a0r1_freeze(protocol, candidate, source, preoutput_root, root / "freeze")

    def test_failed_power_writes_no_freeze_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = root / "protocol.json"
            protocol_payload = {
                "protocol_id": "a0-r1-tier-r1-v1.0",
                "protocol_status": "planned",
                "status": "planned",
                "primary_endpoint": {"layer": 6, "token_site": "mean_transformation_span", "primary_view": "problem_plus_transformation", "surface_baseline_view": "problem_only", "is_max_statistic_selection": False, "multiplicity": 1},
            }
            protocol.write_text(json.dumps(protocol_payload), encoding="utf-8")
            candidate = root / "candidate"
            source = root / "source"
            preoutput_root = root / "preoutput"
            candidate.mkdir()
            source.mkdir()
            preoutput_root.mkdir()
            self._manifest(candidate, "a0-r1-tier-r1-v1.0", _sha256(protocol), 3)
            self._manifest(source, "a0-source", "0000", 2)
            self._write_preoutput(preoutput_root, protocol, candidate / "manifest.json", source / "manifest.json")

            output = root / "freeze"
            with patch("latent_triz.a0r1_freeze.calibrate_a0r1_power", return_value={"status": "failed"}):
                with self.assertRaises(A0R1FreezeError):
                    run_a0r1_freeze(protocol, candidate, source, preoutput_root, output)
            self.assertFalse(output.exists())

    def test_freeze_rejects_non_pass_preoutput(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = root / "protocol.json"
            protocol_payload = {
                "protocol_id": "a0-r1-tier-r1-v1.0",
                "protocol_status": "planned",
                "status": "planned",
                "primary_endpoint": {"layer": 6, "token_site": "mean_transformation_span", "primary_view": "problem_plus_transformation", "surface_baseline_view": "problem_only", "is_max_statistic_selection": False, "multiplicity": 1},
            }
            protocol.write_text(json.dumps(protocol_payload), encoding="utf-8")

            candidate = root / "candidate"
            source = root / "source"
            preoutput_root = root / "preoutput"
            candidate.mkdir()
            source.mkdir()
            preoutput_root.mkdir()
            self._manifest(candidate, "a0-r1-tier-r1-v1.0", _sha256(protocol), 3)
            self._manifest(source, "a0-source", "0000", 2)
            self._write_preoutput(preoutput_root, protocol, candidate / "manifest.json", source / "manifest.json")
            preoutput = json.loads((preoutput_root / "preoutput-manifest.json").read_text(encoding="utf-8"))
            preoutput["status"] = "failed"
            (preoutput_root / "preoutput-manifest.json").write_text(json.dumps(preoutput), encoding="utf-8")

            with self.assertRaises(A0R1FreezeError):
                run_a0r1_freeze(protocol, candidate, source, preoutput_root, root / "freeze")

    def test_freeze_rejects_existing_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = root / "protocol.json"
            protocol_payload = {
                "protocol_id": "a0-r1-tier-r1-v1.0",
                "protocol_status": "planned",
                "status": "planned",
                "primary_endpoint": {"layer": 6, "token_site": "mean_transformation_span", "primary_view": "problem_plus_transformation", "surface_baseline_view": "problem_only", "is_max_statistic_selection": False, "multiplicity": 1},
            }
            protocol.write_text(json.dumps(protocol_payload), encoding="utf-8")

            candidate = root / "candidate"
            source = root / "source"
            preoutput_root = root / "preoutput"
            candidate.mkdir()
            source.mkdir()
            preoutput_root.mkdir()
            self._manifest(candidate, "a0-r1-tier-r1-v1.0", _sha256(protocol), 3)
            self._manifest(source, "a0-source", "0000", 2)
            self._write_preoutput(preoutput_root, protocol, candidate / "manifest.json", source / "manifest.json")

            output = root / "freeze"
            output.mkdir()
            (output / "old.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(A0R1FreezeError):
                run_a0r1_freeze(protocol, candidate, source, preoutput_root, output)

    def test_freeze_rejects_protocol_not_planned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol = root / "protocol.json"
            protocol_payload = {
                "protocol_id": "a0-r1-tier-r1-v1.0",
                "protocol_status": "frozen",
                "status": "frozen",
                "primary_endpoint": {"layer": 6, "token_site": "mean_transformation_span", "primary_view": "problem_plus_transformation", "surface_baseline_view": "problem_only", "is_max_statistic_selection": False, "multiplicity": 1},
            }
            protocol.write_text(json.dumps(protocol_payload), encoding="utf-8")

            candidate = root / "candidate"
            source = root / "source"
            preoutput_root = root / "preoutput"
            candidate.mkdir()
            source.mkdir()
            preoutput_root.mkdir()
            self._manifest(candidate, "a0-r1-tier-r1-v1.0", "0000", 3)
            self._manifest(source, "a0-source", "0000", 2)
            self._write_preoutput(preoutput_root, protocol, candidate / "manifest.json", source / "manifest.json")

            with self.assertRaises(A0R1FreezeError):
                run_a0r1_freeze(protocol, candidate, source, preoutput_root, root / "freeze")


if __name__ == "__main__":
    unittest.main()
