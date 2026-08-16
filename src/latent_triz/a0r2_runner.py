"""Deterministic command-line orchestration for A0-R2 sealed runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import resource
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .a0r2_activations import run_a0r2_activations
from .a0r2_analysis import analyze_a0r2
from .a0r2_execution import verify_a0r2_execution_contract
from .a0r2_report import (
    ACTIVATION_RECEIPT_FILE,
    MANIFEST_FILE,
    REPORT_FILE,
    REPRESENTATION_INDEX_FILE,
    RESULT_FAILURE_FILE,
    RESULT_STATISTICAL_FILE,
    generate_a0r2_report,
    verify_a0r2_publication,
)
from .validator import validate


class A0R2RunnerError(RuntimeError):
    """Raised when an A0-R2 runner stage cannot be executed safely."""


class A0R2IncompatibleError(A0R2RunnerError):
    """Raised when the frozen runtime envelope is incompatible with execution."""


ARTIFACTS_DIR = Path("artifacts") / "a0r2"
RESULTS_DIR = Path("results") / "a0r2"
PROTOCOL_PATH = Path("experiments") / "a0r2-independent-model" / "study-protocol.json"
IMPLEMENTATION_PATH = Path("experiments") / "a0r2-independent-model" / "implementation.json"
RUN_FAILURE_FILE_NAME = RESULT_FAILURE_FILE
STAGE_CHOICES = ("activate", "analyze", "verify", "all")
_RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")

_MODEL = {
    "id": "HuggingFaceTB/SmolLM2-360M",
    "revision": "f8027fd0eaeea54caa13c31d31b9fdc459c38b49",
    "license_id": "Apache-2.0",
    "model_type": "llama",
    "architecture": "LlamaForCausalLM",
    "num_hidden_layers": 32,
    "hidden_size": 960,
    "local_locator": "artifacts/models/smollm2-360m-f8027fd0",
}


@dataclass(frozen=True)
class A0R2RunnerArtifacts:
    activation_dir: Path
    package_dir: Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic A0-R2 activation + analysis stages")
    parser.add_argument("--root", default=".")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--stage", choices=STAGE_CHOICES, default="all")
    parser.add_argument("--model-root", default=None)
    return parser


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise A0R2RunnerError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R2RunnerError(f"cannot read {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise A0R2RunnerError(f"{label} must be an object")
    return payload


def _validate_run_id(value: str) -> None:
    if not _RUN_ID_RE.match(value):
        raise A0R2RunnerError("run-id must match regex ^[a-z0-9][a-z0-9._-]{0,79}$")


def _read_schema(root: Path, name: str) -> dict[str, Any]:
    return _read_json(root / "schemas" / name, f"schema {name}")


def _sync_file(src: Path, dst: Path) -> None:
    if dst.exists():
        if _sha256(src) != _sha256(dst):
            raise A0R2RunnerError(f"refusing to overwrite existing file: {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    if _sha256(src) != _sha256(dst):
        raise A0R2RunnerError(f"copied file hash mismatch: {dst}")


def _sync_activation_package(activation_dir: Path, package_dir: Path) -> None:
    _require(activation_dir.is_dir(), f"activation directory missing: {activation_dir}")
    package_dir.mkdir(parents=True, exist_ok=True)
    for name in (ACTIVATION_RECEIPT_FILE, REPRESENTATION_INDEX_FILE):
        _sync_file(activation_dir / name, package_dir / name)


def _shortcut_audit_path(root: Path) -> Path:
    path = root / "results" / "a0r1" / "preoutput" / "shortcuts.json"
    if not path.is_file():
        raise A0R2RunnerError(f"shortcuts artifact missing: {path}")
    return path


def _validate_shortcuts(root: Path) -> Path:
    shortcut_path = _shortcut_audit_path(root)
    shortcuts = _read_json(shortcut_path, "shortcut audit")
    if shortcuts.get("status") != "pass":
        raise A0R2RunnerError("shortcut gate must pass before model access")
    return shortcut_path


def _failure_access(stage: str) -> dict[str, str]:
    if stage in {"identity", "compatibility"}:
        return {
            "model_output_accessed": "not_accessed",
            "sealed_targets_accessed": "not_accessed",
        }
    if stage == "execution":
        return {
            "model_output_accessed": "possibly_accessed",
            "sealed_targets_accessed": "not_accessed",
        }
    return {
        "model_output_accessed": "possibly_accessed",
        "sealed_targets_accessed": "possibly_accessed",
    }


def _failure_model_loaded(stage: str) -> bool:
    return stage not in {"identity", "compatibility"}


def _failure_payload(*, stage: str, created_at: str, exc: Exception) -> dict[str, Any]:
    access = _failure_access(stage)
    return {
        "artifact_class": "a0r2-run-failure",
        "status": "incompatible" if isinstance(exc, A0R2IncompatibleError) else "failed",
        "created_at": created_at,
        "scientific_status": "exploratory",
        "empirical": True,
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "protocol_id": "a0r2-independent-model-v1.0.0",
        "model": dict(_MODEL),
        "failure": {
            "stage": stage,
            "failure_kind": type(exc).__name__,
            "failure_digest": _sha256_text(str(exc)),
        },
        "access": {
            "model_loaded": _failure_model_loaded(stage),
            "model_output_accessed": access["model_output_accessed"],
            "sealed_targets_accessed": access["sealed_targets_accessed"],
            "claim_promotion": False,
        },
        "reports": ["report.md"],
    }


def _write_failure(root: Path, run_id: str, payload: dict[str, Any]) -> None:
    result_dir = root / RESULTS_DIR / run_id
    result_dir.mkdir(parents=True, exist_ok=True)
    failure_path = result_dir / RUN_FAILURE_FILE_NAME
    if failure_path.is_file():
        raise A0R2RunnerError(f"run-failure already exists: {failure_path}")

    schema = _read_schema(root, "a0r2-run-failure.schema.json")
    if validate(payload, schema):
        raise A0R2RunnerError("failure payload does not validate schema")

    serialised = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
    with tempfile.NamedTemporaryFile("w", dir=result_dir, delete=False, encoding="utf-8", suffix=".tmp") as handle:
        handle.write(serialised)
        tmp_path = Path(handle.name)

    try:
        os.link(tmp_path, failure_path)
    except Exception as exc:  # pragma: no cover
        raise A0R2RunnerError(f"cannot atomically persist failure receipt: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)


def _record_failure(root: Path, run_id: str, stage: str, created_at: str, exc: Exception) -> None:
    result_path = root / RESULTS_DIR / run_id / RESULT_STATISTICAL_FILE
    if result_path.is_file():
        return
    payload = _failure_payload(stage=stage, created_at=created_at, exc=exc)
    _write_failure(root, run_id, payload)


def _best_effort_failure_publication(root: Path, run_id: str, created_at: str) -> None:
    package_dir = root / RESULTS_DIR / run_id
    failure_path = package_dir / RESULT_FAILURE_FILE
    if not failure_path.is_file():
        return

    report_path = package_dir / REPORT_FILE
    manifest_path = package_dir / MANIFEST_FILE
    external_dense_dir = root / ARTIFACTS_DIR / run_id
    try:
        if not report_path.is_file() and not manifest_path.is_file():
            generate_a0r2_report(
                package_dir=package_dir.relative_to(root),
                external_dense_dir=external_dense_dir.relative_to(root),
                created_at=created_at,
            )
        verify_a0r2_publication(
            package_dir=package_dir.relative_to(root),
            external_dense_dir=external_dense_dir.relative_to(root),
        )
    except Exception:
        return


def _artifacts(root: Path, run_id: str) -> A0R2RunnerArtifacts:
    return A0R2RunnerArtifacts(
        activation_dir=root / ARTIFACTS_DIR / run_id,
        package_dir=root / RESULTS_DIR / run_id,
    )


def _run_activate(root: Path, args: argparse.Namespace, *, shortcut_path: Path) -> A0R2RunnerArtifacts:
    artifacts = _artifacts(root, args.run_id)
    if artifacts.activation_dir.exists():
        raise A0R2RunnerError(f"activation would overwrite existing path: {artifacts.activation_dir}")

    run_a0r2_activations(
        protocol_path=root / PROTOCOL_PATH,
        model_root=Path(args.model_root),
        output_dir=artifacts.activation_dir,
        created_at=args.created_at,
    )
    _sync_activation_package(artifacts.activation_dir, artifacts.package_dir)
    _require(shortcut_path.is_file(), "shortcut audit missing")
    return artifacts


def _peak_rss_bytes() -> int:
    observed = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return observed if sys.platform == "darwin" else observed * 1024


def _enforce_resource_envelope(root: Path, artifacts: A0R2RunnerArtifacts, *, started_at: float) -> None:
    protocol = _read_json(root / PROTOCOL_PATH, "study protocol")
    envelope = protocol.get("resource_envelope")
    if not isinstance(envelope, Mapping):
        raise A0R2RunnerError("resource envelope missing")
    wall_seconds = time.monotonic() - started_at
    dense_path = artifacts.activation_dir / "activations.json"
    checks = (
        (wall_seconds <= float(envelope["maximum_wall_seconds"]), "wall-time envelope exceeded"),
        (_peak_rss_bytes() <= int(envelope["maximum_peak_rss_bytes"]), "peak-RSS envelope exceeded"),
        (dense_path.is_file() and dense_path.stat().st_size <= int(envelope["maximum_new_dense_output_bytes"]), "dense-output envelope exceeded"),
    )
    for passed, message in checks:
        if not passed:
            raise A0R2IncompatibleError(message)


def _run_analyze(root: Path, args: argparse.Namespace, artifacts: A0R2RunnerArtifacts, *, shortcut_path: Path) -> None:
    package_result = artifacts.package_dir / RESULT_STATISTICAL_FILE
    if package_result.exists():
        raise A0R2RunnerError(f"analysis would overwrite existing path: {package_result}")

    _sync_activation_package(artifacts.activation_dir, artifacts.package_dir)
    targets_path = _discover_targets_path(root)
    analyze_a0r2(
        protocol_path=root / PROTOCOL_PATH,
        activation_receipt_path=artifacts.package_dir / ACTIVATION_RECEIPT_FILE,
        activation_index_path=artifacts.package_dir / REPRESENTATION_INDEX_FILE,
        dense_path=artifacts.activation_dir / "activations.json",
        targets_path=targets_path,
        output_path=package_result,
        shortcut_path=shortcut_path,
    )


def _run_verify(root: Path, args: argparse.Namespace, artifacts: A0R2RunnerArtifacts) -> None:
    _sync_activation_package(artifacts.activation_dir, artifacts.package_dir)
    report_path = artifacts.package_dir / REPORT_FILE
    manifest_path = artifacts.package_dir / MANIFEST_FILE
    if not report_path.is_file() and not manifest_path.is_file():
        generate_a0r2_report(
            package_dir=artifacts.package_dir.relative_to(root),
            external_dense_dir=artifacts.activation_dir.relative_to(root),
            created_at=args.created_at,
        )
    verify_a0r2_publication(
        package_dir=artifacts.package_dir.relative_to(root),
        external_dense_dir=artifacts.activation_dir.relative_to(root),
    )


def _discover_targets_path(root: Path) -> Path:
    corpus_manifest = _read_json(root / "data" / "a0r1" / "manifest.json", "a0r1 corpus manifest")
    files = corpus_manifest.get("files")
    if not isinstance(files, Mapping):
        raise A0R2RunnerError("corpus manifest files is not a mapping")
    sealed = files.get("sealed_targets_jsonl")
    if not isinstance(sealed, Mapping):
        raise A0R2RunnerError("corpus manifest missing sealed_targets_jsonl")
    path_value = sealed.get("path")
    if not isinstance(path_value, str) or not path_value:
        raise A0R2RunnerError("sealed target path is missing")
    path = (root / "data" / "a0r1" / path_value).resolve()
    if not path.is_file():
        raise A0R2RunnerError("sealed target artifact is missing")
    return path


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.root).resolve()

    failure_stage = "identity"
    run_id_valid = False
    try:
        run_started_at = time.monotonic()
        _validate_run_id(args.run_id)
        run_id_valid = True
        failure_stage = "compatibility"
        if args.stage in {"activate", "all"}:
            if args.model_root is None:
                raise A0R2RunnerError("--model-root is required for activation")
            verify_a0r2_execution_contract(root, model_root=Path(args.model_root))
        else:
            verify_a0r2_execution_contract(root)

        shortcut_path = _validate_shortcuts(root)

        artifacts = _artifacts(root, args.run_id)

        if args.stage in {"activate", "all"}:
            failure_stage = "execution"
            artifacts = _run_activate(root, args, shortcut_path=shortcut_path)
            _enforce_resource_envelope(root, artifacts, started_at=run_started_at)

        if args.stage in {"analyze", "all"}:
            failure_stage = "data"
            _require(artifacts.activation_dir.is_dir(), "activation artifacts are missing")
            _run_analyze(root, args, artifacts, shortcut_path=shortcut_path)

        if args.stage in {"verify", "all"}:
            failure_stage = "publication"
            _require(artifacts.activation_dir.is_dir(), "activation artifacts are missing")
            _run_verify(root, args, artifacts)

        return 0
    except Exception as exc:
        if run_id_valid:
            try:
                _record_failure(root, args.run_id, failure_stage, args.created_at, exc)
                _best_effort_failure_publication(root, args.run_id, args.created_at)
            except Exception:
                print(f"a0r2-run: FAILED: {exc}")
                print("a0r2-run: FAILED to persist run-failure artifact")
                return 1
        print(f"a0r2-run: FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
