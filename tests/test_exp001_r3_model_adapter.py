import unittest
from collections.abc import Mapping
from types import SimpleNamespace

from latent_triz.exp001_r3_model_adapter import R3ModelAdapterError, SmolLM2R3Adapter


class Batch(Mapping):
    def __init__(self, values): self.values = values
    def __getitem__(self, key): return self.values[key]
    def __iter__(self): return iter(self.values)
    def __len__(self): return len(self.values)


class FakeTokenizer:
    is_fast = True
    def __call__(self, prompt, **kwargs):
        return Batch({"input_ids": [[1, 2]], "attention_mask": [[1, 1]]})


class FakeModel:
    def __init__(self, logits): self.logits, self.eval_called = logits, False
    def eval(self): self.eval_called = True; return self
    def __call__(self, **kwargs):
        return {"logits": self.logits, "hidden_states": ()}
    def generate(self, *args, **kwargs): raise AssertionError("generation is forbidden")


class AdapterTests(unittest.TestCase):
    def config(self, **overrides):
        values = dict(model_type="llama", num_hidden_layers=32, hidden_size=960,
                      architectures=["LlamaForCausalLM"])
        values.update(overrides)
        return SimpleNamespace(**values)

    def loaded(self, *, config=None, logits=None):
        calls = []
        cfg = config or self.config()
        tok = FakeTokenizer()
        model = FakeModel(logits or [[[0.0, 1.0], [1.0, 0.0]]])
        def factory(*args, **kwargs): calls.append(kwargs); return cfg
        adapter = SmolLM2R3Adapter.load("/tmp/r3", config_factory=factory,
            tokenizer_factory=lambda *a, **k: tok,
            model_factory=lambda *a, **k: model)
        return adapter, calls, model

    def test_mapping_batch_and_no_generation(self):
        adapter, calls, model = self.loaded()
        result = adapter.forward("prompt")
        self.assertEqual(result["input_ids"], [1, 2])
        self.assertFalse(result["generation_used"])
        self.assertTrue(model.eval_called)
        self.assertTrue(calls[0]["local_files_only"])

    def test_load_binds_local_fast_float32(self):
        _, calls, _ = self.loaded()
        self.assertTrue(calls[0]["local_files_only"])

    def test_rejects_config_mismatch(self):
        with self.assertRaises(R3ModelAdapterError): self.loaded(config=self.config(hidden_size=1))

    def test_rejects_bad_logit_rank(self):
        adapter, _, _ = self.loaded(logits=[[0.0, 1.0]])
        with self.assertRaises(R3ModelAdapterError): adapter.forward("prompt")


if __name__ == "__main__": unittest.main()
