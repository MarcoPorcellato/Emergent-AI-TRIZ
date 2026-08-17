"""C3 runner refusal tests: no authorization means no target or model path."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz import a0r2c3_runner as runner  # noqa: E402
from latent_triz.a0r2c3_authorization import A0R2C3AuthorizationError  # noqa: E402


class A0R2C3RunnerTests(unittest.TestCase):
    def test_missing_authorization_stops_before_source_or_target_discovery(self) -> None:
        with (
            patch.object(runner, "verify_a0r2c3_contract", return_value={"status": "pass"}),
            patch.object(runner, "verify_a0r2c3_authorization", side_effect=A0R2C3AuthorizationError("not authorized")),
            patch.object(runner, "_source_activation_dir") as source,
            patch.object(runner.base_runner, "_discover_targets_path") as targets,
        ):
            with self.assertRaisesRegex(A0R2C3AuthorizationError, "not authorized"):
                runner.main(["--root", str(ROOT), "--created-at", "2026-08-17T07:15:00Z"])
        source.assert_not_called()
        targets.assert_not_called()


if __name__ == "__main__":
    unittest.main()
