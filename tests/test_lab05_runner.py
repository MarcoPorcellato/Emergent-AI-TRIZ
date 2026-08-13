from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.lab04 import stable_json_dumps
from latent_triz.lab05_runner import run_lab05_bundle


def _write_fixture(root: Path) -> tuple[Path, Path, Path]:
    cases = root / "cases.jsonl"
    reps = root / "representations.jsonl"
    config = root / "config.json"
    case_rows = []
    rep_rows = []
    labels = ("segmentation", "inversion", "merging", "universality")
    for index, label in enumerate(labels):
        case_id = f"case-{index}"
        case_rows.append({"case_id": case_id, "domain": f"domain-{index}", "labels": [{"principle": label}]})
        rep_rows.append({"case_id": case_id, "layer_index": 0, "vector_dim": 2, "vector": [float(index + 1), float(index)]})
    cases.write_text("\n".join(json.dumps(row) for row in case_rows) + "\n", encoding="utf-8")
    reps.write_text("\n".join(json.dumps(row) for row in rep_rows) + "\n", encoding="utf-8")
    config.write_text(json.dumps({
        "target_label": "segmentation", "contrast_label": "inversion",
        "unrelated_labels": ["merging", "universality"], "random_control_seeds": [1729, 1730, 1731],
        "norm_match_tolerance": 1e-12, "minimum_cases_per_label": 2, "minimum_domains_per_label": 2,
    }), encoding="utf-8")
    return cases, reps, config


def _predecessor(status: str) -> dict:
    payload = {
        "artifact_class": "representation-decodability-instrumentation", "status": status,
        "empirical": False, "evidence_eligible": False, "claim_ids": [], "hashes": {"summary_json": ""},
    }
    payload["hashes"]["summary_json"] = hashlib.sha256(stable_json_dumps(payload).encode()).hexdigest()
    return payload


class Lab05RunnerTests(unittest.TestCase):
    def test_failed_predecessor_still_emits_diagnostic_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases, reps, config = _write_fixture(root)
            artifacts = run_lab05_bundle(cases, reps, config, _predecessor("fail"), output_dir=root / "out")
            summary = json.loads(artifacts.summary.read_text())
            self.assertEqual(summary["status"], "fail")
            self.assertFalse(summary["predecessor"]["scientifically_ready"])
            self.assertTrue(summary["predecessor"]["integrity_verified"])
            self.assertEqual(summary["gates"][0]["gate"], "D1")
            self.assertEqual(summary["gates"][0]["status"], "fail")
            self.assertTrue(artifacts.report_html.is_file())

    def test_outputs_are_deterministic_and_hash_backed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases, reps, config = _write_fixture(root)
            predecessor = _predecessor("pass")
            first = run_lab05_bundle(cases, reps, config, predecessor, output_dir=root / "a")
            second = run_lab05_bundle(cases, reps, config, predecessor, output_dir=root / "b")
            for name in ("direction_result.json", "summary.json", "report.html"):
                self.assertEqual(hashlib.sha256((root / "a" / name).read_bytes()).hexdigest(), hashlib.sha256((root / "b" / name).read_bytes()).hexdigest())
            summary = json.loads(first.summary.read_text())
            canonical = dict(summary)
            canonical["hashes"] = dict(summary["hashes"])
            declared = canonical["hashes"]["summary_json"]
            canonical["hashes"]["summary_json"] = ""
            self.assertEqual(declared, hashlib.sha256(stable_json_dumps(canonical).encode()).hexdigest())
            self.assertFalse(summary["publication_boundary"]["dense_vectors_published"])
            self.assertNotIn('"unit":', first.summary.read_text())

    def test_invalid_predecessor_hash_fails_closed_without_skipping_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases, reps, config = _write_fixture(root)
            predecessor = _predecessor("pass")
            predecessor["hashes"]["summary_json"] = "0" * 64
            artifacts = run_lab05_bundle(cases, reps, config, predecessor, output_dir=root / "out")
            summary = json.loads(artifacts.summary.read_text())
            self.assertFalse(summary["predecessor"]["integrity_verified"])
            self.assertTrue(summary["layers"])
            self.assertEqual(summary["status"], "fail")


if __name__ == "__main__":
    unittest.main()
