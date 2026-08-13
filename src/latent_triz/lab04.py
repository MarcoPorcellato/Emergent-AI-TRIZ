from __future__ import annotations

import hashlib
import importlib
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
_DEFAULT_NUMERIC_BACKEND = "pure_python"
_PINNED_NUMPY_VERSION = "2.4.3"


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


def _coerce_numeric_backend(value: Any) -> str:
    if value is None:
        return _DEFAULT_NUMERIC_BACKEND
    if value in {"pure_python", "numpy"}:
        return str(value)
    raise Lab04Error(
        f"invalid numeric_backend {value!r}; expected one of 'pure_python', 'numpy'"
    )


def _is_numpy_available() -> bool:
    try:
        importlib.import_module("numpy")
        return True
    except Exception:
        return False


def _require_numpy_available() -> str:
    try:
        module = importlib.import_module("numpy")
    except Exception as exc:
        raise Lab04Error(
            "numeric_backend requested as numpy but NumPy is not available"
        ) from exc
    version = str(getattr(module, "__version__", "unknown"))
    if version != _PINNED_NUMPY_VERSION:
        raise Lab04Error(
            f"numeric_backend requires NumPy {_PINNED_NUMPY_VERSION}, found {version}"
        )
    return version


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _build_permutation_labels(
    sorted_case_ids: list[str],
    case_labels: list[str],
    blocks: list[str],
    permutations: int,
    base_seed: int,
) -> list[list[str]]:
    if len(sorted_case_ids) != len(case_labels) or len(blocks) != len(case_labels):
        raise Lab04Error("case ids, labels, and permutation blocks must align")
    if permutations <= 0:
        return []
    sequence: list[list[str]] = []
    for permutation_index in range(permutations):
        rng = Random(base_seed + permutation_index + 1)
        shuffled = case_labels[:]
        for block in sorted(set(blocks)):
            indices = [index for index, value in enumerate(blocks) if value == block]
            values = [case_labels[index] for index in indices]
            rng.shuffle(values)
            for index, value in zip(indices, values):
                shuffled[index] = value
        sequence.append(shuffled)
    return sequence


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


def _load_external_vector(
    item: Mapping[str, Any],
    *,
    representation_root: Path,
    artifact_cache: dict[Path, tuple[str, Mapping[str, Any]]],
) -> list[float]:
    artifact_uri = str(item.get("artifact_uri", "")).strip()
    tensor_key = str(item.get("tensor_key", "")).strip()
    if not artifact_uri or not tensor_key:
        raise Lab04Error("external representation requires artifact_uri and tensor_key")

    relative = Path(artifact_uri)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".safetensors":
        raise Lab04Error(f"unsafe representation artifact_uri {artifact_uri!r}")
    root = representation_root.resolve()
    artifact_path = (root / relative).resolve()
    if not artifact_path.is_relative_to(root):
        raise Lab04Error(f"representation artifact escapes its index directory: {artifact_uri!r}")

    declared_artifact_hash = str(item.get("artifact_sha256", ""))
    cached = artifact_cache.get(artifact_path)
    if cached is None:
        if not artifact_path.is_file():
            raise Lab04Error(f"representation artifact not found: {artifact_uri}")
        actual_artifact_hash = _sha256_file(artifact_path)
        if declared_artifact_hash != actual_artifact_hash:
            raise Lab04Error(f"representation artifact hash mismatch: {artifact_uri}")
        try:
            safetensors_numpy = importlib.import_module("safetensors.numpy")
            tensors = safetensors_numpy.load_file(str(artifact_path))
        except Exception as exc:
            raise Lab04Error(f"cannot load representation artifact {artifact_uri}: {exc}") from exc
        if not isinstance(tensors, Mapping):
            raise Lab04Error(f"invalid safetensors payload: {artifact_uri}")
        cached = (actual_artifact_hash, tensors)
        artifact_cache[artifact_path] = cached
    elif declared_artifact_hash != cached[0]:
        raise Lab04Error(f"inconsistent representation artifact hash: {artifact_uri}")

    tensor = cached[1].get(tensor_key)
    if tensor is None:
        raise Lab04Error(f"tensor key {tensor_key!r} not found in {artifact_uri}")
    try:
        array = tensor.reshape(-1)
        dtype = str(array.dtype)
        byte_order = array.dtype.byteorder or "little"
        if byte_order not in ("<", "|"):
            array = array.astype(array.dtype.newbyteorder("<"), copy=False)
            byte_order = "<"
        shape = list(array.shape)
        metadata = stable_json_dumps(
            {"byte_order": byte_order, "dtype": dtype, "shape": shape}
        ).encode("utf-8")
        vector_hash = hashlib.sha256(metadata + b"|" + array.tobytes(order="C")).hexdigest()
        values = array.tolist()
    except Exception as exc:
        raise Lab04Error(f"invalid tensor {tensor_key!r} in {artifact_uri}: {exc}") from exc

    if item.get("dtype") != dtype or item.get("shape") != shape:
        raise Lab04Error(f"tensor metadata mismatch for {tensor_key!r}")
    if item.get("vector_dim") != len(values):
        raise Lab04Error(f"vector_dim mismatch for {tensor_key!r}")
    if item.get("vector_sha256") != vector_hash:
        raise Lab04Error(f"vector hash mismatch for {tensor_key!r}")
    return _to_float_vector(values, label=f"tensor {tensor_key}")


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
    representation_root: Path | None = None,
) -> tuple[dict[int, dict[str, list[float]]], list[str]]:
    layers: dict[int, dict[str, list[float]]] = {}
    issues: list[str] = []
    seen_pairs: set[tuple[int, str]] = set()
    case_ids = set(case_label)
    artifact_cache: dict[Path, tuple[str, Mapping[str, Any]]] = {}

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
        if "vector" in item:
            vector = _to_float_vector(item["vector"], label=f"case {case_id} layer {key}")
        elif representation_root is not None:
            vector = _load_external_vector(
                item,
                representation_root=representation_root,
                artifact_cache=artifact_cache,
            )
        else:
            issues.append(f"representation line {index} has no vector field")
            continue
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


