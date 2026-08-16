from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz import a0r2_runner as base_runner  # noqa: E402
from latent_triz import a0r2c1_runner as c1_runner  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = c1_runner.RUN_ID


class A0R2C1RunnerTests(unittest.TestCase):
    def test_exact_run_id_is_enforced_before_material_work(self) -> None:
        with patch.object(c1_runner, "verify_a0r2c1_contract") as contract:
            with self.assertRaisesRegex(base_runner.A0R2RunnerError, "corrective run-id"):
                c1_runner.main(["--root", str(ROOT), "--run-id", "wrong", "--created-at", "2026-08-16T00:00:00Z", "--stage", "verify"])
        contract.assert_not_called()

    def test_missing_authorization_stops_before_base_execution_or_model(self) -> None:
        error = base_runner.A0R2RunnerError("missing corrective authorization")
        with patch.object(c1_runner, "verify_a0r2c1_contract"), patch.object(c1_runner, "verify_a0r2c1_authorization", side_effect=error), patch.object(base_runner, "verify_a0r2_execution_contract") as execution, patch.object(base_runner, "run_a0r2_activations") as activate, patch.object(base_runner, "_record_failure"), patch.object(base_runner, "_best_effort_failure_publication"):
            result = c1_runner.main(["--root", str(ROOT), "--run-id", RUN_ID, "--created-at", "2026-08-16T00:00:00Z", "--stage", "all", "--model-root", str(ROOT / "artifacts/models/smollm2-360m-f8027fd0")])
        self.assertEqual(1, result)
        execution.assert_not_called()
        activate.assert_not_called()

    def test_verify_stage_requires_no_material_authorization(self) -> None:
        sentinel = object()
        with tempfile.TemporaryDirectory() as directory:
            artifacts = base_runner.A0R2RunnerArtifacts(Path(directory), Path(directory))
            Path(directory).mkdir(exist_ok=True)
            with patch.object(c1_runner, "verify_a0r2c1_contract"), patch.object(c1_runner, "verify_a0r2c1_authorization", side_effect=AssertionError("authorization must not run")), patch.object(base_runner, "verify_a0r2_execution_contract"), patch.object(base_runner, "_validate_shortcuts", return_value=Path("shortcuts.json")), patch.object(base_runner, "_artifacts", return_value=artifacts), patch.object(base_runner, "_run_verify", return_value=sentinel) as verify:
                result = c1_runner.main(["--root", str(ROOT), "--run-id", RUN_ID, "--created-at", "2026-08-16T00:00:00Z", "--stage", "verify"])
        self.assertEqual(0, result)
        verify.assert_called_once()

    def test_corrected_adapter_factory_is_installed_and_restored(self) -> None:
        original = base_runner.run_a0r2_activations
        observed: list[object] = []

        def fake_base_main(_arguments: list[str]) -> int:
            observed.append(base_runner.run_a0r2_activations)
            return 0

        with patch.object(c1_runner, "verify_a0r2c1_contract"), patch.object(base_runner, "main", side_effect=fake_base_main):
            result = c1_runner.main(["--root", str(ROOT), "--run-id", RUN_ID, "--created-at", "2026-08-16T00:00:00Z", "--stage", "verify"])
        self.assertEqual(0, result)
        self.assertIs(observed[0], c1_runner._corrected_activations)
        self.assertIs(base_runner.run_a0r2_activations, original)


if __name__ == "__main__":
    unittest.main()
