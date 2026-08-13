from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from math import sqrt
from pathlib import Path
from random import Random
from typing import Any, Iterable, Mapping, Sequence


class Lab03Error(RuntimeError):
    pass


_REQUIRED_METHODS = (
    "majority",
    "keyword_matching",
    "bag_of_words",
    "char_ngram",
    "length_punctuation",
)

_LODO_VIEWS = ("problem_only", "transformation_only", "resulting_state_only", "problem_plus_solution")

_VIEW_TEXT_FIELDS: dict[str, tuple[str, ...]] = {
    "problem_only": ("problem",),
    "transformation_only": ("transformation",),
    "resulting_state_only": ("resulting_state",),
    "problem_plus_solution": (
        "problem",
        "constraints",
        "initial_state",
        "desired_improvement",
        "worsening_consequence",
        "transformation",
        "resulting_state",
        "solution",
    ),
}

_UNAVAILABLE_FAMILIES = (
    "conventional_sentence_embeddings",
    "topic_classification",
    "output_only_llm",
)

_DEFAULT_LABEL_PRIOR_MIN = 2
_DEFAULT_SHORTCUT_THRESHOLD = 0.55
_DEFAULT_SHORTCUT_MARGIN = 0.08
_DEFAULT_MIN_DOMAINS = 2
_DEFAULT_RANDOM_PERMUTATIONS = 3
_DEFAULT_RANDOM_SEED = 13
_DEFAULT_MIN_CASES_PER_LABEL = 1
_DEFAULT_MIN_CASES_PER_HELD_OUT_DOMAIN = 1
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class FoldResult:
    domain: str
    train_count: int
    test_count: int
    predictions: list[dict[str, str]]
    metrics: Mapping[str, float]
    status: str
    details: str | None = None
    train_labels: tuple[str, ...] = ()
    test_labels: tuple[str, ...] = ()


