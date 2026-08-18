"""Small, dependency-free response scoring primitives for EXP-001 R3.

This module deliberately knows nothing about a model, tokenizer implementation,
filesystem, or network.  It validates the mapping-shaped result returned by a
tokenizer and scores an already materialised finite logits tensor.  The latter
keeps the protocol's teacher-forced, no-generation boundary explicit and makes
the functions straightforward to exercise with fakes.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from numbers import Integral, Real
from typing import Any


class R3ResponseAdapterError(ValueError):
    """Raised when a tokenizer batch or logits score is not protocol-safe."""


def _as_sequence(value: Any, name: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise R3ResponseAdapterError(f"{name} must be a sequence")
    return value


def validate_tokenizer_batch(batch: Any, *, vocab_size: int | None = None) -> dict[str, list[int]]:
    """Validate and copy a single tokenizer batch.

    Any ``collections.abc.Mapping`` is accepted, including mapping-like
    ``BatchEncoding`` implementations.  Exactly one sequence is required in
    both ``input_ids`` and ``attention_mask``; the returned lists are plain
    integers so later protocol code cannot observe mutable tokenizer state.
    """

    if not isinstance(batch, Mapping):
        raise R3ResponseAdapterError("tokenizer output must implement Mapping")
    if "input_ids" not in batch or "attention_mask" not in batch:
        raise R3ResponseAdapterError("tokenizer batch requires input_ids and attention_mask")
    ids_batch = _as_sequence(batch["input_ids"], "input_ids")
    mask_batch = _as_sequence(batch["attention_mask"], "attention_mask")
    if len(ids_batch) != 1 or len(mask_batch) != 1:
        raise R3ResponseAdapterError("only batch size one is permitted")
    ids = _as_sequence(ids_batch[0], "input_ids[0]")
    mask = _as_sequence(mask_batch[0], "attention_mask[0]")
    if not ids or len(ids) != len(mask):
        raise R3ResponseAdapterError("input_ids and attention_mask must be non-empty and aligned")
    out_ids: list[int] = []
    out_mask: list[int] = []
    for index, (token, flag) in enumerate(zip(ids, mask)):
        if isinstance(token, bool) or not isinstance(token, Integral) or int(token) < 0:
            raise R3ResponseAdapterError(f"invalid token id at position {index}")
        if isinstance(flag, bool):
            value = int(flag)
        elif isinstance(flag, Integral) and int(flag) in (0, 1):
            value = int(flag)
        else:
            raise R3ResponseAdapterError(f"attention_mask must contain 0/1 at position {index}")
        if vocab_size is not None and (not isinstance(vocab_size, Integral) or vocab_size <= 0):
            raise R3ResponseAdapterError("vocab_size must be a positive integer")
        if vocab_size is not None and int(token) >= int(vocab_size):
            raise R3ResponseAdapterError(f"token id out of vocabulary at position {index}")
        out_ids.append(int(token))
        out_mask.append(value)
    if not any(out_mask):
        raise R3ResponseAdapterError("attention_mask must contain an active token")
    return {"input_ids": out_ids, "attention_mask": out_mask}


def _validate_logits(logits: Any, *, target_count: int, vocab_size: int | None = None) -> tuple[int, int, int]:
    if isinstance(logits, (str, bytes, bytearray)) or not isinstance(logits, Sequence) or len(logits) != 1:
        raise R3ResponseAdapterError("logits must have shape [1, T, V]")
    rows = _as_sequence(logits[0], "logits[0]")
    if len(rows) == 0 or len(rows) < target_count:
        raise R3ResponseAdapterError("logits time dimension is too short for the choice")
    first = _as_sequence(rows[0], "logits[0][0]")
    if not first:
        raise R3ResponseAdapterError("logits vocabulary dimension must be non-empty")
    width = len(first)
    if vocab_size is not None and width != int(vocab_size):
        raise R3ResponseAdapterError("logits vocabulary dimension does not match vocab_size")
    for row in rows:
        values = _as_sequence(row, "logits row")
        if len(values) != width:
            raise R3ResponseAdapterError("logits must be rectangular")
        if any(not isinstance(value, Real) or not math.isfinite(float(value)) for value in values):
            raise R3ResponseAdapterError("logits must contain only finite real values")
    return 1, len(rows), width


def score_teacher_forced_choice(
    logits: Any,
    choice_token_ids: Sequence[int],
    *,
    target_positions: Sequence[int] | None = None,
    vocab_size: int | None = None,
) -> float:
    """Return mean log-probability for a finite multi-token choice.

    ``logits[0][position]`` predicts the token at the corresponding target
    position.  Positions are explicit when supplied; otherwise the final
    ``len(choice_token_ids)`` time positions are used.  This function never
    invokes generation or performs model/tokenizer I/O.
    """

    choice = _as_sequence(choice_token_ids, "choice_token_ids")
    if not choice:
        raise R3ResponseAdapterError("choice must contain at least one token")
    ids: list[int] = []
    for index, token in enumerate(choice):
        if isinstance(token, bool) or not isinstance(token, Integral) or int(token) < 0:
            raise R3ResponseAdapterError(f"invalid choice token id at position {index}")
        ids.append(int(token))
    _validate_logits(logits, target_count=len(ids), vocab_size=vocab_size)
    rows = logits[0]
    positions = list(target_positions) if target_positions is not None else list(range(len(rows) - len(ids), len(rows)))
    if len(positions) != len(ids) or any(isinstance(pos, bool) or not isinstance(pos, Integral) for pos in positions):
        raise R3ResponseAdapterError("target_positions must align with choice tokens")
    if any(int(pos) < 0 or int(pos) >= len(rows) for pos in positions):
        raise R3ResponseAdapterError("target position is outside logits time dimension")
    scores: list[float] = []
    for position, token in zip(positions, ids):
        row = [float(value) for value in rows[int(position)]]
        if token >= len(row):
            raise R3ResponseAdapterError("choice token id is outside logits vocabulary")
        maximum = max(row)
        log_normalizer = maximum + math.log(sum(math.exp(value - maximum) for value in row))
        scores.append(row[token] - log_normalizer)
    return sum(scores) / len(scores)

