"""Strict local-only SmolLM2 adapter for the A0-R2 activation study."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .a0r2_acquisition import A0R2_REQUIRED_FILES, build_runtime_file_receipts


class A0R2AdapterError(RuntimeError):
    """Raised when the SmolLM2 adapter cannot be initialized or executed locally."""


MODEL_ID = "HuggingFaceTB/SmolLM2-360M"
MODEL_REVISION = "f8027fd0eaeea54caa13c31d31b9fdc459c38b49"
MODEL_TYPE = "llama"
MODEL_ARCHITECTURE = "LlamaForCausalLM"
MODEL_HIDDEN_LAYERS = 32
MODEL_HIDDEN_SIZE = 960


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise A0R2AdapterError(message)


def _normalize_nested_lists(value: Any, *, label: str) -> list[list[int]]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)) or not value:
        raise A0R2AdapterError(f"{label} must be a non-empty sequence")
    if value and not isinstance(value[0], (list, tuple)):
        value = [value]
    rows: list[list[int]] = []
    for row in value:
        if not isinstance(row, (list, tuple)):
            raise A0R2AdapterError(f"{label} must be a nested sequence")
        rows.append([int(item) for item in row])
    if not rows or not rows[0]:
        raise A0R2AdapterError(f"{label} must not be empty")
    return rows


def _normalize_offsets(value: Any) -> list[list[list[int]]]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)) or not value:
        raise A0R2AdapterError("offset_mapping must be a non-empty sequence")
    if value and isinstance(value[0], (list, tuple)) and value[0] and isinstance(value[0][0], (int, float)):
        value = [value]
    batches: list[list[list[int]]] = []
    for batch in value:
        if not isinstance(batch, (list, tuple)):
            raise A0R2AdapterError("offset_mapping must be a batched nested sequence")
        rows: list[list[int]] = []
        for pair in batch:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise A0R2AdapterError("offset_mapping entries must be start/end pairs")
            rows.append([int(pair[0]), int(pair[1])])
        batches.append(rows)
    if not batches or not batches[0]:
        raise A0R2AdapterError("offset_mapping must not be empty")
    return batches


def _normalize_1d_sequence(value: Any, *, label: str) -> list[list[int]]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)) or not value:
        raise A0R2AdapterError(f"{label} must be a non-empty sequence")
    if value and not isinstance(value[0], (list, tuple)):
        value = [value]
    rows: list[list[int]] = []
    for row in value:
        if not isinstance(row, (list, tuple)):
            raise A0R2AdapterError(f"{label} must be a nested sequence")
        rows.append([int(item) for item in row])
    if not rows or not rows[0]:
        raise A0R2AdapterError(f"{label} must not be empty")
    return rows


class SmolLM2TransformersAdapter:
    """Minimal CPU-only adapter that binds exact local files before any forward pass."""

    def __init__(
        self,
        model_root: str | Path,
        *,
        local_files_only: bool = True,
        device: str = "cpu",
        torch_dtype: str = "float32",
    ) -> None:
        _require(local_files_only, "local_files_only must be true")
        _require(device == "cpu", "only cpu execution is permitted")

        self.model_root = Path(model_root).resolve()
        _require(self.model_root.exists() and self.model_root.is_dir(), f"model_root not found: {self.model_root}")

        try:
            import torch
            from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
        except Exception as exc:  # pragma: no cover
            raise A0R2AdapterError(f"torch/transformers unavailable: {exc}") from exc

        self.torch = torch
        dtype = getattr(torch, torch_dtype, None) if isinstance(torch_dtype, str) else torch_dtype
        _require(dtype is not None, f"unsupported torch_dtype: {torch_dtype!r}")

        expected_files = list(A0R2_REQUIRED_FILES)
        present_files = sorted(item.name for item in self.model_root.iterdir() if item.is_file())
        _require(
            present_files == expected_files,
            "model_root must contain the exact nine runtime files and nothing else",
        )

        self.runtime_file_receipts = tuple(build_runtime_file_receipts(self.model_root))

        try:
            config = AutoConfig.from_pretrained(str(self.model_root), local_files_only=True)
        except Exception as exc:  # pragma: no cover
            raise A0R2AdapterError(f"cannot read model config from {self.model_root}") from exc

        if getattr(config, "model_type", None) != MODEL_TYPE:
            raise A0R2AdapterError(f"unsupported model_type {getattr(config, 'model_type', None)!r}")
        if int(getattr(config, "num_hidden_layers", -1)) != MODEL_HIDDEN_LAYERS:
            raise A0R2AdapterError("unexpected num_hidden_layers")
        if int(getattr(config, "hidden_size", -1)) != MODEL_HIDDEN_SIZE:
            raise A0R2AdapterError("unexpected hidden_size")
        architectures = list(getattr(config, "architectures", []) or [])
        if MODEL_ARCHITECTURE not in architectures:
            raise A0R2AdapterError("unexpected architecture")

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                str(self.model_root),
                local_files_only=True,
                use_fast=True,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                str(self.model_root),
                local_files_only=True,
                dtype=dtype,
            )
        except Exception as exc:  # pragma: no cover
            raise A0R2AdapterError(f"cannot load model/tokenizer locally from {self.model_root}") from exc

        if not bool(getattr(self.tokenizer, "is_fast", False)):
            raise A0R2AdapterError("fast tokenizer required")

        self.model.to(torch.device("cpu"))
        self.model.eval()

    def _to_cpu_tensor(self, value: Any) -> Any:
        if hasattr(value, "to"):
            return value.to(self.torch.device("cpu"))
        tensor = self.torch.tensor(value)
        return tensor.to(self.torch.device("cpu")) if hasattr(tensor, "to") else tensor

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
        if not isinstance(encoded, dict):
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
        except Exception as exc:  # pragma: no cover
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
                {
                    "token_id": int(token_id),
                    "token_piece": str(token_piece),
                    "is_special": bool(flag),
                }
                for token_id, token_piece, flag in zip(token_ids, token_pieces, special_flags)
            ],
            "special_token_flags": special_flags,
            "hidden_states": tuple(hidden_states),
            "logits": getattr(outputs, "logits", None),
            "model_output_accessed": True,
            "model_output_retained": False,
            "instrumented": True,
        }

    def __repr__(self) -> str:
        return f"SmolLM2TransformersAdapter(model_root={self.model_root!s})"
