"""Fail-closed operator-authorization verification for the single A0-R2.3 run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .validator import validate


class A0R2AuthorizationError(RuntimeError):
    """Raised before any material R2.3 access when authorization is incomplete."""


AUTHORIZATION_PATH = Path(
    "results/a0r2/preexecution/smollm2-360m-f8027fd0/sealed-execution-authorization.json"
)
DOSSIER_PATH = Path("experiments/a0r2-independent-model/sealed-execution-approval-dossier.json")
IMPLEMENTATION_PATH = Path("experiments/a0r2-independent-model/implementation.json")
STUDY_PROTOCOL_PATH = Path("experiments/a0r2-independent-model/study-protocol.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R2AuthorizationError(f"cannot read {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise A0R2AuthorizationError(f"{label} must be an object")
    return payload


def _require(value: bool, message: str) -> None:
    if not value:
        raise A0R2AuthorizationError(message)


def verify_a0r2_sealed_execution_authorization(
    root: str | Path,
    authorization_path: str | Path | None = None,
) -> dict[str, Any]:
    """Verify the corrective authorization before model or target access.

    This function reads only tracked contracts and the authorization receipt.  It
    deliberately does not resolve, hash, or open the sealed target artifact.
    """

    repository = Path(root).resolve()
    receipt_path = Path(authorization_path) if authorization_path is not None else repository / AUTHORIZATION_PATH
    if not receipt_path.is_absolute():
        receipt_path = repository / receipt_path
    receipt_path = receipt_path.resolve()
    _require(receipt_path.is_relative_to(repository), "authorization receipt path escapes repository")

    receipt = _read_json(receipt_path, "authorization receipt")
    schema = _read_json(repository / "schemas/a0r2-sealed-execution-authorization.schema.json", "authorization schema")
    if validate(receipt, schema):
        raise A0R2AuthorizationError("authorization receipt schema validation failed")
    _require(receipt.get("receipt_status") == "authorized", "authorization receipt is not active")

    dossier_path = repository / DOSSIER_PATH
    implementation_path = repository / IMPLEMENTATION_PATH
    protocol_path = repository / STUDY_PROTOCOL_PATH
    dossier = _read_json(dossier_path, "approval dossier")
    bindings = receipt.get("bindings")
    _require(isinstance(bindings, Mapping), "authorization bindings missing")
    expected_bindings = {
        "approval_dossier_sha256": _sha256(dossier_path),
        "implementation_sha256": _sha256(implementation_path),
        "study_protocol_sha256": _sha256(protocol_path),
    }
    for key, expected in expected_bindings.items():
        _require(bindings.get(key) == expected, f"authorization binding mismatch: {key}")

    prior = receipt.get("prior_boundary_observation")
    _require(isinstance(prior, Mapping), "prior boundary observation missing")
    _require(prior.get("event") == "sealed_target_file_hash_read_outside_analysis_boundary", "prior boundary event drift")
    _require(prior.get("content_emitted") is False and prior.get("content_retained") is False, "prior boundary observation drift")
    _require(prior.get("new_operator_authorization_required") is True, "prior boundary reauthorization missing")

    _require(dossier.get("dossier_id") == "a0r2-sealed-execution-approval-v1", "approval dossier identity mismatch")
    scope = receipt.get("scope")
    _require(isinstance(scope, Mapping), "authorization scope missing")
    expected_scope = {
        "model_id": "HuggingFaceTB/SmolLM2-360M",
        "revision": "f8027fd0eaeea54caa13c31d31b9fdc459c38b49",
        "device": "cpu",
        "dtype": "float32",
        "local_only": True,
        "network_access": False,
        "generation_allowed": False,
        "maximum_wall_seconds": 1800,
        "maximum_peak_rss_bytes": 8589934592,
        "maximum_new_dense_output_bytes": 67108864,
        "maximum_material_runs": 1,
        "analysis_target_content_reads": 1,
        "publish_every_terminal_outcome": True,
        "tuning_allowed": False,
        "model_substitution_allowed": False,
        "protocol_change_allowed": False,
        "retry_after_model_or_target_access": "new_explicit_approval_required",
    }
    for key, expected in expected_scope.items():
        _require(scope.get(key) == expected, f"authorization scope mismatch: {key}")

    return {
        "artifact_class": "a0r2-sealed-execution-authorization-verification",
        "status": "pass",
        "model_output_accessed": False,
        "sealed_targets_accessed": False,
        "authorization_receipt": str(receipt_path.relative_to(repository)),
    }