def _ridge_weights(
    vectors: list[list[float]],
    y: list[float],
    alpha: float,
    backend: str = _DEFAULT_NUMERIC_BACKEND,
) -> list[float]:
    X = [row + [1.0] for row in vectors]
    if backend == "numpy":
        import numpy as np

        design = np.asarray(X, dtype=float)
        feature_count = design.shape[1] - 1
        penalty = np.zeros((feature_count, feature_count + 1), dtype=float)
        penalty[:, :feature_count] = np.eye(feature_count, dtype=float) * np.sqrt(alpha)
        augmented_design = np.vstack((design, penalty))
        augmented_target = np.concatenate((np.asarray(y, dtype=float), np.zeros(feature_count)))
        try:
            weights, _, rank, _ = np.linalg.lstsq(
                augmented_design, augmented_target, rcond=None
            )
        except Exception as exc:
            raise Lab04Error(f"NumPy ridge least-squares solve failed: {exc}") from exc
        if rank < feature_count + 1 or not np.isfinite(weights).all():
            raise Lab04Error("NumPy ridge least-squares solve is rank-deficient or non-finite")
        return weights.tolist()

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
    backend: str = _DEFAULT_NUMERIC_BACKEND,
) -> dict[str, list[float]]:
    vectors = [row for _, __, row in examples]
    x = _standardize(vectors, mean, std)
    models: dict[str, list[float]] = {}
    for label in labels:
        y = [1.0 if y_label == label else -1.0 for _, y_label, _ in examples]
        models[label] = _ridge_weights(x, y, alpha, backend)
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
    backend: str = _DEFAULT_NUMERIC_BACKEND,
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
            models = _fit_one_vs_rest(inner_train, labels, alpha, mean, std, backend)
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
    permutation_sequences: list[list[str]] | None = None,
    reselect_alpha_within_permutation: bool = True,
    backend: str = _DEFAULT_NUMERIC_BACKEND,
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
        train, labels, domain_lookup, backend
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
    models = _fit_one_vs_rest(train, labels, selected_alpha, mean, std, backend)
    pred = _predict_one_vs_rest(models, test_vectors, mean, std)
    observed, _ = _macro_and_balanced(test_labels, pred, labels)

    majority = _majority_label(train_labels)
    baseline_pred = [majority] * len(test_labels)
    baseline_metrics, _ = _macro_and_balanced(test_labels, baseline_pred, labels)
    majority_margin = observed["macro_f1"] - baseline_metrics["macro_f1"]

    null_hits = 0
    null_scores: list[float] = []
    original_counts = {label: train_labels.count(label) for label in labels}
    permutation_counts_preserved = True
    sorted_train = sorted(train, key=lambda item: item[0])
    sorted_train_ids = [case_id for case_id, _, _ in sorted_train]
    sorted_train_labels = [label for _, label, _ in sorted_train]
    sorted_train_blocks = [domain_lookup[case_id] for case_id in sorted_train_ids]
    if permutation_sequences is None:
        permutation_sequences = _build_permutation_labels(
            sorted_case_ids=sorted_train_ids,
            case_labels=sorted_train_labels,
            blocks=sorted_train_blocks,
            permutations=permutations,
            base_seed=seed + int(_sha256_text(held_domain)[:8], 16),
        )
    elif len(permutation_sequences) < permutations:
        raise Lab04Error("insufficient permutation_sequences for requested permutations")

    permutation_alpha_reselection: list[dict[str, Any]] = []
    permuted_alpha_errors: list[str] = []
    original_block_counts = {
        block: {
            label: sum(
                1
                for candidate_block, candidate_label in zip(
                    sorted_train_blocks, sorted_train_labels
                )
                if candidate_block == block and candidate_label == label
            )
            for label in labels
        }
        for block in sorted(set(sorted_train_blocks))
    }
    permutation_block_counts_preserved = True
    for _ in range(permutations):
        shuffled = permutation_sequences[_]
        if {label: shuffled.count(label) for label in labels} != original_counts:
            permutation_counts_preserved = False
        for block, expected in original_block_counts.items():
            observed_block_counts = {
                label: sum(
                    1
                    for candidate_block, candidate_label in zip(
                        sorted_train_blocks, shuffled
                    )
                    if candidate_block == block and candidate_label == label
                )
                for label in labels
            }
            if observed_block_counts != expected:
                permutation_block_counts_preserved = False
        perm_alpha = selected_alpha
        if reselect_alpha_within_permutation:
            perm_train = [
                (case_id, shuffled[index], vector)
                for index, (case_id, _, vector) in enumerate(sorted_train)
            ]
            perm_alpha_candidate, _perm_alpha_scores, perm_alpha_errors, perm_inner_receipts = _inner_alpha_search(
                perm_train, labels, domain_lookup, backend
            )
            status = "pass"
            details: list[str] = []
            if perm_alpha_candidate is None:
                perm_alpha_candidate = selected_alpha
                status = "fail"
                details = perm_alpha_errors or ["inner alpha search failed"]
                permuted_alpha_errors.extend(perm_alpha_errors)
            permutation_alpha_reselection.append(
                {
                    "permutation_index": _,
                    "status": status,
                    "selected_alpha": perm_alpha_candidate,
                    "inner_split_receipts": perm_inner_receipts,
                    "details": "; ".join(details),
                }
            )
            perm_alpha = perm_alpha_candidate
        else:
            permutation_alpha_reselection.append(
                {
                    "permutation_index": _,
                    "status": "pass",
                    "selected_alpha": perm_alpha,
                    "inner_split_receipts": [],
                    "details": "",
                }
            )
        shuffled_train = [
            (case_id, shuffled[index], vector)
            for index, (case_id, _, vector) in enumerate(sorted_train)
        ]
        p_models = _fit_one_vs_rest(
            shuffled_train, labels, perm_alpha, mean, std, backend
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
            "block": "outer_training_domain",
            "block_label_counts_preserved": permutation_block_counts_preserved,
            "case_order_sha256": _sha256_text(stable_json_dumps(sorted_train_ids)),
            "null_hits": null_hits,
            "formula": "p=(1+null>=observed)/(1+n)",
            "alpha_reselected_within_each_permutation": reselect_alpha_within_permutation,
            "alpha_reselection_count": len(permutation_alpha_reselection),
            "alpha_reselection_failures": sum(
                item.get("status") != "pass" for item in permutation_alpha_reselection
            ),
            "alpha_reselection_sha256": _sha256_text(
                stable_json_dumps(permutation_alpha_reselection)
            ),
            "permutation_alpha_errors": bool(permuted_alpha_errors),
            "numeric_backend": backend,
            "numeric_solver": (
                "numpy_augmented_lstsq" if backend == "numpy"
                else "pure_python_normal_equations_reference"
            ),
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
    max_statistic_permutation_states: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    backend = _coerce_numeric_backend(config.get("numeric_backend"))
    permutations = _coerce_int(config.get("permutations", _DEFAULT_PERMUTATIONS), _DEFAULT_PERMUTATIONS)
    seed = _coerce_int(config.get("seed", _DEFAULT_SEED), _DEFAULT_SEED)
    reselect_within_each_permutation = _coerce_bool(
        config.get("reselect_within_each_permutation", True), True
    )
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
            "aggregate": {"accuracy": 0.0, "macro_f1": 0.0, "balanced_accuracy": 0.0},
            "folds": [],
            "issues": ["no cases for layer"],
        }, ["no cases"]

    domains = sorted(by_domain)
    fold_results: list[FoldResult] = []
    alpha_by_fold: dict[str, float] = {}
    for domain in domains:
        sorted_train = sorted(
            [
                item
                for domain_name in sorted(by_domain)
                if domain_name != domain
                for item in by_domain[domain_name]
            ],
            key=lambda item: item[0],
        )
        permutation_labels = _build_permutation_labels(
            sorted_case_ids=[case_id for case_id, _, _ in sorted_train],
            case_labels=[label for _, label, _ in sorted_train],
            blocks=[case_domain[case_id] for case_id, _, _ in sorted_train],
            permutations=permutations,
            base_seed=seed + int(_sha256_text(domain)[:8], 16),
        )
        fold = _run_outer_fold(
            held_domain=domain,
            by_domain=by_domain,
            labels=labels,
            permutations=permutations,
            seed=seed,
            alpha_cache=alpha_by_fold,
            permutation_sequences=permutation_labels,
            reselect_alpha_within_permutation=reselect_within_each_permutation,
            backend=backend,
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

    if max_statistic_permutation_states is not None:
        max_statistic_permutation_states.append(
            {
                "layer": layer,
                "observed_layer_macro": observed_macro,
                "permutation_null": aggregate_null,
                "permutation_count": len(aggregate_null),
            }
        )

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


def _select_max_stat_layer(records: list[dict[str, Any]]) -> int | None:
    if not records:
        return None
    selected = min(records, key=lambda item: (-item.get("observed_layer_macro", 0.0), item.get("layer", 0)))
    return selected.get("layer")


def _compute_max_stat_p(
    records: list[dict[str, Any]],
    selected_layer: int | None,
) -> tuple[float, int]:
    if not records or selected_layer is None:
        return 1.0, 0
    selected = next(
        (item for item in records if item.get("layer") == selected_layer),
        None,
    )
    if selected is None:
        return 1.0, 0
    selected_observed = selected.get("observed_layer_macro", 0.0)
    null_count = min(item.get("permutation_count", 0) for item in records)
    if null_count == 0:
        return 1.0, 0
    max_null: list[float] = []
    for permutation_index in range(null_count):
        per_layer = [
            item.get("permutation_null", [])[permutation_index]
            for item in records
            if len(item.get("permutation_null", [])) > permutation_index
        ]
        if not per_layer:
            return 1.0, 0
        max_null.append(max(per_layer))
    hits = sum(value >= selected_observed for value in max_null)
    return (1 + hits) / (1 + null_count), null_count


def _evaluate_gates(
    predecessor_ok: bool,
    predecessor_issues: list[str],
    case_issues: list[str],
    config: Mapping[str, Any],
    results: list[dict[str, Any]],
    representation_issues: list[str],
    layer_issues: list[str],
    case_summary: Mapping[str, Any],
    config_min_labels: int,
    config_min_domains: int,
    config_min_cases_per_label: int,
    config_min_cases_per_domain: int,
    selected_layer: int | None,
    max_statistic_p: float,
    max_statistic_permutations: int,
    max_statistic_error: str | None,
) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []

    p1 = (
        predecessor_ok
        and not predecessor_issues
        and not representation_issues
        and not case_issues
    )
    gates.append({
        "gate": "P1",
        "status": "pass" if p1 else "fail",
        "details": (
            "Lab01/Lab02/Lab03 summaries pass and declare hashes."
            if p1
            else "; ".join(predecessor_issues + representation_issues + case_issues)
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
            and fold.get("permutation_receipt", {}).get("block") == "outer_training_domain"
            and fold.get("permutation_receipt", {}).get("block_label_counts_preserved") is True
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

    readiness_thresholds = config.get("readiness_thresholds", {})
    if not isinstance(readiness_thresholds, Mapping):
        readiness_thresholds = {}
    significance_alpha = _coerce_float(
        readiness_thresholds.get("corrected_p_max", 0.05), 0.05
    )
    margin_min = _coerce_float(
        readiness_thresholds.get("macro_f1_margin_over_majority_min", 0.10),
        0.10,
    )
    selected_payload = next(
        (layer for layer in results if layer.get("layer") == selected_layer),
        None,
    )
    method_ok = config.get("max_statistic") == "outer_fold_macro_f1_max"
    block_ok = config.get("permutation_blocks") == "outer_training_domain"
    reselection_ok = config.get("reselect_within_each_permutation") is True
    fold_reselection_ok = bool(results) and all(
        fold.get("permutation_receipt", {}).get(
            "alpha_reselected_within_each_permutation"
        ) is True
        and fold.get("permutation_receipt", {}).get("permutation_alpha_errors") is False
        for layer in results
        for fold in layer.get("folds", [])
    )
    p6 = (
        p5
        and method_ok
        and block_ok
        and reselection_ok
        and fold_reselection_ok
        and max_statistic_error is None
        and selected_payload is not None
        and max_statistic_permutations > 0
        and 0.0 <= max_statistic_p <= 1.0
    )
    p7_ok = p6 and max_statistic_p <= significance_alpha and selected_payload is not None
    details: list[str] = []
    if not p6 and max_statistic_error is not None:
        details.append(max_statistic_error)
    if max_statistic_p > significance_alpha:
        p7_ok = False
        details.append(
            f"max-statistic p {max_statistic_p} exceeds configured alpha {significance_alpha}"
        )
    if selected_payload is None:
        p7_ok = False
        details.append("no selected layer for max-statistic control")
    else:
        for fold in selected_payload.get("folds", []):
            if fold.get("majority_margin", 0.0) < margin_min:
                p7_ok = False
                details.append(
                    f"selected layer {selected_layer} fold {fold.get('domain')} margin below {margin_min}"
                )
            if fold.get("permutation_receipt", {}).get(
                "alpha_reselected_within_each_permutation"
            ) is not True:
                p7_ok = False
                details.append(
                    f"selected layer {selected_layer} fold {fold.get('domain')} did not reselect alpha per permutation"
                )
            if fold.get("permutation_receipt", {}).get("permutation_alpha_errors") is True:
                p7_ok = False
                details.append(
                    f"selected layer {selected_layer} fold {fold.get('domain')} permutation alpha reselection failed"
                )
    gates.append({
        "gate": "P6",
        "status": "pass" if p6 else "fail",
        "details": "Permutation controls and max-statistic summary are available." if p6 else "Permutation protocol or max-statistic control is invalid.",
    })
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
    numeric_backend = _coerce_numeric_backend(config.get("numeric_backend"))
    numeric_library_version = "none"
    if numeric_backend == "numpy":
        numeric_library_version = _require_numpy_available()

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
    layers_data, representation_issues = _collect_representations(
        raw_repr,
        case_label,
        representation_root=repr_file.parent,
    )

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
    max_statistic_records: list[dict[str, Any]] = []
    for layer in sorted(layers_data):
        layer_payload, issues = _run_layer(
            layer=layer,
            vectors=layers_data[layer],
            case_domain=case_domain,
            case_label=case_label,
            labels=labels,
            config=config,
            max_statistic_permutation_states=max_statistic_records,
        )
        layer_results.append(layer_payload)
        layer_issue.extend(issues)

    permutations = _coerce_int(config.get("permutations", _DEFAULT_PERMUTATIONS), _DEFAULT_PERMUTATIONS)
    if permutations <= 0:
        permutations = _DEFAULT_PERMUTATIONS
    readiness_thresholds = config.get("readiness_thresholds", {})
    if not isinstance(readiness_thresholds, Mapping):
        readiness_thresholds = {}
    significance_alpha = _coerce_float(
        readiness_thresholds.get("corrected_p_max", 0.05), 0.05
    )
    max_statistic_error: str | None = None
    selected_layer: int | None = None
    max_statistic_p = 1.0
    max_statistic_null_count = 0
    max_statistic_null: list[float] = []

    if permutations > 0 and 1.0 / (permutations + 1) > significance_alpha:
        max_statistic_error = (
            f"configured significance_alpha {significance_alpha} is below minimum resolvable p={1.0/(permutations+1):.6f}"
        )

    if max_statistic_records:
        selected_layer = _select_max_stat_layer(max_statistic_records)
        max_statistic_p, max_statistic_null_count = _compute_max_stat_p(
            records=max_statistic_records, selected_layer=selected_layer
        )
        if max_statistic_null_count == 0 and max_statistic_error is None:
            max_statistic_error = "no valid max-statistic null draws"

    if max_statistic_error is None and max_statistic_null_count > 0:
        selected_record = next(
            (item for item in max_statistic_records if item.get("layer") == selected_layer),
            None,
        )
        if selected_record is not None:
            max_statistic_null = selected_record.get("permutation_null", [])[:max_statistic_null_count]
            max_statistic_null = [
                max(
                    item.get("permutation_null", [])[index]
                    for item in max_statistic_records
                    if len(item.get("permutation_null", [])) > index
                )
                for index in range(max_statistic_null_count)
            ]
        if not max_statistic_null:
            max_statistic_error = "no valid max-statistic null draws"

    if max_statistic_error is None and max_statistic_null_count == 0 and max_statistic_records:
        max_statistic_error = "no valid max-statistic null draws"
    statistical_issues = [max_statistic_error] if max_statistic_error else []
    gates = _evaluate_gates(
        predecessor_ok=predecessor_ok,
        predecessor_issues=predecessor_issues,
        case_issues=case_issues,
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
        selected_layer=selected_layer,
        max_statistic_p=max_statistic_p,
        max_statistic_permutations=max_statistic_null_count,
        max_statistic_error=max_statistic_error,
    )

    status = "pass" if all(item["status"] == "pass" for item in gates) and predecessor_ok else "fail"

    issues = [
        *case_issues,
        *representation_issues,
        *case_counts_issue,
        *predecessor_issues,
        *layer_issue,
        *statistical_issues,
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
            "method": (
                "training labels permuted with deterministic shared draws across layers; "
                "inner alpha selection repeated inside every draw; test labels unchanged"
            ),
            "formula": "p=(1+null>=observed)/(1+n)",
            "max_statistic": {
                "selected_layer": selected_layer,
                "max_statistic_p": max_statistic_p,
                "null_count": max_statistic_null_count,
                "null_sha256": _sha256_text(stable_json_dumps(max_statistic_null)),
                "signature": "max_statistic_family_wise",
                "configured_alpha": significance_alpha,
            },
        },
        "config": {
            "numeric_backend": numeric_backend,
            "numeric_solver": (
                "numpy_augmented_lstsq" if numeric_backend == "numpy"
                else "pure_python_normal_equations_reference"
            ),
            "numeric_library_version": numeric_library_version,
            "minimum_labels": config_min_labels,
            "minimum_domains": config_min_domains,
            "minimum_cases_per_label_domain_cell": config_min_cell,
            "alphas": list(_ALPHA_GRID),
            "max_statistic": config.get("max_statistic", "outer_fold_macro_f1_max"),
            "permutation_blocks": config.get("permutation_blocks", "outer_training_domain"),
            "reselect_within_each_permutation": _coerce_bool(
                config.get("reselect_within_each_permutation", True), True
            ),
            "permutations": _coerce_int(config.get("permutations", _DEFAULT_PERMUTATIONS), _DEFAULT_PERMUTATIONS),
            "seed": _coerce_int(config.get("seed", _DEFAULT_SEED), _DEFAULT_SEED),
            "significance_alpha": significance_alpha,
        },
        "layers": layer_results,
        "gates": gates,
        "issues": issues,
    }
