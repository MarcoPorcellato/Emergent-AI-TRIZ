"""Prerecorded, model-independent statistics for EXP-002 transfer studies."""
from __future__ import annotations

from itertools import product
import math
from collections.abc import Sequence
from typing import Any


class Exp002AnalysisError(ValueError):
    """Raised when an EXP-002 statistical input is not interpretable."""


TERMINAL_STATUSES = ("positive", "null", "failed", "non_interpretable", "incompatible")
DEFAULT_ALPHA = 0.05
DEFAULT_MARGIN = 0.10
DEFAULT_MIN_DOMAINS = 8


def _finite_deltas(deltas: Sequence[Any]) -> tuple[float, ...]:
    if isinstance(deltas, (str, bytes, bytearray)) or not isinstance(deltas, Sequence):
        raise Exp002AnalysisError("domain deltas must be a sequence")
    values: list[float] = []
    for value in deltas:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise Exp002AnalysisError("domain deltas must be finite numbers")
        values.append(float(value))
    return tuple(values)


def exact_sign_flip_pvalue(deltas: Sequence[Any]) -> float:
    """Return the exact two-sided mean sign-flip p-value for one delta/domain."""
    values = _finite_deltas(deltas)
    if not values or len(values) > 16:
        raise Exp002AnalysisError("exact sign-flip test requires 1-16 domains")
    observed = abs(sum(values) / len(values))
    extreme = 0
    total = 0
    for signs in product((-1.0, 1.0), repeat=len(values)):
        statistic = abs(sum(value * sign for value, sign in zip(values, signs)) / len(values))
        if statistic >= observed - 1e-15:
            extreme += 1
        total += 1
    return extreme / total


def evaluate_transfer(
    deltas: Sequence[Any], *, alpha: float = DEFAULT_ALPHA, margin: float = DEFAULT_MARGIN,
    minimum_domains: int = DEFAULT_MIN_DOMAINS,
) -> dict[str, Any]:
    """Classify a frozen transfer vector without selecting domains post hoc."""
    values = _finite_deltas(deltas)
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not 0 < float(alpha) <= 1:
        raise Exp002AnalysisError("alpha must be in (0,1]")
    if isinstance(margin, bool) or not isinstance(margin, (int, float)) or float(margin) < 0:
        raise Exp002AnalysisError("margin must be non-negative")
    if isinstance(minimum_domains, bool) or not isinstance(minimum_domains, int) or minimum_domains < 1:
        raise Exp002AnalysisError("minimum_domains must be positive")
    if len(values) < minimum_domains:
        return {"status": "non_interpretable", "reason": "insufficient_domains", "domain_count": len(values)}
    mean_delta = sum(values) / len(values)
    p_value = exact_sign_flip_pvalue(values)
    domain_directions = sum(value > 0 for value in values)
    all_positive = domain_directions == len(values)
    positive = p_value <= float(alpha) and mean_delta >= float(margin) and all_positive
    return {
        "status": "positive" if positive else "null",
        "domain_count": len(values),
        "mean_delta": mean_delta,
        "p_value": p_value,
        "margin_threshold": float(margin),
        "alpha": float(alpha),
        "positive_domain_count": domain_directions,
        "all_domains_positive": all_positive,
        "primary_is_single_fixed_endpoint": True,
        "sensitivity_cannot_replace_primary": True,
    }


def validate_analysis_result(result: dict[str, Any]) -> None:
    """Validate the immutable statistical envelope and forbid claim promotion."""
    if not isinstance(result, dict) or result.get("status") not in TERMINAL_STATUSES:
        raise Exp002AnalysisError("invalid EXP-002 analysis terminal result")
    if result.get("status") in {"positive", "null"}:
        for field in ("domain_count", "mean_delta", "p_value", "positive_domain_count"):
            if field not in result:
                raise Exp002AnalysisError(f"missing statistical field: {field}")
    if result.get("status") == "positive" and result.get("sensitivity_cannot_replace_primary") is not True:
        raise Exp002AnalysisError("positive result lacks primary/sensitivity separation")


__all__ = ["DEFAULT_ALPHA", "DEFAULT_MARGIN", "DEFAULT_MIN_DOMAINS", "Exp002AnalysisError", "exact_sign_flip_pvalue", "evaluate_transfer", "validate_analysis_result"]
