from __future__ import annotations

import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.lab_suite import LabSuiteError, build_lab_suite_report
from latent_triz.cli import main


class LabSuiteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(tempfile.mkdtemp())
        self.output = self.repo_root / "artifacts" / "suite" / "index.html"
        self._write_repo_fixtures()

    def _write_json(self, relpath: str, payload: dict) -> Path:
        path = self.repo_root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        return path

    def _write_html(self, relpath: str, body: str) -> Path:
        path = self.repo_root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            (
                "<html><body>"
                "<h1>Lab 00 Synthetic Report</h1>"
                "<p>Infrastructure-only synthetic smoke report.</p>"
                "<p>Non-evidence process demonstration.</p>"
                f"{body}"
                "</body></html>"
            ),
            encoding="utf-8",
        )
        return path

    def _write_repo_fixtures(self) -> None:
        self._write_html("artifacts/lab00/index.html", "<p>Boundary: synthetic only.</p>")
        for relpath in (
            "results/lab01/model-anatomy/report.html",
            "results/lab02/dataset-anatomy/report.html",
            "results/lab03/behavioral-baselines/report.html",
            "results/lab04/decodability/report.html",
        ):
            path = self.repo_root / relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("<html><body>Detailed report</body></html>", encoding="utf-8")
        self._write_json(
            "results/lab01/model-anatomy/parity_report.json",
            {
                "artifact_class": "model-instrumentation",
                "status": "pass",
                "empirical": True,
                "evidence_eligible": False,
                "claim_ids": [],
            },
        )
        self._write_json(
            "results/lab02/dataset-anatomy/summary.json",
            {
                "artifact_class": "dataset-anatomy",
                "status": "fail",
                "empirical": False,
                "evidence_eligible": False,
                "claim_ids": [],
            },
        )
        self._write_json(
            "results/lab03/behavioral-baselines/summary.json",
            {
                "artifact_class": "behavioral-baseline-instrumentation",
                "status": "pass",
                "empirical": False,
                "evidence_eligible": False,
                "claim_ids": [],
            },
        )
        self._write_json(
            "results/lab04/decodability/summary.json",
            {
                "artifact_class": "representation-decodability-instrumentation",
                "status": "fail",
                "empirical": False,
                "evidence_eligible": False,
                "claim_ids": [],
            },
        )

    def _expected_file_hash(self, relpath: str) -> str:
        path = self.repo_root / relpath
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _assert_no_absolute_paths(self, html: str) -> None:
        class LinkParser(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.links: list[str] = []

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                if tag == "a":
                    self.links.extend(value for key, value in attrs if key == "href" and value is not None)

        parser = LinkParser()
        parser.feed(html)
        for link in parser.links:
            self.assertFalse(link.startswith("/"), link)
            self.assertNotIn("://", link)
            self.assertNotIn(self.repo_root.as_posix(), link)

    def test_lab_suite_report_is_deterministic(self) -> None:
        output1 = self.repo_root / "artifacts" / "suite" / "first.html"
        output2 = self.repo_root / "artifacts" / "suite" / "second.html"
        path1 = build_lab_suite_report(self.repo_root, output1)
        path2 = build_lab_suite_report(self.repo_root, output2)
        self.assertEqual(path1.read_bytes(), path2.read_bytes())

    def test_lab_suite_report_contains_boundary_text_and_status_cards(self) -> None:
        path = build_lab_suite_report(self.repo_root, self.output)
        html = path.read_text(encoding="utf-8")
        self.assertIn("Latent TRIZ Lab Suite Readiness Dashboard", html)
        self.assertIn("Not all tracked labs are pass-ready", html)
        self.assertIn("LAB01 source", html)
        self.assertIn("LAB02 source", html)
        self.assertIn("LAB03 source", html)
        self.assertIn("LAB04 source", html)
        self.assertIn("LAB00 source", html)
        self.assertIn("Synthetic/process-only", html)
        self.assertIn("Empirical instrumentation (not evidence-eligible)", html)
        self.assertIn("<span class='pill pass'>pass</span>", html)
        self.assertIn("<span class='pill fail'>fail</span>", html)

    def test_lab_suite_report_contains_hashes_and_relative_links(self) -> None:
        path = build_lab_suite_report(self.repo_root, self.output)
        html = path.read_text(encoding="utf-8")
        expected = [
            self._expected_file_hash("artifacts/lab00/index.html"),
            self._expected_file_hash("results/lab01/model-anatomy/parity_report.json"),
            self._expected_file_hash("results/lab02/dataset-anatomy/summary.json"),
            self._expected_file_hash("results/lab03/behavioral-baselines/summary.json"),
            self._expected_file_hash("results/lab04/decodability/summary.json"),
        ]
        for digest in expected:
            self.assertIn(digest, html)
        self.assertIn("artifacts/lab00/index.html", html)
        self.assertIn("results/lab01/model-anatomy/parity_report.json", html)
        self.assertIn("results/lab02/dataset-anatomy/summary.json", html)
        self.assertIn("results/lab03/behavioral-baselines/summary.json", html)
        self.assertIn("results/lab04/decodability/summary.json", html)
        self.assertIn("../../results/lab01/model-anatomy/report.html", html)
        self._assert_no_absolute_paths(html)

    def test_lab_suite_report_rejects_evidence_eligible_true(self) -> None:
        path = self.repo_root / "results/lab03/behavioral-baselines/summary.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["evidence_eligible"] = True
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        with self.assertRaises(LabSuiteError):
            build_lab_suite_report(self.repo_root, self.output)

    def test_lab_suite_report_rejects_nonempty_claim_ids(self) -> None:
        path = self.repo_root / "results/lab04/decodability/summary.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["claim_ids"] = ["C-01"]
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        with self.assertRaises(LabSuiteError):
            build_lab_suite_report(self.repo_root, self.output)

    def test_lab_suite_report_rejects_missing_or_malformed_file(self) -> None:
        path = self.repo_root / "results/lab01/model-anatomy/parity_report.json"
        path.unlink()
        with self.assertRaises(LabSuiteError):
            build_lab_suite_report(self.repo_root, self.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{", encoding="utf-8")
        with self.assertRaises(LabSuiteError):
            build_lab_suite_report(self.repo_root, self.output)

    def test_lab_suite_cli_renders_and_opens_only_when_requested(self) -> None:
        cli_output = self.repo_root / "artifacts/lab/index.html"
        with patch("latent_triz.cli.build_lab00_report", return_value=str(self.repo_root / "artifacts/lab00/index.html")):
            stdout = StringIO()
            with redirect_stdout(stdout), patch("latent_triz.cli.webbrowser.open") as open_browser:
                code = main([
                    "lab-suite",
                    "--root",
                    str(self.repo_root),
                    "--output",
                    "artifacts/lab/index.html",
                    "--open",
                ])
        self.assertEqual(code, 0)
        self.assertTrue(cli_output.is_file())
        self.assertIn("lab-suite: rendered", stdout.getvalue())
        open_browser.assert_called_once_with(cli_output.resolve().as_uri())

    def test_lab_suite_cli_does_not_open_without_flag_and_rejects_output_escape(self) -> None:
        with patch("latent_triz.cli.build_lab00_report", return_value=str(self.repo_root / "artifacts/lab00/index.html")):
            with patch("latent_triz.cli.webbrowser.open") as open_browser:
                code = main([
                    "lab-suite",
                    "--root",
                    str(self.repo_root),
                    "--output",
                    "artifacts/lab/index.html",
                ])
            self.assertEqual(code, 0)
            open_browser.assert_not_called()

            outside = self.repo_root.parent / "escaped-lab-suite.html"
            with patch("latent_triz.cli.webbrowser.open") as open_browser:
                code = main([
                    "lab-suite",
                    "--root",
                    str(self.repo_root),
                    "--output",
                    "../escaped-lab-suite.html",
                ])
            self.assertEqual(code, 1)
            self.assertFalse(outside.exists())
            open_browser.assert_not_called()

if __name__ == "__main__":
    unittest.main()
