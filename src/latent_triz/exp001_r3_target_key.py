"""Post-freeze validation for the EXP-001 R3 sealed response key."""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


class Exp001TargetKeyError(ValueError):
    """Raised when a sealed key is incomplete, mismatched, or position-biased."""


def validate_sealed_target_key(records: Sequence[Mapping[str, Any]], targets: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Bind every supplied record while preserving the 72-record primary balance."""
    expected = {record.get("record_id"): record for record in records if isinstance(record, Mapping)}
    if len(records) < 72 or len(expected) != len(records) or None in expected:
        raise Exp001TargetKeyError("record inventory must contain unique non-empty IDs")
    primary = [record for record in records if isinstance(record, Mapping) and "unit_id" in record]
    if len(primary) != 72:
        raise Exp001TargetKeyError("primary record inventory must contain exactly 72 records")
    resolved: dict[str, str] = {}
    for target in targets:
        if not isinstance(target, Mapping):
            raise Exp001TargetKeyError("target must be an object")
        record_id, choice = target.get("record_id"), target.get("expected_choice")
        if not isinstance(record_id, str) or choice not in {"A", "B", "C", "D"} or record_id in resolved:
            raise Exp001TargetKeyError("target identity is invalid")
        resolved[record_id] = choice
    if set(resolved) != set(expected):
        raise Exp001TargetKeyError("sealed key must bind exactly the public records")
    primary_ids = {record["record_id"] for record in primary}
    for suffix in ("transfer-blinded", "lexical-control", "transfer-exposed"):
        choices = Counter(choice for record_id, choice in resolved.items() if record_id in primary_ids and record_id.endswith(suffix))
        if choices != Counter({"A": 6, "B": 6, "C": 6, "D": 6}):
            raise Exp001TargetKeyError(f"{suffix} target positions are not exactly balanced")
    for record_id, record in expected.items():
        if record["condition"] == "transfer":
            twin = record_id.replace("-transfer-exposed", "-transfer-blinded")
            if record_id.endswith("-transfer-exposed") and resolved[record_id] != resolved[twin]:
                raise Exp001TargetKeyError("exposed and blinded transfer keys must agree")
    return {"status": "balanced", "records": len(records), "primary_records": 72, "positions_per_condition": 6}
