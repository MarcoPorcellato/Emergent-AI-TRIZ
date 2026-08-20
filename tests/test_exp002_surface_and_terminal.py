import unittest

from latent_triz.exp002_surface import (
    CONDITIONS,
    Exp002SurfaceError,
    LABELS,
    adjust_label_prior,
    all_label_permutations,
    cyclic_permutations,
    remap_scores,
    score_candidate_descriptions,
    build_surface_schedule,
    classify_measurement_surface,
    evaluate_surface_conditions,
    summarize_surface,
)
from latent_triz.exp002_terminal import build_terminal_result, validate_terminal_result


class Exp002SurfaceTests(unittest.TestCase):
    def test_permutation_inventory_and_bijection(self):
        self.assertEqual(len(cyclic_permutations()), 4)
        self.assertEqual(len(all_label_permutations()), 24)
        for mapping in all_label_permutations():
            self.assertEqual(set(mapping), set(LABELS))
            self.assertEqual(set(mapping.values()), set(LABELS))

    def test_remap_and_prior_adjustment(self):
        scores = {"A": 1, "B": 2, "C": 3, "D": 4}
        mapping = {"A": "B", "B": "C", "C": "D", "D": "A"}
        self.assertEqual(remap_scores(scores, mapping), {"A": 4.0, "B": 1.0, "C": 2.0, "D": 3.0})
        self.assertEqual(adjust_label_prior(scores, {label: 1 for label in LABELS}), {label: float(scores[label] - 1) for label in LABELS})

    def test_surface_summary_and_candidate_scorer(self):
        rows = [{"condition": "original_abcd", "scores": {"A": 2, "B": 1, "C": 0, "D": -1}}, {"condition": "original_abcd", "scores": {"A": 0, "B": 3, "C": 2, "D": 1}}]
        summary = summarize_surface(rows)
        self.assertEqual(summary["top_label_counts"], {"A": 1, "B": 1, "C": 0, "D": 0})
        self.assertEqual(score_candidate_descriptions(lambda text: len(text), ("alpha", "beta")), (5.0, 4.0))
        with self.assertRaises(Exp002SurfaceError):
            score_candidate_descriptions(lambda _: float("nan"), ("alpha",))

    def test_surface_schedule_is_balanced_and_deterministic(self):
        schedule = build_surface_schedule(["r1"])
        self.assertEqual(len(schedule), 1 + 4 + 24 + 1 + 1 + 1 + 1)
        self.assertEqual(schedule[0]["condition"], "original_abcd")
        self.assertEqual({row["condition"] for row in schedule}, set(CONDITIONS))
        self.assertEqual(len({tuple(row["mapping"].items()) for row in schedule if row["condition"] == "all_24_label_permutations"}), 24)

    def test_measurement_surface_classifier_requires_label_free_agreement(self):
        robust = classify_measurement_surface({"balanced_complete": True, "all_permutations_complete": True, "label_free_agreement": True, "semantic_invariance": True})
        self.assertEqual(robust["status"], "measurement_robust")
        artifact = classify_measurement_surface({"balanced_complete": True, "all_permutations_complete": True, "label_free_agreement": False, "semantic_invariance": False})
        self.assertEqual(artifact["status"], "measurement_artifact_supported")
        with self.assertRaises(Exp002SurfaceError):
            classify_measurement_surface({"balanced_complete": True})

    def test_surface_condition_evaluator_is_target_free_and_detects_artifact(self):
        rows = []
        rows.append({"record_id": "r1", "condition": "original_abcd", "semantic_choice": "0"})
        rows.extend({"record_id": "r1", "condition": "balanced_cyclic_label_permutations", "semantic_choice": "0"} for _ in range(4))
        rows.extend({"record_id": "r1", "condition": "all_24_label_permutations", "semantic_choice": "0"} for _ in range(24))
        rows.append({"record_id": "r1", "condition": "label_free_candidate_description_scoring", "semantic_choice": "0"})
        result = evaluate_surface_conditions(rows)
        self.assertEqual(result["observation"]["status"], "measurement_robust")
        rows[-1]["semantic_choice"] = "1"
        result = evaluate_surface_conditions(rows)
        self.assertEqual(result["observation"]["status"], "measurement_artifact_supported")


class Exp002TerminalTests(unittest.TestCase):
    def test_all_terminal_states_are_claim_free(self):
        for status in ("positive", "null", "failed", "non_interpretable", "incompatible"):
            result = build_terminal_result(study_id="EXP-002A", model_id="Qwen/Qwen3-0.6B-Base", status=status)
            validate_terminal_result(result)

    def test_inconsistent_target_read_is_rejected(self):
        result = build_terminal_result(study_id="EXP-002A", model_id="Qwen/Qwen3-0.6B-Base", status="failed")
        result["access"]["target_reads"] = 1
        with self.assertRaises(ValueError):
            validate_terminal_result(result)


if __name__ == "__main__":
    unittest.main()
