from __future__ import annotations

import json
import io
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz import a0r2_feasibility as feasibility
from latent_triz.a0r2_acquisition import A0R2AcquisitionError
from latent_triz.validator import validate


class _FakeBackend:
    def __init__(self, metrics: dict[str, object] | None = None) -> None:
        self.timings = {
            "config_load_seconds": 0.1,
            "tokenizer_load_seconds": 0.2,
            "model_load_seconds": 0.3,
        }
        self.calls: list[tuple[str, int, int]] = []
        self.metrics = metrics or {
            "tokenizer_fast": True,
            "offsets_supported": True,
            "token_count": 21,
            "hidden_states_count": 33,
            "final_hidden_shape": [1, 21, 960],
            "logits_shape": [1, 21, 49152],
            "finite_hidden_states": True,
            "finite_logits": True,
            "max_abs_repeat_difference": 0.0,
            "forward_seconds": [0.4, 0.3],
        }

    def run_probe(self, prompt: str, *, maximum_prompt_tokens: int, inference_passes: int):
        self.calls.append((prompt, maximum_prompt_tokens, inference_passes))
        return dict(self.metrics)


class A0R2FeasibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = ROOT / "experiments/a0r2-independent-model/feasibility-contract.json"
        self.model_root = ROOT / "artifacts/models/not-opened-by-fake"
        self.receipt_schema = json.loads(
            (ROOT / "schemas/a0r2-feasibility-receipt.schema.json").read_text(encoding="utf-8")
        )

    def _run(self, backend: _FakeBackend) -> dict[str, object]:
        with patch.object(feasibility, "acquire_a0r2_runtime") as verify, patch.object(
            feasibility, "_peak_rss_bytes", return_value=2_000_000_000
        ), patch.object(feasibility, "_version", return_value="test-version"):
            payload = feasibility.run_feasibility(
                root=ROOT,
                model_root=self.model_root,
                contract_path=self.contract,
                created_at="2026-08-15T17:00:00Z",
                backend_factory=lambda _root, _contract: backend,
            )
        verify.assert_called_once_with(self.model_root, allow_download=False)
        return payload

    def test_compatible_probe_is_instrumentation_only(self) -> None:
        backend = _FakeBackend()
        payload = self._run(backend)
        self.assertEqual("compatible", payload["status"])
        self.assertFalse(payload["empirical"])
        self.assertFalse(payload["evidence_eligible"])
        self.assertEqual([], payload["claim_ids"])
        self.assertEqual(1, len(backend.calls))
        _, maximum_tokens, passes = backend.calls[0]
        self.assertEqual(128, maximum_tokens)
        self.assertEqual(2, passes)
        self.assertEqual("accessed", payload["access"]["model_loaded"])
        self.assertEqual("accessed", payload["access"]["model_output_accessed"])
        self.assertEqual("not_accessed", payload["access"]["model_output_content_retained"])
        self.assertEqual("not_accessed", payload["access"]["sealed_targets_accessed"])
        self.assertEqual([], validate(payload, self.receipt_schema))

    def test_snapshot_failure_prevents_backend_creation(self) -> None:
        factory = Mock()
        with patch.object(
            feasibility,
            "acquire_a0r2_runtime",
            side_effect=A0R2AcquisitionError("bad snapshot"),
        ):
            with self.assertRaisesRegex(A0R2AcquisitionError, "bad snapshot"):
                feasibility.run_feasibility(
                    root=ROOT,
                    model_root=self.model_root,
                    contract_path=self.contract,
                    created_at="2026-08-15T17:00:00Z",
                    backend_factory=factory,
                )
        factory.assert_not_called()

    def test_contract_failure_prevents_snapshot_and_backend(self) -> None:
        factory = Mock()
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "contract.json"
            payload = json.loads(self.contract.read_text(encoding="utf-8"))
            payload["model"]["model_type"] = "gpt_neox"
            bad.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(feasibility, "acquire_a0r2_runtime") as verify:
                with self.assertRaisesRegex(feasibility.A0R2FeasibilityError, "validation failed"):
                    feasibility.run_feasibility(
                        root=ROOT,
                        model_root=self.model_root,
                        contract_path=bad,
                        created_at="2026-08-15T17:00:00Z",
                        backend_factory=factory,
                    )
        verify.assert_not_called()
        factory.assert_not_called()

    def test_hidden_state_mapping_mismatch_is_terminal_incompatible(self) -> None:
        metrics = dict(_FakeBackend().metrics)
        metrics["hidden_states_count"] = 32
        payload = self._run(_FakeBackend(metrics))
        self.assertEqual("incompatible", payload["status"])
        self.assertFalse(payload["compatibility"]["checks"]["hidden_states_count"])
        self.assertFalse(payload["compatibility"]["compatible"])

    def test_nonfinite_or_repeatability_failure_is_incompatible(self) -> None:
        metrics = dict(_FakeBackend().metrics)
        metrics["finite_logits"] = False
        metrics["max_abs_repeat_difference"] = 0.5
        payload = self._run(_FakeBackend(metrics))
        self.assertEqual("incompatible", payload["status"])
        self.assertFalse(payload["compatibility"]["checks"]["finite_logits"])
        self.assertFalse(payload["compatibility"]["checks"]["repeatability"])

    def test_resource_envelope_failure_is_incompatible(self) -> None:
        backend = _FakeBackend()
        with patch.object(feasibility, "acquire_a0r2_runtime"), patch.object(
            feasibility, "_peak_rss_bytes", return_value=9_000_000_000
        ):
            payload = feasibility.run_feasibility(
                root=ROOT,
                model_root=self.model_root,
                contract_path=self.contract,
                created_at="2026-08-15T17:00:00Z",
                backend_factory=lambda _root, _contract: backend,
            )
        self.assertEqual("incompatible", payload["status"])
        self.assertFalse(payload["runtime"]["within_resource_envelope"])

    def test_receipt_writer_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            feasibility.write_receipt_exclusive(path, {"status": "compatible"})
            with self.assertRaisesRegex(feasibility.A0R2FeasibilityError, "refusing to overwrite"):
                feasibility.write_receipt_exclusive(path, {"status": "failed"})

    def test_verifier_binds_contract_and_predecessor_hashes(self) -> None:
        payload = self._run(_FakeBackend())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            feasibility.write_receipt_exclusive(path, payload)
            verified = feasibility.verify_receipt(root=ROOT, contract_path=self.contract, receipt_path=path)
            self.assertEqual("compatible", verified["status"])

            payload["contract_sha256"] = "0" * 64
            path.unlink()
            feasibility.write_receipt_exclusive(path, payload)
            with self.assertRaisesRegex(feasibility.A0R2FeasibilityError, "contract hash mismatch"):
                feasibility.verify_receipt(root=ROOT, contract_path=self.contract, receipt_path=path)

    def test_public_module_has_no_generation_or_sealed_input_api(self) -> None:
        parser_args = feasibility.main
        self.assertFalse(hasattr(parser_args, "sealed_targets"))
        self.assertFalse(hasattr(feasibility.TransformersFeasibilityBackend, "generate"))

    def test_cli_publishes_hashed_failure_without_error_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / "failure.json"
            with patch.object(feasibility, "run_feasibility", side_effect=RuntimeError("private/path")):
                with redirect_stdout(io.StringIO()):
                    result = feasibility.main(
                        [
                            "--root", str(ROOT),
                            "--model-root", str(self.model_root),
                            "--receipt", str(receipt),
                            "--created-at", "2026-08-15T17:00:00Z",
                        ]
                    )
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(2, result)
            self.assertEqual("failed", payload["status"])
            self.assertNotIn("private/path", receipt.read_text(encoding="utf-8"))
            self.assertEqual("unknown", payload["access"]["model_loaded"])
            self.assertEqual("not_accessed", payload["access"]["sealed_targets_accessed"])
            self.assertEqual([], validate(payload, self.receipt_schema))


if __name__ == "__main__":
    unittest.main()
