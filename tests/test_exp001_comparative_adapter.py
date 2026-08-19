from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
import unittest

from latent_triz.exp001_comparative_adapter import (
    ComparativeAdapterError,
    ComparativeModelContract,
    ComparativeTeacherForcingAdapter,
)


class Batch(dict):
    pass


class FakeTokenizer:
    is_fast = True

    def __init__(self, *, drift: bool = False):
        self.drift = drift
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, text, **kwargs):
        self.calls.append((text, kwargs))
        ids = [1, 2] if text == "prompt" else [1, 2, 3]
        if self.drift and text != "prompt":
            ids = [0, 2, 3]
        return Batch(input_ids=[ids], attention_mask=[[1] * len(ids)])


class FakeModel:
    def __init__(self, *, logits=None):
        self.logits = logits if logits is not None else [[[0.0, 0.0, 0.0, 5.0]] * 3]
        self.eval_called = False
        self.to_value = None
        self.calls: list[dict] = []

    def eval(self):
        self.eval_called = True
        return self

    def to(self, value):
        self.to_value = value
        return self

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return {"logits": self.logits}

    def generate(self, *_args, **_kwargs):
        raise AssertionError("generation must never be invoked")


class FakeTorch:
    float32 = "float32"

    @staticmethod
    def device(name):
        return name

    @staticmethod
    def inference_mode():
        return nullcontext()


def contract(**overrides):
    values = {
        "model_id": "test/model",
        "revision": "a" * 40,
        "model_type": "gpt_neox",
        "architecture": "GPTNeoXForCausalLM",
        "num_hidden_layers": 2,
        "hidden_size": 8,
    }
    values.update(overrides)
    return ComparativeModelContract(**values)


def config_for(value):
    return SimpleNamespace(
        model_type=value.model_type,
        architectures=[value.architecture],
        num_hidden_layers=value.num_hidden_layers,
        hidden_size=value.hidden_size,
        vocab_size=4,
    )


class ComparativeAdapterTests(unittest.TestCase):
    def load(self, value=None, *, tokenizer=None, model=None):
        value = value or contract()
        tokenizer = tokenizer or FakeTokenizer()
        model = model or FakeModel()
        factory_calls = []

        def config_factory(root, **kwargs):
            factory_calls.append(("config", root, kwargs))
            return config_for(value)

        def tokenizer_factory(root, **kwargs):
            factory_calls.append(("tokenizer", root, kwargs))
            return tokenizer

        def model_factory(root, **kwargs):
            factory_calls.append(("model", root, kwargs))
            return model

        adapter = ComparativeTeacherForcingAdapter.load(
            "/tmp/comparative-model",
            contract=value,
            config_factory=config_factory,
            tokenizer_factory=tokenizer_factory,
            model_factory=model_factory,
            torch_module=FakeTorch,
        )
        return adapter, tokenizer, model, factory_calls

    def test_loads_supported_gpt_neox_llama_and_qwen_contracts_locally(self):
        variants = (
            contract(),
            contract(model_type="gpt2", architecture="GPT2LMHeadModel"),
            contract(model_type="llama", architecture="LlamaForCausalLM"),
            contract(model_type="qwen3", architecture="Qwen3ForCausalLM"),
        )
        for value in variants:
            with self.subTest(model_type=value.model_type):
                adapter, _tokenizer, model, calls = self.load(value)
                self.assertEqual(adapter.contract, value)
                self.assertTrue(model.eval_called)
                self.assertEqual(model.to_value, "cpu")
                for _name, _root, kwargs in calls:
                    self.assertTrue(kwargs["local_files_only"])
                    self.assertFalse(kwargs["trust_remote_code"])

    def test_rejects_network_generation_or_non_cpu_float32_contract(self):
        for value in (
            contract(network="enabled"),
            contract(generation=True),
            contract(device="cuda"),
            contract(dtype="float16"),
        ):
            with self.subTest(value=value):
                with self.assertRaises(ComparativeAdapterError):
                    self.load(value)
        with self.assertRaises(ComparativeAdapterError):
            ComparativeTeacherForcingAdapter.load(
                "https://example.invalid/model", contract=contract(),
                config_factory=lambda *_a, **_k: config_for(contract()),
                tokenizer_factory=lambda *_a, **_k: FakeTokenizer(),
                model_factory=lambda *_a, **_k: FakeModel(), torch_module=FakeTorch,
            )

    def test_rejects_model_contract_drift(self):
        fields = {
            "model_type": "llama",
            "architectures": ["LlamaForCausalLM"],
            "num_hidden_layers": 3,
            "hidden_size": 9,
        }
        for field, wrong in fields.items():
            with self.subTest(field=field):
                expected = contract()
                def config_factory(_root, **_kwargs):
                    result = config_for(expected)
                    setattr(result, field, wrong)
                    return result
                with self.assertRaises(ComparativeAdapterError):
                    ComparativeTeacherForcingAdapter.load(
                        "/tmp/model", contract=expected, config_factory=config_factory,
                        tokenizer_factory=lambda *_a, **_k: FakeTokenizer(),
                        model_factory=lambda *_a, **_k: FakeModel(), torch_module=FakeTorch,
                    )

    def test_rejects_non_fast_tokenizer_before_model_use(self):
        tokenizer = FakeTokenizer()
        tokenizer.is_fast = False
        with self.assertRaisesRegex(ComparativeAdapterError, "fast tokenizer"):
            self.load(tokenizer=tokenizer)

    def test_teacher_forcing_never_generates_and_uses_causal_position(self):
        adapter, tokenizer, model, _calls = self.load()
        self.assertGreater(adapter.score_prompt_choice("prompt", "A"), -0.1)
        self.assertEqual(len(model.calls), 1)
        self.assertFalse(model.calls[0]["use_cache"])
        self.assertTrue(all(call[1]["return_tensors"] == "pt" for call in tokenizer.calls))

    def test_rejects_prefix_drift_before_model_access(self):
        adapter, _tokenizer, model, _calls = self.load(tokenizer=FakeTokenizer(drift=True))
        with self.assertRaisesRegex(ComparativeAdapterError, "prefix drift"):
            adapter.score_prompt_choice("prompt", "A")
        self.assertEqual(model.calls, [])

    def test_rejects_nonfinite_logits(self):
        adapter, _tokenizer, _model, _calls = self.load(
            model=FakeModel(logits=[[[0.0, float("nan"), 1.0, 0.0]] * 3])
        )
        with self.assertRaisesRegex(ComparativeAdapterError, "finite"):
            adapter.score_prompt_choice("prompt", "A")


if __name__ == "__main__":
    unittest.main()
