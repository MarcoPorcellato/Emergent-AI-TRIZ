from collections import UserDict
from types import SimpleNamespace
import unittest

from latent_triz.a0r2_adapter import A0R2AdapterError
from latent_triz.a0r2c1_adapter import SmolLM2C1MappingAdapter

try:
    from transformers.tokenization_utils_base import BatchEncoding
except ImportError:  # The repository's dependency-free test lane remains supported.
    BatchEncoding = None


class _Tokenizer:
    is_fast = True

    def __init__(self, result):
        self.result = result

    def __call__(self, *args, **kwargs):
        return self.result

    def convert_ids_to_tokens(self, values):
        return [f"tok-{value}" for value in values]

    def get_special_tokens_mask(self, values, *, already_has_special_tokens):
        return [False] * len(values)


class _Adapter(SmolLM2C1MappingAdapter):
    def __init__(self, encoded):
        self.tokenizer = _Tokenizer(encoded)
        self.model = lambda **kwargs: SimpleNamespace(hidden_states=("hidden",), logits=None)
        self.torch = SimpleNamespace(device=lambda name: name)

    def _to_cpu_tensor(self, value):
        return value


def _encoded():
    return {"input_ids": [[1, 2]], "attention_mask": [[1, 1]], "offset_mapping": [[[0, 1], [1, 2]]]}


class TestA0R2C1Adapter(unittest.TestCase):
    def test_accepts_userdict_tokenizer_output(self):
        result = _Adapter(UserDict(_encoded())).run_prompt(prompt="ab")
        self.assertEqual(result["token_ids"], [1, 2])
        self.assertEqual(result["offsets_mapping"], [[0, 1], [1, 2]])

    @unittest.skipUnless(BatchEncoding is not None, "requires the installed Transformers ABI")
    def test_accepts_actual_transformers_batch_encoding(self):
        encoded = BatchEncoding(_encoded())
        self.assertFalse(isinstance(encoded, dict))
        result = _Adapter(encoded).run_prompt(prompt="ab")
        self.assertEqual(result["token_ids"], [1, 2])
        self.assertEqual(result["offsets_mapping"], [[0, 1], [1, 2]])

    def test_rejects_non_mapping_tokenizer_output(self):
        with self.assertRaisesRegex(A0R2AdapterError, "must be a mapping"):
            _Adapter([("input_ids", [[1]])]).run_prompt(prompt="a")
