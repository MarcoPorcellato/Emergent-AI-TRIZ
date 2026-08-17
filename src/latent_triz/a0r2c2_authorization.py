"""Fail-closed C2 contract and operator authorization verification."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .validator import validate


class A0R2C2AuthorizationError(RuntimeError):
    """Raised before any C2 material access when a binding is absent or drifts."""


CONTRACT_PATH = Path("experiments/a0r2c2-shape-correction/contract.json")
AUTHORIZATION_PATH = Path("results/a0r2c2/preexecution/sealed-execution-authorization.json")
CONTRACT_SCHEMA_PATH = Path("schemas/a0r2c2-correction-contract.schema.json")
AUTHORIZATION_SCHEMA_PATH = Path("schemas/a0r2c2-sealed-execution-authorization.schema.json")


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
        raise A0R2C2AuthorizationError(f"cannot read {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise A0R2C2AuthorizationError(f"{label} must be an object")
    return payload


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise A0R2C2AuthorizationError(message)


def _safe_file(root: Path, value: Any, label: str) -> Path:
    relative = Path(str(value))
    _require(not relative.is_absolute() and ".." not in relative.parts, f"{label} path escapes repository")
    path = (root / relative).resolve()
    _require(path.is_relative_to(root) and path.is_file(), f"{label} missing")
    return path


def verify_a0r2c2_contract(root: str | Path) -> dict[str, Any]:
    """Verify the C2 pre-output contract without model or target access."""

    repository = Path(root).resolve()
    contract = _json(repository / CONTRACT_PATH, "C2 corrective contract")
    schema = _json(repository / CONTRACT_SCHEMA_PATH, "C2 corrective contract schema")
    _require(not validate(contract, schema), "C2 corrective contract schema validation failed")
    _require(contract.get("contract_status") == "approval_requested", "C2 contract status drift")
    _require(contract.get("operator_approval_granted") is False, "C2 contract must not imply authorization")

    predecessor = contract.get("predecessor")
    _require(isinstance(predecessor, Mapping), "C2 predecessor bindings missing")
    for field in ("study_protocol", "c1_terminal_failure", "c1_publication_manifest"):
        binding = predecessor.get(field)
        _require(isinstance(binding, Mapping), f"C2 predecessor binding missing: {field}")
        path = _safe_file(repository, binding.get("path"), field)
        _require(binding.get("sha256") == _sha256(path), f"C2 predecessor hash mismatch: {field}")

    failure = _json(repository / str(predecessor["c1_terminal_failure"]["path"]), "C1 terminal failure")
    _require(failure.get("status") == "failed", "C1 predecessor is not terminal failed")
    _require(failure.get("access", {}).get("sealed_targets_accessed") == "not_accessed", "C1 target eligibility was consumed")

    code = contract.get("implementation_code")
    _require(isinstance(code, list) and len(code) == 3, "C2 implementation binding missing")
    for item in code:
        _require(isinstance(item, Mapping), "C2 implementation entry malformed")
        path = _safe_file(repository, item.get("path"), "C2 implementation")
        _require(item.get("sha256") == _sha256(path), f"C2 code hash mismatch: {item.get('path')}")
        _require(item.get("size") == path.stat().st_size, f"C2 code size mismatch: {item.get('path')}")

    return {"artifact_class": "a0r2c2-contract-verification", "status": "pass", "model_output_accessed": False, "sealed_targets_accessed": False}


def verify_a0r2c2_authorization(root: str | Path, authorization_path: str | Path | None = None) -> dict[str, Any]:
    """Require the exact C2 authorization before its one material attempt."""

    repository = Path(root).resolve()
    verify_a0r2c2_contract(repository)
    receipt_path = Path(authorization_path) if authorization_path is not None else repository / AUTHORIZATION_PATH
    if not receipt_path.is_absolute():
        receipt_path = repository / receipt_path
    receipt_path = receipt_path.resolve()
    _require(receipt_path.is_relative_to(repository), "C2 authorization receipt path escapes repository")
    receipt = _json(receipt_path, "C2 authorization receipt")
    schema = _json(repository / AUTHORIZATION_SCHEMA_PATH, "C2 authorization schema")
    _require(not validate(receipt, schema), "C2 authorization schema validation failed")
    _require(receipt.get("receipt_status") == "authorized", "C2 execution is not authorized")
    bindings = receipt.get("bindings")
    _require(isinstance(bindings, Mapping), "C2 authorization bindings missing")
    _require(bindings.get("contract_sha256") == _sha256(repository / CONTRACT_PATH), "C2 authorization contract hash mismatch")
    return {"artifact_class": "a0r2c2-authorization-verification", "status": "pass", "model_output_accessed": False, "sealed_targets_accessed": False}
