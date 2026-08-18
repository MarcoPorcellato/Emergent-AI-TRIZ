import copy
import json
import unittest
from pathlib import Path

from latent_triz.exp001_r3_secondary_fixture import Exp001SecondaryFixtureError, build_secondary_records


ROOT = Path(__file__).parents[1]


def _load(name):
    return [json.loads(line) for line in (ROOT / "experiments/exp001-reference-integrated/fixtures" / name).read_text().splitlines() if line.strip()]


class SecondaryFixtureTests(unittest.TestCase):
    def setUp(self):
        self.cells = _load("matrix-cells.jsonl")
        self.edges = _load("tool-edges.jsonl")

    def test_builds_nine_matrix_and_four_tool_records(self):
        records = build_secondary_records(self.cells, self.edges)
        self.assertEqual(len(records), 13)
        self.assertEqual(sum(record["task_family"] == "matrix" for record in records), 9)
        self.assertEqual(sum(record["task_family"] == "tool_relationship" for record in records), 4)
        self.assertTrue(all(set(record) == {"record_id", "endpoint_id", "stratum", "task_family", "source_fixture_id", "prompt", "options", "pooling_prohibited", "response_locator"} for record in records))
        self.assertTrue(all([option["id"] for option in record["options"]] == list("ABCD") for record in records))

    def test_rejects_direction_or_recommendation_drift(self):
        bad = copy.deepcopy(self.cells)
        bad[0]["direction"] = "worsening_row_improving_column"
        with self.assertRaises(Exp001SecondaryFixtureError):
            build_secondary_records(bad, self.edges)
        bad = copy.deepcopy(self.cells)
        bad[0]["recommended_principles"] = [1, 2, 3]
        with self.assertRaises(Exp001SecondaryFixtureError):
            build_secondary_records(bad, self.edges)

    def test_rejects_selectable_unestablished_edge(self):
        bad = copy.deepcopy(self.edges)
        bad[2]["selection_allowed"] = True
        with self.assertRaises(Exp001SecondaryFixtureError):
            build_secondary_records(self.cells, bad)

    def test_rejects_wrong_inventory_and_duplicate_ids(self):
        with self.assertRaises(Exp001SecondaryFixtureError):
            build_secondary_records(self.cells[:2], self.edges)
        bad = copy.deepcopy(self.edges)
        bad[1]["edge_id"] = bad[0]["edge_id"]
        with self.assertRaises(Exp001SecondaryFixtureError):
            build_secondary_records(self.cells, bad)


if __name__ == "__main__":
    unittest.main()
