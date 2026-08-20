"""Fail-closed validation for the EXP-002 direct-question answer key.

The public question bank deliberately has no answers. This module validates a
separate expert-reviewed key supplied at a later boundary; it never opens a
model, tokenizer, target, or source file.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from typing import Any

from .exp002_expert_review import validate_review_packets


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
    reviewer_ids = review.get("reviewer_ids")
    if isinstance(reviewer_ids, (str, bytes, bytearray)) or not isinstance(reviewer_ids, Sequence):
        raise Exp002AnswerKeyError("reviewer_ids must be a sequence")
    if len(set(reviewer_ids)) != len(reviewer_ids) or any(not isinstance(value, str) or not value.strip() for value in reviewer_ids):
        raise Exp002AnswerKeyError("reviewer_ids must be unique non-empty pseudonyms")
    if review.get("disagreement_policy") != "unresolved_records_remain_rubric_required":
        raise Exp002AnswerKeyError("answer-key disagreement policy drift")
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
        if records or review.get("status") != "pending" or reviewer_ids:
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
        if review.get("status") != "complete" or int(review.get("reviewer_count", 0)) < 3 or len(reviewer_ids) < 3 or int(review.get("reviewer_count", 0)) != len(reviewer_ids):
            raise Exp002AnswerKeyError("frozen key lacks three completed expert reviews")
        if any(record.get("expert_status") != "reviewed" for record in records):
            raise Exp002AnswerKeyError("frozen key contains unreviewed records")
        return
    raise Exp002AnswerKeyError("unsupported answer-key status")


def freeze_answer_key_from_packets(
    packets: Sequence[Mapping[str, Any]], question_ids: Sequence[str], *, question_bank: str,
    question_bank_sha256: str,
) -> dict[str, Any]:
    """Build a frozen key only from three complete, independently reviewed packets.

    A disagreement is preserved as ``rubric_required`` under the preregistered
    policy; it is never resolved by majority vote or by inspecting model data.
    """
    try:
        summary = validate_review_packets(packets, question_ids, question_bank_sha256=question_bank_sha256)
    except Exception as exc:
        raise Exp002AnswerKeyError("review packets are not ready for key freeze") from exc
    by_question: dict[str, list[Mapping[str, Any]]] = {question_id: [] for question_id in question_ids}
    for packet in packets:
        for decision in packet["decisions"]:
            if "answer" not in decision and decision.get("key_type") in {"exact", "abstention"}:
                raise Exp002AnswerKeyError("exact or abstention decisions require an explicit answer")
            by_question[decision["question_id"]].append(decision)
    records: list[dict[str, Any]] = []
    for question_id in question_ids:
        decisions = by_question[question_id]
        signatures = {
            json.dumps({"key_type": item.get("key_type"), "answer": item.get("answer"), "unsupported": bool(item.get("unsupported", False))}, sort_keys=True, ensure_ascii=False)
            for item in decisions
        }
        if len(signatures) != 1:
            records.append({"question_id": question_id, "key_type": "rubric_required", "expert_status": "reviewed"})
            continue
        item = decisions[0]
        record: dict[str, Any] = {"question_id": question_id, "key_type": item["key_type"], "expert_status": "reviewed"}
        if "answer" in item:
            record["expected"] = item["answer"]
        if "unsupported" in item:
            record["unsupported"] = bool(item["unsupported"])
        records.append(record)
    artifact = {
        "artifact_class": "exp002-direct-answer-key",
        "key_id": "exp002-direct-answer-key-v1.0.0",
        "protocol_id": "exp002-qwen3-followup-v1.0.0",
        "status": "frozen",
        "question_bank": question_bank,
        "question_bank_sha256": question_bank_sha256,
        "records": records,
        "expert_review": {
            "required": True,
            "status": "complete",
            "reviewer_count": summary["reviewer_count"],
            "reviewer_ids": [packet["reviewer_id"] for packet in packets],
            "disagreement_policy": "unresolved_records_remain_rubric_required",
        },
        "model_access": False,
        "sealed_target_access": False,
        "scientific_status": "exploratory",
        "claim_ids": [],
    }
    try:
        validate_answer_key(artifact, question_ids, question_bank_sha256=question_bank_sha256)
    except Exp002AnswerKeyError:
        raise
    return artifact


__all__ = ["Exp002AnswerKeyError", "freeze_answer_key_from_packets", "validate_answer_key"]
