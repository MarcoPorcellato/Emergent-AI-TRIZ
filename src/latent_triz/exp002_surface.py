"""Model-independent EXP-002 response-surface and permutation primitives.

These functions operate only on already materialised finite score mappings. They
never tokenize, load a model, generate text, or open a target/key file. A later
execution adapter may supply scores through the same narrow interfaces.
"""
from __future__ import annotations

from itertools import permutations
import math
from collections.abc import Mapping, Sequence
from typing import Any, Callable


class Exp002SurfaceError(ValueError):
    """Raised when a response-surface observation is not protocol-safe."""


LABELS = ("A", "B", "C", "D")
CONDITIONS = (
    "original_abcd",
    "balanced_cyclic_label_permutations",
    "all_24_label_permutations",
    "numeric_labels",
    "matched_neutral_symbols",
    "label_free_candidate_description_scoring",
    "answer_boundary_variants",
)


def validate_score_mapping(scores: Mapping[str, Any]) -> dict[str, float]:
    """Copy an exact A/B/C/D finite score vector."""
    if not isinstance(scores, Mapping) or set(scores) != set(LABELS):
        raise Exp002SurfaceError("scores must contain exactly A/B/C/D")
    copied: dict[str, float] = {}
    for label in LABELS:
        value = scores[label]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise Exp002SurfaceError(f"score for {label} is not finite")
        copied[label] = float(value)
    return copied


def top_label(scores: Mapping[str, Any]) -> str:
    """Return a deterministic top label; ties resolve in A/B/C/D order."""
    copied = validate_score_mapping(scores)
    return max(LABELS, key=lambda label: copied[label])


def label_entropy(labels: Sequence[str]) -> float:
    """Calculate Shannon entropy for observed top labels."""
    counts = {label: 0 for label in LABELS}
    for label in labels:
        if label not in counts:
            raise Exp002SurfaceError("unknown top label")
        counts[label] += 1
    total = len(labels)
    if total == 0:
        return 0.0
    return -sum((count / total) * math.log2(count / total) for count in counts.values() if count)


def cyclic_permutations() -> tuple[dict[str, str], ...]:
    """Return the four balanced cyclic observed-label -> semantic-label maps."""
    return tuple(
        {observed: LABELS[(index + shift) % len(LABELS)] for index, observed in enumerate(LABELS)}
        for shift in range(len(LABELS))
    )


def all_label_permutations() -> tuple[dict[str, str], ...]:
    """Return all 24 deterministic observed-label -> semantic-label maps."""
    return tuple(
        {observed: semantic for observed, semantic in zip(LABELS, permutation)}
        for permutation in permutations(LABELS)
    )


def remap_scores(scores: Mapping[str, Any], observed_to_semantic: Mapping[str, str]) -> dict[str, float]:
    """Move observed label scores into semantic option slots."""
    copied = validate_score_mapping(scores)
    if set(observed_to_semantic) != set(LABELS) or set(observed_to_semantic.values()) != set(LABELS):
        raise Exp002SurfaceError("permutation must be a bijection over A/B/C/D")
    remapped = {semantic: copied[observed] for observed, semantic in observed_to_semantic.items()}
    return validate_score_mapping(remapped)


def adjust_label_prior(scores: Mapping[str, Any], prior: Mapping[str, Any]) -> dict[str, float]:
    """Subtract a predeclared log-prior from each label score."""
    copied = validate_score_mapping(scores)
    prior_copy = validate_score_mapping(prior)
    return {label: copied[label] - prior_copy[label] for label in LABELS}


def score_candidate_descriptions(
    scorer: Callable[[str], float], candidates: Sequence[str],
) -> tuple[float, ...]:
    """Score complete candidate descriptions through an injected pure scorer."""
    if not candidates or any(not isinstance(candidate, str) or not candidate.strip() for candidate in candidates):
        raise Exp002SurfaceError("candidate descriptions must be non-empty")
    values = tuple(float(scorer(candidate)) for candidate in candidates)
    if any(not math.isfinite(value) for value in values):
        raise Exp002SurfaceError("candidate description scores must be finite")
    return values


