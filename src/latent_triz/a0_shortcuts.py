"""Automated surface-shortcut audit for A0 calibration corpus.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping


__all__ = ["audit_a0_shortcuts"]


_WORD_RE = re.compile(r"[a-z0-9]+")
_CONTROL_NAME = tuple[str, ...]
_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")
_LOWER_RE = re.compile(r"[a-z0-9]")

_DEFAULT_A0_CONTROLS = (
    "bag_of_words_baselines",
    "character_ngram_baselines",
    "length_and_punctuation_baselines",
    "style_and_template_baselines",
    "provenance_classifiers",
    "problem_only_label_prediction",
    "leave_one_domain_out_surface_evaluation",
    "duplicate_and_near_duplicate_detection",
    "family_leakage_detection",
    "random_label_controls",
    "random_partition_controls",
    "generic_action_taxonomy_controls",
    "generic_transformation_taxonomy_controls",
    "adjacent_principle_proxy_controls",
)


def audit_a0_shortcuts(
    cases_path: str | Path,
    targets_path: str | Path,
    protocol_path: str | Path,
) -> dict[str, Any]:
    """Run deterministic shortcut controls on calibration-only A0 split.

    Parameters
    ----------
    cases_path:
        Path to ``cases.jsonl`` (label-free problem surfaces).
    targets_path:
        Path to ``procedural-targets/calibration-targets.jsonl``. Sealed
        targets are physically separate and must never be passed here.
    protocol_path:
        Path to the protocol JSON containing shortcut thresholds and control list.
    """

    protocol = _load_protocol(protocol_path)
    controls_required = tuple(protocol.get("shortcut_evaluation", {}).get("a0_controls", _DEFAULT_A0_CONTROLS))
    threshold = _coerce_float(
        protocol.get("shortcut_evaluation", {}).get("macro_f1_threshold"), 0.65
    )
    margin_over_majority = _coerce_float(
        protocol.get("shortcut_evaluation", {}).get("margin_over_majority"), 0.10
    )

    case_records = _read_jsonl(cases_path)
    target_records = _read_jsonl(targets_path)
    joined, integrity_issues = _join_and_validate(case_records, target_records)
    cal_records = [row for row in joined if row.get("split") == "calibration"]
    sealed_count = len([row for row in joined if row.get("split") == "sealed"])

    control_results: dict[str, Any] = {}
    for name in controls_required:
        control_results[name] = {"status": "not_evaluable", "reason": "unknown control"}

    if integrity_issues:
        for issue in integrity_issues:
            control_results["integrity"] = {
                "status": "failed",
                "issues": integrity_issues,
            }
        control_results["overall"] = {
            "status": "failed",
            "non_interpretable": False,
            "missing_required_controls": [],
            "integrity_issues": integrity_issues,
        }

        return _build_report(
            protocol=protocol,
            controls=control_results,
            counts={"families": len({row["problem_family_id"] for row in joined}), "total_cases": len(joined), "calibration_cases": len(cal_records), "sealed_cases": sealed_count},
            integrity_status="failed",
            protocol_threshold=threshold,
            protocol_margin=margin_over_majority,
        )

    controls_data = _run_controls(cal_records, threshold, margin_over_majority)
    for name, payload in controls_data.items():
        if name in control_results:
            control_results[name] = payload

    # Keep deterministic explicit controls in report even if protocol does not list them.
    for missing in {
        "generic_action_taxonomy_controls",
        "generic_transformation_taxonomy_controls",
        "adjacent_principle_proxy_controls",
    } - set(controls_required):
        control_results[missing] = controls_data[missing]

    missing_required_controls = [
        item
        for item in controls_required
        if item
        not in {"random_label_controls", "random_partition_controls"}
        and control_results.get(item, {}).get("status") == "not_evaluable"
    ]
    integrity_status = "failed" if missing_required_controls else "pass"
    if missing_required_controls:
        control_results["missing_controls"] = {
            "status": "failed",
            "controls": missing_required_controls,
        }

    real_controls = {
        key: value
        for key, value in control_results.items()
        if key not in {"random_label_controls", "random_partition_controls", "integrity", "missing_controls"}
    }
    non_interpretable = any(
        value.get("status") == "non_interpretable"
        for value in real_controls.values()
        if isinstance(value, Mapping)
    )

    if integrity_status == "failed" or missing_required_controls:
        overall_status = "failed"
    elif non_interpretable:
        overall_status = "non_interpretable"
    else:
        overall_status = "pass"

    control_results["overall"] = {
        "status": overall_status,
        "non_interpretable": bool(non_interpretable),
        "missing_required_controls": list(missing_required_controls),
    }
    control_results["integrity"] = {"status": integrity_status, "issues": []}

    return _build_report(
        protocol=protocol,
        controls=control_results,
        counts={"families": len({row["problem_family_id"] for row in cal_records}), "total_cases": len(cal_records), "calibration_cases": len(cal_records), "sealed_cases": 0},
        integrity_status=integrity_status,
        protocol_threshold=threshold,
        protocol_margin=margin_over_majority,
    )


def _load_protocol(protocol_path: str | Path) -> dict[str, Any]:
    path = Path(protocol_path)
    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("protocol is not a JSON object")
    return payload


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _join_and_validate(
    case_records: list[dict[str, Any]],
    target_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    joined: list[dict[str, Any]] = []
    case_ids = [str(row.get("case_id", "")) for row in case_records]
    target_ids = [str(row.get("case_id", "")) for row in target_records]
    if len(case_ids) != len(set(case_ids)):
        issues.append({"code": "duplicate_case_id"})
    if len(target_ids) != len(set(target_ids)):
        issues.append({"code": "duplicate_target_case_id"})

    family_splits: dict[str, set[str]] = defaultdict(set)
    for case in case_records:
        family_splits[str(case.get("problem_family_id", ""))].add(str(case.get("split", "")))
    for family_id, splits in family_splits.items():
        if len(splits) != 1:
            issues.append({"code": "split_crosses_family", "family_id": family_id})

    calibration_cases = [row for row in case_records if row.get("split") == "calibration"]
    by_case = {str(row.get("case_id", "")): row for row in calibration_cases}
    target_by_case: dict[str, dict[str, Any]] = {}
    for target in target_records:
        case_id = str(target.get("case_id", ""))
        if target.get("split") != "calibration":
            issues.append({"code": "non_calibration_target_supplied", "case_id": case_id})
            continue
        target_by_case[case_id] = target

    for case_id, case in by_case.items():
        if case_id not in target_by_case:
            issues.append({"code": "missing_target", "case_id": case_id})
            continue
        target = target_by_case[case_id]
        family = str(case.get("problem_family_id", "")).strip()
        split = str(case.get("split", "")).strip()
        domain = str(case.get("domain", "")).strip() or "unknown"
        if not family:
            issues.append({"code": "missing_family", "case_id": case_id})
            continue
        if split != "calibration":
            issues.append({"code": "invalid_split", "case_id": case_id, "split": split})
            continue

        operator_family = str(target.get("operator_proxy_family", "")).strip()
        row = {
            "case_id": case_id,
            "problem_family_id": family,
            "solution_variant_id": str(case.get("solution_variant_id", "")).strip(),
            "domain": domain,
            "split": split,
            "problem": str(case.get("problem", "")),
            "constraints": _coerce_list(case.get("constraints", [])),
            "initial_state": str(case.get("initial_state", "")),
            "desired_improvement": str(case.get("desired_improvement", "")),
            "worsening_consequence": str(case.get("worsening_consequence", "")),
            "transformation": str(case.get("transformation", "")),
            "resulting_state": str(case.get("resulting_state", "")),
            "solution": str(case.get("solution", "")),
            "label": operator_family,
            "template_id": _coerce_text(
                target.get("provenance", {}).get("template_id")
                if isinstance(target.get("provenance"), Mapping)
                else None
            ),
            "generator_id": _coerce_text(
                target.get("provenance", {}).get("generator_id")
                if isinstance(target.get("provenance"), Mapping)
                else None
            ),
        }
        if not row["label"]:
            issues.append({"code": "missing_label", "case_id": case_id})
            continue
        if row["template_id"] in {"", "unknown"}:
            issues.append({"code": "missing_template", "case_id": case_id})
        if row["generator_id"] in {"", "unknown"}:
            issues.append({"code": "missing_generator", "case_id": case_id})
        joined.append(row)

    family_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in joined:
        family_map[row["problem_family_id"]].append(row)

    for family_id, rows in family_map.items():
        if not rows:
            issues.append({"code": "empty_family", "family_id": family_id})
            continue
        labels = sorted({row["label"] for row in rows})
        if labels != ["inversion_like", "segmentation_like"]:
            issues.append(
                {
                    "code": "non_opposite_labels_in_family",
                    "family_id": family_id,
                    "labels": ",".join(labels),
                }
            )
        if len({row.get("domain", "") for row in rows}) != 1:
            issues.append({"code": "domain_mismatch_in_family", "family_id": family_id})
    seen: dict[str, tuple[str, str]] = {}
    for row in joined:
        normalized = _normalize_text(_join_all_fields(row))
        key = normalized
        if key in seen and seen[key] != (row["problem_family_id"], row["split"]):
            issues.append(
                {
                    "code": "cross_family_duplicate",
                    "problem_family_id": row["problem_family_id"],
                    "other_family_id": seen[key][0],
                    "split": row["split"],
                }
            )
        seen[key] = (row["problem_family_id"], row["split"])

    return joined, issues


def _coerce_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip()
    return value if value else ""


def _coerce_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _coerce_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    return parsed


def _join_all_fields(row: Mapping[str, Any]) -> str:
    chunks = [
        str(row.get("problem", "")),
        str(row.get("initial_state", "")),
        str(row.get("desired_improvement", "")),
        str(row.get("worsening_consequence", "")),
        str(row.get("transformation", "")),
        str(row.get("resulting_state", "")),
        str(row.get("solution", "")),
        " ".join(_coerce_list(row.get("constraints", []))),
    ]
    return " ".join(part.strip() for part in chunks if str(part).strip())


def _normalize_text(value: str) -> str:
    text = value.strip().lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def _tokenize(value: str) -> list[str]:
    return _WORD_RE.findall(_normalize_text(value))


def _char_ngrams(value: str, min_n: int = 3, max_n: int = 5) -> list[str]:
    text = _normalize_text(value)
    if len(text) < min_n:
        return []
    grams: list[str] = []
    for n in range(min_n, max_n + 1):
        if len(text) < n:
            continue
        for index in range(len(text) - n + 1):
            grams.append(text[index : index + n])
    return grams


def _length_features(value: str) -> tuple[float, float, float, float]:
    text = value
    chars = len(text)
    digits = sum(1 for ch in text if ch.isdigit())
    punct = sum(1 for ch in text if (not ch.isalnum() and not ch.isspace()))
    words = len(_tokenize(text)) or 1
    return (
        float(chars),
        float(chars / max(words, 1)),
        float(punct / max(chars, 1)),
        float(digits / max(chars, 1)),
    )


def _row_text(row: Mapping[str, Any], *, view: str) -> str:
    if view == "problem_only":
        return str(row.get("problem", ""))
    return _join_all_fields(row)


def _build_feature(row: Mapping[str, Any], view: str) -> Any:
    text = _row_text(row, view=view)
    if view == "word_unigrams":
        return Counter(_tokenize(text))
    if view == "char_3_5_grams":
        return Counter(_char_ngrams(text))
    if view == "length_and_punctuation_baselines":
        return _length_features(text)
    if view == "template_provenance_categorical":
        return {
            "template_id": str(row.get("template_id", "")),
            "generator_id": str(row.get("generator_id", "")),
            "domain": str(row.get("domain", "")),
        }
    if view == "problem_only":
        return Counter(_tokenize(str(row.get("problem", ""))))
    if view == "generic_action_taxonomy_controls":
        return _keyword_features(str(row.get("transformation", "")), _ACTION_LEXICON)
    if view == "generic_transformation_taxonomy_controls":
        return _keyword_features(str(row.get("solution", "")), _TRANSFORMATION_LEXICON)
    if view == "adjacent_principle_proxy_controls":
        return _keyword_features(_join_all_fields(row), _ADJACENT_LEXICON)
    return _join_all_fields(row)


def _keyword_features(text: str, vocab: dict[str, list[str]]) -> dict[str, int]:
    tokens = Counter(_tokenize(text))
    return {
        label: sum(tokens[token] for token in keywords)
        for label, keywords in vocab.items()
    }


_ACTION_LEXICON = {
    "segmentation_like": [
        "divide",
        "segment",
        "partition",
        "split",
        "components",
        "decompose",
        "local",
        "distributed",
    ],
    "inversion_like": [
        "reverse",
        "invert",
        "swap",
        "exchange",
        "opposite",
        "central",
        "controller",
    ],
}

_TRANSFORMATION_LEXICON = {
    "segmentation_like": ["local", "stage", "system", "subsystem", "component", "parallel"],
    "inversion_like": ["system", "before", "after", "overall", "single", "global", "endpoint"],
}

_ADJACENT_LEXICON = {
    "segmentation_like": ["adjacent", "neighbor", "around", "near", "side", "proximity"],
    "inversion_like": ["far", "away", "isolate", "distance", "separate", "apart"],
}


def _evaluate_textual_control(
    rows: list[dict[str, Any]],
    view: str,
    threshold: float,
    margin: float,
) -> dict[str, Any]:
    if len(rows) < 4:
        return {"status": "not_evaluable", "aggregate": _empty_metrics(), "threshold": threshold, "margin": margin}

    labels = sorted({row["label"] for row in rows})
    folds = _leave_one_domain_out_folds(rows)
    if not folds:
        return {"status": "fail", "aggregate": _empty_metrics(), "reason": "no folds"}

    fold_metrics = []
    for domain, train, test in folds:
        if len(set(row["label"] for row in test)) < 2:
            continue
        train_features = [_build_feature(row, view=view) for row in train]
        test_features = [_build_feature(row, view=view) for row in test]
        y_true = [row["label"] for row in test]
        y_pred, train_labels = _nearest_centroid_predict(
            train_features,
            [row["label"] for row in train],
            test_features,
            labels,
        )
        metrics = _classification_metrics(y_true, y_pred, labels)
        majority = _majority_baseline_pred(train_labels, y_true)
        majority_metrics = _classification_metrics(y_true, majority, labels)
        margin_value = metrics["macro_f1"] - majority_metrics["macro_f1"]
        fold_metrics.append(
            {
                "domain": domain,
                "metrics": dict(metrics),
                "majority_metrics": dict(majority_metrics),
                "margin_over_majority": margin_value,
                "train_count": len(train),
                "test_count": len(test),
            }
        )
    if not fold_metrics:
        return {"status": "fail", "aggregate": _empty_metrics(), "reason": "insufficient support"}
    aggregate = _aggregate_folds(fold_metrics)
    margin = min(item["margin_over_majority"] for item in fold_metrics)
    status = (
        "non_interpretable"
        if (aggregate["macro_f1"] >= threshold and margin >= margin)
        else "pass"
    )
    return {
        "status": status,
        "aggregate": aggregate,
        "folds": fold_metrics,
        "threshold": threshold,
        "margin_over_majority": margin,
        "min_margin_over_majority": margin,
    }


def _evaluate_random_partition(
    rows: list[dict[str, Any]],
    controls: list[str],
    threshold: float,
    margin: float,
) -> dict[str, Any]:
    if len(rows) < 6:
        return {"status": "not_evaluable", "aggregate": _empty_metrics(), "seed": 0}

    labels = sorted({row["label"] for row in rows})
    if len(labels) < 2:
        return {"status": "fail", "aggregate": _empty_metrics(), "seed": 0}

    rng = random.Random(20260814)
    runs = []
    for index, control in enumerate(controls):
        order = list(rows)
        rng.shuffle(order)
        fold_size = max(1, len(order) // 5)
        diagnostics = []
        macro_f1_values: list[float] = []
        for fold_index in range(5):
            start = fold_index * fold_size
            end = len(order) if fold_index == 4 else (fold_index + 1) * fold_size
            test = order[start:end]
            if not test:
                continue
            test_ids = {row["case_id"] for row in test}
            train = [row for row in rows if row["case_id"] not in test_ids]
            y_true = [row["label"] for row in test]
            if len(set(y_true)) < 2:
                continue
            y_pred, _ = _nearest_centroid_predict(
                [_build_feature(row, view=control) for row in train],
                [row["label"] for row in train],
                [_build_feature(row, view=control) for row in test],
                labels,
            )
            metrics = _classification_metrics(y_true, y_pred, labels)
            macro_f1_values.append(metrics["macro_f1"])
            diagnostics.append(
                {
                    "fold": fold_index,
                    "metrics": dict(metrics),
                    "train_count": len(train),
                    "test_count": len(test),
                }
            )
        aggregate = _aggregate_metric_values(macro_f1_values)
        runs.append(
            {
                "control": control,
                "folds": diagnostics,
                "aggregate": aggregate,
            }
        )
    if runs:
        aggregate_macro = {
            "macro_f1": sum(run["aggregate"].get("macro_f1", 0.0) for run in runs) / len(runs),
            "accuracy": 0.0,
            "balanced_accuracy": 0.0,
        }
    else:
        aggregate_macro = _empty_metrics()
    status = (
        "non_interpretable"
        if aggregate_macro["macro_f1"] >= threshold
        and aggregate_macro["macro_f1"] - aggregate_macro.get("macro_f1_majority", 0.0) >= margin
        else "pass"
    )
    return {
        "status": status,
        "seed": 20260814,
        "runs": runs,
        "aggregate": aggregate_macro,
        "threshold": threshold,
        "margin_over_majority": margin,
    }


def _run_controls(
    rows: list[dict[str, Any]],
    threshold: float,
    margin: float,
) -> dict[str, dict[str, Any]]:
    controls = {
        "bag_of_words_baselines": _evaluate_textual_control(rows, "word_unigrams", threshold, margin),
        "character_ngram_baselines": _evaluate_textual_control(rows, "char_3_5_grams", threshold, margin),
        "length_and_punctuation_baselines": _evaluate_textual_control(
            rows, "length_and_punctuation_baselines", threshold, margin
        ),
        "style_and_template_baselines": _evaluate_textual_control(
            rows, "template_provenance_categorical", threshold, margin
        ),
        "provenance_classifiers": _evaluate_textual_control(
            rows, "template_provenance_categorical", threshold, margin
        ),
        "problem_only_label_prediction": _evaluate_textual_control(
            rows, "problem_only", threshold, margin
        ),
        "leave_one_domain_out_surface_evaluation": _evaluate_textual_control(
            rows, "word_unigrams", threshold, margin
        ),
        "duplicate_and_near_duplicate_detection": {
            "status": "pass",
            "reason": "no exact normalized duplicates across families/splits in calibration",
        },
        "family_leakage_detection": {
            "status": "pass",
            "families_checked": len({row["problem_family_id"] for row in rows}),
            "note": "all families hold one split and two opposite labels",
        },
        "random_label_controls": _evaluate_random_label(rows, threshold, margin),
        "random_partition_controls": _evaluate_random_partition(
            rows,
            ["word_unigrams", "problem_only", "template_provenance_categorical"],
            threshold,
            margin,
        ),
        "generic_action_taxonomy_controls": _evaluate_lexicon_controls(
            rows, "generic_action_taxonomy_controls", _ACTION_LEXICON, threshold, margin
        ),
        "generic_transformation_taxonomy_controls": _evaluate_lexicon_controls(
            rows,
            "generic_transformation_taxonomy_controls",
            _TRANSFORMATION_LEXICON,
            threshold,
            margin,
        ),
        "adjacent_principle_proxy_controls": _evaluate_lexicon_controls(
            rows,
            "adjacent_principle_proxy_controls",
            _ADJACENT_LEXICON,
            threshold,
            margin,
        ),
    }
    return controls


def _evaluate_random_label(
    rows: list[dict[str, Any]],
    threshold: float,
    margin: float,
) -> dict[str, Any]:
    if len(rows) < 6:
        return {"status": "not_evaluable", "macro_f1": 0.0, "seed": 0}
    labels = sorted({row["label"] for row in rows})
    if len(labels) < 2:
        return {"status": "fail", "seed": 20260814, "macro_f1": 0.0}

    base_rows = list(rows)
    true_labels = [row["label"] for row in base_rows]
    majorities = []
    macro_values = []
    rng = random.Random(20260814)

    for _ in range(30):
        permuted = list(base_rows)
        perm_labels = true_labels.copy()
        rng.shuffle(perm_labels)
        for row, label in zip(permuted, perm_labels):
            row["random_label"] = label
        folds = _leave_one_domain_out_folds(permuted)
        if not folds:
            continue
        fold_metrics = []
        for _domain, train, test in folds:
            train_labels = [row["random_label"] for row in train]
            if len(set(train_labels)) < 2 or len(set(row["label"] for row in test)) < 2:
                continue
            y_pred, _ = _nearest_centroid_predict(
                [_build_feature(row, view="word_unigrams") for row in train],
                train_labels,
                [_build_feature(row, view="word_unigrams") for row in test],
                labels,
            )
            metrics = _classification_metrics(
                [row["label"] for row in test],
                y_pred,
                labels,
            )
            majorities.append(
                _classification_metrics(
                    [row["label"] for row in test],
                    [_majority_label(train_labels)] * len(test),
                    labels,
                )
            )
            fold_metrics.append(metrics)
        if fold_metrics:
            macro_values.append(sum(item["macro_f1"] for item in fold_metrics) / len(fold_metrics))

    aggregate = _aggregate_from_macro(macro_values)
    status = "non_interpretable" if aggregate["macro_f1"] >= threshold else "pass"
    return {
        "status": status,
        "seed": 20260814,
        "permutations": 30,
        "aggregate": aggregate,
        "majority_macrof1": sum(item["macro_f1"] for item in majorities) / len(majorities) if majorities else 0.0,
        "threshold": threshold,
        "margin_over_majority": margin,
    }


def _evaluate_lexicon_controls(
    rows: list[dict[str, Any]],
    name: str,
    lexicon: dict[str, list[str]],
    threshold: float,
    margin: float,
) -> dict[str, Any]:
    if not rows:
        return {"name": name, "status": "not_evaluable", "aggregate": _empty_metrics()}

    if "action" in name or "transformation" in name:
        if name == "generic_action_taxonomy_controls":
            view = "generic_action_taxonomy_controls"
        elif name == "generic_transformation_taxonomy_controls":
            view = "generic_transformation_taxonomy_controls"
        else:
            view = "adjacent_principle_proxy_controls"
    else:
        view = "adjacent_principle_proxy_controls"

    labels = sorted({row["label"] for row in rows})
    folds = _leave_one_domain_out_folds(rows)
    fold_metrics = []
    for _domain, train, test in folds:
        if len(set(row["label"] for row in test)) < 2:
            continue
        y_pred: list[str] = []
        for row in test:
            counts = _keyword_features(_join_all_fields(row) if view != "problem_only" else str(row.get("problem", "")), lexicon)
            pred = max(counts, key=counts.get, default="")
            y_pred.append(pred or _majority_label([r["label"] for r in train] if train else labels))
        metrics = _classification_metrics([row["label"] for row in test], y_pred, labels)
        y_true = [row["label"] for row in test]
        majority = _majority_baseline_pred([row["label"] for row in train], y_true)
        majority_metrics = _classification_metrics(y_true, majority, labels)
        fold_metrics.append(
            {
                "metrics": dict(metrics),
                "majority_metrics": dict(majority_metrics),
                "margin_over_majority": metrics["macro_f1"] - majority_metrics["macro_f1"],
            }
        )
    if not fold_metrics:
        return {"name": name, "status": "not_evaluable", "aggregate": _empty_metrics()}
    aggregate = _aggregate_folds(fold_metrics)
    min_margin = min(fold["margin_over_majority"] for fold in fold_metrics)
    status = (
        "non_interpretable"
        if aggregate["macro_f1"] >= threshold and min_margin >= margin
        else "pass"
    )
    return {
        "name": name,
        "status": status,
        "aggregate": aggregate,
        "folds": fold_metrics,
        "threshold": threshold,
        "margin_over_majority": margin,
        "min_margin_over_majority": min_margin,
    }


def _leave_one_domain_out_folds(rows: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]], list[dict[str, Any]]]]:
    by_domain: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_domain[str(row.get("domain", "unknown"))].append(row)
    folds = []
    domains = sorted(by_domain)
    for domain in domains:
        test = by_domain[domain]
        train = [row for key, records in by_domain.items() if key != domain for row in records]
        if train and test:
            folds.append((domain, train, test))
    return folds


def _nearest_centroid_predict(
    train_features: list[Any],
    train_labels: list[str],
    test_features: list[Any],
    labels: list[str],
) -> tuple[list[str], list[str]]:
    if not train_features or not labels:
        return [], train_labels
    majority = _majority_label(train_labels)
    centroids = {}
    for label in labels:
        vectors = [feature for feature, lab in zip(train_features, train_labels) if lab == label]
        if not vectors:
            continue
        centroids[label] = _centroid(vectors)
    if len(centroids) < len(labels):
        return [majority] * len(test_features), labels

    predictions: list[str] = []
    for feature in test_features:
        distances = {
            label: _vector_distance(feature, centroid)
            for label, centroid in centroids.items()
        }
        if not distances:
            predictions.append(majority)
            continue
        best_label = min(distances.items(), key=lambda item: (item[1], item[0]))[0]
        predictions.append(best_label)
    return predictions, labels


def _centroid(vectors: list[Any]) -> Any:
    if not vectors:
        return {}
    first = vectors[0]
    if isinstance(first, Counter):
        counter = Counter()
        for vector in vectors:
            counter.update(vector)
        return {key: value / len(vectors) for key, value in counter.items()}
    if isinstance(first, dict):
        if all(isinstance(value, (int, float)) for value in first.values()):
            sums = Counter()
            for vector in vectors:
                sums.update(vector)
            return {key: value / len(vectors) for key, value in sums.items()}
        sums = Counter()
        for vector in vectors:
            if not isinstance(vector, Mapping):
                continue
            for key, value in vector.items():
                sums[f"{key}::{value}"] += 1
        return {key: value / len(vectors) for key, value in sums.items()}
    values = [tuple(float(v) for v in vector) for vector in vectors]
    dim = len(values[0])
    means = []
    for index in range(dim):
        means.append(sum(vec[index] for vec in values) / len(values))
    return tuple(means)


def _vector_distance(first: Any, second: Any) -> float:
    if isinstance(first, Mapping) and isinstance(second, Mapping):
        first_has_text = any(isinstance(value, str) for value in first.values())
        second_has_text = any(isinstance(value, str) for value in second.values())
        if first_has_text and not second_has_text:
            first = _encode_categorical_mapping(first)
        elif second_has_text and not first_has_text:
            second = _encode_categorical_mapping(second)
        return math.sqrt(
            sum((float(first.get(key, 0.0)) - float(second.get(key, 0.0))) ** 2
            for key in set(first) | set(second)
        ))
    if isinstance(first, tuple) and isinstance(second, tuple):
        dim = max(len(first), len(second))
        padded_a = tuple(float(first[i]) if i < len(first) else 0.0 for i in range(dim))
        padded_b = tuple(float(second[i]) if i < len(second) else 0.0 for i in range(dim))
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(padded_a, padded_b)))
    if isinstance(first, Counter) and isinstance(second, Mapping):
        return _vector_distance(dict(first), second)
    return 0.0


def _encode_categorical_mapping(row: Mapping[str, Any]) -> dict[str, float]:
    encoded: dict[str, float] = {}
    for key, value in row.items():
        encoded[f"{key}::{value}"] = 1.0
    return encoded


def _majority_label(labels: list[str]) -> str:
    if not labels:
        return "segmentation_like"
    counts = Counter(labels)
    max_count = max(counts.values())
    candidates = sorted(label for label, count in counts.items() if count == max_count)
    return candidates[0]


def _majority_baseline_pred(train_labels: list[str], test_labels: list[str]) -> list[str]:
    predicted = _majority_label(train_labels)
    return [predicted for _ in test_labels]


def _classification_metrics(y_true: list[str], y_pred: list[str], label_space: list[str]) -> dict[str, float]:
    if not y_true or not label_space:
        return _empty_metrics()
    total = len(y_true)
    accuracy = sum(1 for a, b in zip(y_true, y_pred) if a == b) / float(total)
    labels = sorted(label_space)
    f1_scores: list[float] = []
    recalls: list[float] = []
    for label in labels:
        tp = sum(1 for a, b in zip(y_true, y_pred) if a == label and b == label)
        fp = sum(1 for a, b in zip(y_true, y_pred) if a != label and b == label)
        fn = sum(1 for a, b in zip(y_true, y_pred) if a == label and b != label)
        precision = tp / float(tp + fp) if (tp + fp) else 0.0
        recall = tp / float(tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        f1_scores.append(f1)
        recalls.append(recall)
    return {
        "accuracy": accuracy,
        "macro_f1": sum(f1_scores) / len(f1_scores) if f1_scores else 0.0,
        "balanced_accuracy": sum(recalls) / len(recalls) if recalls else 0.0,
    }


def _empty_metrics() -> dict[str, float]:
    return {"accuracy": 0.0, "macro_f1": 0.0, "balanced_accuracy": 0.0}


def _aggregate_folds(folds: list[Mapping[str, Any]]) -> dict[str, float]:
    if not folds:
        return _empty_metrics()
    return {
        "accuracy": sum(fold["metrics"]["accuracy"] for fold in folds) / len(folds),
        "macro_f1": sum(fold["metrics"]["macro_f1"] for fold in folds) / len(folds),
        "balanced_accuracy": sum(fold["metrics"]["balanced_accuracy"] for fold in folds) / len(folds),
    }


def _aggregate_metric_values(values: list[float]) -> dict[str, float]:
    if not values:
        return {"macro_f1": 0.0, "accuracy": 0.0, "balanced_accuracy": 0.0}
    return {"macro_f1": sum(values) / len(values), "accuracy": 0.0, "balanced_accuracy": 0.0}


def _aggregate_from_macro(values: list[float]) -> dict[str, float]:
    if not values:
        return {"macro_f1": 0.0, "accuracy": 0.0, "balanced_accuracy": 0.0}
    return {"macro_f1": sum(values) / len(values), "accuracy": 0.0, "balanced_accuracy": 0.0}


def _build_report(
    *,
    protocol: Mapping[str, Any],
    controls: dict[str, Any],
    counts: Mapping[str, int],
    integrity_status: str,
    protocol_threshold: float,
    protocol_margin: float,
) -> dict[str, Any]:
    return {
        "artifact_class": "a0-shortcut-audit",
        "protocol_id": protocol.get("protocol_id", "unknown"),
        "empirical": True,
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": list(protocol.get("claim_ids", [])) if isinstance(protocol.get("claim_ids"), list) else [],
        "status": controls.get("overall", {}).get("status", "failed" if integrity_status == "failed" else "pass"),
        "counts": dict(counts),
        "controls": controls,
        "shortcut_threshold": protocol_threshold,
        "margin_over_majority": protocol_margin,
    }
