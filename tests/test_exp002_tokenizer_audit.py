import unittest

from latent_triz.exp002_tokenizer_audit import Exp002TokenizerAuditError, audit_tokenizer, validate_observation


class FakeFastTokenizer:
    is_fast = True
    bos_token_id = 1
    eos_token_id = 2
    pad_token_id = 0
    all_special_ids = [0, 1, 2]

    def __call__(self, text, add_special_tokens=False):
        values = [len(part) + 10 for part in text.split()]
        return {"input_ids": values}


class FakeSlowTokenizer(FakeFastTokenizer):
    is_fast = False


class Exp002TokenizerAuditTests(unittest.TestCase):
    def test_fake_fast_tokenizer_observation(self):
        observation = audit_tokenizer(
            model_id="Qwen/Qwen3-0.6B-Base",
            revision="da87bfb608c14b7cf20ba1ce41287e8de496c0cd",
            tokenizer=FakeFastTokenizer(),
            tokenizer_files_sha256="0" * 64,
            runtime_versions={"transformers": "synthetic"},
            prompt_texts=("a transfer prompt",),
            transfer_control_pairs=(("transfer prompt", "control prompt"),),
        )
        validate_observation(observation)
        self.assertEqual(set(observation["label_token_ids"]), set("ABCD"))
        self.assertTrue(observation["prefix_boundary_ok"])

    def test_slow_tokenizer_and_identity_drift_fail_closed(self):
        with self.assertRaises(Exp002TokenizerAuditError):
            audit_tokenizer(model_id="Qwen/Qwen3-0.6B-Base", revision="da87bfb608c14b7cf20ba1ce41287e8de496c0cd", tokenizer=FakeSlowTokenizer(), tokenizer_files_sha256="0" * 64, runtime_versions={"transformers": "synthetic"})
        with self.assertRaises(Exp002TokenizerAuditError):
            audit_tokenizer(model_id="Qwen/Qwen3-0.6B-Base", revision="0" * 40, tokenizer=FakeFastTokenizer(), tokenizer_files_sha256="0" * 64, runtime_versions={"transformers": "synthetic"})


if __name__ == "__main__":
    unittest.main()
