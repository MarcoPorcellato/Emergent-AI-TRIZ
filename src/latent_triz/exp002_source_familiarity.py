"""Fail-closed, no-model fixture validation for EXP-002B source familiarity.

The public fixture carries only prompt locators and hashes. Canonical source
text, answer keys, and model outputs stay outside the repository boundary and
are opened only by a separately authorized material analysis.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import re
from typing import Any


class Exp002SourceFamiliarityError(ValueError):
    """Raised when a source-familiarity fixture crosses a provenance boundary."""


CONDITIONS = (
    "canonical_short_phrase",
    "independent_paraphrase",
    "matched_non_triz_lexical_control",
    "nonce_relation_edit",
    "source_attribution_with_unknown",
)
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_CASE_ID = re.compile(r"^exp002b-source-[a-z0-9-]+$")
_PAIR_ID = re.compile(r"^exp002b-pair-[a-z0-9-]+$")
_LOCATOR = re.compile(r"^public://exp002b/source-familiarity/[a-z0-9._/-]+$")
_FORBIDDEN = {
    "expected_answer", "correct_choice", "target", "sealed_target", "expert_label",
    "model_output", "prediction", "source_excerpt", "canonical_text", "generator_intent",
}


def _text(value: Any, field: str, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Exp002SourceFamiliarityError(f"{field} must be non-empty text")
    value = value.strip()
    if pattern is not None and not pattern.fullmatch(value):
        raise Exp002SourceFamiliarityError(f"{field} has an unsafe format")
    return value


def validate_source_familiarity_fixture(
    records: Sequence[Mapping[str, Any]], *, status: str = "design",
) -> dict[str, Any]:
    """Validate paired, locator-only records without opening any source asset."""
    if status not in {"design", "frozen"}:
        raise Exp002SourceFamiliarityError("status must be design or frozen")
    if isinstance(records, (str, bytes, bytearray)) or not isinstance(records, Sequence):
        raise Exp002SourceFamiliarityError("records must be a sequence")

    seen_cases: set[str] = set()
    pairs: dict[str, set[str]] = {}
    source_ids: set[str] = set()
    for record in records:
        if not isinstance(record, Mapping):
            raise Exp002SourceFamiliarityError("record must be an object")
        leaked = _FORBIDDEN.intersection(record)
        if leaked:
            raise Exp002SourceFamiliarityError(f"answer or source content leaked: {sorted(leaked)}")
        case_id = _text(record.get("case_id"), "case_id", _CASE_ID)
        if case_id in seen_cases:
            raise Exp002SourceFamiliarityError("duplicate case_id")
        seen_cases.add(case_id)
        pair_id = _text(record.get("pair_id"), "pair_id", _PAIR_ID)
        condition = _text(record.get("condition"), "condition")
        if condition not in CONDITIONS:
            raise Exp002SourceFamiliarityError("unknown source-familiarity condition")
        locator = _text(record.get("prompt_locator"), "prompt_locator", _LOCATOR)
        digest = _text(record.get("prompt_sha256"), "prompt_sha256")
        if not _SHA256.fullmatch(digest):
            raise Exp002SourceFamiliarityError("prompt_sha256 must be a lowercase SHA-256")
        source_id = _text(record.get("source_id"), "source_id")
        exposure = _text(record.get("exposure_mode"), "exposure_mode")
        if exposure not in {"metadata_only", "human_reviewed_excerpt", "citation_only"}:
            raise Exp002SourceFamiliarityError("unsupported source exposure mode")
        if condition == "matched_non_triz_lexical_control" and source_id.startswith("triz-ref-"):
            raise Exp002SourceFamiliarityError("non-TRIZ lexical control uses a TRIZ source")
        pairs.setdefault(pair_id, set()).add(condition)
        source_ids.add(source_id)
        # Keep the locator value live so a future refactor cannot silently drop
        # the no-content requirement while retaining only a hash.
        if not locator.startswith("public://"):
            raise Exp002SourceFamiliarityError("prompt locator must remain public and logical")

    incomplete = {pair: sorted(set(CONDITIONS) - observed) for pair, observed in pairs.items() if set(observed) != set(CONDITIONS)}
    if incomplete:
        raise Exp002SourceFamiliarityError(f"paired conditions are incomplete: {incomplete}")
    ready = bool(pairs) and not incomplete
    if status == "frozen" and not ready:
        raise Exp002SourceFamiliarityError("frozen source-familiarity fixture is empty")
    return {
        "artifact_class": "exp002-source-familiarity-audit",
        "status": status,
        "record_count": len(records),
        "pair_count": len(pairs),
        "condition_counts": dict(sorted(Counter(record.get("condition") for record in records).items())),
        "source_ids": sorted(source_ids),
        "locator_only": True,
        "model_access": False,
        "sealed_target_access": False,
        "scientific_status": "exploratory",
        "claim_ids": [],
    }


__all__ = ["CONDITIONS", "Exp002SourceFamiliarityError", "validate_source_familiarity_fixture"]
