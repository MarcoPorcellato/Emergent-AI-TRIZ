from __future__ import annotations

from pathlib import Path
from typing import Any


class Lab01TransformersError(RuntimeError):
    """Raised when local GPT-NeoX loading or inference is not possible."""


def _to_matrix(value: Any) -> list[list[int]]:
    data = value.tolist() if hasattr(value, "tolist") else list(value)
    if not data:
        return []
    if not isinstance(data[0], (list, tuple)):
        return [list(data)]
    return [list(row) for row in data]


def _to_int_list(value: Any) -> list[int]:
    if hasattr(value, "tolist"):
        return [int(item) for item in value.tolist()]
    return [int(item) for item in list(value)]


class GPTNeoXTransformersAdapter:
    """Adapter that wraps a local-only GPT-NeoX model from transformers."""

    def __init__(
        self,
        model_root: str | Path,
        *,
        local_files_only: bool = True,
        device: str = "cpu",
        torch_dtype: str = "float32",
        top_k: int = 3,
    ) -> None:
        if not local_files_only:
            raise Lab01TransformersError("transformers adapter only supports local_files_only=True")
        self.model_root = Path(model_root)
        if not self.model_root.exists():
            raise Lab01TransformersError(f"model root not found: {self.model_root}")
        try:
            import torch
            from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
        except Exception as exc:  # pragma: no cover
            raise Lab01TransformersError(f"transformers/torch unavailable: {exc}") from exc

        self._torch = torch
        dtype = getattr(torch, torch_dtype, None)
        if dtype is None:
            raise Lab01TransformersError(f"unsupported torch_dtype: {torch_dtype}")
        config = AutoConfig.from_pretrained(str(self.model_root), local_files_only=True)
        if config.model_type != "gpt_neox":
            raise Lab01TransformersError(f"unsupported model_type {config.model_type!r}; expected gpt_neox")
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
        except Exception as exc:
            raise Lab01TransformersError(f"failed loading local model from {self.model_root}: {exc}") from exc
        self.model.to(torch.device(device))
        self.model.eval()
        self.top_k = int(top_k)
        if self.top_k < 1:
            raise Lab01TransformersError("top_k must be >= 1")

    def run_prompt(self, *, prompt: str, instrumented: bool = True) -> dict[str, Any]:
        encoded = self._encode(prompt)
        encoded["position_ids"] = self._build_position_ids(encoded["attention_mask"])
        with self._torch.no_grad():
            outputs = self._run_model(prompt_inputs=encoded, instrumented=instrumented)
        tensor_info = self._collect_tensors_from_outputs(outputs, instrumented=instrumented)
        per_layer_topk = self._compute_per_layer_logit_lens_topk(tensor_info["residuals"])
        model_logits = self._compute_logit_lens(tensor_info["final_norm_output"])
        payload: dict[str, Any] = {
            "raw_prompt": str(prompt),
            "rendered_prompt": str(prompt),
            "token_ids": _to_int_list(encoded["input_ids"][0]),
            "token_pieces": [str(token) for token in self.tokenizer.convert_ids_to_tokens(encoded["input_ids"][0])],
            "token_inputs": [
                {
                    "token_id": int(token_id),
                    "token_piece": str(token),
                    "is_special": bool(special),
                }
                for token_id, token, special in zip(
                    _to_int_list(encoded["input_ids"][0]),
                    self.tokenizer.convert_ids_to_tokens(encoded["input_ids"][0]),
                    [bool(flag) for flag in self._special_token_flags(encoded["input_ids"][0])],
                )
            ],
            "special_flags": [bool(flag) for flag in self._special_token_flags(encoded["input_ids"][0])],
            "attention_mask": _to_matrix(encoded["attention_mask"]),
            "position_ids": _to_matrix(encoded["position_ids"]),
            "hidden_states": tuple(outputs.hidden_states),
            "embedding_output": tensor_info.get("embedding_output"),
            "final_norm_output": tensor_info.get("final_norm_output"),
            "logits": outputs.logits,
            "model_logits": model_logits,
            "instrumented": bool(instrumented),
        }
        payload.update(tensor_info.get("residuals", {}))
        payload.update(per_layer_topk)
        return payload

    def _run_model(self, prompt_inputs: dict[str, Any], *, instrumented: bool) -> Any:
        final_norm = self.model.gpt_neox.final_layer_norm
        capture: dict[str, Any] = {}
        pre_hook = None
        post_hook = None

        if instrumented:
            def pre_hook_func(module, args):  # type: ignore[no-redef]
                del module
                if args:
                    capture["input"] = args[0]
                return None

            def post_hook_func(module, _args, output):  # type: ignore[no-redef]
                del module
                capture["output"] = output
                return output

            pre_hook = final_norm.register_forward_pre_hook(pre_hook_func)
            post_hook = final_norm.register_forward_hook(post_hook_func)

        try:
            outputs = self.model(
                **prompt_inputs,
                use_cache=False,
                output_hidden_states=True,
                return_dict=True,
            )
            if instrumented:
                outputs.final_layer_norm_input = capture.get("input")
                outputs.final_layer_norm_output = capture.get("output", None)
            else:
                outputs.final_layer_norm_input = outputs.hidden_states[-1] if outputs.hidden_states else None
                outputs.final_layer_norm_output = outputs.hidden_states[-1] if outputs.hidden_states else None
        finally:
            if pre_hook is not None:
                pre_hook.remove()
            if post_hook is not None:
                post_hook.remove()
        return outputs

    def _collect_tensors_from_outputs(self, outputs: Any, *, instrumented: bool) -> dict[str, Any]:
        del instrumented
        hidden = getattr(outputs, "hidden_states", None) or []
        residuals: dict[str, Any] = {}
        embedding_output = hidden[0] if isinstance(hidden, (list, tuple)) and hidden else None

        if isinstance(hidden, (list, tuple)) and hidden:
            for idx in range(1, max(0, len(hidden) - 1)):
                residuals[f"resid_post_layer_{idx-1}"] = hidden[idx]
            if outputs.final_layer_norm_input is not None:
                final_layer_index = int(self.model.config.num_hidden_layers) - 1
                residuals[f"resid_post_layer_{final_layer_index}"] = outputs.final_layer_norm_input

        final_norm_output = outputs.final_layer_norm_output
        if final_norm_output is None:
            raise Lab01TransformersError("final_layer_norm_output not available; instrumentation contract broken")
        return {
            "embedding_output": embedding_output,
            "final_norm_output": final_norm_output,
            "residuals": residuals,
        }

    def _unembed(self, normalized_output: Any) -> Any:
        output_head = self.model.get_output_embeddings()
        if output_head is None:
            raise Lab01TransformersError("output embedding head missing; cannot compute canonical logit lens")
        return output_head(normalized_output)

    def _compute_logit_lens(self, final_layer_output: Any) -> Any:
        """Project an already final-normalized residual to vocabulary logits."""
        return self._unembed(final_layer_output)

    def _compute_per_layer_logit_lens_topk(self, residuals: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in residuals.items():
            if not isinstance(value, self._torch.Tensor):
                continue
            logits = self._unembed(self.model.gpt_neox.final_layer_norm(value))
            top_values, top_ids = self._torch.topk(logits, k=min(self.top_k, logits.shape[-1]), dim=-1)
            top_ids_list = top_ids.cpu().tolist()
            values_list = top_values.cpu().tolist()
            last_position_ids = top_ids_list[0][-1] if top_ids_list and top_ids_list[0] else []
            last_position_values = values_list[0][-1] if values_list and values_list[0] else []
            # Emit only the last input position; dense layer logits never leave memory.
            out[f"{key}_topk"] = {
                "token_ids": [int(item) for item in last_position_ids],
                "token_pieces": [str(self.tokenizer.convert_ids_to_tokens(int(item))) for item in last_position_ids],
                "values": [float(v) for v in last_position_values],
            }
        return out

    def _build_position_ids(self, attention_mask: Any) -> Any:
        attention = attention_mask.to(dtype=self._torch.long)
        mask = _to_matrix(attention)[0]
        position_row: list[int] = []
        counter = 0
        for bit in mask:
            if bit:
                position_row.append(counter)
                counter += 1
            else:
                position_row.append(-1)
        if attention_mask.dim() == 1:
            return self._torch.tensor([position_row], dtype=self._torch.long, device=attention_mask.device)
        return self._torch.tensor([position_row], dtype=self._torch.long, device=attention_mask.device)

    def _special_token_flags(self, token_ids: Any) -> list[bool]:
        if hasattr(self.tokenizer, "get_special_tokens_mask"):
            ids = _to_int_list(token_ids)
            return [bool(item) for item in self.tokenizer.get_special_tokens_mask(ids, already_has_special_tokens=True)]
        return [False for _ in _to_int_list(token_ids)]

    def _encode(self, prompt: str) -> dict[str, Any]:
        return self.tokenizer(
            prompt,
            return_tensors="pt",
            add_special_tokens=True,
            return_attention_mask=True,
        )
