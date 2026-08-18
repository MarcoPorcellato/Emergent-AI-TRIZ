import json
import unittest
from pathlib import Path

from latent_triz.exp001_r3_primary_fixture import Exp001PrimaryFixtureError, build_primary_records


ROOT = Path(__file__).parents[1]
UNITS = ROOT / "experiments/exp001-reference-integrated/fixtures/primary-units.jsonl"


def _units():
    return [json.loads(line) for line in UNITS.read_text(encoding="utf-8").splitlines() if line.strip()]


class Exp001PrimaryFixtureTest(unittest.TestCase):
    def test_expands_to_separate_blinded_and_exposed_records(self):
        records = build_primary_records(_units())
        self.assertEqual(len(records), 72)
        self.assertEqual(sum(record["stratum"] == "TRIZ-blinded-transfer" for record in records), 48)
        self.assertEqual(sum(record["stratum"] == "source-exposed-competence" for record in records), 24)
        self.assertTrue(all(record["pooling_prohibited"] for record in records))
        self.assertTrue(all(record["response_locator"].startswith("sealed://") for record in records))

    def test_duplicate_transfer_control_is_rejected(self):
        units = _units()
        units[0]["lexical_control_prompt"] = units[0]["transfer_prompt"]
        with self.assertRaises(Exp001PrimaryFixtureError):
            build_primary_records(units)


if __name__ == "__main__":
    unittest.main()
