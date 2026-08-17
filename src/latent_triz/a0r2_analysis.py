"""Frozen A0-R2 statistical analysis for the SmolLM2 cross-model study.

This module is intentionally narrow:
- it validates the frozen study protocol and analysis receipt;
- it binds the analysis to the canonical shortcut audit and exact hashes;
- it opens the sealed targets only after all pre-analysis checks succeed;
- it reuses the established A0 R1 statistical kernels without changing them;
- it emits only the schema-aligned A0-R2 statistical result payload.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .a0r1_analysis import _combo_metrics, _family_permutation_null, _family_successes, _run_sensitivity, _score_operator
from .a0r2_comparison import compare_frozen_scores
from .validator import validate


class A0R2AnalysisError(RuntimeError):
    """Raised when the frozen A0-R2 analysis contract cannot be executed."""


REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_SCHEMA_PATH = REPO_ROOT / "schemas/a0r2-study-protocol.schema.json"
SHORTCUT_SCHEMA_PATH = REPO_ROOT / "schemas/a0-shortcut-audit.schema.json"
ACTIVATION_SCHEMA_PATH = REPO_ROOT / "schemas/a0r2-activation-receipt.schema.json"
STATISTICAL_SCHEMA_PATH = REPO_ROOT / "schemas/a0r2-statistical-result.schema.json"

PRIMARY_TUPLE_INDEX = 32
PAIR_PERMUTATIONS = 999
PAIR_PERMUTATION_SEED = 20260815
TERMINAL_OUTCOMES = ("positive", "null", "failed", "non_interpretable", "incompatible")
DEFAULT_SHORTCUT_PATH = REPO_ROOT / "results/a0r1/preoutput/shortcuts.json"
DEFAULT_R1_RESULT_PATH = REPO_ROOT / "results/a0r1/a0r1-v1.0.0-e93a9faa-r1/statistical-result.json"
EXPECTED_R1_RESULT_SHA256 = "a2ad1ed0148a332fe85cb42ee2f3295e042d277d772353ebd84ccd2e255a6738"
DESCRIPTIVE_TUPLE_INDICES = (0, 11, 21, 32)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise A0R2AnalysisError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R2AnalysisError(f"cannot read JSON object: {path}") from exc
    if not isinstance(payload, dict):
        raise A0R2AnalysisError(f"{path.name} must contain a JSON object")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise A0R2AnalysisError(f"cannot read JSONL file: {path}") from exc
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise A0R2AnalysisError(f"{path.name} must contain JSON object lines")
        rows.append(row)
    if not rows:
        raise A0R2AnalysisError(f"{path.name} must not be empty")
    return rows


def _load_schema(path: Path) -> dict[str, Any]:
    return _read_json(path)


def _validate_against_schema(payload: Mapping[str, Any], schema_path: Path, *, label: str) -> None:
    issues = validate(payload, _load_schema(schema_path))
    if issues:
        raise A0R2AnalysisError(f"{label} validation failed: " + "; ".join(str(item) for item in issues))


def _validate_protocol(protocol: Mapping[str, Any]) -> None:
    _validate_against_schema(protocol, PROTOCOL_SCHEMA_PATH, label="protocol")
    primary = protocol["primary_endpoint"]
    _require(int(primary["tuple_index"]) == PRIMARY_TUPLE_INDEX, "primary tuple index drift")
    _require(int(protocol["model"]["num_hidden_layers"]) == 32, "model hidden-layer drift")
    _require(int(protocol["model"]["hidden_size"]) == 960, "model hidden-size drift")
    _require(tuple(protocol["sensitivity_endpoints"]["descriptive_tuple_indices"]) == DESCRIPTIVE_TUPLE_INDICES, "sensitivity tuple drift")
    _require(not bool(protocol["sensitivity_endpoints"]["may_replace_primary"]), "sensitivity may not replace the primary")
    _require(str(protocol["sensitivity_endpoints"]["interpretation"]) == "descriptive_only", "sensitivity must be descriptive only")
    _require(len(protocol["negative_controls"]) == 14, "negative control count drift")
    _require(protocol["shortcut_refusal"]["predictive_control_scope"] == "aggregate", "shortcut scope drift")
    _require(protocol["shortcut_refusal"]["required_control_count"] == 14, "shortcut control count drift")


def _validate_shortcuts(shortcuts: Mapping[str, Any]) -> None:
    _validate_against_schema(shortcuts, SHORTCUT_SCHEMA_PATH, label="shortcut audit")
    overall = shortcuts.get("overall", {})
    status = str(shortcuts.get("status", ""))
    overall_status = str(overall.get("status", ""))
    _require(status in {"pass", "non_interpretable", "failed"}, "shortcut status drift")
    if overall_status:
        _require(overall_status in {"pass", "non_interpretable", "failed"}, "shortcut overall status drift")


def _validate_activation_receipt(receipt: Mapping[str, Any], protocol: Mapping[str, Any]) -> None:
    _validate_against_schema(receipt, ACTIVATION_SCHEMA_PATH, label="activation receipt")
    _require(receipt.get("status") == "pass", "activation receipt must pass")
    _require(receipt.get("protocol_id") == protocol["protocol_id"], "activation protocol id drift")
    _require(int(receipt["activation"]["tuple_index"]) == PRIMARY_TUPLE_INDEX, "activation tuple index drift")
    _require(int(receipt["activation"]["hidden_states_count"]) == 33, "activation hidden-state count drift")
    _require(int(receipt["activation"]["hidden_size"]) == 960, "activation hidden size drift")
    _require(bool(receipt["activation"]["output_content_retained"]) is True, "activation output retention drift")
    _require(bool(receipt["access"]["model_loaded"]) is True, "activation model must be loaded")
    _require(bool(receipt["access"]["model_output_accessed"]) is True, "activation output access drift")
    _require(bool(receipt["access"]["sealed_targets_accessed"]) is False, "activation must not access sealed targets")
    _require(bool(receipt["access"]["claim_promotion"]) is False, "activation claim promotion drift")
    output_bundle = receipt["output_bundle"]
    _require(int(output_bundle["records"]) == 1920, "activation record count drift")
    _require(int(output_bundle["hidden_size"]) == 960, "activation hidden size bundle drift")
    _require(isinstance(output_bundle["dense_locator"], str) and output_bundle["dense_locator"].endswith("/activations.json"), "activation dense locator drift")
    _require(isinstance(output_bundle["exact_head"], str) and len(output_bundle["exact_head"]) == 40, "activation exact head drift")
    artifact_hashes = output_bundle["artifact_hashes"]
    for field in ("summary_sha256", "index_sha256", "dense_sha256"):
        _require(isinstance(artifact_hashes.get(field), str) and len(artifact_hashes[field]) == 64, f"{field} missing or invalid")
    input_hashes = receipt["input_hashes"]
    protocol_inputs = protocol["inputs"]
    _require(input_hashes["protocol_sha256"] == _sha256(REPO_ROOT / "experiments/a0r2-independent-model/study-protocol.json"), "activation protocol hash mismatch")
    _require(input_hashes["r1_protocol_sha256"] == protocol_inputs["r1_protocol_sha256"], "r1 protocol hash mismatch")
    _require(input_hashes["r1_freeze_manifest_sha256"] == protocol_inputs["r1_freeze_manifest_sha256"], "r1 freeze manifest hash mismatch")
    _require(input_hashes["corpus_manifest_sha256"] == protocol_inputs["corpus_manifest_sha256"], "corpus manifest hash mismatch")
    _require(input_hashes["cases_sha256"] == protocol_inputs["cases_sha256"], "cases hash mismatch")
    _require(input_hashes["sealed_targets_sha256"] == protocol_inputs["sealed_targets_sha256"], "sealed target input hash mismatch")
    _require(input_hashes["shortcuts_sha256"] == protocol_inputs["shortcuts_sha256"], "shortcut input hash mismatch")
    _require(input_hashes["integrity_receipt_sha256"] == protocol["model"]["integrity_receipt_sha256"], "integrity input hash mismatch")
    _require(input_hashes["feasibility_receipt_sha256"] == protocol["model"]["feasibility_receipt_sha256"], "feasibility input hash mismatch")


def _score_key(row: Mapping[str, Any]) -> tuple[str, int, str]:
    return (str(row["view"]), int(row["tuple_index"]), str(row["token_site"]))


def _case_domain(row: Mapping[str, Any]) -> str:
    domain = row.get("domain")
    if isinstance(domain, str) and domain.strip():
        return domain.strip()
    family = str(row["problem_family_id"])
    derived = family.rsplit("_", 1)[0]
    return derived[3:] if derived.startswith("r1_") else derived


def _shortcut_refusal(shortcuts: Mapping[str, Any]) -> str | None:
    status = str(shortcuts.get("status", ""))
    if status == "pass":
        return None
    if status == "non_interpretable":
        return "non_interpretable"
    return "failed"


def _read_targets_verified_once(path: Path, expected_sha256: str) -> dict[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise A0R2AnalysisError(f"cannot open sealed targets: {exc}") from exc
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise A0R2AnalysisError("sealed target hash mismatch")
    try:
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise A0R2AnalysisError("sealed target payload is invalid") from exc

    targets: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise A0R2AnalysisError("sealed target entry is not an object")
        case_id = str(row.get("case_id", ""))
        if not case_id or case_id in targets:
            raise A0R2AnalysisError("sealed targets contain missing or duplicate case_id")
        if not row.get("problem_family_id"):
            raise A0R2AnalysisError("sealed target problem_family_id missing")
        if row.get("operator_proxy_family") not in {"segmentation_like", "inversion_like"}:
            raise A0R2AnalysisError("sealed target operator family is invalid")
        targets[case_id] = row
    if not targets:
        raise A0R2AnalysisError("sealed target payload is empty")
    return targets


def _dense_vectors_from_payload(payload: Mapping[str, Any]) -> dict[str, list[float]]:
    vectors: dict[str, list[float]] = {}
    for key, value in payload.items():
        if not isinstance(value, list) or not value:
            raise A0R2AnalysisError("dense vector entry is malformed")
        vector = [float(item) for item in value]
        if not all(math.isfinite(item) for item in vector):
            raise A0R2AnalysisError("dense vector contains non-finite values")
        vectors[str(key)] = vector
    if not vectors:
        raise A0R2AnalysisError("dense vector payload is empty")
    return vectors


def _descriptive_block(
    *,
    metrics: Mapping[str, Any],
    family_outcomes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    block = {
        "family_successes": int(metrics["family_successes"]),
        "family_success_rate": float(metrics["family_success_rate"]),
        "macro_f1": float(metrics["macro_f1"]),
        "scores": [float(value) for value in metrics["scores"]],
        "per_domain_accuracy": dict(metrics["per_domain_accuracy"]),
        "domain_direction_successes": dict(metrics["domain_direction_successes"]),
    }
    if family_outcomes is not None:
        block["family_outcomes"] = dict(family_outcomes)
    return block


def _descriptive_results(
    *,
    primary_metrics: Mapping[str, Any],
    surface_metrics: Mapping[str, Any],
    family_outcomes: Mapping[str, Any],
    sensitivity: Mapping[str, Any],
    cross_model: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "interpretation": "descriptive_only",
        "may_replace_primary": False,
        "primary": _descriptive_block(metrics=primary_metrics, family_outcomes=family_outcomes),
        "surface_baseline": _descriptive_block(metrics=surface_metrics),
        "sensitivity": json.loads(json.dumps(sensitivity, sort_keys=True)),
        "cross_model": dict(cross_model),
    }


def _result_payload(
    *,
    protocol: Mapping[str, Any],
    status: str,
    created_at: str,
    primary_metrics: Mapping[str, Any],
    surface_metrics: Mapping[str, Any],
    descriptive_results: Mapping[str, Any] | None,
    primary_permutation_p: float,
    family_successes: int,
    successful_domain_directions: int,
    input_hashes: Mapping[str, str],
    artifact_hashes: Mapping[str, str],
    dense_locator: str,
    exact_head: str,
) -> dict[str, Any]:
    primary = protocol["primary_endpoint"]
    sensitivity = protocol["sensitivity_endpoints"]
    model = protocol["model"]
    runtime = protocol["runtime"]
    return {
        "artifact_class": "a0r2-statistical-result",
        "status": status,
        "created_at": created_at,
        "scientific_status": protocol["scientific_status"],
        "empirical": protocol["empirical"],
        "evidence_eligible": protocol["evidence_eligible"],
        "expert_validated": protocol["expert_validated"],
        "claim_ids": list(protocol["claim_ids"]),
        "protocol_id": protocol["protocol_id"],
        "model": {
            "id": model["id"],
            "revision": model["revision"],
            "license_id": model["license_id"],
            "model_type": model["model_type"],
            "architecture": model["architecture"],
            "num_hidden_layers": model["num_hidden_layers"],
            "hidden_size": model["hidden_size"],
            "local_locator": model["local_locator"],
        },
        "runtime": {
            "device": runtime["device"],
            "torch_dtype": runtime["torch_dtype"],
            "network_access": runtime["network_access"],
            "local_files_only": runtime["local_files_only"],
            "generation": runtime["generation"],
            "fast_offsets_required": protocol["tokenizer"]["fast_offsets_required"],
        },
        "primary_endpoint": {
            "tuple_index": primary["tuple_index"],
            "primary_semantics": primary["semantics"],
            "token_site": primary["token_site"],
            "primary_view": primary["primary_view"],
            "surface_baseline_view": primary["surface_baseline_view"],
            "surface_baseline_token_site": primary["surface_baseline_token_site"],
        },
        "sensitivity_endpoints": {
            "tuple_indices": list(sensitivity["descriptive_tuple_indices"]),
            "token_sites": list(sensitivity["token_sites"]),
            "views": list(sensitivity["views"]),
            "descriptive_only": True,
            "may_replace_primary": False,
        },
        "controls": {
            "negative_controls": list(protocol["negative_controls"]),
            "shortcut_refusal": dict(protocol["shortcut_refusal"]),
        },
        "statistics": {
            "primary_permutation_p": primary_permutation_p,
            "macro_f1_margin_over_surface": primary_metrics["macro_f1"] - surface_metrics["macro_f1"],
            "family_successes": family_successes,
            "successful_domain_directions": successful_domain_directions,
        },
        "descriptive_results": descriptive_results,
        "access": {
            "model_loaded": True,
            "model_output_accessed": True,
            "sealed_targets_accessed": True,
            "claim_promotion": False,
        },
        "input_hashes": dict(input_hashes),
        "artifact_hashes": dict(artifact_hashes),
        "result_bundle": {
            "reports": ["report.md"],
            "dense_locator": dense_locator,
            "dense_locator_sha256": _canonical_json_sha256({"dense_locator": dense_locator}),
            "exact_head": exact_head,
        },
    }


def analyze_a0r2(
    *,
    protocol_path: str | Path,
    activation_receipt_path: str | Path,
    activation_index_path: str | Path,
    dense_path: str | Path,
    targets_path: str | Path,
    output_path: str | Path,
    shortcut_path: str | Path | None = None,
    r1_result_path: str | Path | None = None,
) -> dict[str, Any]:
    try:
        import numpy as np
    except ImportError as exc:
        raise A0R2AnalysisError("numpy is required for A0-R2 statistical analysis") from exc

    protocol_path = Path(protocol_path).resolve()
    activation_receipt_path = Path(activation_receipt_path).resolve()
    activation_index_path = Path(activation_index_path).resolve()
    dense_path = Path(dense_path).resolve()
    targets_path = Path(targets_path).resolve()
    output_path = Path(output_path).resolve()
    shortcut_path = Path(shortcut_path).resolve() if shortcut_path is not None else DEFAULT_SHORTCUT_PATH
    r1_result_path = Path(r1_result_path).resolve() if r1_result_path is not None else DEFAULT_R1_RESULT_PATH

    if output_path.exists():
        raise A0R2AnalysisError(f"refusing to overwrite {output_path}")

    protocol = _read_json(protocol_path)
    receipt = _read_json(activation_receipt_path)
    shortcuts = _read_json(shortcut_path)
    r1_result = _read_json(r1_result_path)
    dense_payload = _read_json(dense_path)
    index_rows = _read_jsonl(activation_index_path)

    _validate_protocol(protocol)
    _validate_shortcuts(shortcuts)
    _validate_activation_receipt(receipt, protocol)

    receipt_sha256 = _sha256(activation_receipt_path)
    _require(_sha256(shortcut_path) == protocol["inputs"]["shortcuts_sha256"], "shortcut hash mismatch")
    _require(receipt["input_hashes"]["protocol_sha256"] == _sha256(protocol_path), "protocol hash mismatch")
    _require(receipt["input_hashes"]["shortcuts_sha256"] == _sha256(shortcut_path), "shortcut receipt hash mismatch")
    _require(receipt["input_hashes"]["integrity_receipt_sha256"] == protocol["model"]["integrity_receipt_sha256"], "integrity receipt hash mismatch")
    _require(receipt["input_hashes"]["feasibility_receipt_sha256"] == protocol["model"]["feasibility_receipt_sha256"], "feasibility receipt hash mismatch")
    _require(_sha256(r1_result_path) == EXPECTED_R1_RESULT_SHA256, "R1 descriptive result hash mismatch")
    _require(r1_result.get("artifact_class") == "a0r1-analytical-result", "R1 descriptive result class mismatch")
    _require(r1_result.get("protocol_id") == "a0-r1-tier-r1-v1.0", "R1 descriptive result protocol mismatch")

    shortcut_refusal = _shortcut_refusal(shortcuts)
    created_at = str(receipt.get("created_at") or protocol.get("created_at"))
    input_hashes = {
        "protocol_sha256": str(receipt["input_hashes"]["protocol_sha256"]),
        "r1_protocol_sha256": str(receipt["input_hashes"]["r1_protocol_sha256"]),
        "r1_freeze_manifest_sha256": str(receipt["input_hashes"]["r1_freeze_manifest_sha256"]),
        "corpus_manifest_sha256": str(receipt["input_hashes"]["corpus_manifest_sha256"]),
        "cases_sha256": str(receipt["input_hashes"]["cases_sha256"]),
        "sealed_targets_sha256": str(receipt["input_hashes"]["sealed_targets_sha256"]),
        "shortcuts_sha256": str(receipt["input_hashes"]["shortcuts_sha256"]),
        "integrity_receipt_sha256": str(receipt["input_hashes"]["integrity_receipt_sha256"]),
        "feasibility_receipt_sha256": str(receipt["input_hashes"]["feasibility_receipt_sha256"]),
        "activation_receipt_sha256": receipt_sha256,
        "representation_index_sha256": str(receipt["output_bundle"]["artifact_hashes"]["index_sha256"]),
        "dense_vectors_sha256": str(receipt["output_bundle"]["artifact_hashes"]["dense_sha256"]),
        "r1_result_sha256": EXPECTED_R1_RESULT_SHA256,
    }

    if shortcut_refusal is not None:
        statistics = {
            "primary_permutation_p": 1.0,
            "macro_f1_margin_over_surface": 0.0,
            "family_successes": 0,
            "successful_domain_directions": 0,
        }
        payload = _result_payload(
            protocol=protocol,
            status=shortcut_refusal,
            created_at=created_at,
            primary_metrics={"macro_f1": 0.0},
            surface_metrics={"macro_f1": 0.0},
            descriptive_results=None,
            primary_permutation_p=1.0,
            family_successes=0,
            successful_domain_directions=0,
            input_hashes=input_hashes,
            artifact_hashes={
                "primary_sha256": _canonical_json_sha256({"status": shortcut_refusal, "descriptive_results": None}),
                "statistics_sha256": _canonical_json_sha256(statistics),
            },
            dense_locator=str(receipt["output_bundle"]["dense_locator"]),
            exact_head=str(receipt["output_bundle"]["exact_head"]),
        )
        output_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        _validate_against_schema(payload, STATISTICAL_SCHEMA_PATH, label="statistical result")
        return payload

    dense_vectors = _dense_vectors_from_payload(dense_payload)
    case_ids = sorted({str(row["case_id"]) for row in index_rows})
    _require(bool(case_ids), "activation index has no cases")

    record_groups: dict[tuple[str, int, str], dict[str, str]] = {}
    for row in index_rows:
        combo = _score_key(row)
        case_id = str(row["case_id"])
        record_id = str(row.get("record_id", ""))
        _require(case_id in case_ids, f"unexpected case in activation index: {case_id}")
        _require(record_id in dense_vectors, f"missing dense vector for {record_id}")
        _require(int(row.get("hidden_size", 0)) == int(protocol["model"]["hidden_size"]), "hidden size drift")
        _require(str(row.get("dtype", "")) == "float32", "activation dtype drift")
        vector = dense_vectors[record_id]
        _require(row.get("vector_sha256") == _canonical_json_sha256(vector), "vector hash mismatch")
        _require(int(row["tuple_index"]) in DESCRIPTIVE_TUPLE_INDICES, "tuple index drift")
        record_groups.setdefault(combo, {})
        _require(case_id not in record_groups[combo], "duplicate representation record")
        record_groups[combo][case_id] = record_id

    _require(receipt["output_bundle"]["artifact_hashes"]["index_sha256"] == _sha256(activation_index_path), "activation index hash mismatch")
    _require(receipt["output_bundle"]["artifact_hashes"]["dense_sha256"] == _sha256(dense_path), "dense activation hash mismatch")

    target_by_case: dict[str, dict[str, Any]] = {}
    targets_sha256 = str(receipt["input_hashes"]["sealed_targets_sha256"])
    _require(targets_sha256 == protocol["inputs"]["sealed_targets_sha256"], "sealed target input hash mismatch")
    targets_map = _read_targets_verified_once(targets_path, targets_sha256)
    for case_id, row in targets_map.items():
        _require(case_id not in target_by_case, f"duplicate sealed target case: {case_id}")
        _require(case_id in case_ids, f"sealed target missing activation record: {case_id}")
        _require(bool(row.get("problem_family_id")), "sealed target missing family id")
        _require(bool(row.get("operator_proxy_family")), "sealed target missing operator proxy family")
        target_by_case[case_id] = row
    _require(len(target_by_case) == 48, "sealed boundary must contain exactly 48 cases")
    _require(set(targets_map) == set(target_by_case), "sealed target verification mismatch")

    labels: list[int] = []
    families: list[str] = []
    domains: list[str] = []
    for case_id in case_ids:
        target = targets_map[case_id]
        families.append(str(target["problem_family_id"]))
        domains.append(_case_domain(target))
        labels.append(1 if target["operator_proxy_family"] == "segmentation_like" else 0)
    _require(len(set(families)) == 24, "sealed boundary must contain 24 families")
    _require(len(set(domains)) == 6, "sealed boundary must contain 6 domains")

    for family in sorted(set(families)):
        members = [index for index, value in enumerate(families) if value == family]
        _require(len(members) == 2, f"family {family} is not a balanced pair")
        _require(sorted(labels[index] for index in members) == [0, 1], f"family {family} is not label-balanced")

    combos: dict[tuple[str, int, str], Any] = {}
    for combo, records in sorted(record_groups.items()):
        _require(set(records) == set(case_ids), f"incomplete representation combo {combo}")
        matrix = np.asarray([dense_vectors[records[case_id]] for case_id in case_ids], dtype=np.float64)
        _require(matrix.ndim == 2, "activation matrix must be 2D")
        _require(matrix.shape[1] == int(protocol["model"]["hidden_size"]), "activation vector dimension drift")
        _require(bool(np.isfinite(matrix).all()), "activation matrix contains non-finite values")
        combos[combo] = _score_operator(matrix, domains, alpha=float(protocol["classifier"]["alpha"]))

    primary_combo = (
        str(protocol["primary_endpoint"]["primary_view"]),
        PRIMARY_TUPLE_INDEX,
        str(protocol["primary_endpoint"]["token_site"]),
    )
    surface_combo = (
        str(protocol["primary_endpoint"]["surface_baseline_view"]),
        PRIMARY_TUPLE_INDEX,
        str(protocol["primary_endpoint"]["surface_baseline_token_site"]),
    )
    _require(primary_combo in combos, "required primary combo missing")
    _require(surface_combo in combos, "required surface combo missing")

    primary_metrics = _combo_metrics(combos[primary_combo], labels, families, domains)
    surface_metrics = _combo_metrics(combos[surface_combo], labels, families, domains)
    primary_successes, family_outcomes = _family_successes(
        primary_metrics["scores"],
        labels,
        families,
    )
    family_successes = int(primary_metrics["family_successes"])
    _require(primary_successes == family_successes, "family success computation mismatch")
    permutation_maxima = _family_permutation_null(
        combos[primary_combo],
        labels,
        families,
        seed=PAIR_PERMUTATION_SEED,
        budget=PAIR_PERMUTATIONS,
    )
    primary_permutation_p = (1 + sum(value >= family_successes for value in permutation_maxima)) / (len(permutation_maxima) + 1)
    successful_domain_directions = sum(1 for value in primary_metrics["domain_direction_successes"].values() if value > 0.0)
    sensitivity = _run_sensitivity(
        combos=combos,
        labels=labels,
        families=families,
        domains=domains,
        layers=list(DESCRIPTIVE_TUPLE_INDICES),
        views=list(protocol["sensitivity_endpoints"]["views"]),
        token_sites=list(protocol["sensitivity_endpoints"]["token_sites"]),
    )
    r1_primary = r1_result.get("primary")
    _require(isinstance(r1_primary, Mapping), "R1 primary descriptive block missing")
    cross_model = compare_frozen_scores(
        r1_scores=r1_primary.get("scores", []),
        r2_scores=primary_metrics["scores"],
        labels=labels,
        families=families,
        r1_domain_directions=r1_primary.get("domain_direction_successes", {}),
        r2_domain_directions=primary_metrics["domain_direction_successes"],
    )
    descriptive_results = _descriptive_results(
        primary_metrics=primary_metrics,
        surface_metrics=surface_metrics,
        family_outcomes=family_outcomes,
        sensitivity=sensitivity,
        cross_model=cross_model,
    )

    positive = (
        primary_permutation_p <= float(protocol["thresholds"]["primary_permutation_p_at_most"])
        and (primary_metrics["macro_f1"] - surface_metrics["macro_f1"]) >= float(protocol["thresholds"]["macro_f1_margin_at_least"])
        and family_successes >= int(protocol["thresholds"]["family_successes_at_least"])
        and successful_domain_directions >= int(protocol["thresholds"]["domain_direction_successes_minimum"])
    )
    status = "positive" if positive else "null"
    statistics = {
        "primary_permutation_p": primary_permutation_p,
        "macro_f1_margin_over_surface": primary_metrics["macro_f1"] - surface_metrics["macro_f1"],
        "family_successes": family_successes,
        "successful_domain_directions": successful_domain_directions,
    }
    artifact_hashes = {
        "primary_sha256": _canonical_json_sha256(descriptive_results["primary"]),
        "statistics_sha256": _canonical_json_sha256(statistics),
    }

    payload = _result_payload(
        protocol=protocol,
        status=status,
        created_at=created_at,
        primary_metrics=primary_metrics,
        surface_metrics=surface_metrics,
        descriptive_results=descriptive_results,
        primary_permutation_p=primary_permutation_p,
        family_successes=family_successes,
        successful_domain_directions=successful_domain_directions,
        input_hashes=input_hashes,
        artifact_hashes=artifact_hashes,
        dense_locator=str(receipt["output_bundle"]["dense_locator"]),
        exact_head=str(receipt["output_bundle"]["exact_head"]),
    )
    output_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    _validate_against_schema(payload, STATISTICAL_SCHEMA_PATH, label="statistical result")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run the frozen A0-R2 analysis.")
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--activation-receipt", required=True)
    parser.add_argument("--activation-index", required=True)
    parser.add_argument("--dense", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--shortcut", default=None)
    parser.add_argument("--r1-result", default=None)
    args = parser.parse_args(argv)

    analyze_a0r2(
        protocol_path=args.protocol,
        activation_receipt_path=args.activation_receipt,
        activation_index_path=args.activation_index,
        dense_path=args.dense,
        targets_path=args.targets,
        output_path=args.output,
        shortcut_path=args.shortcut,
        r1_result_path=args.r1_result,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
