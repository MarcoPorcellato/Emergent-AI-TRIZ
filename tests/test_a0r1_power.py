from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0r1_power import A0R1PowerError, calibrate_a0r1_power


class A0R1PowerTests(unittest.TestCase):
    protocol = Path(__file__).resolve().parents[1] / "results/a0r1/freeze/protocol-planned.json"

    def _mutate_protocol(self, **updates: object) -> Path:
        payload = json.loads(self.protocol.read_text(encoding="utf-8"))
        for dotted_key, value in updates.items():
            target = payload
            parts = dotted_key.split(".")
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = value
        directory = Path(tempfile.mkdtemp(prefix="a0r1-power-"))
        path = directory / "protocol.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def _run_default(self, protocol_path: Path | None = None):
        return calibrate_a0r1_power(protocol_path or self.protocol)

    def test_deterministic_reproducible_output(self) -> None:
        first = self._run_default()
        second = self._run_default()
        self.assertEqual(first, second)

    def test_expected_exact_values_and_status(self) -> None:
        result = self._run_default()
        selected = result["selected"]

        self.assertEqual(result["status"], "pass")
        self.assertNotEqual(result["status"], "failed")
        self.assertEqual(selected["family_count"], 24)
        self.assertEqual(selected["critical_successes"], 17)
        self.assertEqual(selected["families_per_domain"], 4)
        self.assertEqual(selected["permutation_budget"], 999)
        self.assertTrue(selected["minimum_attainable_p"] <= 0.001 + 1e-12)

        expected_fpr = 0.03195732831954956
        expected_power = 0.9108287412264922
        expected_mde = 0.2597184664182352

        self.assertTrue(math.isclose(selected["exact_false_positive_rate"], expected_fpr, rel_tol=0.0, abs_tol=1e-12))
        self.assertTrue(math.isclose(selected["exact_power_at_target_success_probability"], expected_power, rel_tol=0.0, abs_tol=1e-12))
        self.assertTrue(math.isclose(selected["minimum_detectable_effect"], expected_mde, rel_tol=0.0, abs_tol=1e-12))

    def test_empirical_confirmation_close_to_exact(self) -> None:
        result = self._run_default()
        selected = result["selected"]
        self.assertEqual(result["simulation"]["seed"], 20260815)
        self.assertEqual(result["simulation"]["trials"], 100000)
        self.assertEqual(result["simulation"]["passes_empirical_check"], True)

        self.assertLess(abs(selected["empirical_null_fpr"] - selected["exact_false_positive_rate"]), 0.01)
        self.assertLess(abs(selected["empirical_target_power"] - selected["exact_power_at_target_success_probability"]), 0.01)
        self.assertEqual(result["simulation"]["empirical_resolution"], 1.0 / 100000)

    def test_strict_epistemic_envelope(self) -> None:
        result = self._run_default()
        self.assertTrue(result["empirical"])
        self.assertEqual(result["scientific_status"], "exploratory")
        self.assertFalse(result["evidence_eligible"])
        self.assertFalse(result["expert_validated"])
        self.assertEqual(result["claim_ids"], [])

    def test_fail_closed_if_status_not_planned(self) -> None:
        path = self._mutate_protocol(**{"status": "frozen"})
        with self.assertRaises(A0R1PowerError):
            self._run_default(path)

    def test_fail_closed_if_multiplicity_mutates(self) -> None:
        path = self._mutate_protocol(**{"primary_endpoint.multiplicity": 2})
        with self.assertRaises(A0R1PowerError):
            self._run_default(path)

    def test_fail_closed_if_thresholds_mutate(self) -> None:
        path = self._mutate_protocol(**{"thresholds.critical_successes": 18})
        with self.assertRaises(A0R1PowerError):
            self._run_default(path)

    def test_pass_requires_exact_and_empirical_gates(self) -> None:
        result = self._run_default()
        self.assertLessEqual(result["selected"]["exact_false_positive_rate"], 0.05)
        self.assertGreaterEqual(result["selected"]["exact_power_at_target_success_probability"], 0.8)
        self.assertLessEqual(result["selected"]["minimum_detectable_effect"], 0.30)


if __name__ == "__main__":
    unittest.main()
