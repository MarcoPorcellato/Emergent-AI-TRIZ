"""C2 adapter with fail-closed singleton-batch hidden-state normalization."""

from __future__ import annotations

import math
from typing import Any

from .a0r2c1_adapter import SmolLM2C1MappingAdapter


class A0R2C2AdapterError(RuntimeError):
    """Raised when a hidden-state shape cannot satisfy the C2 contract."""


def _nested_lists(value: Any) -> Any:
    if hasattr(value, "detach"):
        try:
            return value.detach().cpu().tolist()
        except Exception as exc:  # pragma: no cover - defensive tensor boundary
            raise A0R2C2AdapterError("hidden state is not list-convertible") from exc
    return value


def normalize_hidden_state_rows(
    value: Any,
    *,
    token_count: int,
    hidden_size: int,
) -> list[list[float]]:
    """Remove only a singleton batch axis and validate every scalar."""

    nested = _nested_lists(value)
    if not isinstance(nested, (list, tuple)) or not nested:
        raise A0R2C2AdapterError("hidden state must be a non-empty sequence")

    first = nested[0]
    if not isinstance(first, (list, tuple)) or not first:
        raise A0R2C2AdapterError("hidden state has malformed list depth")
    first_item = first[0]
    if isinstance(first_item, (list, tuple)):
        if len(nested) != 1:
            raise A0R2C2AdapterError("hidden state batch dimension must equal one")
        rows = first
    else:
        rows = nested

    if len(rows) != token_count:
        raise A0R2C2AdapterError("hidden state token dimension mismatch")
    normalized: list[list[float]] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != hidden_size:
            raise A0R2C2AdapterError("hidden state hidden dimension mismatch")
        try:
            normalized_row = [float(item) for item in row]
        except (TypeError, ValueError) as exc:
            raise A0R2C2AdapterError("hidden state contains non-scalar values") from exc
        if not all(math.isfinite(item) for item in normalized_row):
            raise A0R2C2AdapterError("hidden state contains non-finite values")
        normalized.append(normalized_row)
    return normalized


class SmolLM2C2ShapeAdapter(SmolLM2C1MappingAdapter):
    """C1 adapter plus the preregistered Llama singleton-batch correction."""

    def run_prompt(self, *, prompt: str, instrumented: bool = True) -> dict[str, Any]:
        payload = super().run_prompt(prompt=prompt, instrumented=instrumented)
        token_ids = payload.get("token_ids")
        hidden_states = payload.get("hidden_states")
        if not isinstance(token_ids, list) or not isinstance(hidden_states, (list, tuple)):
            raise A0R2C2AdapterError("C1 adapter output lacks token IDs or hidden states")
        payload["hidden_states"] = tuple(
            normalize_hidden_state_rows(state, token_count=len(token_ids), hidden_size=960)
            for state in hidden_states
        )
        return payload


__all__ = ["A0R2C2AdapterError", "SmolLM2C2ShapeAdapter", "normalize_hidden_state_rows"]
