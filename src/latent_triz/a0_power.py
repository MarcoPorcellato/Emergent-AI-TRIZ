"""Exact dependency-free power calibration for Phase A0."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping


class A0PowerError(RuntimeError):
    """Raised when the preregistered calibration contract is invalid."""


def _binomial_tail(n: int, probability: float, threshold: int) -> float:
    return math.fsum(
        math.comb(n, successes)
        * probability**successes
        * (1.0 - probability) ** (n - successes)
        for successes in range(threshold, n + 1)
    )


def _critical_successes(n: int, site_alpha: float) -> int | None:
    return next(
        (threshold for threshold in range(n + 1) if _binomial_tail(n, 0.5, threshold) <= site_alpha),
        None,
    )


def _minimum_detectable_effect(n: int, threshold: int, target_power: float) -> float | None:
    if _binomial_tail(n, 1.0, threshold) < target_power:
        return None
    low, high = 0.0, 0.5
    for _ in range(64):
        midpoint = (low + high) / 2.0
        if _binomial_tail(n, 0.5 + midpoint, threshold) >= target_power:
            high = midpoint
        else:
            low = midpoint
    return high


def _number(mapping: Mapping[str, Any], key: str) -> float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise A0PowerError(f"{key} must be numeric")
    return float(value)


def calibrate_a0_power(protocol_path: str | Path) -> dict[str, Any]:
    try:
        protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0PowerError(f"cannot load protocol: {exc}") from exc
    if not isinstance(protocol, Mapping):
        raise A0PowerError("protocol must be an object")
    rule = protocol.get("predeclared_calibration_rule")
    domains = protocol.get("neutral_domains")
    layers = protocol.get("preregistered_layers")
    token_sites = protocol.get("token_sites")
    if not isinstance(rule, Mapping):
        raise A0PowerError("protocol must define predeclared_calibration_rule")
    if not isinstance(domains, list) or len(domains) != 6:
        raise A0PowerError("protocol must define exactly six domains")
    if not isinstance(layers, list) or not layers or not isinstance(token_sites, list) or not token_sites:
        raise A0PowerError("layers and token sites must be preregistered")

    families = sorted({int(value) for value in rule.get("candidate_families_per_domain", [])})
    budgets = sorted({int(value) for value in rule.get("permutation_budgets", [])})
    if not families or not budgets or min(families + budgets) <= 0:
        raise A0PowerError("calibration candidates must be positive")
    target_power = _number(rule, "target_power")
    maximum_fpr = _number(rule, "maximum_false_positive_rate")
    target_effect = _number(rule, "target_effect_size")
    if not 0.0 < target_power <= 1.0 or not 0.0 < maximum_fpr < 1.0 or not 0.0 <= target_effect <= 0.5:
        raise A0PowerError("invalid power, FPR, or effect target")

    multiplicity = len(layers) * len(token_sites)
    site_alpha = maximum_fpr / multiplicity
    candidates: list[dict[str, Any]] = []
    for per_domain in families:
        family_count = per_domain * len(domains)
        critical = _critical_successes(family_count, site_alpha)
        for budget in budgets:
            row: dict[str, Any] = {
                "families_per_domain": per_domain,
                "family_count": family_count,
                "permutation_budget": budget,
                "minimum_attainable_p": 1.0 / (budget + 1),
                "site_alpha": site_alpha,
                "critical_successes": critical,
            }
            if critical is None:
                row.update({
                    "exact_site_false_positive_rate": None,
                    "exact_familywise_false_positive_rate": None,
                    "exact_power_at_target_effect": 0.0,
                    "minimum_detectable_effect": None,
                    "passes": False,
                    "failure_reason": "no exact critical value exists for this sample size",
                })
            else:
                site_fpr = _binomial_tail(family_count, 0.5, critical)
                familywise_fpr = 1.0 - (1.0 - site_fpr) ** multiplicity
                power = _binomial_tail(family_count, 0.5 + target_effect, critical)
                mde = _minimum_detectable_effect(family_count, critical, target_power)
                row.update({
                    "exact_site_false_positive_rate": site_fpr,
                    "exact_familywise_false_positive_rate": familywise_fpr,
                    "exact_power_at_target_effect": power,
                    "minimum_detectable_effect": mde,
                    "passes": (
                        row["minimum_attainable_p"] <= site_alpha
                        and familywise_fpr <= maximum_fpr
                        and power >= target_power
                        and mde is not None
                        and mde <= target_effect
                    ),
                })
            candidates.append(row)

    selected_row = next((row for row in candidates if row["passes"]), None)
    selected = None if selected_row is None else {
        key: selected_row[key]
        for key in (
            "families_per_domain",
            "family_count",
            "permutation_budget",
            "critical_successes",
            "minimum_detectable_effect",
        )
    }
    scenario_row = selected_row or next(
        (row for row in reversed(candidates) if row["critical_successes"] is not None), None
    )
    confounds = {}
    if scenario_row is not None:
        confounds = {
            name: {
                "assumed_macro_f1_margin": margin,
                "raw_rejection_probability": _binomial_tail(
                    scenario_row["family_count"], 0.5 + margin, scenario_row["critical_successes"]
                ),
                "interpretation": "must be caught by the separate surface-shortcut gate",
            }
            for name, margin in (
                ("lexical_confound_only", 0.10),
                ("domain_confound_only", 0.07),
                ("template_confound_only", 0.06),
            )
        }

    return {
        "artifact_class": "a0-power-calibration",
        "protocol_id": protocol.get("protocol_id"),
        "empirical": True,
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "method": "exact_family_blocked_binomial_max_statistic",
        "effect_definition": "family_level_macro_f1_margin_over_balanced_chance",
        "multiplicity": {"layers": len(layers), "token_sites": len(token_sites), "total": multiplicity},
        "targets": {"power": target_power, "maximum_false_positive_rate": maximum_fpr, "effect_size": target_effect},
        "null_signal": {"family_success_probability": 0.5},
        "positive_signal": {"family_success_probability": 0.5 + target_effect},
        "confound_only_scenarios": confounds,
        "candidates": candidates,
        "selected": selected,
        "status": "pass" if selected is not None else "failed_no_feasible_candidate",
    }
