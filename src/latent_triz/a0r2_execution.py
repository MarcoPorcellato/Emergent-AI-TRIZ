"""Fail-closed verification for the frozen A0-R2 execution contract."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .validator import validate


class A0R2ExecutionError(RuntimeError):
    """Raised when R2 is not safe to advance to model or target access."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R2ExecutionError(f"cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise A0R2ExecutionError(f"{label} must be an object")
    return payload


def _safe_file(root: Path, value: Any, label: str) -> Path:
    relative = Path(str(value))
    if relative.is_absolute() or ".." in relative.parts:
        raise A0R2ExecutionError(f"{label} path escapes repository")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise A0R2ExecutionError(f"{label} file missing or outside repository")
    return path


def _runtime_entries(payload: Any, *, label: str) -> dict[str, tuple[str, int]]:
    if not isinstance(payload, list) or len(payload) != 9:
        raise A0R2ExecutionError(f"{label} must bind exactly nine runtime files")
    result: dict[str, tuple[str, int]] = {}
    for item in payload:
        if not isinstance(item, Mapping):
            raise A0R2ExecutionError(f"{label} contains a malformed entry")
        name = str(item.get("name") or item.get("path") or "")
        if Path(name).name != name or not name or name in result:
            raise A0R2ExecutionError(f"{label} contains an invalid or duplicate path")
        sha = str(item.get("sha256", ""))
        size = item.get("size")
        if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
            raise A0R2ExecutionError(f"{label} contains an invalid digest")
        if not isinstance(size, int) or size <= 0:
            raise A0R2ExecutionError(f"{label} contains an invalid size")
        result[name] = (sha, size)
    return result


