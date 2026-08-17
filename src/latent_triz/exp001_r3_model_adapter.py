"""Local-only, no-generation SmolLM2 adapter for EXP-001 R3.

The transformers import is intentionally confined to :meth:`load`.  Tests can
inject factories, so this module can be exercised without a model, network, or
ML runtime.  The adapter exposes finite forward outputs only; it never calls
``generate``.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Callable

from .exp001_r3_response_adapter import (
    R3ResponseAdapterError,
    score_teacher_forced_choice,
    validate_tokenizer_batch,
)

MODEL_ID = "HuggingFaceTB/SmolLM2-360M"
MODEL_REVISION = "f8027fd0eaeea54caa13c31d31b9fdc459c38b49"
MODEL_TYPE = "llama"
MODEL_ARCHITECTURE = "LlamaForCausalLM"
NUM_HIDDEN_LAYERS = 32
HIDDEN_SIZE = 960


class R3ModelAdapterError(RuntimeError):
    """Raised when the exact R3 model contract cannot be satisfied."""


def _shape(value: Any) -> tuple[int, ...]:
    shape = getattr(value, "shape", None)
    if shape is not None:
        try:
            return tuple(int(x) for x in shape)
        except (TypeError, ValueError):
            pass
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        dims: list[int] = []
        current: Any = value
        while isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)):
            dims.append(len(current))
            if not current:
                break
            current = current[0]
        return tuple(dims)
    raise R3ModelAdapterError("model logits must expose a rank-3 shape")


def _config_check(config: Any) -> None:
    if getattr(config, "model_type", None) != MODEL_TYPE:
        raise R3ModelAdapterError("unexpected model_type")
    if int(getattr(config, "num_hidden_layers", -1)) != NUM_HIDDEN_LAYERS:
        raise R3ModelAdapterError("unexpected num_hidden_layers")
    if int(getattr(config, "hidden_size", -1)) != HIDDEN_SIZE:
        raise R3ModelAdapterError("unexpected hidden_size")
    if MODEL_ARCHITECTURE not in list(getattr(config, "architectures", []) or []):
        raise R3ModelAdapterError("unexpected model architecture")


class SmolLM2R3Adapter:
    """CPU float32 forward adapter with a strict singleton Mapping batch."""

    def __init__(self, tokenizer: Any, model: Any, torch_module: Any) -> None:
        if not bool(getattr(tokenizer, "is_fast", False)):
            raise R3ModelAdapterError("fast tokenizer required")
        self.tokenizer = tokenizer
        self.model = model
        self.torch = torch_module
        if hasattr(self.model, "eval"):
            self.model.eval()

    @classmethod
    def load(
        cls,
        model_root: str | Path,
        *,
        tokenizer_factory: Callable[..., Any] | None = None,
        model_factory: Callable[..., Any] | None = None,
        config_factory: Callable[..., Any] | None = None,
    ) -> "SmolLM2R3Adapter":
        """Load only from a local directory; imports happen at this boundary."""
        root = str(Path(model_root).resolve())
        try:
            import torch
            from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise R3ModelAdapterError(f"torch/transformers unavailable: {exc}") from exc
        config_factory = config_factory or AutoConfig.from_pretrained
        tokenizer_factory = tokenizer_factory or AutoTokenizer.from_pretrained
        model_factory = model_factory or AutoModelForCausalLM.from_pretrained
        common = {"local_files_only": True}
        try:
            config = config_factory(root, **common)
            _config_check(config)
            tokenizer = tokenizer_factory(root, use_fast=True, **common)
            model = model_factory(root, torch_dtype=torch.float32, **common)
        except R3ModelAdapterError:
            raise
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise R3ModelAdapterError(f"local model load failed: {exc}") from exc
        if hasattr(model, "to"):
            model.to(torch.device("cpu"))
        return cls(tokenizer, model, torch)

    def forward(self, prompt: str) -> dict[str, Any]:
        if not isinstance(prompt, str) or not prompt:
            raise R3ModelAdapterError("prompt must be a non-empty string")
        try:
            batch = self.tokenizer(
                prompt, add_special_tokens=True, return_attention_mask=True,
                return_tensors="pt",
            )
            if not isinstance(batch, Mapping):
                raise R3ModelAdapterError("tokenizer output must implement Mapping")
            # Validate the public shape without assuming BatchEncoding is dict.
            ids = validate_tokenizer_batch(batch)
            input_ids = batch["input_ids"]
            attention_mask = batch["attention_mask"]
            outputs = self.model(
                input_ids=input_ids, attention_mask=attention_mask,
                output_hidden_states=True, use_cache=False, return_dict=True,
            )
        except R3ResponseAdapterError as exc:
            raise R3ModelAdapterError(str(exc)) from exc
        except R3ModelAdapterError:
            raise
        except Exception as exc:
            raise R3ModelAdapterError(f"model forward failed: {exc}") from exc
        logits = outputs.get("logits") if isinstance(outputs, Mapping) else getattr(outputs, "logits", None)
        shape = _shape(logits)
        if len(shape) != 3 or shape[0] != 1 or shape[1] != len(ids["input_ids"]):
            raise R3ModelAdapterError("logits must have shape [1, token_count, vocab]")
        return {"input_ids": ids["input_ids"], "attention_mask": ids["attention_mask"],
                "logits": logits, "hidden_states": getattr(outputs, "hidden_states", None),
                "model_output_accessed": True, "generation_used": False}

    @staticmethod
    def score_choice(logits: Any, choice_token_ids: Sequence[int], **kwargs: Any) -> float:
        """Score an already materialised continuation without invoking generation."""
        try:
            return score_teacher_forced_choice(logits, choice_token_ids, **kwargs)
        except R3ResponseAdapterError as exc:
            raise R3ModelAdapterError(str(exc)) from exc


__all__ = ["SmolLM2R3Adapter", "R3ModelAdapterError"]
