import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from latent_triz.validator import validate as validate_minimal


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas/exp001-additional-model-selection.schema.json"
INSTANCE_PATH = ROOT / "experiments/exp001-comparative-reference/additional-model-selection.json"


class AdditionalModelSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.instance = json.loads(INSTANCE_PATH.read_text(encoding="utf-8"))

    def test_frozen_selection_is_valid_under_both_validators(self):
        self.assertEqual(validate_minimal(self.instance, self.schema), [])
        self.assertEqual(list(Draft202012Validator(self.schema).iter_errors(self.instance)), [])
        self.assertEqual(len(self.instance["candidates"]), 2)
        self.assertFalse(self.instance["selection_observed_prior_result"])

    def test_model_ids_and_revisions_are_exact(self):
        models = {candidate["model_id"]: candidate for candidate in self.instance["candidates"]}
        self.assertEqual(models["openai-community/gpt2"]["revision"], "607a30d783dfa663caf39e06633721c8d4cfcd7e")
        self.assertEqual(models["HuggingFaceTB/SmolLM2-135M"]["revision"], "93efa2f097d58c2a74874c7e644dbc9b0cee75a2")
        self.assertTrue(all(candidate["acquisition_status"] == "not_acquired" for candidate in models.values()))

    def test_mutations_fail_closed(self):
        mutations = []
        extra = copy.deepcopy(self.instance)
        extra["candidates"].append(copy.deepcopy(extra["candidates"][0]))
        mutations.append(extra)
        observed = copy.deepcopy(self.instance)
        observed["selection_observed_prior_result"] = True
        mutations.append(observed)
        downloaded = copy.deepcopy(self.instance)
        downloaded["candidates"][0]["acquisition_status"] = "integrity_verified"
        mutations.append(downloaded)
        for mutation in mutations:
            self.assertTrue(validate_minimal(mutation, self.schema))
            self.assertTrue(list(Draft202012Validator(self.schema).iter_errors(mutation)))


if __name__ == "__main__":
    unittest.main()
