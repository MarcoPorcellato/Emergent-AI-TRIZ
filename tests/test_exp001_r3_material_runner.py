from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from latent_triz import exp001_r3_material_runner as runner


def _records():
    return [{"record_id": f"r{i}", "prompt": "choose", "options": [{"id": x, "description": x} for x in "ABCD"]} for i in range(85)]


def _responses(records):
    return [{"record_id": r["record_id"], "scores": {x: 0.0 for x in "ABCD"}, "prompt_sha256": "0" * 64} for r in records]


class MaterialRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "experiments/exp001-reference-integrated").mkdir(parents=True)
        (self.root / "experiments/exp001-reference-integrated/analysis-plan.json").write_text("{}", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def _preflight(self, *_):
        return {"status": "ready_for_material_execution"}

    def _report(self, **_):
        return None

    def test_success_writes_three_core_artifacts_and_one_target_read(self):
        records = _records()
        fake_analysis = {"analysis": {"status": "null", "primary": {"mean_domain_delta": 0.0, "two_sided_exact_p": 1.0, "bootstrap_95_ci": [-1.0, 1.0], "all_domain_directions_positive": False}}, "access": {}, "public_record_count": 85}
        reader = unittest.mock.Mock(return_value=[])
        with patch.object(runner, "_records", return_value=records), patch.object(runner, "execute_public_responses", return_value=_responses(records)), patch.object(runner, "run_analysis_boundary", return_value=fake_analysis):
            result = runner.run_material(root=self.root, run_id="ok", authorization={}, adapter=object(), target_reader=reader, created_at="2026-08-18T00:00:00Z", preflight_fn=self._preflight, report_fn=self._report)
        self.assertEqual(result["status"], "null")
        self.assertTrue((self.root / "results/exp001-r3/ok/response-index.json").is_file())
        self.assertTrue((self.root / "results/exp001-r3/ok/statistical-result.json").is_file())
        self.assertTrue((self.root / "results/exp001-r3/ok/execution-receipt.json").is_file())

    def test_invalid_response_stops_before_reader(self):
        reader = unittest.mock.Mock()
        with patch.object(runner, "_records", return_value=_records()), patch.object(runner, "execute_public_responses", side_effect=ValueError("bad response")):
            result = runner.run_material(root=self.root, run_id="invalid", authorization={}, adapter=object(), target_reader=reader, created_at="2026-08-18T00:00:00Z", preflight_fn=self._preflight, report_fn=self._report)
        self.assertEqual(result["status"], "failed")
        reader.assert_not_called()
        self.assertTrue((self.root / "results/exp001-r3/invalid/statistical-result.json").is_file())

    def test_reader_failure_is_terminal_and_target_read_is_recorded(self):
        records = _records()
        reader = unittest.mock.Mock(side_effect=RuntimeError("sealed key failure"))
        def boundary(_records, _responses, target_reader, _plan):
            target_reader(_records)
            raise RuntimeError("sealed key failure")
        with patch.object(runner, "_records", return_value=records), patch.object(runner, "execute_public_responses", return_value=_responses(records)), patch.object(runner, "run_analysis_boundary", side_effect=boundary):
            result = runner.run_material(root=self.root, run_id="reader", authorization={}, adapter=object(), target_reader=reader, created_at="2026-08-18T00:00:00Z", preflight_fn=self._preflight, report_fn=self._report)
        self.assertEqual(result["status"], "failed")
        reader.assert_called_once()

    def test_existing_package_is_not_overwritten(self):
        directory = self.root / "results/exp001-r3/existing"
        directory.mkdir(parents=True)
        marker = directory / "marker"
        marker.write_text("keep", encoding="utf-8")
        with self.assertRaises(runner.Exp001MaterialRunnerError):
            runner.run_material(root=self.root, run_id="existing", authorization={}, adapter=object(), target_reader=lambda _: [], preflight_fn=self._preflight, report_fn=self._report)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_resource_cap_is_terminal_before_model_output(self):
        reader = unittest.mock.Mock()
        with patch.object(runner, "_records", return_value=_records()), patch.object(runner, "execute_public_responses") as execute:
            result = runner.run_material(root=self.root, run_id="cap", authorization={}, adapter=object(), target_reader=reader, resource_probe=lambda: {"wall_seconds": 1801, "peak_rss_bytes": 0}, preflight_fn=self._preflight, report_fn=self._report)
        self.assertEqual(result["status"], "incompatible")
        execute.assert_not_called()
        reader.assert_not_called()

    def test_wall_cap_after_public_scoring_is_terminal(self):
        reader = unittest.mock.Mock()
        ticks = iter((0.0, 1.0, 1801.0))
        with patch.object(runner, "_records", return_value=_records()), patch.object(runner, "execute_public_responses", return_value=_responses(_records())) as execute:
            result = runner.run_material(root=self.root, run_id="wall-after-score", authorization={}, adapter=object(), target_reader=reader, clock=lambda: next(ticks), preflight_fn=self._preflight, report_fn=self._report)
        self.assertEqual(result["status"], "incompatible")
        execute.assert_called_once()
        reader.assert_not_called()

    def test_report_failure_is_returned_and_recovery_observation_preserves_artifacts(self):
        records = _records()
        fake_analysis = {"analysis": {"status": "null", "primary": {"mean_domain_delta": 0.0, "two_sided_exact_p": 1.0, "bootstrap_95_ci": [-1.0, 1.0], "all_domain_directions_positive": False}}, "access": {}, "public_record_count": 85}
        def failing_report(**_):
            raise OSError("report writer unavailable")
        with patch.object(runner, "_records", return_value=records), patch.object(runner, "execute_public_responses", return_value=_responses(records)), patch.object(runner, "run_analysis_boundary", return_value=fake_analysis):
            with self.assertRaises(runner.Exp001MaterialRunnerError) as caught:
                runner.run_material(root=self.root, run_id="report-failure", authorization={}, adapter=object(), target_reader=lambda _: [], created_at="2026-08-18T00:00:00Z", preflight_fn=self._preflight, report_fn=failing_report)
        self.assertIn("publication failed", str(caught.exception))
        package = self.root / "results/exp001-r3/report-failure"
        self.assertTrue((package / "statistical-result.json").is_file())
        observation = json.loads((package / "publication-recovery-observation.json").read_text(encoding="utf-8"))
        self.assertEqual(observation["status"], "publication_failed")

    def test_reader_failure_records_possible_access_in_receipt(self):
        records = _records()
        reader = unittest.mock.Mock(side_effect=RuntimeError("sealed key failure"))
        def boundary(_records, _responses, target_reader, _plan):
            target_reader(_records)
            raise AssertionError("reader should have failed")
        with patch.object(runner, "_records", return_value=records), patch.object(runner, "execute_public_responses", return_value=_responses(records)), patch.object(runner, "run_analysis_boundary", side_effect=boundary):
            result = runner.run_material(root=self.root, run_id="reader-access", authorization={}, adapter=object(), target_reader=reader, created_at="2026-08-18T00:00:00Z", preflight_fn=self._preflight, report_fn=self._report)
        self.assertEqual(result["status"], "failed")
        receipt = json.loads((self.root / "results/exp001-r3/reader-access/execution-receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["access"]["target_reads"], 1)
        self.assertEqual(receipt["access"]["sealed_targets_accessed"], "possibly_accessed")


if __name__ == "__main__":
    unittest.main()
