from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.validator import validate


class A0R2FeasibilitySchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (ROOT / "schemas/a0r2-feasibility-contract.schema.json").read_text(encoding="utf-8")
        )
        cls.contract = json.loads(
            (ROOT / "experiments/a0r2-independent-model/feasibility-contract.json").read_text(encoding="utf-8")
        )

    def test_tracked_contract_is_valid(self) -> None:
        self.assertEqual([], validate(self.contract, self.schema))

    def test_generation_cannot_be_enabled(self) -> None:
        mutated = deepcopy(self.contract)
        mutated["runtime"]["generation"] = True
        self.assertTrue(validate(mutated, self.schema))

    def test_primary_mapping_cannot_drift(self) -> None:
        mutated = deepcopy(self.contract)
        mutated["compatibility"]["primary_hidden_states_tuple_index"] = 6
        self.assertTrue(validate(mutated, self.schema))

    def test_sealed_execution_cannot_be_removed_from_boundary(self) -> None:
        mutated = deepcopy(self.contract)
        mutated["authorization"]["not_authorized"].remove("sealed_r2_execution")
        self.assertTrue(validate(mutated, self.schema))


if __name__ == "__main__":
    unittest.main()
