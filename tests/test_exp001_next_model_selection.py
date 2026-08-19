import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from latent_triz.validator import validate as validate_minimal


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas/exp001-next-model-selection.schema.json"
INSTANCE_PATH = ROOT / "experiments/exp001-comparative-reference/next-model-selection.json"


class NextModelSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.instance = json.loads(INSTANCE_PATH.read_text(encoding="utf-8"))

    def test_frozen_selection_is_valid_under_both_validators(self):
        self.assertEqual(validate_minimal(self.instance, self.schema), [])
        self.assertEqual(list(Draft202012Validator(self.schema).iter_errors(self.instance)), [])
        self.assertEqual(
            {candidate["model_id"] for candidate in self.instance["candidates"]},
            {"EleutherAI/gpt-neo-125m", "Qwen/Qwen2.5-0.5B"},
        )
        self.assertFalse(self.instance["selection_observed_prior_result"])

    def test_exact_revisions_and_no_download_boundary(self):
        models = {candidate["model_id"]: candidate for candidate in self.instance["candidates"]}
        self.assertEqual(models["EleutherAI/gpt-neo-125m"]["revision"], "21def0189f5705e2521767faed922f1f15e7d7db")
        self.assertEqual(models["Qwen/Qwen2.5-0.5B"]["revision"], "060db6499f32faf8b98477b0a26969ef7d8b9987")
        self.assertTrue(all(candidate["acquisition_status"] == "not_acquired" for candidate in models.values()))
        self.assertTrue(all(candidate["compatibility_mapping"]["trust_remote_code"] is False for candidate in models.values()))

    def test_mutations_fail_closed(self):
        mutations = []
        observed = copy.deepcopy(self.instance)
        observed["selection_observed_prior_result"] = True
        mutations.append(observed)
        downloaded = copy.deepcopy(self.instance)
        downloaded["candidates"][0]["acquisition_status"] = "integrity_verified"
        mutations.append(downloaded)
        substituted = copy.deepcopy(self.instance)
        substituted["candidates"][0]["model_id"] = "apple/OpenELM-270M"
        mutations.append(substituted)
        for mutation in mutations:
            self.assertTrue(validate_minimal(mutation, self.schema))
            self.assertTrue(list(Draft202012Validator(self.schema).iter_errors(mutation)))


if __name__ == "__main__":
    unittest.main()
