"""Approval and CCP gates for future EXP-002 material execution.

This module has no model-library imports at module load time. The current
repository state contains an unapproved dossier, so every material entry point
fails closed until a separately reviewed authorized dossier is supplied.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any, Callable

from .exp002_followup import EXPECTED_MODELS, Exp002ContractError
from .exp002_surface import validate_score_mapping


class Exp002ExecutionError(RuntimeError):
    """Raised when an EXP-002 material boundary is not satisfied."""


def validate_ccp_gate(gate: Mapping[str, Any]) -> None:
    """Require the exact local admission state before a heavy run."""
    if not isinstance(gate, Mapping):
        raise Exp002ExecutionError("CCP gate must be a mapping")
    if gate.get("resource_decision") != "admit":
        raise Exp002ExecutionError("CCP resource decision is not Admit")
    if gate.get("admission_active") is not False or gate.get("queue_count") != 0:
        raise Exp002ExecutionError("CCP admission is active or queue is non-empty")


def validate_authorized_dossier(dossier: Mapping[str, Any], model_id: str) -> None:
    """Validate one exact model against a consumed operator authorization."""
    if not isinstance(dossier, Mapping) or dossier.get("artifact_class") != "exp002-approval-dossier":
        raise Exp002ExecutionError("unexpected EXP-002 approval dossier")
    if dossier.get("protocol_id") != "exp002-qwen3-followup-v1.0.0" or dossier.get("status") != "authorized":
        raise Exp002ExecutionError("EXP-002 material execution is not authorized")
    approval = dossier.get("operator_approval")
    if not isinstance(approval, Mapping) or approval.get("granted") is not True or approval.get("operator_id") != "MarcoPorcellato":
        raise Exp002ExecutionError("operator approval is missing")
    models = dossier.get("exact_models")
    if not isinstance(models, Sequence) or model_id not in {entry.get("model_id") for entry in models if isinstance(entry, Mapping)}:
        raise Exp002ExecutionError("requested model is not in the exact dossier")
    if EXPECTED_MODELS.get(model_id) not in {entry.get("revision") for entry in models if isinstance(entry, Mapping) and entry.get("model_id") == model_id}:
        raise Exp002ExecutionError("requested model revision is not exact")
    permissions = dossier.get("permissions_requested")
    if not isinstance(permissions, Mapping) or permissions.get("model_load") is not True or permissions.get("network") is not False or permissions.get("generation") is not False:
        raise Exp002ExecutionError("material permissions are unsafe or incomplete")
    if permissions.get("sealed_target_read") != "exactly_one_at_analysis_boundary":
        raise Exp002ExecutionError("sealed-target boundary is not exact")
    limits = dossier.get("limits")
    if not isinstance(limits, Mapping) or limits.get("wall_time_seconds_per_model") != 1800 or limits.get("peak_rss_bytes_per_model") != 8589934592 or limits.get("new_dense_output_bytes_per_model") != 134217728:
        raise Exp002ExecutionError("material limits drift")


def authorize_material_run(dossier: Mapping[str, Any], gate: Mapping[str, Any], model_id: str) -> None:
    """Apply both independent gates; no side effect occurs on failure."""
    validate_authorized_dossier(dossier, model_id)
    validate_ccp_gate(gate)


def score_injected_surface(
    rows: Sequence[Mapping[str, Any]], scorer: Callable[[str], Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Score a target-free prompt list through an explicitly injected adapter.

    The caller supplies the adapter only after ``authorize_material_run``. This
    helper itself never opens targets and never performs generation.
    """
    output: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("prompt"), str) or not row["prompt"].strip():
            raise Exp002ExecutionError("surface row prompt is missing")
        scores = validate_score_mapping(scorer(row["prompt"]))
        output.append({"record_id": row.get("record_id"), "condition": row.get("condition", "original_abcd"), "scores": scores})
    return output


__all__ = ["Exp002ExecutionError", "authorize_material_run", "score_injected_surface", "validate_authorized_dossier", "validate_ccp_gate"]
