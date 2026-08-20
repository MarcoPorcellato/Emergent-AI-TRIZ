"""Deterministic no-model power calibration for EXP-002C domain selection."""
from __future__ import annotations

from collections.abc import Sequence
import math
from typing import Any


class Exp002PowerError(ValueError):
    """Raised when a preregistered power calibration is malformed."""


def _binomial_at_least(n: int, probability: float, threshold: int) -> float:
    return sum(math.comb(n, k) * probability**k * (1.0 - probability) ** (n - k) for k in range(threshold, n + 1))


def calibrate_domain_count(
    candidate_domains: Sequence[int], *, minimum_domains: int = 8,
    target_power: float = 0.80, expected_positive_probability: float = 0.98,
) -> dict[str, Any]:
    """Select the smallest preregistered domain count meeting a fixed power rule.

    The rule models the frozen all-domain-positive endpoint only; it does not
    inspect model output, target labels, or observed effect sizes.
    """
    if isinstance(candidate_domains, (str, bytes, bytearray)) or not isinstance(candidate_domains, Sequence) or not candidate_domains:
        raise Exp002PowerError("candidate_domains must be non-empty")
    candidates = sorted(set(candidate_domains))
    if any(isinstance(value, bool) or not isinstance(value, int) or value < minimum_domains for value in candidates):
        raise Exp002PowerError("candidate domain counts are below the fixed minimum")
    if not 0.0 < target_power < 1.0 or not 0.5 < expected_positive_probability <= 1.0:
        raise Exp002PowerError("power assumptions are outside the declared range")
    rows = []
    for domains in candidates:
        power = _binomial_at_least(domains, expected_positive_probability, domains)
        rows.append({"domain_count": domains, "positive_direction_probability": expected_positive_probability, "power": power, "meets_target": power >= target_power})
    selected = next((row for row in rows if row["meets_target"]), None)
    if selected is None or selected["domain_count"] < minimum_domains:
        raise Exp002PowerError("candidate domain counts do not meet the fixed power target")
    return {
        "artifact_class": "exp002-power-calibration",
        "calibration_id": "exp002c-power-v1.0.0",
        "status": "pass",
        "method": "all_domain_positive_binomial_power",
        "minimum_domains": minimum_domains,
        "target_power": target_power,
        "expected_positive_probability": expected_positive_probability,
        "candidates": rows,
        "selected_domain_count": selected["domain_count"],
        "selected_power": selected["power"],
        "model_access": False,
        "sealed_target_access": False,
        "scientific_status": "exploratory",
        "claim_ids": [],
    }


def validate_calibration(receipt: dict[str, Any]) -> None:
    """Validate a completed calibration receipt without recomputing model data."""
    required = ("artifact_class", "calibration_id", "status", "selected_domain_count", "selected_power", "model_access", "sealed_target_access", "claim_ids")
    if not isinstance(receipt, dict) or any(field not in receipt for field in required):
        raise Exp002PowerError("calibration receipt is incomplete")
    if receipt["artifact_class"] != "exp002-power-calibration" or receipt["calibration_id"] != "exp002c-power-v1.0.0" or receipt["status"] != "pass":
        raise Exp002PowerError("calibration identity/status drift")
    if receipt["model_access"] is not False or receipt["sealed_target_access"] is not False or receipt["claim_ids"] != []:
        raise Exp002PowerError("calibration crossed a forbidden boundary")
    if not isinstance(receipt["selected_domain_count"], int) or receipt["selected_domain_count"] < 8 or not math.isfinite(float(receipt["selected_power"])) or float(receipt["selected_power"]) < float(receipt["target_power"]):
        raise Exp002PowerError("selected calibration result does not meet target")


__all__ = ["Exp002PowerError", "calibrate_domain_count", "validate_calibration"]
