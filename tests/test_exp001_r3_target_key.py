import json
import unittest
from pathlib import Path

from latent_triz.exp001_r3_primary_fixture import build_primary_records
from latent_triz.exp001_r3_target_key import Exp001TargetKeyError, validate_sealed_target_key


ROOT = Path(__file__).parents[1]
UNITS = ROOT / "experiments/exp001-reference-integrated/fixtures/primary-units.jsonl"


def _records():
    units = [json.loads(line) for line in UNITS.read_text().splitlines() if line.strip()]
    return build_primary_records(units)


def _targets(records):
    choices = ("A", "B", "C", "D")
    answer = []
    for record in records:
        index = int(record["unit_id"].rsplit("-", 1)[-1])
        unit_position = [r["unit_id"] for r in records if r["record_id"].endswith("transfer-blinded")].index(record["unit_id"])
        choice = choices[unit_position % 4]
        answer.append({"record_id": record["record_id"], "expected_choice": choice})
    return answer


class Exp001TargetKeyTest(unittest.TestCase):
    def test_balanced_key_passes(self):
        records = _records()
        self.assertEqual(validate_sealed_target_key(records, _targets(records))["status"], "balanced")

    def test_position_collapse_rejects(self):
        records = _records()
        targets = _targets(records)
        targets[0]["expected_choice"] = "B"
        with self.assertRaises(Exp001TargetKeyError):
            validate_sealed_target_key(records, targets)


if __name__ == "__main__":
    unittest.main()
