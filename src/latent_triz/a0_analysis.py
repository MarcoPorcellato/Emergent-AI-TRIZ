"""Frozen family-safe statistical analysis for A0 activation vectors."""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


class A0AnalysisError(RuntimeError):
    """Raised when the sealed A0 statistic cannot be computed safely."""


EPISTEMIC = {
    "empirical": True,
    "scientific_status": "exploratory",
    "evidence_eligible": False,
    "expert_validated": False,
    "claim_ids": [],
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise A0AnalysisError(f"{path.name} must contain an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise A0AnalysisError(f"{path.name} must contain object records")
    return rows


def _macro_f1(labels: Sequence[int], predictions: Sequence[int]) -> float:
    scores: list[float] = []
    for value in (0, 1):
        tp = sum(int(y == value and p == value) for y, p in zip(labels, predictions))
        fp = sum(int(y != value and p == value) for y, p in zip(labels, predictions))
        fn = sum(int(y == value and p != value) for y, p in zip(labels, predictions))
        denominator = 2 * tp + fp + fn
        scores.append(0.0 if denominator == 0 else (2.0 * tp) / denominator)
    return math.fsum(scores) / 2.0


def _wilson(successes: int, total: int) -> list[float]:
    if total <= 0:
        raise A0AnalysisError("Wilson interval requires observations")
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    radius = (
        z
        * math.sqrt(proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total))
        / denominator
    )
    return [max(0.0, center - radius), min(1.0, center + radius)]


def _score_operator(
    matrix: Any,
    domains: Sequence[str],
    *,
    alpha: float,
) -> Any:
    import numpy as np

    matrix = np.asarray(matrix, dtype=np.float64)
    count = matrix.shape[0]
    operator = np.zeros((count, count), dtype=np.float64)
    for held_domain in sorted(set(domains)):
        train = np.asarray([index for index, domain in enumerate(domains) if domain != held_domain])
        test = np.asarray([index for index, domain in enumerate(domains) if domain == held_domain])
        if not len(train) or not len(test):
            raise A0AnalysisError("leave-one-domain-out split is empty")
        mean = matrix[train].mean(axis=0)
        std = matrix[train].std(axis=0)
        std[std < 1e-12] = 1.0
        train_x = (matrix[train] - mean) / std
        test_x = (matrix[test] - mean) / std
        kernel = train_x @ train_x.T
        solved = np.linalg.solve(kernel + alpha * np.eye(len(train)), np.eye(len(train)))
        operator[np.ix_(test, train)] = test_x @ train_x.T @ solved
    return operator


def _family_successes(
    scores: Sequence[float],
    labels: Sequence[int],
    families: Sequence[str],
) -> tuple[int, dict[str, bool]]:
    members: dict[str, list[int]] = defaultdict(list)
    for index, family in enumerate(families):
        members[family].append(index)
    outcomes: dict[str, bool] = {}
    for family, indices in sorted(members.items()):
        if len(indices) != 2 or sorted(labels[index] for index in indices) != [0, 1]:
            raise A0AnalysisError(f"family {family} is not a balanced pair")
        positive = next(index for index in indices if labels[index] == 1)
        negative = next(index for index in indices if labels[index] == 0)
        outcomes[family] = float(scores[positive]) > float(scores[negative])
    return sum(outcomes.values()), outcomes


def _combo_metrics(
    operator: Any,
    labels: Sequence[int],
    families: Sequence[str],
    domains: Sequence[str],
) -> dict[str, Any]:
    import numpy as np

    signed = np.asarray([1.0 if value == 1 else -1.0 for value in labels])
    scores = operator @ signed
    predictions = [int(value >= 0.0) for value in scores]
    successes, family_outcomes = _family_successes(scores, labels, families)
    per_domain = {}
    for domain in sorted(set(domains)):
        indices = [index for index, value in enumerate(domains) if value == domain]
        per_domain[domain] = sum(predictions[index] == labels[index] for index in indices) / len(indices)
    return {
        "family_successes": successes,
        "family_success_rate": successes / len(family_outcomes),
        "family_success_wilson_95": _wilson(successes, len(family_outcomes)),
        "macro_f1": _macro_f1(labels, predictions),
        "accuracy": sum(p == y for p, y in zip(predictions, labels)) / len(labels),
        "per_domain_accuracy": per_domain,
    }


def analyze_a0(
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
    protocol_path = Path(protocol_path).resolve()
    implementation_path = Path(implementation_path).resolve()
    shortcut_path = Path(shortcut_path).resolve()
    activation_receipt_path = Path(activation_receipt_path).resolve()
    activation_index_path = Path(activation_index_path).resolve()
    dense_path = Path(dense_path).resolve()
    targets_path = Path(targets_path).resolve()
    output_path = Path(output_path).resolve()
    if output_path.exists():
        raise A0AnalysisError(f"refusing to overwrite {output_path}")

    protocol = _read_json(protocol_path)
    implementation = _read_json(implementation_path)
    shortcuts = _read_json(shortcut_path)
    receipt = _read_json(activation_receipt_path)
    for label, payload in (
        ("protocol", protocol),
        ("implementation", implementation["epistemic_boundary"]),
        ("activation receipt", receipt),
    ):
        for key, expected in EPISTEMIC.items():
            if payload.get(key) != expected:
                raise A0AnalysisError(f"{label} has invalid epistemic field {key}")
    if shortcuts.get("status") != "pass":
        raise A0AnalysisError("shortcut gate is not pass")
    if receipt.get("status") != "pass" or not receipt["corpus"].get("sealed_targets_accessed"):
        raise A0AnalysisError("activation receipt is not a valid sealed pass")
    if receipt["protocol"]["sha256"] != _sha256(protocol_path):
        raise A0AnalysisError("protocol receipt mismatch")
    if receipt["protocol"]["implementation_sha256"] != _sha256(implementation_path):
        raise A0AnalysisError("implementation receipt mismatch")
    if receipt["dense_vectors"]["sha256"] != _sha256(dense_path):
        raise A0AnalysisError("dense activation receipt mismatch")
    if receipt["representation_index"]["sha256"] != _sha256(activation_index_path):
        raise A0AnalysisError("representation index receipt mismatch")
    if receipt["corpus"]["sealed_targets_sha256"] != _sha256(targets_path):
        raise A0AnalysisError("sealed target receipt mismatch")

    index_rows = _read_jsonl(activation_index_path)
    targets = {str(row["case_id"]): row for row in _read_jsonl(targets_path)}
    case_ids = sorted({str(row["case_id"]) for row in index_rows})
    if len(case_ids) != int(receipt["corpus"]["selected_cases"]):
        raise A0AnalysisError("activation index case count mismatch")
    labels = [
        1 if targets[case_id]["operator_proxy_family"] == "segmentation_like" else 0
        for case_id in case_ids
    ]
    families = [str(targets[case_id]["problem_family_id"]) for case_id in case_ids]
    domains = [family.rsplit("_", 1)[0] for family in families]

    from safetensors import safe_open
    import numpy as np

    rows_by_combo: dict[tuple[str, int, str], dict[str, str]] = defaultdict(dict)
    for row in index_rows:
        combo = (str(row["view"]), int(row["layer"]), str(row["token_site"]))
        case_id = str(row["case_id"])
        if case_id in rows_by_combo[combo]:
            raise A0AnalysisError("duplicate representation record")
        rows_by_combo[combo][case_id] = str(row["tensor_key"])

    operators: dict[tuple[str, int, str], Any] = {}
    with safe_open(dense_path, framework="np", device="cpu") as handle:
        for combo, case_map in sorted(rows_by_combo.items()):
            if set(case_map) != set(case_ids):
                raise A0AnalysisError(f"incomplete representation combo {combo}")
            matrix = np.stack([handle.get_tensor(case_map[case_id]) for case_id in case_ids])
            operators[combo] = _score_operator(
                matrix,
                domains,
                alpha=float(implementation["classifier"]["alpha"]),
            )

    layers = [int(value) for value in protocol["preregistered_layers"]]
    sites = [str(value) for value in protocol["token_sites"]]
    primary_view = str(implementation["primary_view"])
    primary_combos = [(primary_view, layer, site) for layer in layers for site in sites]
    if any(combo not in operators for combo in primary_combos):
        raise A0AnalysisError("one or more preregistered primary combinations are missing")
    primary = {
        f"layer_{layer:02d}::{site}": _combo_metrics(operators[(primary_view, layer, site)], labels, families, domains)
        for _, layer, site in primary_combos
    }
    observed_max = max(value["family_successes"] for value in primary.values())
    best_keys = sorted(key for key, value in primary.items() if value["family_successes"] == observed_max)

    surface_view = str(implementation["surface_baseline_view"])
    surface = {
        f"layer_{layer:02d}::sentinel": _combo_metrics(
            operators[(surface_view, layer, "sentinel")],
            labels,
            families,
            domains,
        )
        for layer in layers
    }
    primary_macro_f1 = max(value["macro_f1"] for value in primary.values())
    surface_macro_f1 = max(value["macro_f1"] for value in surface.values())
    surface_margin = primary_macro_f1 - surface_macro_f1

    family_members: dict[str, list[int]] = defaultdict(list)
    for index, family in enumerate(families):
        family_members[family].append(index)
    rng = random.Random(int(implementation["permutations"]["seed"]))
    budget = int(implementation["permutations"]["budget"])
    null_maxima: list[int] = []
    seen_masks: set[int] = set()
    while len(null_maxima) < budget:
        mask = rng.getrandbits(len(family_members))
        if mask in seen_masks:
            continue
        seen_masks.add(mask)
        permuted = list(labels)
        for bit, indices in enumerate(family_members.values()):
            if mask & (1 << bit):
                permuted[indices[0]], permuted[indices[1]] = permuted[indices[1]], permuted[indices[0]]
        null_maxima.append(
            max(
                _family_successes(
                    operators[combo] @ np.asarray([1.0 if value else -1.0 for value in permuted]),
                    permuted,
                    families,
                )[0]
                for combo in primary_combos
            )
        )
    max_statistic_p = (1 + sum(value >= observed_max for value in null_maxima)) / (budget + 1)

    sensitivity: dict[str, Any] = {}
    for view in implementation["sensitivity_views"]:
        available = {
            f"layer_{layer:02d}::{site}": _combo_metrics(
                operators[(view, layer, site)],
                labels,
                families,
                domains,
            )
            for layer in layers
            for site in sites
        }
        sensitivity[view] = {
            "max_family_successes": max(value["family_successes"] for value in available.values()),
            "macro_f1_range": [
                min(value["macro_f1"] for value in available.values()),
                max(value["macro_f1"] for value in available.values()),
            ],
        }

    frozen = protocol["frozen_analysis"]
    positive = (
        max_statistic_p <= 0.05
        and surface_margin >= 0.10
        and observed_max >= int(frozen["critical_successes"])
    )
    result = {
        "artifact_class": "a0-sealed-statistical-result",
        **EPISTEMIC,
        "status": "positive" if positive else "null",
        "protocol_id": protocol["protocol_id"],
        "input_hashes": {
            "protocol": _sha256(protocol_path),
            "implementation": _sha256(implementation_path),
            "shortcuts": _sha256(shortcut_path),
            "activation_receipt": _sha256(activation_receipt_path),
            "representation_index": _sha256(activation_index_path),
            "dense_vectors": _sha256(dense_path),
            "sealed_targets": _sha256(targets_path),
        },
        "design": {
            "cases": len(case_ids),
            "families": len(family_members),
            "domains": len(set(domains)),
            "layers": layers,
            "token_sites": sites,
            "primary_view": primary_view,
            "surface_baseline_view": surface_view,
            "permutation_budget": budget,
            "critical_successes": int(frozen["critical_successes"]),
        },
        "primary": primary,
        "observed_max_family_successes": observed_max,
        "maximizing_combinations": best_keys,
        "max_statistic_p": max_statistic_p,
        "null_maxima": {
            "minimum": min(null_maxima),
            "median": sorted(null_maxima)[len(null_maxima) // 2],
            "maximum": max(null_maxima),
            "sha256": hashlib.sha256(
                json.dumps(null_maxima, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        },
        "surface_baseline": surface,
        "maximum_primary_macro_f1": primary_macro_f1,
        "maximum_surface_macro_f1": surface_macro_f1,
        "macro_f1_margin_over_surface": surface_margin,
        "sensitivity": sensitivity,
        "outcome_rule": {
            "max_statistic_p_at_most": 0.05,
            "macro_f1_margin_at_least": 0.10,
            "family_successes_at_least": int(frozen["critical_successes"]),
            "passed": positive,
        },
        "interpretation": (
            "Exploratory decodable signal for the frozen automated operator proxies only."
            if positive
            else "No positive signal under the frozen A0 implementation; this does not falsify the broader hypothesis."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_stable_json(result), encoding="utf-8")
    return result
