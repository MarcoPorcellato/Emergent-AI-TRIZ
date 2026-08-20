"""One-read, claim-free analysis boundary for future EXP-002-AUTO scores."""
from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .exp002_analysis import evaluate_transfer


class Exp002AutoAnalysisError(ValueError):
    """Raised when analysis would access a key before immutable inputs verify."""


_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _validate_hashes(observed: Mapping[str, str], expected: Mapping[str, str]) -> None:
    if not isinstance(observed, Mapping) or not isinstance(expected, Mapping) or set(observed) != set(expected) or not expected:
        raise Exp002AutoAnalysisError("score-asset hash inventory drift")
    for locator, digest in expected.items():
        if not isinstance(locator, str) or not isinstance(digest, str) or not _SHA256.fullmatch(digest) or observed.get(locator) != digest:
            raise Exp002AutoAnalysisError("score asset is missing or hash-mutated")


def _rows(rows: Sequence[Mapping[str, Any]], required_field: str) -> dict[str, Mapping[str, Any]]:
    if isinstance(rows, (str, bytes, bytearray)) or not isinstance(rows, Sequence) or not rows:
        raise Exp002AutoAnalysisError("score rows must be non-empty")
    copied: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("record_id"), str) or not row["record_id"].strip() or not isinstance(row.get(required_field), str) or not row[required_field]:
            raise Exp002AutoAnalysisError("score row identity is malformed")
        scores = row.get("candidate_scores")
        if isinstance(scores, (str, bytes, bytearray)) or not isinstance(scores, Sequence) or len(scores) != 4:
            raise Exp002AutoAnalysisError("candidate score vector is malformed")
        values = [float(value) for value in scores]
        if any(not math.isfinite(value) for value in values) or row["record_id"] in copied:
            raise Exp002AutoAnalysisError("candidate score vector is non-finite or duplicate")
        copied[row["record_id"]] = {**row, "candidate_scores": values}
    return copied


def _read_key_once(reader: Callable[[], Mapping[str, Any]], expected_ids: set[str]) -> dict[str, int]:
    key = reader()
    if not isinstance(key, Mapping) or key.get("artifact_class") != "exp002-auto-combined-target-key" or key.get("status") != "sealed":
        raise Exp002AutoAnalysisError("combined target key is not sealed")
    rows = key.get("records")
    if isinstance(rows, (str, bytes, bytearray)) or not isinstance(rows, Sequence):
        raise Exp002AutoAnalysisError("combined target key records are malformed")
    indices: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("record_id"), str) or isinstance(row.get("expected_candidate_index"), bool) or not isinstance(row.get("expected_candidate_index"), int) or row["expected_candidate_index"] not in range(4):
            raise Exp002AutoAnalysisError("combined target key entry is malformed")
        if row["record_id"] in indices:
            raise Exp002AutoAnalysisError("combined target key has duplicate record IDs")
        indices[row["record_id"]] = row["expected_candidate_index"]
    if set(indices) != expected_ids:
        raise Exp002AutoAnalysisError("combined target key coverage drift")
    return indices


def _top_index(scores: Sequence[float]) -> int:
    return max(range(4), key=lambda index: scores[index])


def analyze_combined_candidate_scores(
    *, factual_rows: Sequence[Mapping[str, Any]], procedural_rows: Sequence[Mapping[str, Any]],
    observed_asset_hashes: Mapping[str, str], expected_asset_hashes: Mapping[str, str],
    key_reader: Callable[[], Mapping[str, Any]],
) -> dict[str, Any]:
    """Verify all score assets, open one combined key once, then analyze two stages."""
    _validate_hashes(observed_asset_hashes, expected_asset_hashes)
    factual = _rows(factual_rows, "family")
    procedural = _rows(procedural_rows, "domain")
    indices = _read_key_once(key_reader, set(factual) | set(procedural))

    factual_family: dict[str, list[bool]] = defaultdict(list)
    for record_id, row in factual.items():
        factual_family[row["family"]].append(_top_index(row["candidate_scores"]) == indices[record_id])
    factual_summary = {
        "record_count": len(factual),
        "correct_count": sum(sum(values) for values in factual_family.values()),
        "accuracy": sum(sum(values) for values in factual_family.values()) / len(factual),
        "family_accuracy": {family: sum(values) / len(values) for family, values in sorted(factual_family.items())},
        "status": "automated_factual_summary",
    }

    domain_margins: dict[str, list[float]] = defaultdict(list)
    for record_id, row in procedural.items():
        expected_index = indices[record_id]
        scores = row["candidate_scores"]
        domain_margins[row["domain"]].append(scores[expected_index] - max(score for index, score in enumerate(scores) if index != expected_index))
    deltas = [sum(domain_margins[domain]) / len(domain_margins[domain]) for domain in sorted(domain_margins)]
    evaluation = evaluate_transfer(deltas, minimum_domains=8, margin=0.10)
    procedural_summary = {
        "record_count": len(procedural),
        "domain_margins": {domain: sum(values) / len(values) for domain, values in sorted(domain_margins.items())},
        "status": "auto_proxy_signal" if evaluation["status"] == "positive" else evaluation["status"],
        "analysis": evaluation,
        "construct": "automated_procedural_transfer_proxy",
    }
    return {
        "artifact_class": "exp002-auto-combined-analysis",
        "sealed_target_read_count": 1,
        "sealed_target_accessed": True,
        "factual": factual_summary,
        "procedural": procedural_summary,
        "scientific_status": "exploratory",
        "expert_validated": False,
        "evidence_eligible": False,
        "claim_ids": [],
    }


__all__ = ["Exp002AutoAnalysisError", "analyze_combined_candidate_scores"]
