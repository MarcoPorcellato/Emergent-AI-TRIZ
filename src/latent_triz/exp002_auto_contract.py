"""Immutable no-model contracts for the independent EXP-002-AUTO programme."""
from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .exp002_followup import EXPECTED_MODELS


class Exp002AutoContractError(ValueError):
    """Raised when an EXP-002-AUTO contract crosses a frozen boundary."""


AUTO_STAGES = ("AUTO-0", "AUTO-1", "AUTO-2", "AUTO-3", "AUTO-4", "AUTO-5")
_NO_MODEL_BOUNDARY = (
    "model_load",
    "tokenizer_construction",
    "generation",
    "sealed_target_read",
    "network",
    "ccp_material_run",
    "new_download",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _models() -> list[dict[str, str]]:
    return [{"model_id": model_id, "revision": revision} for model_id, revision in EXPECTED_MODELS.items()]


def build_no_model_protocol() -> dict[str, Any]:
    """Build the canonical target-free protocol payload without touching runtime assets."""
    return {
        "artifact_class": "exp002-auto-protocol",
        "protocol_id": "exp002-auto-v1.0.0",
        "status": "frozen_no_model",
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "models": _models(),
        "approval_boundary": {field: False for field in _NO_MODEL_BOUNDARY},
        "stages": [
            {"stage_id": stage_id, "model_access": False, "target_access": False}
            for stage_id in AUTO_STAGES
        ],
    }


def _mapping(value: Any, message: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Exp002AutoContractError(message)
    return value


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise Exp002AutoContractError(f"{field} must be a SHA-256")
    return value


def _validate_models(models: Any, field: str) -> None:
    if isinstance(models, (str, bytes, bytearray)) or not isinstance(models, Sequence):
        raise Exp002AutoContractError(f"{field} must be a sequence")
    observed = {
        entry.get("model_id"): entry.get("revision")
        for entry in models
        if isinstance(entry, Mapping)
    }
    if observed != EXPECTED_MODELS or len(models) != len(EXPECTED_MODELS):
        raise Exp002AutoContractError("exact seven-model registry drift")


def validate_auto_protocol(protocol: Mapping[str, Any]) -> None:
    """Validate the immutable no-model protocol and forbid all capabilities."""
    protocol = _mapping(protocol, "AUTO protocol must be an object")
    if protocol.get("artifact_class") != "exp002-auto-protocol" or protocol.get("protocol_id") != "exp002-auto-v1.0.0":
        raise Exp002AutoContractError("unexpected AUTO protocol identity")
    if protocol.get("status") not in {"draft", "frozen_no_model", "approval_requested"}:
        raise Exp002AutoContractError("AUTO protocol is not in a no-model state")
    if protocol.get("scientific_status") != "exploratory" or protocol.get("evidence_eligible") is not False or protocol.get("expert_validated") is not False or protocol.get("claim_ids") != []:
        raise Exp002AutoContractError("AUTO epistemic envelope drift")
    _validate_models(protocol.get("models"), "models")
    boundary = _mapping(protocol.get("approval_boundary"), "AUTO approval boundary must be an object")
    if set(boundary) != set(_NO_MODEL_BOUNDARY) or any(boundary.get(field) is not False for field in _NO_MODEL_BOUNDARY):
        raise Exp002AutoContractError("AUTO no-model boundary is not closed")
    stages = protocol.get("stages")
    if isinstance(stages, (str, bytes, bytearray)) or not isinstance(stages, Sequence):
        raise Exp002AutoContractError("AUTO stages must be a sequence")
    if tuple(stage.get("stage_id") for stage in stages if isinstance(stage, Mapping)) != AUTO_STAGES or len(stages) != len(AUTO_STAGES):
        raise Exp002AutoContractError("AUTO stage inventory drift")
    if any(not isinstance(stage, Mapping) or stage.get("model_access") is not False or stage.get("target_access") is not False for stage in stages):
        raise Exp002AutoContractError("AUTO stage authorizes model or target access")


def validate_auto_schedule(schedule: Mapping[str, Any]) -> None:
    """Validate only schedule identity and immutable hash bindings at this layer."""
    schedule = _mapping(schedule, "AUTO schedule must be an object")
    if schedule.get("artifact_class") != "exp002-auto-schedule" or schedule.get("protocol_id") != "exp002-auto-v1.0.0":
        raise Exp002AutoContractError("unexpected AUTO schedule identity")
    if schedule.get("status") != "frozen_no_model" or schedule.get("claim_ids") != []:
        raise Exp002AutoContractError("AUTO schedule is not a frozen claim-free artifact")
    bindings = _mapping(schedule.get("input_bindings"), "AUTO schedule input bindings are missing")
    if not bindings:
        raise Exp002AutoContractError("AUTO schedule requires input bindings")
    for path, digest in bindings.items():
        if not isinstance(path, str) or not path or path.startswith("/") or ".." in path.split("/"):
            raise Exp002AutoContractError("AUTO schedule input locator is unsafe")
        _sha256(digest, f"input binding {path}")


def validate_auto_dossier(dossier: Mapping[str, Any], *, protocol_sha256: str) -> None:
    """Validate an unapproved or explicitly authorized material dossier."""
    dossier = _mapping(dossier, "AUTO dossier must be an object")
    if dossier.get("artifact_class") != "exp002-auto-approval-dossier" or dossier.get("protocol_id") != "exp002-auto-v1.0.0":
        raise Exp002AutoContractError("unexpected AUTO dossier identity")
    if dossier.get("status") not in {"approval_requested", "authorized"}:
        raise Exp002AutoContractError("AUTO dossier has invalid status")
    if _sha256(dossier.get("protocol_sha256"), "protocol_sha256") != _sha256(protocol_sha256, "expected protocol SHA-256"):
        raise Exp002AutoContractError("AUTO dossier protocol hash drift")
    _sha256(dossier.get("schedule_sha256"), "schedule_sha256")
    _sha256(dossier.get("input_manifest_sha256"), "input_manifest_sha256")
    _validate_models(dossier.get("exact_models"), "exact_models")
    if dossier.get("claim_ids") != []:
        raise Exp002AutoContractError("AUTO dossier cannot promote claims")
    permissions = _mapping(dossier.get("permissions"), "AUTO dossier permissions are missing")
    expected_permissions = {
        "model_load": True,
        "network": False,
        "generation": False,
        "sealed_target_read": "exactly_one_at_analysis_boundary",
    }
    if dict(permissions) != expected_permissions:
        raise Exp002AutoContractError("AUTO dossier permissions drift")
    limits = _mapping(dossier.get("limits"), "AUTO dossier limits are missing")
    expected_limits = {
        "wall_time_seconds_per_shard": 1800,
        "peak_rss_bytes_per_shard": 8589934592,
        "new_score_output_bytes_per_model": 134217728,
    }
    if dict(limits) != expected_limits:
        raise Exp002AutoContractError("AUTO dossier limits drift")
    shards = dossier.get("shards")
    if isinstance(shards, (str, bytes, bytearray)) or not isinstance(shards, Sequence):
        raise Exp002AutoContractError("AUTO dossier shards must be a sequence")
    approval = _mapping(dossier.get("operator_approval"), "AUTO dossier approval is missing")
    granted = approval.get("granted")
    if dossier["status"] == "authorized":
        if granted is not True or approval.get("operator_id") != "MarcoPorcellato":
            raise Exp002AutoContractError("AUTO authorization is missing")
        _sha256(approval.get("approval_text_sha256"), "approval_text_sha256")
    elif granted is not False:
        raise Exp002AutoContractError("approval-requested dossier must remain ungranted")


__all__ = [
    "AUTO_STAGES",
    "Exp002AutoContractError",
    "build_no_model_protocol",
    "validate_auto_dossier",
    "validate_auto_protocol",
    "validate_auto_schedule",
]
