from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


class Lab05Error(RuntimeError):
    """Raised for malformed Lab 05 inputs, never for scientific non-readiness."""


FORBIDDEN_REPRESENTATION_FIELDS = {
    "label",
    "labels",
    "principle",
    "principles",
    "target",
    "target_label",
    "contrast",
    "contrast_label",
}


def run_lab05_analysis(
    cases_path: str | Path,
    representations_path: str | Path,
    config: Mapping[str, Any],
    predecessor_summary: Any | None = None,
) -> dict[str, Any]:
    """Describe contrastive candidate directions without publishing vectors.

    Labels come exclusively from case annotations. Representation records that
    contain label-like fields fail the integrity gate. Scientific insufficiency
    produces a deterministic ``status=fail`` artifact instead of an exception.
    """

    del predecessor_summary  # predecessor qualification belongs to the runner
    cases_file = Path(cases_path)
    representations_file = Path(representations_path)
    cases_raw = _read_jsonl(cases_file, "cases")
    representations_raw = _read_jsonl(representations_file, "representations")
    cfg = _validate_config(config)

    gates = {f"D{index}": True for index in range(1, 9)}
    issues: list[str] = []
    cases, case_integrity = _load_cases(cases_raw)
    representations, representation_integrity = _load_representations(
        representations_raw,
        known_case_ids=set(cases),
    )

    gates["D1"] = bool(cfg.get("predecessor_ready", True))
    if not gates["D1"]:
        issues.append("Lab 04 predecessor is present and integrity-checked but not scientifically ready")
    gates["D2"] = case_integrity and representation_integrity and bool(representations)
    if not case_integrity:
        issues.append("case labels are missing, ambiguous, or malformed")
    if not representation_integrity:
        issues.append("representation integrity or label-separation check failed")

    target_label = cfg["target_label"]
    contrast_label = cfg["contrast_label"]
    minimum_cases = cfg["minimum_cases_per_label"]
    minimum_domains = cfg["minimum_domains_per_label"]
    labels = Counter(row["label"] for row in cases.values())
    domains_by_label: dict[str, set[str]] = defaultdict(set)
    for row in cases.values():
        domains_by_label[row["label"]].add(row["domain"])

    gates["D3"] = labels[target_label] >= minimum_cases and labels[contrast_label] >= minimum_cases
    if not gates["D3"]:
        issues.append("target/contrast case minimum is not met")
    gates["D4"] = (
        len(domains_by_label[target_label]) >= minimum_domains
        and len(domains_by_label[contrast_label]) >= minimum_domains
    )
    if not gates["D4"]:
        issues.append("target/contrast domain minimum is not met")

    layers: list[dict[str, Any]] = []
    directions_valid = bool(representations)
    controls_valid = bool(representations)
    unrelated_valid = bool(representations)
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in representations:
        grouped[record["layer_index"]].append(record)

    for layer_index in sorted(grouped):
        rows = sorted(grouped[layer_index], key=lambda row: row["case_id"])
        target_vectors = [row["vector"] for row in rows if cases[row["case_id"]]["label"] == target_label]
        contrast_vectors = [row["vector"] for row in rows if cases[row["case_id"]]["label"] == contrast_label]
        candidate = _candidate_direction(target_vectors, contrast_vectors)
        if not candidate["available"]:
            directions_valid = False

        random_controls = _random_controls(
            dimension=rows[0]["vector_dim"] if rows else 0,
            candidate_unit=candidate.get("unit"),
            candidate_norm=candidate.get("l2_norm", 0.0),
            seeds=cfg["random_control_seeds"],
            layer_index=layer_index,
            tolerance=cfg["norm_match_tolerance"],
        )
        if not random_controls["available"]:
            controls_valid = False

        unrelated_controls = []
        for unrelated_label in cfg["unrelated_labels"]:
            unrelated_vectors = [
                row["vector"]
                for row in rows
                if cases[row["case_id"]]["label"] == unrelated_label
            ]
            control = _unrelated_control(target_vectors, unrelated_vectors, candidate.get("unit"))
            control["label"] = unrelated_label
            unrelated_controls.append(control)
        if not unrelated_controls or not all(row["available"] for row in unrelated_controls):
            unrelated_valid = False

        layers.append(
            {
                "layer_index": layer_index,
                "case_count": len(rows),
                "candidate_direction": {
                    "available": candidate["available"],
                    "l2_norm": candidate["l2_norm"],
                    "unit_vector_sha256": candidate["unit_vector_sha256"],
                    "target_mean_projection": _mean_projection(target_vectors, candidate.get("unit")),
                    "contrast_mean_projection": _mean_projection(contrast_vectors, candidate.get("unit")),
                },
                "norm_matched_random_controls": random_controls,
                "unrelated_label_controls": unrelated_controls,
            }
        )

    gates["D5"] = directions_valid and bool(layers)
    gates["D6"] = controls_valid and bool(layers)
    gates["D7"] = unrelated_valid and bool(layers)
    gates["D8"] = True
    if not gates["D5"]:
        issues.append("a non-zero candidate direction is unavailable for one or more layers")
    if not gates["D6"]:
        issues.append("norm-matched seeded random controls are unavailable")
    if not gates["D7"]:
        issues.append("one or more unrelated-label controls are unavailable")

    gate_rows = [
        {
            "gate": gate,
            "status": "pass" if passed else "fail",
            "details": _gate_details(gate),
        }
        for gate, passed in gates.items()
    ]
    return {
        "artifact_class": "candidate-direction-instrumentation",
        "empirical": False,
        "evidence_eligible": False,
        "claim_ids": [],
        "status": "pass" if all(gates.values()) else "fail",
        "interpretation": "diagnostic_only_not_scientifically_interpretable",
        "target_label": target_label,
        "contrast_label": contrast_label,
        "unrelated_labels": list(cfg["unrelated_labels"]),
        "seed_policy": list(cfg["random_control_seeds"]),
        "case_summary": {
            "total": len(cases),
            "label_counts": dict(sorted(labels.items())),
            "domains_by_label": {
                label: sorted(domains) for label, domains in sorted(domains_by_label.items())
            },
        },
        "input_hashes": {
            "cases_jsonl": _sha256_path(cases_file),
            "representations_jsonl": _sha256_path(representations_file),
            "config": _sha256_json(dict(config)),
        },
        "gates": gate_rows,
        "issues": sorted(set(issues)),
        "layers": layers,
        "publication_boundary": {
            "dense_vectors_published": False,
            "interventions_executed": False,
            "steering_claim_allowed": False,
            "causal_claim_allowed": False,
        },
    }


