from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0r1_preoutput import A0R1PreoutputError, run_a0r1_preoutput_audits


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class A0R1PreoutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.protocol = {
            "protocol_id": "a0-r1-tier-r1-v1.0",
            "protocol_status": "planned",
        }
        self.independence_pass = {"artifact_class": "a0-r1-independence-audit", "status": "pass", "ready": True, "counts": {}}
        self.shortcuts_pass = {
            "artifact_class": "a0-shortcuts",
            "overall": {"status": "pass"},
            "counts": {},
            "status": "pass",
        }

    def _write_cases(self, path: Path, lines: int, *, prefix: str) -> None:
        payloads = []
        for index in range(1, lines + 1):
            payloads.append(
                json.dumps(
                    {
                        "case_id": f"case_{prefix}_{index}",
                        "problem_family_id": f"fam_{index}",
                        "provenance": {"template_id": f"tpl_{index}"},
                        "problem": f"Candidate problem {prefix}-{index}",
                        "constraints": ["no_cost"],
                        "initial_state": "baseline",
                        "desired_improvement": "improve",
                        "worsening_consequence": "worse",
                        "transformation": "transform",
                        "resulting_state": "better",
                        "split": "calibration" if index % 2 else "sealed",
                    },
                    ensure_ascii=False,
                )
            )
        text = "\n".join(payloads) + "\n"
        path.write_text(text, encoding="utf-8")

    def _build_target_file(self, path: Path, entries: int) -> None:
        payloads = [
            json.dumps({"case_id": f"case_{prefix}_{index}", "split": split, "target_text": f"target-{index}"}, ensure_ascii=False)
            for index, (prefix, split) in enumerate(
                [(f"prefix_{i%2}_{i}", "calibration" if i % 2 == 0 else "sealed") for i in range(entries)],
                start=1,
            )
        ]
        path.write_text("\n".join(payloads) + "\n", encoding="utf-8")

    def _write_manifest(self, root: Path, protocol_id: str, case_path: str, calibration_path: str, sealed_path: str) -> None:
        manifest = {
            "protocol_id": protocol_id,
            "protocol_hash": _sha256(root.parent / "protocol.json") if protocol_id == self.protocol["protocol_id"] else "0" * 64,
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "files": {
                "cases_jsonl": {
                    "path": case_path,
                    "sha256": _sha256(root / case_path),
                    "size": (root / case_path).stat().st_size,
                },
                "calibration_targets_jsonl": {
                    "path": calibration_path,
                    "sha256": _sha256(root / calibration_path),
                    "size": (root / calibration_path).stat().st_size,
                },
                "sealed_targets_jsonl": {
                    "path": sealed_path,
                    "sha256": _sha256(root / sealed_path),
                    "size": (root / sealed_path).stat().st_size,
                },
            },
        }
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    def _setup_corpus(self, workdir: Path, protocol_id: str, *, include_protocol_match: bool = True) -> tuple[Path, dict]:
        candidate = workdir / "candidate"
        source = workdir / "source"
        candidate.mkdir()
        source.mkdir()

        candidate_cases = candidate / "cases.jsonl"
        candidate_cal = candidate / "procedural-targets" / "calibration-targets.jsonl"
        candidate_sealed = candidate / "sealed-targets" / "targets.jsonl"
        source_cases = source / "cases.jsonl"
        source_cal = source / "procedural-targets" / "calibration-targets.jsonl"
        source_sealed = source / "sealed-targets" / "targets.jsonl"

        candidate_cal.parent.mkdir(parents=True)
        candidate_sealed.parent.mkdir(parents=True)
        source_cal.parent.mkdir(parents=True)
        source_sealed.parent.mkdir(parents=True)

        self._write_cases(candidate_cases, 2, prefix="cand")
        self._build_target_file(candidate_cal, 1)
        self._build_target_file(candidate_sealed, 1)

        self._write_cases(source_cases, 2, prefix="src")
        self._build_target_file(source_cal, 1)
        self._build_target_file(source_sealed, 1)

        man_proto = protocol_id if include_protocol_match else f"{protocol_id}-other"
        candidate_manifest = self._write_manifest(
            candidate,
            man_proto,
            "cases.jsonl",
            "procedural-targets/calibration-targets.jsonl",
            "sealed-targets/targets.jsonl",
        )
        source_manifest = self._write_manifest(
            source,
            "a0-source",
            "cases.jsonl",
            "procedural-targets/calibration-targets.jsonl",
            "sealed-targets/targets.jsonl",
        )
        return candidate, source, candidate_manifest

    def test_preoutput_pass_and_artifacts_written_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            root = Path(workdir)
            protocol_path = root / "protocol.json"
            protocol_path.write_text(json.dumps(self.protocol, indent=2), encoding="utf-8")
            candidate, source, _ = self._setup_corpus(root, self.protocol["protocol_id"])
            output_dir = root / "out"

            with patch("latent_triz.a0r1_preoutput.run_a0r1_independence_audit", return_value=self.independence_pass) as ind:
                with patch("latent_triz.a0r1_preoutput.audit_a0_shortcuts", return_value=self.shortcuts_pass) as shortcuts:
                    summary = run_a0r1_preoutput_audits(
                        protocol_path=protocol_path,
                        candidate_corpus_dir=candidate,
                        source_corpus_dir=source,
                        output_dir=output_dir,
                    )
                    self.assertEqual("pass", summary["status"])
                    self.assertFalse(summary["model_output_accessed"])
                    self.assertTrue(summary["candidate_sealed_targets_accessed_by_independence_audit"])
                    self.assertFalse(summary["candidate_sealed_targets_accessed_by_shortcut_audit"])

                    independence_art = json.loads((output_dir / "independence.json").read_text(encoding="utf-8"))
                    shortcuts_art = json.loads((output_dir / "shortcuts.json").read_text(encoding="utf-8"))
                    summary_art = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
                    manifest_art = json.loads((output_dir / "preoutput-manifest.json").read_text(encoding="utf-8"))

                    self.assertEqual("a0-r1-preoutput-summary", summary_art["artifact_class"])
                    self.assertEqual(manifest_art["protocol_status"], "planned")
                    self.assertEqual(summary["protocol_status"], "planned")
                    self.assertEqual(
                        "a0-r1-preoutput-manifest",
                        manifest_art["artifact_class"],
                    )
                    self.assertTrue(ind.called)
                    self.assertTrue(shortcuts.called)
                    shortcut_args, _shortcut_kwargs = shortcuts.call_args
                    called_cases, called_calibration, called_protocol = shortcut_args
                    self.assertEqual(candidate.resolve() / "cases.jsonl", called_cases)
                    self.assertEqual(candidate.resolve() / "procedural-targets/calibration-targets.jsonl", called_calibration)
                    self.assertEqual("protocol.json", called_protocol.name)
                    self.assertNotIn("sealed-targets", str(shortcut_args[1]))

                    self.assertEqual(independence_art["status"], "pass")
                    self.assertEqual(shortcuts_art["overall"]["status"], "pass")

    def test_preoutput_refuses_protocol_id_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            root = Path(workdir)
            protocol_path = root / "protocol.json"
            protocol_path.write_text(json.dumps(self.protocol, indent=2), encoding="utf-8")
            candidate, source, _ = self._setup_corpus(root, self.protocol["protocol_id"], include_protocol_match=False)
            with self.assertRaises(A0R1PreoutputError):
                run_a0r1_preoutput_audits(
                    protocol_path=protocol_path,
                    candidate_corpus_dir=candidate,
                    source_corpus_dir=source,
                    output_dir=root / "out",
                )

    def test_preoutput_refuses_non_empty_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            root = Path(workdir)
            protocol_path = root / "protocol.json"
            protocol_path.write_text(json.dumps(self.protocol, indent=2), encoding="utf-8")
            candidate, source, _ = self._setup_corpus(root, self.protocol["protocol_id"])
            output_dir = root / "out"
            output_dir.mkdir()
            (output_dir / "old.txt").write_text("keep", encoding="utf-8")
            with patch("latent_triz.a0r1_preoutput.run_a0r1_independence_audit", return_value=self.independence_pass):
                with patch("latent_triz.a0r1_preoutput.audit_a0_shortcuts", return_value=self.shortcuts_pass):
                    with self.assertRaises(A0R1PreoutputError):
                        run_a0r1_preoutput_audits(
                            protocol_path=protocol_path,
                            candidate_corpus_dir=candidate,
                            source_corpus_dir=source,
                            output_dir=output_dir,
                        )

    def test_preoutput_refuses_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            root = Path(workdir)
            protocol_path = root / "protocol.json"
            protocol_path.write_text(json.dumps(self.protocol, indent=2), encoding="utf-8")
            candidate, source, candidate_manifest = self._setup_corpus(root, self.protocol["protocol_id"])
            candidate_cases = candidate / "cases.jsonl"
            candidate_cases.write_text(candidate_cases.read_text(encoding="utf-8") + "{}", encoding="utf-8")

            with self.assertRaises(A0R1PreoutputError):
                run_a0r1_preoutput_audits(
                    protocol_path=protocol_path,
                    candidate_corpus_dir=candidate,
                    source_corpus_dir=source,
                    output_dir=root / "out",
                )


if __name__ == "__main__":
    unittest.main()
