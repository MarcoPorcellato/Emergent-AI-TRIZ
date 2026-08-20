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
        correct = sum(row["prediction"] == answer_key[row["question_id"]] for row in scored)
        abstained = sum(row["abstained"] for row in scored)
        unsupported = 0
        for row in scored:
            key = answer_key[row["question_id"]]
            if isinstance(key, Mapping) and bool(key.get("unsupported", False)) and row["prediction"] == key.get("answer"):
                unsupported += 1
        modules[module] = {
            "record_count": len(module_rows),
            "scored_count": len(scored),
            "self_report_excluded": len(module_rows) - len(scored),
            "accuracy": correct / len(scored) if scored else None,
            "abstention_rate": abstained / len(scored) if scored else None,
            "unsupported_claim_count": unsupported,
            "unsupported_claim_rate": unsupported / len(scored) if scored else None,
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


__all__ = ["Exp002KnowledgeError", "evaluate_direct_questions", "source_familiarity_contrast"]
