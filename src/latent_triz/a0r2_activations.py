"""Deterministic A0-R2 activation extraction for the frozen SmolLM2 study."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .a0_activation_sites import build_view_texts, select_token_indices
from .a0r2_adapter import SmolLM2TransformersAdapter
from .validator import validate


EPISTEMIC = {
    "empirical": True,
    "scientific_status": "exploratory",
    "evidence_eligible": False,
    "expert_validated": False,
    "claim_ids": [],
}


SENTINEL_TEXT = "Analysis anchor:"
REQUIRED_TUPLE_INDICES = (0, 11, 21, 32)
VIEW_ORDER = (
    "problem_only",
    "transformation_only",
    "problem_plus_transformation",
    "problem_plus_solution",
)
VIEW_SITE_POLICY = {
    "problem_only": ("sentinel",),
    "transformation_only": ("sentinel", "final_transformation_token", "mean_transformation_span"),
    "problem_plus_transformation": ("sentinel", "final_transformation_token", "mean_transformation_span"),
    "problem_plus_solution": ("sentinel", "final_transformation_token", "mean_transformation_span"),
}
VIEW_ANCHOR_SOURCE = {
    "problem_only": "transformation",
    "transformation_only": "transformation",
    "problem_plus_transformation": "transformation",
    "problem_plus_solution": "solution",
}
EXPECTED_CASE_COUNT = 48
EXPECTED_FORWARD_PASSES = 192
EXPECTED_VECTOR_COUNT = 1920
EXPECTED_HIDDEN_STATES = 33
EXPECTED_HIDDEN_SIZE = 960
REQUIRED_INDEX_FIELDS = frozenset(
    {
        "record_id",
        "case_id",
        "problem_family_id",
        "domain",
        "split",
        "view",
        "anchor_source",
        "token_site",
        "tuple_index",
        "hidden_states_count",
        "hidden_size",
        "dtype",
        "token_count",
        "prompt_token_count",
        "prompt_sha256",
        "vector_sha256",
    }
)

R1_CORPUS_MANIFEST_REL = Path("data/a0r1/manifest.json")
R1_CASES_REL = Path("data/a0r1/cases.jsonl")
R1_INDEPENDENCE_REL = Path("results/a0r1/preoutput/independence.json")
R1_FREEZE_MANIFEST_REL = Path("results/a0r1/freeze/freeze-manifest.json")
R1_PROTOCOL_FROZEN_REL = Path("results/a0r1/freeze/protocol-frozen.json")
R1_SHORTCUTS_REL = Path("results/a0r1/preoutput/shortcuts.json")
R2_INTEGRITY_RECEIPT_REL = Path("results/a0r2/preexecution/smollm2-360m-f8027fd0/integrity-receipt.json")
R2_FEASIBILITY_RECEIPT_REL = Path("results/a0r2/preexecution/smollm2-360m-f8027fd0/feasibility-receipt.json")


class A0R2ActivationError(RuntimeError):
    """Raised when activation extraction cannot proceed under contract."""


@dataclass(frozen=True)
class A0R2ActivationArtifacts:
    dense_path: Path
    index_path: Path
    summary_path: Path
    receipt_path: Path


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_sha256(payload: Any) -> str:
    return _sha256_bytes(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R2ActivationError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise A0R2ActivationError(f"{label} must be a JSON object")
    return value


def _read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R2ActivationError(f"cannot read {label}: {path}") from exc
    if any(not isinstance(row, dict) for row in rows):
        raise A0R2ActivationError(f"{label} contains non-object records")
    return rows


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise A0R2ActivationError(message)


def _normalize_tensor(value: Any) -> list[list[float]]:
    if hasattr(value, "detach"):
        try:
            value = value.detach().cpu().tolist()
        except Exception as exc:  # pragma: no cover - defensive for tensor backends
            raise A0R2ActivationError("hidden-state tensor not list-convertible") from exc
    if not isinstance(value, (list, tuple)) or not value:
        raise A0R2ActivationError("hidden-state layer must be a non-empty sequence")
    if value and not isinstance(value[0], (list, tuple)):
        value = [value]
    rows: list[list[float]] = []
    for row in value:
        if not isinstance(row, (list, tuple)) or not row:
            raise A0R2ActivationError("hidden-state layer contains invalid rows")
        rows.append([float(item) for item in row])
    return rows


def _mean_vectors(vectors: list[list[float]], expected_dim: int) -> list[float]:
    _require(vectors, "no vectors provided")
    _require(len(vectors[0]) == expected_dim, "vector dimension drift")
    accumulator = [0.0] * expected_dim
    for vector in vectors:
        _require(len(vector) == expected_dim, "vector dimension drift")
        for value in vector:
            _require(math.isfinite(float(value)), "non-finite activation detected")
        for index, value in enumerate(vector):
            accumulator[index] += float(value)
    return [value / len(vectors) for value in accumulator]


def _validate_representation_index_rows(
    index_rows: list[dict[str, Any]],
    dense_rows: dict[str, list[float]],
    *,
    expected_records: int = EXPECTED_VECTOR_COUNT,
) -> None:
    """Fail closed on an incomplete activation index before it reaches analysis.

    This is deliberately independent of the statistical analyzer: an export
    contract defect must stop while targets remain unopened. JSON Schema is
    published for external tooling; this local check additionally binds each
    row to the dense vector it indexes.
    """

    _require(len(index_rows) == expected_records, "representation index record-count drift")
    _require(len(dense_rows) == expected_records, "dense representation record-count drift")
    seen: set[str] = set()
    for row in index_rows:
        _require(isinstance(row, dict), "representation index row must be an object")
        _require(REQUIRED_INDEX_FIELDS.issubset(row), "representation index missing required metadata")
        record_id = row.get("record_id")
        _require(isinstance(record_id, str) and record_id and record_id not in seen, "representation index record ID drift")
        seen.add(record_id)
        _require(row.get("dtype") == "float32", "representation index dtype drift")
        _require(row.get("hidden_states_count") == EXPECTED_HIDDEN_STATES, "representation index hidden-state count drift")
        _require(row.get("hidden_size") == EXPECTED_HIDDEN_SIZE, "representation index hidden-size drift")
        _require(row.get("tuple_index") in REQUIRED_TUPLE_INDICES, "representation index tuple-index drift")
        _require(isinstance(row.get("token_count"), int) and row["token_count"] > 0, "representation index token-count drift")
        _require(
            isinstance(row.get("prompt_token_count"), int) and row["prompt_token_count"] >= row["token_count"],
            "representation index prompt-token count drift",
        )
        vector = dense_rows.get(record_id)
        _require(isinstance(vector, list) and len(vector) == EXPECTED_HIDDEN_SIZE, "representation index dense vector missing")
        _require(row.get("vector_sha256") == _stable_sha256(vector), "representation index vector hash drift")
    _require(seen == set(dense_rows), "representation index and dense record IDs differ")


def _git_head_sha(root: Path) -> str:
    git_path = root / ".git"
    try:
        if git_path.is_file():
            git_text = git_path.read_text(encoding="utf-8").strip()
            if git_text.startswith("gitdir:"):
                git_dir = (root / git_text.split(":", 1)[1].strip()).resolve()
            else:
                return git_text if len(git_text) == 40 and all(ch in "0123456789abcdef" for ch in git_text) else "0" * 40
        else:
            git_dir = git_path
        head_path = git_dir / "HEAD"
        if head_path.is_file():
            head = head_path.read_text(encoding="utf-8").strip()
            if head.startswith("ref:"):
                ref = head.split(" ", 1)[1]
                ref_path = git_dir / ref
                if ref_path.is_file():
                    value = ref_path.read_text(encoding="utf-8").strip()
                    if len(value) == 40 and all(ch in "0123456789abcdef" for ch in value):
                        return value
            elif len(head) == 40 and all(ch in "0123456789abcdef" for ch in head):
                return head
    except OSError:
        pass

    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception:
        return "0" * 40
    value = completed.stdout.strip()
    return value if len(value) == 40 and all(ch in "0123456789abcdef" for ch in value) else "0" * 40


def _validate_protocol(protocol: dict[str, Any], root: Path) -> None:
    schema = _read_json(root / "schemas/a0r2-study-protocol.schema.json", "study protocol schema")
    issues = validate(protocol, schema)
    if issues:
        raise A0R2ActivationError("protocol validation failed: " + "; ".join(str(item) for item in issues))

    if protocol.get("artifact_class") != "a0r2-study-protocol":
        raise A0R2ActivationError("protocol artifact_class drift")
    if protocol.get("protocol_status") != "frozen":
        raise A0R2ActivationError("protocol must be frozen")
    if protocol.get("no_human_review") is not True:
        raise A0R2ActivationError("no_human_review must be true")
    if protocol.get("approval_required") is not True:
        raise A0R2ActivationError("approval_required must be true")

    primary = protocol.get("primary_endpoint")
    sensitivity = protocol.get("sensitivity_endpoints")
    thresholds = protocol.get("thresholds")
    runtime = protocol.get("runtime")
    model = protocol.get("model")
    tokenizer = protocol.get("tokenizer")
    outputs = protocol.get("outcomes", {})
    seals = protocol.get("sealed_execution")
    publication = protocol.get("publication")

    _require(isinstance(primary, dict), "primary_endpoint missing")
    _require(isinstance(sensitivity, dict), "sensitivity_endpoints missing")
    _require(isinstance(thresholds, dict), "thresholds missing")
    _require(isinstance(runtime, dict), "runtime missing")
    _require(isinstance(model, dict), "model missing")
    _require(isinstance(tokenizer, dict), "tokenizer missing")
    _require(isinstance(outputs, dict), "outcomes missing")
    _require(isinstance(seals, dict), "sealed_execution missing")
    _require(isinstance(publication, dict), "publication missing")

    _require(int(primary.get("tuple_index", -1)) == 32, "primary tuple_index drift")
    _require(primary.get("semantics") == "final_transformer_block_output", "primary semantics drift")
    _require(primary.get("token_site") == "mean_transformation_span", "primary token site drift")
    _require(primary.get("primary_view") == "problem_plus_transformation", "primary view drift")
    _require(primary.get("surface_baseline_view") == "problem_only", "baseline view drift")
    _require(primary.get("surface_baseline_token_site") == "sentinel", "baseline token site drift")
    _require(int(primary.get("multiplicity", 0)) == 1, "primary multiplicity drift")
    _require(bool(primary.get("is_max_statistic_selection")) is False, "primary max-statistic drift")

    _require(tuple(sensitivity.get("descriptive_tuple_indices", ())) == REQUIRED_TUPLE_INDICES, "tuple indices drift")
    _require(tuple(sensitivity.get("token_sites", ())) == ("sentinel", "final_transformation_token", "mean_transformation_span"), "token-site drift")
    _require(tuple(sensitivity.get("views", ())) == VIEW_ORDER, "view drift")
    _require(bool(sensitivity.get("may_replace_primary")) is False, "sensitivity may not replace primary")
    _require(sensitivity.get("interpretation") == "descriptive_only", "sensitivity interpretation drift")

    _require(int(thresholds.get("critical_successes", -1)) == 17, "critical_successes drift")
    _require(float(thresholds.get("primary_permutation_p_at_most", 1.0)) == 0.05, "primary permutation threshold drift")
    _require(float(thresholds.get("macro_f1_margin_at_least", 0.0)) == 0.1, "macro_f1 margin drift")
    _require(int(thresholds.get("family_successes_at_least", -1)) == 17, "family success threshold drift")
    _require(int(thresholds.get("domain_direction_successes_minimum", -1)) == 4, "domain direction threshold drift")

    _require(bool(runtime.get("network_access")) is False, "network access must be disabled")
    _require(bool(runtime.get("local_files_only")) is True, "local_files_only must be true")
    _require(runtime.get("device") == "cpu", "device must be cpu")
    _require(runtime.get("torch_dtype") == "float32", "torch dtype must be float32")
    _require(bool(runtime.get("generation")) is False, "generation must be false")

    _require(model.get("id") == "HuggingFaceTB/SmolLM2-360M", "model id drift")
    _require(model.get("revision") == "f8027fd0eaeea54caa13c31d31b9fdc459c38b49", "model revision drift")
    _require(model.get("license_id") == "Apache-2.0", "model license drift")
    _require(model.get("model_type") == "llama", "model type drift")
    _require(model.get("architecture") == "LlamaForCausalLM", "model architecture drift")
    _require(int(model.get("num_hidden_layers", -1)) == 32, "model layer count drift")
    _require(int(model.get("hidden_size", -1)) == 960, "model hidden size drift")
    _require(model.get("local_locator") == "artifacts/models/smollm2-360m-f8027fd0", "model locator drift")

    _require(tokenizer.get("id") == "HuggingFaceTB/SmolLM2-360M", "tokenizer id drift")
    _require(tokenizer.get("revision") == "f8027fd0eaeea54caa13c31d31b9fdc459c38b49", "tokenizer revision drift")
    _require(bool(tokenizer.get("fast_offsets_required")) is True, "fast offsets must be required")

    _require(tuple(outputs.get("terminal", ())) == ("positive", "null", "failed", "non_interpretable", "incompatible"), "outcome vocabulary drift")
    rules = outputs.get("rules", {})
    _require(isinstance(rules, dict), "outcome rules missing")
    _require("all gates pass" in str(rules.get("positive", "")), "positive rule drift")
    _require("primary_permutation_p <= 0.05" in str(rules.get("positive", "")), "positive rule drift")
    _require("all gates pass" in str(rules.get("null", "")), "null rule drift")
    _require("integrity, identity, execution, data, or receipt gate fails" in str(rules.get("failed", "")), "failed rule drift")
    _require("predictive aggregate macro_f1 >= 0.65" in str(rules.get("non_interpretable", "")), "non-interpretable rule drift")
    _require("resource envelope violated" in str(rules.get("incompatible", "")), "incompatible rule drift")

    _require(int(seals.get("max_runs", -1)) == 1, "sealed max_runs drift")
    _require(seals.get("sealed_targets_access") == "approval_required", "sealed target access drift")
    _require(bool(seals.get("activation_may_read_target_content")) is False, "activation may not read target content")
    _require(int(seals.get("analysis_target_reads", -1)) == 1, "analysis target read budget drift")
    _require(bool(seals.get("generation_allowed")) is False, "generation must be disabled")
    _require(seals.get("retry_after_model_or_target_access") == "new_explicit_approval_required", "retry rule drift")
    _require(seals.get("stopping_rule") == "stop_after_first_terminal_attempt", "stopping rule drift")

    _require(bool(publication.get("publish_every_terminal_outcome")) is True, "publication fanout drift")
    _require(bool(publication.get("sensitivity_may_rescue_primary")) is False, "sensitivity rescue drift")
    _require(bool(publication.get("model_substitution_after_output")) is False, "model substitution drift")
    _require(bool(publication.get("claim_promotion")) is False, "claim promotion drift")


def _case_id_list(cases: list[dict[str, Any]]) -> list[str]:
    return [str(case["case_id"]) for case in cases]


def _selected_cases(root: Path, protocol: dict[str, Any]) -> list[dict[str, Any]]:
    corpus_manifest_path = root / R1_CORPUS_MANIFEST_REL
    cases_path = root / R1_CASES_REL
    freeze_manifest_path = root / R1_FREEZE_MANIFEST_REL
    protocol_frozen_path = root / R1_PROTOCOL_FROZEN_REL
    shortcuts_path = root / R1_SHORTCUTS_REL
    independence_path = root / R1_INDEPENDENCE_REL
    integrity_path = root / R2_INTEGRITY_RECEIPT_REL
    feasibility_path = root / R2_FEASIBILITY_RECEIPT_REL

    corpus_manifest = _read_json(corpus_manifest_path, "corpus manifest")
    cases = _read_jsonl(cases_path, "corpus cases")
    freeze_manifest = _read_json(freeze_manifest_path, "freeze manifest")
    protocol_frozen = _read_json(protocol_frozen_path, "frozen protocol")
    shortcuts = _read_json(shortcuts_path, "shortcut audit")
    independence = _read_json(independence_path, "independence audit")
    integrity_receipt = _read_json(integrity_path, "integrity receipt")
    feasibility_receipt = _read_json(feasibility_path, "feasibility receipt")

    _require(_sha256_file(corpus_manifest_path) == protocol["inputs"]["corpus_manifest_sha256"], "corpus manifest hash mismatch")
    _require(_sha256_file(cases_path) == protocol["inputs"]["cases_sha256"], "cases hash mismatch")
    _require(_sha256_file(freeze_manifest_path) == protocol["inputs"]["r1_freeze_manifest_sha256"], "freeze manifest hash mismatch")
    _require(_sha256_file(protocol_frozen_path) == protocol["inputs"]["r1_protocol_sha256"], "frozen protocol hash mismatch")
    _require(_sha256_file(shortcuts_path) == protocol["inputs"]["shortcuts_sha256"], "shortcut hash mismatch")
    _require(_sha256_file(integrity_path) == protocol["model"]["integrity_receipt_sha256"], "integrity receipt hash mismatch")
    _require(_sha256_file(feasibility_path) == protocol["model"]["feasibility_receipt_sha256"], "feasibility receipt hash mismatch")

    _require(corpus_manifest.get("files", {}).get("cases_jsonl", {}).get("sha256") == protocol["inputs"]["cases_sha256"], "corpus cases hash mismatch")
    _require(corpus_manifest.get("files", {}).get("sealed_targets_jsonl", {}).get("sha256") == protocol["inputs"]["sealed_targets_sha256"], "sealed targets hash mismatch")
    _require(
        corpus_manifest.get("protocol_hash") == freeze_manifest.get("planned_protocol_snapshot_hash"),
        "benchmark protocol hash mismatch",
    )
    _require(freeze_manifest.get("protocol_id") == protocol["r1_benchmark_reference"]["protocol_id"], "freeze protocol id mismatch")
    _require(freeze_manifest.get("cases_sha256") == protocol["inputs"]["cases_sha256"], "freeze cases hash mismatch")
    _require(shortcuts.get("status") == "pass", "shortcut audit must pass")
    _require(integrity_receipt.get("status") == "pass", "integrity receipt must pass")
    _require(integrity_receipt.get("access", {}).get("feasibility_tested") is False, "integrity receipt feasibility drift")
    _require(feasibility_receipt.get("status") == "compatible", "feasibility receipt must be compatible")
    _require(feasibility_receipt.get("access", {}).get("sealed_targets_accessed") == "not_accessed", "feasibility receipt target access drift")
    _require(feasibility_receipt.get("access", {}).get("model_output_accessed") == "accessed", "feasibility receipt model output drift")
    _require(protocol_frozen.get("status") == "frozen", "frozen protocol status drift")
    _require(independence.get("status") == "pass", "independence audit must pass")

    expected_ids = independence.get("partitions", {}).get("candidate_split_values", {}).get("sealed", [])
    _require(isinstance(expected_ids, list) and len(expected_ids) == EXPECTED_CASE_COUNT, "sealed candidate count drift")

    sealed_rows = [row for row in cases if str(row.get("split")) == "sealed"]
    _require(len(sealed_rows) == EXPECTED_CASE_COUNT, "sealed case count drift")
    selected_by_id = {str(row.get("case_id", "")): row for row in sealed_rows}
    _require(sorted(selected_by_id) == sorted(expected_ids), "sealed case set drift")
    return [selected_by_id[case_id] for case_id in expected_ids]


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _normalize_adapter_output(payload: Any, *, prompt: str) -> tuple[list[int], list[list[int]], list[bool], list[int], tuple[Any, ...]]:
    if not isinstance(payload, dict):
        raise A0R2ActivationError("adapter.run_prompt did not return a mapping")
    token_ids = payload.get("token_ids")
    offsets = payload.get("offsets_mapping")
    attention = payload.get("attention_mask")
    special = payload.get("special_token_flags")
    hidden_states = payload.get("hidden_states")
    if not isinstance(token_ids, list) or not isinstance(offsets, list) or not isinstance(attention, list):
        raise A0R2ActivationError("adapter output missing token metadata")
    if not isinstance(special, list) or hidden_states is None:
        raise A0R2ActivationError("adapter output missing special flags or hidden states")
    token_ids = [int(value) for value in token_ids]
    offsets = [[int(start), int(end)] for start, end in offsets]
    attention = [int(value) for value in attention]
    special_flags = [bool(value) for value in special]
    if len(token_ids) != len(offsets) or len(token_ids) != len(attention) or len(token_ids) != len(special_flags):
        raise A0R2ActivationError("adapter token metadata length mismatch")
    if not prompt:
        raise A0R2ActivationError("prompt unavailable")
    if not isinstance(hidden_states, (list, tuple)):
        raise A0R2ActivationError("adapter hidden_states missing")
    return token_ids, offsets, special_flags, attention, tuple(hidden_states)


def _layer_rows(hidden_states: tuple[Any, ...], tuple_index: int) -> list[list[float]]:
    if tuple_index >= len(hidden_states):
        raise A0R2ActivationError("tuple index out of hidden-state range")
    return _normalize_tensor(hidden_states[tuple_index])


def _dense_file_payload(*, rows: dict[str, list[float]]) -> dict[str, list[float]]:
    """Return the external dense asset keyed by the index record identifier."""

    return rows


def _summary_payload(
    *,
    protocol_id: str,
    created_at: str,
    case_ids: list[str],
    forward_passes: int,
    vector_count: int,
    dense_sha256: str,
    index_sha256: str,
    protocol_hashes: dict[str, str],
    model: dict[str, Any],
) -> dict[str, Any]:
    return {
        "artifact_class": "a0r2-activation-summary",
        **EPISTEMIC,
        "status": "pass",
        "created_at": created_at,
        "protocol_id": protocol_id,
        "case_count": len(case_ids),
        "case_ids": case_ids,
        "case_ids_sha256": _stable_sha256(case_ids),
        "forward_passes": forward_passes,
        "vector_count": vector_count,
        "hidden_states_count": EXPECTED_HIDDEN_STATES,
        "hidden_size": EXPECTED_HIDDEN_SIZE,
        "tuple_indices": list(REQUIRED_TUPLE_INDICES),
        "views": list(VIEW_ORDER),
        "site_policy": {view: list(sites) for view, sites in VIEW_SITE_POLICY.items()},
        "runtime": {
            "device": "cpu",
            "torch_dtype": "float32",
            "network_access": False,
            "local_files_only": True,
            "generation": False,
            "fast_offsets_required": True,
        },
        "model": model,
        "input_hashes": protocol_hashes,
        "bundle_hashes": {
            "dense_sha256": dense_sha256,
            "index_sha256": index_sha256,
        },
        "access": {
            "model_loaded": True,
            "model_output_accessed": True,
            "model_output_retained": True,
            "sealed_targets_accessed": False,
        },
    }


def _receipt_payload(
    *,
    protocol: dict[str, Any],
    created_at: str,
    summary_sha256: str,
    index_sha256: str,
    dense_sha256: str,
    dense_locator: str,
    repo_root: Path,
    model_root: Path,
    summary_name: str,
    index_name: str,
    dense_name: str,
    case_count: int,
    forward_passes: int,
    vector_count: int,
) -> dict[str, Any]:
    return {
        "artifact_class": "a0r2-activation-receipt",
        "status": "pass",
        **EPISTEMIC,
        "created_at": created_at,
        "protocol_id": protocol["protocol_id"],
        "model": {
            key: protocol["model"][key]
            for key in (
                "id",
                "revision",
                "license_id",
                "model_type",
                "architecture",
                "num_hidden_layers",
                "hidden_size",
                "local_locator",
            )
        },
        "runtime": {
            "device": protocol["runtime"]["device"],
            "torch_dtype": protocol["runtime"]["torch_dtype"],
            "network_access": protocol["runtime"]["network_access"],
            "local_files_only": protocol["runtime"]["local_files_only"],
            "generation": protocol["runtime"]["generation"],
            "fast_offsets_required": protocol["tokenizer"]["fast_offsets_required"],
        },
        "activation": {
            "tuple_index": protocol["primary_endpoint"]["tuple_index"],
            "primary_semantics": protocol["primary_endpoint"]["semantics"],
            "token_site": protocol["primary_endpoint"]["token_site"],
            "primary_view": protocol["primary_endpoint"]["primary_view"],
            "surface_baseline_view": protocol["primary_endpoint"]["surface_baseline_view"],
            "surface_baseline_token_site": protocol["primary_endpoint"]["surface_baseline_token_site"],
            "hidden_states_count": EXPECTED_HIDDEN_STATES,
            "hidden_size": EXPECTED_HIDDEN_SIZE,
            "output_content_retained": True,
        },
        "access": {
            "model_loaded": True,
            "model_output_accessed": True,
            "sealed_targets_accessed": False,
            "claim_promotion": False,
        },
        "input_hashes": {
            "protocol_sha256": _sha256_file(repo_root / "experiments/a0r2-independent-model/study-protocol.json"),
            "r1_protocol_sha256": protocol["inputs"]["r1_protocol_sha256"],
            "r1_freeze_manifest_sha256": protocol["inputs"]["r1_freeze_manifest_sha256"],
            "corpus_manifest_sha256": protocol["inputs"]["corpus_manifest_sha256"],
            "cases_sha256": protocol["inputs"]["cases_sha256"],
            "sealed_targets_sha256": protocol["inputs"]["sealed_targets_sha256"],
            "shortcuts_sha256": protocol["inputs"]["shortcuts_sha256"],
            "integrity_receipt_sha256": protocol["model"]["integrity_receipt_sha256"],
            "feasibility_receipt_sha256": protocol["model"]["feasibility_receipt_sha256"],
        },
        "output_bundle": {
            "reports": [summary_name, index_name, dense_name, "activation-receipt.json"],
            "dense_locator": dense_locator,
            "artifact_hashes": {
                "summary_sha256": summary_sha256,
                "index_sha256": index_sha256,
                "dense_sha256": dense_sha256,
            },
            "records": vector_count,
            "hidden_size": EXPECTED_HIDDEN_SIZE,
            "exact_head": _git_head_sha(repo_root),
        },
    }


def run_a0r2_activations(
    *,
    protocol_path: str | Path,
    model_root: str | Path,
    output_dir: str | Path,
    created_at: str,
    adapter_factory: Any = SmolLM2TransformersAdapter,
) -> A0R2ActivationArtifacts:
    root = Path(__file__).resolve().parents[2]
    protocol_path = Path(protocol_path).resolve()
    output_root = Path(output_dir).resolve()
    _require(not output_root.exists(), f"refusing to overwrite output directory: {output_root}")

    try:
        timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise A0R2ActivationError("created_at must be ISO-8601 with timezone") from exc
    _require(timestamp.tzinfo is not None, "created_at must include timezone")
    created_at = timestamp.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    protocol = _read_json(protocol_path, "protocol")
    _validate_protocol(protocol, root)

    selected_cases = _selected_cases(root, protocol)
    model_root = Path(model_root)

    adapter = adapter_factory(
        model_root=model_root,
        local_files_only=True,
        device="cpu",
        torch_dtype="float32",
    )
    tokenizer = getattr(adapter, "tokenizer", None)
    _require(tokenizer is not None, "adapter has no tokenizer")
    _require(bool(getattr(tokenizer, "is_fast", False)) is True, "fast tokenizer required")

    protocol_id = str(protocol["protocol_id"])
    protocol_hashes = {
        "r1_protocol_sha256": protocol["inputs"]["r1_protocol_sha256"],
        "r1_freeze_manifest_sha256": protocol["inputs"]["r1_freeze_manifest_sha256"],
        "corpus_manifest_sha256": protocol["inputs"]["corpus_manifest_sha256"],
        "cases_sha256": protocol["inputs"]["cases_sha256"],
        "sealed_targets_sha256": protocol["inputs"]["sealed_targets_sha256"],
        "shortcuts_sha256": protocol["inputs"]["shortcuts_sha256"],
        "integrity_receipt_sha256": protocol["model"]["integrity_receipt_sha256"],
        "feasibility_receipt_sha256": protocol["model"]["feasibility_receipt_sha256"],
    }

    dense_rows: dict[str, list[float]] = {}
    index_rows: list[dict[str, Any]] = []
    forward_passes = 0

    for case in selected_cases:
        views = build_view_texts(case, sentinel_text=SENTINEL_TEXT)
        for view_name in VIEW_ORDER:
            prompt = views[view_name]
            forward_passes += 1
            adapter_output = adapter.run_prompt(prompt=prompt, instrumented=True)
            token_ids, offsets, special_flags, attention, hidden_states = _normalize_adapter_output(adapter_output, prompt=prompt)
            _require(len(hidden_states) == EXPECTED_HIDDEN_STATES, "hidden_states count mismatch")

            expected_sites = VIEW_SITE_POLICY[view_name]
            anchor_source = VIEW_ANCHOR_SOURCE[view_name]
            anchor_text = str(case[anchor_source])
            token_map = select_token_indices(
                view_text=prompt,
                transformation_text=anchor_text,
                sentinel_text=SENTINEL_TEXT,
                offsets=offsets,
                special_flags=special_flags,
                attention_mask=attention,
            )
            _require(tuple(token_map) == expected_sites, f"site policy drift for {view_name}")

            layer_tensors = {
                tuple_index: _layer_rows(hidden_states, tuple_index)
                for tuple_index in REQUIRED_TUPLE_INDICES
            }
            for layer in layer_tensors.values():
                _require(len(layer[0]) == EXPECTED_HIDDEN_SIZE, "hidden-size mismatch")
            for site in expected_sites:
                selected_indices = token_map[site]
                _require(bool(selected_indices), f"missing token site {site}")
                for tuple_index in REQUIRED_TUPLE_INDICES:
                    layer = layer_tensors[tuple_index]
                    mean_vector = _mean_vectors([layer[index] for index in selected_indices], EXPECTED_HIDDEN_SIZE)
                    record_id = f"{case['case_id']}::{view_name}::{site}::{tuple_index}"
                    _require(record_id not in dense_rows, "duplicate dense record id")
                    dense_rows[record_id] = mean_vector
                    index_rows.append(
                        {
                            "record_id": record_id,
                            "case_id": case["case_id"],
                            "problem_family_id": case["problem_family_id"],
                            "domain": case["domain"],
                            "split": case.get("split", "sealed"),
                            "view": view_name,
                            "anchor_source": anchor_source,
                            "token_site": site,
                            "tuple_index": int(tuple_index),
                            "hidden_states_count": len(hidden_states),
                            "hidden_size": EXPECTED_HIDDEN_SIZE,
                            "dtype": "float32",
                            "token_count": len(selected_indices),
                            "prompt_token_count": len(token_ids),
                            "prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
                            "vector_sha256": _stable_sha256(mean_vector),
                        }
                    )

    _require(forward_passes == EXPECTED_FORWARD_PASSES, "forward-pass count drift")
    _require(len(index_rows) == EXPECTED_VECTOR_COUNT, "vector-count drift")
    _require(len(dense_rows) == EXPECTED_VECTOR_COUNT, "dense row-count drift")
    _validate_representation_index_rows(index_rows, dense_rows)

    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(output_root.parent)) as staging_root:
        staging = Path(staging_root) / output_root.name
        staging.mkdir(parents=True)

        dense_path = staging / "activations.json"
        index_path = staging / "representations-index.jsonl"
        summary_path = staging / "activation-summary.json"
        receipt_path = staging / "activation-receipt.json"

        dense_payload = _dense_file_payload(rows=dense_rows)
        dense_path.write_text(_canonical_json(dense_payload) + "\n", encoding="utf-8")

        index_path.write_text(
            "".join(_canonical_json(row) + "\n" for row in index_rows),
            encoding="utf-8",
        )

        dense_sha256 = _sha256_file(dense_path)
        index_sha256 = _sha256_file(index_path)

        summary_payload = _summary_payload(
            protocol_id=protocol_id,
            created_at=created_at,
            case_ids=[str(case["case_id"]) for case in selected_cases],
            forward_passes=forward_passes,
            vector_count=len(index_rows),
            dense_sha256=dense_sha256,
            index_sha256=index_sha256,
            protocol_hashes=protocol_hashes,
            model=protocol["model"],
        )
        summary_path.write_text(_canonical_json(summary_payload) + "\n", encoding="utf-8")
        summary_sha256 = _sha256_file(summary_path)

        receipt_payload = _receipt_payload(
            protocol=protocol,
            created_at=created_at,
            summary_sha256=summary_sha256,
            index_sha256=index_sha256,
            dense_sha256=dense_sha256,
            model_root=model_root,
            summary_name=summary_path.name,
            index_name=index_path.name,
            dense_name=dense_path.name,
            dense_locator=f"artifacts/a0r2/{output_root.name}/activations.json",
            repo_root=root,
            case_count=len(selected_cases),
            forward_passes=forward_passes,
            vector_count=len(index_rows),
        )
        receipt_path.write_text(_canonical_json(receipt_payload) + "\n", encoding="utf-8")

        staging.replace(output_root)

    return A0R2ActivationArtifacts(
        dense_path=output_root / "activations.json",
        index_path=output_root / "representations-index.jsonl",
        summary_path=output_root / "activation-summary.json",
        receipt_path=output_root / "activation-receipt.json",
    )
