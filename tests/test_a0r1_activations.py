from __future__ import annotations

import builtins
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz import lab01_acquisition
from latent_triz.a0r1_activations import A0R1ActivationError, run_a0r1_activations
from latent_triz.validator import validate


class _FakeTokenizer:
    name_or_path = "tests/fake-tokenizer"
    is_fast = True

    def __call__(
        self,
        text: str,
        *,
        add_special_tokens: bool,
        return_attention_mask: bool,
        return_offsets_mapping: bool,
    ) -> dict:
        offsets = [[i, i + 1] for i in range(len(text))]
        input_ids = [int(ord(ch)) for ch in text]
        return {
            "input_ids": input_ids,
            "attention_mask": [1] * len(input_ids),
            "offset_mapping": offsets,
        }

    def get_special_tokens_mask(self, input_ids: list[int], already_has_special_tokens: bool = True) -> list[int]:
        return [0] * len(input_ids)


class _FakeAdapter:
    def __init__(self, hidden_states: tuple, token_ids: list[int] | None = None, call_assertion=None):
        self.tokenizer = _FakeTokenizer()
        self.hidden_states = hidden_states
        self.token_ids = token_ids
        self.calls: list[str] = []
        self.call_assertion = call_assertion

    def run_prompt(self, *, prompt: str, instrumented: bool = True):
        self.calls.append(prompt)
        if self.call_assertion is not None:
            self.call_assertion(prompt)
        token_ids = self.token_ids if self.token_ids is not None else [ord(ch) for ch in prompt]
        return {
            "token_ids": token_ids,
            "hidden_states": self.hidden_states,
            "special_token_flags": [False] * len(token_ids),
        }


