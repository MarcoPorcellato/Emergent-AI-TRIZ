"""Model-parametric local-only teacher-forcing adapter for comparative EXP-001.

This is deliberately separate from the frozen R3 SmolLM2 adapter.  It accepts
only a declared causal-LM snapshot contract, loads that snapshot locally on
CPU float32, and exposes finite teacher-forced choice scores.  It never
generates text, reads fixtures, or has any sealed-target capability.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import nullcontext
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Callable

from .exp001_r3_response_adapter import (
    R3ResponseAdapterError,
    score_teacher_forced_choice,
    validate_tokenizer_batch,
)


class ComparativeAdapterError(RuntimeError):
    """Raised when a comparative model cannot meet the fixed runtime contract."""


_SUPPORTED_CONFIGS: dict[str, str] = {
    "gpt2": "GPT2LMHeadModel",
    "gpt_neox": "GPTNeoXForCausalLM",
    "llama": "LlamaForCausalLM",
    "qwen3": "Qwen3ForCausalLM",
}
_LABELS = frozenset(("A", "B", "C", "D"))


@dataclass(frozen=True)
class ComparativeModelContract:
    """The exact approved snapshot and runtime invariants for one model.

    ``model_type`` intentionally determines the required architecture so an
    approval cannot accidentally pair a GPT-NeoX, Llama, or Qwen checkpoint
    with an incompatible loader configuration.
    """

    model_id: str
    revision: str
    model_type: str
    architecture: str
    num_hidden_layers: int
    hidden_size: int
    network: str = "disabled"
    device: str = "cpu"
    dtype: str = "float32"
    generation: bool = False
    add_special_tokens: bool = True

    def validate(self) -> None:
        if not isinstance(self.model_id, str) or not self.model_id:
            raise ComparativeAdapterError("model_id must be a non-empty string")
        if not isinstance(self.revision, str) or not self.revision:
            raise ComparativeAdapterError("revision must be a non-empty string")
        expected_architecture = _SUPPORTED_CONFIGS.get(self.model_type)
        if expected_architecture is None:
            raise ComparativeAdapterError("model_type is not supported")
        if self.architecture != expected_architecture:
            raise ComparativeAdapterError("model architecture is not supported for model_type")
        if (not isinstance(self.num_hidden_layers, int) or isinstance(self.num_hidden_layers, bool)
                or self.num_hidden_layers <= 0):
            raise ComparativeAdapterError("num_hidden_layers must be a positive integer")
        if (not isinstance(self.hidden_size, int) or isinstance(self.hidden_size, bool)
                or self.hidden_size <= 0):
            raise ComparativeAdapterError("hidden_size must be a positive integer")
        if self.network != "disabled":
            raise ComparativeAdapterError("network must be disabled")
        if self.device != "cpu" or self.dtype != "float32":
            raise ComparativeAdapterError("comparative runtime requires CPU float32")
        if self.generation is not False:
            raise ComparativeAdapterError("generation must be disabled")
        if not isinstance(self.add_special_tokens, bool):
            raise ComparativeAdapterError("add_special_tokens must be boolean")


def _plain(value: Any, name: str) -> Any:
    """Materialise a tensor-like object for dependency-free validation."""
    try:
        detach = getattr(value, "detach", None)
        cpu = detach().cpu() if callable(detach) else getattr(value, "cpu", lambda: value)()
        tolist = getattr(cpu, "tolist", None)
        if callable(tolist):
            return tolist()
    except Exception as exc:
        raise ComparativeAdapterError(f"could not normalize {name}") from exc
    return value


def _plain_batch(batch: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "input_ids": _plain(batch["input_ids"], "input_ids"),
        "attention_mask": _plain(batch["attention_mask"], "attention_mask"),
    }


def _shape(value: Any) -> tuple[int, ...]:
    shape = getattr(value, "shape", None)
    if shape is not None:
        try:
            return tuple(int(part) for part in shape)
        except (TypeError, ValueError):
            pass
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        dimensions: list[int] = []
        current: Any = value
        while isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)):
            dimensions.append(len(current))
            if not current:
                break
            current = current[0]
        return tuple(dimensions)
    raise ComparativeAdapterError("model logits must expose a rank-3 shape")


def _validate_logits(logits: Any, *, token_count: int, vocab_size: int | None) -> list[list[list[float]]]:
    plain = _plain(logits, "logits")
    shape = _shape(plain)
    if len(shape) != 3 or shape[0] != 1 or shape[1] != token_count:
        raise ComparativeAdapterError("logits must have shape [1, token_count, vocab]")
    if vocab_size is not None and shape[2] != vocab_size:
        raise ComparativeAdapterError("logits vocabulary dimension does not match config")
    if not isinstance(plain, Sequence) or isinstance(plain, (str, bytes, bytearray)):
        raise ComparativeAdapterError("logits must be a finite rank-3 sequence")
    try:
        copied = [[[float(value) for value in row] for row in rows] for rows in plain]
    except (TypeError, ValueError) as exc:
        raise ComparativeAdapterError("logits must be numeric") from exc
    if any(not math.isfinite(value) for batch in copied for row in batch for value in row):
        raise ComparativeAdapterError("logits must be finite")
    return copied


def _config_check(config: Any, contract: ComparativeModelContract) -> int:
    if getattr(config, "model_type", None) != contract.model_type:
        raise ComparativeAdapterError("unexpected model_type")
    if contract.architecture not in list(getattr(config, "architectures", []) or []):
        raise ComparativeAdapterError("unexpected model architecture")
    if int(getattr(config, "num_hidden_layers", -1)) != contract.num_hidden_layers:
        raise ComparativeAdapterError("unexpected num_hidden_layers")
    if int(getattr(config, "hidden_size", -1)) != contract.hidden_size:
        raise ComparativeAdapterError("unexpected hidden_size")
    vocab_size = getattr(config, "vocab_size", None)
    if isinstance(vocab_size, bool) or not isinstance(vocab_size, int) or vocab_size <= 0:
        raise ComparativeAdapterError("config vocab_size must be a positive integer")
    return vocab_size


def _runtime_check(model: Any, torch_module: Any) -> None:
    parameters = getattr(model, "parameters", None)
    if not callable(parameters):
        return  # Dependency-free fakes need not emulate parameters.
    try:
        observed = list(parameters())
    except Exception as exc:
        raise ComparativeAdapterError("could not inspect model parameters") from exc
    if not observed:
        raise ComparativeAdapterError("loaded model has no parameters")
    for parameter in observed:
        if getattr(getattr(parameter, "device", None), "type", None) != "cpu":
            raise ComparativeAdapterError("model parameter is not on CPU")
        if getattr(parameter, "dtype", None) != torch_module.float32:
            raise ComparativeAdapterError("model parameter is not float32")


class ComparativeTeacherForcingAdapter:
    """A local-only causal-LM adapter implementing the public score protocol."""

    def __init__(self, tokenizer: Any, model: Any, torch_module: Any, contract: ComparativeModelContract, vocab_size: int) -> None:
        contract.validate()
        if not bool(getattr(tokenizer, "is_fast", False)):
            raise ComparativeAdapterError("fast tokenizer required")
        self.tokenizer = tokenizer
        self.model = model
        self.torch = torch_module
        self.contract = contract
        self.vocab_size = vocab_size
        self.model_loaded = True
        if hasattr(model, "eval"):
            model.eval()

    @classmethod
    def load(
        cls,
        model_root: str | Path,
        *,
        contract: ComparativeModelContract,
        tokenizer_factory: Callable[..., Any] | None = None,
        model_factory: Callable[..., Any] | None = None,
        config_factory: Callable[..., Any] | None = None,
        torch_module: Any | None = None,
    ) -> "ComparativeTeacherForcingAdapter":
        """Load one approved snapshot with hard local-only factory arguments."""
        contract.validate()
        if not isinstance(model_root, (str, Path)) or not str(model_root):
            raise ComparativeAdapterError("model_root must be a non-empty local path")
        if "://" in str(model_root):
            raise ComparativeAdapterError("model_root must not be a network locator")
        if torch_module is None or any(factory is None for factory in (tokenizer_factory, model_factory, config_factory)):
            try:
                import torch
                from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
            except Exception as exc:  # pragma: no cover - runtime dependency boundary
                raise ComparativeAdapterError(f"torch/transformers unavailable: {exc}") from exc
            torch_module = torch if torch_module is None else torch_module
            config_factory = config_factory or AutoConfig.from_pretrained
            tokenizer_factory = tokenizer_factory or AutoTokenizer.from_pretrained
            model_factory = model_factory or AutoModelForCausalLM.from_pretrained
        root = str(Path(model_root).resolve())
        common = {"local_files_only": True, "trust_remote_code": False}
        try:
            config = config_factory(root, **common)
            vocab_size = _config_check(config, contract)
            tokenizer = tokenizer_factory(root, use_fast=True, **common)
            model = model_factory(root, torch_dtype=torch_module.float32, **common)
        except ComparativeAdapterError:
            raise
        except Exception as exc:
            raise ComparativeAdapterError(f"local model load failed: {exc}") from exc
        if hasattr(model, "to"):
            model.to(torch_module.device("cpu"))
        _runtime_check(model, torch_module)
        return cls(tokenizer, model, torch_module, contract, vocab_size)

    def _tokenize(self, text: str) -> tuple[Mapping[str, Any], dict[str, list[int]]]:
        batch = self.tokenizer(
            text,
            add_special_tokens=self.contract.add_special_tokens,
            return_attention_mask=True,
            return_tensors="pt",
        )
        if not isinstance(batch, Mapping):
            raise ComparativeAdapterError("tokenizer output must implement Mapping")
        try:
            return batch, validate_tokenizer_batch(_plain_batch(batch), vocab_size=self.vocab_size)
        except R3ResponseAdapterError as exc:
            raise ComparativeAdapterError(str(exc)) from exc

    def _forward_full(self, batch: Mapping[str, Any], token_count: int) -> list[list[list[float]]]:
        no_grad = getattr(self.torch, "inference_mode", None) or getattr(self.torch, "no_grad", None)
        try:
            with (no_grad() if callable(no_grad) else nullcontext()):
                outputs = self.model(
                    input_ids=batch["input_ids"], attention_mask=batch["attention_mask"],
                    output_hidden_states=False, output_attentions=False,
                    use_cache=False, return_dict=True,
                )
        except Exception as exc:
            raise ComparativeAdapterError(f"model forward failed: {exc}") from exc
        logits = outputs.get("logits") if isinstance(outputs, Mapping) else getattr(outputs, "logits", None)
        return _validate_logits(logits, token_count=token_count, vocab_size=self.vocab_size)

    def forward(self, prompt: str) -> dict[str, Any]:
        if not isinstance(prompt, str) or not prompt:
            raise ComparativeAdapterError("prompt must be a non-empty string")
        batch, normalized = self._tokenize(prompt)
        logits = self._forward_full(batch, len(normalized["input_ids"]))
        return {
            **normalized,
            "logits": logits,
            "model_output_accessed": True,
            "generation_used": False,
        }

    def score_prompt_choice(self, rendered_prompt: str, label: str) -> float:
        """Return one finite causal score, rejecting boundary-tokenisation drift."""
        if not isinstance(rendered_prompt, str) or not rendered_prompt:
            raise ComparativeAdapterError("rendered_prompt must be a non-empty string")
        if label not in _LABELS:
            raise ComparativeAdapterError("choice label must be one of A/B/C/D")
        prefix_batch, prefix = self._tokenize(rendered_prompt)
        full_batch, full = self._tokenize(rendered_prompt + f" {label}")
        prefix_ids = prefix["input_ids"]
        full_ids = full["input_ids"]
        if len(full_ids) <= len(prefix_ids) or full_ids[:len(prefix_ids)] != prefix_ids:
            raise ComparativeAdapterError("tokenizer prefix drift at answer boundary")
        continuation_ids = full_ids[len(prefix_ids):]
        if not continuation_ids:
            raise ComparativeAdapterError("choice continuation must contain at least one token")
        logits = self._forward_full(full_batch, len(full_ids))
        positions = list(range(len(prefix_ids) - 1, len(full_ids) - 1))
        try:
            return score_teacher_forced_choice(
                logits, continuation_ids, target_positions=positions, vocab_size=self.vocab_size,
            )
        except R3ResponseAdapterError as exc:
            raise ComparativeAdapterError(str(exc)) from exc


__all__ = [
    "ComparativeAdapterError",
    "ComparativeModelContract",
    "ComparativeTeacherForcingAdapter",
]
