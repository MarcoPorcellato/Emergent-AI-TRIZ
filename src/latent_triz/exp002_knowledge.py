"""Target-injected metrics for EXP-002 direct TRIZ knowledge probes.

The answer key is supplied explicitly by a later analysis boundary. This module
does not know where keys are stored and cannot open them; it only scores copied
outcomes against an injected mapping.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any


class Exp002KnowledgeError(ValueError):
    """Raised when direct-question outcomes are incomplete or malformed."""


_ABSTENTION_WORDS = {
    "abstain", "abstention", "uncertain", "insufficient_information",
    "not_established", "unsupported",
}


def _key_info(key: Any) -> tuple[Any, bool]:
    if isinstance(key, Mapping):
        return key.get("answer"), bool(key.get("unsupported", False))
    return key, isinstance(key, str) and key.strip().lower() in _ABSTENTION_WORDS


def _is_abstention(row: Mapping[str, Any]) -> bool:
    prediction = row.get("prediction")
    return bool(row.get("abstained")) or (
        isinstance(prediction, str) and prediction.strip().lower() in _ABSTENTION_WORDS
    )


def evaluate_direct_questions(
    outcomes: Sequence[Mapping[str, Any]], answer_key: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute per-module factual and abstention metrics from injected keys."""
    if not isinstance(answer_key, Mapping) or not answer_key:
        raise Exp002KnowledgeError("answer key must be supplied at the analysis boundary")
    rows = list(outcomes)
    if not rows:
        raise Exp002KnowledgeError("outcomes cannot be empty")
    by_module: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("question_id"), str) or not isinstance(row.get("module"), str):
            raise Exp002KnowledgeError("outcome identity is malformed")
        question_id = row["question_id"]
        if question_id not in answer_key:
            raise Exp002KnowledgeError(f"missing answer key for {question_id}")
        if "prediction" not in row or not isinstance(row.get("abstained"), bool):
            raise Exp002KnowledgeError(f"outcome fields are incomplete: {question_id}")
        by_module.setdefault(row["module"], []).append(row)

    modules: dict[str, Any] = {}
    for module, module_rows in sorted(by_module.items()):
        scored = [row for row in module_rows if row.get("scientific_role") != "familiarity_diagnostic"]
        correct = 0
        abstained = 0
        abstention_correct = 0
        unsupported_total = 0
        unsupported_false_accepts = 0
        unsupported = 0
        for row in scored:
            key, key_is_unsupported = _key_info(answer_key[row["question_id"]])
            is_abstention = _is_abstention(row)
            correct += row["prediction"] == key
            abstained += is_abstention
            if key_is_unsupported:
                unsupported_total += 1
                abstention_correct += is_abstention
                unsupported_false_accepts += not is_abstention
            if key_is_unsupported and row["prediction"] == key:
                unsupported += 1
        scored_count = len(scored)
        modules[module] = {
            "record_count": len(module_rows),
            "scored_count": scored_count,
            "self_report_excluded": len(module_rows) - scored_count,
            "accuracy": correct / scored_count if scored_count else None,
            "exact_precision": correct / (scored_count - abstained) if scored_count - abstained else None,
            "exact_recall": correct / scored_count if scored_count else None,
            "abstention_rate": abstained / scored_count if scored_count else None,
            "abstention_precision": abstention_correct / abstained if abstained else None,
            "abstention_recall": abstention_correct / unsupported_total if unsupported_total else None,
            "unsupported_claim_count": unsupported,
            "unsupported_claim_rate": unsupported / scored_count if scored_count else None,
            "unsupported_false_accept_rate": unsupported_false_accepts / unsupported_total if unsupported_total else None,
        }
    return {"modules": modules, "self_report_is_non_evidential": True, "claim_ids": [], "evidence_eligible": False}


def source_familiarity_contrast(condition_scores: Mapping[str, Sequence[float]]) -> dict[str, Any]:
    """Compare canonical, paraphrase, lexical-control, and nonce scores."""
    required = ("canonical_short_phrase", "independent_paraphrase", "matched_non_triz_lexical_control", "nonce_relation_edit")
    if any(condition not in condition_scores for condition in required):
        raise Exp002KnowledgeError("source-familiarity conditions are incomplete")
    copied: dict[str, tuple[float, ...]] = {}
    for condition in required:
        values = tuple(float(value) for value in condition_scores[condition])
        if not values or any(not math.isfinite(value) for value in values):
            raise Exp002KnowledgeError(f"invalid source-familiarity scores: {condition}")
        copied[condition] = values
    lengths = {len(values) for values in copied.values()}
    if len(lengths) != 1:
        raise Exp002KnowledgeError("source-familiarity conditions must be paired")
    mean = {condition: sum(values) / len(values) for condition, values in copied.items()}
    return {
        "mean_scores": mean,
        "canonical_minus_paraphrase": mean["canonical_short_phrase"] - mean["independent_paraphrase"],
        "canonical_minus_non_triz_control": mean["canonical_short_phrase"] - mean["matched_non_triz_lexical_control"],
        "nonce_rejection_margin": mean["canonical_short_phrase"] - mean["nonce_relation_edit"],
        "interpretation": "behavioural_source_familiarity_is_not_training_membership",
        "claim_ids": [],
    }


def evaluate_source_familiarity(
    condition_scores: Mapping[str, Sequence[float]], *, attribution_correct: Sequence[bool],
    exact_phrase_completed: Sequence[bool], unsupported_claims: Sequence[bool],
) -> dict[str, Any]:
    """Return descriptive source-familiarity metrics from injected observations.

    These metrics are behavioural contrasts only. They do not infer training
    membership and never open source files, models, or targets.
    """
    contrast = source_familiarity_contrast(condition_scores)
    required_count = len(tuple(condition_scores["canonical_short_phrase"]))
    sequences = {
        "attribution_correct": attribution_correct,
        "exact_phrase_completed": exact_phrase_completed,
        "unsupported_claims": unsupported_claims,
    }
    for name, values in sequences.items():
        if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence) or len(values) != required_count or any(not isinstance(value, bool) for value in values):
            raise Exp002KnowledgeError(f"{name} must be a boolean sequence paired to the scores")
    canonical = tuple(float(value) for value in condition_scores["canonical_short_phrase"])
    paraphrase = tuple(float(value) for value in condition_scores["independent_paraphrase"])
    stability = sum(1.0 - abs(left - right) / (1.0 + abs(left) + abs(right)) for left, right in zip(canonical, paraphrase)) / required_count
    nonce = tuple(float(value) for value in condition_scores["nonce_relation_edit"])
    return {
        **contrast,
        "paraphrase_stability": stability,
        "nonce_rejection_rate": sum(left > right for left, right in zip(canonical, nonce)) / required_count,
        "attribution_accuracy": sum(attribution_correct) / required_count,
        "exact_phrase_completion_rate": sum(exact_phrase_completed) / required_count,
        "unsupported_claim_rate": sum(unsupported_claims) / required_count,
        "interpretation_boundary": "behavioural_source_familiarity_is_not_training_membership",
        "claim_ids": [],
    }


__all__ = ["Exp002KnowledgeError", "evaluate_direct_questions", "evaluate_source_familiarity", "source_familiarity_contrast"]