def run_behavioral_baselines(cases_path: str | Path, snapshot_path: str | Path, config_path: str | Path) -> dict[str, Any]:
    cases_file = Path(cases_path).resolve()
    snapshot_file = Path(snapshot_path).resolve()
    config_file = Path(config_path).resolve()
    cases = _read_jsonl(cases_file, "cases")
    snapshot = _load_json(snapshot_file, "snapshot")
    config = _load_json(config_file, "config")

    canonical_cases, case_issues = _canonicalize_cases(cases)
    if not canonical_cases:
        raise Lab03Error("no valid canonical cases")

    labels = sorted({item["label"] for item in canonical_cases})
    domains = sorted({item["domain"] for item in canonical_cases})

    random_seed = _coerce_int(config, "seed", _DEFAULT_RANDOM_SEED)
    shortcut_threshold = _coerce_float(config, "shortcut_macro_f1_threshold", _DEFAULT_SHORTCUT_THRESHOLD)
    shortcut_margin = _coerce_float(config, "shortcut_margin_over_majority", _DEFAULT_SHORTCUT_MARGIN)
    random_permutations = _coerce_int(config, "random_permutations", _DEFAULT_RANDOM_PERMUTATIONS, minimum=1)
    minimum_labels = _coerce_int(config, "minimum_labels", _DEFAULT_LABEL_PRIOR_MIN, minimum=2)
    minimum_domains = _coerce_int(config, "minimum_domains", _DEFAULT_MIN_DOMAINS, minimum=2)
    minimum_cases_per_label = _coerce_int(
        config,
        "minimum_cases_per_label",
        _DEFAULT_MIN_CASES_PER_LABEL,
        minimum=1,
    )
    minimum_training_cases_per_label = _coerce_int(
        config,
        "minimum_training_cases_per_label",
        minimum_cases_per_label,
        minimum=1,
    )
    minimum_cases_per_held_out_domain = _coerce_int(
        config,
        "minimum_cases_per_held_out_domain",
        _DEFAULT_MIN_CASES_PER_HELD_OUT_DOMAIN,
        minimum=1,
    )
    minimum_cases_per_label_per_domain = _coerce_int(
        config,
        "minimum_cases_per_label_per_domain",
        1,
        minimum=1,
    )

    method_families = _coerce_str_list(config.get("method_families"))
    allow_local = set(_coerce_str_list(config.get("allow_local_diagnostics")))
    configured_views = _coerce_str_list(config.get("evaluation_views"))
    if configured_views and tuple(configured_views) != _LODO_VIEWS:
        raise Lab03Error(f"evaluation_views must be exactly {list(_LODO_VIEWS)!r}")

    method_requests = set(method_families) | set(_REQUIRED_METHODS)
    # keep char_ngram active only when explicitly enabled by local diagnostics or explicit request
    requested_methods = sorted({
        name
        for name in _REQUIRED_METHODS
        if name != "char_ngram" or name in method_requests or name in allow_local
    })

    baseline_gates_input = {
        "minimum_labels": minimum_labels,
        "minimum_domains": minimum_domains,
        "minimum_cases_per_label": minimum_cases_per_label,
        "minimum_training_cases_per_label": minimum_training_cases_per_label,
        "minimum_cases_per_held_out_domain": minimum_cases_per_held_out_domain,
        "minimum_cases_per_label_per_domain": minimum_cases_per_label_per_domain,
        "random_permutations": random_permutations,
        "seed": random_seed,
        "requested_methods": requested_methods,
        "labels": labels,
        "domains": domains,
    }

    case_counts_by_label = Counter(item["label"] for item in canonical_cases)
    case_counts_by_domain = Counter(item["domain"] for item in canonical_cases)

    random_control = _run_random_label_control(
        canonical_cases=canonical_cases,
        labels=labels,
        random_seed=random_seed,
        random_permutations=random_permutations,
        minimum_training_cases_per_label=minimum_training_cases_per_label,
        minimum_cases_per_held_out_domain=minimum_cases_per_held_out_domain,
        minimum_cases_per_label_per_domain=minimum_cases_per_label_per_domain,
        allow_local=allow_local,
    )

    view_texts = {
        view_name: _cases_to_text(canonical_cases, view_name=view_name)
        for view_name in _LODO_VIEWS
    }
    provenance_shortcuts = _provenance_shortcut_diagnostics(canonical_cases, labels)

    methods: dict[str, Any] = {}
    for method in requested_methods:
        method_status = "pass"
        method_views: dict[str, Any] = {}
        for view_name, values in view_texts.items():
            folds = _leave_one_domain_out_folds(values)
            fold_rows: list[FoldResult] = []
            if not folds:
                method_views[view_name] = {
                    "status": "fail",
                    "reason": "no complete domain folds",
                    "folds": [],
                    "aggregate": _empty_metrics(),
                }
                method_status = "fail"
                continue

            for domain, (train, test) in folds:
                if method == "majority":
                    pred = _predict_majority(train=train, test=test, labels=labels)
                elif method == "keyword_matching":
                    pred = _predict_keyword(train=train, test=test, labels=labels)
                elif method == "bag_of_words":
                    pred = _predict_bag_of_words(train=train, test=test, labels=labels)
                elif method == "char_ngram":
                    pred = _predict_char_ngram(train=train, test=test, labels=labels)
                else:
                    pred = _predict_length_punctuation(train=train, test=test, labels=labels)
                pred = replace(
                    pred,
                    train_labels=tuple(sorted({row["label"] for row in train})),
                    test_labels=tuple(sorted({row["label"] for row in test})),
                )
                if pred.status != "pass":
                    method_status = "fail"
                fold_rows.append(pred)

            method_views[view_name] = {
                "status": method_status,
                "folds": [
                    {
                        "domain": item.domain,
                        "train_count": item.train_count,
                        "test_count": item.test_count,
                        "predictions": item.predictions,
                        "metrics": dict(item.metrics),
                        "status": item.status,
                        "details": item.details,
                        "train_labels": list(item.train_labels),
                        "test_labels": list(item.test_labels),
                    }
                    for item in fold_rows
                ],
                "aggregate": dict(_aggregate_folds(fold_rows)),
            }
        methods[method] = {
            "status": method_status,
            "views": method_views,
        }

    unavailable = _unavailable_family_plan(config, config_file.parent)
    methods.update(unavailable)

    baseline_report = {
        "artifact_class": "behavioral-baseline-instrumentation",
        "empirical": False,
        "evidence_eligible": False,
        "claim_ids": [],
        "config_hash": _sha256_file(config_file),
        "provenance": {
            "cases_sha256": _sha256_file(cases_file),
            "snapshot_sha256": _sha256_file(snapshot_file),
            "config_sha256": _sha256_file(config_file),
        },
        "snapshot": {
            "status": snapshot.get("status"),
            "immutable_revision": snapshot.get("immutable_revision"),
            "split_membership_digest": snapshot.get("split_membership_digest"),
        },
        "cases": {
            "total_cases": len(canonical_cases),
            "label_count": len(labels),
            "domain_count": len(domains),
            "labels": labels,
            "domains": domains,
            "label_counts": {label: count for label, count in sorted(case_counts_by_label.items())},
            "domain_counts": {domain: count for domain, count in sorted(case_counts_by_domain.items())},
        },
        "methods": methods,
        "random_label_control": random_control,
        "config": {
            "non_claim_boundary": config.get("non_claim_boundary", {}),
            "method_families": sorted(method_requests),
            "allow_local_diagnostics": sorted(allow_local),
            "evaluation_views": list(_LODO_VIEWS),
        },
        "issues": case_issues,
        "shortcuts": {
            "provenance": provenance_shortcuts,
        },
    }

    gates = _evaluate_gates(
        snapshot=snapshot,
        cases=canonical_cases,
        methods=methods,
        baseline_gates_input=baseline_gates_input,
        random_control=random_control,
        shortcut_threshold=shortcut_threshold,
        shortcut_margin=shortcut_margin,
        baseline_config=config,
    )
    baseline_report["gates"] = gates
    return baseline_report


def _coerce_int(mapping: Mapping[str, Any], key: str, default: int, *, minimum: int = 0) -> int:
    value = mapping.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed < minimum:
        return minimum
    return parsed


def _coerce_float(mapping: Mapping[str, Any], key: str, default: float) -> float:
    value = mapping.get(key, default)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    return parsed


