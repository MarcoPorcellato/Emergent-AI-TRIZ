from __future__ import annotations

import json
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0r1_corpus import A0R1CorpusError, generate_a0r1_corpus
from latent_triz.validator import validate


class A0R1CorpusGeneratorTests(unittest.TestCase):
    protocol_path = (
        Path(__file__).resolve().parents[1] / "experiments" / "a0r1-independent-proxy" / "protocol.json"
    )
    target_fields = {"target_text", "operator_proxy_family", "ground_truth", "labels", "label"}

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_generator_is_deterministic_and_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            out_a = Path(first) / "r1"
            out_b = Path(second) / "r1"
            manifest_a = generate_a0r1_corpus(self.protocol_path, out_a)
            manifest_b = generate_a0r1_corpus(self.protocol_path, out_b)
            self.assertEqual(manifest_a, manifest_b)
            self.assertEqual((out_a / "cases.jsonl").read_bytes(), (out_b / "cases.jsonl").read_bytes())
            self.assertEqual(
                (out_a / "targets" / "calibration.jsonl").read_bytes(),
                (out_b / "targets" / "calibration.jsonl").read_bytes(),
            )
            self.assertEqual(
                (out_a / "targets" / "sealed.jsonl").read_bytes(),
                (out_b / "targets" / "sealed.jsonl").read_bytes(),
            )

    def test_counts_and_splits_match_contract(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            output = Path(workdir) / "r1"
            manifest = generate_a0r1_corpus(self.protocol_path, output)
            cases = self._read_jsonl(output / "cases.jsonl")
            cal_targets = self._read_jsonl(output / "targets" / "calibration.jsonl")
            sealed_targets = self._read_jsonl(output / "targets" / "sealed.jsonl")

            self.assertEqual(manifest["counts"]["total_cases"], 96)
            self.assertEqual(manifest["counts"]["total_targets"], 96)
            self.assertEqual(manifest["counts"]["families"], 48)
            self.assertEqual(manifest["counts"]["domains"], 6)
            self.assertEqual(len(cases), 96)
            self.assertEqual(len(cal_targets), 48)
            self.assertEqual(len(sealed_targets), 48)
            self.assertEqual(manifest["seed"], 20260815)
            self.assertEqual(manifest["deterministic_seed"], 20260815)
            self.assertEqual(manifest["license"], "Apache-2.0")
            self.assertEqual(
                {"segmentation_like", "inversion_like"},
                {row["operator_proxy_family"] for row in cal_targets + sealed_targets},
            )

            manifest_schema = json.loads(
                (self.protocol_path.parents[1].parent / "schemas/a0r1-corpus-manifest.schema.json").read_text(encoding="utf-8")
            )
            case_schema = json.loads(
                (self.protocol_path.parents[1].parent / "schemas/a0-case.schema.json").read_text(encoding="utf-8")
            )
            target_schema = json.loads(
                (self.protocol_path.parents[1].parent / "schemas/a0-procedural-target.schema.json").read_text(encoding="utf-8")
            )
            self.assertEqual([], validate(manifest, manifest_schema))
            self.assertTrue(all(not validate(row, case_schema) for row in cases))
            self.assertTrue(all(not validate(row, target_schema) for row in cal_targets + sealed_targets))

    def test_family_split_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            output = Path(workdir) / "r1"
            generate_a0r1_corpus(self.protocol_path, output)
            cases = self._read_jsonl(output / "cases.jsonl")
            by_family = defaultdict(list)
            for case in cases:
                by_family[case["problem_family_id"]].append(case["split"])
            self.assertTrue(all(len(splits) == 2 for splits in by_family.values()))
            self.assertEqual(48, len(by_family))

    def test_physical_target_partitioning(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            output = Path(workdir) / "r1"
            generate_a0r1_corpus(self.protocol_path, output)
            cal = self._read_jsonl(output / "targets" / "calibration.jsonl")
            sealed = self._read_jsonl(output / "targets" / "sealed.jsonl")
            cal_ids = {row["case_id"] for row in cal}
            sealed_ids = {row["case_id"] for row in sealed}

            self.assertEqual(len(cal), 48)
            self.assertEqual(len(sealed), 48)
            self.assertFalse(cal_ids.intersection(sealed_ids))
            self.assertTrue(all(row["split"] == "calibration" for row in cal))
            self.assertTrue(all(row["split"] == "sealed" for row in sealed))

    def test_case_records_have_no_target_surface_fields(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            output = Path(workdir) / "r1"
            generate_a0r1_corpus(self.protocol_path, output)
            cases = self._read_jsonl(output / "cases.jsonl")
            for row in cases:
                for key in row.keys():
                    lowered = key.lower()
                    self.assertFalse(
                        any(token in lowered for token in self.target_fields),
                        msg=f"case contains surfaced target-like key: {key}",
                    )

    def test_preexisting_output_dir_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            output = Path(workdir) / "r1"
            output.mkdir()
            (output / "already-there.txt").write_text("keep-me", encoding="utf-8")
            with self.assertRaises(A0R1CorpusError):
                generate_a0r1_corpus(self.protocol_path, output)

    def test_seed_override_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            with self.assertRaises(A0R1CorpusError):
                generate_a0r1_corpus(self.protocol_path, Path(workdir) / "r1", seed=20260814)


if __name__ == "__main__":
    unittest.main()
