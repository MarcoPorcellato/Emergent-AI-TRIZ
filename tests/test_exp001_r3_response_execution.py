import math
import unittest

from latent_triz.exp001_r3_response_execution import (
    R3ResponseExecutionError,
    execute_public_responses,
)


def _records():
    return [
        {
            "record_id": f"r-{index:02d}",
            "prompt": f"Choose the best response for case {index}.",
            "options": [
                {"id": "A", "description": "First neutral description."},
                {"id": "B", "description": "Second neutral description."},
                {"id": "C", "description": "Third neutral description."},
                {"id": "D", "description": "Fourth neutral description."},
            ],
        }
        for index in range(72)
    ]


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def score_prompt_choice(self, rendered_prompt, label):
        self.calls.append((rendered_prompt, label))
        return {"A": 0.1, "B": 0.2, "C": 0.3, "D": 0.4}[label]


class R3ResponseExecutionTests(unittest.TestCase):
    def test_scores_all_records_once_per_choice_without_generation(self):
        adapter = FakeAdapter()
        rows = execute_public_responses(_records(), adapter)
        self.assertEqual(len(rows), 72)
        self.assertEqual(len(adapter.calls), 288)
        self.assertEqual([label for _, label in adapter.calls[:4]], ["A", "B", "C", "D"])
        self.assertEqual(set(rows[0]), {"record_id", "scores", "prompt_sha256"})
        self.assertEqual(set(rows[0]["scores"]), {"A", "B", "C", "D"})
        self.assertNotIn("target", rows[0])
        self.assertIn("Answer with exactly one option label", adapter.calls[0][0])
        self.assertEqual(adapter.calls[0][0].count("A."), 1)

    def test_rejects_wrong_inventory_before_adapter_calls(self):
        adapter = FakeAdapter()
        with self.assertRaises(R3ResponseExecutionError):
            execute_public_responses(_records()[:-1], adapter)
        self.assertEqual(adapter.calls, [])

    def test_rejects_malformed_options_before_adapter_calls(self):
        records = _records()
        records[3]["options"] = records[3]["options"][:3]
        adapter = FakeAdapter()
        with self.assertRaises(R3ResponseExecutionError):
            execute_public_responses(records, adapter)
        self.assertEqual(adapter.calls, [])

    def test_nan_score_is_fail_closed(self):
        class NaNAdapter(FakeAdapter):
            def score_prompt_choice(self, rendered_prompt, label):
                super().score_prompt_choice(rendered_prompt, label)
                return math.nan

        adapter = NaNAdapter()
        with self.assertRaises(R3ResponseExecutionError):
            execute_public_responses(_records(), adapter)

    def test_adapter_error_is_fail_closed(self):
        class ErrorAdapter(FakeAdapter):
            def score_prompt_choice(self, rendered_prompt, label):
                raise RuntimeError("generation is unavailable")

        with self.assertRaises(R3ResponseExecutionError):
            execute_public_responses(_records(), ErrorAdapter())


if __name__ == "__main__":
    unittest.main()
