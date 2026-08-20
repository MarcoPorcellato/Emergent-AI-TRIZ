"""Injected, target-free execution boundaries for EXP-002-AUTO."""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .exp002_auto_contract import Exp002AutoContractError, validate_auto_dossier
from .exp002_followup import EXPECTED_MODELS
from .exp002_surface import validate_score_mapping


class Exp002AutoExecutionError(RuntimeError):
    """Raised before an unsafe AUTO scorer can be invoked."""


_FORBIDDEN_PUBLIC_FIELDS = frozenset({"target", "expected_candidate_index", "correct_choice", "expected_answer"})


def _public_row(row: Mapping[str, Any], *, require_candidates: bool) -> None:
    if not isinstance(row, Mapping) or not isinstance(row.get("record_id"), str) or not row["record_id"].strip():
        raise Exp002AutoExecutionError("AUTO public row identity is malformed")
    if any(field in row for field in _FORBIDDEN_PUBLIC_FIELDS):
        raise Exp002AutoExecutionError("AUTO public scorer received target material")
    if require_candidates:
        candidates = row.get("candidate_descriptions")
        if isinstance(candidates, (str, bytes, bytearray)) or not isinstance(candidates, Sequence) or len(candidates) != 4 or any(not isinstance(value, str) or not value.strip() for value in candidates):
            raise Exp002AutoExecutionError("AUTO candidate descriptions are malformed")


def authorize_auto_shard(
    dossier: Mapping[str, Any], protocol_sha256: str, gate: Mapping[str, Any], model_id: str,
    stage_id: str, shard_id: str,
) -> dict[str, str]:
    """Require one exact authorized model/shard after a fresh clean CCP gate."""
    try:
        validate_auto_dossier(dossier, protocol_sha256=protocol_sha256)
    except Exp002AutoContractError as exc:
        raise Exp002AutoExecutionError(str(exc)) from exc
    if dossier.get("status") != "authorized":
        raise Exp002AutoExecutionError("AUTO material dossier is not authorized")
    if EXPECTED_MODELS.get(model_id) is None:
        raise Exp002AutoExecutionError("AUTO model identity is unknown")
    if not isinstance(gate, Mapping) or gate.get("resource_decision", gate.get("decision")) != "admit" or gate.get("admission_active", gate.get("active")) is not False or gate.get("queue_count") != 0:
        raise Exp002AutoExecutionError("AUTO CCP gate is not Admit/inactive/queue-zero")
    shards = dossier.get("shards")
    if not isinstance(shards, Sequence) or not any(
        isinstance(shard, Mapping) and shard.get("stage_id") == stage_id and shard.get("shard_id") == shard_id
        for shard in shards
    ):
        raise Exp002AutoExecutionError("AUTO shard is not frozen in the authorization dossier")
    return {"model_id": model_id, "revision": EXPECTED_MODELS[model_id], "stage_id": stage_id, "shard_id": shard_id}


def score_auto_surface(rows: Sequence[Mapping[str, Any]], scorer: Callable[[Mapping[str, Any]], Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Score public four-label rows through an injected scorer, never a target key."""
    if isinstance(rows, (str, bytes, bytearray)) or not isinstance(rows, Sequence) or not rows:
        raise Exp002AutoExecutionError("AUTO surface rows must be non-empty")
    output: list[dict[str, Any]] = []
    for row in rows:
        _public_row(row, require_candidates=False)
        scores = validate_score_mapping(scorer(row))
        output.append({"record_id": row["record_id"], "condition": row.get("condition"), "scores": scores})
    return output


def score_auto_candidates(rows: Sequence[Mapping[str, Any]], scorer: Callable[[str], float]) -> list[dict[str, Any]]:
    """Score complete public candidates without label-token scores or target reads."""
    if isinstance(rows, (str, bytes, bytearray)) or not isinstance(rows, Sequence) or not rows:
        raise Exp002AutoExecutionError("AUTO candidate rows must be non-empty")
    output: list[dict[str, Any]] = []
    for row in rows:
        _public_row(row, require_candidates=True)
        values = [float(scorer(candidate)) for candidate in row["candidate_descriptions"]]
        if any(not math.isfinite(value) for value in values):
            raise Exp002AutoExecutionError("AUTO candidate scorer returned non-finite score")
        output.append({"record_id": row["record_id"], "condition": "label_free_candidate_description_scoring", "candidate_scores": values})
    return output


__all__ = ["Exp002AutoExecutionError", "authorize_auto_shard", "score_auto_candidates", "score_auto_surface"]
