from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import latent_triz.lab01 as lab01


class FakeAdapter:
    def __init__(self, jitter: float = 0.0) -> None:
        self.jitter = jitter
        self.call = 0

    def run_prompt(self, *, prompt: str, instrumented: bool = True) -> dict[str, Any]:
        self.call += 1
        if not instrumented:
            return self._payload(0.0, prompt)
        if self.jitter and self.call % 2 == 0:
            return self._payload(self.jitter, prompt)
        return self._payload(0.0, prompt)

    def _payload(self, jitter: float, prompt: str) -> dict[str, Any]:
        embedding = [[1.0, 2.0], [3.0, 4.0]]
        layer_00 = [[val + 1.0 + jitter for val in row] for row in embedding]
        layer_01 = [[val + 2.0 + jitter for val in row] for row in embedding]
        final_norm = [[val + 3.0 + jitter for val in row] for row in embedding]
        logits = [[3.0 + jitter, 4.0 + jitter], [5.0 + jitter, 6.0 + jitter]]
        model_logits = [list(row) for row in logits]
        return {
            "raw_prompt": prompt,
            "rendered_prompt": f"<r>{prompt}</r>",
            "token_ids": [10, 11, 12],
            "token_pieces": ["a", "b", "c"],
            "token_inputs": [
                {"token_id": 10, "token_piece": "a", "is_special": False},
                {"token_id": 11, "token_piece": "b", "is_special": True},
                {"token_id": 12, "token_piece": "c", "is_special": False},
            ],
            "special_flags": [False, True, False],
            "attention_mask": [[1, 1, 1]],
            "position_ids": [[0, 1, 2]],
            "hidden_states": (embedding, layer_00, layer_01),
            "embedding_output": embedding,
            "resid_post_layer_0": layer_00,
            "resid_post_layer_1": layer_01,
            "final_norm_output": final_norm,
            "logits": logits,
            "model_logits": model_logits,
            "resid_post_layer_0_topk": {
                "token_ids": [1, 2], "token_pieces": ["x", "y"], "values": [1.0, 0.5]
            },
        }


class Lab01Tests(unittest.TestCase):
    def test_lab01_artifact_records_required_classification_and_canonical_tensors(self) -> None:
        artifact = lab01.run_lab01(FakeAdapter(), "demo prompt", repeats=1)
        self.assertTrue(artifact.empirical)
        self.assertFalse(artifact.evidence_eligible)
        self.assertEqual(artifact.artifact_class, "model-instrumentation")
        self.assertEqual(artifact.claim_ids, [])
        self.assertEqual(artifact.raw_prompt, "demo prompt")
        self.assertEqual(artifact.rendered_prompt, "<r>demo prompt</r>")
        self.assertEqual(artifact.token_ids, [10, 11, 12])
        self.assertIn("embedding_output", artifact.canonical_tensors)
        self.assertIn("resid_post_layer_0", artifact.canonical_tensors)
        self.assertIn("resid_post_layer_1", artifact.canonical_tensors)
        self.assertIn("final_norm_output", artifact.canonical_tensors)
        self.assertIn("model_logits", artifact.canonical_tensors)
        self.assertIn("model_logits_raw", artifact.canonical_tensors)
        self.assertIn("embedding_output", artifact.health)
        self.assertIn("resid_post_layer_0_topk", artifact.topk_logits)
        self.assertEqual(artifact.instrumentation_parity["final_lens_parity_status"], "pass")

    def test_lab01_instrumentation_parity_and_repeats_pass_for_deterministic_adapter(self) -> None:
        adapter = FakeAdapter()
        artifact = lab01.run_lab01(adapter, "prompt")
        self.assertEqual(artifact.instrumentation_parity["status"], "pass")
        self.assertEqual(artifact.instrumentation_parity["max_abs_diff"], 0.0)
        repeat = lab01.run_lab01(adapter, "prompt", repeats=2)
        self.assertEqual(repeat.repeatability["status"], "pass")

    def test_lab01_repeated_run_reports_drift(self) -> None:
        artifact = lab01.run_lab01(FakeAdapter(jitter=0.02), "prompt", repeats=2)
        self.assertEqual(artifact.repeatability["status"], "fail")
        self.assertGreater(artifact.repeatability["max_abs_diff"], 0.0)

    def test_lab01_tolerance_policy_is_backend_and_dtype_driven(self) -> None:
        policy = lab01.stable_json_dumps(lab01._default_tolerance_policy())
        parsed = json.loads(policy)
        self.assertIn("float16", parsed["default"])
        self.assertIn("rtol", parsed["default"]["float16"])
        self.assertIn("atol", parsed["default"]["float16"])

    def test_stable_dump_is_deterministic(self) -> None:
        artifact = lab01.run_lab01(FakeAdapter(), "prompt")
        first = artifact.stable_dump()
        second = artifact.stable_dump()
        self.assertEqual(first, second)

    def test_artifact_has_deterministic_digest_and_shape_metadata(self) -> None:
        artifact = lab01.run_lab01(FakeAdapter(), "prompt")
        embedding_meta = artifact.canonical_tensors["embedding_output"]
        self.assertEqual(embedding_meta.shape, [2, 2])
        self.assertTrue(embedding_meta.digest)
        self.assertEqual(len(embedding_meta.dtype), len(embedding_meta.dtype))
        self.assertIn("finite_ratio", artifact.health["embedding_output"])
        self.assertTrue(artifact.health["embedding_output"]["finite_ratio"] == 1.0)


if __name__ == "__main__":
    unittest.main()
