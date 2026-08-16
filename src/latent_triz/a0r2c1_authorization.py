"""Fail-closed contract and operator authorization for A0-R2-C1."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .validator import validate


class A0R2C1AuthorizationError(RuntimeError):
    """Raised before any corrective material access when a binding is absent."""


CONTRACT_PATH = Path("experiments/a0r2c1-tokenizer-correction/contract.json")
AUTHORIZATION_PATH = Path("results/a0r2c1/preexecution/sealed-execution-authorization.json")
CONTRACT_SCHEMA_PATH = Path("schemas/a0r2c1-correction-contract.schema.json")
AUTHORIZATION_SCHEMA_PATH = Path("schemas/a0r2c1-sealed-execution-authorization.schema.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R2C1AuthorizationError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise A0R2C1AuthorizationError(f"{label} must be an object")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise A0R2C1AuthorizationError(message)


def _safe_file(root: Path, value: Any, label: str) -> Path:
    relative = Path(str(value))
    _require(not relative.is_absolute() and ".." not in relative.parts, f"{label} path escapes repository")
    path = (root / relative).resolve()
    _require(path.is_relative_to(root) and path.is_file(), f"{label} missing")
    return path


def verify_a0r2c1_contract(root: str | Path) -> dict[str, Any]:
    """Verify the corrective pre-output contract without model or target access."""

    repository = Path(root).resolve()
    contract_path = repository / CONTRACT_PATH
    contract = _json(contract_path, "corrective contract")
    schema = _json(repository / CONTRACT_SCHEMA_PATH, "corrective contract schema")
    _require(not validate(contract, schema), "corrective contract schema validation failed")
    _require(contract.get("contract_status") == "approval_requested", "corrective contract status drift")
    _require(contract.get("operator_approval_granted") is False, "contract must not imply authorization")

    predecessor = contract.get("predecessor")
    _require(isinstance(predecessor, Mapping), "predecessor bindings missing")
    for field in (
        "study_protocol",
        "terminal_failure",
        "publication_manifest",
        "tokenizer_compatibility",
    ):
        binding = predecessor.get(field)
        _require(isinstance(binding, Mapping), f"predecessor binding missing: {field}")
        path = _safe_file(repository, binding.get("path"), field)
        _require(binding.get("sha256") == _sha256(path), f"predecessor hash mismatch: {field}")

    failure = _json(repository / str(predecessor["terminal_failure"]["path"]), "terminal failure")
    _require(failure.get("status") == "failed", "predecessor is not terminal failed")
    access = failure.get("access")
    _require(isinstance(access, Mapping), "predecessor access record missing")
    _require(access.get("sealed_targets_accessed") == "not_accessed", "sealed target eligibility was consumed")

    compatibility = _json(
        repository / str(predecessor["tokenizer_compatibility"]["path"]),
        "tokenizer compatibility",
    )
    _require(compatibility.get("status") == "pass", "tokenizer compatibility did not pass")
    observation = compatibility.get("observation")
    _require(isinstance(observation, Mapping), "tokenizer compatibility observation missing")
    _require(observation.get("is_mapping") is True, "tokenizer is not a Mapping")
    _require(observation.get("is_dict") is False, "tokenizer correction is not demonstrated")
    compatibility_access = compatibility.get("access")
    _require(isinstance(compatibility_access, Mapping), "tokenizer compatibility access missing")
    _require(compatibility_access.get("model_loaded") is False, "compatibility probe loaded model")
    _require(
        compatibility_access.get("sealed_targets_accessed") is False,
        "compatibility probe accessed sealed targets",
    )

    code = contract.get("implementation_code")
    _require(isinstance(code, list) and code, "corrective implementation binding missing")
    for item in code:
        _require(isinstance(item, Mapping), "corrective implementation entry malformed")
        path = _safe_file(repository, item.get("path"), "corrective implementation")
        _require(item.get("sha256") == _sha256(path), f"corrective code hash mismatch: {item.get('path')}")
        _require(item.get("size") == path.stat().st_size, f"corrective code size mismatch: {item.get('path')}")

    return {
        "artifact_class": "a0r2c1-contract-verification",
        "status": "pass",
        "model_output_accessed": False,
        "sealed_targets_accessed": False,
        "code_files_verified": len(code),
    }


def verify_a0r2c1_authorization(
    root: str | Path,
    authorization_path: str | Path | None = None,
) -> dict[str, Any]:
    """Require the exact new authorization before the single corrective run."""

    repository = Path(root).resolve()
    verify_a0r2c1_contract(repository)
    receipt_path = Path(authorization_path) if authorization_path is not None else repository / AUTHORIZATION_PATH
    if not receipt_path.is_absolute():
        receipt_path = repository / receipt_path
    receipt_path = receipt_path.resolve()
    _require(receipt_path.is_relative_to(repository), "authorization receipt path escapes repository")
    receipt = _json(receipt_path, "corrective authorization receipt")
    schema = _json(repository / AUTHORIZATION_SCHEMA_PATH, "corrective authorization schema")
    _require(not validate(receipt, schema), "corrective authorization schema validation failed")
    _require(receipt.get("receipt_status") == "authorized", "corrective execution is not authorized")
    bindings = receipt.get("bindings")
    _require(isinstance(bindings, Mapping), "corrective authorization bindings missing")
    _require(bindings.get("contract_sha256") == _sha256(repository / CONTRACT_PATH), "authorization contract hash mismatch")
    return {
        "artifact_class": "a0r2c1-authorization-verification",
        "status": "pass",
        "model_output_accessed": False,
        "sealed_targets_accessed": False,
    }
