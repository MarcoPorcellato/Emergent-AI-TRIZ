import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Exp002AutoCliTests(unittest.TestCase):
    def test_no_model_contract_cli_reports_closed_access_boundary(self):
        environment = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        completed = subprocess.run(
            [sys.executable, "scripts/exp002_auto_contract_check.py"], cwd=ROOT,
            env=environment, check=False, capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("model_access=false", completed.stdout)
        self.assertIn("sealed_target_access=false", completed.stdout)


if __name__ == "__main__":
    unittest.main()
