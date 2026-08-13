from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping


class Lab01Error(RuntimeError):
    """Base exception for Lab01 lab utilities."""


class AdapterProtocolError(Lab01Error):
    """Raised when an adapter is missing required Lab01 hooks."""


@dataclass(frozen=True)
class TensorMeta:
    name: str
    shape: list[int]
    dtype: str
    backend: str
    digest: str
    finite_ratio: float
    max_abs: float
    mean_abs: float
    l2: float
    storage_path: str | None = None


@dataclass
class Lab01Artifact:
    raw_prompt: str
    rendered_prompt: str
    token_ids: list[int]
    token_pieces: list[str]
    special_flags: list[bool]
    attention_mask: list[list[int]]
    position_ids: list[list[int]]
    canonical_tensors: dict[str, TensorMeta]
    health: dict[str, dict[str, float | int | str]]
    instrumentation_parity: dict[str, float]
    repeatability: dict[str, Any]
    topk_logits: dict[str, Any] = field(default_factory=dict)
    empirical: bool = True
    evidence_eligible: bool = False
    artifact_class: str = "model-instrumentation"
    claim_ids: list[str] = field(default_factory=list)

    def stable_dump(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, ensure_ascii=False) + "\n"

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_class": self.artifact_class,
            "empirical": self.empirical,
            "evidence_eligible": self.evidence_eligible,
            "claim_ids": list(self.claim_ids),
            "raw_prompt": self.raw_prompt,
            "rendered_prompt": self.rendered_prompt,
            "token_ids": self.token_ids,
            "token_pieces": self.token_pieces,
            "special_flags": self.special_flags,
            "attention_mask": self.attention_mask,
            "position_ids": self.position_ids,
            "canonical_tensors": {
                name: {
                    "shape": meta.shape,
                    "dtype": meta.dtype,
                    "backend": meta.backend,
                    "digest": meta.digest,
                    "finite_ratio": meta.finite_ratio,
                    "max_abs": meta.max_abs,
                    "mean_abs": meta.mean_abs,
                    "l2": meta.l2,
                    "storage_path": meta.storage_path,
                }
                for name, meta in self.canonical_tensors.items()
            },
            "health": self.health,
            "instrumentation_parity": self.instrumentation_parity,
            "repeatability": self.repeatability,
            "topk_logits": self.topk_logits,
        }


def run_lab01(
    adapter: Any,
    prompt: str,
    *,
    repeats: int = 1,
    tolerance_by_backend: dict[str, dict[str, float]] | None = None,
    include_dense_storage: bool = False,
    artifact_root: str | Path | None = None,  # kept for compatibility
) -> Lab01Artifact:
    if repeats <= 0:
        raise Lab01Error("repeats must be >= 1")
    if include_dense_storage:
        raise Lab01Error("dense tensor storage unsupported; include_dense_storage must be False")
    if not hasattr(adapter, "run_prompt"):
        raise AdapterProtocolError("adapter must expose run_prompt(prompt, instrumented=False|True)")

    base, base_payload = _run_once(
        adapter,
        prompt,
        instrumented=True,
        include_dense_storage=False,
        artifact_root=artifact_root,
    )
    repeats_checks: list[dict[str, Any]] = []

    for index in range(1, repeats):
        _, payload = _run_once(
            adapter,
            prompt,
            instrumented=True,
            include_dense_storage=False,
            artifact_root=artifact_root,
        )
        checks = _compare_payloads(
            first=base_payload,
            second=payload,
            tolerance_by_backend=tolerance_by_backend,
            label=f"repeat:{index}",
        )
        repeats_checks.append(checks)

    if repeats_checks:
        repeat_report = {
            "repeats": repeats,
            "checks": repeats_checks,
            "max_abs_diff": max(item["max_abs_diff"] for item in repeats_checks),
            "status": "pass" if all(item["status"] == "pass" for item in repeats_checks) else "fail",
        }
    else:
        repeat_report = {"repeats": 1, "checks": []}

    instrumentation_checks = _check_instrumentation_parity(
        adapter=adapter,
        prompt=prompt,
        tolerance_by_backend=tolerance_by_backend,
    )
    base.instrumentation_parity = instrumentation_checks
    base.repeatability = repeat_report
    return base


