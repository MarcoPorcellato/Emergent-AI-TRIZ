from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.a0r2_comparison import A0R2ComparisonError, compare_frozen_scores


class A0R2ComparisonTests(unittest.TestCase):
    def _inputs(self):
        labels = [value for _ in range(24) for value in (0, 1)]
        families = [f"f{index:02d}" for index in range(24) for _ in range(2)]
        scores = [value for _ in range(24) for value in (-1.0, 1.0)]
        domains = {f"d{index}": 1.0 for index in range(6)}
        return labels, families, scores, domains

    def test_identical_scores_have_complete_concordance(self) -> None:
        labels, families, scores, domains = self._inputs()
        result = compare_frozen_scores(
            r1_scores=scores,
            r2_scores=scores,
            labels=labels,
            families=families,
            r1_domain_directions=domains,
            r2_domain_directions=domains,
        )
        self.assertAlmostEqual(1.0, result["pearson_score_correlation"])
        self.assertAlmostEqual(1.0, result["spearman_score_correlation"])
        self.assertEqual(1.0, result["score_sign_agreement"])
        self.assertEqual(1.0, result["family_outcome_agreement"])
        self.assertEqual(1.0, result["domain_direction_sign_agreement"])
        self.assertFalse(result["may_affect_primary"])

    def test_reversed_scores_disagree(self) -> None:
        labels, families, scores, domains = self._inputs()
        result = compare_frozen_scores(
            r1_scores=scores,
            r2_scores=[-value for value in scores],
            labels=labels,
            families=families,
            r1_domain_directions=domains,
            r2_domain_directions={key: -value for key, value in domains.items()},
        )
        self.assertAlmostEqual(-1.0, result["pearson_score_correlation"])
        self.assertEqual(0.0, result["family_outcome_agreement"])
        self.assertEqual(0.0, result["domain_direction_sign_agreement"])

    def test_rejects_length_and_constant_vector_drift(self) -> None:
        labels, families, scores, domains = self._inputs()
        with self.assertRaises(A0R2ComparisonError):
            compare_frozen_scores(
                r1_scores=scores[:-1], r2_scores=scores, labels=labels, families=families,
                r1_domain_directions=domains, r2_domain_directions=domains,
            )
        with self.assertRaisesRegex(A0R2ComparisonError, "constant"):
            compare_frozen_scores(
                r1_scores=[1.0] * 48, r2_scores=scores, labels=labels, families=families,
                r1_domain_directions=domains, r2_domain_directions=domains,
            )


if __name__ == "__main__":
    unittest.main()
