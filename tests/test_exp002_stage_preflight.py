import unittest

from scripts.exp002_stage_preflight import preflight_stage


class Exp002StagePreflightTests(unittest.TestCase):
    def test_current_dossiers_stop_before_material_gate(self):
        for stage in ("EXP-002B", "EXP-002C"):
            result = preflight_stage(stage)
            self.assertEqual(result["status"], "approval_required")
            self.assertFalse(result["model_access"])
            self.assertFalse(result["sealed_target_access"])


if __name__ == "__main__":
    unittest.main()
