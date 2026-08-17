"""Sealed-target analysis boundary for EXP-001 R3.

This module deliberately stops at the boundary between model responses and
the sealed response key.  It has no filesystem, network, model, or runtime
dependencies: callers provide the public records, scored response rows, and
the one-shot target reader.  Invalid public responses are rejected before the
reader is called, and target-key failures remain terminal after that call.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .exp001_r3_analysis import analyze_primary
from .exp001_r3_target_key import validate_sealed_target_key


class Exp001RunnerError(ValueError):
    """Raised when the analysis boundary contract is violated."""


_CHOICES = ("A", "B", "C", "D")
_STRATA = {"TRIZ-blinded-transfer", "source-exposed-competence"}


def _record_ids(records: Sequence[Mapping[str, Any]]) -> set[str]:
    if len(records) != 72:
        raise Exp001RunnerError("analysis boundary requires exactly 72 public records")
    identifiers: set[str] = set()
    for record in records:
        if not isinstance(record, Mapping):
            raise Exp001RunnerError("public record must be an object")
        record_id = record.get("record_id")
        if not isinstance(record_id, str) or not record_id or record_id in identifiers:
            raise Exp001RunnerError("public record IDs must be unique non-empty strings")
        if record.get("stratum") not in _STRATA:
            raise Exp001RunnerError("public record has an unknown stratum")
        identifiers.add(record_id)
    return identifiers


def _validate_responses(
    responses: Sequence[Mapping[str, Any]], expected_ids: set[str]
) -> dict[str, Mapping[str, Any]]:
    if len(responses) != len(expected_ids):
        raise Exp001RunnerError("response row count must equal the public record count")
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in responses:
        if not isinstance(row, Mapping):
            raise Exp001RunnerError("response row must be an object")
        record_id = row.get("record_id")
        scores = row.get("scores")
        if not isinstance(record_id, str) or record_id not in expected_ids or record_id in indexed:
            raise Exp001RunnerError("response IDs must match public IDs exactly once")
        if not isinstance(scores, Mapping) or set(scores) != set(_CHOICES):
            raise Exp001RunnerError("each response must provide exactly A/B/C/D scores")
        for choice in _CHOICES:
            value = scores[choice]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise Exp001RunnerError(f"response score {record_id}/{choice} must be finite numeric")
        indexed[record_id] = row
    if set(indexed) != expected_ids:
        raise Exp001RunnerError("response IDs do not cover the public records exactly")
    return indexed


def _choice_margin(scores: Mapping[str, Any], expected_choice: str) -> float:
    distractors = [float(scores[choice]) for choice in _CHOICES if choice != expected_choice]
    return float(scores[expected_choice]) - (sum(distractors) / len(distractors))


def run_analysis_boundary(
    records: Sequence[Mapping[str, Any]],
    responses: Sequence[Mapping[str, Any]],
    target_reader: Callable[[Sequence[Mapping[str, Any]]], Sequence[Mapping[str, Any]]],
    analysis_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Open the sealed key exactly once, then run the non-pooled primary.

    ``target_reader`` is the sole sealed-data capability.  It is not called
    until all public response rows have passed validation.  The reader's
    return value is passed to ``validate_sealed_target_key`` without copying
    or inspecting target contents before that validation step.
    """
    public_ids = _record_ids(records)
    response_by_id = _validate_responses(responses, public_ids)

    # This is intentionally the only invocation of the supplied sealed-data
    # capability.  A key failure after this point is terminal and not retried.
    targets = target_reader(records)
    if not isinstance(targets, Sequence) or isinstance(targets, (str, bytes)):
        raise Exp001RunnerError("sealed target reader must return a sequence")
    try:
        validate_sealed_target_key(records, targets)
    except Exception as exc:
        raise Exp001RunnerError("sealed target key validation failed") from exc

    target_by_id = {target["record_id"]: target["expected_choice"] for target in targets}
    record_by_id = {record["record_id"]: record for record in records}
    units: dict[str, dict[str, Any]] = {}
    for record_id, record in record_by_id.items():
        # Exposed competence is a separate descriptive stratum and is never
        # merged into the transfer-vs-control primary endpoint.
        if record.get("stratum") != "TRIZ-blinded-transfer":
            continue
        condition = record.get("condition")
        if condition not in {"transfer", "lexical_control"}:
            raise Exp001RunnerError("primary record has an unknown condition")
        unit_id = record.get("unit_id")
        if not isinstance(unit_id, str) or not unit_id:
            raise Exp001RunnerError("primary record lacks unit_id")
        entry = units.setdefault(unit_id, {key: record.get(key) for key in ("domain", "problem_family", "replicate")})
        field = "blinded_score" if condition == "transfer" else "lexical_control_score"
        if field in entry:
            raise Exp001RunnerError("duplicate primary condition for unit")
        entry[field] = _choice_margin(response_by_id[record_id]["scores"], target_by_id[record_id])

    if len(units) != 24 or any(set(value) != {"domain", "problem_family", "replicate", "blinded_score", "lexical_control_score"} for value in units.values()):
        raise Exp001RunnerError("primary boundary must produce exactly 24 complete non-pooled units")
    scored_units = [{"unit_id": unit_id, **value} for unit_id, value in units.items()]
    result = analyze_primary(scored_units, analysis_plan)
    return {
        "analysis": result,
        "access": {"sealed_target_reader_calls": 1, "sealed_targets_accessed": True},
        "public_record_count": len(records),
        "response_row_count": len(responses),
        "primary_unit_count": len(scored_units),
        "exposed_rows_excluded_from_primary": sum(
            1 for record in records if record.get("stratum") == "source-exposed-competence"
        ),
    }
