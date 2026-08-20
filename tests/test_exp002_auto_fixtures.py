import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from latent_triz.exp002_auto_fixtures import (
    Exp002AutoFixtureError,
    build_combined_key,
    build_factual_records,
    build_formulation_records,
    build_procedural_records,
    validate_public_records,
)


ROOT = Path(__file__).resolve().parents[1]


def _jsonl(path):
    return [json.loads(line) for line in (ROOT / path).read_text(encoding="utf-8").splitlines() if line]


class Exp002AutoFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.principles = _jsonl("data/triz-reference/principles.jsonl")
        cls.matrix_cells = _jsonl("experiments/exp001-reference-integrated/fixtures/matrix-cells.jsonl")
        cls.tool_edges = _jsonl("experiments/exp001-reference-integrated/fixtures/tool-edges.jsonl")

    def test_factual_inventory_has_frozen_178_record_family_split_without_key_leakage(self):
        records, key = build_factual_records(self.principles, self.matrix_cells, self.tool_edges)
        self.assertEqual(len(records), 178)
        self.assertEqual(len(key), 178)
        counts = {}
        for record in records:
            counts[record["family"]] = counts.get(record["family"], 0) + 1
            self.assertNotIn("expected_candidate_index", record)
            self.assertNotIn("target", record)
        self.assertEqual(counts, {
            "principle_number_to_name": 40,
            "principle_name_to_operator": 40,
            "real_vs_invented": 40,
            "insufficient_information": 40,
            "canary": 8,
            "matrix_direction": 6,
            "tool_relationship": 4,
        })
        validate_public_records(records, expected_count=178)

    def test_formulation_inventory_has_four_conditions_for_every_principle(self):
        records = build_formulation_records(self.principles)
        self.assertEqual(len(records), 160)
        self.assertEqual({record["condition"] for record in records}, {
            "canonical_short_field", "structured_paraphrase", "matched_non_triz_control", "nonce_edit_control",
        })
        validate_public_records(records, expected_count=160)

    def test_continuation_contrast_rejects_candidate_score_fields(self):
        records = build_formulation_records(self.principles)
        records[0]["candidate_descriptions"] = ["a", "b", "c", "d"]
        with self.assertRaises(Exp002AutoFixtureError):
            validate_public_records(records, expected_count=160)

    def test_procedural_inventory_has_eight_domains_without_triz_surface_cues(self):
        records, key = build_procedural_records()
        self.assertEqual(len(records), 48)
        self.assertEqual(len(key), 48)
        domains = {record["domain"] for record in records}
        self.assertEqual(domains, {
            "agriculture", "energy", "logistics", "manufacturing", "medical", "software", "construction", "public_services",
        })
        for record in records:
            self.assertNotRegex(record["prompt"].lower(), r"triz|principle\\s*\\d|screwdriver|pencil|socks|spork")
            self.assertNotIn("expected_candidate_index", record)
        validate_public_records(records, expected_count=48)

    def test_combined_key_cannot_be_created_from_public_records_without_private_indices(self):
        factual, factual_key = build_factual_records(self.principles, self.matrix_cells, self.tool_edges)
        procedural, procedural_key = build_procedural_records()
        combined = build_combined_key(factual, factual_key, procedural, procedural_key)
        self.assertEqual(combined["record_count"], 226)
        self.assertEqual(combined["sealed_target_accessed"], False)
        with self.assertRaises(Exp002AutoFixtureError):
            build_combined_key(factual, factual, procedural, procedural_key)

    def test_fixture_builder_cli_writes_only_public_records_and_an_unmaterialized_key_template(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            completed = subprocess.run(
                ["python3", "scripts/exp002_auto_build_fixtures.py", "--output-dir", str(output)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(len((output / "factual-public.jsonl").read_text(encoding="utf-8").splitlines()), 178)
            self.assertEqual(len((output / "formulation-public.jsonl").read_text(encoding="utf-8").splitlines()), 160)
            self.assertEqual(len((output / "procedural-public.jsonl").read_text(encoding="utf-8").splitlines()), 48)
            key_template = json.loads((output / "combined-target-key-template.json").read_text(encoding="utf-8"))
            self.assertEqual(key_template["status"], "not_ready")
            self.assertEqual(key_template["records"], [])


if __name__ == "__main__":
    unittest.main()
