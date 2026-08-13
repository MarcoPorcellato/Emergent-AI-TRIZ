from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import latent_triz.lab01_acquisition as acquisition
import latent_triz.lab01_runner as runner


REQUIRED_FILES = acquisition.LAB01_REQUIRED_FILES


class FakeAdapter:
    def __init__(
        self,
        *,
        model_root: Path,
        local_files_only: bool = True,
        device: str = "cpu",
        torch_dtype: str = "float32",
        top_k: int = 3,
        drift: float = 0.0,
        allow: bool = True,
        include_non_finite: bool = False,
    ) -> None:
        self.model_root = Path(model_root)
        self.local_files_only = local_files_only
        self.device = device
        self.torch_dtype = torch_dtype
        self.top_k = top_k
        self.drift = float(drift)
        self.call = 0
        if not local_files_only:
            raise ValueError("only local_files_only=True allowed")
        if device != "cpu":
            raise ValueError("only cpu allowed")
        if torch_dtype != "float32":
            raise ValueError("only float32 allowed")
        if not allow:
            raise ValueError("adapter disabled")
        self.include_non_finite = include_non_finite

    def run_prompt(self, *, prompt: str, instrumented: bool = True) -> dict[str, Any]:
        del prompt
        self.call += 1
        shift = 0.0 if instrumented else self.drift
        values = [1.0 + shift, 2.0 + shift]
        model_logits = [[1.0 + shift, 2.0 + shift], [3.0 + shift, 4.0 + shift]]
        if self.include_non_finite:
            model_logits[0][0] = float("nan")
        return {
            "raw_prompt": "prompt",
            "rendered_prompt": "prompt",
            "token_ids": [10, 11, 12],
            "token_pieces": ["a", "b", "c"],
            "token_inputs": [
                {"token_id": 10, "token_piece": "a", "is_special": False},
                {"token_id": 11, "token_piece": "b", "is_special": False},
                {"token_id": 12, "token_piece": "c", "is_special": True},
            ],
            "special_flags": [False, False, True],
            "attention_mask": [[1, 1, 1]],
            "position_ids": [[0, 1, 2]],
            "embedding_output": [[1.0 + shift, values[0]], [values[1], 1.5 + shift]],
            "resid_post_layer_0": [[2.0 + shift, 2.5 + shift], [2.5 + shift, 2.8 + shift]],
            "final_norm_output": [[3.0 + shift, 3.5 + shift], [3.8 + shift, 4.1 + shift]],
            "logits": model_logits,
            "model_logits": model_logits,
            "resid_post_layer_0_topk": {
                "token_ids": [1, 2],
                "token_pieces": ["x", "y"],
                "values": [values[0], values[1]],
            },
        }


class UnstableAdapter(FakeAdapter):
    def run_prompt(self, *, prompt: str, instrumented: bool = True) -> dict[str, Any]:
        payload = super().run_prompt(prompt=prompt, instrumented=instrumented)
        if instrumented and self.call % 2 == 0:
            payload["model_logits"][0][0] += 0.05
            payload["logits"][0][0] += 0.05
            payload["final_norm_output"][0][0] += 0.05
        return payload


def _build_fake_model_root() -> Path:
    model_root = Path(tempfile.mkdtemp())
    for filename in REQUIRED_FILES:
        (model_root / filename).write_text("{}", encoding="utf-8")
    return model_root


def _build_prompts(path: Path) -> Path:
    prompts = [
        {"prompt_id": "p1", "prompt": "Explain this clearly with no labels.", "prompt_kind": "frozen", "domain": "tests"},
    ]
    path.write_text("\n".join(str(item).replace("'", '"') for item in prompts), encoding="utf-8")
    return path


class Lab01RunnerTests(unittest.TestCase):
    def test_runner_writes_sparse_artifacts_and_html_notice(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            model_root = _build_fake_model_root()
            prompts_path = _build_prompts(Path(tempdir) / "prompts.jsonl")
            out_dir = Path(tempdir) / "out"
            outputs = runner.run_lab01_bundle(
                model_root=model_root,
                prompts_jsonl=prompts_path,
                output_dir=out_dir,
                repeats=2,
                adapter_factory=FakeAdapter,
                identity_verifier=lambda _path: (True, []),
            )

            for path in [
                outputs.model_receipt,
                outputs.environment,
                outputs.run_record,
                outputs.prompt_record,
                outputs.token_record,
                outputs.layer_summary,
                outputs.topk_logits,
                outputs.parity_report,
                outputs.report_html,
            ]:
                self.assertTrue(path.is_file())

            model_receipt = outputs.model_receipt.read_text(encoding="utf-8")
            self.assertIn('"artifact_class": "model-instrumentation"', model_receipt)
            self.assertIn('"evidence_eligible": false', model_receipt)

            report = outputs.report_html.read_text(encoding="utf-8")
            self.assertIn("No TRIZ claim", report)

            parity = _load_json(outputs.parity_report)
            self.assertEqual(parity["status"], "pass")
            self.assertEqual([item["gate"] for item in parity["gates"]], ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"])
            self.assertTrue(all(item["status"] == "pass" for item in parity["gates"]))

            topk_rows = list(_load_jsonl(outputs.topk_logits))
            self.assertEqual(topk_rows[0]["layer"], "resid_post_layer_0_topk")
            tokens = _load_json(outputs.tokens)[0]
            self.assertEqual(tokens["token_ids"], [10, 11, 12])

    def test_gates_fail_when_repeat_is_unstable(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            model_root = _build_fake_model_root()
            prompts_path = _build_prompts(Path(tempdir) / "prompts.jsonl")
            out_dir = Path(tempdir) / "out"
            outputs = runner.run_lab01_bundle(
                model_root=model_root,
                prompts_jsonl=prompts_path,
                output_dir=out_dir,
                repeats=2,
                adapter_factory=lambda **kwargs: FakeAdapter(drift=0.0, **kwargs),
                identity_verifier=lambda _path: (True, []),
            )
            parity = _load_json(outputs.parity_report)
            gate7 = next(g for g in parity["gates"] if g["gate"] == "G7")
            self.assertEqual(gate7["status"], "pass")

            outputs_unstable = runner.run_lab01_bundle(
                model_root=model_root,
                prompts_jsonl=prompts_path,
                output_dir=Path(tempdir) / "out2",
                repeats=2,
                adapter_factory=UnstableAdapter,
                identity_verifier=lambda _path: (True, []),
            )
            parity_unstable = _load_json(outputs_unstable.parity_report)
            gate7_unstable = next(g for g in parity_unstable["gates"] if g["gate"] == "G7")
            self.assertEqual(gate7_unstable["status"], "fail")
            self.assertEqual(parity_unstable["status"], "fail")

    def test_nonfinite_fails_health_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            model_root = _build_fake_model_root()
            prompts_path = _build_prompts(Path(tempdir) / "prompts.jsonl")
            outputs = runner.run_lab01_bundle(
                model_root=model_root,
                prompts_jsonl=prompts_path,
                output_dir=Path(tempdir) / "out",
                repeats=1,
                adapter_factory=lambda **kwargs: FakeAdapter(include_non_finite=True, **kwargs),
                identity_verifier=lambda _path: (True, []),
            )
            parity = _load_json(outputs.parity_report)
            gate5 = next(g for g in parity["gates"] if g["gate"] == "G5")
            self.assertEqual(gate5["status"], "fail")


def _load_json(path: Path) -> Any:
    return __import__("json").loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw:
            rows.append(__import__("json").loads(raw))
    return rows


if __name__ == "__main__":
    unittest.main()
