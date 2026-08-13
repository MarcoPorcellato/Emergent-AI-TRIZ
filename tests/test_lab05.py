from __future__ import annotations

import json
import random
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.lab05 import run_lab05


class Lab05Tests(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    def _build_cases_and_reps(self, workspace: Path) -> tuple[Path, Path]:
        cases_path = workspace / "cases.jsonl"
        reps_path = workspace / "reps.jsonl"
        definitions = (
            ("s1", "manufacturing", "segmentation", (3.0, 0.0)),
            ("s2", "packaging", "segmentation", (2.0, 0.0)),
            ("i1", "software", "inversion", (0.0, 3.0)),
            ("i2", "logistics", "inversion", (0.0, 2.0)),
            ("m1", "construction", "merging", (1.0, 1.0)),
            ("m2", "healthcare", "merging", (1.0, 2.0)),
            ("u1", "energy", "universality", (-1.0, 1.0)),
            ("u2", "education", "universality", (-2.0, 1.0)),
        )
        cases = [
            {
                "case_id": case_id,
                "domain": domain,
                "labels": [{"principle": label}],
            }
            for case_id, domain, label, _ in definitions
        ]
        reps = []
        for layer in (0, 1):
            for case_id, _domain, _label, vector in definitions:
                transformed = list(vector if layer == 0 else (vector[1], -vector[0]))
                reps.append(
                    {
                        "record_id": f"{case_id}-l{layer}",
                        "case_id": case_id,
                        "layer_index": layer,
                        "representation_type": "synthetic_process_vector",
                        "source": {"kind": "synthetic_process_fixture", "path": "fixture"},
                        "vector": transformed,
                        "vector_dim": 2,
                        "provenance": {"synthetic": True},
                        "non_claim_boundary": {"empirical": False, "evidence_eligible": False, "claim_ids": []},
                    }
                )
        self._write_jsonl(cases_path, cases)
        self._write_jsonl(reps_path, reps)
        return cases_path, reps_path

    def _run(self, cases_path: Path, reps_path: Path, seed: int = 101) -> dict:
        return run_lab05(
            cases_path,
            reps_path,
            seed=seed,
            min_cases_per_label=2,
            min_domains=2,
            unrelated_labels=("merging", "universality"),
        )

    def test_lab05_math_and_projection_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            cases_path, reps_path = self._build_cases_and_reps(Path(tempdir))
            result = self._run(cases_path, reps_path)
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["artifact_class"], "candidate-direction-instrumentation")
            self.assertFalse(result["empirical"])
            self.assertFalse(result["evidence_eligible"])
            self.assertEqual(result["claim_ids"], [])
            layer = result["layers"][0]
            self.assertTrue(layer["candidate_direction"]["available"])
            self.assertGreater(layer["candidate_direction"]["l2_norm"], 0.0)
            self.assertEqual(len(layer["norm_matched_random_controls"]["controls"]), 3)
            self.assertTrue(all(row["available"] for row in layer["unrelated_label_controls"]))
            self.assertGreater(
                layer["candidate_direction"]["target_mean_projection"],
                layer["candidate_direction"]["contrast_mean_projection"],
            )

    def test_lab05_is_deterministic_and_order_invariant(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            cases_path, reps_path = self._build_cases_and_reps(root)
            cases_lines = cases_path.read_text(encoding="utf-8").splitlines()
            reps_lines = reps_path.read_text(encoding="utf-8").splitlines()
            random.Random(7).shuffle(cases_lines)
            random.Random(11).shuffle(reps_lines)
            perm_cases = root / "cases-permuted.jsonl"
            perm_reps = root / "reps-permuted.jsonl"
            perm_cases.write_text("\n".join(cases_lines) + "\n", encoding="utf-8")
            perm_reps.write_text("\n".join(reps_lines) + "\n", encoding="utf-8")
            first = self._run(cases_path, reps_path, seed=777)
            second = self._run(perm_cases, perm_reps, seed=777)
            self.assertEqual(first["status"], second["status"])
            self.assertEqual(first["gates"], second["gates"])
            for left, right in zip(first["layers"], second["layers"], strict=True):
                self.assertEqual(
                    left["candidate_direction"]["unit_vector_sha256"],
                    right["candidate_direction"]["unit_vector_sha256"],
                )

    def test_lab05_leakage_rejects_representation_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            cases_path, reps_path = self._build_cases_and_reps(root)
            rows = [json.loads(line) for line in reps_path.read_text(encoding="utf-8").splitlines()]
            rows[0]["target_label"] = "segmentation"
            leak_path = root / "reps-leak.jsonl"
            self._write_jsonl(leak_path, rows)
            result = self._run(cases_path, leak_path)
            self.assertEqual(result["status"], "fail")
            self.assertEqual(next(row for row in result["gates"] if row["gate"] == "D2")["status"], "fail")

    def test_lab05_no_dense_vectors_or_interventions_in_output(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            cases_path, reps_path = self._build_cases_and_reps(Path(tempdir))
            result = self._run(cases_path, reps_path)
            payload = json.dumps(result, sort_keys=True)
            self.assertNotIn('"vector":', payload)
            self.assertFalse(result["publication_boundary"]["dense_vectors_published"])
            self.assertFalse(result["publication_boundary"]["interventions_executed"])

    def test_repository_fixture_fails_scientifically_without_contrast(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        result = run_lab05(
            repo / "data/pilot/cases.jsonl",
            repo / "data/pilot/representations.jsonl",
            seed=1729,
        )
        self.assertEqual(result["status"], "fail")
        self.assertFalse(result["evidence_eligible"])
        self.assertEqual(result["claim_ids"], [])
        self.assertIn("target/contrast case minimum is not met", result["issues"])


if __name__ == "__main__":
    unittest.main()
