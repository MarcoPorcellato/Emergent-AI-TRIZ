import unittest

from latent_triz.exp002_transfer_corpus import (
    Exp002TransferCorpusError,
    summarize_transfer_fixture,
    validate_transfer_fixture,
)


def _fixture(domain_count=8):
    records = []
    for domain_index in range(domain_count):
        domain = f"domain-{domain_index:02d}"
        for family_index in range(2):
            family = f"family-{domain_index:02d}-{family_index:02d}"
            for replicate in range(2):
                records.append(
                    {
                        "case_id": f"exp002c-{domain_index:02d}-{family_index:02d}-{replicate:02d}",
                        "domain": domain,
                        "family_id": family,
                        "replicate_id": f"r{replicate}",
                        "split": ("sealed_novel" if domain_index == 1 else ("held_out_domain" if domain_index else "validation")),
                        "problem": f"A device in {domain} has tradeoff family {family} replicate {replicate} under load.",
                        "candidate_descriptions": [
                            f"Candidate {option} changes one observable property in {domain} for {family} replicate {replicate}."
                            for option in "ABCD"
                        ],
                        "option_order": [0, 1, 2, 3],
                        "source_exposure": "blinded_primary",
                        "author_id": f"author-{domain_index % 3}",
                        "generator_intent_locator": f"sealed://exp002c/intent/{domain_index:02d}/{family_index:02d}/{replicate:02d}",
                        "expert_label_locator": f"sealed://exp002c/expert/{domain_index:02d}/{family_index:02d}/{replicate:02d}",
                        "source_proximity_status": "pass",
                    }
                )
    return records


class Exp002TransferCorpusTests(unittest.TestCase):
    def test_accepts_complete_target_free_fixture(self):
        summary = validate_transfer_fixture(_fixture(), status="frozen")
        self.assertEqual(summary["domain_count"], 8)
        self.assertEqual(summary["family_count"], 16)
        self.assertEqual(summary["record_count"], 32)
        self.assertTrue(summary["primary_is_label_free"])

    def test_rejects_triz_cue_in_blinded_primary(self):
        records = _fixture()
        records[0]["problem"] = "Use TRIZ to resolve this engineering tradeoff."
        with self.assertRaises(Exp002TransferCorpusError):
            validate_transfer_fixture(records, status="frozen")

    def test_rejects_reused_exp001_identity(self):
        records = _fixture()
        records[0]["case_id"] = "exp001-reused-case"
        with self.assertRaises(Exp002TransferCorpusError):
            validate_transfer_fixture(records, status="frozen")

    def test_requires_separate_expert_and_generator_locators(self):
        records = _fixture()
        records[0]["expert_label_locator"] = records[0]["generator_intent_locator"]
        with self.assertRaises(Exp002TransferCorpusError):
            validate_transfer_fixture(records, status="frozen")

    def test_design_status_can_remain_incomplete_without_model_access(self):
        summary = validate_transfer_fixture(_fixture(domain_count=2), status="design")
        self.assertEqual(summary["domain_count"], 2)
        self.assertFalse(summary["freeze_ready"])

    def test_summary_rejects_answer_or_target_fields(self):
        records = _fixture()
        records[0]["expected_answer"] = "A"
        with self.assertRaises(Exp002TransferCorpusError):
            summarize_transfer_fixture(records)


if __name__ == "__main__":
    unittest.main()
