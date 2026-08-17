"""Synthetic C2 shape-contract tests; no model or sealed artifact access."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0r2c2_adapter import (  # noqa: E402
    A0R2C2AdapterError,
    SmolLM2C2ShapeAdapter,
    normalize_hidden_state_rows,
)


class A0R2C2ShapeContractTests(unittest.TestCase):
    def test_rank_three_single_batch_normalizes_to_token_rows(self) -> None:
        value = [[[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]]
        self.assertEqual([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], normalize_hidden_state_rows(value, token_count=3, hidden_size=2))

    def test_rank_two_token_rows_remain_valid(self) -> None:
        value = [[1.0, 2.0], [3.0, 4.0]]
        self.assertEqual(value, normalize_hidden_state_rows(value, token_count=2, hidden_size=2))

    def test_batch_size_other_than_one_fails_closed(self) -> None:
        with self.assertRaisesRegex(A0R2C2AdapterError, "batch"):
            normalize_hidden_state_rows([[[1.0], [2.0]], [[3.0], [4.0]]], token_count=2, hidden_size=1)

    def test_token_dimension_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(A0R2C2AdapterError, "token"):
            normalize_hidden_state_rows([[[1.0], [2.0]]], token_count=3, hidden_size=1)

    def test_hidden_dimension_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(A0R2C2AdapterError, "hidden"):
            normalize_hidden_state_rows([[[1.0, 2.0]]], token_count=1, hidden_size=3)

    def test_nonfinite_scalar_fails_closed(self) -> None:
        with self.assertRaisesRegex(A0R2C2AdapterError, "non-finite"):
            normalize_hidden_state_rows([[[float("nan")]]], token_count=1, hidden_size=1)

    def test_malformed_list_depth_fails_closed(self) -> None:
        with self.assertRaises(A0R2C2AdapterError):
            normalize_hidden_state_rows([1.0, 2.0, 3.0], token_count=3, hidden_size=1)

    def test_adapter_replaces_only_singleton_batch_axis(self) -> None:
        payload = {
            "token_ids": [11, 12],
            "hidden_states": ([[[1.0] * 960, [2.0] * 960]],),
        }
        adapter = object.__new__(SmolLM2C2ShapeAdapter)
        with patch("latent_triz.a0r2c2_adapter.SmolLM2C1MappingAdapter.run_prompt", return_value=payload):
            result = adapter.run_prompt(prompt="synthetic")
        self.assertEqual(2, len(result["hidden_states"][0]))
        self.assertEqual(960, len(result["hidden_states"][0][0]))

    def test_adapter_normalizes_all_33_documented_llama_states(self) -> None:
        rank_three_state = [[[1.0] * 960, [2.0] * 960]]
        payload = {
            "token_ids": [11, 12],
            "hidden_states": tuple(rank_three_state for _ in range(33)),
        }
        adapter = object.__new__(SmolLM2C2ShapeAdapter)
        with patch("latent_triz.a0r2c2_adapter.SmolLM2C1MappingAdapter.run_prompt", return_value=payload):
            result = adapter.run_prompt(prompt="synthetic")
        self.assertEqual(33, len(result["hidden_states"]))
        self.assertTrue(all(len(state) == 2 and len(state[0]) == 960 for state in result["hidden_states"]))


if __name__ == "__main__":
    unittest.main()
