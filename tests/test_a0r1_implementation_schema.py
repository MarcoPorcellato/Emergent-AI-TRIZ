from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.validator import validate


class A0R1ImplementationSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.schema = json.loads((self.root / "schemas/a0r1-implementation.schema.json").read_text(encoding="utf-8"))
        self.implementation = json.loads(
            (self.root / "experiments/a0r1-independent-proxy/implementation.json").read_text(encoding="utf-8")
        )

    def test_a0r1_implementation_schema_valid(self) -> None:
        issues = validate(self.implementation, self.schema)
        self.assertEqual([], issues)

    def test_a0r1_implementation_schema_rejects_mutations(self) -> None:
        mutation = copy.deepcopy(self.implementation)
        mutation["protocol"]["run_protocol_status"] = "unknown"
        issues = validate(mutation, self.schema)
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("protocol.run_protocol_status") for issue in issues))

        mutation = copy.deepcopy(self.implementation)
        mutation["model_output_accessed"] = True
        issues = validate(mutation, self.schema)
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("model_output_accessed") for issue in issues))

        mutation = copy.deepcopy(self.implementation)
        mutation["status"] = "positive"
        mutation["epistemic_boundary"] = copy.deepcopy(self.implementation["epistemic_boundary"])
        mutation["epistemic_boundary"]["evidence_eligible"] = True
        issues = validate(mutation, self.schema)
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("status") for issue in issues))
        self.assertTrue(any(issue.path.endswith("epistemic_boundary.evidence_eligible") for issue in issues))

    def test_a0r1_implementation_schema_rejects_unknown_properties(self) -> None:
        mutation = copy.deepcopy(self.implementation)
        mutation["forbidden_root_field"] = "nope"
        issues = validate(mutation, self.schema)
        self.assertTrue(issues)
        self.assertTrue(any("Additional property not allowed" in issue.message for issue in issues))


if __name__ == "__main__":
    unittest.main()
