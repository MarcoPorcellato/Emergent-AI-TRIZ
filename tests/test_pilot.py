from __future__ import annotations

import hashlib
import io
import json
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.cli import main
from latent_triz.pilot import PilotError, prepare_packets, score_annotations, stable_json_dumps, STANDARD_DIMENSIONS


class PilotCoreTests(unittest.TestCase):
    now = "2026-08-12T10:00:00Z"

    def _packet(self, packet_id: str, case_id: str, pair_id: str, arm_mapping: dict[str, str]) -> dict[str, object]:
        return {
            "packet_id": packet_id,
            "case_id": case_id,
            "pair_id": pair_id,
            "non_empirical": True,
            "arms_by_blind": arm_mapping,
            "blind_order": ["A", "B"],
            "seed": 1,
            "source": {"case_id": case_id},
        }

    def setUp(self) -> None:
        self.base_packets = [
            self._packet("p1", "case-a", "pair-1", {"A": "control", "B": "treatment"}),
            self._packet("p2", "case-b", "pair-1", {"A": "treatment", "B": "control"}),
        ]

    def _response_record(self, response_id: str, packet_id: str, blinded_arm: str, **overrides: object) -> dict[str, object]:
        record = {
            "response_id": response_id,
            "packet_id": packet_id,
            "blinded_arm": blinded_arm,
            "model": {
                "name": "pilot-smoke-model",
                "family": "synthetic",
                "revision": "non-empirical",
            },
            "response_text": "Synthetic stage-1 response",
            "generated_at": self.now,
            "non_empirical": True,
        }
        record.update(overrides)
        return record

    def _annotation_record(
        self,
        annotation_id: str,
        response_id: str,
        packet_id: str,
        blinded_arm: str,
        scores: dict[str, int],
        **overrides: object,
    ) -> dict[str, object]:
        record = {
            "annotation_id": annotation_id,
            "response_id": response_id,
            "packet_id": packet_id,
            "blinded_arm": blinded_arm,
            "rater_id": "smoke_rater_1",
            "scores": scores,
            "annotated_at": self.now,
            "non_empirical": True,
        }
        record.update(overrides)
        return record

    def _write_jsonl(self, path: Path, records: list[object]) -> None:
        path.write_text(
            "\n".join(stable_json_dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )

    def _scores(self, value: int) -> dict[str, int]:
        return {dim: value for dim in STANDARD_DIMENSIONS}

    def _base_scores(self, start=1) -> list[dict[str, int]]:
        return [
            {
                "contradiction_resolution": 4,
                "principle_use": 2,
                "feasibility": 4,
                "novelty": 1,
                "constraint_adherence": 4,
                "terminology_only": 0,
            },
            {
                "contradiction_resolution": 0,
                "principle_use": 2,
                "feasibility": 2,
                "novelty": 4,
                "constraint_adherence": 1,
                "terminology_only": 1,
            },
            {
                "contradiction_resolution": 2,
                "principle_use": 4,
                "feasibility": 0,
                "novelty": 1,
                "constraint_adherence": 2,
                "terminology_only": 4,
            },
            {
                "contradiction_resolution": 2,
                "principle_use": 2,
                "feasibility": 2,
                "novelty": 3,
                "constraint_adherence": 0,
                "terminology_only": 1,
            },
        ]

    def test_prepare_packets_is_deterministic_with_seed(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            case_file = Path(workdir) / "cases.json"
            case_file.write_text(
                json.dumps(
                    [
                        {"case_id": "case-b", "pair_id": "pair-1", "arms": ["control", "treatment"]},
                        {"case_id": "case-a", "pair_id": "pair-1", "arms": ["control", "treatment"]},
                    ]
                ),
                encoding="utf-8",
            )
            first = prepare_packets(str(case_file), ["control", "treatment"], 2026)
            second = prepare_packets(str(case_file), ["control", "treatment"], 2026)
            self.assertEqual(first, second)

    def test_prepare_packets_changes_with_different_seed(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            case_file = Path(workdir) / "cases.json"
            case_file.write_text(json.dumps([{"case_id": "case-a", "arms": ["control", "treatment"]}]), encoding="utf-8")
            first = prepare_packets(str(case_file), ["control", "treatment"], 2026)
            second = prepare_packets(str(case_file), ["control", "treatment"], 2027)
            self.assertNotEqual(first, second)

    def test_prepare_packets_defaults_pair_id_to_case_id(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            case_file = Path(workdir) / "cases.json"
            case_file.write_text(json.dumps([{"case_id": "case-a", "arms": ["control", "treatment"]}]), encoding="utf-8")
            packets = prepare_packets(str(case_file), ["control", "treatment"], 1)
            self.assertEqual(packets[0]["pair_id"], "case-a")

    def test_prepare_packets_rejects_duplicate_case_ids(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            dup = [
                {"case_id": "case-a", "arms": ["control", "treatment"]},
                {"case_id": "case-a", "arms": ["control", "treatment"]},
            ]
            case_file = Path(workdir) / "cases.json"
            case_file.write_text(json.dumps(dup), encoding="utf-8")
            with self.assertRaisesRegex(PilotError, "duplicate case_id"):
                prepare_packets(str(case_file), ["control", "treatment"], 1)

    def test_prepare_packets_rejects_incomplete_case_arms(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            bad = [{"case_id": "case-a", "arms": ["control"]}]
            case_file = Path(workdir) / "cases.json"
            case_file.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(PilotError):
                prepare_packets(str(case_file), ["control", "treatment"], 1)

    def test_prepare_packets_rejects_three_or_custom_arms(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            case_file = Path(workdir) / "cases.json"
            case_file.write_text(json.dumps([{"case_id": "case-a", "arms": ["control", "treatment", "placebo"]}]), encoding="utf-8")
            with self.assertRaises(PilotError):
                prepare_packets(str(case_file), ["control", "treatment", "placebo"], 1)
            with self.assertRaises(PilotError):
                prepare_packets(str(case_file), ["a", "b"], 1)

    def test_score_aggregates_and_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            packets_path = Path(workdir) / "packets.json"
            responses_path = Path(workdir) / "responses.jsonl"
            annotations_path = Path(workdir) / "annotations.jsonl"
            packets_path.write_text(stable_json_dumps(self.base_packets), encoding="utf-8")
            self._write_jsonl(
                responses_path,
                [
                    self._response_record("r1", "p1", "A"),
                    self._response_record("r2", "p1", "B"),
                    self._response_record("r3", "p2", "A"),
                    self._response_record("r4", "p2", "B"),
                ],
            )
            scores = self._base_scores()
            self._write_jsonl(
                annotations_path,
                [
                    self._annotation_record("a1", "r1", "p1", "A", scores[0]),
                    self._annotation_record("a2", "r2", "p1", "B", scores[1]),
                    self._annotation_record("a3", "r3", "p2", "A", scores[2]),
                    self._annotation_record("a4", "r4", "p2", "B", scores[3]),
                ],
            )

            summary = score_annotations(str(packets_path), str(responses_path), str(annotations_path))
            self.assertEqual(summary["schema_version"], "1.0")
            self.assertEqual(summary["counts"]["cases"], 2)
            self.assertEqual(summary["counts"]["packets"], 2)
            self.assertEqual(summary["counts"]["responses"], 4)
            self.assertEqual(summary["counts"]["annotations"], 4)
            self.assertEqual(summary["dimensions"], list(STANDARD_DIMENSIONS))
            self.assertEqual(summary["rater_coverage"]["minimum_distinct_raters"], 1)
            self.assertEqual(summary["rater_coverage"]["responses_with_minimum_raters"], 4)
            self.assertEqual(summary["rater_coverage"]["responses_total"], 4)
            self.assertEqual(summary["rater_coverage"]["response_rater_counts"]["r1"], 1)
            self.assertEqual(summary["agreement_diagnostics"]["mean_pairwise_absolute_difference_by_dimension"]["contradiction_resolution"], 0.0)
            self.assertAlmostEqual(summary["per_arm_means"]["control"]["novelty"], 2.0)
            self.assertAlmostEqual(summary["per_arm_means"]["treatment"]["novelty"], 2.5)
            self.assertTrue(summary["non_empirical"])
            self.assertIn("smoke_rater_1", summary["rater_coverage"]["distinct_raters"])
            self.assertEqual(
                summary["paired_deltas"]["pair-1"]["control|treatment"]["novelty"],
                0.5,
            )
            self.assertEqual(
                summary["provenance"]["packets_fingerprint"],
                f"sha256:{hashlib.sha256(packets_path.read_bytes()).hexdigest()}",
            )
            self.assertEqual(
                summary["provenance"]["responses_fingerprint"],
                f"sha256:{hashlib.sha256(responses_path.read_bytes()).hexdigest()}",
            )
            self.assertEqual(
                summary["provenance"]["annotations_fingerprint"],
                f"sha256:{hashlib.sha256(annotations_path.read_bytes()).hexdigest()}",
            )

    def test_score_non_empirical_false_when_any_false(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            packets_path = Path(workdir) / "packets.json"
            responses_path = Path(workdir) / "responses.jsonl"
            annotations_path = Path(workdir) / "annotations.jsonl"
            packets_path.write_text(stable_json_dumps(self.base_packets), encoding="utf-8")
            self._write_jsonl(
                responses_path,
                [
                    self._response_record("r1", "p1", "A", non_empirical=False),
                    self._response_record("r2", "p1", "B"),
                    self._response_record("r3", "p2", "A"),
                    self._response_record("r4", "p2", "B"),
                ],
            )
            self._write_jsonl(
                annotations_path,
                [
                    self._annotation_record("a1", "r1", "p1", "A", {k: 0 for k in STANDARD_DIMENSIONS}, non_empirical=False),
                    self._annotation_record("a2", "r2", "p1", "B", {k: 0 for k in STANDARD_DIMENSIONS}),
                    self._annotation_record("a3", "r3", "p2", "A", {k: 0 for k in STANDARD_DIMENSIONS}),
                    self._annotation_record("a4", "r4", "p2", "B", {k: 0 for k in STANDARD_DIMENSIONS}),
                ],
            )
            summary = score_annotations(str(packets_path), str(responses_path), str(annotations_path))
            self.assertFalse(summary["non_empirical"])

    def test_score_rejects_missing_response_model_or_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            packets_path = Path(workdir) / "packets.json"
            responses_path = Path(workdir) / "responses.jsonl"
            annotations_path = Path(workdir) / "annotations.jsonl"
            packets_path.write_text(stable_json_dumps([self.base_packets[0]]), encoding="utf-8")
            self._write_jsonl(
                responses_path,
                [
                    self._response_record("r1", "p1", "A", model=None),
                    self._response_record("r2", "p1", "B", generated_at=None),
                ],
            )
            self._write_jsonl(
                annotations_path,
                [
                    self._annotation_record("a1", "r1", "p1", "A", {k: 1 for k in STANDARD_DIMENSIONS}),
                    self._annotation_record("a2", "r2", "p1", "B", {k: 1 for k in STANDARD_DIMENSIONS}),
                ],
            )
            with self.assertRaises(PilotError):
                score_annotations(str(packets_path), str(responses_path), str(annotations_path))

    def test_score_rejects_missing_annotation_rater_or_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            packets_path = Path(workdir) / "packets.json"
            responses_path = Path(workdir) / "responses.jsonl"
            annotations_path = Path(workdir) / "annotations.jsonl"
            packets_path.write_text(stable_json_dumps([self.base_packets[0]]), encoding="utf-8")
            self._write_jsonl(
                responses_path,
                [
                    self._response_record("r1", "p1", "A"),
                    self._response_record("r2", "p1", "B"),
                ],
            )
            self._write_jsonl(
                annotations_path,
                [
                    self._annotation_record("a1", "r1", "p1", "A", {k: 1 for k in STANDARD_DIMENSIONS}, rater_id=None),
                    self._annotation_record("a2", "r2", "p1", "B", {k: 1 for k in STANDARD_DIMENSIONS}, annotated_at=None),
                ],
            )
            with self.assertRaises(PilotError):
                score_annotations(str(packets_path), str(responses_path), str(annotations_path))

    def test_score_rejects_duplicate_response_rater_pair(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            packets_path = Path(workdir) / "packets.json"
            responses_path = Path(workdir) / "responses.jsonl"
            annotations_path = Path(workdir) / "annotations.jsonl"
            packets_path.write_text(stable_json_dumps(self.base_packets), encoding="utf-8")
            self._write_jsonl(
                responses_path,
                [
                    self._response_record("r1", "p1", "A"),
                    self._response_record("r2", "p1", "B"),
                    self._response_record("r3", "p2", "A"),
                    self._response_record("r4", "p2", "B"),
                ],
            )
            score = self._scores(1)
            self._write_jsonl(
                annotations_path,
                [
                    self._annotation_record("a1", "r1", "p1", "A", score, rater_id="same"),
                    self._annotation_record("a2", "r1", "p1", "A", score, rater_id="same"),
                    self._annotation_record("a3", "r2", "p1", "B", score, rater_id="alt"),
                    self._annotation_record("a4", "r3", "p2", "A", score, rater_id="third"),
                    self._annotation_record("a5", "r4", "p2", "B", score, rater_id="fourth"),
                ],
            )
            with self.assertRaises(PilotError):
                score_annotations(str(packets_path), str(responses_path), str(annotations_path))

    def test_score_rejects_insufficient_distinct_raters_per_response(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            packets_path = Path(workdir) / "packets.json"
            responses_path = Path(workdir) / "responses.jsonl"
            annotations_path = Path(workdir) / "annotations.jsonl"
            packets_path.write_text(stable_json_dumps(self.base_packets), encoding="utf-8")
            self._write_jsonl(
                responses_path,
                [
                    self._response_record("r1", "p1", "A"),
                    self._response_record("r2", "p1", "B"),
                    self._response_record("r3", "p2", "A"),
                    self._response_record("r4", "p2", "B"),
                ],
            )
            scores = self._base_scores()
            self._write_jsonl(
                annotations_path,
                [
                    self._annotation_record("a1", "r1", "p1", "A", scores[0], rater_id="r1"),
                    self._annotation_record("a2", "r2", "p1", "B", scores[1], rater_id="r2"),
                    self._annotation_record("a3", "r3", "p2", "A", scores[2], rater_id="r1"),
                    self._annotation_record("a4", "r3", "p2", "A", scores[3], rater_id="r2"),
                    self._annotation_record("a5", "r4", "p2", "B", scores[3], rater_id="r4"),
                ],
            )
            with self.assertRaises(PilotError):
                score_annotations(
                    str(packets_path),
                    str(responses_path),
                    str(annotations_path),
                    minimum_distinct_raters=2,
                )

    def test_score_aggregates_with_equal_response_weighting(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            packets_path = Path(workdir) / "packets.json"
            responses_path = Path(workdir) / "responses.jsonl"
            annotations_path = Path(workdir) / "annotations.jsonl"
            packets_path.write_text(
                stable_json_dumps(
                    [
                        self._packet("p1", "case-a", "pair-1", {"A": "control", "B": "treatment"}),
                        self._packet("p2", "case-b", "pair-1", {"A": "control", "B": "treatment"}),
                    ]
                ),
                encoding="utf-8",
            )
            self._write_jsonl(
                responses_path,
                [
                    self._response_record("r1", "p1", "A"),
                    self._response_record("r2", "p1", "B"),
                    self._response_record("r3", "p2", "A"),
                    self._response_record("r4", "p2", "B"),
                ],
            )
            self._write_jsonl(
                annotations_path,
                [
                    self._annotation_record("a1", "r1", "p1", "A", self._scores(0), rater_id="r1"),
                    self._annotation_record("a2", "r2", "p1", "B", self._scores(0), rater_id="r2"),
                    self._annotation_record("a3", "r3", "p2", "A", self._scores(4), rater_id="r3"),
                    self._annotation_record("a4", "r3", "p2", "A", self._scores(4), rater_id="r4"),
                    self._annotation_record("a5", "r4", "p2", "B", self._scores(0), rater_id="r5"),
                ],
            )
            summary = score_annotations(str(packets_path), str(responses_path), str(annotations_path), minimum_distinct_raters=1)
            self.assertAlmostEqual(summary["per_arm_means"]["control"]["novelty"], 2.0)
            self.assertAlmostEqual(summary["per_arm_means"]["treatment"]["novelty"], 0.0)
            self.assertAlmostEqual(summary["agreement_diagnostics"]["mean_pairwise_absolute_difference_by_dimension"]["novelty"], 0.0)

    def test_score_rejects_duplicate_response_id(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            packets_path = Path(workdir) / "packets.json"
            responses_path = Path(workdir) / "responses.jsonl"
            annotations_path = Path(workdir) / "annotations.jsonl"
            packets_path.write_text(stable_json_dumps(self.base_packets), encoding="utf-8")
            self._write_jsonl(
                responses_path,
                [self._response_record("r1", "p1", "A"), self._response_record("r1", "p1", "B")],
            )
            with self.assertRaisesRegex(PilotError, "duplicate response_id"):
                score_annotations(str(packets_path), str(responses_path), str(annotations_path))

    def test_score_rejects_missing_responses(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            packets_path = Path(workdir) / "packets.json"
            responses_path = Path(workdir) / "responses.jsonl"
            annotations_path = Path(workdir) / "annotations.jsonl"
            packets_path.write_text(stable_json_dumps(self.base_packets), encoding="utf-8")
            self._write_jsonl(
                responses_path,
                [
                    self._response_record("r1", "p1", "A"),
                    self._response_record("r2", "p1", "B"),
                    self._response_record("r3", "p2", "A"),
                ],
            )
            self._write_jsonl(
                annotations_path,
                [
                    self._annotation_record("a1", "r1", "p1", "A", self._scores(1)),
                    self._annotation_record("a2", "r2", "p1", "B", self._scores(1)),
                    self._annotation_record("a3", "r3", "p2", "A", self._scores(1)),
                ],
            )
            with self.assertRaisesRegex(PilotError, "missing responses"):
                score_annotations(str(packets_path), str(responses_path), str(annotations_path))

    def test_score_rejects_extra_responses(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            packets_path = Path(workdir) / "packets.json"
            responses_path = Path(workdir) / "responses.jsonl"
            annotations_path = Path(workdir) / "annotations.jsonl"
            packets_path.write_text(stable_json_dumps([self.base_packets[0]]), encoding="utf-8")
            self._write_jsonl(
                responses_path,
                [
                    self._response_record("r1", "p1", "A"),
                    self._response_record("r2", "p1", "B"),
                    self._response_record("r3", "p1", "A"),
                ],
            )
            self._write_jsonl(
                annotations_path,
                [
                    self._annotation_record("a1", "r1", "p1", "A", self._scores(1)),
                    self._annotation_record("a2", "r2", "p1", "B", self._scores(1)),
                    self._annotation_record("a3", "r3", "p1", "A", self._scores(1)),
                ],
            )
            with self.assertRaisesRegex(PilotError, "multiple responses for packet"):
                score_annotations(str(packets_path), str(responses_path), str(annotations_path))

    def test_score_rejects_unknown_response_in_annotation(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            packets_path = Path(workdir) / "packets.json"
            responses_path = Path(workdir) / "responses.jsonl"
            annotations_path = Path(workdir) / "annotations.jsonl"
            packets_path.write_text(stable_json_dumps([self.base_packets[0]]), encoding="utf-8")
            self._write_jsonl(
                responses_path,
                [
                    self._response_record("r1", "p1", "A"),
                    self._response_record("r2", "p1", "B"),
                ],
            )
            self._write_jsonl(
                annotations_path,
                [
                    self._annotation_record("a1", "r1", "p1", "A", self._scores(1)),
                    self._annotation_record("a2", "rx", "p1", "B", self._scores(1)),
                ],
            )
            with self.assertRaisesRegex(PilotError, "annotation for unknown response"):
                score_annotations(str(packets_path), str(responses_path), str(annotations_path))

    def test_score_rejects_annotation_packet_arm_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            packets_path = Path(workdir) / "packets.json"
            responses_path = Path(workdir) / "responses.jsonl"
            annotations_path = Path(workdir) / "annotations.jsonl"
            packets_path.write_text(stable_json_dumps([self.base_packets[0]]), encoding="utf-8")
            self._write_jsonl(
                responses_path,
                [
                    self._response_record("r1", "p1", "A"),
                    self._response_record("r2", "p1", "B"),
                ],
            )
            self._write_jsonl(
                annotations_path,
                [
                    self._annotation_record("a1", "r1", "p1", "A", self._scores(1)),
                    self._annotation_record("a2", "r2", "p1", "A", self._scores(1)),
                ],
            )
            with self.assertRaisesRegex(PilotError, "does not match blinded_arm"):
                score_annotations(str(packets_path), str(responses_path), str(annotations_path))

    def test_score_rejects_missing_dimension(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            packets_path = Path(workdir) / "packets.json"
            responses_path = Path(workdir) / "responses.jsonl"
            annotations_path = Path(workdir) / "annotations.jsonl"
            packets_path.write_text(stable_json_dumps([self.base_packets[0]]), encoding="utf-8")
            self._write_jsonl(
                responses_path,
                [
                    self._response_record("r1", "p1", "A"),
                    self._response_record("r2", "p1", "B"),
                ],
            )
            incomplete = [k for k in list(STANDARD_DIMENSIONS)[1:]]
            self._write_jsonl(
                annotations_path,
                [
                    self._annotation_record(
                        "a1",
                        "r1",
                        "p1",
                        "A",
                        {k: 1 for k in incomplete},
                    ),
                    self._annotation_record(
                        "a2",
                        "r2",
                        "p1",
                        "B",
                        {k: 1 for k in incomplete},
                    ),
                ],
            )
            with self.assertRaisesRegex(PilotError, "configured dimensions"):
                score_annotations(str(packets_path), str(responses_path), str(annotations_path))

    def test_score_rejects_extra_score_dimension(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            packets_path = Path(workdir) / "packets.json"
            responses_path = Path(workdir) / "responses.jsonl"
            annotations_path = Path(workdir) / "annotations.jsonl"
            packets_path.write_text(stable_json_dumps([self.base_packets[0]]), encoding="utf-8")
            self._write_jsonl(responses_path, [self._response_record("r1", "p1", "A"), self._response_record("r2", "p1", "B")])
            invalid_scores = self._scores(1)
            invalid_scores["unexpected_dimension"] = 1
            self._write_jsonl(
                annotations_path,
                [
                    self._annotation_record("a1", "r1", "p1", "A", invalid_scores),
                    self._annotation_record("a2", "r2", "p1", "B", self._scores(1)),
                ],
            )
            with self.assertRaisesRegex(PilotError, "configured dimensions"):
                score_annotations(str(packets_path), str(responses_path), str(annotations_path))

    def test_cli_pilot_prepare_and_score_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            case_file = Path(workdir) / "cases.json"
            packets_file = Path(workdir) / "packets.jsonl"
            responses_file = Path(workdir) / "responses.jsonl"
            annotations_file = Path(workdir) / "annotations.jsonl"

            case_file.write_text(json.dumps([{"case_id": "case-a", "arms": ["control", "treatment"]}], ensure_ascii=False), encoding="utf-8")

            out = io.StringIO()
            err = io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = main(
                    [
                        "pilot-prepare",
                        "--seed",
                        "99",
                        "--arms",
                        "control",
                        "treatment",
                        "--cases",
                        str(case_file),
                        "--output",
                        str(packets_file),
                        "--format",
                        "jsonl",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(err.getvalue(), "")

            packets_lines = packets_file.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(packets_lines), 1)
            packet = json.loads(packets_lines[0])

            blind = sorted(packet["arms_by_blind"])
            self._write_jsonl(
                responses_file,
                [
                    self._response_record("r1", packet["packet_id"], blind[0]),
                    self._response_record("r2", packet["packet_id"], blind[1]),
                ],
            )
            self._write_jsonl(
                annotations_file,
                [
                    self._annotation_record("a1", "r1", packet["packet_id"], blind[0], self._scores(3)),
                    self._annotation_record("a2", "r2", packet["packet_id"], blind[1], self._scores(4)),
                ],
            )

            out_score = io.StringIO()
            err_score = io.StringIO()
            with redirect_stdout(out_score), redirect_stderr(err_score):
                code_score = main(
                    [
                        "pilot-score",
                        "--packets",
                        str(packets_file),
                        "--responses",
                        str(responses_file),
                        "--annotations",
                        str(annotations_file),
                        "--output",
                        "-",
                    ]
                )
            self.assertEqual(code_score, 0)
            self.assertEqual(err_score.getvalue(), "")
            score = json.loads(out_score.getvalue())
            self.assertEqual(score["counts"]["annotations"], 2)
            self.assertEqual(score["counts"]["responses"], 2)

    def test_cli_prepare_outputs_json_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            case_file = Path(workdir) / "cases.json"
            case_file.write_text(json.dumps([{"case_id": "case-a", "arms": ["control", "treatment"]}]), encoding="utf-8")
            out = io.StringIO()
            err = io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = main(
                    [
                        "pilot-prepare",
                        "--seed",
                        "123",
                        "--arms",
                        "control",
                        "treatment",
                        "--cases",
                        str(case_file),
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(err.getvalue(), "")
            payload = json.loads(out.getvalue())
            self.assertIsInstance(payload, list)
            self.assertIn("packet_id", payload[0])

    def test_cli_prepare_rejects_non_object_json_array_record(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            case_file = Path(workdir) / "cases.json"
            case_file.write_text("[1]", encoding="utf-8")
            err = io.StringIO()
            with redirect_stderr(err):
                code = main(
                    [
                        "pilot-prepare",
                        "--seed",
                        "123",
                        "--arms",
                        "control",
                        "treatment",
                        "--cases",
                        str(case_file),
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(code, 1)
            self.assertIn("non-object JSON array record", err.getvalue())
            self.assertNotIn("Traceback", err.getvalue())


if __name__ == "__main__":
    unittest.main()
