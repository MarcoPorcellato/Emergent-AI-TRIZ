"""C1 compatibility adapter for tokenizer mapping implementations.

This deliberately subclasses the frozen A0-R2 adapter.  Its only semantic
change is accepting any ``collections.abc.Mapping`` returned by a tokenizer;
some Transformers-compatible tokenizers use mapping-like containers rather
than a concrete ``dict``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .a0r2_adapter import (
    A0R2AdapterError,
    SmolLM2TransformersAdapter,
    _normalize_nested_lists,
    _normalize_offsets,
)


class SmolLM2C1MappingAdapter(SmolLM2TransformersAdapter):
    """A0-R2 adapter variant accepting tokenizer ``Mapping`` results."""

    def run_prompt(self, *, prompt: str, instrumented: bool = True) -> dict[str, Any]:
        del instrumented
        if not isinstance(prompt, str) or not prompt:
            raise A0R2AdapterError("prompt must be a non-empty string")

        encoded = self.tokenizer(
            prompt,
            add_special_tokens=True,
            return_attention_mask=True,
            return_offsets_mapping=True,
            return_tensors="pt",
        )
        if not isinstance(encoded, Mapping):
            raise A0R2AdapterError("tokenizer output must be a mapping")

        input_ids = self._to_cpu_tensor(encoded.get("input_ids"))
        attention_mask = self._to_cpu_tensor(encoded.get("attention_mask"))
        offsets_mapping = _normalize_offsets(encoded.get("offset_mapping"))
        token_rows = _normalize_nested_lists(input_ids, label="input_ids")
        attention_rows = _normalize_nested_lists(attention_mask, label="attention_mask")
        if len(token_rows) != 1 or len(attention_rows) != 1 or len(offsets_mapping) != 1:
            raise A0R2AdapterError("tokenizer output must be a single batched sequence")

        token_ids = [int(value) for value in token_rows[0]]
        attention = [int(value) for value in attention_rows[0]]
        offsets = [[int(start), int(end)] for start, end in offsets_mapping[0]]
        if len(token_ids) != len(attention) or len(token_ids) != len(offsets):
            raise A0R2AdapterError("token metadata length mismatch")

        try:
            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                output_hidden_states=True,
                use_cache=False,
                return_dict=True,
            )
        except Exception as exc:  # pragma: no cover - boundary is tested by parent adapter
            raise A0R2AdapterError(f"model forward pass failed: {exc}") from exc
        hidden_states = getattr(outputs, "hidden_states", None)
        if not isinstance(hidden_states, (list, tuple)) or not hidden_states:
            raise A0R2AdapterError("model output missing hidden_states")

        token_pieces = [str(token) for token in self.tokenizer.convert_ids_to_tokens(token_ids)]
        special_flags = (
            [bool(flag) for flag in self.tokenizer.get_special_tokens_mask(token_ids, already_has_special_tokens=True)]
            if hasattr(self.tokenizer, "get_special_tokens_mask")
            else [False] * len(token_ids)
        )
        if len(special_flags) != len(token_ids):
            raise A0R2AdapterError("special token flag length mismatch")
        return {
            "token_ids": token_ids,
            "token_pieces": token_pieces,
            "attention_mask": attention,
            "offsets_mapping": offsets,
            "token_inputs": [
                {"token_id": int(token_id), "token_piece": str(token_piece), "is_special": bool(flag)}
                for token_id, token_piece, flag in zip(token_ids, token_pieces, special_flags)
            ],
            "special_token_flags": special_flags,
            "hidden_states": tuple(hidden_states),
            "logits": getattr(outputs, "logits", None),
            "model_output_accessed": True,
            "model_output_retained": False,
            "instrumented": True,
        }


__all__ = ["SmolLM2C1MappingAdapter"]