def _run_once(
    adapter: Any,
    prompt: str,
    *,
    instrumented: bool,
    include_dense_storage: bool,
    artifact_root: str | Path | None,
) -> tuple[Lab01Artifact, Mapping[str, Any]]:
    raw = adapter.run_prompt(prompt=prompt, instrumented=instrumented)
    run = _validate_adapter_output(raw)
    canonical_tensors = _collect_canonical_tensors(
        raw,
        include_dense_storage=include_dense_storage,
        root=artifact_root,
    )
    health = _collect_health_metrics(
        canonical_tensors,
        include_dense_storage=include_dense_storage,
    )
    artifact = Lab01Artifact(
        raw_prompt=run["raw_prompt"],
        rendered_prompt=run["rendered_prompt"],
        token_ids=list(run["token_ids"]),
        token_pieces=list(run["token_pieces"]),
        special_flags=[bool(x) for x in run["special_flags"]],
        attention_mask=[list(x) for x in run["attention_mask"]],
        position_ids=[list(x) for x in run["position_ids"]],
        canonical_tensors=canonical_tensors,
        health=health,
        instrumentation_parity={},
        repeatability={},
        topk_logits={
            key: value
            for key, value in raw.items()
            if re.match(r"^resid_post_layer_\d+_topk$", key)
        },
        empirical=True,
        evidence_eligible=False,
        artifact_class="model-instrumentation",
        claim_ids=[],
    )
    return artifact, raw


def _validate_adapter_output(payload: Mapping[str, Any]) -> Dict[str, Any]:
    required = [
        "raw_prompt",
        "rendered_prompt",
        "token_ids",
        "token_pieces",
        "special_flags",
        "attention_mask",
        "position_ids",
        "token_inputs",
    ]
    missing = [field for field in required if field not in payload]
    if missing:
        raise AdapterProtocolError(f"adapter output missing required fields: {missing}")
    return {
        "raw_prompt": str(payload["raw_prompt"]),
        "rendered_prompt": str(payload["rendered_prompt"]),
        "token_ids": list(payload["token_ids"]),
        "token_pieces": list(payload["token_pieces"]),
        "special_flags": [bool(item["is_special"]) for item in payload["token_inputs"]],
        "attention_mask": [list(row) for row in payload["attention_mask"]],
        "position_ids": [list(row) for row in payload["position_ids"]],
    }


def _collect_canonical_tensors(
    payload: Mapping[str, Any],
    *,
    include_dense_storage: bool,
    root: str | Path | None,
) -> dict[str, TensorMeta]:
    _ = (include_dense_storage, root)
    canonical: dict[str, TensorMeta] = {}
    if "embedding_output" in payload:
        canonical["embedding_output"] = _to_meta("embedding_output", payload["embedding_output"])

    residue = re.compile(r"^resid_post_layer_\d+$")
    for key, value in payload.items():
        if residue.match(key):
            canonical[key] = _to_meta(key, value)

    if "final_norm_output" in payload:
        canonical["final_norm_output"] = _to_meta("final_norm_output", payload["final_norm_output"])
    if "model_logits" in payload:
        canonical["model_logits"] = _to_meta("model_logits", payload["model_logits"])
    if "logits" in payload:
        canonical["model_logits_raw"] = _to_meta("model_logits_raw", payload["logits"])
    if "hidden_states" in payload:
        hidden_states = payload["hidden_states"] or []
        if isinstance(hidden_states, (list, tuple)) and hidden_states:
            if "embedding_output" not in canonical:
                canonical["embedding_output"] = _to_meta("embedding_output", hidden_states[0])
    return canonical


def _collect_health_metrics(
    canonical: dict[str, TensorMeta],
    *,
    include_dense_storage: bool,
) -> dict[str, dict[str, float | int | str]]:
    _ = include_dense_storage
    health: dict[str, dict[str, float | int | str]] = {}
    for name, meta in canonical.items():
        health[name] = {
            "shape": meta.shape,
            "dtype": meta.dtype,
            "backend": meta.backend,
            "finite_ratio": meta.finite_ratio,
            "max_abs": meta.max_abs,
            "mean_abs": meta.mean_abs,
            "l2": meta.l2,
            "has_dense_storage": False,
        }
    return health


