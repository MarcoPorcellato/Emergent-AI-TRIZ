"""Fail-closed, no-model preflight records for EXP-002-AUTO shards."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .exp002_followup import EXPECTED_MODELS


def preflight_auto_shard(
    *, dossier: Mapping[str, Any], stage_id: str, shard_id: str, model_id: str,
) -> dict[str, Any]:
    """Return a transparent non-material state without constructing a model.

    This helper is deliberately incapable of advancing execution.  A caller
    must use the separately authorized executor only after a new exact dossier
    is validated against the frozen protocol and local CCP admission state.
    """
    if model_id not in EXPECTED_MODELS:
        raise ValueError("AUTO preflight model is not in the frozen seven-model registry")
    if not isinstance(stage_id, str) or not stage_id.startswith("AUTO-") or not isinstance(shard_id, str) or not shard_id:
        raise ValueError("AUTO preflight shard identity is malformed")
    approved = isinstance(dossier, Mapping) and dossier.get("status") == "authorized"
    return {
        "artifact_class": "exp002-auto-stage-preflight",
        "protocol_id": "exp002-auto-v1.0.0",
        "stage_id": stage_id,
        "shard_id": shard_id,
        "model_id": model_id,
        "status": "authorization_validation_required" if approved else "approval_required",
        "model_accessed": False,
        "sealed_target_accessed": False,
        "network_accessed": False,
    }


def build_preexecution_receipt() -> dict[str, Any]:
    """Build the immutable-safe template that documents no material access."""
    return {
        "artifact_class": "exp002-auto-execution-receipt",
        "protocol_id": "exp002-auto-v1.0.0",
        "run_id": "exp002-auto-template",
        "model_id": None,
        "revision": None,
        "status": "not_started",
        "execution": {
            "device": "cpu", "dtype": "float32", "network": False,
            "generation": False, "run_count": 0, "wall_seconds": 0,
            "peak_rss_bytes": 0, "new_score_output_bytes": 0,
        },
        "access": {
            "model_loaded": False, "model_output_accessed": False,
            "sealed_target_accessed": False, "target_reads": 0,
        },
        "scientific_status": "exploratory", "evidence_eligible": False,
        "expert_validated": False, "claim_ids": [],
    }


__all__ = ["build_preexecution_receipt", "preflight_auto_shard"]
