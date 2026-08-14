from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0_power import A0PowerError, calibrate_a0_power


class A0PowerTests(unittest.TestCase):
    protocol = Path(__file__).resolve().parents[1] / "experiments/a0-automated-weak-proxy/protocol.json"

    def _protocol_with(self, **updates: object) -> Path:
        payload = json.loads(self.protocol.read_text(encoding="utf-8"))
        payload["predeclared_calibration_rule"].update(updates)
        directory = Path(tempfile.mkdtemp(prefix="a0-power-"))
        path = directory / "protocol.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_exact_calibration_is_repeatable_and_choose_smallest(self) -> None:
        first = calibrate_a0_power(self.protocol)
        self.assertEqual(first, calibrate_a0_power(self.protocol))
        self.assertEqual(first["status"], "pass")
        self.assertTrue(first["empirical"])
        self.assertEqual(first["scientific_status"], "exploratory")
        self.assertFalse(first["evidence_eligible"])
        self.assertFalse(first["expert_validated"])
        self.assertEqual(first["claim_ids"], [])
        passing = [row for row in first["candidates"] if row["passes"]]
        self.assertEqual(first["selected"]["families_per_domain"], passing[0]["families_per_domain"])
        self.assertEqual(first["selected"]["permutation_budget"], passing[0]["permutation_budget"])

    def test_selected_candidate_meets_frozen_targets(self) -> None:
        result = calibrate_a0_power(self.protocol)
        selected = result["selected"]
        row = next(item for item in result["candidates"] if item["families_per_domain"] == selected["families_per_domain"] and item["permutation_budget"] == selected["permutation_budget"])
        self.assertLessEqual(row["exact_familywise_false_positive_rate"], 0.06)
        self.assertGreaterEqual(row["exact_power_at_target_effect"], 0.8)
        self.assertLessEqual(row["minimum_attainable_p"], row["site_alpha"])

    def test_infeasible_rule_fails_closed(self) -> None:
        result = calibrate_a0_power(self._protocol_with(candidate_families_per_domain=[1], permutation_budgets=[1], target_power=0.99))
        self.assertEqual(result["status"], "failed_no_feasible_candidate")
        self.assertIsNone(result["selected"])

    def test_invalid_effect_is_rejected(self) -> None:
        with self.assertRaises(A0PowerError):
            calibrate_a0_power(self._protocol_with(target_effect_size=0.75))


if __name__ == "__main__":
    unittest.main()
