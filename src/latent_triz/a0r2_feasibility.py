"""Bounded, local-only A0-R2 runtime feasibility for the frozen SmolLM2 snapshot."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import resource
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from .a0r2_acquisition import acquire_a0r2_runtime
from .validator import validate


class A0R2FeasibilityError(RuntimeError):
    """Raised when the frozen feasibility contract cannot be executed safely."""


MODEL_ID = "HuggingFaceTB/SmolLM2-360M"
MODEL_REVISION = "f8027fd0eaeea54caa13c31d31b9fdc459c38b49"
CONTRACT_REL = Path("experiments/a0r2-independent-model/feasibility-contract.json")
CONTRACT_SCHEMA_REL = Path("schemas/a0r2-feasibility-contract.schema.json")
RECEIPT_SCHEMA_REL = Path("schemas/a0r2-feasibility-receipt.schema.json")
ACQUISITION_CONTRACT_REL = Path("experiments/a0r2-independent-model/acquisition-contract.json")
INTEGRITY_RECEIPT_REL = Path("results/a0r2/preexecution/smollm2-360m-f8027fd0/integrity-receipt.json")
DEFAULT_RECEIPT_REL = Path("results/a0r2/preexecution/smollm2-360m-f8027fd0/feasibility-receipt.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R2FeasibilityError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise A0R2FeasibilityError(f"{label} must be a JSON object")
    return value


def _load_contract(root: Path, contract_path: Path) -> tuple[dict[str, Any], str]:
    contract = _read_object(contract_path, "feasibility contract")
    schema = _read_object(root / CONTRACT_SCHEMA_REL, "feasibility schema")
    issues = validate(contract, schema)
    if issues:
        raise A0R2FeasibilityError("feasibility contract validation failed: " + "; ".join(str(x) for x in issues))

    predecessor = contract.get("predecessor")
    if not isinstance(predecessor, Mapping):
        raise A0R2FeasibilityError("feasibility predecessor binding missing")
    bound = (
        (root / ACQUISITION_CONTRACT_REL, predecessor.get("acquisition_contract_sha256"), "acquisition contract"),
        (root / INTEGRITY_RECEIPT_REL, predecessor.get("integrity_receipt_sha256"), "integrity receipt"),
    )
    for path, expected, label in bound:
        if not isinstance(expected, str) or _sha256(path) != expected:
            raise A0R2FeasibilityError(f"{label} hash mismatch")
    return contract, _sha256(contract_path)


def _peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


class TransformersFeasibilityBackend:
    """Minimal local-only causal-LM loader; it never generates or decodes output."""

    def __init__(self, model_root: Path, contract: Mapping[str, Any]) -> None:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        try:
            import torch
            from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
        except Exception as exc:  # pragma: no cover - exercised only in the material environment
            raise A0R2FeasibilityError(f"torch/transformers unavailable: {exc}") from exc

        self.torch = torch
        self.timings: dict[str, float] = {}
        started = time.perf_counter()
        config = AutoConfig.from_pretrained(str(model_root), local_files_only=True)
        self.timings["config_load_seconds"] = time.perf_counter() - started
        expected_model = contract["model"]
        if config.model_type != expected_model["model_type"]:
            raise A0R2FeasibilityError(f"model_type mismatch: {config.model_type!r}")
        if int(config.num_hidden_layers) != int(expected_model["num_hidden_layers"]):
            raise A0R2FeasibilityError("num_hidden_layers mismatch")
        if int(config.hidden_size) != int(expected_model["hidden_size"]):
            raise A0R2FeasibilityError("hidden_size mismatch")
        if expected_model["architecture"] not in list(getattr(config, "architectures", []) or []):
            raise A0R2FeasibilityError("architecture mismatch")

        started = time.perf_counter()
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(model_root), local_files_only=True, use_fast=True
        )
        self.timings["tokenizer_load_seconds"] = time.perf_counter() - started
        started = time.perf_counter()
        self.model = AutoModelForCausalLM.from_pretrained(
            str(model_root), local_files_only=True, dtype=torch.float32
        )
        self.model.to(torch.device("cpu"))
        self.model.eval()
        self.timings["model_load_seconds"] = time.perf_counter() - started

    def run_probe(self, prompt: str, *, maximum_prompt_tokens: int, inference_passes: int) -> dict[str, Any]:
        if not bool(getattr(self.tokenizer, "is_fast", False)):
            raise A0R2FeasibilityError("fast tokenizer required")
        encoded = self.tokenizer(
            prompt,
            return_tensors="pt",
            return_attention_mask=True,
            return_offsets_mapping=True,
            add_special_tokens=True,
        )
        offsets = encoded.pop("offset_mapping", None)
        if offsets is None:
            raise A0R2FeasibilityError("fast tokenizer offset mapping unavailable")
        token_count = int(encoded["input_ids"].shape[-1])
        if token_count < 1 or token_count > maximum_prompt_tokens:
            raise A0R2FeasibilityError(f"prompt token count outside contract: {token_count}")
        encoded = {key: value.to(self.torch.device("cpu")) for key, value in encoded.items()}

        outputs: list[Any] = []
        forward_seconds: list[float] = []
        with self.torch.inference_mode():
            for _ in range(inference_passes):
                started = time.perf_counter()
                output = self.model(
                    **encoded, use_cache=False, output_hidden_states=True, return_dict=True
                )
                forward_seconds.append(time.perf_counter() - started)
                outputs.append(output)

        first = outputs[0]
        hidden = getattr(first, "hidden_states", None)
        logits = getattr(first, "logits", None)
        if not isinstance(hidden, (tuple, list)) or logits is None:
            raise A0R2FeasibilityError("hidden states or logits missing")
        hidden_count = len(hidden)
        final_hidden = hidden[-1]
        if not bool(self.torch.isfinite(final_hidden).all()):
            raise A0R2FeasibilityError("non-finite final hidden state")
        if not bool(self.torch.isfinite(logits).all()):
            raise A0R2FeasibilityError("non-finite logits")
        repeat_diff = 0.0
        if len(outputs) > 1:
            repeat_diff = float((outputs[0].logits - outputs[1].logits).abs().max().item())
        return {
            "tokenizer_fast": True,
            "offsets_supported": True,
            "token_count": token_count,
            "hidden_states_count": hidden_count,
            "final_hidden_shape": [int(item) for item in final_hidden.shape],
            "logits_shape": [int(item) for item in logits.shape],
            "finite_hidden_states": True,
            "finite_logits": True,
            "max_abs_repeat_difference": repeat_diff,
            "forward_seconds": forward_seconds,
        }


BackendFactory = Callable[[Path, Mapping[str, Any]], Any]


def run_feasibility(
    *,
    root: Path,
    model_root: Path,
    contract_path: Path,
    created_at: str,
    backend_factory: BackendFactory = TransformersFeasibilityBackend,
) -> dict[str, Any]:
    started = time.perf_counter()
    contract, contract_sha256 = _load_contract(root, contract_path)
    # This verifier is explicitly no-download and completes before importing model libraries.
    acquire_a0r2_runtime(model_root, allow_download=False)
    runtime_contract = contract["runtime"]
    compatibility_contract = contract["compatibility"]
    probe_text = str(contract["probe"]["text"])

    backend = backend_factory(model_root, contract)
    metrics = backend.run_probe(
        probe_text,
        maximum_prompt_tokens=int(runtime_contract["maximum_prompt_tokens"]),
        inference_passes=int(runtime_contract["inference_passes"]),
    )
    expected_count = int(compatibility_contract["expected_hidden_states_count"])
    expected_index = int(compatibility_contract["primary_hidden_states_tuple_index"])
    hidden_shape = metrics.get("final_hidden_shape")
    logits_shape = metrics.get("logits_shape")
    checks = {
        "fast_tokenizer_offsets": bool(metrics.get("tokenizer_fast")) and bool(metrics.get("offsets_supported")),
        "hidden_states_count": int(metrics.get("hidden_states_count", -1)) == expected_count,
        "primary_tuple_index_available": expected_index < int(metrics.get("hidden_states_count", 0)),
        "hidden_size": isinstance(hidden_shape, list) and len(hidden_shape) == 3 and hidden_shape[-1] == int(contract["model"]["hidden_size"]),
        "logits_shape": isinstance(logits_shape, list) and len(logits_shape) == 3 and logits_shape[0] == 1,
        "finite_hidden_states": bool(metrics.get("finite_hidden_states")),
        "finite_logits": bool(metrics.get("finite_logits")),
        "repeatability": float(metrics.get("max_abs_repeat_difference", float("inf"))) <= float(compatibility_contract["repeatability_max_abs_difference"]),
    }
    elapsed = time.perf_counter() - started
    peak = _peak_rss_bytes()
    within_envelope = (
        elapsed <= float(runtime_contract["maximum_wall_seconds"])
        and peak <= int(runtime_contract["maximum_peak_rss_bytes"])
    )
    compatible = all(checks.values()) and within_envelope
    backend_timings = getattr(backend, "timings", {})
    return {
        "artifact_class": "a0r2-feasibility-receipt",
        "status": "compatible" if compatible else "incompatible",
        "created_at": created_at,
        "scientific_status": "instrumentation_only",
        "empirical": False,
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "contract_sha256": contract_sha256,
        "integrity_receipt_sha256": contract["predecessor"]["integrity_receipt_sha256"],
        "model": contract["model"],
        "runtime": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "torch_version": _version("torch"),
            "transformers_version": _version("transformers"),
            "device": "cpu",
            "torch_dtype": "float32",
            "network_access": False,
            "generation": False,
            "process_peak_rss_bytes": peak,
            "maximum_peak_rss_bytes": int(runtime_contract["maximum_peak_rss_bytes"]),
            "within_resource_envelope": within_envelope,
        },
        "probe": {
            "text_sha256": _text_sha256(probe_text),
            "token_count": int(metrics["token_count"]),
            "inference_passes": int(runtime_contract["inference_passes"]),
            "output_content_retained": False,
        },
        "compatibility": {
            "checks": checks,
            "hidden_states_count": int(metrics["hidden_states_count"]),
            "primary_hidden_states_tuple_index": expected_index,
            "final_hidden_shape": hidden_shape,
            "logits_shape": logits_shape,
            "max_abs_repeat_difference": float(metrics["max_abs_repeat_difference"]),
            "compatible": compatible,
        },
        "timings_seconds": {
            "config_load": float(backend_timings.get("config_load_seconds", 0.0)),
            "tokenizer_load": float(backend_timings.get("tokenizer_load_seconds", 0.0)),
            "model_load": float(backend_timings.get("model_load_seconds", 0.0)),
            "forward_passes": [float(x) for x in metrics.get("forward_seconds", [])],
            "total": elapsed,
        },
        "access": {
            "model_loaded": "accessed",
            "feasibility_tested": "accessed",
            "model_output_accessed": "accessed",
            "model_output_content_retained": "not_accessed",
            "sealed_targets_accessed": "not_accessed",
        },
    }


def write_receipt_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(encoded)
    except FileExistsError as exc:
        raise A0R2FeasibilityError(f"refusing to overwrite receipt: {path}") from exc


def verify_receipt(*, root: Path, contract_path: Path, receipt_path: Path) -> dict[str, Any]:
    contract, contract_sha256 = _load_contract(root, contract_path)
    receipt = _read_object(receipt_path, "feasibility receipt")
    schema = _read_object(root / RECEIPT_SCHEMA_REL, "feasibility receipt schema")
    issues = validate(receipt, schema)
    if issues:
        raise A0R2FeasibilityError("feasibility receipt validation failed: " + "; ".join(str(x) for x in issues))
    if receipt.get("contract_sha256") != contract_sha256:
        raise A0R2FeasibilityError("feasibility receipt contract hash mismatch")
    if receipt.get("integrity_receipt_sha256") != contract["predecessor"]["integrity_receipt_sha256"]:
        raise A0R2FeasibilityError("feasibility receipt predecessor hash mismatch")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run bounded local-only A0-R2 feasibility")
    parser.add_argument("--root", default=".")
    parser.add_argument("--model-root")
    parser.add_argument("--contract", default=str(CONTRACT_REL))
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT_REL))
    parser.add_argument("--created-at")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    contract_path = Path(args.contract)
    if not contract_path.is_absolute():
        contract_path = root / contract_path
    receipt_path = Path(args.receipt)
    if not receipt_path.is_absolute():
        receipt_path = root / receipt_path
    if args.verify_only:
        payload = verify_receipt(root=root, contract_path=contract_path, receipt_path=receipt_path)
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    if not args.model_root:
        parser.error("--model-root is required unless --verify-only is used")
    if not args.created_at:
        parser.error("--created-at is required unless --verify-only is used")
    try:
        payload = run_feasibility(
            root=root,
            model_root=Path(args.model_root),
            contract_path=contract_path,
            created_at=args.created_at,
        )
    except Exception as exc:
        error_text = f"{type(exc).__name__}:{exc}"
        payload = {
            "artifact_class": "a0r2-feasibility-receipt",
            "status": "failed",
            "created_at": args.created_at,
            "scientific_status": "instrumentation_only",
            "empirical": False,
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "contract_sha256": _sha256(contract_path) if contract_path.is_file() else "0" * 64,
            "integrity_receipt_sha256": _sha256(root / INTEGRITY_RECEIPT_REL)
            if (root / INTEGRITY_RECEIPT_REL).is_file()
            else "0" * 64,
            "failure": {
                "stage": "bounded_feasibility",
                "error_type": type(exc).__name__,
                "error_digest": _text_sha256(error_text),
            },
            "access": {
                "model_loaded": "unknown",
                "feasibility_tested": "unknown",
                "model_output_accessed": "unknown",
                "model_output_content_retained": "unknown",
                "sealed_targets_accessed": "not_accessed",
            },
        }
    write_receipt_exclusive(receipt_path, payload)
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if payload["status"] == "compatible" else 2


if __name__ == "__main__":
    raise SystemExit(main())
