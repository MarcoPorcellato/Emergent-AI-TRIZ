"""Fail-closed structural checks for the no-model EXP-001 R3 records."""
import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).parents[1]


def validator(name):
    schema = json.loads((ROOT / "schemas" / name).read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


class Exp001R3SchemasTest(unittest.TestCase):
    def test_item_valid_and_blinded_cannot_expose_source(self):
        record = {
            "item_id": "exp001-r3-principle-a1", "stratum": "TRIZ-blinded-transfer",
            "task_family": "principle", "problem_family": "thermal", "domain": "fluid",
            "source_ids": ["triz-ref-inventive-principles-2023"],
            "locator": {"source_id": "triz-ref-inventive-principles-2023", "kind": "page", "value": "p.7"},
            "derivation": {"method": "independent_paraphrase", "independent_author": "fixture-author-1", "verbatim_copy": False, "source_wording_used": False},
            "rights": {"status": "independently_authored", "redistribution_allowed": False, "locator_only": True},
            "lexical_audit": {"source_lexemes_present": False, "score": 0.0, "method": "token audit", "reviewed": True},
            "proximity_audit": {"source_lexemes_present": False, "canonical_example_proximity": False, "score": 0.0, "method": "nearest-neighbour audit", "reviewed": True},
            "split": {"source_family": "principles", "problem_family": "thermal", "held_out_domain": True, "pooling_prohibited": True},
            "prompt": "A bounded problem statement with no reference terms.", "expected_response_mode": "principle_choice",
        }
        v = validator("exp001-r3-item.schema.json")
        self.assertFalse(list(v.iter_errors(record)))
        bad = copy.deepcopy(record); bad["lexical_audit"]["source_lexemes_present"] = True
        self.assertTrue(list(v.iter_errors(bad)))

    def test_matrix_requires_double_check_and_direction(self):
        digest = "a" * 64
        record = {"cell_id": "matrix2003-cell-a1", "source_id": "triz-ref-matrix-2003", "locator": {"page": 1, "table": "48 by 48 contradiction matrix"}, "direction": "improving_row_worsening_column", "improving_parameter": 1, "worsening_parameter": 2, "recommended_principles": [15, 19], "transcription_receipts": [{"check_id": "visual-a", "method": "independent_visual_transcription", "source_sha256": "65fc567d9d76b95d462fa0e89bddac8d0db481780691d90ec11a06c9e75b32c8", "page": 1, "normalized_cell_sha256": digest}, {"check_id": "visual-b", "method": "independent_visual_transcription", "source_sha256": "65fc567d9d76b95d462fa0e89bddac8d0db481780691d90ec11a06c9e75b32c8", "page": 1, "normalized_cell_sha256": digest}], "inference_prohibited": True, "rights": {"status": "public_reference_external", "locator_only": True}}
        v = validator("exp001-r3-matrix-cell.schema.json")
        self.assertFalse(list(v.iter_errors(record)))
        bad = copy.deepcopy(record); bad["transcription_receipts"] = bad["transcription_receipts"][:1]
        self.assertTrue(list(v.iter_errors(bad)))

    def test_tool_edge_uncertain_is_not_selectable(self):
        record = {"edge_id": "panitz-edge-a1", "source_id": "triz-ref-tools-overview-panitz", "from_tool": "contradiction", "to_tool": "principles", "edge_status": "uncertain", "locator": "map panel 1", "rights": {"status": "user_attributed_unverified", "locator_only": True}, "selection_allowed": False, "abstention_allowed": True}
        v = validator("exp001-r3-tool-edge.schema.json")
        self.assertFalse(list(v.iter_errors(record)))
        bad = copy.deepcopy(record); bad["selection_allowed"] = True
        self.assertTrue(list(v.iter_errors(bad)))

    def test_exposure_requires_paired_blinded_item_and_no_verbatim_text(self):
        record = {"exposure_context_id": "exp001-exposure-a1", "item_id": "exp001-r3-principle-a1", "mode": "source_exposed", "source_id": "triz-ref-inventive-principles-2023", "locator": "p.7", "context": "An independently authored bounded reference context.", "verbatim_copy": False, "canonical_example_included": False, "rights": {"status": "public_reference_external", "redistribution_allowed": False, "locator_only": True}, "bounded": True, "blinded_counterpart_id": "exp001-r3-principle-a1-blinded"}
        v = validator("exp001-r3-source-exposure.schema.json")
        self.assertFalse(list(v.iter_errors(record)))
        bad = copy.deepcopy(record); bad["verbatim_copy"] = True
        self.assertTrue(list(v.iter_errors(bad)))


if __name__ == "__main__":
    unittest.main()
