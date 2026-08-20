"""Fail-closed terminal-result helpers for EXP-002 synthetic and later runs."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .exp002_followup import EXPECTED_MODELS, Exp002ContractError


TERMINAL_STATUSES = ("positive", "null", "failed", "non_interpretable", "incompatible")


def build_terminal_result(
    *, study_id: str, model_id: str, status: str, model_loaded: bool = False,
    model_output_accessed: bool = False, generation_used: bool = False,
    sealed_target_accessed: bool = False, target_reads: int = 0,
) -> dict[str, Any]:
    """Build an exploratory terminal envelope without any scientific claim."""
    revision = EXPECTED_MODELS.get(model_id)
    if revision is None:
        raise Exp002ContractError("unknown EXP-002 model identity")
    if study_id not in {"EXP-002A", "EXP-002B", "EXP-002C", "EXP-002D"}:
        raise Exp002ContractError("unknown EXP-002 study")
    if status not in TERMINAL_STATUSES:
        raise Exp002ContractError("invalid terminal status")
    if isinstance(target_reads, bool) or not isinstance(target_reads, int) or target_reads < 0:
        raise Exp002ContractError("target_reads must be a non-negative integer")
    if not sealed_target_accessed and target_reads != 0:
        raise Exp002ContractError("target reads require sealed-target access")
    return {
        "artifact_class": "exp002-followup-terminal-result",
        "protocol_id": "exp002-qwen3-followup-v1.0.0",
        "study_id": study_id,
        "model_id": model_id,
        "revision": revision,
        "status": status,
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "access": {
            "model_loaded": bool(model_loaded),
            "model_output_accessed": bool(model_output_accessed),
            "generation_used": bool(generation_used),
            "sealed_target_accessed": bool(sealed_target_accessed),
            "target_reads": target_reads,
        },
    }


def validate_terminal_result(result: Mapping[str, Any]) -> None:
    """Reject claim promotion and access-accounting inconsistencies."""
    if not isinstance(result, Mapping) or result.get("artifact_class") != "exp002-followup-terminal-result":
        raise Exp002ContractError("unexpected EXP-002 result envelope")
    if result.get("protocol_id") != "exp002-qwen3-followup-v1.0.0" or result.get("status") not in TERMINAL_STATUSES:
        raise Exp002ContractError("terminal identity or status drift")
    if result.get("scientific_status") != "exploratory" or result.get("evidence_eligible") is not False or result.get("expert_validated") is not False or result.get("claim_ids") != []:
        raise Exp002ContractError("scientific envelope drift")
    model_id = result.get("model_id")
    if EXPECTED_MODELS.get(model_id) != result.get("revision"):
        raise Exp002ContractError("terminal model identity drift")
    access = result.get("access")
    if not isinstance(access, Mapping):
        raise Exp002ContractError("terminal access receipt missing")
    reads = access.get("target_reads")
    if isinstance(reads, bool) or not isinstance(reads, int) or reads < 0:
        raise Exp002ContractError("terminal target read count is invalid")
    if access.get("sealed_target_accessed") is not True and reads != 0:
        raise Exp002ContractError("target reads recorded without target access")


__all__ = ["TERMINAL_STATUSES", "build_terminal_result", "validate_terminal_result"]