def run_lab05(
    cases_path: str | Path,
    representations_path: str | Path,
    *,
    seed: int = 1729,
    target_label: str = "segmentation",
    contrast_label: str = "inversion",
    unrelated_labels: Sequence[str] = ("merging", "universality"),
    min_cases_per_label: int = 6,
    min_domains: int = 4,
    random_control_count: int = 3,
    norm_match_tolerance: float = 1e-12,
    **_: Any,
) -> dict[str, Any]:
    """Compatibility wrapper used by focused unit tests."""

    seeds = [seed + offset for offset in range(max(1, random_control_count))]
    return run_lab05_analysis(
        cases_path,
        representations_path,
        {
            "target_label": target_label,
            "contrast_label": contrast_label,
            "unrelated_labels": list(unrelated_labels),
            "random_control_seeds": seeds,
            "norm_match_tolerance": norm_match_tolerance,
            "minimum_cases_per_label": min_cases_per_label,
            "minimum_domains_per_label": min_domains,
        },
    )


def _validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "target_label",
        "contrast_label",
        "unrelated_labels",
        "random_control_seeds",
        "norm_match_tolerance",
        "minimum_cases_per_label",
        "minimum_domains_per_label",
    )
    missing = [field for field in required if field not in config]
    if missing:
        raise Lab05Error(f"config missing required fields: {', '.join(missing)}")
    target = config["target_label"]
    contrast = config["contrast_label"]
    unrelated = config["unrelated_labels"]
    seeds = config["random_control_seeds"]
    if not isinstance(target, str) or not target or not isinstance(contrast, str) or not contrast:
        raise Lab05Error("target_label and contrast_label must be non-empty strings")
    if target == contrast:
        raise Lab05Error("target_label and contrast_label must differ")
    if not isinstance(unrelated, list) or not unrelated or not all(isinstance(v, str) and v for v in unrelated):
        raise Lab05Error("unrelated_labels must be a non-empty string array")
    if target in unrelated or contrast in unrelated or len(set(unrelated)) != len(unrelated):
        raise Lab05Error("unrelated labels must be unique and distinct from target/contrast")
    if not isinstance(seeds, list) or not seeds or not all(isinstance(v, int) and not isinstance(v, bool) for v in seeds):
        raise Lab05Error("random_control_seeds must be a non-empty integer array")
    tolerance = config["norm_match_tolerance"]
    minimum_cases = config["minimum_cases_per_label"]
    minimum_domains = config["minimum_domains_per_label"]
    if not isinstance(tolerance, (int, float)) or isinstance(tolerance, bool) or tolerance < 0:
        raise Lab05Error("norm_match_tolerance must be non-negative")
    if not isinstance(minimum_cases, int) or minimum_cases < 2:
        raise Lab05Error("minimum_cases_per_label must be at least 2")
    if not isinstance(minimum_domains, int) or minimum_domains < 2:
        raise Lab05Error("minimum_domains_per_label must be at least 2")
    return dict(config)


