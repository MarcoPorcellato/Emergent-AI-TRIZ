"""Fail-closed validation for the EXP-002 direct-question answer key.

The public question bank deliberately has no answers. This module validates a
separate expert-reviewed key supplied at a later boundary; it never opens a
model, tokenizer, target, or source file.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class Exp002AnswerKeyError(ValueError):
    """Raised when the direct-question key is incomplete or unsafe."""


def validate_answer_key(
    artifact: Mapping[str, Any], question_ids: Sequence[str], *, question_bank_sha256: str,
) -> None:
    """Validate readiness without scoring or reading sealed content."""
    if not isinstance(artifact, Mapping) or artifact.get("artifact_class") != "exp002-direct-answer-key":
        raise Exp002AnswerKeyError("unexpected answer-key artifact")
    if artifact.get("protocol_id") != "exp002-qwen3-followup-v1.0.0":
        raise Exp002AnswerKeyError("answer-key protocol drift")
    if artifact.get("question_bank_sha256") != question_bank_sha256:
        raise Exp002AnswerKeyError("question-bank hash mismatch")
    if artifact.get("model_access") is not False or artifact.get("sealed_target_access") is not False:
        raise Exp002AnswerKeyError("answer-key preparation crossed the model/target boundary")
    records = artifact.get("records")
    review = artifact.get("expert_review")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes, bytearray)) or not isinstance(review, Mapping):
        raise Exp002AnswerKeyError("answer-key records/review are malformed")
    expected_ids = set(question_ids)
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, Mapping):
            raise Exp002AnswerKeyError("answer-key record is not an object")
        question_id = record.get("question_id")
        if not isinstance(question_id, str) or question_id not in expected_ids or question_id in seen:
            raise Exp002AnswerKeyError("answer-key question coverage is invalid")
        if record.get("key_type") not in {"exact", "abstention", "rubric_required", "non_evidential"}:
            raise Exp002AnswerKeyError("answer-key type is invalid")
        if record.get("expert_status") not in {"pending", "reviewed"}:
            raise Exp002AnswerKeyError("answer-key expert status is invalid")
        seen.add(question_id)
    status = artifact.get("status")
    if status == "not_ready":
        if records or review.get("status") != "pending":
            raise Exp002AnswerKeyError("not_ready key contains reviewed material")
        return
    if status == "expert_review":
        if not records or review.get("status") != "pending":
            raise Exp002AnswerKeyError("expert_review key is not awaiting review")
        if seen != expected_ids:
            raise Exp002AnswerKeyError("expert_review key does not cover the full bank")
        return
    if status == "frozen":
        if seen != expected_ids or not records:
            raise Exp002AnswerKeyError("frozen key must cover every question exactly once")
        if review.get("status") != "complete" or int(review.get("reviewer_count", 0)) < 3:
            raise Exp002AnswerKeyError("frozen key lacks three completed expert reviews")
        if any(record.get("expert_status") != "reviewed" for record in records):
            raise Exp002AnswerKeyError("frozen key contains unreviewed records")
        return
    raise Exp002AnswerKeyError("unsupported answer-key status")


__all__ = ["Exp002AnswerKeyError", "validate_answer_key"]
