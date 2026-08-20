"""No-model EXP-002 contract and response-surface diagnostics."""
from __future__ import annotations

from collections import Counter
import math
from collections.abc import Mapping, Sequence
from typing import Any


class Exp002ContractError(ValueError):
    """Raised when the frozen no-model EXP-002 boundary is violated."""


LABELS = ("A", "B", "C", "D")
EXPECTED_MODELS = {
    "EleutherAI/pythia-70m-deduped": "e93a9faa9c77e5d09219f6c868bfc7a1bd65593c",
    "HuggingFaceTB/SmolLM2-360M": "f8027fd0eaeea54caa13c31d31b9fdc459c38b49",
    "Qwen/Qwen3-0.6B-Base": "da87bfb608c14b7cf20ba1ce41287e8de496c0cd",
    "openai-community/gpt2": "607a30d783dfa663caf39e06633721c8d4cfcd7e",
    "HuggingFaceTB/SmolLM2-135M": "93efa2f097d58c2a74874c7e644dbc9b0cee75a2",
    "EleutherAI/gpt-neo-125m": "21def0189f5705e2521767faed922f1f15e7d7db",
    "Qwen/Qwen2.5-0.5B": "060db6499f32faf8b98477b0a26969ef7d8b9987",
}


def validate_no_model_protocol(protocol: Mapping[str, Any]) -> None:
    """Validate the safety boundary without importing ML libraries."""
    if protocol.get("artifact_class") != "exp002-qwen3-followup-protocol":
        raise Exp002ContractError("unexpected EXP-002 artifact class")
    if protocol.get("status") not in {"draft", "frozen_no_model", "approval_requested"}:
        raise Exp002ContractError("protocol is not a no-model state")
    if protocol.get("scientific_status") != "exploratory" or protocol.get("claim_ids") != []:
        raise Exp002ContractError("scientific envelope drift")
    boundary = protocol.get("approval_boundary")
    required_false = ("model_load", "generation", "sealed_target_read", "network", "ccp_material_run", "new_download")
    if not isinstance(boundary, Mapping) or any(boundary.get(field) is not False for field in required_false):
        raise Exp002ContractError("no-model approval boundary is not closed")
    models = protocol.get("models")
    if not isinstance(models, Sequence) or len(models) != len(EXPECTED_MODELS):
        raise Exp002ContractError("exact seven-model registry is required")
    observed = {entry.get("model_id"): entry.get("revision") for entry in models if isinstance(entry, Mapping)}
    if observed != EXPECTED_MODELS:
        raise Exp002ContractError("model identity or revision drift")
    stages = protocol.get("stages")
    if not isinstance(stages, Sequence) or {stage.get("stage_id") for stage in stages if isinstance(stage, Mapping)} != {"EXP-002A", "EXP-002B", "EXP-002C", "EXP-002D"}:
        raise Exp002ContractError("stage inventory drift")
    if any(stage.get("model_access") is not False or stage.get("target_access") is not False for stage in stages):
        raise Exp002ContractError("stage authorizes model or target access")


def summarize_label_surface(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize top-label frequencies from a public response index only."""
    counts: Counter[str] = Counter()
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("scores"), Mapping):
            raise Exp002ContractError("response row lacks score mapping")
        scores = row["scores"]
        if set(scores) != set(LABELS) or any(not isinstance(scores[label], (int, float)) or isinstance(scores[label], bool) or not math.isfinite(float(scores[label])) for label in LABELS):
            raise Exp002ContractError("response score surface is malformed")
        top = max(LABELS, key=lambda label: float(scores[label]))
        counts[top] += 1
    total = sum(counts.values())
    probabilities = [counts[label] / total for label in LABELS] if total else []
    entropy = -sum(value * math.log(value, 2) for value in probabilities if value > 0)
    return {"record_count": total, "top_label_counts": {label: counts[label] for label in LABELS}, "top_label_entropy_bits": entropy}


def validate_tokenizer_observation(observation: Mapping[str, Any]) -> None:
    """Validate one audit observation without reading model weights."""
    required = ("model_id", "revision", "tokenizer_files_sha256", "label_token_ids", "continuation_token_counts", "prefix_boundary_ok", "special_tokens", "runtime_versions")
    if not isinstance(observation, Mapping) or any(field not in observation for field in required):
        raise Exp002ContractError("tokenizer observation is incomplete")
    model_id = observation.get("model_id")
    if EXPECTED_MODELS.get(model_id) != observation.get("revision"):
        raise Exp002ContractError("tokenizer observation identity drift")
    label_ids = observation.get("label_token_ids")
    if not isinstance(label_ids, Mapping) or set(label_ids) != set(LABELS):
        raise Exp002ContractError("label token IDs must cover A/B/C/D")
    counts = observation.get("continuation_token_counts")
    if not isinstance(counts, Mapping) or set(counts) != set(LABELS) or any(not isinstance(counts[label], int) or counts[label] < 1 for label in LABELS):
        raise Exp002ContractError("continuation token counts are malformed")
    if observation.get("prefix_boundary_ok") is not True:
        raise Exp002ContractError("tokenizer prefix boundary failed")


__all__ = ["EXPECTED_MODELS", "Exp002ContractError", "summarize_label_surface", "validate_no_model_protocol", "validate_tokenizer_observation"]
