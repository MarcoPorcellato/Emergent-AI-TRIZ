"""Fail-closed C3 analysis-only contract and authorization verification."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .validator import validate


class A0R2C3AuthorizationError(RuntimeError):
    """Raised before any C3 target access when an exact binding is absent."""


CONTRACT_PATH = Path("experiments/a0r2c3-analysis-only-recovery/contract.json")
AUTHORIZATION_PATH = Path("results/a0r2c3/preexecution/analysis-authorization.json")
CONTRACT_SCHEMA_PATH = Path("schemas/a0r2c3-analysis-contract.schema.json")
AUTHORIZATION_SCHEMA_PATH = Path("schemas/a0r2c3-analysis-authorization.schema.json")


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
        raise A0R2C3AuthorizationError(f"cannot read {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise A0R2C3AuthorizationError(f"{label} must be an object")
    return payload


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise A0R2C3AuthorizationError(message)


def _safe_file(root: Path, value: Any, label: str) -> Path:
    relative = Path(str(value))
    _require(not relative.is_absolute() and ".." not in relative.parts, f"{label} path escapes repository")
    path = (root / relative).resolve()
    _require(path.is_relative_to(root) and path.is_file(), f"{label} missing")
    return path


def verify_a0r2c3_contract(root: str | Path) -> dict[str, Any]:
    """Verify C3 bindings without importing a model or reading target content."""

    repository = Path(root).resolve()
    contract = _json(repository / CONTRACT_PATH, "C3 analysis contract")
    schema = _json(repository / CONTRACT_SCHEMA_PATH, "C3 analysis contract schema")
    _require(not validate(contract, schema), "C3 analysis contract schema validation failed")
    _require(contract.get("contract_status") == "approval_requested", "C3 contract status drift")
    _require(contract.get("operator_approval_granted") is False, "C3 contract must not imply authorization")

    predecessor = contract.get("predecessor")
    _require(isinstance(predecessor, Mapping), "C3 predecessor bindings missing")
    for field in ("study_protocol", "c2_failure", "c2_activation_receipt", "c2_representation_index", "c2_publication_manifest"):
        binding = predecessor.get(field)
        _require(isinstance(binding, Mapping), f"C3 predecessor binding missing: {field}")
        path = _safe_file(repository, binding.get("path"), field)
        _require(binding.get("sha256") == _sha256(path), f"C3 predecessor hash mismatch: {field}")
        _require(binding.get("size") == path.stat().st_size, f"C3 predecessor size mismatch: {field}")

    failure = _json(repository / str(predecessor["c2_failure"]["path"]), "C2 terminal failure")
    _require(failure.get("status") == "failed", "C2 predecessor is not terminal failed")
    _require(failure.get("failure", {}).get("failure_digest") == contract["correction"]["failure_digest"], "C2 failure digest drift")

    receipt = _json(repository / str(predecessor["c2_activation_receipt"]["path"]), "C2 activation receipt")
    _require(receipt.get("runtime", {}).get("torch_dtype") == "float32", "C2 runtime dtype drift")
    _require(receipt.get("output_bundle", {}).get("artifact_hashes", {}).get("index_sha256") == predecessor["c2_representation_index"]["sha256"], "C2 index binding drift")

    code = contract.get("implementation_code")
    _require(isinstance(code, list) and code, "C3 implementation binding missing")
    for item in code:
        _require(isinstance(item, Mapping), "C3 implementation entry malformed")
        path = _safe_file(repository, item.get("path"), "C3 implementation")
        _require(item.get("sha256") == _sha256(path), f"C3 code hash mismatch: {item.get('path')}")
        _require(item.get("size") == path.stat().st_size, f"C3 code size mismatch: {item.get('path')}")

    return {"artifact_class": "a0r2c3-contract-verification", "status": "pass", "model_output_accessed": False, "sealed_targets_accessed": False}


def verify_a0r2c3_authorization(root: str | Path, authorization_path: str | Path | None = None) -> dict[str, Any]:
    """Require the exact C3 analysis-only authorization before one target read."""

    repository = Path(root).resolve()
    verify_a0r2c3_contract(repository)
    receipt_path = Path(authorization_path) if authorization_path is not None else repository / AUTHORIZATION_PATH
    if not receipt_path.is_absolute():
        receipt_path = repository / receipt_path
    receipt_path = receipt_path.resolve()
    _require(receipt_path.is_relative_to(repository), "C3 authorization receipt path escapes repository")
    receipt = _json(receipt_path, "C3 authorization receipt")
    schema = _json(repository / AUTHORIZATION_SCHEMA_PATH, "C3 authorization schema")
    _require(not validate(receipt, schema), "C3 authorization schema validation failed")
    _require(receipt.get("receipt_status") == "authorized", "C3 analysis is not authorized")
    bindings = receipt.get("bindings")
    _require(isinstance(bindings, Mapping), "C3 authorization bindings missing")
    _require(bindings.get("contract_sha256") == _sha256(repository / CONTRACT_PATH), "C3 authorization contract hash mismatch")
    return {"artifact_class": "a0r2c3-authorization-verification", "status": "pass", "model_output_accessed": False, "sealed_targets_accessed": False}
