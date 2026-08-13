from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from random import Random
from typing import Any, Mapping


class Lab04Error(RuntimeError):
    pass


_ALPHA_GRID = (0.01, 0.1, 1.0, 10.0)
_DEFAULT_SEED = 1729
_DEFAULT_PERMUTATIONS = 100


def stable_json_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _read_json(path: Path, label: str) -> Mapping[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise Lab04Error(f"{label} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise Lab04Error(f"invalid JSON in {label}: {path}: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise Lab04Error(f"{label} must be an object")
    return raw


def _read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise Lab04Error(f"{label} file not found: {path}") from exc
    except OSError as exc:
        raise Lab04Error(f"cannot read {label}: {path}: {exc}") from exc

    records: list[dict[str, Any]] = []
    for index, line in enumerate(raw_lines, start=1):
        text = line.strip()
        if not text:
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise Lab04Error(f"invalid JSONL in {label} line {index}: {exc}") from exc
        if not isinstance(value, Mapping):
            raise Lab04Error(f"{label} line {index} must be an object")
        records.append(dict(value))
    if not records:
        raise Lab04Error(f"{label} is empty")
    return records


def _sha256_text(text: str) -> str:
    hasher = hashlib.sha256()
    hasher.update(text.encode("utf-8"))
    return hasher.hexdigest()


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _coerce_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed < 0:
        return default
    return parsed


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_float_vector(raw: Any, *, label: str) -> list[float]:
    if not isinstance(raw, (list, tuple)):
        raise Lab04Error(f"{label} vector must be a list")
    values: list[float] = []
    for item in raw:
        try:
            value = float(item)
        except (TypeError, ValueError):
            raise Lab04Error(f"{label} vector contains non-numeric value")
        if not math.isfinite(value):
            raise Lab04Error(f"{label} vector contains non-finite value")
        values.append(value)
    if not values:
        raise Lab04Error(f"{label} vector is empty")
    return values


def _parse_layer(raw: Any) -> int:
    if isinstance(raw, int):
        if raw < 0:
            raise Lab04Error("layer must be non-negative")
        return raw
    if not isinstance(raw, str):
        raise Lab04Error("layer must be numeric")
    match = re.fullmatch(r"resid_post_layer_(\d+)", raw.strip())
    if match is not None:
        return int(match.group(1))
    try:
        return int(raw)
    except ValueError as exc:
        raise Lab04Error("layer must be numeric") from exc


def _majority_label(labels: list[str]) -> str:
    if not labels:
        raise Lab04Error("majority label requires at least one label")
    counts: dict[str, int] = {}
    for item in labels:
        counts[item] = counts.get(item, 0) + 1
    best_count = max(counts.values())
    winners = sorted(name for name, count in counts.items() if count == best_count)
    return winners[0]


def _collect_cases(
    raw_cases: list[dict[str, Any]],
    minimum_labels: int,
) -> tuple[dict[str, str], dict[str, str], list[str]]:
    case_label: dict[str, str] = {}
    case_domain: dict[str, str] = {}
    seen_case_ids: set[str] = set()
    issues: list[str] = []

    for idx, case in enumerate(raw_cases, start=1):
        case_id = str(case.get("case_id", "")).strip()
        if not case_id:
            issues.append(f"case line {idx} missing case_id")
            continue
        if case_id in seen_case_ids:
            issues.append(f"duplicate case_id {case_id!r}")
            continue
        seen_case_ids.add(case_id)

        domain = str(case.get("domain", "")).strip()
        if not domain:
            issues.append(f"case {case_id} missing domain")
            continue

        raw_labels = case.get("labels")
        canonical: str | None = None
        if isinstance(raw_labels, list) and raw_labels:
            candidates = [
                str(item.get("principle")).strip()
                for item in raw_labels
                if isinstance(item, Mapping)
                and isinstance(item.get("principle"), str)
                and str(item.get("principle")).strip()
            ]
            if candidates:
                canonical_set = sorted(set(candidates))
                if len(canonical_set) == 1:
                    canonical = canonical_set[0]
                else:
                    issues.append(f"case {case_id} has non-unanimous labels: {canonical_set!r}")
        if not canonical:
            if not issues or not issues[-1].startswith(f"case {case_id}"):
                issues.append(f"case {case_id} has no usable label")
            continue

        case_label[case_id] = canonical
        case_domain[case_id] = domain

    if not case_label:
        raise Lab04Error("no usable cases with unanimous labels")
    if len(set(case_label.values())) < minimum_labels:
        issues.append(
            f"only {len(set(case_label.values()))} labels available; minimum_labels is {minimum_labels}"
        )
    return case_label, case_domain, issues


def _collect_representations(
    raw_representations: list[dict[str, Any]],
    case_label: Mapping[str, str],
) -> tuple[dict[int, dict[str, list[float]]], list[str]]:
    layers: dict[int, dict[str, list[float]]] = {}
    issues: list[str] = []
    seen_pairs: set[tuple[int, str]] = set()
    case_ids = set(case_label)

    for index, item in enumerate(raw_representations, start=1):
        case_id = str(item.get("case_id", "")).strip()
        if not case_id:
            issues.append(f"representation line {index} missing case_id")
            continue
        if case_id not in case_ids:
            issues.append(f"representation line {index} unknown case_id={case_id}")
            continue

        if "label" in item:
            issues.append(f"representation line {index} contains forbidden label field for case {case_id}")
            continue
        layer = _parse_layer(item.get("layer_index"))
        pair = (layer, case_id)
        if pair in seen_pairs:
            issues.append(f"duplicate representation for case {case_id} at layer {layer}")
            continue
        seen_pairs.add(pair)

        provenance = item.get("provenance")
        if not isinstance(provenance, Mapping):
            issues.append(f"representation line {index} missing provenance for case {case_id}")
            continue
        boundary = item.get("non_claim_boundary")
        if (
            not isinstance(boundary, Mapping)
            or not isinstance(boundary.get("empirical"), bool)
            or boundary.get("evidence_eligible") is not False
            or boundary.get("claim_ids") != []
        ):
            issues.append(f"representation line {index} violates the non-claim boundary for case {case_id}")
            continue

        key = str(layer)
        if "vector" not in item:
            issues.append(f"representation line {index} has no vector field")
            continue
        vector = _to_float_vector(item["vector"], label=f"case {case_id} layer {key}")
        if item.get("vector_dim") != len(vector):
            issues.append(f"representation line {index} vector_dim mismatch for case {case_id}")
            continue

        layers.setdefault(layer, {})[case_id] = vector

    if not layers:
        raise Lab04Error("no valid representation records")

    for layer, mapping in layers.items():
        if set(mapping) != case_ids:
            missing = sorted(case_ids - set(mapping))
            extra = sorted(set(mapping) - case_ids)
            if missing:
                issues.append(f"layer {layer} missing cases {missing!r}")
            if extra:
                issues.append(f"layer {layer} has unknown cases {extra!r}")
        dims = {len(vec) for vec in mapping.values() if vec}
        if len(dims) != 1:
            issues.append(f"layer {layer} has non-uniform vector dimensions {sorted(dims)!r}")
    return layers, issues


def _mean_std(vectors: list[list[float]]) -> tuple[list[float], list[float]]:
    if not vectors:
        raise Lab04Error("empty train matrix")
    dim = len(vectors[0])
    if any(len(v) != dim for v in vectors):
        raise Lab04Error("inconsistent vector dimensions")
    mean = [0.0] * dim
    for row in vectors:
        for idx, value in enumerate(row):
            mean[idx] += value
    mean = [value / len(vectors) for value in mean]
    m2 = [0.0] * dim
    for row in vectors:
        for idx, value in enumerate(row):
            d = value - mean[idx]
            m2[idx] += d * d
    std = [math.sqrt(v / len(vectors)) for v in m2]
    return mean, [v if v != 0.0 else 1.0 for v in std]


def _standardize(vectors: list[list[float]], mean: list[float], std: list[float]) -> list[list[float]]:
    out: list[list[float]] = []
    for row in vectors:
        out.append([(row[i] - mean[i]) / std[i] for i in range(len(row))])
    return out


def _mat_vec_mul(a: list[list[float]], b: list[float]) -> list[float]:
    out = []
    for row in a:
        total = 0.0
        for idx, value in enumerate(row):
            total += value * b[idx]
        out.append(total)
    return out


def _gram_matrix(vectors: list[list[float]]) -> list[list[float]]:
    xt = [list(row) for row in zip(*vectors)]
    rows = len(vectors[0]) if vectors else 0
    gram = [[0.0 for _ in range(rows)] for _ in range(rows)]
    for i in range(rows):
        for j in range(rows):
            total = 0.0
            for row in vectors:
                total += row[i] * row[j]
            gram[i][j] = total
    return gram


def _mat_mul(xt: list[list[float]], y: list[float]) -> list[float]:
    out = [0.0] * len(xt)
    for i, row in enumerate(xt):
        total = 0.0
        for idx, value in enumerate(row):
            total += value * y[idx]
        out[i] = total
    return out


def _solve_linear_system(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(a)
    if n == 0:
        return []
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = col
        pivot_abs = abs(m[pivot][col])
        for row in range(col + 1, n):
            value = abs(m[row][col])
            if value > pivot_abs:
                pivot = row
                pivot_abs = value
        if pivot_abs < 1e-15:
            return [0.0] * n
        if pivot != col:
            m[col], m[pivot] = m[pivot], m[col]
        pivot_value = m[col][col]
        for j in range(col, n + 1):
            m[col][j] /= pivot_value
        for row in range(n):
            if row == col:
                continue
            factor = m[row][col]
            if factor == 0.0:
                continue
            for j in range(col, n + 1):
                m[row][j] -= factor * m[col][j]
    return [m[i][n] for i in range(n)]


def _ridge_weights(vectors: list[list[float]], y: list[float], alpha: float) -> list[float]:
    X = [row + [1.0] for row in vectors]
    xt = [list(row) for row in zip(*X)]
    gram = _gram_matrix(X)
    xTy = _mat_mul(xt, y)
    for i in range(len(gram) - 1):
        gram[i][i] += alpha
    return _solve_linear_system(gram, xTy)


def _fit_one_vs_rest(
    examples: list[tuple[str, str, list[float]]],
    labels: list[str],
    alpha: float,
    mean: list[float],
    std: list[float],
) -> dict[str, list[float]]:
    vectors = [row for _, __, row in examples]
    x = _standardize(vectors, mean, std)
    models: dict[str, list[float]] = {}
    for label in labels:
        y = [1.0 if y_label == label else -1.0 for _, y_label, _ in examples]
        models[label] = _ridge_weights(x, y, alpha)
    return models


def _predict_one_vs_rest(models: dict[str, list[float]], vectors: list[list[float]], mean: list[float], std: list[float]) -> list[str]:
    if not models:
        return []
    labels = sorted(models)
    x = _standardize(vectors, mean, std)
    preds: list[str] = []
    for row in x:
        scores = {}
        for label in labels:
            model = models[label]
            scores[label] = sum(item * row[idx] for idx, item in enumerate(model[:-1])) + model[-1]
        best = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[0][0]
        preds.append(best)
    return preds


def _macro_and_balanced(y_true: list[str], y_pred: list[str], labels: list[str]) -> tuple[dict[str, float], float]:
    total = len(y_true)
    if total == 0:
        return ({"accuracy": 0.0, "macro_f1": 0.0, "balanced_accuracy": 0.0}, 0.0)
    correct = sum(1 for a, b in zip(y_true, y_pred) if a == b)
    accuracy = correct / total

    macro_f1 = 0.0
    balanced = 0.0
    for label in labels:
        tp = sum(1 for a, b in zip(y_true, y_pred) if a == label and b == label)
        fp = sum(1 for a, b in zip(y_true, y_pred) if a != label and b == label)
        fn = sum(1 for a, b in zip(y_true, y_pred) if a == label and b != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        macro_f1 += f1
        balanced += recall
    macro_f1 /= len(labels)
    balanced /= len(labels)
    return {"accuracy": accuracy, "macro_f1": macro_f1, "balanced_accuracy": balanced}, balanced


@dataclass
class FoldResult:
    domain: str
    train_count: int
    test_count: int
    metrics: dict[str, float]
    predictions: list[str]
    selected_alpha: float
    inner_alpha_scores: dict[float, float]
    majority_margin: float
    permutation_p: float
    train_case_ids: list[str] = field(default_factory=list)
    test_case_ids: list[str] = field(default_factory=list)
    train_domains: list[str] = field(default_factory=list)
    test_domains: list[str] = field(default_factory=list)
    scaler_receipt: dict[str, Any] = field(default_factory=dict)
    inner_split_receipts: list[dict[str, Any]] = field(default_factory=list)
    permutation_receipt: dict[str, Any] = field(default_factory=dict)
    permutation_null_scores: list[float] = field(default_factory=list)
    status: str = "pass"
    details: str = ""


def _inner_alpha_search(
    outer_train: list[tuple[str, str, list[float]]],
    labels: list[str],
    domain_by_case: dict[str, str],
) -> tuple[float | None, dict[float, float], list[str], list[dict[str, Any]]]:
    by_domain: dict[str, list[tuple[str, str, list[float]]]] = {}
    for item in outer_train:
        by_domain.setdefault(domain_by_case[item[0]], []).append(item)

    if len(by_domain) < 2:
        return None, {}, ["insufficient domains for inner CV"], []

    scores: dict[float, list[float]] = {alpha: [] for alpha in _ALPHA_GRID}
    errors: list[str] = []
    receipts: list[dict[str, Any]] = []
    for hold_domain in sorted(by_domain):
        hold_rows = by_domain[hold_domain]
        inner_train = [
            item
            for name in sorted(by_domain)
            if name != hold_domain
            for item in by_domain[name]
        ]
        inner_test = hold_rows
        train_ids = sorted(item[0] for item in inner_train)
        validation_ids = sorted(item[0] for item in inner_test)
        receipt: dict[str, Any] = {
            "validation_domain": hold_domain,
            "train_domains": sorted(name for name in by_domain if name != hold_domain),
            "validation_domains": [hold_domain],
            "train_case_ids": train_ids,
            "validation_case_ids": validation_ids,
            "overlap_case_ids": sorted(set(train_ids) & set(validation_ids)),
            "status": "pass",
        }
        if not inner_train or not inner_test:
            receipt["status"] = "fail"
            errors.append(f"inner fold for domain {hold_domain} has empty train or test")
            receipts.append(receipt)
            continue
        inner_train_labels = [label for _, label, _ in inner_train]
        inner_test_labels = [label for _, label, _ in inner_test]
        if len(set(inner_train_labels)) < len(labels) or len(set(inner_test_labels)) < len(labels):
            receipt["status"] = "fail"
            errors.append(f"inner fold for domain {hold_domain} lacks full labels")
            receipts.append(receipt)
            continue
        inner_vectors = [vector for _, __, vector in inner_train]
        mean, std = _mean_std(inner_vectors)
        receipt["scaler_fit_case_ids"] = train_ids
        receipt["scaler_sha256"] = _sha256_text(
            stable_json_dumps({"mean": mean, "std": std, "fit_case_ids": train_ids})
        )
        for alpha in _ALPHA_GRID:
            models = _fit_one_vs_rest(inner_train, labels, alpha, mean, std)
            preds = _predict_one_vs_rest(
                models, [vector for _, __, vector in inner_test], mean, std
            )
            metrics, _ = _macro_and_balanced(inner_test_labels, preds, labels)
            scores[alpha].append(metrics["macro_f1"])
        receipts.append(receipt)

    if not scores or all(len(v) == 0 for v in scores.values()):
        return None, {}, ["inner alpha search found no valid folds"] + errors, receipts

    mean_scores = {
        alpha: (sum(vals) / len(vals) if vals else 0.0)
        for alpha, vals in scores.items()
    }
    best = min(_ALPHA_GRID, key=lambda alpha: (-mean_scores[alpha], alpha))
    return best, mean_scores, errors, receipts


def _run_outer_fold(
    held_domain: str,
    by_domain: dict[str, list[tuple[str, str, list[float]]]],
    labels: list[str],
    permutations: int,
    seed: int,
    alpha_cache: dict[str, float],
) -> FoldResult:
    train = [
        item
        for domain in sorted(by_domain)
        if domain != held_domain
        for item in by_domain[domain]
    ]
    test = list(by_domain.get(held_domain, []))
    train_labels = [label for _, label, _ in train]
    test_labels = [label for _, label, _ in test]
    train_ids = sorted(case_id for case_id, _, _ in train)
    test_ids = sorted(case_id for case_id, _, _ in test)
    train_domains = sorted(domain for domain in by_domain if domain != held_domain)
    common_receipt = {
        "train_case_ids": train_ids,
        "test_case_ids": test_ids,
        "train_domains": train_domains,
        "test_domains": [held_domain],
    }

    if not test or len(set(train_labels)) < len(labels) or len(set(test_labels)) < len(labels):
        details = "empty outer test split" if not test else "outer split lacks full label support"
        return FoldResult(
            domain=held_domain,
            train_count=len(train),
            test_count=len(test),
            metrics={"accuracy": 0.0, "macro_f1": 0.0, "balanced_accuracy": 0.0},
            predictions=[],
            selected_alpha=0.0,
            inner_alpha_scores={},
            majority_margin=0.0,
            permutation_p=1.0,
            train_case_ids=train_ids,
            test_case_ids=test_ids,
            train_domains=train_domains,
            test_domains=[held_domain],
            status="fail",
            details=details,
        )

    domain_lookup = {
        case_id: domain
        for domain, rows in by_domain.items()
        for case_id, _, _ in rows
    }
    selected_alpha, alpha_scores, errors, inner_receipts = _inner_alpha_search(
        train, labels, domain_lookup
    )
    if selected_alpha is None:
        return FoldResult(
            domain=held_domain,
            train_count=len(train),
            test_count=len(test),
            metrics={"accuracy": 0.0, "macro_f1": 0.0, "balanced_accuracy": 0.0},
            predictions=[],
            selected_alpha=0.0,
            inner_alpha_scores=alpha_scores,
            majority_margin=0.0,
            permutation_p=1.0,
            train_case_ids=train_ids,
            test_case_ids=test_ids,
            train_domains=train_domains,
            test_domains=[held_domain],
            inner_split_receipts=inner_receipts,
            status="fail",
            details="; ".join(errors),
        )

    alpha_cache[held_domain] = selected_alpha
    train_vectors = [vector for _, _, vector in train]
    test_vectors = [vector for _, _, vector in test]
    mean, std = _mean_std(train_vectors)
    scaler_receipt = {
        "fit_scope": "outer_train_only",
        "fit_case_ids": train_ids,
        "excluded_case_ids": test_ids,
        "sha256": _sha256_text(
            stable_json_dumps({"mean": mean, "std": std, "fit_case_ids": train_ids})
        ),
    }
    models = _fit_one_vs_rest(train, labels, selected_alpha, mean, std)
    pred = _predict_one_vs_rest(models, test_vectors, mean, std)
    observed, _ = _macro_and_balanced(test_labels, pred, labels)

    majority = _majority_label(train_labels)
    baseline_pred = [majority] * len(test_labels)
    baseline_metrics, _ = _macro_and_balanced(test_labels, baseline_pred, labels)
    majority_margin = observed["macro_f1"] - baseline_metrics["macro_f1"]

    stable_domain_seed = int(_sha256_text(held_domain)[:16], 16)
    rng = Random(seed + stable_domain_seed)
    null_hits = 0
    null_scores: list[float] = []
    original_counts = {label: train_labels.count(label) for label in labels}
    permutation_counts_preserved = True
    for _ in range(permutations):
        shuffled = train_labels[:]
        rng.shuffle(shuffled)
        if {label: shuffled.count(label) for label in labels} != original_counts:
            permutation_counts_preserved = False
        shuffled_train = [
            (case_id, shuffled[index], vector)
            for index, (case_id, _, vector) in enumerate(train)
        ]
        p_models = _fit_one_vs_rest(
            shuffled_train, labels, selected_alpha, mean, std
        )
        p_pred = _predict_one_vs_rest(p_models, test_vectors, mean, std)
        p_metrics, _ = _macro_and_balanced(test_labels, p_pred, labels)
        null_scores.append(p_metrics["macro_f1"])
        if p_metrics["macro_f1"] >= observed["macro_f1"]:
            null_hits += 1
    permutation_p = (1 + null_hits) / (1 + permutations)

    return FoldResult(
        domain=held_domain,
        train_count=len(train),
        test_count=len(test),
        metrics=observed,
        predictions=pred,
        selected_alpha=selected_alpha,
        inner_alpha_scores=alpha_scores,
        majority_margin=majority_margin,
        permutation_p=permutation_p,
        train_case_ids=common_receipt["train_case_ids"],
        test_case_ids=common_receipt["test_case_ids"],
        train_domains=common_receipt["train_domains"],
        test_domains=common_receipt["test_domains"],
        scaler_receipt=scaler_receipt,
        inner_split_receipts=inner_receipts,
        permutation_receipt={
            "scope": "training_labels_only",
            "permutations": permutations,
            "seed": seed,
            "domain_seed_sha256": _sha256_text(held_domain),
            "label_counts_preserved": permutation_counts_preserved,
            "null_hits": null_hits,
            "formula": "p=(1+null>=observed)/(1+n)",
        },
        permutation_null_scores=null_scores,
    )


def _run_layer(
    layer: int,
    vectors: Mapping[str, list[float]],
    case_domain: Mapping[str, str],
    case_label: Mapping[str, str],
    labels: list[str],
    config: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    permutations = _coerce_int(config.get("permutations", _DEFAULT_PERMUTATIONS), _DEFAULT_PERMUTATIONS)
    seed = _coerce_int(config.get("seed", _DEFAULT_SEED), _DEFAULT_SEED)
    if permutations <= 0:
        permutations = _DEFAULT_PERMUTATIONS

    examples: list[tuple[str, str, list[float]]] = []
    for case_id, vector in vectors.items():
        if case_id not in case_label:
            continue
        examples.append((case_id, case_label[case_id], vector))

    by_domain: dict[str, list[tuple[str, str, list[float]]]] = {}
    for case_id, label, vector in examples:
        by_domain.setdefault(case_domain[case_id], []).append((case_id, label, vector))

    if not by_domain:
        return {
            "layer": layer,
            "status": "fail",
            "selected_alpha": 0.0,
            "mean_inner_scores": {},
            "permutation_count": permutations,
            "p_value_raw": 1.0,
            "p_value_holm": 1.0,
            "aggregate": {"accuracy": 0.0, "macro_f1": 0.0, "balanced_accuracy": 0.0},
            "folds": [],
            "issues": ["no cases for layer"],
        }, ["no cases"]

    domains = sorted(by_domain)
    fold_results: list[FoldResult] = []
    alpha_by_fold: dict[str, float] = {}
    for domain in domains:
        fold = _run_outer_fold(
            held_domain=domain,
            by_domain=by_domain,
            labels=labels,
            permutations=permutations,
            seed=seed,
            alpha_cache=alpha_by_fold,
        )
        fold_results.append(fold)

    valid_folds = [f for f in fold_results if f.status == "pass"]
    if valid_folds:
        observed_macro = sum(f.metrics["macro_f1"] for f in valid_folds) / len(valid_folds)
    else:
        observed_macro = 0.0

    if valid_folds and all(len(f.permutation_null_scores) == permutations for f in valid_folds):
        aggregate_null = [
            sum(f.permutation_null_scores[index] for f in valid_folds) / len(valid_folds)
            for index in range(permutations)
        ]
        aggregate_hits = sum(value >= observed_macro for value in aggregate_null)
        layer_p = (1 + aggregate_hits) / (1 + permutations)
    else:
        aggregate_null = []
        layer_p = 1.0

    mean_inner_scores: dict[float, float] = {}
    for alpha in _ALPHA_GRID:
        vals = [f.inner_alpha_scores.get(alpha, 0.0) for f in valid_folds]
        mean_inner_scores[alpha] = sum(vals) / len(vals) if vals else 0.0
    selected_alpha = 0.0
    if mean_inner_scores:
        selected_alpha = min(_ALPHA_GRID, key=lambda a: (-mean_inner_scores[a], _ALPHA_GRID.index(a)))

    status = "pass"
    if any(f.status != "pass" for f in fold_results):
        status = "fail"

    agg_accuracy = sum(f.metrics["accuracy"] for f in fold_results) / len(fold_results) if fold_results else 0.0
    agg_macro = sum(f.metrics["macro_f1"] for f in fold_results) / len(fold_results) if fold_results else 0.0
    agg_balanced = sum(f.metrics["balanced_accuracy"] for f in fold_results) / len(fold_results) if fold_results else 0.0

    return {
        "layer": layer,
        "status": status,
        "selected_alpha": selected_alpha,
        "mean_inner_scores": mean_inner_scores,
        "permutation_count": permutations,
        "p_value_raw": layer_p,
        "p_value_holm": 1.0,
        "permutation_aggregate_receipt": {
            "statistic": "mean_outer_fold_macro_f1",
            "null_count": len(aggregate_null),
            "null_sha256": _sha256_text(stable_json_dumps(aggregate_null)),
            "formula": "p=(1+null>=observed)/(1+n)",
        },
        "aggregate": {
            "accuracy": agg_accuracy,
            "macro_f1": agg_macro,
            "balanced_accuracy": agg_balanced,
        },
        "folds": [
            {
                "domain": fold.domain,
                "train_count": fold.train_count,
                "test_count": fold.test_count,
                "predictions": fold.predictions,
                "metrics": fold.metrics,
                "status": fold.status,
                "details": fold.details,
                "selected_alpha": fold.selected_alpha,
                "inner_alpha_scores": fold.inner_alpha_scores,
                "majority_margin": fold.majority_margin,
                "permutation_p": fold.permutation_p,
                "split_receipt": {
                    "train_case_ids": fold.train_case_ids,
                    "test_case_ids": fold.test_case_ids,
                    "train_domains": fold.train_domains,
                    "test_domains": fold.test_domains,
                    "overlap_case_ids": sorted(set(fold.train_case_ids) & set(fold.test_case_ids)),
                },
                "scaler_receipt": fold.scaler_receipt,
                "inner_split_receipts": fold.inner_split_receipts,
                "permutation_receipt": fold.permutation_receipt,
            }
            for fold in fold_results
        ],
        "observed_layer_macro": observed_macro,
        "observed_seed": seed,
        "issues": issues,
    }, issues


def _holm_adjust(p_values: list[float]) -> list[float]:
    if not p_values:
        return []
    order = sorted((value, idx) for idx, value in enumerate(p_values))
    m = len(p_values)
    adjusted = [0.0] * m
    running = 0.0
    for rank, (value, idx) in enumerate(order):
        candidate = min(1.0, value * (m - rank))
        if candidate < running:
            candidate = running
        adjusted[idx] = candidate
        running = candidate
    return adjusted


def _evaluate_gates(
    predecessor_ok: bool,
    predecessor_issues: list[str],
    config: Mapping[str, Any],
    results: list[dict[str, Any]],
    representation_issues: list[str],
    layer_issues: list[str],
    case_summary: Mapping[str, Any],
    config_min_labels: int,
    config_min_domains: int,
    config_min_cases_per_label: int,
    config_min_cases_per_domain: int,
) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []

    p1 = predecessor_ok and not predecessor_issues and not representation_issues
    gates.append({
        "gate": "P1",
        "status": "pass" if p1 else "fail",
        "details": (
            "Lab01/Lab02/Lab03 summaries pass and declare hashes."
            if p1
            else "; ".join(predecessor_issues or representation_issues)
        ),
    })

    p2 = not layer_issues
    gates.append({
        "gate": "P2",
        "status": "pass" if p2 else "fail",
        "details": "Representations are provenance-aware, finite, and aligned with cases/layers." if p2 else "Representation invariants violated.",
    })

    labels = case_summary.get("labels", [])
    domains = case_summary.get("domains", [])
    cell_counts = case_summary.get("label_domain_cell_counts", {})

    mins_ok = True
    reasons: list[str] = []
    if len(labels) < config_min_labels:
        mins_ok = False
        reasons.append("insufficient unique labels")
    if len(domains) < config_min_domains:
        mins_ok = False
        reasons.append("insufficient unique domains")
    for cell, count in cell_counts.items():
        if count < config_min_cases_per_label:
            mins_ok = False
            reasons.append(f"label-domain cell {cell} below minimum")
    gates.append({
        "gate": "P3",
        "status": "pass" if mins_ok else "fail",
        "details": "; ".join(reasons) if reasons else "Support meets configured minima.",
    })

    receipts_ok = bool(results)
    for layer in results:
        for fold in layer.get("folds", []):
            split = fold.get("split_receipt", {})
            scaler = fold.get("scaler_receipt", {})
            inner = fold.get("inner_split_receipts", [])
            if (
                split.get("overlap_case_ids")
                or set(split.get("train_domains", [])) & set(split.get("test_domains", []))
                or scaler.get("fit_case_ids") != split.get("train_case_ids")
                or set(scaler.get("excluded_case_ids", [])) != set(split.get("test_case_ids", []))
                or not inner
                or any(receipt.get("status") != "pass" or receipt.get("overlap_case_ids") for receipt in inner)
            ):
                receipts_ok = False
    gates.append({
        "gate": "P4",
        "status": "pass" if receipts_ok else "fail",
        "details": "Nested fold and standardization receipts are recorded." if receipts_ok else "Fold receipts incomplete.",
    })

    p5 = bool(results) and all(
        layer.get("permutation_count", 0) > 0
        and layer.get("permutation_aggregate_receipt", {}).get("null_count")
        == layer.get("permutation_count")
        and all(
            fold.get("selected_alpha") in _ALPHA_GRID
            and fold.get("permutation_receipt", {}).get("label_counts_preserved") is True
            and fold.get("permutation_receipt", {}).get("scope") == "training_labels_only"
            for fold in layer.get("folds", [])
        )
        for layer in results
    )
    gates.append({
        "gate": "P5",
        "status": "pass" if p5 else "fail",
        "details": "Permutation protocol executed." if p5 else "Permutation protocol invalid.",
    })

    corrected: list[float] = _holm_adjust([layer.get("p_value_raw", 1.0) for layer in results])
    significance_alpha = _coerce_float(config.get("significance_alpha", 0.05), 0.05)
    for layer, value in zip(results, corrected):
        layer["p_value_holm"] = value

    p6 = p5 and all(
        0.0 <= layer.get("p_value_raw", -1.0) <= 1.0
        and 0.0 <= layer.get("p_value_holm", -1.0) <= 1.0
        for layer in results
    )
    gates.append({
        "gate": "P6",
        "status": "pass" if p6 else "fail",
        "details": "Permutation p-values are valid and Holm correction is recorded." if p6 else "Permutation or Holm correction receipt is invalid.",
    })

    p7_ok = True
    details: list[str] = []
    for layer in results:
        if layer.get("p_value_holm", 1.0) > significance_alpha:
            p7_ok = False
            details.append(f"layer {layer.get('layer')} not Holm-significant")
        for fold in layer.get("folds", []):
            if fold.get("majority_margin", 0.0) < 0.10:
                p7_ok = False
                details.append(f"layer {layer.get('layer')} fold {fold.get('domain')} margin below 0.10")
    gates.append({
        "gate": "P7",
        "status": "pass" if p7_ok else "fail",
        "details": "; ".join(details) if details else "Significance and majority-margin thresholds met.",
    })

    gates.append({
        "gate": "P8",
        "status": "pass",
        "details": "No Latent TRIZ claim is made; decodability evidence is correlational, not causal.",
    })

    return gates


def _collect_predecessor_summary(path: str | Path) -> Mapping[str, Any]:
    payload = _read_json(Path(path).resolve(), "predecessor summary")
    return payload


def run_lab04_analysis(
    *,
    cases_path: str | Path,
    representations_path: str | Path,
    config_path: str | Path,
    predecessor_lab01_summary: str | Path,
    predecessor_lab02_summary: str | Path,
    predecessor_lab03_summary: str | Path,
) -> dict[str, Any]:
    cases_file = Path(cases_path).resolve()
    repr_file = Path(representations_path).resolve()
    config_file = Path(config_path).resolve()

    config = _read_json(config_file, "config")

    thresholds = config.get("readiness_thresholds", {})
    if not isinstance(thresholds, Mapping):
        raise Lab04Error("config readiness_thresholds must be an object")
    config_min_labels = _coerce_int(thresholds.get("minimum_labels", 2), 2)
    config_min_domains = _coerce_int(thresholds.get("minimum_domains", 4), 4)
    config_min_cell = _coerce_int(
        thresholds.get("minimum_cases_per_label_domain_cell", 6), 6
    )

    raw_cases = _read_jsonl(cases_file, "cases")
    case_label, case_domain, case_issues = _collect_cases(raw_cases, config_min_labels)

    raw_repr = _read_jsonl(repr_file, "representations")
    layers_data, representation_issues = _collect_representations(raw_repr, case_label)

    source = config.get("representation_source", {})
    declared_hashes = source.get("hashes", {}) if isinstance(source, Mapping) else {}
    if declared_hashes.get("records_sha256") != _sha256_file(repr_file):
        representation_issues.append("representation file hash does not match config")
    if declared_hashes.get("cases_sha256") != _sha256_file(cases_file):
        representation_issues.append("cases file hash does not match config")

    if len(representation_issues) > 0:
        layer_issue = list(representation_issues)
    else:
        layer_issue = []

    predecessor_paths = [
        Path(predecessor_lab01_summary).resolve(),
        Path(predecessor_lab02_summary).resolve(),
        Path(predecessor_lab03_summary).resolve(),
    ]
    pred01, pred02, pred03 = [
        _collect_predecessor_summary(path) for path in predecessor_paths
    ]

    predecessor_payloads = (pred01, pred02, pred03)
    predecessor_ok = True
    predecessor_issues: list[str] = []
    for name, payload in zip(("lab01", "lab02", "lab03"), predecessor_payloads):
        if payload.get("status") != "pass":
            predecessor_ok = False
            predecessor_issues.append(f"{name} did not pass")
        hashes = payload.get("hashes", payload.get("artifact_hashes"))
        if not isinstance(hashes, Mapping) or not hashes:
            predecessor_ok = False
            predecessor_issues.append(f"{name} missing hash declarations")

    labels = sorted(set(case_label.values()))
    domains = sorted(set(case_domain.values()))

    counts_label = {label: 0 for label in labels}
    for label in case_label.values():
        counts_label[label] = counts_label.get(label, 0) + 1
    counts_domain = {domain: 0 for domain in domains}
    for domain in case_domain.values():
        counts_domain[domain] = counts_domain.get(domain, 0) + 1

    cell_counts = {
        f"{label}|{domain}": sum(
            1
            for case_id, case_label_value in case_label.items()
            if case_label_value == label and case_domain[case_id] == domain
        )
        for label in labels
        for domain in domains
    }

    case_counts_issue: list[str] = []
    if len(labels) < config_min_labels:
        case_counts_issue.append("insufficient unique labels")
    if len(domains) < config_min_domains:
        case_counts_issue.append("insufficient unique domains")
    for cell, count in cell_counts.items():
        if count < config_min_cell:
            case_counts_issue.append(f"label-domain cell {cell} below minimum")

    layer_results: list[dict[str, Any]] = []
    for layer in sorted(layers_data):
        layer_payload, issues = _run_layer(
            layer=layer,
            vectors=layers_data[layer],
            case_domain=case_domain,
            case_label=case_label,
            labels=labels,
            config=config,
        )
        layer_results.append(layer_payload)
        layer_issue.extend(issues)

    gates = _evaluate_gates(
        predecessor_ok=predecessor_ok,
        predecessor_issues=predecessor_issues,
        config=config,
        results=layer_results,
        representation_issues=representation_issues,
        layer_issues=layer_issue,
        case_summary={
            "labels": labels,
            "domains": domains,
            "label_counts": counts_label,
            "domain_counts": counts_domain,
            "label_domain_cell_counts": cell_counts,
        },
        config_min_labels=config_min_labels,
        config_min_domains=config_min_domains,
        config_min_cases_per_label=config_min_cell,
        config_min_cases_per_domain=config_min_cell,
    )

    status = "pass" if all(item["status"] == "pass" for item in gates) and predecessor_ok else "fail"

    issues = [
        *case_issues,
        *representation_issues,
        *case_counts_issue,
        *predecessor_issues,
        *layer_issue,
    ]

    return {
        "artifact_class": "representation-decodability-instrumentation",
        "empirical": False,
        "evidence_eligible": False,
        "claim_ids": [],
        "status": status,
        "non_claim_boundary": (
            "No Latent TRIZ claim is made from this run. "
            "Decodability is correlational, not causal."
        ),
        "hashes": {
            "cases_jsonl": _sha256_file(cases_file),
            "representations_jsonl": _sha256_file(repr_file),
            "config_json": _sha256_file(config_file),
            "probe_result_json": "",
            "report_html": "",
            "summary_json": "",
        },
        "predecessors": {
            "lab01": {"status": str(pred01.get("status")), "summary_sha256": _sha256_file(predecessor_paths[0])},
            "lab02": {"status": str(pred02.get("status")), "summary_sha256": _sha256_file(predecessor_paths[1])},
            "lab03": {"status": str(pred03.get("status")), "summary_sha256": _sha256_file(predecessor_paths[2])},
        },
        "case_summary": {
            "case_count": len(case_label),
            "label_count": len(labels),
            "domain_count": len(domains),
            "labels": labels,
            "domains": domains,
            "label_counts": counts_label,
            "domain_counts": counts_domain,
            "label_domain_cell_counts": cell_counts,
        },
        "random_control": {
            "seed": _coerce_int(config.get("seed", _DEFAULT_SEED), _DEFAULT_SEED),
            "permutations": _coerce_int(config.get("permutations", _DEFAULT_PERMUTATIONS), _DEFAULT_PERMUTATIONS),
            "method": "training-label permutation only; test labels unchanged",
            "formula": "p=(1+null>=observed)/(1+n)",
        },
        "config": {
            "minimum_labels": config_min_labels,
            "minimum_domains": config_min_domains,
            "minimum_cases_per_label_domain_cell": config_min_cell,
            "alphas": list(_ALPHA_GRID),
            "permutations": _coerce_int(config.get("permutations", _DEFAULT_PERMUTATIONS), _DEFAULT_PERMUTATIONS),
            "seed": _coerce_int(config.get("seed", _DEFAULT_SEED), _DEFAULT_SEED),
            "significance_alpha": _coerce_float(config.get("significance_alpha", 0.05), 0.05),
        },
        "layers": layer_results,
        "gates": gates,
        "issues": issues,
    }