class A0R1ActivationsTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.activation_schema = json.loads((root / "schemas/a0r1-activation-receipt.schema.json").read_text(encoding="utf-8"))
        self.protocol = {
            "artifact_class": "a0-r1-protocol",
            "protocol_id": "a0-r1-tier-r1-v1.0",
            "protocol_status": "frozen",
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "primary_endpoint": {
                "layer": 6,
                "token_site": "mean_transformation_span",
                "primary_view": "problem_plus_transformation",
                "surface_baseline_view": "problem_only",
                "multiplicity": 1,
            },
            "sensitivity_endpoints": {
                "layers": [0, 2, 4, 6],
                "views": [
                    "problem_only",
                    "transformation_only",
                    "problem_plus_transformation",
                    "problem_plus_solution",
                ],
                "token_sites": [
                    "sentinel",
                    "final_transformation_token",
                    "mean_transformation_span",
                ],
                "status": "frozen",
            },
            "status": "frozen",
        }
        self.implementation = {
            "artifact_class": "a0-r1-implementation",
            "protocol_id": "a0-r1-tier-r1-v1.0",
            "protocol_status": "frozen",
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "token_site_applicability": {
                "problem_only": ["sentinel"],
                "transformation_only": ["sentinel", "final_transformation_token", "mean_transformation_span"],
                "problem_plus_transformation": ["sentinel", "final_transformation_token", "mean_transformation_span"],
                "problem_plus_solution": ["sentinel", "final_transformation_token"],
            },
            "sentinel_text": "Analysis anchor:",
            "status": "frozen_before_model_output",
            "epistemic_boundary": {
                "empirical": True,
                "scientific_status": "exploratory",
                "evidence_eligible": False,
                "expert_validated": False,
                "claim_ids": [],
            },
            "runtime": {
                "requires_interactive_model_server": False,
                "runtime_device": "cpu",
                "binding_scope": "exact",
                "model_runtime_hashes": [],
            },
        }
        self.freeze = {
            "artifact_class": "a0-r1-protocol-freeze-manifest",
            "protocol_id": "a0-r1-tier-r1-v1.0",
            "protocol_status": "frozen",
            "status": "frozen",
            "model_output_accessed": False,
            "sealed_model_output_accessed": False,
            "frozen_at": "2026-08-14T12:00:00Z",
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
        }
        self._verify_snapshot_patch = patch(
            "latent_triz.lab01_acquisition.verify_expected_snapshot",
            return_value=(True, []),
        )
        self._verify_snapshot_patch.start()

    def tearDown(self) -> None:
        self._verify_snapshot_patch.stop()

    def _build_case(self, case_id: str) -> dict:
        return {
            "case_id": case_id,
            "split": "sealed",
            "domain": "manufacturing",
            "problem_family_id": "mfg_01",
            "problem": "Improve throughput without cost increase",
            "constraints": ["low cost", "high safety"],
            "initial_state": "Initial throughput is low",
            "desired_improvement": "Increase output",
            "worsening_consequence": "Delays grow",
            "transformation": "Use queue balancing",
            "solution": "Use queue balancing",
        }

    def _write_case_bundle(self, root: Path, count: int = 1) -> Path:
        cases = [self._build_case(f"case_{index:03d}") for index in range(1, count + 1)]
        cases_path = root / "cases.jsonl"
        cases_payload = "\n".join(json.dumps(case, ensure_ascii=False) for case in cases) + "\n"
        cases_path.write_text(cases_payload, encoding="utf-8")
        (root / "sealed_targets_jsonl.json").write_text("{\"a\":1}\n", encoding="utf-8")
        (root / "calibration_targets_jsonl.jsonl").write_text("{\"b\":2}\n", encoding="utf-8")
        return cases_path

    def _write_manifest(self, root: Path, cases_path: Path) -> None:
        manifest = {
            "artifact_class": "a0-r1-corpus-manifest",
            "protocol_id": "a0-r1-tier-r1-v1.0",
            "status": "sealed",
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "files": {
                "cases_jsonl": {
                    "path": cases_path.name,
                    "sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
                    "size": cases_path.stat().st_size,
                },
                "sealed_targets_jsonl": {
                    "path": "sealed_targets_jsonl.json",
                    "sha256": hashlib.sha256((root / "sealed_targets_jsonl.json").read_bytes()).hexdigest(),
                    "size": (root / "sealed_targets_jsonl.json").stat().st_size,
                },
                "calibration_targets_jsonl": {
                    "path": "calibration_targets_jsonl.jsonl",
                    "sha256": hashlib.sha256((root / "calibration_targets_jsonl.jsonl").read_bytes()).hexdigest(),
                    "size": (root / "calibration_targets_jsonl.jsonl").stat().st_size,
                },
            },
        }
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False) + "\n", encoding="utf-8")

    def _write_model_root(self, root: Path) -> None:
        for filename in lab01_acquisition.LAB01_REQUIRED_FILES:
            (root / filename).write_text(filename, encoding="utf-8")

    def _write_inputs(self, root: Path, case_count: int = 1) -> tuple[Path, Path, Path, Path, Path]:
        model_root = root / "pythia"
        model_root.mkdir(parents=True)
        self._write_model_root(model_root)
        cases_path = self._write_case_bundle(root, count=case_count)
        self._write_manifest(root, cases_path)
        protocol_path = root / "protocol.json"
        implementation_path = root / "implementation.json"
        freeze_path = root / "freeze.json"

        runtime_receipts = [
            {"path": value.name, "sha256": value.sha256, "size": value.size}
            for value in sorted(
                lab01_acquisition.build_runtime_file_receipts(model_root).values(),
                key=lambda item: item.name,
            )
        ]
        self.implementation["runtime"]["model_runtime_hashes"] = runtime_receipts

        protocol_path.write_text(json.dumps(self.protocol, ensure_ascii=False) + "\n", encoding="utf-8")
        self.freeze["frozen_protocol_hash"] = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
        self.freeze["corpus_manifest_hash"] = hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()
        self.freeze["cases_sha256"] = hashlib.sha256(cases_path.read_bytes()).hexdigest()
        self.freeze["sealed_targets_sha256"] = hashlib.sha256((root / "sealed_targets_jsonl.json").read_bytes()).hexdigest()
        implementation_path.write_text(json.dumps(self.implementation, ensure_ascii=False) + "\n", encoding="utf-8")
        freeze_path.write_text(json.dumps(self.freeze, ensure_ascii=False) + "\n", encoding="utf-8")
        return protocol_path, implementation_path, freeze_path, root / "manifest.json", model_root

    @staticmethod
    def _vector_state(value: float = 1.0) -> tuple:
        vectors = [[value + i * 0.1, value + i * 0.2] for i in range(300)]
        return tuple([vectors] * 7)

    def _run(self, adapter_factory, root: Path, case_count: int = 1):
        protocol_path, implementation_path, freeze_path, corpus_manifest, model_root = self._write_inputs(
            root, case_count=case_count
        )
        return run_a0r1_activations(
            protocol_path=protocol_path,
            implementation_path=implementation_path,
            freeze_path=freeze_path,
            corpus_dir=root,
            model_root=model_root,
            output_dir=root / "out",
            created_at="2026-08-14T12:00:00Z",
            adapter_factory=adapter_factory,
        )

    def test_refuses_overwrite_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            root = Path(workdir)
            protocol_path, implementation_path, freeze_path, corpus_manifest, model_root = self._write_inputs(root)
            (root / "out").mkdir(parents=True)
            (root / "out" / "old.txt").write_text("legacy", encoding="utf-8")
            with self.assertRaises(A0R1ActivationError):
                run_a0r1_activations(
                    protocol_path=protocol_path,
                    implementation_path=implementation_path,
                    freeze_path=freeze_path,
                    corpus_dir=root,
                    model_root=model_root,
                    output_dir=root / "out",
                    created_at="2026-08-14T12:00:00Z",
                    adapter_factory=lambda **kwargs: _FakeAdapter(
                        hidden_states=self._vector_state(),
                        token_ids=[1, 2, 3],
                    ),
                )

    def test_detector_flags_token_id_drift(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            root = Path(workdir)
            old_open = builtins.open
            root_manifest_calls: list[str] = []
            with patch("builtins.open", side_effect=lambda file, *a, **k: root_manifest_calls.append(str(file)) or old_open(file, *a, **k)):
                protocol_path, implementation_path, freeze_path, corpus_manifest, model_root = self._write_inputs(root)
                with self.assertRaises(A0R1ActivationError):
                    run_a0r1_activations(
                        protocol_path=protocol_path,
                        implementation_path=implementation_path,
                        freeze_path=freeze_path,
                        corpus_dir=root,
                        model_root=model_root,
                        output_dir=root / "out",
                        created_at="2026-08-14T12:00:00Z",
                        adapter_factory=lambda **kwargs: _FakeAdapter(
                            hidden_states=self._vector_state(),
                            token_ids=[1, 2],
                        ),
                    )
                self.assertNotIn("sealed_targets_jsonl.json", "".join(root_manifest_calls))

    def test_requires_finite_vectors(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            root = Path(workdir)
            protocol_path, implementation_path, freeze_path, corpus_manifest, model_root = self._write_inputs(root)
            state = (tuple([[[1.0, float("nan")]] * 60] for _ in range(7)))
            with self.assertRaises(A0R1ActivationError):
                run_a0r1_activations(
                    protocol_path=protocol_path,
                    implementation_path=implementation_path,
                    freeze_path=freeze_path,
                    corpus_dir=root,
                    model_root=model_root,
                    output_dir=root / "out",
                    created_at="2026-08-14T12:00:00Z",
                    adapter_factory=lambda **kwargs: _FakeAdapter(
                        hidden_states=state,
                        token_ids=[i for i in range(len("Improve throughput without cost increase\n\nConstraints: low cost high safety\n\nInitial throughput is low\n\nDesired improvement: Increase output\n\nWorsening consequence: Delays grow\n\nAnalysis anchor:"))],
                    ),
                )

    def test_missing_hidden_states_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            root = Path(workdir)
            protocol_path, implementation_path, freeze_path, corpus_manifest, model_root = self._write_inputs(root)
            with self.assertRaises(A0R1ActivationError):
                run_a0r1_activations(
                    protocol_path=protocol_path,
                    implementation_path=implementation_path,
                    freeze_path=freeze_path,
                    corpus_dir=root,
                    model_root=model_root,
                    output_dir=root / "out",
                    created_at="2026-08-14T12:00:00Z",
                    adapter_factory=lambda **kwargs: _FakeAdapter(
                        hidden_states=[],
                        token_ids=[1, 2, 3],
                    ),
                )

    def test_output_and_hashes_are_bound(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            root = Path(workdir)
            protocol_path = root / "protocol.json"
            implementation_path = root / "implementation.json"
            freeze_path = root / "freeze.json"
            protocol_path, implementation_path, freeze_path, _, model_root = self._write_inputs(root)
            adapter_payload = _FakeAdapter(
                hidden_states=self._vector_state(2.0),
            )
            artifacts = run_a0r1_activations(
                protocol_path=protocol_path,
                implementation_path=implementation_path,
                freeze_path=freeze_path,
                corpus_dir=root,
                model_root=model_root,
                output_dir=root / "out",
                created_at="2026-08-14T12:00:00Z",
                adapter_factory=lambda **_: adapter_payload,
            )
            self.assertTrue(artifacts.dense_path.is_file())
            self.assertTrue(artifacts.index_path.is_file())
            self.assertTrue(artifacts.receipt_path.is_file())

            receipt = json.loads(artifacts.receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["artifact_class"], "a0r1-activation-receipt")
            self.assertEqual(receipt["sealed_target_semantics_accessed"], False)
            self.assertEqual(receipt["protocol"]["id"], self.protocol["protocol_id"])
            self.assertEqual(receipt["primary_contract"]["primary_view"], "problem_plus_transformation")
            self.assertEqual(receipt["primary_contract"]["baseline_view"], "problem_only")
            self.assertEqual(
                receipt["corpus"]["manifest_sha256"],
                hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest(),
            )
            self.assertEqual(len((root / "out" / "representations-index.jsonl").read_text(encoding="utf-8").splitlines()), 2)

    def test_frozen_contract_generates_expected_record_count(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            root = Path(workdir)
            protocol_path, implementation_path, freeze_path, _, model_root = self._write_inputs(root, case_count=48)
            artifacts = run_a0r1_activations(
                protocol_path=protocol_path,
                implementation_path=implementation_path,
                freeze_path=freeze_path,
                corpus_dir=root,
                model_root=model_root,
                output_dir=root / "out",
                created_at="2026-08-14T12:00:00Z",
                adapter_factory=lambda **kwargs: _FakeAdapter(
                    hidden_states=self._vector_state(3.0),
                ),
            )
            self.assertEqual(json.loads(artifacts.receipt_path.read_text(encoding="utf-8"))["records"], 96)

    def test_frozen_contract_receipt_validates_against_schema(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            root = Path(workdir)
            protocol_path, implementation_path, freeze_path, _, model_root = self._write_inputs(root, case_count=48)
            artifacts = run_a0r1_activations(
                protocol_path=protocol_path,
                implementation_path=implementation_path,
                freeze_path=freeze_path,
                corpus_dir=root,
                model_root=model_root,
                output_dir=root / "out",
                created_at="2026-08-14T12:00:00Z",
                adapter_factory=lambda **kwargs: _FakeAdapter(
                    hidden_states=self._vector_state(3.0),
                ),
            )
            receipt = json.loads(artifacts.receipt_path.read_text(encoding="utf-8"))
            self.assertEqual([], validate(receipt, self.activation_schema))

    def test_verifies_runtime_contract_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            root = Path(workdir)
            protocol_path, implementation_path, freeze_path, _, model_root = self._write_inputs(root)
            implementation_payload = json.loads((root / "implementation.json").read_text(encoding="utf-8"))
            implementation_payload["runtime"]["model_runtime_hashes"][0]["sha256"] = "f" * 64
            (root / "implementation.json").write_text(json.dumps(implementation_payload, ensure_ascii=False) + "\n", encoding="utf-8")
            with self.assertRaises(A0R1ActivationError):
                run_a0r1_activations(
                    protocol_path=protocol_path,
                    implementation_path=implementation_path,
                    freeze_path=freeze_path,
                    corpus_dir=root,
                    model_root=model_root,
                    output_dir=root / "out",
                    created_at="2026-08-14T12:00:00Z",
                    adapter_factory=lambda **_: _FakeAdapter(hidden_states=self._vector_state()),
                )

    def test_token_index_error_is_a0r1_activation_error(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            root = Path(workdir)
            protocol_path, implementation_path, freeze_path, _, model_root = self._write_inputs(root)
            broken_state = tuple([[[1.0, 2.0]]] * 7)
            with self.assertRaises(A0R1ActivationError):
                run_a0r1_activations(
                    protocol_path=protocol_path,
                    implementation_path=implementation_path,
                    freeze_path=freeze_path,
                    corpus_dir=root,
                    model_root=model_root,
                    output_dir=root / "out",
                    created_at="2026-08-14T12:00:00Z",
                    adapter_factory=lambda **kwargs: _FakeAdapter(
                        hidden_states=broken_state,
                    ),
                )

    def test_rejects_freeze_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            root = Path(workdir)
            protocol_path, implementation_path, freeze_path, _, model_root = self._write_inputs(root)
            freeze_payload = json.loads((root / "freeze.json").read_text(encoding="utf-8"))
            freeze_payload["frozen_protocol_hash"] = "0" * 64
            (root / "freeze.json").write_text(json.dumps(freeze_payload, ensure_ascii=False) + "\n", encoding="utf-8")
            with self.assertRaises(A0R1ActivationError):
                run_a0r1_activations(
                    protocol_path=protocol_path,
                    implementation_path=implementation_path,
                    freeze_path=freeze_path,
                    corpus_dir=root,
                    model_root=model_root,
                    output_dir=root / "out",
                    created_at="2026-08-14T12:00:00Z",
                    adapter_factory=lambda **kwargs: _FakeAdapter(hidden_states=self._vector_state()),
                )