def _read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    if not path.is_file():
        raise Lab05Error(f"{label} file not found")
    records = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise Lab05Error(f"{label} line {line_number}: invalid JSON") from exc
        if not isinstance(record, dict):
            raise Lab05Error(f"{label} line {line_number}: expected object")
        records.append(record)
    return records


def _load_cases(records: Sequence[dict[str, Any]]) -> tuple[dict[str, dict[str, str]], bool]:
    output: dict[str, dict[str, str]] = {}
    valid = bool(records)
    for record in records:
        case_id = record.get("case_id")
        domain = record.get("domain")
        labels = record.get("labels")
        principles = []
        if isinstance(labels, list):
            principles = sorted(
                {
                    row.get("principle")
                    for row in labels
                    if isinstance(row, dict) and isinstance(row.get("principle"), str) and row.get("principle")
                }
            )
        if (
            not isinstance(case_id, str)
            or not case_id
            or case_id in output
            or not isinstance(domain, str)
            or not domain
            or len(principles) != 1
        ):
            valid = False
            continue
        output[case_id] = {"domain": domain, "label": principles[0]}
    return output, valid and len(output) == len(records)


def _load_representations(
    records: Sequence[dict[str, Any]],
    *,
    known_case_ids: set[str],
) -> tuple[list[dict[str, Any]], bool]:
    output = []
    valid = bool(records)
    dimensions: dict[int, int] = {}
    seen: set[tuple[str, int]] = set()
    for record in records:
        if FORBIDDEN_REPRESENTATION_FIELDS.intersection(record):
            valid = False
            continue
        case_id = record.get("case_id")
        layer = record.get("layer_index", record.get("layer"))
        vector = record.get("vector")
        if (
            not isinstance(case_id, str)
            or case_id not in known_case_ids
            or not isinstance(layer, int)
            or isinstance(layer, bool)
            or layer < 0
            or not isinstance(vector, list)
            or not vector
            or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in vector)
            or (case_id, layer) in seen
        ):
            valid = False
            continue
        declared_dim = record.get("vector_dim")
        if declared_dim != len(vector) or (layer in dimensions and dimensions[layer] != len(vector)):
            valid = False
            continue
        dimensions[layer] = len(vector)
        seen.add((case_id, layer))
        output.append(
            {
                "case_id": case_id,
                "layer_index": layer,
                "vector_dim": len(vector),
                "vector": tuple(float(v) for v in vector),
            }
        )
    return output, valid and len(output) == len(records)


