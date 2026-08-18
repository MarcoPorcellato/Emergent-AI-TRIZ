"""Fail-closed audit for the v1.2 human H1 collection packet.

The historical annotation audit is intentionally kept on its v1.1 contract.
This module is the separate v1.2 boundary: it accepts exactly the public H1
packet, binds every raw record to that packet, and never promotes a collection
audit to a scientific claim.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from .annotation_audit import (
    _bootstrap_agreement_intervals,
    _nominal_alpha_bycase,
    _ordinal_alpha_bycase,
    _pairwise_agreement,
)
from .validator import validate


class H1CollectionAuditError(RuntimeError):
    """Raised when H1 inputs are missing, drifted, or malformed."""


_CASE_FIELDS = (
    "case_id", "domain", "problem", "constraints", "initial_state",
    "desired_improvement", "worsening_consequence", "displayed_solution",
    "resulting_state",
)
_LABELS = {"segmentation", "inversion", "both", "other", "abstain"}
_SCORES = (
    "operator_presence", "operator_essentiality",
    "contradiction_resolution", "solution_feasibility",
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise H1CollectionAuditError(f"cannot read JSON {path.name}") from exc
    if not isinstance(value, dict):
        raise H1CollectionAuditError(f"expected JSON object: {path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise H1CollectionAuditError(f"cannot read JSONL {path.name}") from exc
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise H1CollectionAuditError(f"invalid JSONL at {path.name}:{line_number}") from exc
        if not isinstance(value, dict):
            raise H1CollectionAuditError(f"JSONL record is not an object at {path.name}:{line_number}")
        records.append(value)
    return records


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _case_hash(case: Mapping[str, Any]) -> str:
    try:
        canonical = {field: case[field] for field in _CASE_FIELDS}
    except KeyError as exc:
        raise H1CollectionAuditError(f"case missing field {exc.args[0]}") from exc
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _batch_hash(case_hashes: Mapping[str, str]) -> str:
    payload = json.dumps(
        [case_hashes[key] for key in sorted(case_hashes)],
        ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def audit_h1_annotations(
    *,
    cases_path: str | Path,
    guide_path: str | Path,
    annotation_schema_path: str | Path,
    annotation_paths: Iterable[str | Path],
) -> dict[str, Any]:
    """Audit three independent v1.2 raw files without opening model/target data."""

    cases_file, guide_file, schema_file = map(Path, (cases_path, guide_path, annotation_schema_path))
    cases, guide, schema = _read_jsonl(cases_file), _read_json(guide_file), _read_json(schema_file)
    if guide.get("revision") != "v1.2.0" or guide.get("status") != "proposed_for_review":
        raise H1CollectionAuditError("H1 guide revision/status mismatch")
    labels = {item.get("id") for item in guide.get("labels", []) if isinstance(item, dict)}
    if labels != _LABELS:
        raise H1CollectionAuditError("H1 guide labels drifted")
    policy = guide.get("agreement_policy")
    if not isinstance(policy, dict):
        raise H1CollectionAuditError("H1 agreement policy is missing")
    expected_policy = {
        "minimum_distinct_raters": 3,
        "raw_agreement_threshold": 0.8,
        "nominal_alpha_threshold": 0.8,
        "maximum_abstention_rate": 0.2,
        "abstain_as_category": True,
        "ordinal_agreement_metric": "krippendorff_alpha_ordinal",
        "confidence_interval_method": "case_bootstrap_percentile",
        "confidence_level": 0.95,
        "confidence_interval_resamples": 2000,
        "confidence_interval_seed": 1729,
        "case_level_unanimity_required": True,
    }
    if any(policy.get(key) != value for key, value in expected_policy.items()):
        raise H1CollectionAuditError("H1 agreement policy drifted")
    if guide.get("non_empirical") is not True or guide.get("evidence_eligible") is not False:
        raise H1CollectionAuditError("guide crossed the non-empirical boundary")

    case_hashes: dict[str, str] = {}
    for case in cases:
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or case_id in case_hashes:
            raise H1CollectionAuditError("H1 case IDs must be unique strings")
        if case.get("non_empirical") is not True:
            raise H1CollectionAuditError(f"case crossed empirical boundary: {case_id}")
        case_hashes[case_id] = _case_hash(case)
    if len(cases) != 6:
        raise H1CollectionAuditError(f"expected six H1 cases, found {len(cases)}")

    guide_sha = _sha(guide_file)
    batch_sha = _batch_hash(case_hashes)
    expected_cases = set(case_hashes)
    paths = [Path(path) for path in annotation_paths]
    issues: list[dict[str, Any]] = []
    by_case: dict[str, dict[str, str]] = defaultdict(dict)
    by_scores: dict[str, dict[str, dict[str, int]]] = defaultdict(dict)
    seen_raters: set[str] = set()
    seen_ids: set[str] = set()
    source_files: list[dict[str, Any]] = []

    def add(code: str, message: str, *, case_id: str | None = None, path: Path | None = None) -> None:
        item: dict[str, Any] = {"code": code, "message": message}
        if case_id is not None:
            item["case_id"] = case_id
        if path is not None:
            item["path"] = path.name
        issues.append(item)

    if len(paths) != 3:
        add("rater_count", "exactly three independent raw files are required")
    for path in paths:
        records = _read_jsonl(path)
        raters = {record.get("rater_id") for record in records}
        if len(raters) != 1 or not all(isinstance(rater, str) and rater for rater in raters):
            add("mixed_or_missing_rater_file", "one rater per file is required", path=path)
            continue
        rater = next(iter(raters))
        if rater in seen_raters:
            add("duplicate_rater_file", f"rater {rater} appears more than once", path=path)
        seen_raters.add(rater)
        source_files.append({"path": path.name, "sha256": _sha(path), "rater_id": rater, "records": len(records)})
        for record in records:
            schema_issues = validate(record, schema)
            case_id = record.get("case_id")
            if schema_issues:
                add("schema_invalid", "; ".join(item.message for item in schema_issues), case_id=case_id if isinstance(case_id, str) else None, path=path)
                continue
            annotation_id = record["annotation_id"]
            if annotation_id in seen_ids:
                add("duplicate_annotation_id", f"annotation {annotation_id} is repeated", path=path)
                continue
            seen_ids.add(annotation_id)
            valid = True
            if case_id not in expected_cases:
                add("unknown_case", f"case {case_id!r} is not in H1 packet", path=path)
                valid = False
            else:
                if record["case_payload_sha256"] != case_hashes[case_id]:
                    add("invalid_case_hash", "case payload hash mismatch", case_id=case_id, path=path)
                    valid = False
            if record["guide_revision"] != "v1.2.0" or record["guide_sha256"] != guide_sha:
                add("guide_mismatch", "guide revision or digest mismatch", case_id=case_id, path=path)
                valid = False
            if record["dataset_batch_sha256"] != batch_sha:
                add("invalid_batch_hash", "dataset batch hash mismatch", case_id=case_id, path=path)
                valid = False
            if record["display_view_version"] != "v1.2.0" or record["non_empirical"] is not False:
                add("invalid_human_boundary", "record is not a v1.2 empirical judgment", case_id=case_id, path=path)
                valid = False
            if valid and rater in by_case[case_id]:
                add("duplicate_case_rater", "rater submitted the case twice", case_id=case_id, path=path)
                valid = False
            if valid:
                by_case[case_id][rater] = record["label"]
                by_scores[case_id][rater] = {field: int(record[field]) for field in _SCORES}

    coverage = {case_id: len(by_case.get(case_id, {})) for case_id in sorted(expected_cases)}
    for case_id, count in coverage.items():
        if count != 3:
            add("incomplete_coverage", f"case has {count}/3 valid raters", case_id=case_id)

    matched = total = abstentions = annotations = 0
    disagreements: list[str] = []
    unanimous_abstentions: list[str] = []
    consensus: dict[str, str] = {}
    per_case: dict[str, float | None] = {}
    for case_id in sorted(expected_cases):
        values = list(by_case.get(case_id, {}).values())
        annotations += len(values)
        abstentions += sum(value == "abstain" for value in values)
        case_matched, case_total = _pairwise_agreement(values)
        matched += case_matched
        total += case_total
        per_case[case_id] = case_matched / case_total if case_total else None
        if case_total and case_matched != case_total:
            disagreements.append(case_id)
        if values and len(set(values)) == 1:
            consensus[case_id] = values[0]
            if values[0] == "abstain":
                unanimous_abstentions.append(case_id)

    overall = matched / total if total else 0.0
    alpha = _nominal_alpha_bycase(by_case)
    ordinal = {field: _ordinal_alpha_bycase(by_scores, field) for field in _SCORES}
    abstention_rate = abstentions / annotations if annotations else 0.0
    intervals = _bootstrap_agreement_intervals(by_case, confidence_level=0.95, resamples=2000, seed=1729)
    if overall < 0.8:
        add("agreement_threshold_not_met", f"agreement {overall:.3f} < 0.800")
    if alpha < 0.8:
        add("nominal_alpha_threshold_not_met", f"nominal alpha {alpha:.3f} < 0.800")
    if abstention_rate > 0.2:
        add("abstention_rate_exceeded", f"abstention rate {abstention_rate:.3f} > 0.200")
    for case_id in disagreements:
        add("unresolved_case", "case requires additive adjudication", case_id=case_id)
    for case_id in unanimous_abstentions:
        add("unanimous_abstention", "case requires additive adjudication", case_id=case_id)

    structural = {"rater_count", "mixed_or_missing_rater_file", "duplicate_rater_file", "schema_invalid", "duplicate_annotation_id", "unknown_case", "invalid_case_hash", "guide_mismatch", "invalid_batch_hash", "invalid_human_boundary", "duplicate_case_rater", "incomplete_coverage"}
    ready_adjudication = not any(item["code"] in structural for item in issues)
    ready_freeze = ready_adjudication and not disagreements and not unanimous_abstentions and overall >= 0.8 and alpha >= 0.8 and abstention_rate <= 0.2
    issues.sort(key=lambda item: (item["code"], item.get("case_id", ""), item.get("path", "")))
    return {
        "artifact_class": "blinded-annotation-audit",
        "status": "pass" if not issues else "fail",
        "ready_for_adjudication": ready_adjudication,
        "ready_for_freeze": ready_freeze,
        "empirical": True,
        "evidence_eligible": False,
        "claim_ids": [],
        "policy": {
            "minimum_distinct_raters": 3, "raw_agreement_threshold": 0.8,
            "nominal_alpha_threshold": 0.8, "maximum_abstention_rate": 0.2,
            "abstain_as_category": True, "raw_agreement_metric": "pairwise_exact_percent_agreement",
            "ordinal_agreement_metric": "krippendorff_alpha_ordinal", "ordinal_gate": "descriptive_only",
            "confidence_interval_method": "case_bootstrap_percentile", "confidence_level": 0.95,
            "confidence_interval_resamples": 2000, "confidence_interval_seed": 1729,
            "confidence_interval_gate": "descriptive_only",
            "adjudication_rule": "Case-level unanimity on a substantive label is required; disagreements and unanimous abstentions remain additive adjudication items.",
        },
        "counts": {"cases": len(expected_cases), "raters": len(seen_raters), "annotations": annotations, "abstentions": abstentions},
        "coverage_by_case": coverage,
        "agreement": {
            "metric": "pairwise_exact_percent_agreement", "overall": overall,
            "nominal_alpha": alpha, "confidence_intervals": intervals,
            "matched_pairs": matched, "total_pairs": total, "per_case": per_case,
            "disagreement_case_ids": sorted(disagreements),
            "unanimous_abstention_case_ids": sorted(unanimous_abstentions),
            "adjudication_case_ids": sorted(set(disagreements + unanimous_abstentions)),
        },
        "ordinal_agreement": {"metric": "krippendorff_alpha_ordinal", "gate": "descriptive_only", "by_dimension": ordinal},
        "abstention_rate": abstention_rate, "consensus_labels": consensus,
        "guide": {"revision": "v1.2.0", "sha256": guide_sha},
        "artifacts": {
            "cases_sha256": _sha(cases_file), "guide_sha256": guide_sha,
            "display_batch_sha256": batch_sha, "annotation_schema_sha256": _sha(schema_file),
            "annotation_files": source_files,
        },
        "issues": issues,
    }
