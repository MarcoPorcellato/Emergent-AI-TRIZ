"""Fail-closed pre-output verification for the A0-R1 execution contract."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import lab01_acquisition


class A0R1ExecutionError(RuntimeError):
    """Raised when R1.4a is not safe to advance to model execution."""


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
        raise A0R1ExecutionError(f"cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise A0R1ExecutionError(f"{label} must be an object")
    return payload


def _safe_path(root: Path, relative: str, label: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise A0R1ExecutionError(f"{label} path escapes repository: {relative}")
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise A0R1ExecutionError(f"{label} file is missing or escapes repository: {relative}")
    return resolved


def verify_a0r1_execution_contract(
    root: str | Path,
    implementation_path: str | Path | None = None,
) -> dict[str, Any]:
    repository = Path(root).resolve()
    implementation_file = (
        Path(implementation_path).resolve()
        if implementation_path is not None
        else repository / "experiments/a0r1-independent-proxy/implementation.json"
    )
    implementation = _json(implementation_file, "implementation contract")
    if implementation.get("status") != "frozen_before_model_output":
        raise A0R1ExecutionError("implementation contract is not frozen before model output")
    if implementation.get("model_output_accessed") is not False or implementation.get("sealed_model_output_accessed") is not False:
        raise A0R1ExecutionError("implementation contract records forbidden model-output access")

    protocol_binding = implementation.get("protocol")
    if not isinstance(protocol_binding, Mapping):
        raise A0R1ExecutionError("implementation protocol binding is missing")
    tracked = {
        "frozen_protocol_sha256": repository / "experiments/a0r1-independent-proxy/protocol.json",
        "freeze_manifest_sha256": repository / "results/a0r1/freeze/freeze-manifest.json",
        "corpus_manifest_sha256": repository / "data/a0r1/manifest.json",
        "cases_sha256": repository / "data/a0r1/cases.jsonl",
        "shortcuts_sha256": repository / "results/a0r1/preoutput/shortcuts.json",
    }
    for field, path in tracked.items():
        if protocol_binding.get(field) != _sha256(path):
            raise A0R1ExecutionError(f"tracked input hash mismatch: {field}")

    freeze = _json(tracked["freeze_manifest_sha256"], "freeze manifest")
    corpus = _json(tracked["corpus_manifest_sha256"], "corpus manifest")
    if freeze.get("status") != "frozen" or freeze.get("protocol_status") != "frozen":
        raise A0R1ExecutionError("freeze manifest is not frozen")
    if freeze.get("model_output_accessed") is not False or freeze.get("sealed_model_output_accessed") is not False:
        raise A0R1ExecutionError("freeze manifest records forbidden output access")
    sealed_hash = protocol_binding.get("sealed_targets_sha256")
    if sealed_hash != freeze.get("sealed_targets_sha256"):
        raise A0R1ExecutionError("sealed target hash differs from freeze manifest")
    files = corpus.get("files")
    if not isinstance(files, Mapping):
        raise A0R1ExecutionError("corpus file manifest is missing")
    sealed_entry = files.get("sealed_targets_jsonl")
    if not isinstance(sealed_entry, Mapping) or sealed_entry.get("sha256") != sealed_hash:
        raise A0R1ExecutionError("sealed target hash differs from corpus manifest")

    runtime = implementation.get("runtime")
    if not isinstance(runtime, Mapping):
        raise A0R1ExecutionError("runtime binding is missing")
    runtime_items = runtime.get("model_runtime_hashes")
    if not isinstance(runtime_items, list) or len(runtime_items) != len(lab01_acquisition.LAB01_REQUIRED_FILES):
        raise A0R1ExecutionError("runtime binding must cover every required file")
    observed_runtime: dict[str, str] = {}
    for item in runtime_items:
        if not isinstance(item, Mapping):
            raise A0R1ExecutionError("runtime binding entry is malformed")
        name = Path(str(item.get("path", ""))).name
        if not name or name in observed_runtime or not isinstance(item.get("size"), int) or item["size"] <= 0:
            raise A0R1ExecutionError("runtime binding entry is missing, duplicated, or empty")
        observed_runtime[name] = str(item.get("sha256", ""))
    if observed_runtime != lab01_acquisition.LAB01_EXPECTED_SHA256:
        raise A0R1ExecutionError("runtime hashes differ from the exact cached revision contract")

    code = implementation.get("implementation_code")
    if not isinstance(code, Mapping) or code.get("binding_state") != "bound" or code.get("pending_code_binding") != []:
        raise A0R1ExecutionError("implementation code binding is not complete")
    bound_files = code.get("bound_code_files")
    if not isinstance(bound_files, list) or not bound_files:
        raise A0R1ExecutionError("implementation code binding is empty")
    verified_code = 0
    for entry in bound_files:
        if not isinstance(entry, Mapping):
            raise A0R1ExecutionError("implementation code entry is malformed")
        path = _safe_path(repository, str(entry.get("path", "")), "implementation code")
        if entry.get("sha256") != _sha256(path) or entry.get("size") != path.stat().st_size:
            raise A0R1ExecutionError(f"implementation code receipt mismatch: {entry.get('path')}")
        verified_code += 1

    return {
        "artifact_class": "a0-r1-execution-contract-verification",
        "protocol_id": implementation.get("protocol_id"),
        "protocol_status": "frozen",
        "status": "pass",
        "tracked_inputs_verified": len(tracked) + 1,
        "runtime_files_bound": len(observed_runtime),
        "code_files_verified": verified_code,
        "model_output_accessed": False,
        "sealed_model_output_accessed": False,
        "empirical": True,
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
    }