def _check_instrumentation_parity(
    *,
    adapter: Any,
    prompt: str,
    tolerance_by_backend: dict[str, dict[str, float]] | None,
) -> dict[str, float]:
    instrumented = adapter.run_prompt(prompt=prompt, instrumented=True)
    plain = adapter.run_prompt(prompt=prompt, instrumented=False)
    cross_run = _compare_payloads(
        instrumented,
        plain,
        tolerance_by_backend=tolerance_by_backend,
        label="instrumentation",
    )
    final_lens = _flatten_and_compare(
        instrumented.get("model_logits"),
        instrumented.get("logits"),
        tolerance_by_backend=tolerance_by_backend or _default_tolerance_policy(),
    )
    cross_run["final_lens_parity_status"] = final_lens["status"]
    cross_run["final_lens_parity_max_abs_diff"] = final_lens["max_abs_diff"]
    if cross_run["status"] == "pass" and final_lens["status"] != "pass":
        cross_run["status"] = "fail"
    return cross_run


def _compare_payloads(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
    *,
    tolerance_by_backend: dict[str, dict[str, float]] | None,
    label: str,
) -> dict[str, Any]:
    policy = tolerance_by_backend or _default_tolerance_policy()
    model_logit_check = _flatten_and_compare(
        first.get("model_logits") if "model_logits" in first else _extract_logit_like(first),
        second.get("model_logits") if "model_logits" in second else _extract_logit_like(second),
        tolerance_by_backend=policy,
    )
    final_norm_check = _flatten_and_compare(
        first.get("final_norm_output"),
        second.get("final_norm_output"),
        tolerance_by_backend=policy,
    )
    status = model_logit_check["status"] if model_logit_check["status"] == final_norm_check["status"] else "mixed"
    return {
        "label": label,
        "status": status,
        "max_abs_diff": max(model_logit_check["max_abs_diff"], final_norm_check["max_abs_diff"]),
        "numel": max(model_logit_check["numel"], final_norm_check["numel"]),
        "final_norm_output_diff": final_norm_check["max_abs_diff"],
        "model_logits_diff": model_logit_check["max_abs_diff"],
        "rtol": model_logit_check["rtol"],
        "atol": model_logit_check["atol"],
    }


def _extract_logit_like(payload: Mapping[str, Any]) -> Any:
    if "model_logits_raw" in payload:
        return payload["model_logits_raw"]
    if "logits" in payload:
        return payload["logits"]
    return payload


def _flatten_and_compare(
    first: Any,
    second: Any,
    *,
    tolerance_by_backend: dict[str, dict[str, float]],
) -> dict[str, Any]:
    flat_a = _flatten_numbers(_coerce_scalar_matrix(first))
    flat_b = _flatten_numbers(_coerce_scalar_matrix(second))
    n = max(len(flat_a), len(flat_b))
    if len(flat_a) != len(flat_b):
        return {"status": "shape_mismatch", "max_abs_diff": float("inf"), "numel": n, "rtol": 0.0, "atol": 0.0}
    if n == 0:
        return {"status": "empty", "max_abs_diff": 0.0, "numel": 0, "rtol": 0.0, "atol": 0.0}

    backend, dtype = _infer_backend_and_dtype(first)
    tolerance = tolerance_by_backend.get(backend, tolerance_by_backend["default"]).get(dtype, {"rtol": 1e-5, "atol": 1e-5})
    rtol = float(tolerance.get("rtol", 1e-5))
    atol = float(tolerance.get("atol", 1e-5))

    max_abs_diff = 0.0
    for a, b in zip(flat_a, flat_b):
        diff = abs(float(a) - float(b))
        max_abs_diff = max(max_abs_diff, diff)
        if diff > atol + abs(float(b)) * rtol:
            return {
                "status": "fail",
                "max_abs_diff": max_abs_diff,
                "numel": n,
                "rtol": rtol,
                "atol": atol,
            }
    return {"status": "pass", "max_abs_diff": max_abs_diff, "numel": n, "rtol": rtol, "atol": atol}


def _to_meta(name: str, value: Any, *, root: str | Path | None = None, include_dense_storage: bool = False) -> TensorMeta:
    _ = (root, include_dense_storage)
    if include_dense_storage:
        raise Lab01Error("dense tensor storage unsupported; provide external artifact handles instead")
    shape, dtype, backend = _infer_shape_dtype_backend(value)
    digest = _hash_payload(value)
    finite_ratio, max_abs, mean_abs, l2 = _numerical_health(value)
    return TensorMeta(
        name=name,
        shape=shape,
        dtype=dtype,
        backend=backend,
        digest=digest,
        finite_ratio=finite_ratio,
        max_abs=max_abs,
        mean_abs=mean_abs,
        l2=l2,
    )


