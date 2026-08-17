import copy
import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "experiments/exp001-reference-integrated/fixtures/split-receipt.json"
PLAN = ROOT / "experiments/exp001-reference-integrated/fixtures/control-plan.json"


class Exp001R3SplitReceiptTest(unittest.TestCase):
    def setUp(self):
        self.receipt = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.plan = json.loads(PLAN.read_text(encoding="utf-8"))
        schema = json.loads((ROOT / "schemas/exp001-r3-split-receipt.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self.validator = Draft202012Validator(schema)

    def test_receipt_binds_all_controls_and_forbids_pooling(self):
        self.assertEqual([], list(self.validator.iter_errors(self.receipt)))
        expected = {p["pair_id"]: p for p in self.plan["pairs"]}
        actual = {b["pair_id"]: b for b in self.receipt["bindings"]}
        self.assertEqual(set(expected), set(actual))
        self.assertEqual(len(actual), 10)
        for pair_id, planned in expected.items():
            bound = actual[pair_id]
            for field in ("task_family", "control_kind", "source_family", "problem_family", "domain_holdout", "source_holdout", "family_holdout", "target_locator"):
                self.assertEqual(planned[field], bound[field], field)
            self.assertEqual(["TRIZ-blinded-transfer", "source-exposed-competence"], bound["strata"])
            self.assertTrue(bound["pooling_prohibited"])
        digest = hashlib.sha256(PLAN.read_bytes()).hexdigest()
        self.assertEqual(digest, self.receipt["control_plan_sha256"])

    def test_duplicate_pair_is_rejected(self):
        bad = copy.deepcopy(self.receipt)
        bad["bindings"][1]["pair_id"] = bad["bindings"][0]["pair_id"]
        ids = [b["pair_id"] for b in bad["bindings"]]
        self.assertNotEqual(len(ids), len(set(ids)))

    def test_missing_control_is_rejected(self):
        bad = copy.deepcopy(self.receipt)
        bad["bindings"].pop()
        self.assertTrue(list(self.validator.iter_errors(bad)))

    def test_target_content_field_is_rejected(self):
        bad = copy.deepcopy(self.receipt)
        bad["bindings"][0]["target_value"] = "option-a"
        self.assertTrue(list(self.validator.iter_errors(bad)))


if __name__ == "__main__":
    unittest.main()
