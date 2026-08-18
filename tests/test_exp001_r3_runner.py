import json
import unittest
from pathlib import Path

from latent_triz.exp001_r3_primary_fixture import build_primary_records
from latent_triz.exp001_r3_secondary_fixture import build_secondary_records
from latent_triz.exp001_r3_runner import Exp001RunnerError, run_analysis_boundary


ROOT = Path(__file__).parents[1]
PLAN = json.loads((ROOT / "experiments/exp001-reference-integrated/analysis-plan.json").read_text())
UNITS = [
    json.loads(line)
    for line in (ROOT / "experiments/exp001-reference-integrated/fixtures/primary-units.jsonl").read_text().splitlines()
    if line.strip()
]
RECORDS = build_primary_records(UNITS)
MATRIX = [json.loads(line) for line in (ROOT / "experiments/exp001-reference-integrated/fixtures/matrix-cells.jsonl").read_text().splitlines() if line.strip()]
EDGES = [json.loads(line) for line in (ROOT / "experiments/exp001-reference-integrated/fixtures/tool-edges.jsonl").read_text().splitlines() if line.strip()]
COMBINED = RECORDS + build_secondary_records(MATRIX, EDGES)


def _targets(records):
    choices = ("A", "B", "C", "D")
    transfer = [record for record in records if record["record_id"].endswith("transfer-blinded")]
    positions = {record["unit_id"]: choices[index % 4] for index, record in enumerate(transfer)}
    return [{"record_id": record["record_id"], "expected_choice": positions.get(record.get("unit_id"), choices[index % 4])} for index, record in enumerate(records)]


def _responses(records):
    return [{"record_id": record["record_id"], "scores": {choice: (1.0 if choice == "A" else 0.0) for choice in ("A", "B", "C", "D")}} for record in records]


class Exp001R3RunnerTest(unittest.TestCase):
    def test_invalid_response_never_opens_sealed_reader(self):
        calls = []
        responses = _responses(COMBINED)
        responses.pop()
        with self.assertRaises(Exp001RunnerError):
            run_analysis_boundary(RECORDS, responses, lambda _: calls.append(1), PLAN)
        self.assertEqual(calls, [])

    def test_valid_response_opens_once_and_excludes_exposed_rows(self):
        calls = []

        def reader(records):
            calls.append(1)
            return _targets(records)

        result = run_analysis_boundary(COMBINED, _responses(COMBINED), reader, PLAN)
        self.assertEqual(calls, [1])
        self.assertEqual(result["access"]["sealed_target_reader_calls"], 1)
        self.assertEqual(result["primary_unit_count"], 24)
        self.assertEqual(result["exposed_rows_excluded_from_primary"], 24)
        self.assertEqual(result["secondary_summaries"]["matrix_direction_and_nonrecommendation"]["record_count"], 9)
        self.assertEqual(result["secondary_summaries"]["tool_edge_and_abstention"]["record_count"], 4)

    def test_key_failure_after_reader_is_terminal(self):
        calls = []

        def reader(records):
            calls.append(1)
            return _targets(records)[:-1]

        with self.assertRaises(Exp001RunnerError):
            run_analysis_boundary(COMBINED, _responses(COMBINED), reader, PLAN)
        self.assertEqual(calls, [1])

    def test_duplicate_choice_or_non_numeric_response_rejects_before_reader(self):
        calls = []
        responses = _responses(COMBINED)
        responses[0]["scores"]["E"] = 0.0
        with self.assertRaises(Exp001RunnerError):
            run_analysis_boundary(COMBINED, responses, lambda _: calls.append(1), PLAN)
        self.assertEqual(calls, [])

    def test_missing_secondary_rejects_before_reader(self):
        calls = []
        records = COMBINED[:-1]
        with self.assertRaises(Exp001RunnerError):
            run_analysis_boundary(records, _responses(records), lambda _: calls.append(1), PLAN)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
