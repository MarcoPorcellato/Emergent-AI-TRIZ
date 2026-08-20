import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Exp002AutoContractCheckTests(unittest.TestCase):
    def test_no_model_contract_check_passes_without_model_or_target_access(self):
        completed = subprocess.run(
            ["python3", "scripts/exp002_auto_contract_check.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("exp002-auto contract: PASS", completed.stdout)
        self.assertIn("model_access=false", completed.stdout)
        self.assertIn("sealed_target_access=false", completed.stdout)


if __name__ == "__main__":
    unittest.main()