def summarize_surface(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize record-level top labels and score range without target access."""
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        raise Exp002SurfaceError("surface rows must be a sequence")
    tops: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping) or "scores" not in row:
            raise Exp002SurfaceError("surface row must contain scores")
        tops.append(top_label(row["scores"]))
    return {
        "record_count": len(tops),
        "top_label_counts": {label: tops.count(label) for label in LABELS},
        "top_label_entropy_bits": label_entropy(tops),
        "conditions_observed": sorted({str(row.get("condition")) for row in rows if row.get("condition") is not None}),
    }


def build_surface_schedule(record_ids: Sequence[str]) -> list[dict[str, Any]]:
    """Build the deterministic response-surface schedule without scores."""
    if isinstance(record_ids, (str, bytes, bytearray)) or not isinstance(record_ids, Sequence) or not record_ids:
        raise Exp002SurfaceError("record_ids must be a non-empty sequence")
    if any(not isinstance(record_id, str) or not record_id.strip() for record_id in record_ids):
        raise Exp002SurfaceError("record IDs must be non-empty text")
    identity = {label: label for label in LABELS}
    numeric = {str(index + 1): label for index, label in enumerate(LABELS)}
    neutral = {symbol: label for symbol, label in zip(("x", "y", "z", "w"), LABELS)}
    mappings: list[tuple[str, Mapping[str, str]]] = [("original_abcd", identity)]
    mappings.extend(("balanced_cyclic_label_permutations", mapping) for mapping in cyclic_permutations())
    mappings.extend(("all_24_label_permutations", mapping) for mapping in all_label_permutations())
    mappings.extend([("numeric_labels", numeric), ("matched_neutral_symbols", neutral)])
    mappings.extend((("label_free_candidate_description_scoring", {}), ("answer_boundary_variants", {})))
    schedule: list[dict[str, Any]] = []
    for record_id in record_ids:
        for condition, mapping in mappings:
            schedule.append({"record_id": record_id, "condition": condition, "mapping": dict(mapping)})
    return schedule


def classify_measurement_surface(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the preregistered robust/artifact decision without model access."""
    required = ("balanced_complete", "all_permutations_complete", "label_free_agreement", "semantic_invariance")
    if not isinstance(observation, Mapping) or any(not isinstance(observation.get(field), bool) for field in required):
        raise Exp002SurfaceError("measurement-surface observation is incomplete")
    if not observation["balanced_complete"]:
        return {"status": "non_interpretable", "reason": "balanced_screen_incomplete", "claim_ids": []}
    if not observation["all_permutations_complete"]:
        return {"status": "non_interpretable", "reason": "permutation_screen_incomplete", "claim_ids": []}
    if not observation["label_free_agreement"] or not observation["semantic_invariance"]:
        return {"status": "measurement_artifact_supported", "reason": "surface_invariance_failed", "claim_ids": []}
    return {"status": "measurement_robust", "reason": "balanced_permutations_and_label_free_agree", "claim_ids": []}


def evaluate_surface_conditions(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize preregistered surface coverage and semantic invariance.

    ``semantic_choice`` is an option identity supplied by an already completed
    scorer; it is not an answer key. This function never opens targets or
    interprets correctness.
    """
    if isinstance(rows, (str, bytes, bytearray)) or not isinstance(rows, Sequence) or not rows:
        raise Exp002SurfaceError("surface observations must be non-empty")
    grouped: dict[str, dict[str, list[Mapping[str, Any]]]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("record_id"), str) or not row["record_id"].strip():
            raise Exp002SurfaceError("surface observation identity is malformed")
        condition = row.get("condition")
        if condition not in CONDITIONS:
            raise Exp002SurfaceError("surface observation condition is unknown")
        choice = row.get("semantic_choice")
        if not isinstance(choice, str) or not choice.strip():
            raise Exp002SurfaceError("semantic_choice is required")
        grouped.setdefault(row["record_id"], {}).setdefault(condition, []).append(row)
    required = {"original_abcd", "balanced_cyclic_label_permutations", "all_24_label_permutations", "label_free_candidate_description_scoring"}
    balanced_complete = True
    all_complete = True
    label_free_matches = 0
    semantic_matches = 0
    total_semantic = 0
    for record_id, conditions in grouped.items():
        if not required.issubset(conditions):
            raise Exp002SurfaceError(f"record lacks required response surfaces: {record_id}")
        original = conditions["original_abcd"]
        label_free = conditions["label_free_candidate_description_scoring"]
        if len(original) != 1 or len(label_free) != 1:
            raise Exp002SurfaceError(f"original/label-free surface must be unique: {record_id}")
        balanced_complete &= len(conditions["balanced_cyclic_label_permutations"]) == 4
        all_complete &= len(conditions["all_24_label_permutations"]) == 24
        label_free_matches += int(label_free[0]["semantic_choice"] == original[0]["semantic_choice"])
        for condition in ("balanced_cyclic_label_permutations", "all_24_label_permutations"):
            semantic_matches += sum(row["semantic_choice"] == original[0]["semantic_choice"] for row in conditions[condition])
            total_semantic += len(conditions[condition])
    record_count = len(grouped)
    label_free_rate = label_free_matches / record_count
    semantic_rate = semantic_matches / total_semantic if total_semantic else 0.0
    decision = classify_measurement_surface({
        "balanced_complete": balanced_complete,
        "all_permutations_complete": all_complete,
        "label_free_agreement": label_free_rate == 1.0,
        "semantic_invariance": semantic_rate == 1.0,
    })
    return {
        "record_count": record_count,
        "balanced_rows_per_record": 4 if balanced_complete else None,
        "permutation_rows_per_record": 24 if all_complete else None,
        "label_free_agreement_rate": label_free_rate,
        "semantic_invariance_rate": semantic_rate,
        "observation": decision,
        "claim_ids": [],
    }


__all__ = [
    "CONDITIONS", "Exp002SurfaceError", "LABELS", "adjust_label_prior", "all_label_permutations",
    "build_surface_schedule", "classify_measurement_surface", "evaluate_surface_conditions",
    "cyclic_permutations", "label_entropy", "remap_scores", "score_candidate_descriptions",
    "summarize_surface", "top_label", "validate_score_mapping",
]
