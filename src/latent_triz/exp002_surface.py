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


__all__ = [
    "CONDITIONS", "Exp002SurfaceError", "LABELS", "adjust_label_prior", "all_label_permutations",
    "cyclic_permutations", "label_entropy", "remap_scores", "score_candidate_descriptions",
    "summarize_surface", "top_label", "validate_score_mapping",
]
