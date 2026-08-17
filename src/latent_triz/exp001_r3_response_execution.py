"""Model-facing, target-free response scoring for EXP-001 R3.

The executor owns only the public response boundary.  It renders each public
record and asks an injected adapter for one teacher-forced score for each of
the four labels.  It has no model, tokenizer, target-key, filesystem, network,
or CCP capability; those boundaries are intentionally outside this module.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class R3ResponseExecutionError(ValueError):
    """Raised when public records or adapter responses violate the contract."""


class ChoiceScoringAdapter(Protocol):
    """Minimal injected capability required by the execution boundary."""

    def score_prompt_choice(self, rendered_prompt: str, label: str) -> float:
        """Return one finite teacher-forced score; generation is forbidden."""


_LABELS = ("A", "B", "C", "D")
_REQUIRED_RECORD_FIELDS = ("record_id", "prompt", "options")


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise R3ResponseExecutionError(f"{field} must be a non-empty string")
    return value.strip()


def _render_record(record: Mapping[str, Any]) -> str:
    """Render one record with exactly four labelled option descriptions."""
    missing = [field for field in _REQUIRED_RECORD_FIELDS if field not in record]
    if missing:
        raise R3ResponseExecutionError(f"record missing required field: {missing[0]}")
    record_id = _text(record["record_id"], "record_id")
    prompt = _text(record["prompt"], f"{record_id}/prompt")
    options = record["options"]
    if isinstance(options, (str, bytes, bytearray)) or not isinstance(options, Sequence) or len(options) != 4:
        raise R3ResponseExecutionError(f"{record_id}/options must contain exactly four entries")
    parsed: list[tuple[str, str]] = []
    for index, option in enumerate(options):
        if not isinstance(option, Mapping):
            raise R3ResponseExecutionError(f"{record_id}/options[{index}] must be an object")
        label = option.get("id")
        description = option.get("description")
        if label != _LABELS[index]:
            raise R3ResponseExecutionError(f"{record_id}/options must be ordered A/B/C/D")
        parsed.append((label, _text(description, f"{record_id}/options[{index}]/description")))
    # Delimiters are fixed and the answer boundary is explicit.  Descriptions
    # are copied verbatim after trimming; no target or expected answer enters.
    lines = [f"Task: {prompt}", "Options:"]
    lines.extend(f"{label}. {description}" for label, description in parsed)
    lines.append("Answer with exactly one option label: A, B, C, or D.")
    return "\n".join(lines)


def _score(adapter: ChoiceScoringAdapter, rendered: str, record_id: str, label: str) -> float:
    try:
        value = adapter.score_prompt_choice(rendered, label)
    except Exception as exc:
        raise R3ResponseExecutionError(f"adapter failed for {record_id}/{label}") from exc
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise R3ResponseExecutionError(f"adapter returned a non-finite score for {record_id}/{label}")
    return float(value)


def execute_public_responses(
    records: Sequence[Mapping[str, Any]], adapter: ChoiceScoringAdapter
) -> list[dict[str, Any]]:
    """Score exactly 72 public records, four labels per record.

    Validation and rendering occur for the complete inventory before any
    adapter call.  A failure is fail-closed: partial rows are never returned.
    The output contains only record IDs, scores, and a digest of the rendered
    prompt; it cannot contain raw targets or expected answers.
    """
    if isinstance(records, (str, bytes, bytearray)) or not isinstance(records, Sequence) or len(records) != 72:
        raise R3ResponseExecutionError("response execution requires exactly 72 records")
    rendered: list[tuple[str, str]] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, Mapping):
            raise R3ResponseExecutionError("each public record must be an object")
        record_id = _text(record.get("record_id"), "record_id")
        if record_id in seen:
            raise R3ResponseExecutionError(f"duplicate record_id: {record_id}")
        seen.add(record_id)
        rendered.append((record_id, _render_record(record)))
    rows: list[dict[str, Any]] = []
    try:
        for record_id, prompt in rendered:
            scores = {label: _score(adapter, prompt, record_id, label) for label in _LABELS}
            rows.append({
                "record_id": record_id,
                "scores": scores,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            })
    except R3ResponseExecutionError:
        raise
    if len(rows) != 72:
        raise R3ResponseExecutionError("execution did not produce exactly 72 rows")
    return rows


__all__ = ["ChoiceScoringAdapter", "R3ResponseExecutionError", "execute_public_responses"]
