"""Pure, no-model primary analysis for the EXP-001 R3 protocol.

This module receives already validated scalar response scores.  It neither
loads a model nor reads target data; the runner owns the one target-read
boundary and supplies the scored units only after its receipt checks pass.
"""
from __future__ import annotations

import itertools
import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any


class Exp001AnalysisError(ValueError):
    """Raised when a primary input violates the frozen analysis contract."""


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise Exp001AnalysisError("bootstrap distribution is empty")
    ordered = sorted(values)
    index = int(math.floor((len(ordered) - 1) * probability))
    return ordered[index]


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Exp001AnalysisError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise Exp001AnalysisError(f"{field} must be finite")
    return result


def analyze_primary(
    scored_units: Sequence[Mapping[str, Any]],
    analysis_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate the frozen non-pooled primary with exact domain sign flips."""
    primary = analysis_plan.get("primary")
    uncertainty = analysis_plan.get("uncertainty")
    if not isinstance(primary, Mapping) or not isinstance(uncertainty, Mapping):
        raise Exp001AnalysisError("analysis plan lacks primary or uncertainty contract")
    required_units = primary.get("required_units")
    required_domains = primary.get("required_domains")
    required_families = primary.get("required_problem_families_per_domain")
    required_replicates = primary.get("required_replicates_per_problem_family")
    if (required_units, required_domains, required_families, required_replicates) != (24, 6, 2, 2):
        raise Exp001AnalysisError("analysis plan primary cardinality drift")
    if primary.get("test") != "exact_two_sided_domain_sign_flip_permutation":
        raise Exp001AnalysisError("analysis plan test drift")
    if primary.get("permutation_count") != 64 or primary.get("alpha") != 0.05:
        raise Exp001AnalysisError("analysis plan permutation or alpha drift")
    if len(scored_units) != required_units:
        raise Exp001AnalysisError("primary unit count drift")

    seen_units: set[str] = set()
    grouped: dict[str, list[tuple[str, int, float]]] = defaultdict(list)
    families: dict[str, set[str]] = defaultdict(set)
    replicates: dict[tuple[str, str], set[int]] = defaultdict(set)
    for record in scored_units:
        if not isinstance(record, Mapping):
            raise Exp001AnalysisError("primary record must be an object")
        unit_id = record.get("unit_id")
        domain = record.get("domain")
        family = record.get("problem_family")
        replicate = record.get("replicate")
        if not all(isinstance(value, str) and value for value in (unit_id, domain, family)):
            raise Exp001AnalysisError("primary identity fields are invalid")
        if not isinstance(replicate, int) or isinstance(replicate, bool) or replicate not in {1, 2}:
            raise Exp001AnalysisError("replicate must be 1 or 2")
        if unit_id in seen_units:
            raise Exp001AnalysisError("duplicate primary unit")
        seen_units.add(unit_id)
        delta = _finite_number(record.get("blinded_score"), "blinded_score") - _finite_number(
            record.get("lexical_control_score"), "lexical_control_score"
        )
        grouped[domain].append((family, replicate, delta))
        families[domain].add(family)
        if replicate in replicates[(domain, family)]:
            raise Exp001AnalysisError("duplicate domain/family replicate")
        replicates[(domain, family)].add(replicate)

    if len(grouped) != required_domains:
        raise Exp001AnalysisError("primary domain count drift")
    domain_deltas: dict[str, float] = {}
    for domain, values in grouped.items():
        if len(values) != required_families * required_replicates or len(families[domain]) != required_families:
            raise Exp001AnalysisError("domain family support drift")
        for family in families[domain]:
            if replicates[(domain, family)] != {1, 2}:
                raise Exp001AnalysisError("domain replicate support drift")
        domain_deltas[domain] = sum(delta for _, _, delta in values) / len(values)

    ordered_domains = sorted(domain_deltas)
    observed = sum(domain_deltas[domain] for domain in ordered_domains) / len(ordered_domains)
    signs = itertools.product((-1.0, 1.0), repeat=required_domains)
    null_distribution = [
        sum(sign * domain_deltas[domain] for sign, domain in zip(signs_row, ordered_domains)) / required_domains
        for signs_row in signs
    ]
    two_sided_p = sum(abs(value) >= abs(observed) for value in null_distribution) / len(null_distribution)
    resamples = uncertainty.get("bootstrap_resamples")
    seed = uncertainty.get("bootstrap_seed")
    if resamples != 10000 or not isinstance(seed, int) or isinstance(seed, bool):
        raise Exp001AnalysisError("bootstrap contract drift")
    rng = random.Random(seed)
    bootstrap = [
        sum(domain_deltas[rng.choice(ordered_domains)] for _ in ordered_domains) / required_domains
        for _ in range(resamples)
    ]
    ci_lower = _quantile(bootstrap, 0.025)
    ci_upper = _quantile(bootstrap, 0.975)
    all_positive = all(value > 0 for value in domain_deltas.values())
    positive = (
        two_sided_p <= primary["alpha"]
        and observed > 0
        and all_positive
        and ci_lower > 0
    )
    return {
        "status": "positive" if positive else "null",
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "claim_ids": [],
        "primary": {
            "unit_count": len(scored_units),
            "domain_count": len(ordered_domains),
            "domain_deltas": {domain: domain_deltas[domain] for domain in ordered_domains},
            "mean_domain_delta": observed,
            "two_sided_exact_p": two_sided_p,
            "bootstrap_95_ci": [ci_lower, ci_upper],
            "all_domain_directions_positive": all_positive,
            "permutation_count": len(null_distribution),
        },
    }
