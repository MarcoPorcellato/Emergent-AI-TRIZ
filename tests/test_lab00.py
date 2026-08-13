from __future__ import annotations

import json
import io
import shutil
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import latent_triz.lab00 as lab00
from latent_triz.lab00 import Lab00Error, build_lab00_report
from latent_triz.cli import main
from latent_triz.pilot import STANDARD_DIMENSIONS


class Lab00Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def _copy_smoke_artifacts(self, workdir: Path) -> tuple[Path, Path, Path, Path]:
        packets = self.repo_root / "data" / "pilot" / "packets.jsonl"
        responses = self.repo_root / "data" / "pilot" / "responses.jsonl"
        annotations = self.repo_root / "data" / "pilot" / "annotations.jsonl"
        summary = self.repo_root / "data" / "pilot" / "summary.json"

        packets_copy = workdir / "packets.jsonl"
        responses_copy = workdir / "responses.jsonl"
        annotations_copy = workdir / "annotations.jsonl"
        summary_copy = workdir / "summary.json"

        for source, target in (
            (packets, packets_copy),
            (responses, responses_copy),
            (annotations, annotations_copy),
            (summary, summary_copy),
        ):
            shutil.copy2(source, target)

        return packets_copy, responses_copy, annotations_copy, summary_copy

    def test_lab00_report_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            workdir_path = Path(workdir)
            packets, responses, annotations, summary = self._copy_smoke_artifacts(workdir_path)
            html1 = build_lab00_report(
                packets_path=packets,
                responses_path=responses,
                annotations_path=annotations,
                summary_path=summary,
                output_path=workdir_path / "report1.html",
            )
            html2 = build_lab00_report(
                packets_path=packets,
                responses_path=responses,
                annotations_path=annotations,
                summary_path=summary,
                output_path=workdir_path / "report2.html",
            )
            report1 = Path(html1).read_text(encoding="utf-8")
            report2 = Path(html2).read_text(encoding="utf-8")
            self.assertEqual(report1, report2)

    def test_lab00_report_content_includes_audit_banner_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            workdir_path = Path(workdir)
            packets, responses, annotations, summary = self._copy_smoke_artifacts(workdir_path)
            html = build_lab00_report(
                packets_path=packets,
                responses_path=responses,
                annotations_path=annotations,
                summary_path=summary,
            )
            self.assertIn("Non-Evidence Stage-1 Smoke Report", html)
            self.assertIn("Unblinded administrative audit view — never use this page for annotation.", html)
            self.assertIn("Infrastructure-only. Not attached to any scientific claim.", html)
            self.assertIn("Boundary", html)
            self.assertIn("problem", html)
            self.assertIn("constraints", html)
            self.assertIn("Per-arm score bars (0-4)", html)
            self.assertIn("metric directions", html)
            self.assertIn("paired deltas (normalized treatment-control)", html)
            self.assertIn("<strong>Summary</strong>", html)
            self.assertIn("[", html)
            self.assertIn("█", html)

    def test_lab00_normalizes_direction_only_for_display_without_losing_raw(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            workdir_path = Path(workdir)
            packets, responses, annotations, summary = self._copy_smoke_artifacts(workdir_path)
            generated_summary = summary
            payload = json.loads(generated_summary.read_text(encoding="utf-8"))
            payload["metric_directions"] = {
                dim: ("minimize" if dim == "terminology_only" else "maximize")
                for dim in STANDARD_DIMENSIONS
            }
            payload["paired_deltas"] = {
                "pilot_case_001": {
                    "control|treatment": {
                        "contradiction_resolution": 0.25,
                        "principle_use": 0.5,
                        "feasibility": -0.5,
                        "novelty": 0.5,
                        "constraint_adherence": 0.0,
                        "terminology_only": -1.5,
                    }
                }
            }
            payload["paired_deltas_normalized"] = {
                "pilot_case_001": {
                    "control|treatment": {
                        "contradiction_resolution": 0.25,
                        "principle_use": 0.5,
                        "feasibility": -0.5,
                        "novelty": 0.5,
                        "constraint_adherence": 0.0,
                        "terminology_only": 1.5,
                    }
                }
            }

            with patch.object(lab00, "score_annotations", return_value=payload):
                generated_summary.write_text(json.dumps(payload), encoding="utf-8")
                html = build_lab00_report(
                    packets_path=packets,
                    responses_path=responses,
                    annotations_path=annotations,
                    summary_path=generated_summary,
                )

            self.assertIn("pilot_case_001", html)
            self.assertIn("paired deltas (normalized treatment-control)", html)
            self.assertIn("terminology_only", html)

    def test_lab00_fails_if_summary_marked_empirical(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            workdir_path = Path(workdir)
            packets, responses, annotations, summary = self._copy_smoke_artifacts(workdir_path)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            payload["non_empirical"] = False
            summary.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(Lab00Error):
                build_lab00_report(
                    packets_path=packets,
                    responses_path=responses,
                    annotations_path=annotations,
                    summary_path=summary,
                )

    def test_lab00_fails_if_response_empirical(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            workdir_path = Path(workdir)
            packets, responses, annotations, summary = self._copy_smoke_artifacts(workdir_path)
            records = [json.loads(line) for line in responses.read_text(encoding="utf-8").splitlines() if line.strip()]
            records[0]["non_empirical"] = False
            responses.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

            with self.assertRaises(Lab00Error):
                build_lab00_report(
                    packets_path=packets,
                    responses_path=responses,
                    annotations_path=annotations,
                    summary_path=summary,
                )

    def test_lab00_fails_if_annotation_empirical(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            workdir_path = Path(workdir)
            packets, responses, annotations, summary = self._copy_smoke_artifacts(workdir_path)
            records = [json.loads(line) for line in annotations.read_text(encoding="utf-8").splitlines() if line.strip()]
            records[0]["non_empirical"] = False
            annotations.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

            with self.assertRaises(Lab00Error):
                build_lab00_report(
                    packets_path=packets,
                    responses_path=responses,
                    annotations_path=annotations,
                    summary_path=summary,
                )

    def test_lab00_fails_if_summary_does_not_match_sources(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            workdir_path = Path(workdir)
            packets, responses, annotations, summary = self._copy_smoke_artifacts(workdir_path)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            payload["counts"]["responses"] = 99
            summary.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(Lab00Error, "summary does not match"):
                build_lab00_report(
                    packets_path=packets,
                    responses_path=responses,
                    annotations_path=annotations,
                    summary_path=summary,
                )

    def test_lab00_cli_renders_report(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            output = Path(workdir) / "index.html"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(["lab00", "--output", str(output)])
            self.assertEqual(code, 0)
            self.assertTrue(output.is_file())
            self.assertIn("lab00: rendered", stdout.getvalue())
            self.assertEqual(stderr.getvalue(), "")

    def test_lab00_cli_reports_output_write_error(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            output = Path(workdir)
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = main(["lab00", "--output", str(output)])
            self.assertEqual(code, 1)
            self.assertIn("cannot write report", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
