"""Target-free contract checks for the two next EXP-001 model controls.

This module validates the exact selection, authorization, protocol envelope,
and local integrity receipts without importing torch/transformers or opening
sealed targets. Material runners must call it immediately before model load.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
from typing import Any


class NextModelContractError(ValueError):
    """Raised when the next-model contract is missing or has drifted."""


NEXT_MODELS: dict[str, dict[str, Any]] = {
    "EleutherAI/gpt-neo-125m": {
        "revision": "21def0189f5705e2521767faed922f1f15e7d7db",
        "model_type": "gpt_neo",
        "architecture": "GPTNeoForCausalLM",
        "layers": 12,
        "hidden": 768,
        "vocab": 50257,
        "tokenizer_class": "GPT2Tokenizer",
        "tokenizer_max_length": 2048,
        "model_context": 2048,
        "key": "gpt-neo-125m-21def018",
        "receipt": "results/exp001-comparative/preexecution/gpt-neo-125m-integrity-receipt.json",
    },
    "Qwen/Qwen2.5-0.5B": {
        "revision": "060db6499f32faf8b98477b0a26969ef7d8b9987",
        "model_type": "qwen2",
        "architecture": "Qwen2ForCausalLM",
        "layers": 24,
        "hidden": 896,
        "vocab": 151936,
        "tokenizer_class": "Qwen2Tokenizer",
        "tokenizer_max_length": 131072,
        "model_context": 32768,
        "key": "qwen2.5-0.5b-060db649",
        "receipt": "results/exp001-comparative/preexecution/qwen2.5-0.5b-integrity-receipt.json",
    },
}


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NextModelContractError(f"cannot read {path}") from exc
    if not isinstance(value, dict):
        raise NextModelContractError(f"{path} must contain an object")
    return value


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1 << 20), b""):
                digest.update(block)
    except OSError as exc:
        raise NextModelContractError(f"cannot hash {path}") from exc
    return digest.hexdigest()


def _candidate(auth: Mapping[str, Any], model_id: str) -> Mapping[str, Any]:
    for item in auth.get("candidates", []):
        if isinstance(item, Mapping) and item.get("model_id") == model_id:
            return item
    raise NextModelContractError(f"authorization does not bind {model_id}")


def validate_next_model_contract(root: str | Path, model_id: str, *, material_execution: bool = False) -> dict[str, Any]:
    """Validate one exact candidate before any model or target access."""
    if model_id not in NEXT_MODELS:
        raise NextModelContractError("model is not in the frozen next-model selection")
    repo = Path(root).resolve()
    meta = NEXT_MODELS[model_id]
    selection = _json(repo / "experiments/exp001-comparative-reference/next-model-selection.json")
    auth = _json(repo / "experiments/exp001-comparative-reference/next-model-authorization.json")
    protocol = _json(repo / "experiments/exp001-comparative-reference/protocol.json")
    if selection.get("selection_observed_prior_result") is not False or selection.get("selection_status") not in {"proposal_frozen_no_download", "approval_requested", "authorized"}:
        raise NextModelContractError("selection is not an independent frozen proposal")
    selected = next((item for item in selection.get("candidates", []) if isinstance(item, Mapping) and item.get("model_id") == model_id), None)
    if not isinstance(selected, Mapping) or selected.get("revision") != meta["revision"]:
        raise NextModelContractError("selection identity drift")
    if protocol.get("inventory", {}).get("records") != 85 or protocol.get("inventory", {}).get("score_calls_per_model") != 340:
        raise NextModelContractError("comparative inventory drift")
    if protocol.get("model_execution", {}).get("network_access") is not False or protocol.get("model_execution", {}).get("generation") is not False:
        raise NextModelContractError("offline/no-generation boundary drift")
    if protocol.get("model_execution", {}).get("sealed_target_reads") != "exactly_one_at_analysis_boundary":
        raise NextModelContractError("sealed target boundary drift")
    bound = _candidate(auth, model_id)
    if auth.get("status") not in {"approval_requested", "authorized"}:
        raise NextModelContractError("authorization state is invalid")
    if bound.get("revision") != meta["revision"]:
        raise NextModelContractError("authorization revision drift")
    permissions = bound.get("permissions")
    if material_execution:
        if auth.get("status") != "authorized" or auth.get("operator_approval", {}).get("granted") is not True:
            raise NextModelContractError("exact operator authorization is absent")
        if not isinstance(permissions, Mapping) or any(permissions.get(name) is not True for name in ("download", "integrity_receipt", "model_load", "feasibility", "sealed_execution")):
            raise NextModelContractError("authorization permissions are incomplete")
    if material_execution:
        receipt_path = repo / meta["receipt"]
        receipt = _json(receipt_path)
        if receipt.get("status") != "integrity_verified" or receipt.get("model_loaded") is not False or receipt.get("sealed_targets_accessed") is not False:
            raise NextModelContractError("integrity receipt is not pre-execution verified")
        if receipt.get("model_id") != model_id or receipt.get("revision") != meta["revision"]:
            raise NextModelContractError("integrity receipt identity drift")
        root_name = receipt.get("runtime_root")
        if not isinstance(root_name, str) or not root_name.startswith("artifacts/models/"):
            raise NextModelContractError("integrity receipt runtime root is unsafe")
        for item in receipt.get("runtime_files", []):
            if not isinstance(item, Mapping):
                raise NextModelContractError("integrity receipt file entry is invalid")
            path = repo / root_name / str(item.get("path", ""))
            if not path.is_file() or path.is_symlink() or _sha(path) != item.get("sha256"):
                raise NextModelContractError(f"integrity receipt hash mismatch: {item.get('path')}")
    return {
        "artifact_class": "exp001-next-model-contract-audit",
        "status": "pass",
        "model_id": model_id,
        "revision": meta["revision"],
        "material_execution": material_execution,
        "model_accessed": False,
        "sealed_targets_accessed": False,
    }


__all__ = ["NEXT_MODELS", "NextModelContractError", "validate_next_model_contract"]
