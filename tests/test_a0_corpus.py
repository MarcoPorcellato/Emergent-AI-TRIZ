from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0_corpus import (
    A0CorpusError,
    _record_hash,
    _reject_duplicate_surface,
    generate_a0_corpus,
)


class A0CorpusGeneratorTests(unittest.TestCase):
    protocol_path = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "a0-automated-weak-proxy"
        / "protocol.json"
    )

    @staticmethod
    def _jsonl(path: Path) -> list[dict]:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_real_protocol_is_deterministic_across_directories(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            manifest_a = generate_a0_corpus(self.protocol_path, Path(first) / "a0")
            manifest_b = generate_a0_corpus(self.protocol_path, Path(second) / "a0")
            self.assertEqual(manifest_a, manifest_b)
            self.assertEqual(
                (Path(first) / "a0" / "cases.jsonl").read_bytes(),
                (Path(second) / "a0" / "cases.jsonl").read_bytes(),
            )
            self.assertEqual(
                (Path(first) / "a0" / "procedural-targets" / "targets.jsonl").read_bytes(),
                (Path(second) / "a0" / "procedural-targets" / "targets.jsonl").read_bytes(),
            )

    def test_counts_splits_and_family_pairing_match_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            output = Path(workdir) / "a0"
            manifest = generate_a0_corpus(self.protocol_path, output)
            cases = self._jsonl(output / "cases.jsonl")
            targets = self._jsonl(output / "procedural-targets" / "targets.jsonl")
            self.assertEqual(manifest["counts"]["families"], 96)
            self.assertEqual(manifest["counts"]["total_cases"], 192)
            self.assertEqual(manifest["counts"]["total_targets"], 192)
            self.assertEqual(manifest["counts"]["calibration_cases"], 96)
            self.assertEqual(manifest["counts"]["sealed_cases"], 96)
            self.assertEqual(len(cases), len(targets))
            by_family: dict[str, set[str]] = {}
            for case in cases:
                by_family.setdefault(case["problem_family_id"], set()).add(case["split"])
            self.assertTrue(all(len(splits) == 1 for splits in by_family.values()))
            self.assertTrue(manifest["family_integrity"]["paired_records_by_family"])
            self.assertTrue(manifest["family_integrity"]["uniform_split_by_family"])

    def test_cases_are_label_free_and_variant_ids_are_counterbalanced(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            output = Path(workdir) / "a0"
            generate_a0_corpus(self.protocol_path, output)
            cases = self._jsonl(output / "cases.jsonl")
            targets = self._jsonl(output / "procedural-targets" / "targets.jsonl")
            target_by_case = {row["case_id"]: row for row in targets}
            variant_a_targets = {
                target_by_case[row["case_id"]]["operator_proxy_family"]
                for row in cases
                if row["solution_variant_id"] == "variant_a"
            }
            self.assertEqual(variant_a_targets, {"segmentation_like", "inversion_like"})
            for case in cases:
                self.assertNotIn("operator_proxy_family", case)
                self.assertNotIn("labels", case)
                self.assertIn(case["solution_variant_id"], {"variant_a", "variant_b"})
                surface = " ".join(
                    str(case[field])
                    for field in (
                        "problem",
                        "initial_state",
                        "desired_improvement",
                        "worsening_consequence",
                        "transformation",
                        "resulting_state",
                        "solution",
                    )
                ).lower()
                for forbidden in ("triz", "segmentation", "inversion", "operator_proxy_family"):
                    self.assertNotIn(forbidden, surface)

    def test_content_hash_links_are_recomputable(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            output = Path(workdir) / "a0"
            manifest = generate_a0_corpus(self.protocol_path, output)
            cases = self._jsonl(output / "cases.jsonl")
            targets = self._jsonl(output / "procedural-targets" / "targets.jsonl")
            targets_by_case = {row["case_id"]: row for row in targets}
            for case in cases:
                target = targets_by_case[case["case_id"]]
                self.assertEqual(
                    case["case_content_sha256"],
                    _record_hash(case, {"case_content_sha256", "target_content_sha256"}),
                )
                self.assertEqual(
                    target["target_content_sha256"],
                    _record_hash(target, {"target_content_sha256", "case_content_sha256"}),
                )
                self.assertEqual(case["target_content_sha256"], target["target_content_sha256"])
                self.assertEqual(target["case_content_sha256"], case["case_content_sha256"])
            for key in ("cases_jsonl", "targets_jsonl"):
                entry = manifest["files"][key]
                path = output / entry["path"]
                self.assertEqual(entry["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertNotIn(str(output), json.dumps(manifest))

    def test_existing_output_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            output = Path(workdir) / "a0"
            output.mkdir()
            (output / "sentinel").write_text("preserve", encoding="utf-8")
            with self.assertRaises(A0CorpusError):
                generate_a0_corpus(self.protocol_path, output)
            self.assertEqual((output / "sentinel").read_text(encoding="utf-8"), "preserve")

    def test_protocol_with_wrong_domain_count_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            protocol = json.loads(self.protocol_path.read_text(encoding="utf-8"))
            protocol["neutral_domains"] = protocol["neutral_domains"][:-1]
            bad_protocol = Path(workdir) / "protocol.json"
            bad_protocol.write_text(json.dumps(protocol), encoding="utf-8")
            with self.assertRaises(A0CorpusError):
                generate_a0_corpus(bad_protocol, Path(workdir) / "a0")

    def test_duplicate_detector_rejects_cross_family_near_copy(self) -> None:
        with self.assertRaises(A0CorpusError):
            _reject_duplicate_surface(
                "family_b",
                "the same normalized surfaced record",
                [("family_a", "the same normalized surfaced record")],
            )
        _reject_duplicate_surface(
            "family_a",
            "paired counterfactual text",
            [("family_a", "paired counterfactual text")],
        )


if __name__ == "__main__":
    unittest.main()
