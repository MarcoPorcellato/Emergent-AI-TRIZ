import unittest

from latent_triz.exp002_knowledge import Exp002KnowledgeError, evaluate_direct_questions, source_familiarity_contrast


class Exp002KnowledgeTests(unittest.TestCase):
    def test_self_report_is_excluded_and_metrics_are_module_specific(self):
        outcomes = [
            {"question_id": "q1", "module": "principle_recognition", "prediction": "Segmentation", "abstained": False, "scientific_role": "knowledge_endpoint"},
            {"question_id": "q2", "module": "self_report_metadata", "prediction": "yes", "abstained": False, "scientific_role": "familiarity_diagnostic"},
            {"question_id": "q3", "module": "false_concept_canary", "prediction": "unsupported", "abstained": True, "scientific_role": "calibration_control"},
        ]
        result = evaluate_direct_questions(outcomes, {"q1": "Segmentation", "q2": "yes", "q3": "unsupported"})
        self.assertEqual(result["modules"]["self_report_metadata"]["scored_count"], 0)
        self.assertEqual(result["modules"]["principle_recognition"]["accuracy"], 1.0)
        self.assertTrue(result["self_report_is_non_evidential"])

    def test_source_contrast_requires_paired_conditions(self):
        result = source_familiarity_contrast({"canonical_short_phrase": [3, 4], "independent_paraphrase": [2, 3], "matched_non_triz_lexical_control": [1, 2], "nonce_relation_edit": [0, 1]})
        self.assertEqual(result["canonical_minus_paraphrase"], 1.0)
        with self.assertRaises(Exp002KnowledgeError):
            source_familiarity_contrast({"canonical_short_phrase": [1], "independent_paraphrase": [1], "matched_non_triz_lexical_control": [1]})

    def test_unsupported_answer_key_is_counted_only_for_matching_claim(self):
        outcomes = [
            {"question_id": "q1", "module": "false_concept_canary", "prediction": "unsupported", "abstained": False, "scientific_role": "calibration_control"},
            {"question_id": "q2", "module": "false_concept_canary", "prediction": "supported", "abstained": False, "scientific_role": "calibration_control"},
        ]
        result = evaluate_direct_questions(
            outcomes,
            {"q1": {"answer": "unsupported", "unsupported": True}, "q2": {"answer": "unsupported", "unsupported": True}},
        )
        self.assertEqual(result["modules"]["false_concept_canary"]["unsupported_claim_count"], 1)


if __name__ == "__main__":
    unittest.main()
