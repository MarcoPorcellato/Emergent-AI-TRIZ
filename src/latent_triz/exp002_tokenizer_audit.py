"""Injected-tokenizer audit for EXP-002A.

The audit is intentionally independent of model weights and sealed targets.
It accepts an already loaded tokenizer only through dependency injection; the
future material runner must prove its offline/local-only boundary before calling
this function.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .exp002_followup import EXPECTED_MODELS, Exp002ContractError, LABELS


class Exp002TokenizerAuditError(ValueError):
    """Raised when tokenizer behaviour is incompatible with EXP-002A."""


_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _ids(tokenizer: Any, text: str) -> list[int]:
    try:
        encoded = tokenizer(text, add_special_tokens=False)
    except Exception as exc:
        raise Exp002TokenizerAuditError(f"tokenizer failed for {text!r}") from exc
    values = encoded.get("input_ids") if isinstance(encoded, Mapping) else getattr(encoded, "input_ids", None)
    if values is None:
        raise Exp002TokenizerAuditError("tokenizer output lacks input_ids")
    if isinstance(values, Sequence) and values and isinstance(values[0], Sequence) and not isinstance(values[0], (str, bytes, bytearray)):
        values = values[0]
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence) or not values:
        raise Exp002TokenizerAuditError("tokenizer input_ids must be a non-empty sequence")
    ids: list[int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise Exp002TokenizerAuditError("tokenizer input_ids must contain non-negative integers")
        ids.append(value)
    return ids


def audit_tokenizer(
    *, model_id: str, revision: str, tokenizer: Any, tokenizer_files_sha256: str,
    runtime_versions: Mapping[str, str], prompt_texts: Sequence[str] = (),
    transfer_control_pairs: Sequence[tuple[str, str]] = (),
) -> dict[str, Any]:
    """Return one strict observation using an injected fast tokenizer."""
    if EXPECTED_MODELS.get(model_id) != revision:
        raise Exp002TokenizerAuditError("model identity or revision drift")
    if not bool(getattr(tokenizer, "is_fast", False)):
        raise Exp002TokenizerAuditError("fast tokenizer is required")
    if not isinstance(tokenizer_files_sha256, str) or not _SHA256.fullmatch(tokenizer_files_sha256):
        raise Exp002TokenizerAuditError("tokenizer file digest must be a SHA-256")
    if not isinstance(runtime_versions, Mapping) or any(not isinstance(k, str) or not isinstance(v, str) or not v for k, v in runtime_versions.items()):
        raise Exp002TokenizerAuditError("runtime_versions must be non-empty string metadata")

    prefix = "EXP002 answer"
    prefix_ids = _ids(tokenizer, prefix)
    label_token_ids: dict[str, int] = {}
    continuation_counts: dict[str, int] = {}
    boundary_ok = True
    for label in LABELS:
        full_ids = _ids(tokenizer, f"{prefix} {label}")
        continuation = full_ids[len(prefix_ids):] if full_ids[:len(prefix_ids)] == prefix_ids else []
        if not continuation:
            boundary_ok = False
        else:
            label_token_ids[label] = continuation[0]
            continuation_counts[label] = len(continuation)
    if set(label_token_ids) != set(LABELS) or not boundary_ok:
        raise Exp002TokenizerAuditError("prefix/full answer boundary mismatch")

    def _special(name: str) -> Any:
        return getattr(tokenizer, name, None)

    prompt_counts = {text: len(_ids(tokenizer, text)) for text in prompt_texts if isinstance(text, str) and text}
    length_differences = []
    for transfer, control in transfer_control_pairs:
        transfer_count = len(_ids(tokenizer, transfer))
        control_count = len(_ids(tokenizer, control))
        length_differences.append({"transfer_tokens": transfer_count, "control_tokens": control_count, "difference": transfer_count - control_count})
    return {
        "model_id": model_id,
        "revision": revision,
        "tokenizer_files_sha256": tokenizer_files_sha256,
        "label_token_ids": label_token_ids,
        "continuation_token_counts": continuation_counts,
        "prefix_boundary_ok": True,
        "special_tokens": {
            "bos_token_id": _special("bos_token_id"),
            "eos_token_id": _special("eos_token_id"),
            "pad_token_id": _special("pad_token_id"),
            "all_special_ids": list(getattr(tokenizer, "all_special_ids", []) or []),
        },
        "prompt_token_counts": prompt_counts,
        "transfer_control_length_differences": length_differences,
        "runtime_versions": dict(runtime_versions),
    }


def validate_observation(observation: Mapping[str, Any]) -> None:
    """Reuse the protocol-level observation validator and enforce hash shape."""
    from .exp002_followup import validate_tokenizer_observation

    try:
        validate_tokenizer_observation(observation)
    except Exp002ContractError as exc:
        raise Exp002TokenizerAuditError(str(exc)) from exc
    if not _SHA256.fullmatch(str(observation.get("tokenizer_files_sha256", ""))):
        raise Exp002TokenizerAuditError("tokenizer file digest is not SHA-256")
    if not isinstance(observation.get("runtime_versions"), Mapping) or not observation["runtime_versions"]:
        raise Exp002TokenizerAuditError("runtime versions are missing")


__all__ = ["Exp002TokenizerAuditError", "audit_tokenizer", "validate_observation"]
