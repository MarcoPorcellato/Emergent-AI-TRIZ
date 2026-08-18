import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
PATH = ROOT / "experiments/exp001-reference-integrated/fixtures/primary-units.jsonl"
DOMAINS = {"agriculture", "medical", "manufacturing", "logistics", "software", "energy"}
FORBIDDEN_BLINDED = re.compile(r"\b(?:triz|inventive|principle|matrix|source)\b", re.I)
FORBIDDEN_KEYS = {"correct_option", "answer", "label", "target", "score", "scoring", "expected"}
REQUIRED_KEYS = {
    "unit_id", "domain", "problem_family", "replicate", "transfer_prompt",
    "transfer_options", "lexical_control_prompt", "lexical_control_options",
    "exposed_context", "source_id",
}
LEXICAL_TASK_MARKERS = re.compile(
    r"\b(?:lists?|sequence|report|record|records|log|order|ordered|first|second|third|"
    r"last|follows|between|front|how many|smallest|greatest|heaviest|lowest|highest|earlier)\b", re.I
)
LEXICAL_LOOKUP_MARKERS = re.compile(
    r"\b(?:lists?|sequence|report|record|records|log|order|ordered|first|second|third|"
    r"last|follows|between|front|how many|smallest|greatest|heaviest|lowest|highest|earlier)\b", re.I
)


class Exp001R3PrimaryUnitsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = [json.loads(line) for line in PATH.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_exact_inventory_and_domain_replicates(self):
        self.assertEqual(len(self.records), 24)
        self.assertEqual({r["domain"] for r in self.records}, DOMAINS)
        for domain in DOMAINS:
            rows = [r for r in self.records if r["domain"] == domain]
            self.assertEqual(len(rows), 4)
            self.assertEqual(sorted(r["replicate"] for r in rows), [1, 1, 2, 2])
            self.assertEqual(len({r["problem_family"] for r in rows}), 2)

    def test_public_shape_and_option_ids(self):
        for record in self.records:
            self.assertEqual(set(record), REQUIRED_KEYS)
            self.assertIsInstance(record["replicate"], int)
            self.assertIn(record["replicate"], (1, 2))
            self.assertEqual(record["source_id"], "triz-ref-inventive-principles-2023")
            for key in ("transfer_options", "lexical_control_options"):
                self.assertEqual(len(record[key]), 4)
                self.assertEqual([o["id"] for o in record[key]], ["A", "B", "C", "D"])
                self.assertTrue(all(set(o) == {"id", "description"} and o["description"].strip() for o in record[key]))

    def test_blinded_text_is_source_and_target_free(self):
        for record in self.records:
            blinded = " ".join([record["transfer_prompt"], record["lexical_control_prompt"]] + [o["description"] for o in record["transfer_options"]])
            self.assertIsNone(FORBIDDEN_BLINDED.search(blinded), record["unit_id"])
            self.assertEqual(set(record).intersection(FORBIDDEN_KEYS), set())
            self.assertNotIn("target", json.dumps(record, ensure_ascii=False).lower())

    def test_transfer_and_lexical_controls_are_distinct(self):
        self.assertEqual(
            len({r["transfer_prompt"] for r in self.records}), len(self.records)
        )
        self.assertEqual(
            len({r["lexical_control_prompt"] for r in self.records}), len(self.records)
        )
        for record in self.records:
            self.assertNotEqual(record["transfer_prompt"], record["lexical_control_prompt"])
            self.assertNotEqual(record["transfer_options"], record["lexical_control_options"])
            self.assertNotRegex(record["lexical_control_prompt"], LEXICAL_LOOKUP_MARKERS)
            self.assertNotEqual(
                {o["description"] for o in record["transfer_options"]},
                {o["description"] for o in record["lexical_control_options"]},
            )

    def test_fixture_retains_no_target_fields(self):
        # Position balance is verified only after the sealed key exists.  The
        # public fixture must remain target-free and therefore cannot encode
        # the intended response or its position.
        for record in self.records:
            self.assertEqual(set(record).intersection(FORBIDDEN_KEYS), set())
            self.assertNotIn("target", json.dumps(record, ensure_ascii=False).lower())

    def test_lexical_options_have_comparable_surface_length(self):
        for record in self.records:
            lengths = [len(option["description"].split()) for option in record["lexical_control_options"]]
            self.assertLessEqual(max(lengths) - min(lengths), 2, record["unit_id"])
        for domain in DOMAINS:
            families = {r["problem_family"] for r in self.records if r["domain"] == domain}
            for family in families:
                rows = [r for r in self.records if r["domain"] == domain and r["problem_family"] == family]
                self.assertEqual({r["replicate"] for r in rows}, {1, 2})
                self.assertEqual(len({r["transfer_prompt"] for r in rows}), 2)
                self.assertEqual(len({r["lexical_control_prompt"] for r in rows}), 2)

    def test_exposed_context_is_bounded_and_distinct(self):
        for record in self.records:
            self.assertTrue(record["exposed_context"].strip())
            self.assertNotEqual(record["exposed_context"], record["transfer_prompt"])
            self.assertNotIn("\n", record["exposed_context"])


if __name__ == "__main__":
    unittest.main()
