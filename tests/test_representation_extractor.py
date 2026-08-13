from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import torch
except ModuleNotFoundError:  # pragma: no cover
    torch = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz import lab01_acquisition
from latent_triz import representation_extractor as extractor


class _FakeTokenizer:
    def __init__(self) -> None:
        self.name_or_path = "fake/tokenizer"


class _FakeAdapter:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[str] = []
        self.tokenizer = _FakeTokenizer()

    def run_prompt(self, *, prompt: str, instrumented: bool = True) -> dict:
        self.calls.append(prompt)
        return self.payload


class RepresentationExtractorTests(unittest.TestCase):
    def _hash_canonical_tensor(self, tensor) -> str:
        t = tensor.detach().to(dtype=torch.float32).cpu().contiguous().numpy()
        byteorder = t.dtype.byteorder or "little"
        if byteorder not in ("<", "|"):
            t = t.astype(t.dtype.newbyteorder("<"), copy=False)
            byteorder = "<"
        payload = t.tobytes(order="C")
        metadata = json.dumps(
            {
                "dtype": str(t.dtype),
                "shape": list(t.shape),
                "byte_order": byteorder,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(metadata + b"|" + payload).hexdigest()

    def _build_case(self, case_id: str) -> dict:
        return {
            "case_id": case_id,
            "domain": "manufacturing",
            "problem": f"Case {case_id}: reduce heat",
            "constraints": ["low_cost", "high_reliability"],
            "initial_state": "Conveyor is unstable",
            "desired_improvement": "Keep quality stable",
            "worsening_consequence": "Frequent defects",
            "transformation": "Segment flow regions",
            "resulting_state": "Stable process",
            "labels": [{"principle": "segmentation", "annotator_id": "unit_test"}],
            "provenance": {"source_type": "human_authored", "license": "Apache-2.0", "created_at": "2026-08-13"},
        }

    def _build_payload(self) -> dict:
        token_ids = [0, 1, 2]
        token_inputs = [{"token_id": i, "token_piece": str(i), "is_special": False} for i in token_ids]
        token_inputs[-1]["is_special"] = True
        return {
            "token_inputs": token_inputs,
            "token_ids": token_ids,
            "attention_mask": [[1] * len(token_ids)],
            "resid_post_layer_0": torch.tensor(
                [[[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8], [0.9, 1.0, 1.1, 1.2]]]
            ),
            "resid_post_layer_1": torch.tensor(
                [[[1.1, 1.2, 1.3, 1.4], [1.5, 1.6, 1.7, 1.8], [1.9, 2.0, 2.1, 2.2]]]
            ),
            "resid_post_layer_0_topk": [{"token_id": 1}],
        }

    def _write_required_model_files(self, directory: Path) -> None:
        for filename in lab01_acquisition.LAB01_REQUIRED_FILES:
            (directory / filename).write_text(f"{filename}", encoding="utf-8")

    def test_canonical_prompt_build(self) -> None:
        case = self._build_case("case_001")
        case["solution"] = "Apply segmentation boundaries."
        payload = extractor._canonical_prompt(case)
        self.assertIn("Problem:\nCase case_001: reduce heat", payload)
        self.assertIn("Constraints:\nlow_cost; high_reliability", payload)
        self.assertIn("Solution:", payload)

    def test_selects_last_non_special_attended_token(self) -> None:
        case_payload = {
            "token_inputs": [{"is_special": True}, {"is_special": False}, {"is_special": True}, {"is_special": False}],
            "attention_mask": [[1, 1, 0, 1]],
        }
        index = extractor._select_last_attended_non_special_token(case_payload)
        self.assertEqual(index, 3)

    @unittest.skipIf(torch is None, "torch dependency is unavailable in this environment")
    def test_canonical_vector_hash_uses_metadata_and_bytes(self) -> None:
        vector = torch.tensor([0.1, 0.2, 0.3], dtype=torch.float32)
        digest, meta, _ = extractor._tensor_payload_hash(vector)
        expected = self._hash_canonical_tensor(vector)
        self.assertEqual(meta["shape"], [3])
        self.assertEqual(digest, expected)

    @unittest.skipIf(torch is None, "torch dependency is unavailable in this environment")
    def test_run_emits_safetensors_and_relative_index(self) -> None:
        payload = self._build_payload()
        adapter = _FakeAdapter(payload)

        with tempfile.TemporaryDirectory() as workdir:
            model_root = Path(workdir) / "pythia"
            model_root.mkdir(parents=True)
            self._write_required_model_files(model_root)

            old_hf = os.environ.get("HF_HUB_OFFLINE")
            old_tx = os.environ.get("TRANSFORMERS_OFFLINE")
            os.environ.pop("HF_HUB_OFFLINE", None)
            os.environ.pop("TRANSFORMERS_OFFLINE", None)

            try:
                cases_path = Path(workdir) / "cases.jsonl"
                with cases_path.open("w", encoding="utf-8") as fp:
                    fp.write(json.dumps(self._build_case("case_alpha"), ensure_ascii=False))
                    fp.write("\n")
                    fp.write(json.dumps(self._build_case("case_beta"), ensure_ascii=False))
                    fp.write("\n")

                cases_sha = extractor._sha256_path(cases_path)
                artifacts = extractor.run_extractor(
                    cases_path=cases_path,
                    model_root=model_root,
                    output_dir=Path(workdir) / "out",
                    adapter_factory=lambda **_: adapter,
                    identity_verifier=lambda _root: (True, []),
                    created_at="2026-08-13T12:34:56Z",
                )

                self.assertTrue(artifacts.tensors_path.is_file())
                self.assertTrue(artifacts.index_path.is_file())
                self.assertTrue(artifacts.summary_path.is_file())

                rows = [json.loads(line) for line in artifacts.index_path.read_text(encoding="utf-8").splitlines() if line]
                self.assertEqual(len(rows), 4)
                for row in rows:
                    self.assertEqual(row["artifact_uri"], artifacts.tensors_path.name)
                    self.assertEqual(row["source"]["path"], artifacts.tensors_path.name)
                    self.assertEqual(row["source"]["kind"], "instrumented_model_run")
                    self.assertFalse(row["artifact_uri"].startswith("/"))
                    self.assertEqual(row["record_id"], row["tensor_key"])
                    self.assertTrue(row["vector_sha256"])
                    self.assertEqual(row["representation_type"], "model_activation")
                    self.assertEqual(row["tokenizer"]["name_or_path"], lab01_acquisition.LAB01_MODEL_ID)
                    self.assertEqual(len(row["tokenizer"]["files"]["tokenizer.json"]), 64)
                    self.assertEqual(len(row["tokenizer"]["fingerprint"]), 64)

                summary = json.loads(artifacts.summary_path.read_text(encoding="utf-8"))
                self.assertEqual(summary["artifact_class"], "model-backed-representation")
                self.assertEqual(summary["empirical"], True)
                self.assertEqual(summary["evidence_eligible"], False)
                self.assertEqual(summary["non_claim_boundary"]["evidence_eligible"], False)
                self.assertEqual(summary["output_artifacts"]["tensors"]["records"], 4)
                self.assertEqual(summary["created_at"], "2026-08-13T12:34:56Z")
                self.assertEqual(summary["run_timestamp_utc"], "2026-08-13T12:34:56Z")
                self.assertEqual(summary["cases_sha256"], cases_sha)
                self.assertTrue(summary["tokenizer"]["fingerprint"])
            finally:
                if old_hf is None:
                    os.environ.pop("HF_HUB_OFFLINE", None)
                else:
                    os.environ["HF_HUB_OFFLINE"] = old_hf
                if old_tx is None:
                    os.environ.pop("TRANSFORMERS_OFFLINE", None)
                else:
                    os.environ["TRANSFORMERS_OFFLINE"] = old_tx

    def test_run_requires_run_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            model_root = Path(workdir) / "pythia"
            model_root.mkdir(parents=True)
            self._write_required_model_files(model_root)

            cases_path = Path(workdir) / "cases.jsonl"
            cases_path.write_text(json.dumps(self._build_case("case_alpha"), ensure_ascii=False) + "\n", encoding="utf-8")

            config_path = Path(workdir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "config_version": "v1",
                        "cases_path": "cases.jsonl",
                        "model_root": "pythia",
                        "model": {
                            "id": lab01_acquisition.LAB01_MODEL_ID,
                            "revision": lab01_acquisition.LAB01_MODEL_REVISION,
                        },
                        "output_dir": "out",
                        "prompt_template": extractor.DEFAULT_TEMPLATE,
                        "activation_site": "resid_post",
                        "token_policy": "last_non_special_token",
                        "non_claim_boundary": {
                            "empirical": True,
                            "evidence_eligible": False,
                            "claim_ids": [],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(extractor.RepresentationExtractorError):
                extractor.run_from_config(
                    config_path,
                    adapter_factory=lambda **kwargs: _FakeAdapter(self._build_payload()),
                    identity_verifier=lambda _root: (True, []),
                )

    def test_run_refuses_nonempty_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            model_root = Path(workdir) / "pythia"
            model_root.mkdir(parents=True)
            self._write_required_model_files(model_root)

            output_dir = Path(workdir) / "out"
            output_dir.mkdir()
            (output_dir / "legacy.txt").write_text("legacy", encoding="utf-8")

            cases_path = Path(workdir) / "cases.jsonl"
            cases_path.write_text(json.dumps(self._build_case("case_alpha"), ensure_ascii=False) + "\n", encoding="utf-8")

            with self.assertRaises(extractor.RepresentationExtractorError):
                extractor.run_extractor(
                    cases_path=cases_path,
                    model_root=model_root,
                    output_dir=output_dir,
                    adapter_factory=lambda **_: _FakeAdapter(self._build_payload()),
                    identity_verifier=lambda _root: (True, []),
                    created_at="2026-08-13T12:34:56Z",
                )

    @unittest.skipIf(torch is None, "torch dependency is unavailable in this environment")
    def test_relative_paths_in_config_are_from_config_location(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            workdir_path = Path(workdir)
            model_root = workdir_path / "models" / "pythia"
            model_root.mkdir(parents=True)
            self._write_required_model_files(model_root)

            (workdir_path / "cases.jsonl").write_text(
                json.dumps(self._build_case("case_alpha"), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            exp_dir = workdir_path / "experiments"
            exp_dir.mkdir()
            config_path = exp_dir / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "config_version": "v1",
                        "cases_path": "../cases.jsonl",
                        "model_root": "../models/pythia",
                        "model": {
                            "id": lab01_acquisition.LAB01_MODEL_ID,
                            "revision": lab01_acquisition.LAB01_MODEL_REVISION,
                        },
                        "output_dir": "results",
                        "run_timestamp_utc": "2026-08-13T12:34:56Z",
                        "prompt_template": extractor.DEFAULT_TEMPLATE,
                        "activation_site": "resid_post",
                        "token_policy": "last_non_special_token",
                        "non_claim_boundary": {
                            "empirical": True,
                            "evidence_eligible": False,
                            "claim_ids": [],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            artifacts = extractor.run_from_config(
                config_path,
                adapter_factory=lambda **kwargs: _FakeAdapter(self._build_payload()),
                identity_verifier=lambda _root: (True, []),
            )
            self.assertEqual(artifacts.summary_path.parent, (exp_dir / "results").resolve())


if __name__ == "__main__":
    unittest.main()
