"""Predeclared descriptive comparison between the frozen R1 and R2 scores."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any


class A0R2ComparisonError(RuntimeError):
    """Raised when the two frozen result vectors are not comparable."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise A0R2ComparisonError(message)


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    _require(len(left) == len(right) and len(left) > 1, "score vectors must have equal non-trivial length")
    left_mean = math.fsum(left) / len(left)
    right_mean = math.fsum(right) / len(right)
    left_centered = [float(value) - left_mean for value in left]
    right_centered = [float(value) - right_mean for value in right]
    numerator = math.fsum(a * b for a, b in zip(left_centered, right_centered, strict=True))
    left_norm = math.sqrt(math.fsum(value * value for value in left_centered))
    right_norm = math.sqrt(math.fsum(value * value for value in right_centered))
    _require(left_norm > 0.0 and right_norm > 0.0, "score correlation is undefined for a constant vector")
    return max(-1.0, min(1.0, numerator / (left_norm * right_norm)))


def _average_ranks(values: Sequence[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: (float(item[1]), item[0]))
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and float(ordered[end][1]) == float(ordered[cursor][1]):
            end += 1
        average = ((cursor + 1) + end) / 2.0
        for position in range(cursor, end):
            ranks[ordered[position][0]] = average
        cursor = end
    return ranks


def _paired_outcomes(scores: Sequence[float], labels: Sequence[int], families: Sequence[str]) -> dict[str, bool]:
    members: dict[str, list[int]] = defaultdict(list)
    for index, family in enumerate(families):
        members[str(family)].append(index)
    outcomes: dict[str, bool] = {}
    for family, indices in sorted(members.items()):
        _require(len(indices) == 2, f"family {family} is not paired")
        _require(sorted(labels[index] for index in indices) == [0, 1], f"family {family} is not balanced")
        positive = next(index for index in indices if labels[index] == 1)
        negative = next(index for index in indices if labels[index] == 0)
        outcomes[family] = float(scores[positive]) > float(scores[negative])
    return outcomes


def compare_frozen_scores(
    *,
    r1_scores: Sequence[float],
    r2_scores: Sequence[float],
    labels: Sequence[int],
    families: Sequence[str],
    r1_domain_directions: Mapping[str, Any],
    r2_domain_directions: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute descriptive-only concordance; callers must not use it for the primary outcome."""

    count = len(r1_scores)
    _require(count == 48, "cross-model comparison requires the frozen 48-case order")
    _require(len(r2_scores) == count == len(labels) == len(families), "cross-model vector length mismatch")
    left = [float(value) for value in r1_scores]
    right = [float(value) for value in r2_scores]
    _require(all(math.isfinite(value) for value in left + right), "cross-model scores must be finite")

    r1_family = _paired_outcomes(left, labels, families)
    r2_family = _paired_outcomes(right, labels, families)
    _require(set(r1_family) == set(r2_family), "cross-model family set mismatch")
    domains = sorted(set(str(key) for key in r1_domain_directions) | set(str(key) for key in r2_domain_directions))
    _require(domains and set(domains) == set(r1_domain_directions) == set(r2_domain_directions), "cross-model domain set mismatch")

    return {
        "interpretation": "descriptive_only",
        "may_affect_primary": False,
        "case_order": "lexicographic_case_id_shared_with_r1",
        "case_count": count,
        "pearson_score_correlation": _pearson(left, right),
        "spearman_score_correlation": _pearson(_average_ranks(left), _average_ranks(right)),
        "score_sign_agreement": math.fsum(float((a >= 0.0) == (b >= 0.0)) for a, b in zip(left, right, strict=True)) / count,
        "family_outcome_agreement": math.fsum(float(r1_family[key] == r2_family[key]) for key in sorted(r1_family)) / len(r1_family),
        "domain_direction_sign_agreement": math.fsum(
            float((float(r1_domain_directions[key]) > 0.0) == (float(r2_domain_directions[key]) > 0.0))
            for key in domains
        ) / len(domains),
    }