def verify_a0r2_execution_contract(
    root: str | Path,
    implementation_path: str | Path | None = None,
    *,
    model_root: str | Path | None = None,
) -> dict[str, Any]:
    """Verify every pre-output binding without importing model libraries."""

    repository = Path(root).resolve()
    implementation_file = (
        Path(implementation_path).resolve()
        if implementation_path is not None
        else repository / "experiments/a0r2-independent-model/implementation.json"
    )
    implementation = _json(implementation_file, "implementation contract")
    schema = _json(repository / "schemas/a0r2-implementation.schema.json", "implementation schema")
    issues = validate(implementation, schema)
    if issues:
        raise A0R2ExecutionError("implementation schema validation failed")
    if implementation.get("status") != "frozen_before_model_output":
        raise A0R2ExecutionError("implementation is not frozen before model output")
    access = implementation.get("access")
    if not isinstance(access, Mapping) or any(access.get(key) is not False for key in (
        "model_loaded", "model_output_accessed", "sealed_targets_accessed"
    )):
        raise A0R2ExecutionError("implementation records forbidden pre-output access")

    protocol_path = repository / "experiments/a0r2-independent-model/study-protocol.json"
    integrity_path = repository / "results/a0r2/preexecution/smollm2-360m-f8027fd0/integrity-receipt.json"
    feasibility_path = repository / "results/a0r2/preexecution/smollm2-360m-f8027fd0/feasibility-receipt.json"
    protocol = _json(protocol_path, "study protocol")
    integrity = _json(integrity_path, "integrity receipt")
    feasibility = _json(feasibility_path, "feasibility receipt")

    bindings = implementation.get("bindings")
    if not isinstance(bindings, Mapping):
        raise A0R2ExecutionError("implementation bindings missing")
    expected_bindings = {
        "study_protocol_sha256": _sha256(protocol_path),
        "integrity_receipt_sha256": _sha256(integrity_path),
        "feasibility_receipt_sha256": _sha256(feasibility_path),
    }
    for field, expected in expected_bindings.items():
        if bindings.get(field) != expected:
            raise A0R2ExecutionError(f"binding mismatch: {field}")

    cross_model = implementation.get("descriptive_cross_model")
    if not isinstance(cross_model, Mapping):
        raise A0R2ExecutionError("descriptive cross-model contract missing")
    if cross_model.get("enabled") is not True or cross_model.get("may_affect_primary") is not False:
        raise A0R2ExecutionError("descriptive cross-model boundary drift")
    r1_result_path = _safe_file(repository, cross_model.get("r1_result_path"), "R1 result")
    if cross_model.get("r1_result_sha256") != _sha256(r1_result_path):
        raise A0R2ExecutionError("R1 descriptive comparison binding mismatch")

    if protocol.get("protocol_status") != "frozen" or protocol.get("approval_required") is not True:
        raise A0R2ExecutionError("study protocol is not frozen and approval-gated")
    authorization = protocol.get("authorization")
    if not isinstance(authorization, Mapping) or authorization.get("sealed_target_access") != "approval_required":
        raise A0R2ExecutionError("sealed-target approval boundary drift")
    if integrity.get("status") != "pass" or integrity.get("integrity_status") != "integrity_verified":
        raise A0R2ExecutionError("model integrity receipt is not verified")
    if feasibility.get("status") != "compatible" or feasibility.get("compatibility", {}).get("compatible") is not True:
        raise A0R2ExecutionError("model feasibility receipt is not compatible")

    model = implementation.get("model")
    for payload, label in ((protocol.get("model"), "protocol"), (integrity.get("model"), "integrity"), (feasibility.get("model"), "feasibility")):
        if not isinstance(payload, Mapping) or not isinstance(model, Mapping):
            raise A0R2ExecutionError(f"{label} model identity missing")
        for key in ("id", "revision"):
            if payload.get(key) != model.get(key):
                raise A0R2ExecutionError(f"{label} model identity mismatch: {key}")

    receipt_runtime = _runtime_entries(integrity.get("runtime_files"), label="integrity runtime")
    contract_runtime = _runtime_entries(implementation.get("runtime_files"), label="implementation runtime")
    if contract_runtime != receipt_runtime:
        raise A0R2ExecutionError("runtime file contract differs from integrity receipt")
    if model_root is not None:
        snapshot = Path(model_root).resolve()
        observed: dict[str, tuple[str, int]] = {}
        for name, expected in receipt_runtime.items():
            path = snapshot / name
            if not path.is_file():
                raise A0R2ExecutionError(f"runtime file missing: {name}")
            observed[name] = (_sha256(path), path.stat().st_size)
            if observed[name] != expected:
                raise A0R2ExecutionError(f"runtime file mismatch: {name}")
        extras = sorted(path.name for path in snapshot.iterdir() if path.is_file() and path.name not in receipt_runtime)
        if extras:
            raise A0R2ExecutionError("runtime snapshot contains undeclared files")

    code = implementation.get("implementation_code")
    if not isinstance(code, Mapping) or code.get("binding_state") != "bound" or code.get("pending_code_binding") != []:
        raise A0R2ExecutionError("implementation code binding incomplete")
    bound = code.get("bound_code_files")
    if not isinstance(bound, list) or not bound:
        raise A0R2ExecutionError("implementation code binding empty")
    verified = 0
    for item in bound:
        if not isinstance(item, Mapping):
            raise A0R2ExecutionError("implementation code entry malformed")
        path = _safe_file(repository, item.get("path"), "implementation code")
        if item.get("sha256") != _sha256(path) or item.get("size") != path.stat().st_size:
            raise A0R2ExecutionError(f"implementation code receipt mismatch: {item.get('path')}")
        verified += 1

    return {
        "artifact_class": "a0r2-execution-contract-verification",
        "status": "pass",
        "protocol_id": protocol.get("protocol_id"),
        "runtime_files_verified": len(receipt_runtime) if model_root is not None else 0,
        "runtime_files_bound": len(receipt_runtime),
        "code_files_verified": verified,
        "model_output_accessed": False,
        "sealed_targets_accessed": False,
        "empirical": True,
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
    }
