import json
import unittest
from pathlib import Path

from latent_triz.exp001_r3_fixture_builder import build_public_record_stubs


ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "experiments/exp001-reference-integrated/fixtures"


class Exp001R3FixtureBuilderTest(unittest.TestCase):
    def setUp(self):
        self.records = build_public_record_stubs(
            FIXTURES / "control-plan.json", FIXTURES / "option-sets.jsonl"
        )

    def test_twenty_records_and_ten_pairs(self):
        self.assertEqual(len(self.records), 20)
        self.assertEqual({r["pair_id"] for r in self.records}, {
            p["pair_id"] for p in json.loads((FIXTURES / "control-plan.json").read_text())["pairs"]
        })
        self.assertEqual({r["stratum"] for r in self.records}, {
            "TRIZ-blinded-transfer", "source-exposed-competence"
        })

    def test_no_target_content_or_scoring_keys(self):
        forbidden = {"target", "target_value", "correct_option", "expected_option", "answer", "score"}
        for record in self.records:
            self.assertTrue(forbidden.isdisjoint(record))
            self.assertTrue(record["response_locator"].startswith("sealed://"))

    def test_strata_are_non_poolable_and_controls_covered(self):
        self.assertTrue(all(r["pooling_prohibited"] for r in self.records))
        self.assertEqual({r["control_kind"] for r in self.records}, {
            "primary", "lexical_matched", "principle_near_neighbour",
            "matrix_direction_swap", "matrix_non_recommended_option",
            "tool_edge_unsupported", "explicit_abstention",
        })


if __name__ == "__main__":
    unittest.main()
