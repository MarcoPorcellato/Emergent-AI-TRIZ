"""Deterministic fixed-primary analysis for A0-R1 statistics.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


class A0R1AnalysisError(RuntimeError):
    """Raised when the R1 analysis cannot be produced safely."""


EPISTEMIC = {
    "empirical": True,
    "scientific_status": "exploratory",
    "evidence_eligible": False,
    "expert_validated": False,
    "claim_ids": [],
}


PRIMARY_ENDPOINT = {
    "layer": 6,
    "token_site": "mean_transformation_span",
    "primary_view": "problem_plus_transformation",
    "surface_baseline_view": "problem_only",
    "surface_token_site": "sentinel",
    "required_successes": 17,
    "required_domain_directions": 4,
    "required_margin": 0.10,
    "required_p_at_most": 0.05,
    "required_permutation_budget": 999,
    "required_seed": 20260815,
}


def analyze_a0r1(
    *,
    protocol_path: str | Path,
    implementation_path: str | Path,
    shortcut_path: str | Path,
    activation_receipt_path: str | Path,
    activation_index_path: str | Path,
    dense_path: str | Path,
    targets_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Run fixed primary R1 statistical analysis and write one JSON result.

    The implementation is intentionally deterministic and refuse-to-overwrite.
    """

    protocol_path = Path(protocol_path).resolve()
    implementation_path = Path(implementation_path).resolve()
    shortcut_path = Path(shortcut_path).resolve()
    activation_receipt_path = Path(activation_receipt_path).resolve()
    activation_index_path = Path(activation_index_path).resolve()
    dense_path = Path(dense_path).resolve()
    targets_path = Path(targets_path).resolve()
    output_path = Path(output_path).resolve()

    if output_path.exists():
        raise A0R1AnalysisError(f"refusing to overwrite {output_path}")

    protocol = _read_json(protocol_path)
    implementation = _read_json(implementation_path)
    shortcuts = _read_json(shortcut_path)
    receipt = _read_json(activation_receipt_path)
    for label, payload in (("implementation", implementation), ("shortcuts", shortcuts), ("activation receipt", receipt)):
        for key, expected in EPISTEMIC.items():
            if payload.get(key) != expected:
                raise A0R1AnalysisError(f"{label} has invalid epistemic field {key}")

    endpoint = _read_protocol(protocol)
    classifier = implementation.get("classifier")
    if not isinstance(classifier, Mapping):
        raise A0R1AnalysisError("implementation classifier is missing")
    if classifier.get("name") != "l2_regularized_linear_least_squares" or classifier.get("solver") != "dual_kernel_closed_form":
        raise A0R1AnalysisError("implementation classifier contract drift")
    if classifier.get("standardization") is not True or classifier.get("standardization_scope") != "within_train_folds":
        raise A0R1AnalysisError("implementation standardization contract drift")
    alpha = _as_float(classifier.get("alpha"), field="implementation.classifier.alpha")
    permutations = implementation.get("permutations")
    if not isinstance(permutations, Mapping) or permutations.get("seed") != endpoint["seed"] or permutations.get("budget") != endpoint["permutation_budget"]:
        raise A0R1AnalysisError("implementation permutation contract drift")
    if permutations.get("pairing") != "paired_within_family_swaps" or permutations.get("correction") != "fixed_primary_no_multiplicity":
        raise A0R1AnalysisError("implementation permutation scheme drift")
    direction = implementation.get("domain_direction")
    if not isinstance(direction, Mapping) or direction.get("statistic") != "mean_paired_primary_score_difference_strictly_positive_in_held_out_domain":
        raise A0R1AnalysisError("implementation domain-direction statistic drift")
    if direction.get("minimum_successful_domains") != endpoint["required_domain_directions"]:
        raise A0R1AnalysisError("implementation domain-direction threshold drift")
    if implementation.get("surface_baseline_token_site") != "sentinel":
        raise A0R1AnalysisError("implementation surface baseline site drift")
    if implementation.get("status") != "frozen_before_model_output":
        raise A0R1AnalysisError("implementation is not frozen before model output")
    if implementation.get("sensitivity_may_replace_primary") is not False:
        raise A0R1AnalysisError("sensitivity must not replace the fixed primary")

    if shortcuts.get("status") != "pass":
        status = "non_interpretable" if shortcuts.get("status") == "non_interpretable" else "failed"
        result = _failure_summary(
            protocol_path,
            implementation_path,
            shortcut_path,
            activation_receipt_path,
            activation_index_path,
            targets_path,
            status,
            outcome_reason="shortcut gate is not pass",
            endpoint=endpoint,
        )
        return _write_result(output_path, result)

    if receipt.get("status") != "pass":
        result = _failure_summary(
            protocol_path,
            implementation_path,
            shortcut_path,
            activation_receipt_path,
            activation_index_path,
            targets_path,
            "failed",
            outcome_reason="activation receipt is not pass",
            endpoint=endpoint,
        )
        return _write_result(output_path, result)
    if receipt.get("sealed_target_semantics_accessed") is not False:
        raise A0R1AnalysisError("activation stage accessed sealed target semantics")
    if receipt.get("model_output_accessed") is not True or receipt.get("sealed_model_output_accessed") is not True:
        raise A0R1AnalysisError("activation receipt does not bind sealed model output")
    if receipt["corpus"].get("sealed_targets_accessed") is not False:
        raise A0R1AnalysisError("activation stage opened sealed target content")

    if receipt["protocol"].get("hash") != _sha256(protocol_path):
        raise A0R1AnalysisError("protocol receipt mismatch")
    if receipt["implementation"].get("hash") != _sha256(implementation_path):
        raise A0R1AnalysisError("implementation receipt mismatch")
    if receipt["dense_vectors"].get("sha256") != _sha256(dense_path):
        raise A0R1AnalysisError("dense activation receipt mismatch")
    if receipt["representation_index"].get("sha256") != _sha256(activation_index_path):
        raise A0R1AnalysisError("representation index receipt mismatch")
    expected_target_hash = str(receipt["corpus"].get("sealed_targets_sha256", ""))
    if expected_target_hash != implementation["protocol"].get("sealed_targets_sha256"):
        raise A0R1AnalysisError("sealed target binding differs from implementation contract")

    index_rows = _read_jsonl(activation_index_path)
    dense_vectors = _read_dense_vectors(dense_path)
    targets_map = _read_targets_once_verified(targets_path, expected_target_hash)
    case_ids = sorted({str(row["case_id"]) for row in index_rows})
    if not case_ids:
        raise A0R1AnalysisError("no activation cases found")
    if len(case_ids) != int(receipt["corpus"]["selected_cases"]):
        raise A0R1AnalysisError("activation index case count mismatch")
    if len(case_ids) != 48 or set(case_ids) != set(targets_map):
        raise A0R1AnalysisError("sealed boundary must contain exactly the same 48 cases")

    labels: list[int] = []
    families: list[str] = []
    domains: list[str] = []
    for case_id in case_ids:
        target = targets_map[str(case_id)]
        families.append(str(target["problem_family_id"]))
        domains.append(str(target["problem_family_id"]).rsplit("_", 1)[0])
        labels.append(1 if target["operator_proxy_family"] == "segmentation_like" else 0)
    if len(set(families)) != 24 or len(set(domains)) != 6:
        raise A0R1AnalysisError("sealed boundary must contain 24 families across 6 domains")

    import numpy as np

    combos: dict[tuple[str, int, str], Any] = {}
    by_combo: dict[tuple[str, int, str], dict[str, str]] = defaultdict(dict)
    for row in index_rows:
        combo = (str(row["view"]), int(row["layer"]), str(row["token_site"]))
        case_id = str(row["case_id"])
        if case_id not in targets_map:
            raise A0R1AnalysisError(f"unexpected case in index: {case_id}")
        if case_id in by_combo[combo]:
            raise A0R1AnalysisError("duplicate representation record")
        record_id = str(row.get("record_id", ""))
        if not record_id or record_id not in dense_vectors:
            raise A0R1AnalysisError("representation index references a missing vector")
        vector = dense_vectors[record_id]
        if row.get("vector_sha256") != _canonical_json_sha256(vector):
            raise A0R1AnalysisError("representation vector hash mismatch")
        by_combo[combo][case_id] = record_id
    for combo, record in sorted(by_combo.items()):
        if set(record) != set(case_ids):
            raise A0R1AnalysisError(f"incomplete representation combo {combo}")
        matrix = np.asarray([dense_vectors[record[case_id]] for case_id in case_ids], dtype=np.float64)
        if matrix.ndim != 2 or not bool(np.isfinite(matrix).all()):
            raise A0R1AnalysisError("activation matrix is invalid")
        combos[combo] = _score_operator(matrix, domains, alpha=alpha)

    primary_combo = (
        endpoint["primary_view"],
        endpoint["layer"],
        endpoint["token_site"],
    )
    baseline_combo = (
        endpoint["surface_baseline_view"],
        endpoint["layer"],
        endpoint["surface_token_site"],
    )
    if primary_combo not in combos or baseline_combo not in combos:
        raise A0R1AnalysisError("required R1 primary/baseline combo missing in index")

    primary = _combo_metrics(combos[primary_combo], labels, families, domains)
    surface = _combo_metrics(combos[baseline_combo], labels, families, domains)

    observed_successes = primary["family_successes"]
    observed_margin = primary["macro_f1"] - surface["macro_f1"]
    domain_successes = primary["domain_direction_successes"]
    domain_successes_count = sum(1 for value in domain_successes.values() if value > 0.0)
    if len(domain_successes) < PRIMARY_ENDPOINT["required_domain_directions"]:
        domain_successes_count = 0

    null_maxima = _family_permutation_null(
        combos[primary_combo],
        labels,
        families,
        seed=endpoint["seed"],
        budget=endpoint["permutation_budget"],
    )
    primary_permutation_p = (1 + sum(value >= observed_successes for value in null_maxima)) / (
        len(null_maxima) + 1
    )

    sensitivity = _run_sensitivity(
        combos=combos,
        labels=labels,
        families=families,
        domains=domains,
        layers=endpoint["sensitivity_layers"],
        views=endpoint["sensitivity_views"],
        token_sites=endpoint["sensitivity_sites"],
    )

    positive = (
        observed_successes >= endpoint["critical_successes"]
        and observed_margin >= endpoint["required_margin"]
        and primary_permutation_p <= endpoint["required_p"]
        and domain_successes_count >= endpoint["required_domain_directions"]
    )
    status = "positive" if positive else "null"

    result = {
        "artifact_class": "a0r1-analytical-result",
        **EPISTEMIC,
        "status": status,
        "protocol_id": protocol["protocol_id"],
        "protocol_status": protocol.get("status") or protocol.get("protocol_status"),
        "analysis_type": "fixed_primary",
        "sealing_rule": "sealed_targets_opened_once_at_boundary",
        "shortcut_status": str(shortcuts.get("status")),
        "input_hashes": {
            "protocol": _canonical_json_sha256(protocol),
            "implementation": _sha256(implementation_path),
            "shortcut": _sha256(shortcut_path),
            "activation_receipt": _sha256(activation_receipt_path),
            "representation_index": _sha256(activation_index_path),
            "dense_vectors": _sha256(dense_path),
            "sealed_targets": _sha256(targets_path),
        },
        "design": {
            "cases": len(case_ids),
            "families": len(set(families)),
            "domains": len(set(domains)),
            "layer": endpoint["layer"],
            "token_site": endpoint["token_site"],
            "primary_view": endpoint["primary_view"],
            "surface_view": endpoint["surface_baseline_view"],
            "surface_site": endpoint["surface_token_site"],
            "permutation_budget": endpoint["permutation_budget"],
            "seed": endpoint["seed"],
            "critical_successes": endpoint["critical_successes"],
            "required_domain_directions": endpoint["required_domain_directions"],
        },
        "primary": primary,
        "surface_baseline": surface,
        "macro_f1_margin_over_surface": observed_margin,
        "max_family_successes_observed": observed_successes,
        "domain_direction_successes": domain_successes,
        "domain_direction_success_count": domain_successes_count,
        "primary_permutation_p": primary_permutation_p,
        "permutation_seed": endpoint["seed"],
        "permutation_budget": endpoint["permutation_budget"],
        "null_maxima": {
            "minimum": min(null_maxima),
            "median": sorted(null_maxima)[len(null_maxima) // 2],
            "maximum": max(null_maxima),
            "sha256": hashlib.sha256(
                json.dumps(null_maxima, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        },
        "sensitivity": sensitivity,
        "outcome_rule": {
            "max_statistic_p_at_most": endpoint["required_p"],
            "macro_f1_margin_at_least": endpoint["required_margin"],
            "family_successes_at_least": endpoint["critical_successes"],
            "domain_direction_successes_minimum": endpoint["required_domain_directions"],
        },
        "outcome_deterministic": True,
        "model_output_accessed": True,
        "sealed_model_output_accessed": True,
        "sealed_targets_accessed": True,
        "primary_is_max_statistic_selection": False,
        "outcome_description": _interpret(status, positive),
        "non_interpretable_reason": None,
    }
    return _write_result(output_path, result)


def _failure_summary(
    protocol_path: Path,
    implementation_path: Path,
    shortcut_path: Path,
    activation_receipt_path: Path,
    activation_index_path: Path,
    targets_path: Path,
    status: str,
    *,
    outcome_reason: str,
    endpoint: Mapping[str, Any],
    dense_path: Path | None = None,
) -> dict[str, Any]:
    return {
        "artifact_class": "a0r1-analytical-result",
        **EPISTEMIC,
        "status": status,
        "protocol_id": _safe_json_key(protocol_path, "protocol_id"),
        "protocol_status": "unknown",
        "analysis_type": "fixed_primary",
        "sealing_rule": "sealed_targets_opened_once_at_boundary",
        "shortcut_status": str(_read_json(shortcut_path).get("status")),
        "input_hashes": {
            "protocol": _safe_canonical(protocol_path),
            "implementation": _safe_sha256(implementation_path),
            "shortcut": _safe_sha256(shortcut_path),
            "activation_receipt": _safe_sha256(activation_receipt_path),
            "representation_index": _safe_sha256(activation_index_path),
            "dense_vectors": _safe_sha256(dense_path),
            "sealed_targets": str(_read_json(implementation_path).get("protocol", {}).get("sealed_targets_sha256", "")),
        },
        "design": {
            "cases": 0,
            "families": 0,
            "domains": 0,
            "layer": endpoint.get("layer"),
            "token_site": endpoint.get("token_site"),
            "primary_view": endpoint.get("primary_view"),
            "surface_view": endpoint.get("surface_baseline_view"),
            "surface_site": endpoint.get("surface_token_site"),
            "permutation_budget": endpoint.get("permutation_budget"),
            "seed": endpoint.get("seed"),
            "critical_successes": endpoint.get("critical_successes"),
            "required_domain_directions": endpoint.get("required_domain_directions"),
        },
        "primary": {},
        "surface_baseline": {},
        "macro_f1_margin_over_surface": 0.0,
        "max_family_successes_observed": 0,
        "domain_direction_successes": {},
        "domain_direction_success_count": 0,
        "primary_permutation_p": 1.0,
        "permutation_seed": endpoint.get("seed", PRIMARY_ENDPOINT["required_seed"]),
        "permutation_budget": endpoint.get("permutation_budget", PRIMARY_ENDPOINT["required_permutation_budget"]),
        "null_maxima": {
            "minimum": None,
            "median": None,
            "maximum": None,
            "sha256": None,
        },
        "sensitivity": {},
        "outcome_rule": {
            "max_statistic_p_at_most": endpoint["required_p"],
            "macro_f1_margin_at_least": endpoint["required_margin"],
            "family_successes_at_least": endpoint["required_successes"],
            "domain_direction_successes_minimum": endpoint["required_domain_directions"],
        },
        "outcome_deterministic": True,
        "model_output_accessed": False,
        "sealed_model_output_accessed": False,
        "sealed_targets_accessed": False,
        "primary_is_max_statistic_selection": False,
        "outcome_description": outcome_reason,
        "non_interpretable_reason": outcome_reason if status == "non_interpretable" else None,
    }


def _safe_json_key(protocol_path: Path, key: str, default: str = "") -> str:
    try:
        payload = _read_json(protocol_path)
        value = payload.get(key)
        return str(value) if value is not None else default
    except OSError:
        return default


def _safe_canonical(protocol_path: Path) -> str:
    try:
        return _canonical_json_sha256(_read_json(protocol_path))
    except OSError:
        return ""


def _read_targets_once(path: Path) -> dict[str, dict[str, Any]]:
    target_rows = _read_jsonl(path)
    targets = {}
    for row in target_rows:
        case_id = str(row["case_id"])
        if case_id in targets:
            raise A0R1AnalysisError(f"duplicate case in sealed targets: {case_id}")
        if "problem_family_id" not in row or "operator_proxy_family" not in row:
            raise A0R1AnalysisError("sealed target records must include problem_family_id/operator_proxy_family")
        targets[case_id] = row
    return targets


def _read_targets_once_verified(path: Path, expected_sha256: str) -> dict[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise A0R1AnalysisError(f"cannot open sealed target boundary: {exc}") from exc
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise A0R1AnalysisError("sealed target receipt mismatch")
    try:
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise A0R1AnalysisError("sealed target payload is invalid") from exc
    targets: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise A0R1AnalysisError("sealed target entry is not an object")
        case_id = str(row.get("case_id", ""))
        if not case_id or case_id in targets:
            raise A0R1AnalysisError("sealed targets contain missing or duplicate case_id")
        if row.get("operator_proxy_family") not in {"segmentation_like", "inversion_like"}:
            raise A0R1AnalysisError("sealed target operator family is invalid")
        if not row.get("problem_family_id"):
            raise A0R1AnalysisError("sealed target problem_family_id is missing")
        targets[case_id] = row
    if not targets:
        raise A0R1AnalysisError("sealed target payload is empty")
    return targets


def _read_dense_vectors(path: Path) -> dict[str, list[float]]:
    payload = _read_json(path)
    vectors: dict[str, list[float]] = {}
    for key, value in payload.items():
        if not isinstance(value, list) or not value:
            raise A0R1AnalysisError("dense vector entry is malformed")
        vector = [float(item) for item in value]
        if not all(math.isfinite(item) for item in vector):
            raise A0R1AnalysisError("dense vector contains non-finite values")
        vectors[str(key)] = vector
    if not vectors:
        raise A0R1AnalysisError("dense vector payload is empty")
    return vectors


def _read_protocol(payload: Mapping[str, Any]) -> dict[str, Any]:
    protocol = dict(payload)
    status = str(protocol.get("status") or protocol.get("protocol_status", "")).strip().lower()
    if status != "frozen" or protocol.get("protocol_status") != "frozen":
        raise A0R1AnalysisError("protocol status must be frozen")

    primary = protocol.get("primary_endpoint")
    if not isinstance(primary, Mapping):
        raise A0R1AnalysisError("protocol missing primary_endpoint")

    if int(primary.get("layer", -1)) != PRIMARY_ENDPOINT["layer"]:
        raise A0R1AnalysisError("protocol primary layer must be 6")
    if str(primary.get("token_site", "")) != PRIMARY_ENDPOINT["token_site"]:
        raise A0R1AnalysisError("protocol token_site must be mean_transformation_span")
    if str(primary.get("primary_view", "")) != PRIMARY_ENDPOINT["primary_view"]:
        raise A0R1AnalysisError("protocol primary_view must be problem_plus_transformation")
    if str(primary.get("surface_baseline_view", "")) != PRIMARY_ENDPOINT["surface_baseline_view"]:
        raise A0R1AnalysisError("protocol surface baseline must be problem_only")
    if int(primary.get("multiplicity", 0)) != 1:
        raise A0R1AnalysisError("protocol primary multiplicity must be 1")
    if bool(primary.get("is_max_statistic_selection", True)):
        raise A0R1AnalysisError("protocol cannot select max-statistic primary")

    calibration = protocol.get("calibration", {})
    if str(calibration.get("selection_mode", "")) != "deterministic_predeclared":
        raise A0R1AnalysisError("protocol calibration selection_mode must be deterministic_predeclared")
    if int(calibration.get("selected_permutation_budget", -1)) != PRIMARY_ENDPOINT["required_permutation_budget"]:
        raise A0R1AnalysisError("protocol permutation budget must be 999")
    if int(calibration.get("deterministic_seed", 0)) != PRIMARY_ENDPOINT["required_seed"]:
        raise A0R1AnalysisError("protocol deterministic_seed must be 20260815")

    if int(protocol.get("calibration", {}).get("selected_family_count", 0)) != 24:
        raise A0R1AnalysisError("calibration selected_family_count must be 24")

    thresholds = protocol.get("thresholds", {})
    if int(thresholds.get("critical_successes", 0)) != PRIMARY_ENDPOINT["required_successes"]:
        raise A0R1AnalysisError("critical_successes must be 17")
    if int(thresholds.get("family_successes_at_least", 0)) != PRIMARY_ENDPOINT["required_successes"]:
        raise A0R1AnalysisError("family_successes_at_least must be 17")
    if not math.isclose(
        float(thresholds.get("primary_permutation_p_at_most", 1.0)),
        PRIMARY_ENDPOINT["required_p_at_most"],
    ):
        raise A0R1AnalysisError("primary_permutation_p_at_most must be 0.05")
    if int(thresholds.get("domain_direction_successes_minimum", 0)) != PRIMARY_ENDPOINT["required_domain_directions"]:
        raise A0R1AnalysisError("domain_direction_successes_minimum must be 4")
    if not math.isclose(float(thresholds.get("macro_f1_margin_at_least", -1.0)), PRIMARY_ENDPOINT["required_margin"]):
        raise A0R1AnalysisError("macro_f1_margin_at_least must be 0.10")

    thresholded = protocol.get("sensitivity_endpoints", {})
    if bool(thresholded.get("may_replace_primary", False)):
        raise A0R1AnalysisError("sensitivity may_replace_primary must be false")
    layers = thresholded.get("layers")
    views = thresholded.get("views")
    sites = thresholded.get("token_sites")
    if not isinstance(layers, Sequence) or not isinstance(views, Sequence) or not isinstance(sites, Sequence):
        raise A0R1AnalysisError("sensitivity_endpoints must define layers/views/token_sites")
    if 6 not in layers or "problem_only" not in views or "sentinel" not in sites:
        raise A0R1AnalysisError("sensitivity_endpoints must include primary-compatible controls")

    return {
        "protocol_id": protocol.get("protocol_id", ""),
        "layer": int(primary.get("layer")),
        "token_site": str(primary.get("token_site")),
        "primary_view": str(primary.get("primary_view")),
        "surface_baseline_view": str(primary.get("surface_baseline_view")),
        "surface_token_site": "sentinel",
        "critical_successes": int(thresholds.get("critical_successes")),
        "required_successes": int(thresholds.get("family_successes_at_least")),
        "required_p": float(thresholds.get("primary_permutation_p_at_most")),
        "required_margin": float(thresholds.get("macro_f1_margin_at_least")),
        "required_domain_directions": int(thresholds.get("domain_direction_successes_minimum")),
        "permutation_budget": int(calibration.get("selected_permutation_budget")),
        "seed": int(calibration.get("deterministic_seed")),
        "sensitivity_layers": [int(value) for value in layers],
        "sensitivity_views": [str(value) for value in views],
        "sensitivity_sites": [str(value) for value in sites],
    }


def _score_operator(matrix: Any, domains: Sequence[str], *, alpha: float) -> Any:
    import numpy as np

    matrix = np.asarray(matrix, dtype=np.float64)
    count = matrix.shape[0]
    operator = np.zeros((count, count), dtype=np.float64)
    for held_domain in sorted(set(domains)):
        train = [index for index, domain in enumerate(domains) if domain != held_domain]
        test = [index for index, domain in enumerate(domains) if domain == held_domain]
        if not train or not test:
            raise A0R1AnalysisError("leave-one-domain-out split is empty")
        mean = matrix[train].mean(axis=0)
        std = matrix[train].std(axis=0)
        std[std < 1e-12] = 1.0
        train_x = (matrix[train] - mean) / std
        test_x = (matrix[test] - mean) / std
        kernel = train_x @ train_x.T
        solved = np.linalg.solve(kernel + alpha * np.eye(len(train)), np.eye(len(train)))
        operator[np.ix_(test, train)] = test_x @ train_x.T @ solved
    return operator


def _macro_f1(labels: Sequence[int], predictions: Sequence[int]) -> float:
    scores: list[float] = []
    for value in (0, 1):
        tp = sum(int(y == value and p == value) for y, p in zip(labels, predictions))
        fp = sum(int(y != value and p == value) for y, p in zip(labels, predictions))
        fn = sum(int(y == value and p != value) for y, p in zip(labels, predictions))
        denom = 2 * tp + fp + fn
        scores.append(0.0 if denom == 0 else (2.0 * tp) / denom)
    return math.fsum(scores) / 2.0


def _paired_family_direction(scores: Sequence[float], labels: Sequence[int], families: Sequence[str]) -> float:
    members: dict[str, list[int]] = defaultdict(list)
    for index, family in enumerate(families):
        members[str(family)].append(index)
    deltas: list[float] = []
    for index, family_indices in sorted(members.items()):
        if len(family_indices) != 2:
            raise A0R1AnalysisError(f"family {index} is not a paired family")
        if sorted(labels[j] for j in family_indices) != [0, 1]:
            raise A0R1AnalysisError(f"family {index} is not balanced")
        positive = next(i for i in family_indices if labels[i] == 1)
        negative = next(i for i in family_indices if labels[i] == 0)
        deltas.append(float(scores[positive]) - float(scores[negative]))
    return math.fsum(deltas) / len(deltas)


def _family_successes(
    scores: Sequence[float],
    labels: Sequence[int],
    families: Sequence[str],
) -> tuple[int, dict[str, bool]]:
    members: dict[str, list[int]] = defaultdict(list)
    for index, family in enumerate(families):
        members[str(family)].append(index)
    outcomes: dict[str, bool] = {}
    for family, indices in sorted(members.items()):
        if len(indices) != 2 or sorted(labels[index] for index in indices) != [0, 1]:
            raise A0R1AnalysisError(f"family {family} is not a balanced pair")
        positive = next(index for index in indices if labels[index] == 1)
        negative = next(index for index in indices if labels[index] == 0)
        outcomes[family] = float(scores[positive]) > float(scores[negative])
    return sum(outcomes.values()), outcomes


def _family_direction_deltas_by_domain(
    scores: Sequence[float],
    labels: Sequence[int],
    families: Sequence[str],
    domains: Sequence[str],
) -> dict[str, float]:
    family_indices_by_domain: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))

    for index, (family, domain) in enumerate(zip(families, domains, strict=True)):
        family_indices_by_domain[str(domain)][str(family)].append(index)

    deltas: dict[str, list[float]] = defaultdict(list)
    for domain, by_family in family_indices_by_domain.items():
        for family, member_indices in sorted(by_family.items()):
            if len(member_indices) != 2:
                raise A0R1AnalysisError(f"family {family} in {domain} is not a paired family")
            if sorted(labels[index] for index in member_indices) != [0, 1]:
                raise A0R1AnalysisError(f"family {family} in {domain} is not balanced")
            positive = member_indices[0] if labels[member_indices[0]] == 1 else member_indices[1]
            negative = member_indices[0] if labels[member_indices[0]] == 0 else member_indices[1]
            deltas[domain].append(float(scores[positive]) - float(scores[negative]))

    return {
        domain: math.fsum(values) / len(values)
        for domain, values in deltas.items()
    }


def _domain_direction_metrics(
    scores: Sequence[float],
    labels: Sequence[int],
    families: Sequence[str],
    domains: Sequence[str],
) -> dict[str, float]:
    deltas = _family_direction_deltas_by_domain(scores, labels, families, domains)
    ordered: dict[str, float] = {}
    for domain in sorted(deltas):
        ordered[domain] = deltas[domain]
    return ordered


def _combo_metrics(
    operator: Any,
    labels: Sequence[int],
    families: Sequence[str],
    domains: Sequence[str],
) -> dict[str, Any]:
    import numpy as np

    signed = np.asarray([1.0 if value == 1 else -1.0 for value in labels], dtype=np.float64)
    scores = operator @ signed
    predictions = [int(value >= 0.0) for value in scores]
    successes, family_outcomes = _family_successes(scores, labels, families)
    per_domain = {}
    for domain in sorted(set(domains)):
        indices = [index for index, value in enumerate(domains) if value == domain]
        if not indices:
            continue
        per_domain[domain] = sum(predictions[index] == labels[index] for index in indices) / len(indices)
    return {
        "family_successes": successes,
        "family_success_rate": successes / len(family_outcomes),
        "scores": [float(value) for value in scores],
        "macro_f1": _macro_f1(labels, predictions),
        "per_domain_accuracy": per_domain,
        "domain_direction_successes": _domain_direction_metrics(scores, labels, families, domains),
    }


def _family_permutation_null(
    operator: Any,
    labels: Sequence[int],
    families: Sequence[str],
    *,
    seed: int,
    budget: int,
) -> list[int]:
    rng = random.Random(seed)
    members: dict[str, list[int]] = defaultdict(list)
    for index, family in enumerate(families):
        members[str(family)].append(index)
    seen_masks: set[int] = set()
    null_values: list[int] = []

    import numpy as np

    signed_base = np.asarray([1.0 if value == 1 else -1.0 for value in labels], dtype=np.float64)
    while len(null_values) < budget:
        mask = rng.getrandbits(len(members))
        if mask in seen_masks:
            continue
        seen_masks.add(mask)
        permuted = list(labels)
        for bit, indices in enumerate(members.values()):
            if mask & (1 << bit):
                if len(indices) != 2:
                    raise A0R1AnalysisError("non-paired family in permutation")
                first, second = indices
                permuted[first], permuted[second] = permuted[second], permuted[first]
        permuted_scores = operator @ np.asarray([1.0 if value == 1 else -1.0 for value in permuted], dtype=np.float64)
        successes, _ = _family_successes(permuted_scores, permuted, families)
        null_values.append(successes)
    return null_values


def _run_sensitivity(
    *,
    combos: Mapping[tuple[str, int, str], Any],
    labels: Sequence[int],
    families: Sequence[str],
    domains: Sequence[str],
    layers: Sequence[int],
    views: Sequence[str],
    token_sites: Sequence[str],
) -> dict[str, Any]:
    sensitivity: dict[str, Any] = {}
    for view in views:
        view_metrics = {}
        for layer in layers:
            layer_metrics = {}
            for site in token_sites:
                combo = (str(view), int(layer), str(site))
                if combo not in combos:
                    continue
                layer_metrics[f"{combo}"] = _combo_metrics(combos[combo], labels, families, domains)
            view_metrics[str(layer)] = layer_metrics
        sensitivity[str(view)] = {
            "combos": view_metrics,
            "paired_direction_delta_mean": (
                sum(
                    _paired_family_direction(payload["scores"], labels, families)
                    for row in view_metrics.values()
                    for payload in row.values()
                )
                / max(
                    1,
                    sum(1 for row in view_metrics.values() for payload in row.values()),
                )
            )
            if any(view_metrics.values())
            else 0.0,
            "rescues_primary": False,
        }
    return sensitivity


def _interpret(status: str, positive: bool) -> str:
    if status == "non_interpretable":
        return "Non-interpretable status from surface-control boundary."
    if status == "failed":
        return "Analysis aborted by integrity or execution gate failure."
    if positive:
        return "Exploratory fixed-primary signal exceeds the frozen R1 thresholds on sealed corpus."
    return "No fixed-primary signal passes all R1 thresholds on sealed corpus."


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_sha256(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    return _sha256(path)


def _canonical_json_sha256(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise A0R1AnalysisError(f"{path.name} must be an object")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise A0R1AnalysisError(f"{path.name} has non-object entry")
        rows.append(row)
    if not rows:
        raise A0R1AnalysisError(f"{path.name} is empty")
    return rows


def _as_float(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise A0R1AnalysisError(f"{field} must be numeric")
    return float(value)


def _write_result(output_path: Path, result: dict[str, Any]) -> dict[str, Any]:
    if output_path.exists():
        raise A0R1AnalysisError(f"refusing to overwrite {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    if temporary.exists():
        raise A0R1AnalysisError(f"temporary result path already exists: {temporary}")
    temporary.write_text(_stable_json(result), encoding="utf-8")
    temporary.replace(output_path)
    return result
