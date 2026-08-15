"""Deterministic command-line orchestration for A0-R1 sealed runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .a0r1_activations import run_a0r1_activations
from .a0r1_analysis import analyze_a0r1
from .a0r1_execution import verify_a0r1_execution_contract
from .validator import validate


class A0R1RunnerError(RuntimeError):
    """Raised when a0r1 runner cannot execute a stage."""


ARTIFACTS_DIR = Path("artifacts") / "a0r1"
RESULTS_DIR = Path("results") / "a0r1"
EXPERIMENT_DIR = Path("experiments") / "a0r1-independent-proxy"
PROTO = EXPERIMENT_DIR / "protocol.json"
IMPL = EXPERIMENT_DIR / "implementation.json"
RUN_FAILURE_FILE = "run-failure.json"
FREEZE_MANIFEST = RESULTS_DIR / "freeze" / "freeze-manifest.json"
CANONICAL_CORPUS = Path("data") / "a0r1" / "manifest.json"
PREOUTPUT_MANIFEST = RESULTS_DIR / "preoutput" / "preoutput-manifest.json"
_RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
_RUN_ID_RESERVED = {"freeze", "preoutput"}


@dataclass(frozen=True)
class A0R1RunnerArtifacts:
    activation_dir: Path
    result_dir: Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic A0-R1 activation + analysis stages")
    parser.add_argument("--root", default=".")
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--stage", choices=("activate", "analyze", "all", "verify"), default="all")
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_sha256(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise A0R1RunnerError(f"cannot canonical-hash non-object json: {path}")
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R1RunnerError(f"cannot read {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise A0R1RunnerError(f"{label} is not an object: {path}")
    return payload


def _validate_run_id(value: str) -> None:
    if not _RUN_ID_RE.match(value):
        raise A0R1RunnerError(
            "run-id must match regex ^[a-z0-9][a-z0-9._-]{0,79}$"
        )
    if value in _RUN_ID_RESERVED:
        raise A0R1RunnerError(f"run-id '{value}' is reserved")


def _coerce_repo_relative(root: Path, value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise A0R1RunnerError(f"{label} is missing")
    rel = Path(value)
    if rel.is_absolute():
        raise A0R1RunnerError(f"{label} must be repository-relative: {value}")
    root_resolved = root.resolve()
    path = (root / rel).resolve()
    if os.path.commonpath([str(path), str(root_resolved)]) != str(root_resolved):
        raise A0R1RunnerError(f"{label} escapes repository root: {value}")
    if ".." in rel.parts:
        raise A0R1RunnerError(f"{label} path cannot contain '..': {value}")
    return path


def _coerce_file_within_base(base: Path, value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise A0R1RunnerError(f"{label} is missing")
    if os.path.isabs(value):
        raise A0R1RunnerError(f"{label} must be relative: {value}")
    rel = Path(value)
    if rel.anchor or ".." in rel.parts:
        raise A0R1RunnerError(f"{label} has invalid traversal: {value}")
    candidate = (base / rel).resolve()
    base_resolved = base.resolve()
    if os.path.commonpath([str(candidate), str(base_resolved)]) != str(base_resolved):
        raise A0R1RunnerError(f"{label} escapes manifest directory: {value}")
    return candidate


def _read_hex(value: Any, *, label: str) -> str:
    if not isinstance(value, str):
        raise A0R1RunnerError(f"{label} is not a sha256 string")
    if len(value) != 64 or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise A0R1RunnerError(f"{label} is not a sha256 digest: {value}")
    return value


def _discover_shortcuts_path(root: Path) -> Path:
    manifest = _read_json(root / PREOUTPUT_MANIFEST, "preoutput manifest")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise A0R1RunnerError("preoutput manifest artifacts is not a mapping")

    path = root / RESULTS_DIR / "preoutput" / "shortcuts.json"
    if not path.is_file():
        raise A0R1RunnerError("shortcuts artifact missing: results/a0r1/preoutput/shortcuts.json")

    direct = artifacts.get("shortcuts.json")
    if not isinstance(direct, Mapping):
        raise A0R1RunnerError("preoutput manifest missing shortcuts.json entry")
    expected = _read_hex(direct.get("sha256"), label="preoutput shortcuts.sha256")
    if _sha256(path) != expected:
        raise A0R1RunnerError("shortcuts artifact hash mismatch")
    return path


def _discover_targets_path(root: Path) -> tuple[Path, str]:
    manifest = _read_json(root / CANONICAL_CORPUS, "a0r1 corpus manifest")
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        raise A0R1RunnerError("corpus manifest files is not a mapping")
    sealed = files.get("sealed_targets_jsonl")
    if not isinstance(sealed, Mapping):
        raise A0R1RunnerError("corpus manifest missing sealed_targets_jsonl")
    path = _coerce_file_within_base(
        root / CANONICAL_CORPUS.parent,
        sealed.get("path"),
        label="sealed target path",
    )
    expected = _read_hex(sealed.get("sha256"), label="sealed target sha256")
    if not path.is_file():
        raise A0R1RunnerError("sealed target artifact is missing")
    implementation = _read_json(root / IMPL, "implementation")
    freeze = _read_json(root / FREEZE_MANIFEST, "freeze manifest")
    implementation_hash = implementation.get("protocol", {}).get("sealed_targets_sha256")
    if implementation_hash != expected or freeze.get("sealed_targets_sha256") != expected:
        raise A0R1RunnerError("sealed target declared hash mismatch across contracts")
    return path, expected


def _read_schema(root: Path, name: str) -> dict[str, Any]:
    return _read_json(root / "schemas" / name, f"schema {name}")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_hash(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    try:
        return _sha256(path)
    except OSError:
        return None


def _coerce_bool_access(value: object, *, fallback: str) -> str:
    if not isinstance(value, bool):
        return fallback
    return "accessed" if value else "not_accessed"


def _coerce_access_from_payload(payload: dict[str, Any], key: str, *, fallback: str) -> str:
    return _coerce_bool_access(payload.get(key), fallback=fallback)


def _collect_input_hashes(root: Path, stage: str, run_id: str) -> dict[str, str | None]:
    protocol_hash: str | None = None
    implementation_hash: str | None = None
    shortcut_hash: str | None = None
    activation_receipt_hash: str | None = None
    representation_index_hash: str | None = None
    dense_hash: str | None = None
    sealed_targets_hash: str | None = None

    try:
        protocol_hash = _canonical_json_sha256(root / PROTO)
    except Exception:
        pass

    implementation_hash = _safe_hash(root / IMPL)

    try:
        if stage != "preflight":
            manifest = _read_json(root / PREOUTPUT_MANIFEST, "preoutput manifest")
            artifacts = manifest.get("artifacts")
            if isinstance(artifacts, Mapping):
                shortcut = artifacts.get("shortcuts.json")
                if isinstance(shortcut, Mapping) and isinstance(shortcut.get("sha256"), str):
                    shortcut_hash = _read_hex(shortcut.get("sha256"), label="shortcuts sha256")
            if shortcut_hash is None:
                shortcut_hash = _safe_hash(root / RESULTS_DIR / "preoutput" / "shortcuts.json")
    except Exception:
        shortcut_hash = None

    artifacts_dir = root / ARTIFACTS_DIR / run_id
    activation_receipt_path = artifacts_dir / "activation-receipt.json"
    activation_receipt_hash = _safe_hash(activation_receipt_path)
    representation_index_hash = _safe_hash(artifacts_dir / "representations-index.jsonl")
    dense_hash = _safe_hash(artifacts_dir / "activations.json")

    try:
        _, sealed_targets_hash = _discover_targets_path(root)
    except A0R1RunnerError:
        sealed_targets_hash = None
    except Exception:
        sealed_targets_hash = None

    return {
        "protocol": protocol_hash,
        "implementation": implementation_hash,
        "shortcut": shortcut_hash,
        "activation_receipt": activation_receipt_hash,
        "representation_index": representation_index_hash,
        "dense_vectors": dense_hash,
        "sealed_targets": sealed_targets_hash,
    }


def _coerce_access_from_result(
    payload: dict[str, Any], *, fallback: str = "possibly_accessed"
) -> dict[str, str]:
    return {
        "model_output": _coerce_access_from_payload(payload, "model_output_accessed", fallback=fallback),
        "sealed_model_output": _coerce_access_from_payload(payload, "sealed_model_output_accessed", fallback=fallback),
        "sealed_targets": _coerce_access_from_payload(payload, "sealed_targets_accessed", fallback=fallback),
    }


def _coerce_access_from_receipt(
    root: Path, run_id: str, *, fallback: str = "possibly_accessed"
) -> dict[str, str] | None:
    try:
        path = root / ARTIFACTS_DIR / run_id / "activation-receipt.json"
        receipt = _read_json(path, "activation receipt")
        schema = _read_schema(root, "a0r1-activation-receipt.schema.json")
        if validate(receipt, schema):
            return None
    except Exception:
        return None

    return {
        "model_output": _coerce_access_from_payload(receipt, "model_output_accessed", fallback=fallback),
        "sealed_model_output": _coerce_access_from_payload(receipt, "sealed_model_output_accessed", fallback=fallback),
        "sealed_targets": _coerce_access_from_payload(receipt, "sealed_targets_accessed", fallback=fallback),
    }


def _access_from_failure_stage(root: Path, run_id: str, stage: str) -> dict[str, str]:
    if stage == "preflight":
        return {
            "model_output": "not_accessed",
            "sealed_model_output": "not_accessed",
            "sealed_targets": "not_accessed",
        }

    if stage == "activation":
        return {
            "model_output": "possibly_accessed",
            "sealed_model_output": "possibly_accessed",
            "sealed_targets": "not_accessed",
        }

    if stage == "analysis":
        access = {
            "model_output": "possibly_accessed",
            "sealed_model_output": "possibly_accessed",
            "sealed_targets": "possibly_accessed",
        }
        receipt = _coerce_access_from_receipt(root, run_id, fallback="possibly_accessed")
        if receipt is None:
            return access
        if receipt.get("model_output") == "accessed" or receipt.get("model_output") == "not_accessed":
            access["model_output"] = receipt["model_output"]
        if receipt.get("sealed_model_output") == "accessed" or receipt.get("sealed_model_output") == "not_accessed":
            access["sealed_model_output"] = receipt["sealed_model_output"]
        return access

    if stage == "verification":
        result_path = root / RESULTS_DIR / run_id / "statistical-result.json"
        if result_path.is_file():
            try:
                result_payload = _read_json(result_path, "analysis result")
                return _coerce_access_from_result(result_payload, fallback="possibly_accessed")
            except Exception:
                pass

        receipt = _coerce_access_from_receipt(root, run_id, fallback="possibly_accessed")
        if receipt is None:
            return {
                "model_output": "possibly_accessed",
                "sealed_model_output": "possibly_accessed",
                "sealed_targets": "possibly_accessed",
            }
        return receipt

    raise A0R1RunnerError(f"unknown failure stage: {stage}")


def _build_failure_payload(
    *, root: Path, run_id: str, stage: str, created_at: str, exc: Exception
) -> dict[str, Any]:
    if stage not in {"preflight", "activation", "analysis", "verification"}:
        raise A0R1RunnerError(f"unknown failure stage: {stage}")

    input_hashes = _collect_input_hashes(root, stage=stage, run_id=run_id)
    access = _access_from_failure_stage(root, run_id, stage)

    return {
        "artifact_class": "a0r1-run-failure",
        "status": "failed",
        "created_at": created_at,
        "run_id": run_id,
        "stage": stage,
        "exception_type": type(exc).__name__,
        "error_message_sha256": _sha256_text(str(exc)),
        "input_hashes": input_hashes,
        "model_output": access["model_output"],
        "sealed_model_output": access["sealed_model_output"],
        "sealed_targets": access["sealed_targets"],
    }


def _write_run_failure(root: Path, run_id: str, payload: dict[str, Any]) -> None:
    result_dir = root / RESULTS_DIR / run_id
    result_dir.mkdir(parents=True, exist_ok=True)
    failure_path = result_dir / RUN_FAILURE_FILE

    if failure_path.is_file():
        raise A0R1RunnerError(f"run-failure already exists: {failure_path}")

    serialised = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ) + "\n"
    with tempfile.NamedTemporaryFile("w", dir=result_dir, delete=False, encoding="utf-8", suffix=".tmp") as handle:
        handle.write(serialised)
        tmp_path = Path(handle.name)

    try:
        os.link(tmp_path, failure_path)
    except Exception as exc:
        raise A0R1RunnerError(f"cannot atomically persist failure receipt: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)


def _record_failure(root: Path, run_id: str, stage: str, created_at: str, exc: Exception) -> None:
    result_path = root / RESULTS_DIR / run_id / "statistical-result.json"
    if result_path.is_file():
        return

    payload = _build_failure_payload(root=root, run_id=run_id, stage=stage, created_at=created_at, exc=exc)
    schema = _read_schema(root, "a0r1-run-failure.schema.json")
    if validate(payload, schema):
        raise A0R1RunnerError("failure payload does not validate schema")
    _write_run_failure(root, run_id, payload)




def _run_activation(root: Path, args: argparse.Namespace) -> A0R1RunnerArtifacts:
    activation_dir = root / ARTIFACTS_DIR / args.run_id
    if activation_dir.exists():
        raise A0R1RunnerError(f"activation would overwrite existing path: {activation_dir}")

    shortcuts = _read_json(_discover_shortcuts_path(root), "shortcuts")
    if shortcuts.get("status") != "pass":
        raise A0R1RunnerError("shortcut gate must pass before model activation")

    artifacts = run_a0r1_activations(
        protocol_path=root / PROTO,
        implementation_path=root / IMPL,
        freeze_path=root / FREEZE_MANIFEST,
        corpus_dir=root / CANONICAL_CORPUS.parent,
        model_root=Path(args.model_root),
        output_dir=activation_dir,
        created_at=args.created_at,
    )

    return A0R1RunnerArtifacts(
        activation_dir=artifacts.dense_path.parent,
        result_dir=root / RESULTS_DIR / args.run_id,
    )


def _run_analysis(root: Path, args: argparse.Namespace, artifacts: A0R1RunnerArtifacts | None) -> None:
    result_path = root / RESULTS_DIR / args.run_id / "statistical-result.json"
    if result_path.exists():
        raise A0R1RunnerError(f"analysis would overwrite existing path: {result_path}")

    if artifacts is None:
        activation_dir = root / ARTIFACTS_DIR / args.run_id
        artifacts = A0R1RunnerArtifacts(
            activation_dir=activation_dir,
            result_dir=root / RESULTS_DIR / args.run_id,
        )

    activation_receipt = artifacts.activation_dir / "activation-receipt.json"
    activation_index = artifacts.activation_dir / "representations-index.jsonl"
    activation_dense = artifacts.activation_dir / "activations.json"
    result_dir = root / RESULTS_DIR / args.run_id

    targets_path, _ = _discover_targets_path(root)
    analyze_a0r1(
        protocol_path=root / PROTO,
        implementation_path=root / IMPL,
        shortcut_path=_discover_shortcuts_path(root),
        activation_receipt_path=activation_receipt,
        activation_index_path=activation_index,
        dense_path=activation_dense,
        targets_path=targets_path,
        output_path=result_dir / "statistical-result.json",
    )


def _run_verify(root: Path, run_id: str) -> None:
    artifacts_dir = root / ARTIFACTS_DIR / run_id
    result_path = root / RESULTS_DIR / run_id / "statistical-result.json"
    activation_receipt_path = artifacts_dir / "activation-receipt.json"
    activation_index_path = artifacts_dir / "representations-index.jsonl"
    activation_dense_path = artifacts_dir / "activations.json"

    for path in (activation_receipt_path, activation_index_path, activation_dense_path, result_path):
        if not path.is_file():
            raise A0R1RunnerError(f"verify requires artifact on disk: {path}")

    activation_receipt = _read_json(activation_receipt_path, "activation receipt")
    result_payload = _read_json(result_path, "analysis result")
    receipt_protocol = activation_receipt.get("protocol")
    if not isinstance(receipt_protocol, Mapping):
        raise A0R1RunnerError("activation receipt protocol is invalid")
    receipt_dense = activation_receipt.get("dense_vectors")
    receipt_index = activation_receipt.get("representation_index")
    if not isinstance(receipt_dense, Mapping) or not isinstance(receipt_index, Mapping):
        raise A0R1RunnerError("activation receipt missing dense/index metadata")

    if not isinstance(receipt_protocol.get("id"), str) or not receipt_protocol.get("id"):
        raise A0R1RunnerError("activation receipt protocol.id is missing")

    dense_name = receipt_dense.get("path")
    if dense_name is None:
        dense_name = receipt_dense.get("locator")
    dense_name = str(dense_name) if dense_name is not None else ""
    index_name = str(receipt_index.get("path", ""))
    dense_path = _coerce_file_within_base(artifacts_dir, dense_name, label="activation receipt dense path")
    index_path = _coerce_file_within_base(artifacts_dir, index_name, label="activation receipt index path")
    if dense_path != activation_dense_path:
        raise A0R1RunnerError("activation receipt dense path mismatch")
    if index_path != activation_index_path:
        raise A0R1RunnerError("activation receipt index path mismatch")
    if receipt_dense.get("sha256") != _sha256(activation_dense_path):
        raise A0R1RunnerError("activation dense hash mismatch")
    if receipt_index.get("sha256") != _sha256(activation_index_path):
        raise A0R1RunnerError("activation index hash mismatch")

    if not isinstance(result_payload.get("protocol_id"), str):
        raise A0R1RunnerError("analysis result missing protocol_id")
    if not isinstance(receipt_protocol.get("hash"), str):
        raise A0R1RunnerError("activation receipt protocol hash missing")
    if receipt_protocol.get("hash") != _sha256(root / PROTO):
        raise A0R1RunnerError("activation receipt protocol file hash mismatch")
    receipt_implementation = activation_receipt.get("implementation")
    if not isinstance(receipt_implementation, Mapping):
        raise A0R1RunnerError("activation receipt implementation is invalid")
    if receipt_implementation.get("hash") != _sha256(root / IMPL):
        raise A0R1RunnerError("activation receipt implementation hash mismatch")
    if result_payload.get("protocol_id") != str(receipt_protocol.get("id", "")):
        raise A0R1RunnerError("protocol id mismatch between result and receipt")

    expected_input_hashes = {
        "protocol": _canonical_json_sha256(root / PROTO),
        "implementation": _sha256(root / IMPL),
        "shortcut": _sha256(_discover_shortcuts_path(root)),
        "activation_receipt": _sha256(activation_receipt_path),
        "representation_index": _sha256(activation_index_path),
        "dense_vectors": _sha256(activation_dense_path),
        "sealed_targets": _discover_targets_path(root)[1],
    }
    receipt_corpus = activation_receipt.get("corpus")
    if not isinstance(receipt_corpus, Mapping):
        raise A0R1RunnerError("activation receipt corpus is invalid")
    if receipt_corpus.get("sealed_targets_sha256") != expected_input_hashes["sealed_targets"]:
        raise A0R1RunnerError("activation receipt sealed target hash mismatch")
    input_hashes = result_payload.get("input_hashes")
    if not isinstance(input_hashes, Mapping):
        raise A0R1RunnerError("analysis result missing input_hashes")
    for key, expected in expected_input_hashes.items():
        if _read_hex(input_hashes.get(key), label=f"result input_hashes.{key}") != expected:
            raise A0R1RunnerError(f"analysis result input_hash {key} mismatch")

    activation_schema = _read_schema(root, "a0r1-activation-receipt.schema.json")
    result_schema = _read_schema(root, "a0r1-statistical-result.schema.json")
    if validate(activation_receipt, activation_schema):
        raise A0R1RunnerError("activation receipt does not validate schema")
    if validate(result_payload, result_schema):
        raise A0R1RunnerError("analysis result does not validate schema")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.root).resolve()

    failure_stage = "preflight"
    run_id_valid = False
    try:
        _validate_run_id(args.run_id)
        run_id_valid = True
        verify_a0r1_execution_contract(root)

        if args.stage in {"activate", "all"}:
            failure_stage = "activation"
            artifacts = _run_activation(root, args)
        elif args.stage in {"analyze", "verify"}:
            artifacts = A0R1RunnerArtifacts(
                activation_dir=root / ARTIFACTS_DIR / args.run_id,
                result_dir=root / RESULTS_DIR / args.run_id,
            )
        else:
            artifacts = None

        if args.stage in {"analyze", "all"}:
            failure_stage = "analysis"
            _run_analysis(root, args, artifacts)
        elif args.stage == "verify":
            failure_stage = "verification"
            _run_verify(root, args.run_id)
        return 0
    except Exception as exc:
        if run_id_valid:
            try:
                _record_failure(
                    root=root,
                    run_id=args.run_id,
                    stage=failure_stage,
                    created_at=args.created_at,
                    exc=exc,
                )
            except Exception:
                print(f"a0r1-run: FAILED: {exc}")
                print(f"a0r1-run: FAILED to persist run-failure artifact")
                return 1
        print(f"a0r1-run: FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
