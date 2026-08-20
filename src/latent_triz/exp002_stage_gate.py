"""Fail-closed authorization gates for EXP-002B and EXP-002C.

This module validates only an injected dossier and CCP snapshot. It never
loads a model, reads a target, accesses a tokenizer, or performs a run.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .exp002_execution import validate_ccp_gate
from .exp002_followup import EXPECTED_MODELS


class Exp002StageGateError(ValueError):
    """Raised when a stage dossier is missing a frozen prerequisite."""


_STAGES = {"EXP-002B", "EXP-002C"}


def _require(value: Any, message: str) -> None:
    if not value:
        raise Exp002StageGateError(message)


def validate_stage_dossier(dossier: Mapping[str, Any], stage_id: str) -> None:
    """Validate a material-stage dossier without authorizing execution."""
    if stage_id not in _STAGES:
        raise Exp002StageGateError("unsupported EXP-002 material stage")
    if not isinstance(dossier, Mapping) or dossier.get("artifact_class") != "exp002-study-approval-dossier":
        raise Exp002StageGateError("unexpected EXP-002 study dossier")
    if dossier.get("protocol_id") != "exp002-qwen3-followup-v1.0.0" or dossier.get("stage_id") != stage_id:
        raise Exp002StageGateError("stage/protocol identity drift")
    if dossier.get("status") not in {"approval_requested", "authorized"}:
        raise Exp002StageGateError("dossier is not awaiting or carrying authorization")
    models = dossier.get("exact_models")
    if isinstance(models, (str, bytes, bytearray)) or not isinstance(models, Sequence) or len(models) != len(EXPECTED_MODELS):
        raise Exp002StageGateError("dossier must enumerate all seven exact models")
    observed: dict[str, str] = {}
    for entry in models:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("model_id"), str) or not isinstance(entry.get("revision"), str):
            raise Exp002StageGateError("model identity record is malformed")
        if entry["model_id"] in observed:
            raise Exp002StageGateError("duplicate model identity")
        observed[entry["model_id"]] = entry["revision"]
    if observed != EXPECTED_MODELS:
        raise Exp002StageGateError("model identity or revision drift")

    prerequisites = dossier.get("prerequisites")
    if not isinstance(prerequisites, Mapping) or prerequisites.get("source_proximity_status") not in {"pass", "pending"}:
        raise Exp002StageGateError("source-proximity prerequisite is not passed")
    if prerequisites.get("answer_key_status") not in {"frozen", "pending", "not_applicable"} or prerequisites.get("transfer_corpus_status") not in {"frozen_no_model", "pending", "not_applicable"} or prerequisites.get("power_calibration_status") not in {"pass", "pending", "not_applicable"}:
        raise Exp002StageGateError("stage prerequisite status is unsupported")
    if dossier["status"] == "authorized":
        if prerequisites.get("source_proximity_status") != "pass":
            raise Exp002StageGateError("authorized stage requires a passed source-proximity audit")
        if stage_id == "EXP-002B" and prerequisites.get("answer_key_status") != "frozen":
            raise Exp002StageGateError("EXP-002B requires a frozen expert answer key")
        if stage_id == "EXP-002C":
            if prerequisites.get("transfer_corpus_status") != "frozen_no_model":
                raise Exp002StageGateError("EXP-002C requires a frozen transfer corpus")
            if prerequisites.get("power_calibration_status") != "pass":
                raise Exp002StageGateError("EXP-002C requires a passed power calibration")

    permissions = dossier.get("permissions")
    if not isinstance(permissions, Mapping):
        raise Exp002StageGateError("stage permissions are missing")
    required = {
        "model_load": True,
        "generation": False,
        "network": False,
        "sealed_target_read": "exactly_one_at_analysis_boundary",
        "ccp_material_run": True,
        "publish_every_terminal_outcome": True,
    }
    if any(permissions.get(key) != value for key, value in required.items()):
        raise Exp002StageGateError("stage permissions drift")
    limits = dossier.get("limits")
    if not isinstance(limits, Mapping) or limits.get("wall_time_seconds_per_model") != 1800 or limits.get("peak_rss_bytes_per_model") != 8589934592 or limits.get("new_dense_output_bytes_per_model") != 134217728:
        raise Exp002StageGateError("stage resource limits drift")
    if dossier.get("scientific_status") != "exploratory" or dossier.get("claim_ids") != []:
        raise Exp002StageGateError("scientific envelope drift")
    approval = dossier.get("operator_approval")
    if not isinstance(approval, Mapping) or approval.get("operator_id") != "MarcoPorcellato":
        raise Exp002StageGateError("operator approval record is malformed")
    if dossier["status"] == "approval_requested" and approval.get("granted") is not False:
        raise Exp002StageGateError("approval-requested dossier is already marked granted")
    if dossier["status"] == "authorized" and (approval.get("granted") is not True or not approval.get("approved_at") or not approval.get("approval_text_sha256")):
        raise Exp002StageGateError("authorized dossier lacks an approval receipt")


def authorize_stage(dossier: Mapping[str, Any], stage_id: str, ccp_gate: Mapping[str, Any]) -> None:
    """Authorize exactly one future stage only after dossier and CCP gates pass."""
    validate_stage_dossier(dossier, stage_id)
    if dossier.get("status") != "authorized":
        raise Exp002StageGateError("operator authorization is required before material execution")
    try:
        validate_ccp_gate(ccp_gate)
    except Exception as exc:
        raise Exp002StageGateError(str(exc)) from exc


__all__ = ["Exp002StageGateError", "authorize_stage", "validate_stage_dossier"]
