"""Multi-rater integrity and agreement audit for blinded dataset annotations."""

from __future__ import annotations

import hashlib
import itertools
import json
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


def _pairwise_agreement(labels: Sequence[str]) -> tuple[int, int]:
    pairs = list(itertools.combinations(labels, 2))
    return sum(left == right for left, right in pairs), len(pairs)


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
    case_ids: list[str] = []
    for case in cases:
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise AnnotationAuditError("every case requires case_id")
        case_ids.append(case_id)
    if len(set(case_ids)) != len(case_ids):
        raise AnnotationAuditError("case IDs must be unique")
    expected_case_ids = set(case_ids)
    labels = guide.get("labels")
    abstention = guide.get("abstention")
    if not isinstance(labels, list) or not isinstance(abstention, dict):
        raise AnnotationAuditError("guide requires labels and abstention")
    allowed_labels = {
        item["id"] for item in labels if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if len(allowed_labels) != len(labels) or len(allowed_labels) < 2:
        raise AnnotationAuditError("guide requires at least two unique string label IDs")
    abstention_id = abstention.get("id")
    if not isinstance(abstention_id, str) or not abstention_id:
        raise AnnotationAuditError("guide abstention requires id")
    allowed_labels.add(abstention_id)
    guide_revision = guide.get("revision")
    if not isinstance(guide_revision, str) or not guide_revision:
        raise AnnotationAuditError("guide requires revision")
    guide_sha256 = _digest(guide_file)

    issues: list[dict[str, Any]] = []
    by_case: dict[str, dict[str, str]] = defaultdict(dict)
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
            seen_annotation_ids.add(annotation_id)
            if case_id not in expected_case_ids:
                add("unknown_case", f"case {case_id} is not in the candidate batch", case_id=case_id, path=path)
                continue
            if record["non_empirical"] is not False:
                add("invalid_human_boundary", "human judgment must set non_empirical false", case_id=case_id, path=path)
            if record.get("guide_revision") != guide_revision or record.get("guide_sha256") != guide_sha256:
                add("guide_mismatch", "annotation guide revision or digest does not match", case_id=case_id, path=path)
            if label not in allowed_labels:
                add("invalid_label", f"label {label!r} is not in the guide", case_id=case_id, path=path)
                continue
            if rater_id in by_case[case_id]:
                add("duplicate_case_rater", f"rater {rater_id} annotated the case twice", case_id=case_id, path=path)
                continue
            by_case[case_id][rater_id] = label

    coverage = {case_id: len(by_case.get(case_id, {})) for case_id in sorted(expected_case_ids)}
    for case_id, count in coverage.items():
        if count < minimum_distinct_raters:
            add(
                "insufficient_raters",
                f"case has {count} distinct raters; minimum is {minimum_distinct_raters}",
                case_id=case_id,
            )

    matched_pairs = total_pairs = 0
    per_case_agreement: dict[str, float | None] = {}
    disagreements: list[str] = []
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
        if case_labels and len(set(case_labels)) == 1:
            consensus[case_id] = case_labels[0]
        if pairs and (case_id not in consensus or consensus.get(case_id) == abstention_id):
            add(
                "unresolved_case",
                "case requires adjudication because it lacks a unanimous substantive label",
                case_id=case_id,
            )

    overall_agreement = matched_pairs / total_pairs if total_pairs else 0.0
    abstention_rate = abstentions / total_annotations if total_annotations else 0.0
    if overall_agreement < agreement_threshold:
        add(
            "agreement_threshold_not_met",
            f"pairwise agreement {overall_agreement:.3f} is below {agreement_threshold:.3f}",
        )
    if abstention_rate > maximum_abstention_rate:
        add(
            "abstention_rate_exceeded",
            f"abstention rate {abstention_rate:.3f} exceeds {maximum_abstention_rate:.3f}",
        )

    issues.sort(key=lambda item: (item["code"], item.get("case_id", ""), item.get("path", "")))
    structural_codes = {
        "mixed_or_missing_rater_file", "duplicate_rater_file", "schema_invalid",
        "duplicate_annotation_id", "unknown_case", "invalid_human_boundary", "guide_mismatch",
        "invalid_label", "duplicate_case_rater", "insufficient_raters",
    }
    structurally_ready = not any(issue["code"] in structural_codes for issue in issues)
    return {
        "artifact_class": "blinded-annotation-audit",
        "status": "pass" if not issues else "fail",
        "ready_for_adjudication": structurally_ready,
        "ready_for_freeze": not issues,
        "empirical": True,
        "evidence_eligible": False,
        "claim_ids": [],
        "policy": {
            "minimum_distinct_raters": minimum_distinct_raters,
            "agreement_threshold": agreement_threshold,
            "maximum_abstention_rate": maximum_abstention_rate,
        },
        "counts": {
            "cases": len(expected_case_ids), "raters": len(seen_raters),
            "annotations": total_annotations, "abstentions": abstentions,
        },
        "coverage_by_case": coverage,
        "agreement": {
            "metric": "pairwise_exact_percent_agreement",
            "overall": overall_agreement,
            "matched_pairs": matched_pairs,
            "total_pairs": total_pairs,
            "per_case": per_case_agreement,
            "disagreement_case_ids": disagreements,
        },
        "abstention_rate": abstention_rate,
        "consensus_labels": consensus,
        "guide": {"revision": guide_revision, "sha256": guide_sha256},
        "artifacts": {
            "cases_sha256": _digest(cases_file), "guide_sha256": guide_sha256,
            "annotation_schema_sha256": _digest(schema_file), "annotation_files": source_files,
        },
        "issues": issues,
    }
