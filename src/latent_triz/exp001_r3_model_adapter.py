"""Local-only, no-generation SmolLM2 adapter for EXP-001 R3.

The transformers import is intentionally confined to :meth:`load`.  Tests can
inject factories, so this module can be exercised without a model, network, or
ML runtime.  The adapter exposes finite forward outputs only; it never calls
``generate``.
"""
from __future__ import annotations

from contextlib import nullcontext
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


def _plain(value: Any, name: str) -> Any:
    """Detach tensor-like values before dependency-free contract validation."""
    try:
        detach = getattr(value, "detach", None)
        cpu = detach().cpu() if callable(detach) else getattr(value, "cpu", lambda: value)()
        tolist = getattr(cpu, "tolist", None)
        if callable(tolist):
            return tolist()
    except Exception as exc:
        raise R3ModelAdapterError(f"could not normalize {name}") from exc
    return value


def _plain_batch(batch: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "input_ids": _plain(batch["input_ids"], "input_ids"),
        "attention_mask": _plain(batch["attention_mask"], "attention_mask"),
    }


def _config_check(config: Any) -> None:
    if getattr(config, "model_type", None) != MODEL_TYPE:
        raise R3ModelAdapterError("unexpected model_type")
    if int(getattr(config, "num_hidden_layers", -1)) != NUM_HIDDEN_LAYERS:
        raise R3ModelAdapterError("unexpected num_hidden_layers")
    if int(getattr(config, "hidden_size", -1)) != HIDDEN_SIZE:
        raise R3ModelAdapterError("unexpected hidden_size")
    if MODEL_ARCHITECTURE not in list(getattr(config, "architectures", []) or []):
        raise R3ModelAdapterError("unexpected model architecture")


def _runtime_check(model: Any, torch_module: Any) -> None:
    """Reject a loaded runtime that is not explicitly CPU float32."""
    parameters = getattr(model, "parameters", None)
    if not callable(parameters):
        return  # Synthetic fakes need not emulate a parameter iterator.
    try:
        observed = list(parameters())
    except Exception as exc:
        raise R3ModelAdapterError("could not inspect model parameters") from exc
    if not observed:
        raise R3ModelAdapterError("loaded model has no parameters")
    for parameter in observed:
        if getattr(getattr(parameter, "device", None), "type", None) != "cpu":
            raise R3ModelAdapterError("model parameter is not on CPU")
        if getattr(parameter, "dtype", None) != torch_module.float32:
            raise R3ModelAdapterError("model parameter is not float32")


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
        _runtime_check(model, torch)
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
            # Validate a detached copy. BatchEncoding tensors are intentionally
            # passed unchanged to the model below, but they are not Sequences.
            ids = validate_tokenizer_batch(_plain_batch(batch))
            input_ids = batch["input_ids"]
            attention_mask = batch["attention_mask"]
            no_grad = getattr(self.torch, "inference_mode", None) or getattr(self.torch, "no_grad", None)
            with (no_grad() if callable(no_grad) else nullcontext()):
                outputs = self.model(
                    input_ids=input_ids, attention_mask=attention_mask,
                    output_hidden_states=False, use_cache=False, return_dict=True,
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
                "logits": logits,
                "model_output_accessed": True, "generation_used": False}

    def score_prompt_choice(self, rendered_prompt: str, label: str) -> float:
        """Teacher-force one answer label without target access or generation.

        The full sequence must retain the exact token prefix of the public
        rendered prompt. A tokenizer that merges across this boundary is an
        incompatibility, rather than an occasion to adjust a score post hoc.
        """
        if not isinstance(rendered_prompt, str) or not rendered_prompt:
            raise R3ModelAdapterError("rendered_prompt must be a non-empty string")
        if label not in {"A", "B", "C", "D"}:
            raise R3ModelAdapterError("choice label must be one of A/B/C/D")
        continuation = f" {label}"
        full_prompt = rendered_prompt + continuation
        try:
            token_args = {"add_special_tokens": True, "return_attention_mask": True, "return_tensors": "pt"}
            prefix_batch = self.tokenizer(rendered_prompt, **token_args)
            full_batch = self.tokenizer(full_prompt, **token_args)
            if not isinstance(prefix_batch, Mapping) or not isinstance(full_batch, Mapping):
                raise R3ModelAdapterError("tokenizer output must implement Mapping")
            prefix = validate_tokenizer_batch(_plain_batch(prefix_batch))
            full = validate_tokenizer_batch(_plain_batch(full_batch))
            prefix_ids = prefix["input_ids"]
            full_ids = full["input_ids"]
            if len(full_ids) <= len(prefix_ids) or full_ids[:len(prefix_ids)] != prefix_ids:
                raise R3ModelAdapterError("tokenizer prefix drift at answer boundary")
            continuation_ids = full_ids[len(prefix_ids):]
            if not continuation_ids:
                raise R3ModelAdapterError("choice continuation must contain at least one token")
            no_grad = getattr(self.torch, "inference_mode", None) or getattr(self.torch, "no_grad", None)
            with (no_grad() if callable(no_grad) else nullcontext()):
                outputs = self.model(
                    input_ids=full_batch["input_ids"], attention_mask=full_batch["attention_mask"],
                    output_hidden_states=False, use_cache=False, return_dict=True,
                )
            logits = outputs.get("logits") if isinstance(outputs, Mapping) else getattr(outputs, "logits", None)
            shape = _shape(logits)
            if len(shape) != 3 or shape[0] != 1 or shape[1] != len(full_ids):
                raise R3ModelAdapterError("logits must match the full teacher-forced sequence")
            positions = list(range(len(prefix_ids) - 1, len(full_ids) - 1))
            vocab_size = getattr(getattr(self.model, "config", None), "vocab_size", None)
            return self.score_choice(
                _plain(logits, "logits"), continuation_ids,
                target_positions=positions, vocab_size=vocab_size,
            )
        except R3ResponseAdapterError as exc:
            raise R3ModelAdapterError(str(exc)) from exc
        except R3ModelAdapterError:
            raise
        except Exception as exc:
            raise R3ModelAdapterError(f"teacher-forced scoring failed: {exc}") from exc

    @staticmethod
    def score_choice(logits: Any, choice_token_ids: Sequence[int], **kwargs: Any) -> float:
        """Score an already materialised continuation without invoking generation."""
        try:
            return score_teacher_forced_choice(logits, choice_token_ids, **kwargs)
        except R3ResponseAdapterError as exc:
            raise R3ModelAdapterError(str(exc)) from exc


__all__ = ["SmolLM2R3Adapter", "R3ModelAdapterError"]
