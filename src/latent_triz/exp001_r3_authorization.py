"""Fail-closed, no-model builder and verifier for the EXP-001 R3 dossier."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .validator import validate

SCHEMA = Path("schemas/exp001-r3-execution-authorization.schema.json")
PROTOCOL = Path("experiments/exp001-reference-integrated/protocol.json")
IMPLEMENTATION = Path("experiments/exp001-reference-integrated/implementation.json")
INTEGRITY = Path("results/a0r2/preexecution/smollm2-360m-f8027fd0/integrity-receipt.json")
FEASIBILITY = Path("results/a0r2/preexecution/smollm2-360m-f8027fd0/feasibility-receipt.json")


class Exp001AuthorizationError(ValueError):
    """Raised when an approval dossier is absent, unsafe, or stale."""


def _safe(root: Path, relative: str | Path) -> Path:
    value = Path(relative)
    if value.is_absolute() or ".." in value.parts:
        raise Exp001AuthorizationError(f"unsafe artifact path: {relative}")
    candidate = root / value
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise Exp001AuthorizationError(f"missing artifact: {relative}") from exc
    if root.resolve() not in resolved.parents or candidate.is_symlink() or not resolved.is_file():
        raise Exp001AuthorizationError(f"artifact escapes repository: {relative}")
    return resolved


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(root: Path, relative: str | Path) -> dict[str, Any]:
    path = _safe(root, relative)
    return {"path": str(Path(relative)), "sha256": _sha(path), "size": path.stat().st_size}


def build_approval_requested(root: str | Path, *, created_at: str | None = None) -> dict[str, Any]:
    """Build an in-memory approval request; never grants operator approval."""
    repository = Path(root).resolve()
    protocol_path = _safe(repository, PROTOCOL)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("protocol_status") != "frozen":
        raise Exp001AuthorizationError("protocol must be frozen before approval request")
    implementation = _safe(repository, IMPLEMENTATION)
    return {
        "artifact_class": "exp001-r3-execution-authorization",
        "dossier_id": "exp001-r3-execution-approval-v1",
        "protocol_id": "exp001-reference-integrated-r3-v1.0.0",
        "created_at": created_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "dossier_status": "approval_requested",
        "operator_approval_granted": False,
        "protocol": _artifact(repository, PROTOCOL),
        "implementation": _artifact(repository, IMPLEMENTATION),
        "model": {"id": "HuggingFaceTB/SmolLM2-360M", "revision": "f8027fd0eaeea54caa13c31d31b9fdc459c38b49", "local_locator": "artifacts/models/smollm2-360m-f8027fd0", "integrity_receipt": _artifact(repository, INTEGRITY), "feasibility_receipt": _artifact(repository, FEASIBILITY)},
        "inventory": {"primary_records": 72, "secondary_records": 13, "combined_records": 85, "teacher_forced_labels_per_record": 4, "score_calls": 340},
        "limits": {"wall_time_seconds": 1800, "peak_rss_bytes": 8589934592, "new_dense_output_bytes": 134217728},
        "policies": {"device": "cpu", "dtype": "float32", "network_access": False, "generation": False, "single_run": True, "retry_after_model_or_target_access": False, "model_substitution": False, "protocol_mutation": False, "sealed_target_reads": "exactly_one_at_analysis_boundary", "publish_every_terminal_outcome": True},
        "publication": {"terminal_outcomes": ["positive", "null", "failed", "non_interpretable", "incompatible"], "general_triz_claim_allowed": False},
    }


def verify_approval_requested(root: str | Path, dossier: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Verify an approval request and every bound artifact, without model access."""
    repository = Path(root).resolve()
    if isinstance(dossier, dict):
        payload = dossier
    else:
        path = _safe(repository, dossier)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise Exp001AuthorizationError("invalid dossier JSON") from exc
    if not isinstance(payload, dict):
        raise Exp001AuthorizationError("dossier must be an object")
    schema = json.loads(_safe(repository, SCHEMA).read_text(encoding="utf-8"))
    issues = validate(payload, schema)
    if issues:
        raise Exp001AuthorizationError(f"dossier schema failure: {issues[0].message}")
    if payload.get("dossier_status") != "approval_requested" or payload.get("operator_approval_granted") is not False:
        raise Exp001AuthorizationError("dossier must remain approval_requested and unapproved")
    protocol = json.loads(_safe(repository, payload["protocol"]["path"]).read_text(encoding="utf-8"))
    if protocol.get("protocol_status") != "frozen" or protocol.get("protocol_id") != payload["protocol_id"]:
        raise Exp001AuthorizationError("frozen protocol binding mismatch")
    for name in ("protocol", "implementation"):
        binding = payload[name]
        path = _safe(repository, binding["path"])
        if _sha(path) != binding["sha256"] or path.stat().st_size != binding["size"]:
            raise Exp001AuthorizationError(f"{name} hash or size mismatch")
    for name in ("integrity_receipt", "feasibility_receipt"):
        binding = payload["model"][name]
        path = _safe(repository, binding["path"])
        if _sha(path) != binding["sha256"] or path.stat().st_size != binding["size"]:
            raise Exp001AuthorizationError(f"{name} hash or size mismatch")
    return {"artifact_class": "exp001-r3-authorization-verification", "status": "pass", "model_accessed": False, "sealed_targets_accessed": False}


def write_approval_requested(root: str | Path, output: str | Path = "experiments/exp001-reference-integrated/execution-authorization.json", *, created_at: str | None = None) -> dict[str, Any]:
    """Persist one unapproved dossier atomically; never upgrades its status."""
    repository = Path(root).resolve()
    relative = Path(output)
    if relative.is_absolute() or ".." in relative.parts:
        raise Exp001AuthorizationError("unsafe dossier path")
    destination = repository / relative
    if destination.exists():
        raise Exp001AuthorizationError("refuse overwrite: authorization dossier exists")
    dossier = build_approval_requested(repository, created_at=created_at)
    verify_approval_requested(repository, dossier)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(dossier, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=destination.parent, prefix=".r3-approval-", delete=False) as stream:
            stream.write(payload)
            temporary = Path(stream.name)
        os.link(temporary, destination)
    except FileExistsError as exc:
        raise Exp001AuthorizationError("refuse overwrite: authorization dossier exists") from exc
    except OSError as exc:
        raise Exp001AuthorizationError("cannot persist authorization dossier") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return dossier
