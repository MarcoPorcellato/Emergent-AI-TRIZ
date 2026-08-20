import unittest

from latent_triz.exp002_analysis import Exp002AnalysisError, evaluate_transfer, exact_sign_flip_pvalue, validate_analysis_result


class Exp002AnalysisTests(unittest.TestCase):
    def test_exact_sign_flip_is_deterministic(self):
        self.assertEqual(exact_sign_flip_pvalue([1, 1, 1, 1, 1, 1, 1, 1]), 2 / 256)
        self.assertEqual(exact_sign_flip_pvalue([1, -1, 1, -1, 1, -1, 1, -1]), 1.0)

    def test_minimum_domain_gate_and_positive_rule(self):
        insufficient = evaluate_transfer([1, 1, 1], minimum_domains=8)
        self.assertEqual(insufficient["status"], "non_interpretable")
        positive = evaluate_transfer([1] * 8, minimum_domains=8, margin=0.1)
        self.assertEqual(positive["status"], "positive")
        validate_analysis_result(positive)
        self.assertEqual(evaluate_transfer([1, 1, 1, 1, 1, 1, 1, -0.01], minimum_domains=8)["status"], "null")

    def test_invalid_and_failed_envelopes(self):
        with self.assertRaises(Exp002AnalysisError):
            exact_sign_flip_pvalue([float("nan")])
        with self.assertRaises(Exp002AnalysisError):
            validate_analysis_result({"status": "positive", "domain_count": 8})


if __name__ == "__main__":
    unittest.main()
