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


class ScoreTokenizer:
    is_fast = True
    def __call__(self, prompt, **kwargs):
        if prompt == "prompt":
            ids = [1, 2]
        elif prompt in {"prompt A", "prompt B", "prompt C", "prompt D"}:
            ids = [1, 2, {"A": 3, "B": 4, "C": 5, "D": 6}[prompt[-1]]]
        else:
            raise AssertionError(prompt)
        return Batch({"input_ids": [ids], "attention_mask": [[1] * len(ids)]})


class DriftTokenizer(ScoreTokenizer):
    def __call__(self, prompt, **kwargs):
        batch = super().__call__(prompt, **kwargs)
        if prompt.endswith(" A"):
            batch.values["input_ids"] = [[9, 3]]
            batch.values["attention_mask"] = [[1, 1]]
        return batch


class TensorTokenizer:
    is_fast = True
    def __call__(self, prompt, **kwargs):
        torch = __import__("torch")
        return Batch({"input_ids": torch.tensor([[1, 2]]), "attention_mask": torch.tensor([[1, 1]])})


class TensorModel(FakeModel):
    def __init__(self):
        super().__init__(None)
        self.received = None
    def __call__(self, **kwargs):
        torch = __import__("torch")
        self.received = kwargs
        return {"logits": torch.tensor([[[0.0, 1.0], [1.0, 0.0]]])}


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

    def test_teacher_forced_scores_continuation_at_causal_position(self):
        # Token 3 is preferred at position 1, which predicts full token index 2.
        model = FakeModel([[[0.0] * 7, [0.0, 0.0, 0.0, 4.0, 0.0, 0.0, 0.0], [0.0] * 7]])
        adapter = SmolLM2R3Adapter(ScoreTokenizer(), model, __import__("torch"))
        self.assertGreater(adapter.score_prompt_choice("prompt", "A"), -0.2)

    def test_teacher_forced_rejects_prefix_drift_before_model_access(self):
        model = FakeModel([[[0.0] * 7] for _ in range(3)])
        adapter = SmolLM2R3Adapter(DriftTokenizer(), model, __import__("torch"))
        with self.assertRaises(R3ModelAdapterError):
            adapter.score_prompt_choice("prompt", "A")

    def test_tensor_tokenizer_is_normalized_but_original_tensors_reach_model(self):
        model = TensorModel()
        adapter = SmolLM2R3Adapter(TensorTokenizer(), model, __import__("torch"))
        result = adapter.forward("prompt")
        self.assertEqual(result["input_ids"], [1, 2])
        self.assertTrue(hasattr(model.received["input_ids"], "detach"))


if __name__ == "__main__": unittest.main()