def _coerce_scalar_matrix(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def _flatten_numbers(value: Any) -> list[float]:
    if isinstance(value, dict):
        out: list[float] = []
        for key in sorted(value.keys()):
            out.extend(_flatten_numbers(value[key]))
        return out
    if isinstance(value, (list, tuple)):
        flat: list[float] = []
        for item in value:
            flat.extend(_flatten_numbers(item))
        return flat
    if isinstance(value, (int, float, bool)):
        return [float(value)]
    return [0.0]


def _infer_shape_dtype_backend(value: Any) -> tuple[list[int], str, str]:
    raw = _coerce_scalar_matrix(value)
    shape = _infer_shape(raw)
    dtype = _normalize_dtype_name(_infer_dtype(raw))
    backend = "python"
    if hasattr(value, "device") and hasattr(value.device, "type"):
        backend = str(value.device.type)
    elif hasattr(value, "dtype"):
        backend = "pytorch"
    return shape, dtype, backend


def _infer_backend_and_dtype(value: Any) -> tuple[str, str]:
    _, dtype, backend = _infer_shape_dtype_backend(value)
    return backend, dtype


def _infer_shape(value: Any) -> list[int]:
    if isinstance(value, (list, tuple)):
        if not value:
            return [0]
        return [len(value)] + _infer_shape(value[0])
    if hasattr(value, "shape"):
        try:
            return list(value.shape)
        except Exception:
            return []
    return []


def _infer_dtype(value: Any) -> str:
    if hasattr(value, "dtype"):
        return str(value.dtype)
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "unknown"


def _normalize_dtype_name(value: Any) -> str:
    text = str(value).lower()
    if "float16" in text or "fp16" in text:
        return "float16"
    if "bfloat16" in text or "bfloat" in text:
        return "bfloat16"
    if "float32" in text or "fp32" in text:
        return "float32"
    if "float64" in text or "fp64" in text:
        return "float64"
    if text.startswith("bool"):
        return "bool"
    if text.startswith("int"):
        return "int"
    return text if text in {"float16", "bfloat16", "float32", "float64", "int", "bool"} else "unknown"


def _numerical_health(value: Any) -> tuple[float, float, float, float]:
    flat = _flatten_numbers(_coerce_scalar_matrix(value))
    if not flat:
        return 1.0, 0.0, 0.0, 0.0
    finite_count = 0
    max_abs = 0.0
    l2 = 0.0
    for item in flat:
        is_finite = item == item and item != float("inf") and item != float("-inf")
        if is_finite:
            finite_count += 1
            max_abs = max(max_abs, abs(item))
            l2 += item * item
    finite_ratio = finite_count / len(flat)
    mean_abs = sum(abs(item) for item in flat) / len(flat)
    return finite_ratio, max_abs, mean_abs, l2 ** 0.5


def _hash_payload(value: Any) -> str:
    try:
        payload = _coerce_scalar_matrix(value)
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    except TypeError:
        blob = repr(value).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _default_tolerance_policy() -> dict[str, dict[str, float]]:
    return {
        "default": {
            "float16": {"rtol": 2e-3, "atol": 2e-3},
            "float32": {"rtol": 2e-5, "atol": 2e-6},
            "float64": {"rtol": 1e-6, "atol": 1e-8},
            "bfloat16": {"rtol": 4e-3, "atol": 2e-3},
            "int": {"rtol": 0.0, "atol": 0.0},
            "bool": {"rtol": 0.0, "atol": 0.0},
            "unknown": {"rtol": 1e-5, "atol": 1e-5},
        },
        "cuda": {
            "float16": {"rtol": 3e-3, "atol": 3e-3},
            "float32": {"rtol": 2e-5, "atol": 1e-6},
            "float64": {"rtol": 1e-6, "atol": 1e-8},
            "bfloat16": {"rtol": 4e-3, "atol": 3e-3},
            "int": {"rtol": 0.0, "atol": 0.0},
            "bool": {"rtol": 0.0, "atol": 0.0},
            "unknown": {"rtol": 1e-4, "atol": 1e-4},
        },
        "mps": {
            "float16": {"rtol": 3e-3, "atol": 3e-3},
            "float32": {"rtol": 2e-5, "atol": 1e-6},
            "float64": {"rtol": 1e-6, "atol": 1e-8},
            "bfloat16": {"rtol": 4e-3, "atol": 3e-3},
            "int": {"rtol": 0.0, "atol": 0.0},
            "bool": {"rtol": 0.0, "atol": 0.0},
            "unknown": {"rtol": 1e-4, "atol": 1e-4},
        },
    }


def stable_json_dumps(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
