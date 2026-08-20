"""Fail-closed, target-free validation for the EXP-002C new corpus.

The validator checks only public fixture structure and lexical separation. It
never opens a target/key locator, loads a model, or infers an expert label.
Frozen readiness is deliberately stricter than design readiness so an
incomplete corpus cannot silently become a material study.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import re
from typing import Any


class Exp002TransferCorpusError(ValueError):
    """Raised when the EXP-002C corpus violates an independence gate."""


_SPLITS = {"discovery", "validation", "held_out_domain", "sealed_novel"}
_EXPOSURES = {"blinded_primary", "lexical_control", "generic_heuristic", "common_sense_control"}
_FORBIDDEN_PRIMARY = re.compile(
    r"\b(?:triz|ariz|panitz|matrix|inventive\s+principle|principle\s*#?\s*\d+|"
    r"substance[- ]field|nine[- ]windows|ideal\s+final\s+result|contradiction)\b",
    re.IGNORECASE,
)
_EXP001 = re.compile(r"\bexp001\b|exp-001|a0r[12]", re.IGNORECASE)
_LOCATOR = re.compile(r"^sealed://exp002c/(?:intent|expert)/")


def _text(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise Exp002TransferCorpusError(f"{field} must be non-empty text")
    return value.strip()


def _permutation(value: Any) -> list[int]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise Exp002TransferCorpusError("option_order must be a four-item permutation")
    copied = list(value)
    if copied != sorted(copied) or copied != [0, 1, 2, 3]:
        raise Exp002TransferCorpusError("option_order must be [0, 1, 2, 3]")
    return copied


def _check_primary_text(record: Mapping[str, Any]) -> None:
    exposure = record.get("source_exposure")
    if exposure != "blinded_primary":
        return
    for field in ("problem", "candidate_descriptions"):
        values = record.get(field)
        if isinstance(values, str):
            values = (values,)
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes, bytearray)):
            for value in values:
                if not isinstance(value, str) or _FORBIDDEN_PRIMARY.search(value):
                    raise Exp002TransferCorpusError("TRIZ/source cue leaked into blinded primary")


def _check_no_answer_fields(record: Mapping[str, Any]) -> None:
    forbidden = {
        "expected_answer", "correct_choice", "target", "sealed_target", "expert_label",
        "model_output", "prediction", "generator_intent", "source_excerpt",
    }
    leaked = forbidden.intersection(record)
    if leaked:
        raise Exp002TransferCorpusError(f"answer/output field leaked into public corpus: {sorted(leaked)}")


def validate_transfer_fixture(
    records: Sequence[Mapping[str, Any]], *, status: str = "design",
    minimum_domains: int = 8, preferred_domains: int = 12,
) -> dict[str, Any]:
    """Validate a target-free fixture and return deterministic readiness facts."""
    if status not in {"design", "frozen"}:
        raise Exp002TransferCorpusError("status must be design or frozen")
    if isinstance(records, (str, bytes, bytearray)) or not isinstance(records, Sequence) or not records:
        raise Exp002TransferCorpusError("records must be a non-empty sequence")
    if not isinstance(minimum_domains, int) or minimum_domains < 8:
        raise Exp002TransferCorpusError("minimum_domains must be at least eight")
    if not isinstance(preferred_domains, int) or preferred_domains < minimum_domains:
        raise Exp002TransferCorpusError("preferred_domains must not be below minimum_domains")

    seen_ids: set[str] = set()
    prompt_fingerprints: set[tuple[str, tuple[str, ...]]] = set()
    domains: set[str] = set()
    families: set[str] = set()
    family_records: Counter[str] = Counter()
    domain_families: dict[str, set[str]] = {}
    authors: set[str] = set()
    split_counts: Counter[str] = Counter()
    primary_count = 0

    for record in records:
        if not isinstance(record, Mapping):
            raise Exp002TransferCorpusError("corpus record must be an object")
        _check_no_answer_fields(record)
        case_id = _text(record, "case_id")
        if case_id in seen_ids or _EXP001.search(case_id):
            raise Exp002TransferCorpusError("case identity is duplicate or reuses EXP-001")
        seen_ids.add(case_id)
        domain = _text(record, "domain")
        family = _text(record, "family_id")
        _text(record, "replicate_id")
        split = _text(record, "split")
        if split not in _SPLITS:
            raise Exp002TransferCorpusError("unknown corpus split")
        candidates = record.get("candidate_descriptions")
        if isinstance(candidates, (str, bytes, bytearray)) or not isinstance(candidates, Sequence) or len(candidates) != 4:
            raise Exp002TransferCorpusError("exactly four candidate descriptions are required")
        candidate_text = tuple(_text({"value": value}, "value") for value in candidates)
        problem = _text(record, "problem")
        _permutation(record.get("option_order"))
        exposure = _text(record, "source_exposure")
        if exposure not in _EXPOSURES:
            raise Exp002TransferCorpusError("unknown source exposure")
        if exposure == "blinded_primary":
            primary_count += 1
        _check_primary_text(record)
        author = _text(record, "author_id")
        intent = _text(record, "generator_intent_locator")
        expert = _text(record, "expert_label_locator")
        if not _LOCATOR.match(intent) or not expert.startswith("sealed://exp002c/expert/") or intent == expert:
            raise Exp002TransferCorpusError("expert and generator locators must be distinct sealed locators")
        if record.get("source_proximity_status") != "pass":
            raise Exp002TransferCorpusError("source proximity audit must pass before freeze")
        fingerprint = (problem, candidate_text)
        if fingerprint in prompt_fingerprints:
            raise Exp002TransferCorpusError("duplicate problem/candidate fingerprint")
        prompt_fingerprints.add(fingerprint)
        domains.add(domain)
        families.add(family)
        family_records[family] += 1
        domain_families.setdefault(domain, set()).add(family)
        authors.add(author)
        split_counts[split] += 1

    if any(count < 2 for count in family_records.values()):
        raise Exp002TransferCorpusError("every family needs at least two replicates")
    if any(len(family_set) < 2 for family_set in domain_families.values()):
        raise Exp002TransferCorpusError("every domain needs at least two families")
    if len(authors) < 2:
        raise Exp002TransferCorpusError("at least two independent author identifiers are required")
    freeze_ready = (
        len(domains) >= minimum_domains
        and primary_count == len(records)
        and split_counts["held_out_domain"] > 0
        and split_counts["sealed_novel"] > 0
    )
    if status == "frozen" and not freeze_ready:
        raise Exp002TransferCorpusError("frozen corpus has not met domain/split/primary gates")
    return {
        "artifact_class": "exp002-transfer-corpus-audit",
        "status": status,
        "record_count": len(records),
        "domain_count": len(domains),
        "family_count": len(families),
        "author_count": len(authors),
        "split_counts": dict(sorted(split_counts.items())),
        "primary_is_label_free": primary_count == len(records),
        "freeze_ready": freeze_ready,
        "model_access": False,
        "sealed_target_access": False,
        "claim_ids": [],
    }


def summarize_transfer_fixture(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return the no-model audit summary, rejecting answer-bearing records."""
    return validate_transfer_fixture(records, status="design")


__all__ = ["Exp002TransferCorpusError", "summarize_transfer_fixture", "validate_transfer_fixture"]