def _candidate_direction(target: Sequence[Sequence[float]], contrast: Sequence[Sequence[float]]) -> dict[str, Any]:
    if not target or not contrast:
        return {"available": False, "l2_norm": 0.0, "unit_vector_sha256": "", "unit": None}
    direction = tuple(a - b for a, b in zip(_mean_vector(target), _mean_vector(contrast), strict=True))
    norm = _norm(direction)
    if norm == 0:
        return {"available": False, "l2_norm": 0.0, "unit_vector_sha256": "", "unit": None}
    unit = tuple(value / norm for value in direction)
    return {
        "available": True,
        "l2_norm": norm,
        "unit_vector_sha256": _sha256_json([round(value, 15) for value in unit]),
        "unit": unit,
    }


def _random_controls(
    *,
    dimension: int,
    candidate_unit: Sequence[float] | None,
    candidate_norm: float,
    seeds: Sequence[int],
    layer_index: int,
    tolerance: float,
) -> dict[str, Any]:
    if dimension < 1 or candidate_unit is None or candidate_norm <= 0:
        return {"available": False, "norm_match_tolerance": tolerance, "controls": []}
    controls = []
    for seed in seeds:
        rng = random.Random((seed * 1_000_003) + layer_index)
        raw = [rng.gauss(0.0, 1.0) for _ in range(dimension)]
        raw_norm = _norm(raw)
        unit = tuple(value / raw_norm for value in raw)
        scaled = tuple(value * candidate_norm for value in unit)
        delta = abs(_norm(scaled) - candidate_norm)
        controls.append(
            {
                "seed": seed,
                "vector_sha256": _sha256_json([round(value, 15) for value in scaled]),
                "l2_norm": _norm(scaled),
                "norm_delta": delta,
                "cosine_to_candidate": _cosine(unit, candidate_unit),
            }
        )
    return {
        "available": all(row["norm_delta"] <= tolerance for row in controls),
        "norm_match_tolerance": tolerance,
        "controls": controls,
    }


def _unrelated_control(
    target: Sequence[Sequence[float]],
    unrelated: Sequence[Sequence[float]],
    candidate_unit: Sequence[float] | None,
) -> dict[str, Any]:
    if not target or not unrelated or candidate_unit is None:
        return {"available": False, "unit_vector_sha256": "", "cosine_to_candidate": None}
    direction = tuple(a - b for a, b in zip(_mean_vector(target), _mean_vector(unrelated), strict=True))
    norm = _norm(direction)
    if norm == 0:
        return {"available": False, "unit_vector_sha256": "", "cosine_to_candidate": None}
    unit = tuple(value / norm for value in direction)
    return {
        "available": True,
        "unit_vector_sha256": _sha256_json([round(value, 15) for value in unit]),
        "cosine_to_candidate": _cosine(unit, candidate_unit),
    }


def _mean_vector(vectors: Sequence[Sequence[float]]) -> tuple[float, ...]:
    return tuple(sum(values) / len(vectors) for values in zip(*vectors, strict=True))


def _mean_projection(vectors: Sequence[Sequence[float]], unit: Sequence[float] | None) -> float | None:
    if not vectors or unit is None:
        return None
    return sum(sum(a * b for a, b in zip(vector, unit, strict=True)) for vector in vectors) / len(vectors)


def _norm(vector: Sequence[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def _cosine(first: Sequence[float], second: Sequence[float]) -> float:
    denominator = _norm(first) * _norm(second)
    return 0.0 if denominator == 0 else sum(a * b for a, b in zip(first, second, strict=True)) / denominator


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _gate_details(gate: str) -> str:
    return {
        "D1": "Lab 04 predecessor integrity and scientific readiness pass",
        "D2": "case/representation integrity and label separation hold",
        "D3": "target and contrast meet the case minimum",
        "D4": "target and contrast meet the domain minimum",
        "D5": "non-zero candidate directions are available",
        "D6": "seeded random controls are norm-matched",
        "D7": "unrelated-label controls are available",
        "D8": "no dense vectors, interventions, or causal claims are published",
    }[gate]
