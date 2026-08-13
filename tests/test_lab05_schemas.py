from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from latent_triz.validator import validate


class Lab05SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.config_schema = json.loads((self.root / "schemas/lab05-config.schema.json").read_text())
        self.result_schema = json.loads((self.root / "schemas/lab05-result.schema.json").read_text())

    def test_tracked_config_and_result_validate(self) -> None:
        config = json.loads((self.root / "experiments/lab05-candidate-directions/config.json").read_text())
        result = json.loads((self.root / "results/lab05/candidate-directions/summary.json").read_text())
        self.assertEqual(validate(config, self.config_schema), [])
        self.assertEqual(validate(result, self.result_schema), [])
        self.assertEqual(config["claim_ids"], [])
        self.assertFalse(result["publication_boundary"]["dense_vectors_published"])

    def test_contract_rejects_claims_and_dense_vector_publication(self) -> None:
        config = json.loads((self.root / "experiments/lab05-candidate-directions/config.json").read_text())
        config["claim_ids"] = ["CLM-999"]
        config["publication_boundary"]["dense_vectors_published"] = True
        issues = validate(config, self.config_schema)
        self.assertTrue(any(issue.path.endswith("claim_ids") for issue in issues))
        self.assertTrue(any(issue.path.endswith("dense_vectors_published") for issue in issues))


if __name__ == "__main__":
    unittest.main()
