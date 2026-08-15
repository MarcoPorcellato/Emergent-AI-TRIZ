from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0_analysis import _family_successes, _macro_f1, _score_operator


class A0AnalysisTests(unittest.TestCase):
    def test_macro_f1_is_one_for_exact_predictions(self) -> None:
        self.assertEqual(_macro_f1([0, 1, 0, 1], [0, 1, 0, 1]), 1.0)

    def test_family_success_uses_paired_score_order(self) -> None:
        successes, outcomes = _family_successes(
            [-1.0, 2.0, 0.5, -0.5],
            [0, 1, 1, 0],
            ["a", "a", "b", "b"],
        )
        self.assertEqual(successes, 2)
        self.assertEqual(outcomes, {"a": True, "b": True})

    def test_leave_one_domain_operator_has_no_self_domain_weights(self) -> None:
        try:
            import numpy as np
        except ModuleNotFoundError:
            self.skipTest("numpy unavailable")
        matrix = np.asarray(
            [
                [-2.0, 0.0],
                [2.0, 0.0],
                [-1.0, 0.5],
                [1.0, 0.5],
                [-3.0, -0.5],
                [3.0, -0.5],
            ]
        )
        domains = ["a", "a", "b", "b", "c", "c"]
        operator = _score_operator(matrix, domains, alpha=1.0)
        for left, left_domain in enumerate(domains):
            for right, right_domain in enumerate(domains):
                if left_domain == right_domain:
                    self.assertEqual(operator[left, right], 0.0)


if __name__ == "__main__":
    unittest.main()
