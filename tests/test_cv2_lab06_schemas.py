from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from latent_triz.validator import validate


class CV2Lab06SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]

    def _load(self, path: str) -> dict:
        return json.loads((self.root / path).read_text())

    def test_no_model_protocols_validate(self) -> None:
        cv2 = self._load("experiments/cv2-negative-controls/protocol.json")
        cv2_schema = self._load("schemas/cv2-negative-control.schema.json")
        lab06 = self._load("experiments/lab06-causal-intervention/dossier.json")
        lab06_schema = self._load("schemas/lab06-dossier.schema.json")
        self.assertEqual(validate(cv2, cv2_schema), [])
        self.assertEqual(validate(lab06, lab06_schema), [])
        self.assertFalse(cv2["publication_boundary"]["model_output_accessed"])
        self.assertFalse(lab06["approval_boundary"]["run_authorized"])

    def test_cv2_rejects_missing_control_family(self) -> None:
        cv2 = self._load("experiments/cv2-negative-controls/protocol.json")
        schema = self._load("schemas/cv2-negative-control.schema.json")
        cv2["control_families"] = cv2["control_families"][:-1]
        issues = validate(cv2, schema)
        self.assertTrue(any(issue.path.endswith("control_families") for issue in issues))

    def test_lab06_rejects_premature_authorization(self) -> None:
        dossier = self._load("experiments/lab06-causal-intervention/dossier.json")
        schema = self._load("schemas/lab06-dossier.schema.json")
        dossier["approval_boundary"]["run_authorized"] = True
        issues = validate(dossier, schema)
        self.assertTrue(any(issue.path.endswith("run_authorized") for issue in issues))


if __name__ == "__main__":
    unittest.main()
