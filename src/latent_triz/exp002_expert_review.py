"""No-model validation of independent EXP-002 answer-key review packets."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any


class Exp002ExpertReviewError(ValueError):
    """Raised when expert review evidence is incomplete or unsafe."""


_HASH = re.compile(r"^[a-f0-9]{64}$")


def validate_review_packet(
    packet: Mapping[str, Any], question_ids: Sequence[str], *, question_bank_sha256: str,
) -> dict[str, Any]:
    """Validate one complete, target-free reviewer packet."""
    if not isinstance(packet, Mapping) or packet.get("artifact_class") != "exp002-expert-review-packet":
        raise Exp002ExpertReviewError("unexpected review packet")
    reviewer_id = packet.get("reviewer_id")
    if not isinstance(reviewer_id, str) or not reviewer_id.strip():
        raise Exp002ExpertReviewError("reviewer ID must be a non-empty pseudonym")
    if not isinstance(question_bank_sha256, str) or not _HASH.fullmatch(question_bank_sha256):
        raise Exp002ExpertReviewError("question-bank hash is malformed")
    if packet.get("question_bank_sha256") != question_bank_sha256 or packet.get("status") != "submitted":
        raise Exp002ExpertReviewError("review packet identity or status drift")
    if packet.get("independence_attestation") is not True or packet.get("model_access") is not False or packet.get("sealed_target_access") is not False:
        raise Exp002ExpertReviewError("review packet crosses an access or independence boundary")
    expected = set(question_ids)
    if not expected or any(not isinstance(value, str) or not value for value in expected):
        raise Exp002ExpertReviewError("question IDs are malformed")
    decisions = packet.get("decisions")
    if isinstance(decisions, (str, bytes, bytearray)) or not isinstance(decisions, Sequence):
        raise Exp002ExpertReviewError("review decisions are missing")
    observed: set[str] = set()
    for decision in decisions:
        if not isinstance(decision, Mapping):
            raise Exp002ExpertReviewError("review decision is malformed")
        question_id = decision.get("question_id")
        if question_id not in expected or question_id in observed:
            raise Exp002ExpertReviewError("review decision coverage is invalid")
        if decision.get("key_type") not in {"exact", "abstention", "rubric_required", "non_evidential"} or decision.get("decision") != "reviewed" or not _HASH.fullmatch(str(decision.get("rationale_sha256", ""))):
            raise Exp002ExpertReviewError("review decision is not receipted")
        if decision.get("key_type") in {"exact", "abstention"} and "answer" not in decision:
            raise Exp002ExpertReviewError("exact or abstention decisions require an answer")
        observed.add(question_id)
    if observed != expected:
        raise Exp002ExpertReviewError("review packet must cover the full question bank exactly once")
    return {
        "artifact_class": "exp002-expert-review-packet-audit",
        "status": "valid_packet",
        "reviewer_id": reviewer_id,
        "question_count": len(expected),
        "full_coverage": True,
        "model_access": False,
        "sealed_target_access": False,
        "claim_ids": [],
    }


def validate_review_packets(
    packets: Sequence[Mapping[str, Any]], question_ids: Sequence[str], *, question_bank_sha256: str,
) -> dict[str, Any]:
    """Validate three independent, target-free review packets."""
    if isinstance(packets, (str, bytes, bytearray)) or not isinstance(packets, Sequence) or len(packets) != 3:
        raise Exp002ExpertReviewError("exactly three review packets are required")
    if not isinstance(question_bank_sha256, str) or not _HASH.fullmatch(question_bank_sha256):
        raise Exp002ExpertReviewError("question-bank hash is malformed")
    expected = set(question_ids)
    if not expected or any(not isinstance(value, str) or not value for value in expected):
        raise Exp002ExpertReviewError("question IDs are malformed")
    reviewers: set[str] = set()
    packet_coverage: list[set[str]] = []
    for packet in packets:
        reviewer_id = packet.get("reviewer_id") if isinstance(packet, Mapping) else None
        if not isinstance(reviewer_id, str) or not reviewer_id.strip() or reviewer_id in reviewers:
            raise Exp002ExpertReviewError("reviewer IDs must be distinct non-empty pseudonyms")
        reviewers.add(reviewer_id)
        validate_review_packet(packet, question_ids, question_bank_sha256=question_bank_sha256)
        packet_coverage.append(expected)
    return {
        "artifact_class": "exp002-expert-review-summary",
        "status": "ready_for_answer_key_freeze",
        "reviewer_count": len(reviewers),
        "question_count": len(expected),
        "full_coverage": all(coverage == expected for coverage in packet_coverage),
        "model_access": False,
        "sealed_target_access": False,
        "claim_ids": [],
    }


def summarize_review_packets(packets: Sequence[Mapping[str, Any]], question_ids: Sequence[str]) -> dict[str, Any]:
    """Return a deterministic summary using the packet hash from the first packet."""
    if not packets or not isinstance(packets[0], Mapping):
        raise Exp002ExpertReviewError("review packets are empty")
    return validate_review_packets(packets, question_ids, question_bank_sha256=str(packets[0].get("question_bank_sha256", "")))


__all__ = ["Exp002ExpertReviewError", "summarize_review_packets", "validate_review_packet", "validate_review_packets"]
