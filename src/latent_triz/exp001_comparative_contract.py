"""No-download validation for the EXP-001 comparative dossier.

This module validates the frozen selection/protocol and source-bound fixture
inventory without importing torch/transformers, opening sealed targets, or
touching model files. Material execution belongs to a later approval-gated
runner.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class ComparativeContractError(ValueError):
    """Raised when the target-free comparative contract is not exact."""


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "experiments/exp001-comparative-reference/model-registry.json"
PROTOCOL = ROOT / "experiments/exp001-comparative-reference/protocol.json"
ANALYSIS_PLAN = ROOT / "experiments/exp001-comparative-reference/analysis-plan.json"
ACQUISITION = ROOT / "experiments/exp001-comparative-reference/qwen-acquisition-dossier.json"
AUTHORIZATION = ROOT / "experiments/exp001-comparative-reference/execution-authorization.json"

EXPECTED_MODELS = {
    "EleutherAI/pythia-70m-deduped": {
        "role": "first_model_retest",
        "revision": "e93a9faa9c77e5d09219f6c868bfc7a1bd65593c",
        "model_type": "gpt_neox",
        "architecture": "GPTNeoXForCausalLM",
    },
    "HuggingFaceTB/SmolLM2-360M": {
        "role": "prior_reference_model",
        "revision": "f8027fd0eaeea54caa13c31d31b9fdc459c38b49",
        "model_type": "llama",
        "architecture": "LlamaForCausalLM",
    },
    "Qwen/Qwen3-0.6B-Base": {
        "role": "third_model",
        "revision": "da87bfb608c14b7cf20ba1ce41287e8de496c0cd",
        "model_type": "qwen3",
        "architecture": "Qwen3ForCausalLM",
    },
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ComparativeContractError(f"cannot read {path}") from exc
    if not isinstance(value, dict):
        raise ComparativeContractError(f"{path} must contain an object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise ComparativeContractError(f"cannot hash {path}") from exc
    return digest.hexdigest()


def validate_comparative_contract(root: str | Path = ROOT) -> dict[str, Any]:
    """Validate the target-free dossier and return a bounded audit summary."""
    repo = Path(root).resolve()
    registry = _read_json(repo / REGISTRY.relative_to(ROOT))
    protocol = _read_json(repo / PROTOCOL.relative_to(ROOT))
    analysis = _read_json(repo / ANALYSIS_PLAN.relative_to(ROOT))
    acquisition = _read_json(repo / ACQUISITION.relative_to(ROOT))
    authorization = _read_json(repo / AUTHORIZATION.relative_to(ROOT))
    if registry.get("registry_status") not in {"proposal_frozen_no_download", "frozen", "approval_requested", "authorized"}:
        raise ComparativeContractError("registry is not a frozen or authorized proposal")
    if registry.get("selection_observed_prior_result") is not False:
        raise ComparativeContractError("selection must not consult prior results")
    if registry.get("substitution_policy") != "no_model_substitution_after_freeze":
        raise ComparativeContractError("model substitution policy drift")
    models = registry.get("models")
    if not isinstance(models, list) or len(models) != 3:
        raise ComparativeContractError("exactly three model roles are required")
    seen: set[str] = set()
    for model in models:
        if not isinstance(model, dict):
            raise ComparativeContractError("model entry must be an object")
        model_id = model.get("model_id")
        expected = EXPECTED_MODELS.get(model_id)
        if expected is None or model_id in seen:
            raise ComparativeContractError("unexpected or duplicate model identity")
        seen.add(model_id)
        for key, value in expected.items():
            if model.get(key) != value:
                raise ComparativeContractError(f"{model_id} {key} drift")
        root_name = model.get("local_root")
        if not isinstance(root_name, str) or not root_name.startswith("artifacts/models/") or ".." in Path(root_name).parts:
            raise ComparativeContractError(f"unsafe local root for {model_id}")
        if model_id == "Qwen/Qwen3-0.6B-Base" and model.get("acquisition_status") not in {"not_acquired", "integrity_verified"}:
            raise ComparativeContractError("Qwen acquisition state is invalid")
    if protocol.get("protocol_status") not in {"frozen_no_download_approval_requested", "authorized"}:
        raise ComparativeContractError("protocol is not frozen or authorized")
    if protocol.get("source_registry", {}).get("principle_count") != 40:
        raise ComparativeContractError("principle count drift")
    if protocol.get("inventory", {}).get("records") != 85 or protocol.get("inventory", {}).get("score_calls_per_model") != 340:
        raise ComparativeContractError("comparative inventory drift")
    execution = protocol.get("model_execution", {})
    if execution.get("network_access") is not False or execution.get("generation") is not False:
        raise ComparativeContractError("offline/no-generation boundary drift")
    if execution.get("sealed_target_reads") != "exactly_one_at_analysis_boundary":
        raise ComparativeContractError("sealed-target read boundary drift")
    if protocol.get("comparison", {}).get("pool_scores_across_models") is not False:
        raise ComparativeContractError("cross-model pooling is forbidden")
    if analysis.get("primary", {}).get("unit_count") != 24 or analysis.get("primary", {}).get("domain_count") != 6:
        raise ComparativeContractError("analysis primary cardinality drift")
    if acquisition.get("model_id") != "Qwen/Qwen3-0.6B-Base" or acquisition.get("revision") != EXPECTED_MODELS["Qwen/Qwen3-0.6B-Base"]["revision"]:
        raise ComparativeContractError("Qwen acquisition identity drift")
    if acquisition.get("download_authorized") is not True or acquisition.get("model_load_authorized") is not False:
        raise ComparativeContractError("Qwen acquisition/load authorization boundary drift")
    if acquisition.get("sealed_execution_authorized") is not False:
        raise ComparativeContractError("sealed execution authorization must remain absent")
    if authorization.get("status") not in {"approval_requested", "authorized"}:
        raise ComparativeContractError("comparative execution authorization state is invalid")
    if authorization.get("status") == "authorized" and authorization.get("operator_approval", {}).get("granted") is not True:
        raise ComparativeContractError("authorized execution lacks operator approval")
    permissions = authorization.get("permissions_requested", {})
    for field in ("download_qwen_runtime_files_only", "load_existing_pythia_once", "load_existing_smollm2_once", "load_qwen_once_after_integrity"):
        expected = authorization.get("status") == "authorized"
        if permissions.get(field) is not expected:
            raise ComparativeContractError(f"material permission drift: {field}")
    return {
        "artifact_class": "exp001-comparative-contract-audit",
        "status": "pass",
        "model_count": len(models),
        "records_per_model": protocol["inventory"]["records"],
        "score_calls_per_model": protocol["inventory"]["score_calls_per_model"],
        "model_accessed": False,
        "sealed_targets_accessed": False,
        "network_accessed": False,
        "hashes_checked": [],
    }


__all__ = ["ComparativeContractError", "validate_comparative_contract"]
