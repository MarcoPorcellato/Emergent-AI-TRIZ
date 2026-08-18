import math
import unittest
from collections.abc import Mapping

from latent_triz.exp001_r3_response_adapter import (
    R3ResponseAdapterError,
    score_teacher_forced_choice,
    validate_tokenizer_batch,
)


class FakeBatch(Mapping):
    def __init__(self, values):
        self._values = values

    def __getitem__(self, key):
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


class R3ResponseAdapterTests(unittest.TestCase):
    def test_accepts_mapping_like_tokenizer_batch(self):
        result = validate_tokenizer_batch(
            FakeBatch({"input_ids": [[1, 2, 3]], "attention_mask": [[1, 1, 1]]}),
            vocab_size=5,
        )
        self.assertEqual(result, {"input_ids": [1, 2, 3], "attention_mask": [1, 1, 1]})

    def test_scores_finite_multitoken_choice(self):
        logits = [[[0.0, 1.0, 2.0, 0.0], [2.0, 0.0, 1.0, 0.0]]]
        score = score_teacher_forced_choice(logits, [2, 0], vocab_size=4)
        expected = sum(
            value - math.log(sum(math.exp(item) for item in row))
            for row, value in zip(logits[0], [2.0, 2.0])
        ) / 2
        self.assertAlmostEqual(score, expected)

    def test_rejects_malformed_batch_and_shape(self):
        with self.assertRaises(R3ResponseAdapterError):
            validate_tokenizer_batch({"input_ids": [[1, 2]], "attention_mask": [[1]]})
        with self.assertRaises(R3ResponseAdapterError):
            validate_tokenizer_batch({"input_ids": [[1], [2]], "attention_mask": [[1], [1]]})
        with self.assertRaises(R3ResponseAdapterError):
            score_teacher_forced_choice([[1.0, 2.0]], [0])

    def test_rejects_nonfinite_logits_and_invalid_choice(self):
        with self.assertRaises(R3ResponseAdapterError):
            score_teacher_forced_choice([[[0.0, float("nan")]]], [0])
        with self.assertRaises(R3ResponseAdapterError):
            score_teacher_forced_choice([[[0.0, 1.0]]], [3])


if __name__ == "__main__":
    unittest.main()
