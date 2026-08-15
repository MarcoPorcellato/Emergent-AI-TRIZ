"""Deterministic exact+simulation power calibration for the A0-R1 primary endpoint."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any, Mapping


class A0R1PowerError(RuntimeError):
    """Raised when the preregistered A0-R1 power contract is invalid."""


EPISTEMIC = {
    "empirical": True,
    "scientific_status": "exploratory",
    "evidence_eligible": False,
    "expert_validated": False,
    "claim_ids": [],
}

CONSTANTS = {
    "method": "exact_primary_endpoint",
    "expected_seed": 20260815,
    "expected_selected_family_count": 24,
    "expected_selected_families_per_domain": 4,
    "expected_domains": 6,
    "expected_permutation_budget": 999,
    "expected_multiplicity": 1,
    "expected_threshold": 17,
    "expected_alpha": 0.05,
    "expected_power": 0.8,
    "expected_target_effect": 0.3,
    "exact_resolution_tolerance": 0.01,
    "simulation_trials": 100000,
}


def calibrate_a0r1_power(protocol_path: str | Path) -> dict[str, Any]:
    protocol_file = Path(protocol_path)
    payload = _read_protocol(protocol_file)
    _validate_protocol(payload)

    n = _as_int(payload["calibration"]["selected_family_count"])
    threshold = _as_int(payload["thresholds"]["critical_successes"])
    p0 = 0.5
    p1 = 0.5 + _as_float(payload["calibration"]["target_effect_size"])
    permutation_budget = _as_int(payload["calibration"]["selected_permutation_budget"])
    minimum_attainable_p = 1.0 / (permutation_budget + 1)

    exact_fpr = _binomial_tail(n, p0, threshold)
    exact_power = _binomial_tail(n, p1, threshold)
    mde = _minimum_detectable_effect(n, threshold, _as_float(payload["calibration"]["power"]))

    # Deterministic Monte Carlo confirmation.
    simulation_seed = CONSTANTS["expected_seed"]
    simulation_trials = CONSTANTS["simulation_trials"]
    empirical_null, empirical_power = _simulate_confirmation(
        n=n,
        threshold=threshold,
        null_p=p0,
        target_p=p1,
        trials=simulation_trials,
        seed=simulation_seed,
    )

    selected = {
        "families_per_domain": _as_int(payload["calibration"]["selected_families_per_domain"]),
        "family_count": n,
        "permutation_budget": permutation_budget,
        "critical_successes": threshold,
        "minimum_attainable_p": minimum_attainable_p,
        "exact_false_positive_rate": exact_fpr,
        "exact_power_at_target_success_probability": exact_power,
        "minimum_detectable_effect": mde,
        "empirical_null_fpr": empirical_null,
        "empirical_target_power": empirical_power,
        "exact_vs_empirical_tolerance": CONSTANTS["exact_resolution_tolerance"],
    }

    passes_exact = (
        exact_fpr <= CONSTANTS["expected_alpha"]
        and exact_power >= CONSTANTS["expected_power"]
        and mde <= CONSTANTS["expected_target_effect"]
    )
    passes_empirical = (
        abs(empirical_null - exact_fpr) <= CONSTANTS["exact_resolution_tolerance"]
        and abs(empirical_power - exact_power) <= CONSTANTS["exact_resolution_tolerance"]
        and minimum_attainable_p <= CONSTANTS["expected_alpha"]
    )
    passes = bool(passes_exact and passes_empirical)

    return {
        "artifact_class": "a0r1-power-calibration",
        "protocol_id": payload.get("protocol_id"),
        "protocol_status": payload.get("status") or payload.get("protocol_status"),
        "status": "pass" if passes else "failed",
        "method": CONSTANTS["method"],
        "selection_mode": "deterministic_simulation",
        "multiplicity": {"layers": 1, "token_sites": 1, "total": 1},
        "targets": {
            "families_per_domain": _as_int(payload["calibration"]["selected_families_per_domain"]),
            "family_level_critical_successes": threshold,
            "family_success_probability_under_null": p0,
            "family_success_probability_under_target": p1,
        },
        "simulation": {
            "seed": simulation_seed,
            "trials": simulation_trials,
            "minimum_resolvable_p": minimum_attainable_p,
            "empirical_resolution": 1.0 / simulation_trials,
            "passes_empirical_check": passes_empirical,
            "min_attainable_p": minimum_attainable_p,
        },
        "selected": selected,
        "model_output_accessed": False,
        "sealed_targets_accessed": False,
        **EPISTEMIC,
    }


def _simulate_confirmation(
    *,
    n: int,
    threshold: int,
    null_p: float,
    target_p: float,
    trials: int,
    seed: int,
) -> tuple[float, float]:
    generator = random.Random(seed)
    null_hits = 0
    target_hits = 0

    for _ in range(trials):
        null_successes = 0
        target_successes = 0
        for _ in range(n):
            if generator.random() < null_p:
                null_successes += 1
            if generator.random() < target_p:
                target_successes += 1
        null_hits += null_successes >= threshold
        target_hits += target_successes >= threshold

    return null_hits / trials, target_hits / trials


def _minimum_detectable_effect(n: int, threshold: int, target_power: float) -> float:
    low, high = 0.0, 0.5
    for _ in range(64):
        midpoint = (low + high) / 2.0
        if _binomial_tail(n, 0.5 + midpoint, threshold) >= target_power:
            high = midpoint
        else:
            low = midpoint
    return high


def _binomial_tail(n: int, p: float, threshold: int) -> float:
    return math.fsum(
        math.comb(n, successes) * (p**successes) * ((1.0 - p) ** (n - successes))
        for successes in range(threshold, n + 1)
    )


def _read_protocol(protocol_file: Path) -> dict[str, Any]:
    try:
        payload = json.loads(protocol_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R1PowerError(f"cannot load protocol: {exc}") from exc
    if not isinstance(payload, dict):
        raise A0R1PowerError("protocol must be an object")
    return payload


def _as_int(value: Any, *, field: str | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise A0R1PowerError(f"{field or 'value'} must be an integer")
    return value


def _as_float(value: Any, *, field: str | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise A0R1PowerError(f"{field or 'value'} must be numeric")
    return float(value)


def _coerce_status(payload: Mapping[str, Any]) -> str:
    status = str(payload.get("status", "")).strip()
    protocol_status = str(payload.get("protocol_status", "")).strip()
    if status and protocol_status and status != protocol_status:
        raise A0R1PowerError("status and protocol_status must match")
    return status or protocol_status


def _validate_protocol(payload: Mapping[str, Any]) -> None:
    status = _coerce_status(payload).strip().lower()
    if not status:
        raise A0R1PowerError("protocol must define status or protocol_status as planned")
    if status != "planned":
        raise A0R1PowerError("protocol status must be planned")

    _validate_block(payload.get("primary_endpoint"), "primary_endpoint")
    _validate_block(payload.get("thresholds"), "thresholds")
    _validate_block(payload.get("calibration"), "calibration")

    method = str(payload["calibration"].get("method", ""))
    if method != "exact_family_blocked_binomial_primary_endpoint":
        raise A0R1PowerError("calibration method must be exact_family_blocked_binomial_primary_endpoint")

    multiplicity = _as_int(payload["primary_endpoint"].get("multiplicity"), field="primary_endpoint.multiplicity")
    if multiplicity != CONSTANTS["expected_multiplicity"]:
        raise A0R1PowerError("primary endpoint multiplicity must be exactly 1")

    selected_families_per_domain = _as_int(
        payload["calibration"].get("selected_families_per_domain"), field="calibration.selected_families_per_domain"
    )
    selected_family_count = _as_int(payload["calibration"].get("selected_family_count"), field="calibration.selected_family_count")
    selected_permutation_budget = _as_int(
        payload["calibration"].get("selected_permutation_budget"), field="calibration.selected_permutation_budget"
    )
    deterministic_seed = _as_int(
        payload["calibration"].get("deterministic_seed"), field="calibration.deterministic_seed"
    )
    threshold = _as_int(payload["thresholds"].get("critical_successes"), field="thresholds.critical_successes")
    family_successes_at_least = _as_int(
        payload["thresholds"].get("family_successes_at_least"), field="thresholds.family_successes_at_least"
    )
    primary_permutation_p_at_most = _as_float(
        payload["thresholds"].get("primary_permutation_p_at_most"), field="thresholds.primary_permutation_p_at_most"
    )
    max_fpr = _as_float(payload["calibration"].get("maximum_false_positive_rate"), field="calibration.maximum_false_positive_rate")
    target_power = _as_float(payload["calibration"].get("power"), field="calibration.power")
    target_effect = _as_float(payload["calibration"].get("target_effect_size"), field="calibration.target_effect_size")
    calibration_mde = _as_float(payload["calibration"].get("minimum_detectable_effect"), field="calibration.minimum_detectable_effect")

    if selected_families_per_domain <= 0 or selected_family_count <= 0 or threshold <= 0:
        raise A0R1PowerError("calibration sizes must be positive")

    if selected_permutation_budget != CONSTANTS["expected_permutation_budget"]:
        raise A0R1PowerError("calibration.selected_permutation_budget must be 999")
    if deterministic_seed != CONSTANTS["expected_seed"]:
        raise A0R1PowerError("calibration.deterministic_seed must be 20260815")
    if selected_family_count != CONSTANTS["expected_selected_family_count"]:
        raise A0R1PowerError("calibration.selected_family_count must be 24")
    if selected_families_per_domain != CONSTANTS["expected_selected_families_per_domain"]:
        raise A0R1PowerError("calibration.selected_families_per_domain must be 4")
    if threshold != CONSTANTS["expected_threshold"] or family_successes_at_least != threshold:
        raise A0R1PowerError("thresholds critical/family successes must be 17")

    if selected_family_count % selected_families_per_domain != 0:
        raise A0R1PowerError(
            "calibration.selected_family_count must equal selected_families_per_domain * len(neutral_domains)"
        )
    derived_domains = selected_family_count // selected_families_per_domain
    if derived_domains != CONSTANTS["expected_domains"]:
        raise A0R1PowerError("derived number of neutral domains must be 6")

    if not math.isclose(primary_permutation_p_at_most, 0.05, rel_tol=0.0, abs_tol=0.0):
        raise A0R1PowerError("thresholds.primary_permutation_p_at_most must be 0.05")
    if not math.isclose(max_fpr, CONSTANTS["expected_alpha"], rel_tol=0.0, abs_tol=0.0):
        raise A0R1PowerError("calibration.maximum_false_positive_rate must be 0.05")
    if not math.isclose(target_power, CONSTANTS["expected_power"], rel_tol=0.0, abs_tol=0.0):
        raise A0R1PowerError("calibration.power must be 0.8")
    if not math.isclose(target_effect, CONSTANTS["expected_target_effect"], rel_tol=0.0, abs_tol=0.0):
        raise A0R1PowerError("calibration.target_effect_size must be 0.3")
    if not (0.0 < calibration_mde <= CONSTANTS["expected_target_effect"]):
        raise A0R1PowerError("calibration.minimum_detectable_effect must be >0 and <=0.3")


def _validate_block(block: Any, name: str) -> None:
    if not isinstance(block, Mapping):
        raise A0R1PowerError(f"protocol must define {name} as an object")
