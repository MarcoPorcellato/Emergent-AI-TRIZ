"""Multi-rater integrity and agreement audit for blinded dataset annotations."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .validator import validate


class AnnotationAuditError(RuntimeError):
    """Raised when annotation audit inputs cannot be interpreted safely."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnnotationAuditError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AnnotationAuditError(f"{path}: expected an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AnnotationAuditError(f"cannot read {path}: {exc}") from exc
    for line_number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AnnotationAuditError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise AnnotationAuditError(f"{path}:{line_number}: expected an object")
        records.append(value)
    return records


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _case_display_hash(case: Mapping[str, Any]) -> str:
    canonical = {
        "case_id": case["case_id"],
        "domain": case["domain"],
        "problem": case["problem"],
        "constraints": case["constraints"],
        "initial_state": case["initial_state"],
        "desired_improvement": case["desired_improvement"],
        "worsening_consequence": case["worsening_consequence"],
        "transformation": case["transformation"],
        "resulting_state": case["resulting_state"],
    }
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _dataset_batch_hash(case_hashes: Mapping[str, str]) -> str:
    payload = json.dumps(
        [case_hashes[case_id] for case_id in sorted(case_hashes)],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _pairwise_agreement(labels: Sequence[str]) -> tuple[int, int]:
    pairs = list(itertools.combinations(labels, 2))
    return sum(left == right for left, right in pairs), len(pairs)


def _nominal_alpha_bycase(case_labels: dict[str, object]) -> float:
    observed_disagreement = 0.0
    category_counts: Counter[str] = Counter()
    total_codes = 0
    for raw_labels in case_labels.values():
        if isinstance(raw_labels, dict):
            labels = list(raw_labels.values())
        else:
            labels = list(raw_labels)  # type: ignore[list-item]
        if len(labels) < 2:
            continue
        unit_counts = Counter(labels)
        size = len(labels)
        observed_disagreement += (
            size * size - sum(count * count for count in unit_counts.values())
        ) / (size - 1)
        category_counts.update(labels)
        total_codes += size

    if total_codes < 2:
        return 1.0
    do = observed_disagreement / total_codes
    de = (
        total_codes * total_codes
        - sum(count * count for count in category_counts.values())
    ) / (total_codes * (total_codes - 1))
    if de == 0:
        return 1.0 if do == 0 else 0.0
    return 1.0 - (do / de)


def _ordinal_alpha_bycase(
    case_scores: Mapping[str, Mapping[str, Mapping[str, int]]], field: str
) -> float:
    units: list[list[int]] = []
    category_counts: Counter[int] = Counter()
    for rater_scores in case_scores.values():
        scores = [values[field] for values in rater_scores.values() if field in values]
        if len(scores) < 2:
            continue
        units.append(scores)
        category_counts.update(scores)
    total_codes = sum(category_counts.values())
    if total_codes < 2:
        return 1.0

    def distance(left: int, right: int) -> float:
        if left == right:
            return 0.0
        low, high = sorted((left, right))
        interval = sum(
            count for category, count in category_counts.items() if low <= category <= high
        ) - (category_counts[left] + category_counts[right]) / 2
        return interval * interval

    observed = 0.0
    for scores in units:
        size = len(scores)
        observed += sum(
            distance(left, right)
            for index, left in enumerate(scores)
            for other_index, right in enumerate(scores)
            if index != other_index
        ) / (size - 1)
    do = observed / total_codes
    expected = sum(
        left_count * right_count * distance(left, right)
        for left, left_count in category_counts.items()
        for right, right_count in category_counts.items()
        if left != right
    ) / (total_codes * (total_codes - 1))
    if expected == 0:
        return 1.0 if do == 0 else 0.0
    return 1.0 - (do / expected)


def _percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise AnnotationAuditError("cannot compute a percentile without values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _bootstrap_agreement_intervals(
    case_labels: Mapping[str, Mapping[str, str]],
    *,
    confidence_level: float,
    resamples: int,
    seed: int,
) -> dict[str, list[float]]:
    units = [
        dict(case_labels[case_id])
        for case_id in sorted(case_labels)
        if len(case_labels[case_id]) >= 2
    ]
    if not units:
        return {"raw_agreement": [0.0, 0.0], "nominal_alpha": [1.0, 1.0]}
    rng = random.Random(seed)
    raw_samples: list[float] = []
    alpha_samples: list[float] = []
    for _ in range(resamples):
        sampled = [units[rng.randrange(len(units))] for _ in units]
        matched = total = 0
        for labels in sampled:
            unit_matched, unit_total = _pairwise_agreement(list(labels.values()))
            matched += unit_matched
            total += unit_total
        raw_samples.append(matched / total if total else 0.0)
        alpha_samples.append(
            _nominal_alpha_bycase({str(index): labels for index, labels in enumerate(sampled)})
        )
    tail = (1.0 - confidence_level) / 2.0
    return {
        "raw_agreement": [_percentile(raw_samples, tail), _percentile(raw_samples, 1.0 - tail)],
        "nominal_alpha": [_percentile(alpha_samples, tail), _percentile(alpha_samples, 1.0 - tail)],
    }


def audit_annotations(
    *,
    cases_path: str | Path,
    guide_path: str | Path,
    annotation_schema_path: str | Path,
    annotation_paths: Iterable[str | Path],
    minimum_distinct_raters: int = 2,
    agreement_threshold: float = 0.8,
    maximum_abstention_rate: float = 0.2,
) -> dict[str, Any]:
    if minimum_distinct_raters < 2:
        raise AnnotationAuditError("minimum_distinct_raters must be at least 2")
    for name, value in (
        ("agreement_threshold", agreement_threshold),
        ("maximum_abstention_rate", maximum_abstention_rate),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise AnnotationAuditError(f"{name} must be in [0,1]")

    cases_file, guide_file, schema_file = Path(cases_path), Path(guide_path), Path(annotation_schema_path)
    cases, guide, schema = _read_jsonl(cases_file), _read_json(guide_file), _read_json(schema_file)
    paths = [Path(path) for path in annotation_paths]
    if len(paths) < minimum_distinct_raters:
        raise AnnotationAuditError(
            f"at least {minimum_distinct_raters} independent annotation files are required"
        )

    expected_case_hashes: dict[str, str] = {}
    case_ids: list[str] = []
    for case in cases:
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise AnnotationAuditError("every case requires case_id")
        if case_id in expected_case_hashes:
            raise AnnotationAuditError(f"duplicate case_id: {case_id}")
        try:
            expected_case_hashes[case_id] = _case_display_hash(case)
        except KeyError as exc:
            raise AnnotationAuditError(f"case {case_id} missing field {exc}") from exc
        case_ids.append(case_id)
    if len(set(case_ids)) != len(case_ids):
        raise AnnotationAuditError("case IDs must be unique")
    expected_case_ids = set(case_ids)
    expected_batch_hash = _dataset_batch_hash(expected_case_hashes)

    labels = guide.get("labels")
    abstention = guide.get("abstention")
    policy = guide.get("agreement_policy")
    if not isinstance(labels, list) or not isinstance(abstention, dict) or not isinstance(policy, dict):
        raise AnnotationAuditError("guide requires labels, abstention, and agreement_policy")
    allowed_labels = {item["id"] for item in labels if isinstance(item, dict) and isinstance(item.get("id"), str)}
    if len(allowed_labels) != len(labels) or len(allowed_labels) < 4:
        raise AnnotationAuditError("guide requires exactly four unique labels")
    required_labels = {"segmentation", "inversion", "both", "other"}
    if allowed_labels != required_labels:
        raise AnnotationAuditError("guide labels must be exactly segmentation, inversion, both, other")
    abstention_id = abstention.get("id")
    if not isinstance(abstention_id, str) or abstention_id != "abstain":
        raise AnnotationAuditError("guide abstention must be abstain")
    if abstention.get("name") != "Cannot determine":
        raise AnnotationAuditError("guide abstention name must be 'Cannot determine'")
    allowed_labels.add(abstention_id)

    guide_revision = guide.get("revision")
    if not isinstance(guide_revision, str) or not guide_revision:
        raise AnnotationAuditError("guide requires revision")
    guide_sha256 = _digest(guide_file)

    policy_keys = [
        "minimum_distinct_raters",
        "raw_agreement_threshold",
        "nominal_alpha_threshold",
        "maximum_abstention_rate",
        "abstain_as_category",
        "raw_agreement_metric",
        "ordinal_agreement_metric",
        "ordinal_gate",
        "confidence_interval_method",
        "confidence_level",
        "confidence_interval_resamples",
        "confidence_interval_seed",
        "confidence_interval_gate",
        "adjudication_rule",
    ]
    if any(key not in policy for key in policy_keys):
        raise AnnotationAuditError("guide agreement policy is incomplete")
    if policy["minimum_distinct_raters"] != minimum_distinct_raters:
        raise AnnotationAuditError("minimum_distinct_raters must match guide policy")
    if policy["raw_agreement_threshold"] != agreement_threshold:
        raise AnnotationAuditError("agreement_threshold must match guide policy")
    if policy["nominal_alpha_threshold"] != 0.8:
        raise AnnotationAuditError("nominal_alpha_threshold must be 0.8 in frozen policy")
    if policy["maximum_abstention_rate"] != maximum_abstention_rate:
        raise AnnotationAuditError("maximum_abstention_rate must match guide policy")
    if policy["raw_agreement_metric"] != "pairwise_exact_percent_agreement":
        raise AnnotationAuditError("guide must use raw pairwise exact percent agreement")
    if policy["ordinal_agreement_metric"] != "krippendorff_alpha_ordinal":
        raise AnnotationAuditError("guide must use nominally declared ordinal alpha")
    if policy["ordinal_gate"] != "descriptive_only":
        raise AnnotationAuditError("ordinal agreement must remain descriptive_only")
    if policy["confidence_interval_method"] != "case_bootstrap_percentile":
        raise AnnotationAuditError("agreement confidence intervals must use case bootstrap percentiles")
    if policy["confidence_level"] != 0.95:
        raise AnnotationAuditError("agreement confidence level must be 0.95 in frozen policy")
    if policy["confidence_interval_resamples"] != 2000:
        raise AnnotationAuditError("agreement confidence intervals must use 2000 resamples")
    if policy["confidence_interval_seed"] != 1729:
        raise AnnotationAuditError("agreement confidence interval seed must be 1729")
    if policy["confidence_interval_gate"] != "descriptive_only":
        raise AnnotationAuditError("agreement confidence intervals must remain descriptive_only")
    if policy["abstain_as_category"] is not True:
        raise AnnotationAuditError("guide must treat abstention as category")

    raw_agreement_threshold = float(policy["raw_agreement_threshold"])
    nominal_alpha_threshold = float(policy["nominal_alpha_threshold"])
    max_abstention = float(policy["maximum_abstention_rate"])

    issues: list[dict[str, Any]] = []
    by_case: dict[str, dict[str, str]] = defaultdict(dict)
    by_case_scores: dict[str, dict[str, dict[str, int]]] = defaultdict(dict)
    source_files: list[dict[str, Any]] = []
    seen_raters: set[str] = set()
    seen_annotation_ids: set[str] = set()

    def add(code: str, message: str, *, case_id: str | None = None, path: Path | None = None) -> None:
        issue: dict[str, Any] = {"code": code, "message": message}
        if case_id is not None:
            issue["case_id"] = case_id
        if path is not None:
            issue["path"] = str(path)
        issues.append(issue)

    for path in paths:
        records = _read_jsonl(path)
        file_raters = {record.get("rater_id") for record in records}
        if len(file_raters) != 1 or not all(isinstance(value, str) and value for value in file_raters):
            add("mixed_or_missing_rater_file", "each annotation file must contain exactly one rater", path=path)
            continue
        rater_id = next(iter(file_raters))
        if not isinstance(rater_id, str):
            raise AnnotationAuditError("internal rater validation failure")
        if rater_id in seen_raters:
            add("duplicate_rater_file", f"rater {rater_id} appears in more than one file", path=path)
        seen_raters.add(rater_id)
        source_files.append({"path": path.name, "sha256": _digest(path), "rater_id": rater_id, "records": len(records)})

        for record in records:
            validation_issues = validate(record, schema)
            if validation_issues:
                details = "; ".join(f"{item.path}: {item.message}" for item in validation_issues)
                add("schema_invalid", details, path=path)
                continue

            annotation_id = record["annotation_id"]
            case_id = record["case_id"]
            label = record["label"]
            if not all(isinstance(value, str) for value in (annotation_id, case_id, label)):
                add("schema_invalid", "annotation_id, case_id, and label must be strings", path=path)
                continue

            if annotation_id in seen_annotation_ids:
                add("duplicate_annotation_id", f"annotation_id {annotation_id} is repeated", path=path)
                continue
            seen_annotation_ids.add(annotation_id)

            if case_id not in expected_case_ids:
                add("unknown_case", f"case {case_id} is not in the candidate batch", case_id=case_id, path=path)
                continue
            record_valid = True
            if not isinstance(record.get("session_id"), str) or not record["session_id"]:
                add("missing_session_id", "session_id is required", case_id=case_id, path=path)
                record_valid = False
            if record["case_payload_sha256"] != expected_case_hashes[case_id]:
                add("invalid_case_hash", f"case {case_id} case_payload_sha256 mismatch", case_id=case_id, path=path)
                record_valid = False
            if record["dataset_batch_sha256"] != expected_batch_hash:
                add("invalid_batch_hash", "dataset_batch_sha256 mismatch", case_id=case_id, path=path)
                record_valid = False
            if record["display_view_version"] != "v1.1.0":
                add("invalid_view_version", "display_view_version must be v1.1.0", case_id=case_id, path=path)
                record_valid = False
            if record["non_empirical"] is not False:
                add("invalid_human_boundary", "human judgment must set non_empirical false", case_id=case_id, path=path)
                record_valid = False
            if record.get("guide_revision") != guide_revision or record.get("guide_sha256") != guide_sha256:
                add("guide_mismatch", "annotation guide revision or digest does not match", case_id=case_id, path=path)
                record_valid = False
            if label not in allowed_labels:
                add("invalid_label", f"label {label!r} is not in the guide", case_id=case_id, path=path)
                continue
            if rater_id in by_case[case_id]:
                add("duplicate_case_rater", f"rater {rater_id} annotated the case twice", case_id=case_id, path=path)
                continue
            if not record_valid:
                continue
            by_case[case_id][rater_id] = label
            by_case_scores[case_id][rater_id] = {
                field: int(record[field])
                for field in (
                    "operator_presence",
                    "operator_essentiality",
                    "contradiction_resolution",
                    "solution_feasibility",
                )
            }

    coverage = {case_id: len(by_case.get(case_id, {})) for case_id in sorted(expected_case_ids)}
    for case_id, count in coverage.items():
        if count < minimum_distinct_raters:
            add(
                "insufficient_raters",
                f"case has {count} distinct rater(s); minimum is {minimum_distinct_raters}",
                case_id=case_id,
            )

    matched_pairs = total_pairs = 0
    per_case_agreement: dict[str, float | None] = {}
    disagreements: list[str] = []
    unanimous_abstentions: list[str] = []
    abstentions = 0
    total_annotations = 0
    consensus: dict[str, str] = {}
    for case_id in sorted(expected_case_ids):
        case_labels = list(by_case.get(case_id, {}).values())
        abstentions += sum(label == abstention_id for label in case_labels)
        total_annotations += len(case_labels)
        matched, pairs = _pairwise_agreement(case_labels)
        matched_pairs += matched
        total_pairs += pairs
        per_case_agreement[case_id] = matched / pairs if pairs else None
        if pairs and matched != pairs:
            disagreements.append(case_id)
            add(
                "unresolved_case",
                "case requires adjudication because it lacks a unanimous label",
                case_id=case_id,
            )
        if case_labels and len(set(case_labels)) == 1:
            consensus[case_id] = case_labels[0]
            if case_labels[0] == abstention_id:
                unanimous_abstentions.append(case_id)
                add(
                    "unanimous_abstention",
                    "case requires adjudication because every rater abstained",
                    case_id=case_id,
                )

    overall_agreement = matched_pairs / total_pairs if total_pairs else 0.0
    nominal_alpha = _nominal_alpha_bycase(by_case)
    ordinal_alpha = {
        field: _ordinal_alpha_bycase(by_case_scores, field)
        for field in (
            "operator_presence",
            "operator_essentiality",
            "contradiction_resolution",
            "solution_feasibility",
        )
    }
    agreement_intervals = _bootstrap_agreement_intervals(
        by_case,
        confidence_level=float(policy["confidence_level"]),
        resamples=int(policy["confidence_interval_resamples"]),
        seed=int(policy["confidence_interval_seed"]),
    )
    abstention_rate = abstentions / total_annotations if total_annotations else 0.0

    if overall_agreement < raw_agreement_threshold:
        add(
            "agreement_threshold_not_met",
            f"pairwise agreement {overall_agreement:.3f} is below {raw_agreement_threshold:.3f}",
        )
    if nominal_alpha < nominal_alpha_threshold:
        add(
            "nominal_alpha_threshold_not_met",
            f"nominal alpha {nominal_alpha:.3f} is below {nominal_alpha_threshold:.3f}",
        )
    if abstention_rate > max_abstention:
        add(
            "abstention_rate_exceeded",
            f"abstention rate {abstention_rate:.3f} exceeds {max_abstention:.3f}",
        )

    issues.sort(key=lambda item: (item["code"], item.get("case_id", ""), item.get("path", "")))
    structural_codes = {
        "mixed_or_missing_rater_file", "duplicate_rater_file", "schema_invalid",
        "duplicate_annotation_id", "unknown_case", "invalid_human_boundary", "guide_mismatch",
        "invalid_label", "duplicate_case_rater", "insufficient_raters", "missing_session_id",
        "invalid_case_hash", "invalid_batch_hash", "invalid_view_version",
    }
    structurally_ready = not any(issue["code"] in structural_codes for issue in issues)
    ready_for_freeze = (
        structurally_ready
        and overall_agreement >= raw_agreement_threshold
        and nominal_alpha >= nominal_alpha_threshold
        and abstention_rate <= max_abstention
        and not unanimous_abstentions
        and all(count >= minimum_distinct_raters for count in coverage.values())
    )

    return {
        "artifact_class": "blinded-annotation-audit",
        "status": "pass" if not issues else "fail",
        "ready_for_adjudication": structurally_ready,
        "ready_for_freeze": ready_for_freeze,
        "empirical": True,
        "evidence_eligible": False,
        "claim_ids": [],
        "policy": {
            "minimum_distinct_raters": minimum_distinct_raters,
            "raw_agreement_threshold": raw_agreement_threshold,
            "nominal_alpha_threshold": nominal_alpha_threshold,
            "maximum_abstention_rate": max_abstention,
            "abstain_as_category": True,
            "raw_agreement_metric": "pairwise_exact_percent_agreement",
            "ordinal_agreement_metric": "krippendorff_alpha_ordinal",
            "ordinal_gate": "descriptive_only",
            "confidence_interval_method": "case_bootstrap_percentile",
            "confidence_level": 0.95,
            "confidence_interval_resamples": 2000,
            "confidence_interval_seed": 1729,
            "confidence_interval_gate": "descriptive_only",
            "adjudication_rule": "Case-level unanimity on a substantive label required for freeze; disagreements and unanimous abstentions remain explicit for adjudication.",
        },
        "counts": {
            "cases": len(expected_case_ids), "raters": len(seen_raters),
            "annotations": total_annotations, "abstentions": abstentions,
        },
        "coverage_by_case": coverage,
        "agreement": {
            "metric": "pairwise_exact_percent_agreement",
            "overall": overall_agreement,
            "nominal_alpha": nominal_alpha,
            "confidence_intervals": agreement_intervals,
            "matched_pairs": matched_pairs,
            "total_pairs": total_pairs,
            "per_case": per_case_agreement,
            "disagreement_case_ids": disagreements,
            "unanimous_abstention_case_ids": unanimous_abstentions,
            "adjudication_case_ids": sorted(set(disagreements + unanimous_abstentions)),
        },
        "ordinal_agreement": {
            "metric": "krippendorff_alpha_ordinal",
            "gate": "descriptive_only",
            "by_dimension": ordinal_alpha,
        },
        "abstention_rate": abstention_rate,
        "consensus_labels": consensus,
        "guide": {"revision": guide_revision, "sha256": guide_sha256},
        "artifacts": {
            "cases_sha256": _digest(cases_file),
            "guide_sha256": guide_sha256,
            "display_batch_sha256": expected_batch_hash,
            "annotation_schema_sha256": _digest(schema_file),
            "annotation_files": source_files,
        },
        "issues": issues,
    }
