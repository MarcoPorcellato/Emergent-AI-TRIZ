from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz import a0r1_runner
from latent_triz.a0r1_runner import main


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_json_sha256(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return _sha256_bytes(text.encode("utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _copy_schemas(root: Path) -> None:
    schema_root = Path(__file__).resolve().parents[1] / "schemas"
    destination = root / "schemas"
    if destination.exists():
        return
    destination.mkdir(parents=True, exist_ok=True)
    for name in (
        "a0r1-activation-receipt.schema.json",
        "a0r1-statistical-result.schema.json",
        "a0r1-run-failure.schema.json",
    ):
        _write_json(destination / name, json.loads((schema_root / name).read_text(encoding="utf-8")))


def _base_schema_payload() -> str:
    return "0" * 64


def _fixture_base(root: Path, run_id: str) -> None:
    _copy_schemas(root)
    (root / "experiments" / "a0r1-independent-proxy").mkdir(parents=True, exist_ok=True)
    (root / "results" / "a0r1" / "freeze").mkdir(parents=True, exist_ok=True)
    (root / "results" / "a0r1" / "preoutput").mkdir(parents=True, exist_ok=True)
    (root / "results" / "a0r1" / run_id).mkdir(parents=True, exist_ok=True)
    (root / "data" / "a0r1").mkdir(parents=True, exist_ok=True)

    protocol = {
        "protocol_id": "a0-r1-tier-r1-v1.0",
        "protocol_status": "frozen",
        "status": "frozen",
    }
    implementation = {
        "protocol_id": "a0-r1-tier-r1-v1.0",
        "protocol_status": "frozen",
        "status": "frozen_before_model_output",
        "protocol": {},
    }
    _write_json(root / "experiments" / "a0r1-independent-proxy" / "protocol.json", protocol)
    _write_json(root / "experiments" / "a0r1-independent-proxy" / "implementation.json", implementation)

    shortcuts_payload = {"artifact_class": "a0r1-shortcuts", "status": "pass"}
    shortcuts_path = root / "results" / "a0r1" / "preoutput" / "shortcuts.json"
    shortcuts_path.write_text(json.dumps(shortcuts_payload), encoding="utf-8")
    _write_json(
        root / "results" / "a0r1" / "preoutput" / "preoutput-manifest.json",
        {"artifacts": {"shortcuts.json": {"sha256": _sha256_path(shortcuts_path)}}},
    )

    sealed_targets = root / "data" / "a0r1" / "sealed_targets.jsonl"
    sealed_targets.write_text("{\"case\": 1}\n", encoding="utf-8")
    sealed_targets_sha256 = _sha256_path(sealed_targets)
    _write_json(
        root / "data" / "a0r1" / "manifest.json",
        {
            "files": {
                "sealed_targets_jsonl": {
                    "path": "sealed_targets.jsonl",
                    "sha256": sealed_targets_sha256,
                    "size": sealed_targets.stat().st_size,
                }
            }
        },
    )
    implementation["protocol"]["sealed_targets_sha256"] = sealed_targets_sha256
    _write_json(root / "experiments" / "a0r1-independent-proxy" / "implementation.json", implementation)
    _write_json(
        root / "results" / "a0r1" / "freeze" / "freeze-manifest.json",
        {"sealed_targets_sha256": sealed_targets_sha256},
    )


def _write_valid_activation_receipt(root: Path, run_id: str) -> Path:
    artifacts_dir = root / "artifacts" / "a0r1" / run_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    index_path = artifacts_dir / "representations-index.jsonl"
    dense_path = artifacts_dir / "activations.json"
    index_path.write_text("{\"record_id\":1}\n", encoding="utf-8")
    dense_payload = [ {"vectors": [1, 2, 3]} ]
    dense_path.write_text(json.dumps(dense_payload), encoding="utf-8")

    protocol_hash = _sha256_path(root / "experiments" / "a0r1-independent-proxy" / "protocol.json")
    implementation_hash = _sha256_path(root / "experiments" / "a0r1-independent-proxy" / "implementation.json")

    manifest = {
        "artifact_class": "a0r1-activation-receipt",
        "empirical": True,
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "status": "pass",
        "created_at": "2026-08-15T00:00:00Z",
        "protocol": {
            "id": "a0-r1-tier-r1-v1.0",
            "protocol_status": "frozen",
            "hash": protocol_hash,
            "snapshot_hash": _base_schema_payload(),
        },
        "implementation": {
            "protocol_status": "frozen",
            "status": "frozen_before_model_output",
            "hash": implementation_hash,
        },
        "freeze": {
            "protocol_status": "frozen",
            "status": "frozen",
            "protocol_id": "a0-r1-tier-r1-v1.0",
            "hash": _base_schema_payload(),
        },
        "corpus": {
            "manifest_sha256": _base_schema_payload(),
            "cases_sha256": _base_schema_payload(),
            "sealed_targets_sha256": _sha256_path(root / "data" / "a0r1" / "sealed_targets.jsonl"),
            "sealed_targets_accessed": False,
            "selected_cases": 48,
        },
        "runtime": {
            "model": "EleutherAI/pythia-70m-deduped",
            "revision": "e93a9faa9c77e5d09219f6c868bfc7a1bd65593c",
            "files": [
                {"name": "a", "sha256": _base_schema_payload(), "size": 10},
                {"name": "b", "sha256": _base_schema_payload(), "size": 10},
                {"name": "c", "sha256": _base_schema_payload(), "size": 10},
                {"name": "d", "sha256": _base_schema_payload(), "size": 10},
                {"name": "e", "sha256": _base_schema_payload(), "size": 10},
                {"name": "f", "sha256": _base_schema_payload(), "size": 10},
            ],
            "binding_hash": _base_schema_payload(),
        },
        "primary_contract": {
            "primary_view": "problem_plus_transformation",
            "primary_token_site": "mean_transformation_span",
            "primary_layer": 6,
            "baseline_view": "problem_only",
            "baseline_token_sites": ["sentinel"],
            "multiplicity": 1,
        },
        "sealed_target_semantics_accessed": False,
        "model_output_accessed": True,
        "sealed_model_output_accessed": True,
        "records": 96,
        "dense_vectors": {
            "path": "activations.json",
            "sha256": _sha256_path(dense_path),
            "format": "json-vectors",
            "bytes": dense_path.stat().st_size,
        },
        "representation_index": {
            "path": "representations-index.jsonl",
            "sha256": _sha256_path(index_path),
        },
    }
    path = artifacts_dir / "activation-receipt.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _write_valid_result(root: Path, run_id: str) -> Path:
    shortcut = _sha256_path(root / "results" / "a0r1" / "preoutput" / "shortcuts.json")
    artifact_dir = root / "artifacts" / "a0r1" / run_id
    index_path = artifact_dir / "representations-index.jsonl"
    dense_path = artifact_dir / "activations.json"
    receipt_path = artifact_dir / "activation-receipt.json"

    payload = {
        "artifact_class": "a0r1-analytical-result",
        "empirical": True,
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "status": "positive",
        "protocol_id": "a0-r1-tier-r1-v1.0",
        "protocol_status": "frozen",
        "analysis_type": "fixed_primary",
        "sealing_rule": "sealed_targets_opened_once_at_boundary",
        "shortcut_status": "pass",
        "input_hashes": {
            "protocol": _canonical_json_sha256(root / "experiments" / "a0r1-independent-proxy" / "protocol.json"),
            "implementation": _sha256_path(root / "experiments" / "a0r1-independent-proxy" / "implementation.json"),
            "shortcut": shortcut,
            "activation_receipt": _sha256_path(receipt_path),
            "representation_index": _sha256_path(index_path),
            "dense_vectors": _sha256_path(dense_path),
            "sealed_targets": _sha256_path(root / "data" / "a0r1" / "sealed_targets.jsonl"),
        },
        "design": {
            "cases": 48,
            "families": 24,
            "domains": 6,
            "layer": 6,
            "token_site": "mean_transformation_span",
            "primary_view": "problem_plus_transformation",
            "surface_view": "problem_only",
            "surface_site": "sentinel",
            "permutation_budget": 999,
            "seed": 20260815,
            "critical_successes": 17,
            "required_domain_directions": 4,
        },
        "primary": {
            "family_successes": 17,
            "scores": [],
            "macro_f1": 1.0,
            "family_success_rate": 0.7,
            "per_domain_accuracy": {
                "agriculture": 1.0,
                "energy": 1.0,
                "manufacturing": 1.0,
                "medicine": 1.0,
                "software": 1.0,
                "transport": 1.0,
            },
            "domain_direction_successes": {"agriculture": 1.0},
        },
        "surface_baseline": {
            "family_successes": 0,
            "scores": [],
            "macro_f1": 0.5,
            "family_success_rate": 0.0,
            "per_domain_accuracy": {
                "agriculture": 0.5,
                "energy": 0.5,
                "manufacturing": 0.5,
                "medicine": 0.5,
                "software": 0.5,
                "transport": 0.5,
            },
            "domain_direction_successes": {},
        },
        "macro_f1_margin_over_surface": 0.5,
        "max_family_successes_observed": 24,
        "domain_direction_successes": {"agriculture": 1.0},
        "domain_direction_success_count": 4,
        "primary_permutation_p": 0.001,
        "permutation_seed": 20260815,
        "permutation_budget": 999,
        "null_maxima": {
            "minimum": 1,
            "median": 2,
            "maximum": 3,
            "sha256": _base_schema_payload(),
        },
        "sensitivity": {
            "problem_plus_transformation": {
                "combos": {},
                "paired_direction_delta_mean": 0.0,
                "rescues_primary": False,
            }
        },
        "outcome_rule": {
            "max_statistic_p_at_most": 0.05,
            "macro_f1_margin_at_least": 0.1,
            "family_successes_at_least": 17,
            "domain_direction_successes_minimum": 4,
        },
        "outcome_deterministic": True,
        "model_output_accessed": True,
        "sealed_model_output_accessed": True,
        "sealed_targets_accessed": True,
        "primary_is_max_statistic_selection": False,
        "outcome_description": "all good",
        "non_interpretable_reason": None,
    }
    path = root / "results" / "a0r1" / run_id / "statistical-result.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class A0R1RunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.execution_contract = patch(
            "latent_triz.a0r1_runner.verify_a0r1_execution_contract",
            return_value={"status": "pass"},
        )
        self.execution_contract.start()

    def tearDown(self) -> None:
        self.execution_contract.stop()

    def test_target_discovery_does_not_open_sealed_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture_base(root, "runsealed")
            with patch("latent_triz.a0r1_runner._sha256", side_effect=AssertionError("sealed content opened")):
                path, declared_hash = a0r1_runner._discover_targets_path(root)
            self.assertEqual((root / "data/a0r1/sealed_targets.jsonl").resolve(), path)
            self.assertEqual(
                json.loads((root / "data/a0r1/manifest.json").read_text())["files"]["sealed_targets_jsonl"]["sha256"],
                declared_hash,
            )

    def test_all_stage_runs_activation_then_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "runok"
            _fixture_base(root, run_id)

            activation_dir = root / "artifacts" / "a0r1" / run_id
            dense = activation_dir / "activations.json"

            calls: list[str] = []

            def _activate(*args, **kwargs):  # noqa: ANN001
                del kwargs
                calls.append("activate")
                return SimpleNamespace(dense_path=dense)

            def _analyze(*args, **kwargs):  # noqa: ANN001
                del kwargs
                calls.append("analyze")
                _ = args

            with (
                patch("latent_triz.a0r1_runner.run_a0r1_activations", side_effect=_activate) as mock_activate,
                patch("latent_triz.a0r1_runner.analyze_a0r1", side_effect=_analyze),
            ):
                mock_activate.return_value = SimpleNamespace(dense_path=dense)

                status = main([
                    "--root",
                    str(root),
                    "--model-root",
                    "models",
                    "--run-id",
                    run_id,
                    "--created-at",
                    "2026-08-15T00:00:00Z",
                    "--stage",
                    "all",
                ])

                self.assertEqual(0, status)
                self.assertEqual(["activate", "analyze"], calls)

                kwargs = mock_activate.call_args.kwargs
                expected_root = root.resolve()
                self.assertEqual(
                    expected_root / "experiments" / "a0r1-independent-proxy" / "protocol.json",
                    kwargs["protocol_path"],
                )
                self.assertEqual(
                    expected_root / "experiments" / "a0r1-independent-proxy" / "implementation.json",
                    kwargs["implementation_path"],
                )
                self.assertEqual(
                    expected_root / "results" / "a0r1" / "freeze" / "freeze-manifest.json",
                    kwargs["freeze_path"],
                )
                self.assertEqual(expected_root / "data" / "a0r1", kwargs["corpus_dir"])
                self.assertEqual(Path("models"), kwargs["model_root"])
                self.assertEqual(expected_root / "artifacts" / "a0r1" / run_id, kwargs["output_dir"])

    def test_execution_contract_failure_blocks_model_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "runcontract"
            _fixture_base(root, run_id)

            with (
                patch(
                    "latent_triz.a0r1_runner.verify_a0r1_execution_contract",
                    side_effect=RuntimeError("contract drift"),
                ),
                patch("latent_triz.a0r1_runner.run_a0r1_activations") as mock_activate,
            ):
                status = main([
                    "--root",
                    str(root),
                    "--model-root",
                    "models",
                    "--run-id",
                    run_id,
                    "--created-at",
                    "2026-08-15T00:00:00Z",
                    "--stage",
                    "activate",
                ])

            self.assertNotEqual(0, status)
            mock_activate.assert_not_called()

    def test_shortcut_failure_blocks_model_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "runshortcut"
            _fixture_base(root, run_id)
            shortcut_path = root / "results" / "a0r1" / "preoutput" / "shortcuts.json"
            shortcut_payload = json.loads(shortcut_path.read_text(encoding="utf-8"))
            shortcut_payload["status"] = "failed"
            shortcut_path.write_text(json.dumps(shortcut_payload), encoding="utf-8")
            manifest_path = root / "results" / "a0r1" / "preoutput" / "preoutput-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"]["shortcuts.json"]["sha256"] = _sha256_path(shortcut_path)
            _write_json(manifest_path, manifest)

            with patch("latent_triz.a0r1_runner.run_a0r1_activations") as mock_activate:
                status = main([
                    "--root",
                    str(root),
                    "--model-root",
                    "models",
                    "--run-id",
                    run_id,
                    "--created-at",
                    "2026-08-15T00:00:00Z",
                    "--stage",
                    "activate",
                ])

            self.assertNotEqual(0, status)
            mock_activate.assert_not_called()

    def test_analyze_shortcuts_hash_mismatch_refuses_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "runshort"
            _fixture_base(root, run_id)

            # break shortcut hash to ensure the runner refuses execution before calling analyze_a0r1
            manifest = json.loads((root / "results" / "a0r1" / "preoutput" / "preoutput-manifest.json").read_text())
            manifest["artifacts"]["shortcuts.json"]["sha256"] = "00" * 32
            _write_json(root / "results" / "a0r1" / "preoutput" / "preoutput-manifest.json", manifest)

            with patch("latent_triz.a0r1_runner.analyze_a0r1") as mock_analyze:
                status = main([
                    "--root",
                    str(root),
                    "--model-root",
                    "models",
                    "--run-id",
                    run_id,
                    "--created-at",
                    "2026-08-15T00:00:00Z",
                    "--stage",
                    "analyze",
                ])
                self.assertNotEqual(0, status)
                mock_analyze.assert_not_called()

    def test_targets_path_escape_in_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "runtrg"
            _fixture_base(root, run_id)
            manifest = json.loads((root / "data" / "a0r1" / "manifest.json").read_text())
            manifest["files"]["sealed_targets_jsonl"]["path"] = "../outside.jsonl"
            _write_json(root / "data" / "a0r1" / "manifest.json", manifest)

            with patch("latent_triz.a0r1_runner.analyze_a0r1") as mock_analyze:
                status = main([
                    "--root",
                    str(root),
                    "--model-root",
                    "models",
                    "--run-id",
                    run_id,
                    "--created-at",
                    "2026-08-15T00:00:00Z",
                    "--stage",
                    "analyze",
                ])
                self.assertNotEqual(0, status)
                mock_analyze.assert_not_called()

    def test_run_id_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _fixture_base(root, "runok")
            with patch("latent_triz.a0r1_runner.run_a0r1_activations"):
                status = main([
                    "--root",
                    str(root),
                    "--model-root",
                    "models",
                    "--run-id",
                    "BadID",
                    "--created-at",
                    "2026-08-15T00:00:00Z",
                    "--stage",
                    "activate",
                ])
                self.assertNotEqual(0, status)
                status = main([
                    "--root",
                    str(root),
                    "--model-root",
                    "models",
                    "--run-id",
                    "freeze",
                    "--created-at",
                    "2026-08-15T00:00:00Z",
                    "--stage",
                    "activate",
                ])
                self.assertNotEqual(0, status)

    def test_overwrite_refused_when_activation_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "runover"
            _fixture_base(root, run_id)
            (root / "artifacts" / "a0r1" / run_id).mkdir(parents=True, exist_ok=True)

            with patch("latent_triz.a0r1_runner.run_a0r1_activations") as mock_activate:
                status = main([
                    "--root",
                    str(root),
                    "--model-root",
                    "models",
                    "--run-id",
                    run_id,
                    "--created-at",
                    "2026-08-15T00:00:00Z",
                    "--stage",
                    "activate",
                ])
                self.assertNotEqual(0, status)
                mock_activate.assert_not_called()

    def test_verify_schema_and_hash_drift_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "runverify"
            _fixture_base(root, run_id)
            _copy_schemas(root)
            _write_valid_activation_receipt(root, run_id)
            _write_valid_result(root, run_id)

            status = main([
                "--root",
                str(root),
                "--model-root",
                "models",
                "--run-id",
                run_id,
                "--created-at",
                "2026-08-15T00:00:00Z",
                "--stage",
                "verify",
            ])
            self.assertEqual(0, status)

            result_path = root / "results" / "a0r1" / run_id / "statistical-result.json"
            result_payload = json.loads(result_path.read_text(encoding="utf-8"))
            result_payload["input_hashes"]["protocol"] = "0" * 64
            result_path.write_text(json.dumps(result_payload), encoding="utf-8")

            status = main([
                "--root",
                str(root),
                "--model-root",
                "models",
                "--run-id",
                run_id,
                "--created-at",
                "2026-08-15T00:00:00Z",
                "--stage",
                "verify",
            ])
            self.assertNotEqual(0, status)

    def test_analysis_exception_leads_to_clean_failure_no_fabrication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "runerr"
            _fixture_base(root, run_id)

            with patch("latent_triz.a0r1_runner.analyze_a0r1", side_effect=RuntimeError("boom")) as mock_analyze:
                status = main([
                    "--root",
                    str(root),
                    "--model-root",
                    "models",
                    "--run-id",
                    run_id,
                    "--created-at",
                    "2026-08-15T00:00:00Z",
                    "--stage",
                    "analyze",
                ])
                self.assertNotEqual(0, status)
                mock_analyze.assert_called_once()

            result_path = root / "results" / "a0r1" / run_id / "statistical-result.json"
            self.assertFalse(result_path.is_file())

    def test_preflight_failure_generates_run_failure_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "runpre"
            _fixture_base(root, run_id)

            with patch("latent_triz.a0r1_runner.verify_a0r1_execution_contract", side_effect=RuntimeError("preflight failed")):
                status = main([
                    "--root",
                    str(root),
                    "--model-root",
                    "models",
                    "--run-id",
                    run_id,
                    "--created-at",
                    "2026-08-15T00:00:00Z",
                    "--stage",
                    "analyze",
                ])

            self.assertNotEqual(0, status)
            failure = json.loads((root / "results" / "a0r1" / run_id / "run-failure.json").read_text(encoding="utf-8"))
            self.assertEqual("preflight", failure["stage"])
            self.assertEqual(
                {
                    "model_output": "not_accessed",
                    "sealed_model_output": "not_accessed",
                    "sealed_targets": "not_accessed",
                },
                {k: failure[k] for k in ["model_output", "sealed_model_output", "sealed_targets"]},
            )
            self.assertFalse((root / "results" / "a0r1" / run_id / "statistical-result.json").is_file())

    def test_activation_failure_generates_stage_and_access_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "runact"
            _fixture_base(root, run_id)

            with patch("latent_triz.a0r1_runner.run_a0r1_activations", side_effect=RuntimeError("activation failed")):
                status = main([
                    "--root",
                    str(root),
                    "--model-root",
                    "models",
                    "--run-id",
                    run_id,
                    "--created-at",
                    "2026-08-15T00:00:00Z",
                    "--stage",
                    "activate",
                ])

            self.assertNotEqual(0, status)
            failure = json.loads((root / "results" / "a0r1" / run_id / "run-failure.json").read_text(encoding="utf-8"))
            self.assertEqual("activation", failure["stage"])
            self.assertEqual("possibly_accessed", failure["model_output"])
            self.assertEqual("possibly_accessed", failure["sealed_model_output"])
            self.assertEqual("not_accessed", failure["sealed_targets"])

    def test_analysis_failure_generates_run_failure_not_statistical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "runerr"
            _fixture_base(root, run_id)

            with patch("latent_triz.a0r1_runner.analyze_a0r1", side_effect=RuntimeError("boom")):
                status = main([
                    "--root",
                    str(root),
                    "--model-root",
                    "models",
                    "--run-id",
                    run_id,
                    "--created-at",
                    "2026-08-15T00:00:00Z",
                    "--stage",
                    "analyze",
                ])
                self.assertNotEqual(0, status)

            failure_path = root / "results" / "a0r1" / run_id / "run-failure.json"
            result_path = root / "results" / "a0r1" / run_id / "statistical-result.json"
            self.assertFalse(result_path.is_file())
            self.assertTrue(failure_path.is_file())

            failure = json.loads(failure_path.read_text(encoding="utf-8"))
            self.assertEqual("analysis", failure["stage"])
            self.assertEqual("possibly_accessed", failure["model_output"])
            self.assertEqual("possibly_accessed", failure["sealed_targets"])

            _copy_schemas(root)
            failure_schema = a0r1_runner._read_json(root / "schemas" / "a0r1-run-failure.schema.json", "failure schema")
            self.assertEqual([], a0r1_runner.validate(failure, failure_schema))

    def test_failure_receipt_refuse_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "runrw"
            _fixture_base(root, run_id)
            _copy_schemas(root)
            failure_path = root / "results" / "a0r1" / run_id / "run-failure.json"
            failure_path.parent.mkdir(parents=True, exist_ok=True)
            failure_path.write_text("{}", encoding="utf-8")

            with patch("latent_triz.a0r1_runner.analyze_a0r1", side_effect=RuntimeError("boom")):
                status = main([
                    "--root",
                    str(root),
                    "--model-root",
                    "models",
                    "--run-id",
                    run_id,
                    "--created-at",
                    "2026-08-15T00:00:00Z",
                    "--stage",
                    "analyze",
                ])

            self.assertNotEqual(0, status)
            self.assertEqual("{}", failure_path.read_text(encoding="utf-8").strip())

    def test_no_sealed_target_content_hashing_in_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "runhash"
            _fixture_base(root, run_id)
            _write_valid_activation_receipt(root, run_id)

            with patch("latent_triz.a0r1_runner._sha256") as mock_sha256:
                hashed_paths: list[str] = []

                def _fake_sha256(path: Path) -> str:
                    hashed_paths.append(str(path))
                    return _sha256_path(path)

                mock_sha256.side_effect = _fake_sha256

                with patch("latent_triz.a0r1_runner.analyze_a0r1", side_effect=RuntimeError("boom")):
                    status = main([
                        "--root",
                        str(root),
                        "--model-root",
                        "models",
                        "--run-id",
                        run_id,
                        "--created-at",
                        "2026-08-15T00:00:00Z",
                        "--stage",
                        "analyze",
                    ])
                self.assertNotEqual(0, status)
                self.assertFalse(any(path.endswith("/sealed_targets.jsonl") for path in hashed_paths))


if __name__ == "__main__":
    unittest.main()
