import json
import unittest
from pathlib import Path

from latent_triz.exp001_r3_analysis import Exp001AnalysisError, analyze_primary


ROOT = Path(__file__).parents[1]
PLAN = json.loads((ROOT / "experiments/exp001-reference-integrated/analysis-plan.json").read_text())


def _records(domain_values):
    records = []
    for domain, value in domain_values.items():
        for family in ("family-a", "family-b"):
            for replicate in (1, 2):
                records.append({
                    "unit_id": f"{domain}-{family}-{replicate}",
                    "domain": domain,
                    "problem_family": family,
                    "replicate": replicate,
                    "blinded_score": value,
                    "lexical_control_score": 0.0,
                })
    return records


class Exp001R3AnalysisTest(unittest.TestCase):
    def test_all_six_positive_domains_meet_exact_primary(self):
        result = analyze_primary(_records({f"domain-{index}": 1.0 for index in range(6)}), PLAN)
        self.assertEqual(result["status"], "positive")
        self.assertEqual(result["primary"]["two_sided_exact_p"], 0.03125)
        self.assertTrue(result["primary"]["all_domain_directions_positive"])

    def test_one_nonpositive_domain_is_null_and_cannot_be_rescued(self):
        values = {f"domain-{index}": 1.0 for index in range(6)}
        values["domain-5"] = 0.0
        result = analyze_primary(_records(values), PLAN)
        self.assertEqual(result["status"], "null")
        self.assertFalse(result["primary"]["all_domain_directions_positive"])

    def test_missing_domain_rejects_fail_closed(self):
        with self.assertRaises(Exp001AnalysisError):
            analyze_primary(_records({f"domain-{index}": 1.0 for index in range(5)}), PLAN)

    def test_duplicate_replicate_rejects_fail_closed(self):
        records = _records({f"domain-{index}": 1.0 for index in range(6)})
        records[-1]["replicate"] = 1
        with self.assertRaises(Exp001AnalysisError):
            analyze_primary(records, PLAN)


if __name__ == "__main__":
    unittest.main()
