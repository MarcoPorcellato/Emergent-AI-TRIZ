import unittest

from latent_triz.exp002_source_familiarity import Exp002SourceFamiliarityError, validate_source_familiarity_fixture


def _records():
    conditions = (
        "canonical_short_phrase", "independent_paraphrase", "matched_non_triz_lexical_control",
        "nonce_relation_edit", "source_attribution_with_unknown",
    )
    return [
        {
            "case_id": f"exp002b-source-case-{index}",
            "pair_id": "exp002b-pair-001",
            "condition": condition,
            "prompt_locator": f"public://exp002b/source-familiarity/case-{index}.txt",
            "prompt_sha256": "a" * 64,
            "source_id": "non-triz-design-reference" if condition == "matched_non_triz_lexical_control" else "triz-ref-inventive-principles-2023",
            "exposure_mode": "citation_only",
        }
        for index, condition in enumerate(conditions)
    ]


class Exp002SourceFamiliarityTests(unittest.TestCase):
    def test_empty_design_fixture_is_safe_and_frozen_fixture_is_not(self):
        result = validate_source_familiarity_fixture([], status="design")
        self.assertTrue(result["locator_only"])
        with self.assertRaises(Exp002SourceFamiliarityError):
            validate_source_familiarity_fixture([], status="frozen")

    def test_paired_locator_only_fixture_passes(self):
        result = validate_source_familiarity_fixture(_records(), status="frozen")
        self.assertEqual(result["pair_count"], 1)
        self.assertEqual(result["record_count"], 5)
        self.assertFalse(result["model_access"])

    def test_leaked_source_or_incomplete_pair_fails_closed(self):
        records = _records()
        records[0]["source_excerpt"] = "forbidden"
        with self.assertRaises(Exp002SourceFamiliarityError):
            validate_source_familiarity_fixture(records)
        records = _records()[:-1]
        with self.assertRaises(Exp002SourceFamiliarityError):
            validate_source_familiarity_fixture(records)


if __name__ == "__main__":
    unittest.main()