def _coerce_str_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def _canonicalize_cases(records: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid_cases: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for row in records:
        if not isinstance(row, Mapping):
            issues.append({"code": "invalid_case", "message": "case record is not an object"})
            continue

        case_id = str(row.get("case_id", "")).strip()
        if not case_id:
            issues.append({"code": "missing_case_id"})
            continue

        domain = str(row.get("domain", "")).strip() or "unknown"
        problem = str(row.get("problem", "")).strip()
        labels = row.get("labels")
        labels_set = _coerce_labels(labels)
        if not labels_set:
            issues.append({"code": "invalid_labels", "case_id": case_id})
            continue
        if len(set(labels_set)) != 1:
            issues.append(
                {
                    "code": "non_canonical_labels",
                    "case_id": case_id,
                    "labels": sorted(set(labels_set)),
                }
            )
            continue

        valid_cases.append(
            {
                "case_id": case_id,
                "domain": domain,
                "source_type": _canonical_text(row.get("provenance", {}).get("source_type") if isinstance(row.get("provenance"), Mapping) else None),
                "template_id": _canonical_text(row.get("provenance", {}).get("template_id") if isinstance(row.get("provenance"), Mapping) else None),
                "problem": problem,
                "solution": str(row.get("solution", "")).strip(),
                "initial_state": str(row.get("initial_state", "")).strip(),
                "desired_improvement": str(row.get("desired_improvement", "")).strip(),
                "worsening_consequence": str(row.get("worsening_consequence", "")).strip(),
                "transformation": str(row.get("transformation", "")).strip(),
                "resulting_state": str(row.get("resulting_state", "")).strip(),
                "constraints": _coerce_text_list(row.get("constraints", [])),
                "label": labels_set[0],
            }
        )
    return valid_cases, issues


def _coerce_labels(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for entry in values:
        if not isinstance(entry, Mapping):
            continue
        value = entry.get("principle")
        if isinstance(value, str):
            name = value.strip().lower()
            if name:
                result.append(name)
    return result


def _coerce_text_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text:
                out.append(text)
    return out


def _canonical_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _cases_to_text(cases: list[dict[str, Any]], *, view_name: str) -> list[dict[str, Any]]:
    output = []
    fields = _VIEW_TEXT_FIELDS.get(view_name)
    if not fields:
        fields = ("problem",)
    for case in cases:
        tokens: list[str] = []
        for field_name in fields:
            if field_name == "constraints":
                tokens.extend(_coerce_text_list(case.get("constraints", [])))
            else:
                value = str(case.get(field_name, "")).strip()
                if value:
                    tokens.append(value)
        text = " ".join(tokens).strip()
        output.append({
            "case_id": case["case_id"],
            "domain": case["domain"],
            "label": case["label"],
            "text": text,
        })
    return output


def _leave_one_domain_out_folds(cases: list[dict[str, Any]]) -> list:
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_domain[case.get("domain", "unknown")].append(case)

    folds = []
    for domain in sorted(by_domain):
        test = by_domain[domain]
        train = [row for key, rows in by_domain.items() if key != domain for row in rows]
        if not train or not test:
            continue
        folds.append((domain, (train, test)))
    return folds


def _predict_majority(train: list[dict[str, Any]], test: list[dict[str, Any]], labels: list[str]) -> FoldResult:
    counts = Counter(row["label"] for row in train)
    prediction = _majority_label(counts, labels)
    preds = [
        {"case_id": row["case_id"], "truth": row["label"], "prediction": prediction}
        for row in test
    ]
    metrics = _classification_metrics(
        y_true=[row["label"] for row in test],
        y_pred=[prediction for _ in test],
        label_space=labels,
    )
    return FoldResult(
        domain=test[0]["domain"] if test else "",
        train_count=len(train),
        test_count=len(test),
        predictions=preds,
        metrics=metrics,
        status="pass" if test else "fail",
    )


def _predict_keyword(train: list[dict[str, Any]], test: list[dict[str, Any]], labels: list[str]) -> FoldResult:
    if not train or not test:
        return FoldResult(test[0]["domain"] if test else "", len(train), len(test), [], _empty_metrics(), "fail", "insufficient data")

    vocab = {label: Counter() for label in labels}
    total = Counter()
    for row in train:
        label = row["label"]
        tokens = _tokenize(row["text"])
        vocab[label].update(tokens)
        total.update(tokens)

    if not total:
        return _predict_majority(train, test, labels)

    preds = []
    for row in test:
        tokens = _tokenize(row["text"])
        scores: dict[str, float] = {}
        for label in labels:
            prior = len(vocab[label]) / max(1, sum(vocab[cls].total() for cls in labels))
            overlap = sum(vocab[label].get(token, 0) for token in tokens)
            scores[label] = prior * (1 + overlap)

        pred = _tie_break(scores)
        preds.append({"case_id": row["case_id"], "truth": row["label"], "prediction": pred})

    metrics = _classification_metrics([row["label"] for row in test], [p["prediction"] for p in preds], labels)
    return FoldResult(
        domain=test[0]["domain"],
        train_count=len(train),
        test_count=len(test),
        predictions=preds,
        metrics=metrics,
        status="pass",
    )


def _predict_bag_of_words(train: list[dict[str, Any]], test: list[dict[str, Any]], labels: list[str]) -> FoldResult:
    if not train:
        return FoldResult(test[0]["domain"] if test else "", len(train), len(test), [], _empty_metrics(), "fail", "insufficient data")

    alpha = 1.0
    class_tokens: dict[str, Counter[str]] = {label: Counter() for label in labels}
    for row in train:
        cls = row["label"]
        class_tokens[cls].update(_tokenize(row["text"]))

    class_total = {label: sum(class_tokens[label].values()) for label in labels}
    vocab = sorted({tok for counts in class_tokens.values() for tok in counts})
    v_size = max(1, len(vocab))
    denom_cache = {cls: float(class_total[cls] + alpha * v_size) for cls in labels}

    preds = []
    for row in test:
        tokens = _tokenize(row["text"])
        scores: dict[str, float] = {}
        for cls in labels:
            prior = class_total[cls] / max(1.0, float(sum(class_total.values())))
            logp = _safe_log(prior)
            for token in tokens:
                count = class_tokens[cls].get(token, 0) + alpha
                logp += _safe_log(float(count) / denom_cache[cls])
            scores[cls] = logp
        pred = _tie_break(scores)
        preds.append({"case_id": row["case_id"], "truth": row["label"], "prediction": pred})

    metrics = _classification_metrics([row["label"] for row in test], [item["prediction"] for item in preds], labels)
    return FoldResult(
        domain=test[0]["domain"],
        train_count=len(train),
        test_count=len(test),
        predictions=preds,
        metrics=metrics,
        status="pass",
    )


def _predict_char_ngram(train: list[dict[str, Any]], test: list[dict[str, Any]], labels: list[str]) -> FoldResult:
    if not train:
        return FoldResult(test[0]["domain"] if test else "", len(train), len(test), [], _empty_metrics(), "fail", "insufficient data")

    profiles: dict[str, Counter[str]] = {label: Counter() for label in labels}
    for row in train:
        cls = row["label"]
        profiles[cls].update(_char_ngrams(_normalize_text(row["text"])))

    norm = {cls: sqrt(sum(v * v for v in counts.values())) for cls, counts in profiles.items()}

    preds = []
    for row in test:
        sample = Counter(_char_ngrams(_normalize_text(row["text"])))
        sample_norm = sqrt(sum(v * v for v in sample.values()))
        scores: dict[str, float] = {}
        for cls in labels:
            num = sum(sample[tok] * profiles[cls].get(tok, 0) for tok in sample)
            denom = max(1e-9, norm[cls] * max(sample_norm, 1e-9))
            scores[cls] = num / denom

        if not any(v > 0.0 for v in scores.values()):
            pred = _majority_label(Counter(row["label"] for row in train), labels)
        else:
            pred = _tie_break(scores)
        preds.append({"case_id": row["case_id"], "truth": row["label"], "prediction": pred})

    metrics = _classification_metrics([row["label"] for row in test], [item["prediction"] for item in preds], labels)
    return FoldResult(
        domain=test[0]["domain"],
        train_count=len(train),
        test_count=len(test),
        predictions=preds,
        metrics=metrics,
        status="pass",
    )


def _predict_length_punctuation(
    train: list[dict[str, Any]],
    test: list[dict[str, Any]],
    labels: list[str],
) -> FoldResult:
    """Nearest-centroid diagnostic using only length and punctuation shape."""
    if not train or not test:
        return FoldResult(
            test[0]["domain"] if test else "", len(train), len(test), [],
            _empty_metrics(), "fail", "insufficient data",
        )

    train_vectors = [_length_punctuation_features(row["text"]) for row in train]
    dimensions = len(train_vectors[0])
    means = [sum(vector[index] for vector in train_vectors) / len(train_vectors) for index in range(dimensions)]
    scales = []
    for index, mean in enumerate(means):
        variance = sum((vector[index] - mean) ** 2 for vector in train_vectors) / len(train_vectors)
        scales.append(max(sqrt(variance), 1.0e-9))

    def standardized(text: str) -> tuple[float, ...]:
        vector = _length_punctuation_features(text)
        return tuple((value - mean) / scale for value, mean, scale in zip(vector, means, scales))

    centroids: dict[str, tuple[float, ...]] = {}
    for label in labels:
        members = [standardized(row["text"]) for row in train if row["label"] == label]
        if members:
            centroids[label] = tuple(
                sum(vector[index] for vector in members) / len(members)
                for index in range(dimensions)
            )

    predictions: list[dict[str, str]] = []
    for row in test:
        vector = standardized(row["text"])
        scores = {
            label: -sum((value - centroid[index]) ** 2 for index, value in enumerate(vector))
            for label, centroid in centroids.items()
        }
        prediction = _tie_break(scores) if scores else _majority_label(Counter(item["label"] for item in train), labels)
        predictions.append({"case_id": row["case_id"], "truth": row["label"], "prediction": prediction})

    metrics = _classification_metrics(
        [row["label"] for row in test],
        [row["prediction"] for row in predictions],
        labels,
    )
    return FoldResult(
        domain=test[0]["domain"], train_count=len(train), test_count=len(test),
        predictions=predictions, metrics=metrics, status="pass",
    )


def _run_random_label_control(
    *,
    canonical_cases: list[dict[str, Any]],
    labels: list[str],
    random_seed: int,
    random_permutations: int,
    minimum_training_cases_per_label: int,
    minimum_cases_per_held_out_domain: int,
    minimum_cases_per_label_per_domain: int,
    allow_local: set[str],
) -> dict[str, Any]:
    if random_permutations < 1 or not labels or len(labels) < 2:
        return {
            "status": "invalid",
            "seed": random_seed,
            "permutations": max(0, random_permutations),
            "views": {},
            "reason": "insufficient setup",
        }

    rng = Random(random_seed)
    views_data = {
        view_name: _cases_to_text(canonical_cases, view_name=view_name)
        for view_name in _LODO_VIEWS
    }

    per_view: dict[str, Any] = {}
    for view_name, view_cases in views_data.items():
        folds = _leave_one_domain_out_folds(view_cases)
        fold_rows: list[dict[str, Any]] = []
        if not folds:
            per_view[view_name] = {
                "status": "invalid",
                "reason": "no complete folds",
                "folds": [],
                "support_adequate": False,
            }
            continue

        fold_support_ok = True
        for domain, (train, test) in folds:
            test_labels = [row["label"] for row in test]
            test_counts = Counter(test_labels)
            train_labels = [row["label"] for row in train]
            train_counts = Counter(train_labels)
            support_ok = (
                len(test) >= minimum_cases_per_held_out_domain
                and len(test_labels) > 0
                and set(test_counts) == set(labels)
                and all(count >= minimum_cases_per_label_per_domain for count in test_counts.values())
                and len(train) >= len(labels) * minimum_training_cases_per_label
                and set(train_counts) == set(labels)
                and all(count >= minimum_training_cases_per_label for count in train_counts.values())
            )
            fold_support_ok = fold_support_ok and support_ok

            permutations: list[dict[str, Any]] = []
            macro_f1_values: list[float] = []
            for index in range(random_permutations):
                shuffled = train_labels.copy()
                rng.shuffle(shuffled)
                permuted_train = [
                    {
                        "case_id": train_row["case_id"],
                        "domain": train_row["domain"],
                        "text": train_row["text"],
                        "label": permuted_label,
                    }
                    for train_row, permuted_label in zip(train, shuffled)
                ]
                perm_result = _predict_bag_of_words(
                    train=permuted_train,
                    test=[
                        {
                            "case_id": row["case_id"],
                            "domain": row["domain"],
                            "text": row["text"],
                            "label": row["label"],
                        }
                        for row in test
                    ],
                    labels=labels,
                )
                metrics = perm_result.metrics if isinstance(perm_result.metrics, Mapping) else _empty_metrics()
                macro_f1_values.append(float(metrics.get("macro_f1", 0.0)))
                permutations.append(
                    {
                        "permutation": index,
                        "metrics": dict(metrics),
                        "train_count": len(train),
                        "test_count": len(test),
                        "label_distribution": _label_distribution(shuffled) if support_ok else {},
                    }
                )

            fold_rows.append(
                {
                    "domain": domain,
                    "support_adequate": support_ok,
                    "test_count": len(test),
                    "permutations": permutations,
                    "macrof1_distribution_quantiles": _quantile_summary(macro_f1_values) if support_ok else {},
                    "accuracy_distribution": {},
                    "macro_f1_distribution": {},
                }
            )

        per_view[view_name] = {
            "status": "pass" if fold_support_ok else "invalid",
            "reason": None if fold_support_ok else "insufficient support for permutation distribution",
            "folds": fold_rows,
            "support_adequate": fold_support_ok,
            "minimum_training_cases_per_label": minimum_training_cases_per_label,
            "minimum_cases_per_held_out_domain": minimum_cases_per_held_out_domain,
        }

    overall_pass = all(v.get("status") == "pass" for v in per_view.values()) if per_view else False
    return {
        "status": "pass" if overall_pass else "invalid",
        "seed": random_seed,
        "permutations": random_permutations,
        "minimum_training_cases_per_label": minimum_training_cases_per_label,
        "minimum_cases_per_held_out_domain": minimum_cases_per_held_out_domain,
        "minimum_cases_per_label_per_domain": minimum_cases_per_label_per_domain,
        "allow_local_diagnostics": sorted(allow_local),
        "views": per_view,
        "reason": None if overall_pass else "insufficient support for at least one held-out fold",
    }


def _quantile_summary(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {}
    ordered = sorted(values)
    n = len(ordered)
    return {
        "count": n,
        "min": ordered[0],
        "p25": ordered[n // 4],
        "p50": ordered[n // 2],
        "p75": ordered[(3 * n) // 4],
        "max": ordered[-1],
    }


def _classification_metrics(y_true: list[str], y_pred: list[str], label_space: Iterable[str]) -> dict[str, float]:
    labels = sorted(set(label_space))
    if not labels or not y_true:
        return {"accuracy": 0.0, "macro_f1": 0.0, "balanced_accuracy": 0.0}

    total = len(y_true)
    accuracy = sum(1 for truth, pred in zip(y_true, y_pred) if truth == pred) / float(total)

    f1_scores = []
    recalls = []
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        precision = tp / float(tp + fp) if (tp + fp) else 0.0
        recall = tp / float(tp + fn) if (tp + fn) else 0.0
        denom = precision + recall
        f1_scores.append(2 * precision * recall / denom if denom else 0.0)
        recalls.append(recall)

    return {
        "accuracy": accuracy,
        "macro_f1": sum(f1_scores) / len(f1_scores) if f1_scores else 0.0,
        "balanced_accuracy": sum(recalls) / len(recalls) if recalls else 0.0,
    }


def _empty_metrics() -> dict[str, float]:
    return {"accuracy": 0.0, "macro_f1": 0.0, "balanced_accuracy": 0.0}


def _aggregate_folds(folds: list[FoldResult]) -> dict[str, float]:
    if not folds:
        return _empty_metrics()
    sum_accuracy = sum(f.metrics["accuracy"] for f in folds)
    sum_macro_f1 = sum(f.metrics["macro_f1"] for f in folds)
    sum_balanced = sum(f.metrics["balanced_accuracy"] for f in folds)
    total = len(folds)
    return {
        "accuracy": sum_accuracy / total,
        "macro_f1": sum_macro_f1 / total,
        "balanced_accuracy": sum_balanced / total,
    }


def _hash_from_family_entry(entry: Mapping[str, Any]) -> dict[str, str] | None:
    if not isinstance(entry, Mapping):
        return None
    sha = entry.get("sha256")
    digest = entry.get("digest")
    if isinstance(sha, str) and re.fullmatch(r"[a-f0-9]{64}", sha):
        return {"sha256": sha}
    if isinstance(digest, str) and re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
        return {"digest": digest}
    return None


def _unavailable_family_plan(config: Mapping[str, Any], config_root: Path) -> dict[str, Any]:
    families = config.get("families")
    if not isinstance(families, Mapping):
        families = {}

    out: dict[str, Any] = {}
    for family in _UNAVAILABLE_FAMILIES:
        entry = families.get(family, {}) if isinstance(families, Mapping) else {}
        if not isinstance(entry, Mapping):
            out[family] = {
                "status": "not_run",
                "reason": "invalid family config block",
                "hash": None,
            }
            continue

        hash_value = _hash_from_family_entry(entry)
        receipt_error = _verify_external_receipt(entry, family, config_root)
        if entry.get("status") == "completed" and hash_value and receipt_error is None:
            out[family] = {
                "status": "completed",
                "reason": None,
                "hash": hash_value,
                "receipt": str(entry.get("receipt_path")),
            }
        else:
            out[family] = {
                "status": "not_run",
                "reason": receipt_error or "dependency-free run; hash-backed adapter inputs not available",
                "hash": None,
            }
    return out


def _verify_external_receipt(entry: Mapping[str, Any], family: str, config_root: Path) -> str | None:
    receipt_value = entry.get("receipt_path")
    expected_sha = entry.get("sha256")
    if not isinstance(receipt_value, str) or not receipt_value.strip():
        return "hash-backed adapter receipt not configured"
    receipt_relative = Path(receipt_value)
    if receipt_relative.is_absolute() or ".." in receipt_relative.parts:
        return "adapter receipt path must be relative and contained by the config directory"
    receipt_path = (config_root / receipt_relative).resolve()
    try:
        receipt_path.relative_to(config_root.resolve())
    except ValueError:
        return "adapter receipt path escapes the config directory"
    if not receipt_path.is_file():
        return "adapter receipt file is missing"
    if not isinstance(expected_sha, str) or _sha256_file(receipt_path) != expected_sha:
        return "adapter receipt hash mismatch"
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "adapter receipt is not valid JSON"
    if not isinstance(receipt, Mapping):
        return "adapter receipt must be an object"
    required_boundary = (
        receipt.get("artifact_class") == "behavioral-baseline-adapter-receipt"
        and receipt.get("family") == family
        and receipt.get("status") == "completed"
        and receipt.get("empirical") is False
        and receipt.get("evidence_eligible") is False
        and receipt.get("claim_ids") == []
    )
    if not required_boundary:
        return "adapter receipt contract or non-claim boundary is invalid"
    return None


def _evaluate_gates(
    *,
    snapshot: Mapping[str, Any],
    cases: list[dict[str, Any]],
    baseline_gates_input: Mapping[str, Any],
    methods: Mapping[str, Any],
    random_control: Mapping[str, Any],
    shortcut_threshold: float,
    shortcut_margin: float,
    baseline_config: Mapping[str, Any],
) -> list[dict[str, str]]:
    g1_pass, g1_msg = _gate_b1(snapshot)
    g2_pass, g2_msg = _gate_b2(
        cases=cases,
        minimum_labels=baseline_gates_input.get("minimum_labels", 0),
        minimum_domains=baseline_gates_input.get("minimum_domains", 0),
        minimum_cases_per_label=baseline_gates_input.get("minimum_cases_per_label", 0),
        minimum_cases_per_held_out_domain=baseline_gates_input.get("minimum_cases_per_held_out_domain", 0),
        minimum_cases_per_label_per_domain=baseline_gates_input.get("minimum_cases_per_label_per_domain", 0),
    )
    g3_pass, g3_msg = _gate_b3(methods, baseline_gates_input)
    g4_pass, g4_msg = _gate_b4(methods)
    g5_pass, g5_msg = _gate_b5(methods, baseline_gates_input)
    g6_pass, g6_msg = _gate_b6(random_control)
    g7_pass, g7_msg = _gate_b7(methods, g2_pass and g5_pass, shortcut_threshold, shortcut_margin)
    g8_pass, g8_msg = _gate_b8(baseline_config)

    return [
        {"gate": "B1", "status": "pass" if g1_pass else "fail", "details": g1_msg},
        {"gate": "B2", "status": "pass" if g2_pass else "fail", "details": g2_msg},
        {"gate": "B3", "status": "pass" if g3_pass else "fail", "details": g3_msg},
        {"gate": "B4", "status": "pass" if g4_pass else "fail", "details": g4_msg},
        {"gate": "B5", "status": "pass" if g5_pass else "fail", "details": g5_msg},
        {"gate": "B6", "status": "pass" if g6_pass else "fail", "details": g6_msg},
        {"gate": "B7", "status": "pass" if g7_pass else "fail", "details": g7_msg},
        {"gate": "B8", "status": "pass" if g8_pass else "fail", "details": g8_msg},
    ]


def _gate_b1(snapshot: Mapping[str, Any]) -> tuple[bool, str]:
    status = snapshot.get("status")
    if status != "pass":
        return False, "snapshot status is not pass"

    imm = snapshot.get("immutable_revision")
    digest = snapshot.get("split_membership_digest")
    if not isinstance(imm, str) or not imm:
        return False, "snapshot immutable_revision missing"
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        return False, "snapshot split_membership_digest missing or invalid"
    return True, "snapshot status pass and immutable hash fields present"


def _gate_b2(
    *,
    cases: list[dict[str, Any]],
    minimum_labels: int,
    minimum_domains: int,
    minimum_cases_per_label: int,
    minimum_cases_per_held_out_domain: int,
    minimum_cases_per_label_per_domain: int,
) -> tuple[bool, str]:
    labels = Counter(item["label"] for item in cases)
    domains = Counter(item["domain"] for item in cases)

    if len(labels) < minimum_labels:
        return False, f"too few labels: {len(labels)} < {minimum_labels}"
    if len(domains) < minimum_domains:
        return False, f"too few domains: {len(domains)} < {minimum_domains}"

    for label, count in sorted(labels.items()):
        if count < minimum_cases_per_label:
            return False, f"insufficient count for label '{label}': {count} < {minimum_cases_per_label}"

    for domain, count in sorted(domains.items()):
        if count < minimum_cases_per_held_out_domain:
            return False, f"insufficient cases for domain '{domain}': {count} < {minimum_cases_per_held_out_domain}"

    cells = Counter((item["label"], item["domain"]) for item in cases)
    for label in sorted(labels):
        for domain in sorted(domains):
            count = cells.get((label, domain), 0)
            if count < minimum_cases_per_label_per_domain:
                return False, (
                    f"insufficient label-domain cell '{label}'/'{domain}': "
                    f"{count} < {minimum_cases_per_label_per_domain}"
                )

    return True, "minimum label/domain and support constraints met"


def _gate_b3(methods: Mapping[str, Any], baseline_gates_input: Mapping[str, Any]) -> tuple[bool, str]:
    required = baseline_gates_input.get("requested_methods", _REQUIRED_METHODS)
    for method in _REQUIRED_METHODS:
        if method not in required:
            continue
        payload = methods.get(method)
        if not isinstance(payload, Mapping):
            return False, f"{method} missing"
        views = payload.get("views")
        if not isinstance(views, Mapping):
            return False, f"{method} missing views"
        if set(views.keys()) != set(_LODO_VIEWS):
            return False, f"{method} must include all baseline views"
        for view_name in _LODO_VIEWS:
            row = views.get(view_name)
            if not isinstance(row, Mapping):
                return False, f"{method}/{view_name} invalid view payload"
            folds = row.get("folds")
            if not isinstance(folds, list) or not folds:
                return False, f"{method}/{view_name} has empty folds"
    return True, "required local methods and all frozen views present"


def _gate_b4(methods: Mapping[str, Any]) -> tuple[bool, str]:
    for family in _UNAVAILABLE_FAMILIES:
        payload = methods.get(family)
        if not isinstance(payload, Mapping):
            return False, f"missing required family: {family}"
        status = payload.get("status")
        if status != "completed":
            return False, f"required family {family} not completed"
        hash_value = payload.get("hash")
        if not isinstance(hash_value, Mapping) or not (hash_value.get("sha256") or hash_value.get("digest")):
            return False, f"required family {family} missing hash-backed inputs"
    return True, "all required families completed with hash-backed inputs"


def _gate_b5(methods: Mapping[str, Any], baseline_gates_input: Mapping[str, Any]) -> tuple[bool, str]:
    required_methods = baseline_gates_input.get("requested_methods", _REQUIRED_METHODS)
    if not isinstance(required_methods, Sequence):
        required_methods = _REQUIRED_METHODS

    expected_labels = set(baseline_gates_input.get("labels", []))
    expected_domains = set(baseline_gates_input.get("domains", []))
    # exact fold coverage by domain and label per view for each required local method
    for method in required_methods:
        payload = methods.get(method)
        if not isinstance(payload, Mapping):
            return False, f"missing method payload {method}"
        views = payload.get("views")
        if not isinstance(views, Mapping):
            return False, f"{method} missing views"

        for view_name in _LODO_VIEWS:
            view = views.get(view_name)
            if not isinstance(view, Mapping):
                return False, f"{method}/{view_name} missing"
            folds = view.get("folds")
            if not isinstance(folds, list) or not folds:
                return False, f"{method}/{view_name} has empty folds"
            if {str(fold.get("domain")) for fold in folds} != expected_domains:
                return False, f"{method}/{view_name} does not cover every held-out domain"
            for fold in folds:
                if int(fold.get("test_count", 0)) <= 0 or int(fold.get("train_count", 0)) <= 0:
                    return False, f"{method}/{view_name}/{fold.get('domain', 'unknown')} has empty train/test"
                if set(fold.get("train_labels", [])) != expected_labels:
                    return False, f"{method}/{view_name}/{fold.get('domain', 'unknown')} train labels incomplete"
                if set(fold.get("test_labels", [])) != expected_labels:
                    return False, f"{method}/{view_name}/{fold.get('domain', 'unknown')} test labels incomplete"
    return True, "exact LODO domain and label coverage satisfied for local methods"


def _gate_b6(random_control: Mapping[str, Any]) -> tuple[bool, str]:
    if random_control.get("status") != "pass":
        return False, str(random_control.get("reason", "random control invalid"))
    views = random_control.get("views", {})
    if not isinstance(views, Mapping) or not views:
        return False, "random control missing views"
    for view_name, payload in views.items():
        if not isinstance(payload, Mapping) or payload.get("status") != "pass":
            return False, f"random control view {view_name} invalid"
        for fold in payload.get("folds", []):
            if not isinstance(fold, Mapping) or not fold.get("support_adequate", False):
                return False, f"random control fold in {view_name} insufficiently supported"
            folds_permutations = fold.get("permutations", [])
            if not isinstance(folds_permutations, list) or not folds_permutations:
                return False, f"random control fold in {view_name} missing permutations"
    return True, "random-label control deterministic and adequate"


def _gate_b7(
    methods: Mapping[str, Any],
    prerequisite_ok: bool,
    shortcut_threshold: float,
    shortcut_margin: float,
) -> tuple[bool, str]:
    if not prerequisite_ok:
        return False, "not evaluable: B2/B5 invalid"

    shallow: list[tuple[str, str, float, float]] = []
    baseline_view = methods.get("majority", {}).get("views", {}) if isinstance(methods.get("majority"), Mapping) else {}
    for method in ("keyword_matching", "bag_of_words", "char_ngram", "length_punctuation"):
        method_payload = methods.get(method)
        if not isinstance(method_payload, Mapping):
            continue
        views = method_payload.get("views")
        if not isinstance(views, Mapping):
            continue
        for view_name in _LODO_VIEWS:
            view = views.get(view_name)
            if not isinstance(view, Mapping):
                continue
            agg = view.get("aggregate", {})
            if not isinstance(agg, Mapping):
                return False, "shallow aggregate missing"
            majority_agg = baseline_view.get(view_name, {}).get("aggregate", {})
            if not isinstance(majority_agg, Mapping):
                return False, "majority aggregate missing"
            shallow.append(
                (
                    method,
                    view_name,
                    float(agg.get("macro_f1", 0.0)),
                    float(majority_agg.get("macro_f1", 0.0)),
                )
            )

    if not shallow:
        return False, "not evaluable: no shallow aggregates available"

    risks: list[str] = []
    for view_name in _LODO_VIEWS:
        candidates = [item for item in shallow if item[1] == view_name]
        if not candidates:
            continue
        method, _, score, majority = max(candidates, key=lambda item: (item[2], item[0]))
        if score >= shortcut_threshold and (score - majority) >= shortcut_margin:
            risks.append(
                f"{view_name}:{method}={score:.4f} vs majority={majority:.4f}"
            )
    if risks:
        return False, "shortcut-risk: " + "; ".join(risks)
    return True, "shortcut risk check passed"


def _provenance_shortcut_diagnostics(cases: list[dict[str, Any]], labels: Sequence[str]) -> dict[str, Any]:
    return {
        "domain": _categorical_shortcut_diagnostic(cases, "domain", labels),
        "source_type": _categorical_shortcut_diagnostic(cases, "source_type", labels),
        "template": _categorical_shortcut_diagnostic(cases, "template_id", labels),
    }


def _categorical_shortcut_diagnostic(cases: list[dict[str, Any]], field: str, labels: Sequence[str]) -> dict[str, Any]:
    field_values = [row.get(field, "") for row in cases]
    if any(not isinstance(value, str) or not value.strip() for value in field_values):
        return {
            "status": "not_evaluable",
            "reason": f"{field} is not fully populated across cases",
            "macro_f1": None,
            "accuracy": None,
            "shortcut_detected": None,
            "evaluable": False,
        }
    values = [str(value).strip() for value in field_values]
    value_support = Counter(values)
    if len(value_support) < 2:
        return {
            "status": "not_evaluable",
            "reason": f"{field} has fewer than two categories",
            "macro_f1": None,
            "accuracy": None,
            "shortcut_detected": None,
            "evaluable": False,
        }
    unsupported = sorted(value for value, count in value_support.items() if count < 2)
    if unsupported:
        return {
            "status": "not_evaluable",
            "reason": f"{field} categories lack leave-one-out support: {unsupported}",
            "macro_f1": None,
            "accuracy": None,
            "shortcut_detected": None,
            "evaluable": False,
        }
    counts: dict[str, Counter[str]] = {}
    for value, row in zip(values, cases):
        counts.setdefault(value, Counter())[_as_safe_label(row.get("label"), labels)] += 1

    predictions: list[str] = []
    for value, row in zip(values, cases):
        value_counter = counts.get(value, Counter())
        value_counter = value_counter.copy()
        current_label = _as_safe_label(row.get("label"), labels)
        if current_label:
            value_counter[current_label] -= 1
            if value_counter[current_label] <= 0:
                del value_counter[current_label]
        if value_counter:
            prediction = _tie_break(_normalize_counts_to_scores(value_counter))
        else:
            prediction = _majority_label(Counter(row.get("label", "") for row in cases), sorted(labels))
        predictions.append(prediction)
    y_true = [_as_safe_label(row.get("label"), labels) for row in cases]
    if not y_true or not predictions:
        return {
            "status": "not_evaluable",
            "reason": "insufficient data for categorical diagnostic",
            "macro_f1": None,
            "accuracy": None,
            "shortcut_detected": None,
            "evaluable": False,
        }
    metrics = _classification_metrics(y_true, predictions, labels)
    macro_f1 = float(metrics.get("macro_f1", 0.0))
    accuracy = float(metrics.get("accuracy", 0.0))
    return {
        "status": "evaluable",
        "macro_f1": round(macro_f1, 12),
        "accuracy": round(accuracy, 12),
        "shortcut_detected": macro_f1 >= 0.75,
        "evaluable": True,
    }


def _as_safe_label(value: Any, labels: Sequence[str]) -> str:
    if isinstance(value, str) and value:
        return value
    return labels[0] if labels else ""


def _normalize_counts_to_scores(values: Mapping[str, int]) -> dict[str, float]:
    total = sum(values.values())
    if total <= 0:
        return {}
    return {label: count / total for label, count in values.items()}


def _gate_b8(config: Mapping[str, Any]) -> tuple[bool, str]:
    boundary = config.get("non_claim_boundary")
    if not isinstance(boundary, Mapping):
        return False, "non_claim_boundary missing"
    if boundary.get("empirical") is not False:
        return False, "non_claim_boundary.empirical must be false"
    if boundary.get("evidence_eligible") is not False:
        return False, "non_claim_boundary.evidence_eligible must be false"
    claim_ids = boundary.get("claim_ids")
    if claim_ids not in ([], None):
        if claim_ids != []:
            return False, "non_claim_boundary.claim_ids must be empty"
    return True, "non-claim boundary enforced"


def _tokenize(text: str) -> list[str]:
    return [match.group(0) for match in _TOKEN_RE.finditer(text.lower())]


def _length_punctuation_features(text: str) -> tuple[float, ...]:
    tokens = _tokenize(text)
    token_characters = sum(len(token) for token in tokens)
    return (
        float(len(text)),
        float(len(tokens)),
        float(token_characters) / max(1, len(tokens)),
        float(sum(text.count(mark) for mark in ".,;:!?")),
        float(text.count(",")),
        float(text.count(";")),
        float(text.count(":")),
        float(text.count("-")),
        float(text.count("(") + text.count(")")),
    )


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip().lower())


def _char_ngrams(text: str, n: int = 3) -> list[str]:
    if len(text) < n:
        return [text] if text else []
    return [text[i : i + n] for i in range(len(text) - n + 1)]


def _tie_break(scores: Mapping[str, float]) -> str:
    if not scores:
        return ""
    best = max(scores.values())
    return sorted(label for label, value in scores.items() if value == best)[0]


def _majority_label(counts: Counter[str], labels: list[str]) -> str:
    if not counts:
        return sorted(labels)[0] if labels else ""
    max_count = max(counts.values())
    return sorted(label for label, value in counts.items() if value == max_count)[0]


def _label_distribution(predictions: list[str]) -> dict[str, int]:
    return dict(Counter(predictions))


def _safe_log(value: float) -> float:
    if value <= 0.0:
        return -1.0e12
    return math.log(value)


def _read_jsonl(path: Path, label: str) -> list[Any]:
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise Lab03Error(f"{label} file not found: {path}") from exc

    rows: list[Any] = []
    for index, raw in enumerate(raw_lines, start=1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise Lab03Error(f"invalid JSONL in {label} {path}:{index}: {exc}") from exc
        rows.append(row)
    if not rows:
        raise Lab03Error(f"no records in {label}: {path}")
    return rows


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise Lab03Error(f"{label} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise Lab03Error(f"invalid JSON in {label}: {path}:{exc}") from exc

    if not isinstance(payload, dict):
        raise Lab03Error(f"{label} payload must be an object")
    return payload


def stable_json_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
