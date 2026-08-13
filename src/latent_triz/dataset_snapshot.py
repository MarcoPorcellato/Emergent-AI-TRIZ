from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

_CASE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]+$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATE_TIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_ALLOWED_SPLITS = ("discovery", "validation", "held_out_domain", "sealed_novel")
_DEFAULT_AGREEMENT_THRESHOLD = 0.8
_DEFAULT_MIN_RATERS = 2


@dataclass(frozen=True)
class DatasetSnapshotIssue:
    code: str
    field: str
    message: str


class DatasetSnapshotError(RuntimeError):
    pass


def stable_json_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def run_dataset_snapshot(
    cases_path: str | Path,
    annotations_path: str | Path,
    plan_path: str | Path,
    registry_entry_path: str | Path,
    registry_manifest_path: str | Path,
    *,
    fail_closed: bool = True,
    generated_at: str | None = None,
    case_schema_path: str | Path | None = None,
) -> Dict[str, Any]:
    manifest = build_dataset_snapshot_manifest(
        cases_path=cases_path,
        annotations_path=annotations_path,
        plan_path=plan_path,
        registry_entry_path=registry_entry_path,
        registry_manifest_path=registry_manifest_path,
        generated_at=generated_at,
        case_schema_path=case_schema_path,
    )
    if fail_closed and manifest["issues"]:
        raise DatasetSnapshotError("dataset snapshot fail-closed: " + "; ".join(issue["message"] for issue in manifest["issues"]))
    return manifest


def build_dataset_snapshot_manifest(
    cases_path: str | Path,
    annotations_path: str | Path,
    plan_path: str | Path,
    registry_entry_path: str | Path,
    registry_manifest_path: str | Path,
    generated_at: str | None = None,
    case_schema_path: str | Path | None = None,
) -> Dict[str, Any]:
    cases_file = Path(cases_path)
    annotations_file = Path(annotations_path)
    plan = _read_json(plan_path)
    registry_entry = _read_json_or_obj(registry_entry_path)
    registry_manifest = _read_json_or_obj(registry_manifest_path)
    _ensure_file_exists(cases_file, "cases")
    _ensure_file_exists(annotations_file, "annotations")

    allowed_source_types = None
    source_type_policy = plan.get("source_type_policy")
    if isinstance(source_type_policy, Mapping) and isinstance(source_type_policy.get("allowed_source_types"), list):
        allowed_source_types = source_type_policy.get("allowed_source_types")

    cases = _read_jsonl(cases_file)
    annotations = _read_jsonl(annotations_file)

    issues: List[DatasetSnapshotIssue] = []
    case_ids: List[str] = []
    split_counts: Dict[str, int] = {split: 0 for split in _ALLOWED_SPLITS}
    domain_counts: Dict[str, int] = {}
    principle_counts: Dict[str, int] = {}
    source_type_counts: Dict[str, int] = {}
    license_counts: Dict[str, int] = {}
    source_fingerprints: List[Dict[str, str]] = []
    template_fingerprints: List[Dict[str, str]] = []
    source_splits: Dict[str, set[str]] = {}
    template_splits: Dict[str, set[str]] = {}
    case_by_id: Dict[str, Dict[str, Any]] = {}
    registry_license = registry_entry.get("license")

    for index, case in enumerate(cases, start=1):
        case_id = case.get("case_id")
        if not _is_case_id(case_id):
            issues.append(DatasetSnapshotIssue("invalid_case_id", "case_id", f"record {index}: invalid case_id"))
            continue

        if case_id in case_by_id:
            issues.append(DatasetSnapshotIssue("duplicate_case_id", "case_id", f"{case_id}: duplicate case_id"))
            continue

        split = case.get("split")
        if split not in _ALLOWED_SPLITS:
            issues.append(DatasetSnapshotIssue("invalid_split", "split", f"{case_id}: split must be one of {_ALLOWED_SPLITS}"))
            continue

        domain = case.get("domain")
        if not isinstance(domain, str) or not domain.strip():
            issues.append(DatasetSnapshotIssue("invalid_domain", "domain", f"{case_id}: domain must be non-empty"))
            continue

        provenance = case.get("provenance")
        if not isinstance(provenance, dict):
            issues.append(DatasetSnapshotIssue("missing_provenance", "provenance", f"{case_id}: provenance must be an object"))
            continue

        _validate_provenance(
            case_id=case_id,
            provenance=provenance,
            registry_license=registry_license,
            allowed_source_types=allowed_source_types,
            issues=issues,
        )

        source_fingerprint = _stable_digest(_collect_source_fingerprint_payload(case, provenance))
        source_fingerprints.append(
            {"case_id": case_id, "split": split, "fingerprint": f"sha256:{source_fingerprint}"}
        )
        source_splits.setdefault(f"sha256:{source_fingerprint}", set()).add(split)

        template_fingerprint = _collect_template_fingerprint_payload(case, provenance)
        if template_fingerprint is not None:
            template_fingerprint_value = _stable_digest(template_fingerprint)
            template_fingerprints.append(
                {"case_id": case_id, "split": split, "fingerprint": f"sha256:{template_fingerprint_value}"}
            )
            template_splits.setdefault(f"sha256:{template_fingerprint_value}", set()).add(split)

        split_counts[split] = split_counts.get(split, 0) + 1
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        for principle in _extract_principles(case):
            principle_counts[principle] = principle_counts.get(principle, 0) + 1
        source_type = provenance.get("source_type")
        if isinstance(source_type, str):
            source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1
        license_value = provenance.get("license")
        if isinstance(license_value, str):
            license_counts[license_value] = license_counts.get(license_value, 0) + 1

        case_ids.append(case_id)
        case_by_id[case_id] = case

    annotation_policy = _read_annotation_policy(plan)
    min_raters = annotation_policy["minimum_distinct_raters"]
    agreement_threshold = annotation_policy["agreement_threshold"]
    enforce_split_leakage_check = bool(annotation_policy.get("enforce_cross_split_source_fingerprints"))
    min_cases_per_domain = int(plan.get("min_cases_per_domain", 0) or 0)
    min_cases_per_principle = int(plan.get("min_cases_per_principle", 0) or 0)
    enforce_targets = bool(plan.get("enforce_targets", False))
    plan_id = str(plan.get("plan_version", "unknown"))
    dataset_id = _infer_dataset_id(registry_entry, plan)

    for split, cases_per_split in split_counts.items():
        expected_min = int(((plan.get("splits") or {}).get(split, {}) or {}).get("target_min", 0))
        expected_exact = (plan.get("splits") or {}).get(split, {}).get("target_exact")
        if cases_per_split < expected_min:
            issues.append(
                DatasetSnapshotIssue(
                    "split_target_min",
                    "splits",
                    f"{split}: has {cases_per_split}, expected at least {expected_min}",
                )
            )
        if expected_exact is not None and cases_per_split != expected_exact:
            issues.append(
                DatasetSnapshotIssue(
                    "split_target_exact",
                    "splits",
                    f"{split}: has {cases_per_split}, expected exactly {expected_exact}",
                )
            )

    if min_cases_per_domain:
        for domain, domain_count in domain_counts.items():
            if domain_count < min_cases_per_domain:
                issues.append(
                    DatasetSnapshotIssue(
                        "domain_minimum_not_met",
                        "domain",
                        f"{domain}: has {domain_count}, expected at least {min_cases_per_domain}",
                    )
                )

    if min_cases_per_principle:
        for principle, count in principle_counts.items():
            if count < min_cases_per_principle:
                issues.append(
                    DatasetSnapshotIssue(
                        "principle_minimum_not_met",
                        "principles",
                        f"{principle}: has {count}, expected at least {min_cases_per_principle}",
                    )
                )

    annotation_records = _read_annotations(annotations_file)
    annotation_issues, coverage, agreement = _evaluate_annotations(
        annotation_records,
        case_by_id,
        min_raters,
        agreement_threshold,
    )
    issues.extend(annotation_issues)

    if enforce_split_leakage_check:
        for source_digest, splits in source_splits.items():
            if len(splits) > 1:
                issues.append(
                    DatasetSnapshotIssue(
                        "cross_split_source_leakage",
                        "source_fingerprint",
                        f"{source_digest} appears in multiple splits: {sorted(splits)}",
                    )
                )
        for template_digest, splits in template_splits.items():
            if len(splits) > 1:
                issues.append(
                    DatasetSnapshotIssue(
                        "cross_split_template_leakage",
                        "template_fingerprint",
                        f"{template_digest} appears in multiple splits: {sorted(splits)}",
                    )
                )

    split_membership_digest = _compute_split_membership_digest(cases)
    artifacts = {
        "cases_jsonl": _fingerprint_file(cases_file),
        "annotations_jsonl": _fingerprint_file(annotations_file),
        "registry_entry": _fingerprint_value(registry_entry, path_hint="registry_entry"),
        "registry_manifest": _fingerprint_value(registry_manifest, path_hint="registry_manifest"),
    }

    if not _is_valid_sha256(registry_entry.get("sha256")):
        issues.append(
            DatasetSnapshotIssue(
                "registry_cases_hash_mismatch",
                "registry_entry.sha256",
                "registry_entry.sha256 must be lowercase 64-hex string",
            )
        )
    elif registry_entry.get("sha256") != artifacts["cases_jsonl"]["sha256"]:
        issues.append(
            DatasetSnapshotIssue(
                "registry_cases_hash_mismatch",
                "registry_entry.sha256",
                "registry_entry.sha256 does not match cases JSONL SHA256",
            )
        )

    if case_schema_path is not None:
        expected_case_schema_revision = _read_text_digest(case_schema_path)
        if registry_entry.get("case_schema_revision") != expected_case_schema_revision:
            issues.append(
                DatasetSnapshotIssue(
                    "case_schema_revision_mismatch",
                    "registry_entry.case_schema_revision",
                    "registry_entry.case_schema_revision does not match provided case schema hash",
                )
            )

    actual_entry_in_manifest = _extract_dataset_entry_record(registry_manifest, dataset_id)
    if actual_entry_in_manifest is None:
        issues.append(
            DatasetSnapshotIssue(
                "registry_entry_mismatch",
                "registry_manifest",
                "registry_manifest.datasets does not include registry_entry payload",
            )
        )
    elif not _registry_entry_equivalent(registry_entry, actual_entry_in_manifest):
        issues.append(
            DatasetSnapshotIssue(
                "registry_entry_mismatch",
                "registry_manifest",
                "registry entry payload does not match entry in registry_manifest.datasets",
            )
        )

    immutable_revision = _stable_digest(
        f"{artifacts['cases_jsonl']['sha256']}|{artifacts['annotations_jsonl']['sha256']}|"
        f"{artifacts['registry_entry']['sha256']}|{artifacts['registry_manifest']['sha256']}"
    )

    manifest: Dict[str, Any] = {
        "artifact_class": "dataset-instrumentation",
        "empirical": any(annotation.get("non_empirical") is False for annotation in annotation_records),
        "evidence_eligible": False,
        "claim_ids": [],
        "dataset_id": dataset_id,
        "snapshot_id": plan_id,
        "generated_at": _derive_generated_at(generated_at, registry_manifest),
        "immutable_revision": f"sha256:{immutable_revision}",
        "artifacts": {
            "cases_jsonl": {
                "path": cases_file.name,
                "sha256": artifacts["cases_jsonl"]["sha256"],
                "size": artifacts["cases_jsonl"]["size"],
            },
            "annotations_jsonl": {
                "path": annotations_file.name,
                "sha256": artifacts["annotations_jsonl"]["sha256"],
                "size": artifacts["annotations_jsonl"]["size"],
            },
            "registry_entry": {
                "sha256": artifacts["registry_entry"]["sha256"],
                "size": artifacts["registry_entry"]["size"],
            },
            "registry_manifest": {
                "sha256": artifacts["registry_manifest"]["sha256"],
                "size": artifacts["registry_manifest"]["size"],
            },
        },
        "counts": {
            "total_cases": len(cases),
            "by_split": dict(sorted(split_counts.items())),
            "by_domain": dict(sorted(domain_counts.items())),
            "by_principle": dict(sorted(principle_counts.items())),
            "by_source_type": dict(sorted(source_type_counts.items())),
            "by_license": dict(sorted(license_counts.items())),
        },
        "split_membership_digest": f"sha256:{split_membership_digest}",
        "source_fingerprints": sorted(source_fingerprints, key=lambda item: (item["split"], item["case_id"])),
        "template_fingerprints": sorted(template_fingerprints, key=lambda item: (item["split"], item["case_id"])),
        "rater_coverage": coverage,
        "agreement": agreement,
        "status": "pass" if not issues else "fail",
        "issues": [_issue_dict(issue) for issue in issues],
    }

    if enforce_targets and manifest["status"] != "pass":
        manifest["status"] = "fail"
    return manifest


def verify_dataset_snapshot_manifest(
    manifest: Mapping[str, Any],
    cases_path: str | Path,
    annotations_path: str | Path,
    plan_path: str | Path,
    registry_entry_path: str | Path,
    registry_manifest_path: str | Path,
    *,
    case_schema_path: str | Path | None = None,
    fail_closed: bool = False,
) -> List[Dict[str, Any]]:
    regenerated = build_dataset_snapshot_manifest(
        cases_path=cases_path,
        annotations_path=annotations_path,
        plan_path=plan_path,
        registry_entry_path=registry_entry_path,
        registry_manifest_path=registry_manifest_path,
        case_schema_path=case_schema_path,
    )
    issues: List[Dict[str, Any]] = []
    for key in ("immutable_revision", "split_membership_digest", "status"):
        if manifest.get(key) != regenerated.get(key):
            issues.append({"code": "manifest_mismatch", "field": key, "message": f"{key} changed"})
    artifacts = regenerated.get("artifacts", {})
    for artifact_name, artifact in artifacts.items():
        manifest_artifact = manifest.get("artifacts", {}).get(artifact_name, {})
        for field in ("sha256", "size"):
            if manifest_artifact.get(field) != artifact.get(field):
                issues.append(
                    {
                        "code": "artifact_fingerprint_mismatch",
                        "field": f"{artifact_name}.{field}",
                        "message": f"{artifact_name} {field} changed",
                    }
                )

    if fail_closed and issues:
        raise DatasetSnapshotError("snapshot manifest mismatch: " + "; ".join(issue["message"] for issue in issues))
    return issues


def _derive_generated_at(generated_at: str | None, registry_manifest: Mapping[str, Any]) -> str:
    if generated_at is not None:
        return _validate_datetime(generated_at)
    registry_generated_at = registry_manifest.get("generated_at")
    if isinstance(registry_generated_at, str):
        return _validate_datetime(registry_generated_at)
    raise DatasetSnapshotError("generated_at is required when registry_manifest.generated_at is missing")


def _read_json_or_obj(payload: str | Path | Mapping[str, Any]) -> Dict[str, Any]:
    if isinstance(payload, Mapping):
        return dict(payload)
    if not isinstance(payload, (str, Path)):
        raise DatasetSnapshotError(f"unsupported payload {type(payload)!r}")
    return _read_json(payload)


def _read_json(path_or_payload: str | Path | Mapping[str, Any]) -> Dict[str, Any]:
    if isinstance(path_or_payload, Mapping):
        if not isinstance(path_or_payload, dict):
            raise DatasetSnapshotError("json payload must be an object")
        return dict(path_or_payload)
    path = Path(path_or_payload)
    _ensure_file_exists(path, str(path))
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DatasetSnapshotError(f"{path}: cannot read JSON: {exc}") from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DatasetSnapshotError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise DatasetSnapshotError(f"{path}: JSON must be an object")
    return value


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DatasetSnapshotError(f"{path}: cannot read JSONL: {exc}") from exc
    for line_no, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetSnapshotError(f"{path}:{line_no}: invalid JSONL record: {exc}") from exc
        if not isinstance(record, dict):
            raise DatasetSnapshotError(f"{path}:{line_no}: record must be an object")
        records.append(record)
    return records


def _read_annotations(path: Path) -> List[Dict[str, Any]]:
    return _read_jsonl(path)


def _read_annotation_policy(plan: Mapping[str, Any]) -> Dict[str, Any]:
    policy = plan.get("annotation_policy")
    if not isinstance(policy, dict):
        return {
            "minimum_distinct_raters": _DEFAULT_MIN_RATERS,
            "agreement_threshold": _DEFAULT_AGREEMENT_THRESHOLD,
            "enforce_cross_split_source_fingerprints": False,
        }
    if "minimum_distinct_raters" not in policy or "agreement_threshold" not in policy:
        raise DatasetSnapshotError("annotation_policy requires minimum_distinct_raters and agreement_threshold")
    min_raters = policy["minimum_distinct_raters"]
    agreement_threshold = policy["agreement_threshold"]
    if not isinstance(min_raters, int) or isinstance(min_raters, bool) or min_raters < 1:
        raise DatasetSnapshotError("annotation_policy.minimum_distinct_raters must be an integer >= 1")
    if not isinstance(agreement_threshold, (int, float)) or agreement_threshold < 0 or agreement_threshold > 1:
        raise DatasetSnapshotError("annotation_policy.agreement_threshold must be in [0,1]")
    return {
        "minimum_distinct_raters": min_raters,
        "agreement_threshold": float(agreement_threshold),
        "enforce_cross_split_source_fingerprints": bool(policy.get("enforce_cross_split_source_fingerprints", False)),
    }


def _evaluate_annotations(
    annotations: Sequence[Dict[str, Any]],
    case_by_id: Dict[str, Dict[str, Any]],
    minimum_distinct_raters: int,
    agreement_threshold: float,
) -> tuple[list[DatasetSnapshotIssue], dict[str, Any], dict[str, Any]]:
    seen_annotation_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    case_raters: Dict[str, set[str]] = {}
    case_labels: Dict[str, List[tuple[str, str]]] = {}

    for index, annotation in enumerate(annotations, start=1):
        annotation_id = annotation.get("annotation_id")
        if not isinstance(annotation_id, str) or not _CASE_ID_PATTERN.match(annotation_id):
            raise DatasetSnapshotError(f"annotation {index}: invalid annotation_id")
        if annotation_id in seen_annotation_ids:
            raise DatasetSnapshotError(f"duplicate annotation_id: {annotation_id}")
        seen_annotation_ids.add(annotation_id)

        case_id = annotation.get("case_id")
        if not isinstance(case_id, str) or case_id not in case_by_id:
            raise DatasetSnapshotError(f"annotation {annotation_id}: unknown case_id {case_id!r}")

        if not isinstance(annotation.get("non_empirical"), bool):
            raise DatasetSnapshotError(f"annotation {annotation_id}: non_empirical must be boolean")

        rater_id = annotation.get("rater_id")
        if not isinstance(rater_id, str) or not rater_id:
            raise DatasetSnapshotError(f"annotation {annotation_id}: invalid rater_id")

        label = annotation.get("label")
        if not isinstance(label, str) or not label:
            raise DatasetSnapshotError(f"annotation {annotation_id}: label must be a non-empty string")

        if (case_id, rater_id) in seen_pairs:
            raise DatasetSnapshotError(f"annotation {annotation_id}: duplicate rater {rater_id} for case {case_id}")
        seen_pairs.add((case_id, rater_id))

        case_raters.setdefault(case_id, set()).add(rater_id)
        case_labels.setdefault(case_id, []).append((rater_id, label))

    issues: list[DatasetSnapshotIssue] = []
    per_case_agreement: Dict[str, float] = {}
    total_pairs = 0
    total_agreement = 0
    for case_id in sorted(case_by_id):
        raters = case_raters.get(case_id, set())
        if len(raters) < minimum_distinct_raters:
            issues.append(
                DatasetSnapshotIssue(
                    "insufficient_raters",
                    "annotations",
                    f"{case_id}: only {len(raters)} distinct raters, minimum is {minimum_distinct_raters}",
                )
            )
            per_case_agreement[case_id] = 0.0
            continue
        labels = [label for _, label in case_labels[case_id]]
        match_count = 0
        pair_count = 0
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                pair_count += 1
                if labels[i] == labels[j]:
                    match_count += 1
        value = float(match_count / pair_count) if pair_count else 0.0
        per_case_agreement[case_id] = value
        total_pairs += pair_count
        total_agreement += match_count

    if not annotations:
        issues.append(DatasetSnapshotIssue("missing_annotations", "annotations", "annotations file is empty"))

    overall_agreement = float(total_agreement / total_pairs) if total_pairs else 0.0
    coverage = {
        "minimum_distinct_raters": minimum_distinct_raters,
        "response_counts": {case_id: len(case_raters.get(case_id, set())) for case_id in sorted(case_by_id)},
        "distinct_raters": sorted({rater for raters in case_raters.values() for rater in raters}),
    }
    agreement = {
        "metric": "exact_percent_agreement",
        "threshold": agreement_threshold,
        "overall": overall_agreement,
        "minimum_met": overall_agreement >= agreement_threshold and not any(
            issue.code == "insufficient_raters" for issue in issues
        ),
        "per_case": {case_id: value for case_id, value in sorted(per_case_agreement.items())},
    }
    if overall_agreement < agreement_threshold:
        issues.append(
            DatasetSnapshotIssue(
                "agreement_threshold_not_met",
                "annotations",
                f"overall agreement {overall_agreement:.3f} below threshold {agreement_threshold:.3f}",
            )
        )

    return issues, coverage, agreement


def _validate_provenance(
    *,
    case_id: str,
    provenance: Mapping[str, Any],
    registry_license: Any,
    issues: List[DatasetSnapshotIssue],
    allowed_source_types: Sequence[str] | None,
) -> None:
    source_type = provenance.get("source_type")
    created_at = provenance.get("created_at")
    license_value = provenance.get("license")
    source_uri = provenance.get("source_uri")
    source_id = provenance.get("source_id")
    source_url = provenance.get("source_url")
    if not isinstance(source_type, str) or not source_type.strip():
        issues.append(DatasetSnapshotIssue("invalid_provenance", "provenance.source_type", f"{case_id}: source_type must be a non-empty string"))
        return

    if allowed_source_types is not None:
        if source_type not in allowed_source_types:
            issues.append(DatasetSnapshotIssue("invalid_provenance", "provenance.source_type", f"{case_id}: source_type {source_type!r} not in plan source_type_policy"))

    if source_type == "synthetic":
        if not isinstance(source_uri, str) or not source_uri.startswith("urn:latent-triz:synthetic:"):
            issues.append(
                DatasetSnapshotIssue(
                    "invalid_provenance",
                    "provenance.source_uri",
                    f"{case_id}: synthetic source_uri must be urn:latent-triz:synthetic:<id>",
                )
            )
    else:
        if not isinstance(source_uri, str) or not source_uri.strip():
            issues.append(
                DatasetSnapshotIssue(
                    "invalid_provenance",
                    "provenance",
                    f"{case_id}: non-synthetic case requires source_uri",
                )
            )

    if not isinstance(created_at, str) or (not _DATE_PATTERN.match(created_at) and not _DATE_TIME_PATTERN.match(created_at)):
        issues.append(
            DatasetSnapshotIssue(
                "invalid_provenance",
                "provenance.created_at",
                f"{case_id}: created_at must be ISO date (YYYY-MM-DD) or UTC timestamp (YYYY-MM-DDTHH:MM:SSZ)",
            )
        )

    if not isinstance(license_value, str) or not license_value.strip():
        issues.append(DatasetSnapshotIssue("invalid_provenance", "provenance.license", f"{case_id}: license must be a non-empty string"))
    elif registry_license is not None and license_value != registry_license:
        issues.append(DatasetSnapshotIssue("license_mismatch", "provenance.license", f"{case_id}: provenance.license {license_value} does not match registry license {registry_license}"))


def _collect_source_fingerprint_payload(case: Mapping[str, Any], provenance: Mapping[str, Any]) -> str:
    source_uri = provenance.get("source_uri", "")
    source_id = provenance.get("source_id", "")
    source_type = provenance.get("source_type", "")
    source_url = provenance.get("source_url", "")
    return stable_json_dumps(
        {
            "source_uri": str(source_uri),
            "source_id": str(source_id),
            "source_type": str(source_type),
            "source_url": str(source_url),
        }
    )


def _collect_template_fingerprint_payload(case: Mapping[str, Any], provenance: Mapping[str, Any]) -> str | None:
    template_id = case.get("template_id") or provenance.get("template_id") or ""
    template_version = case.get("template_version") or provenance.get("template_version") or ""
    if not template_id and not template_version:
        return None
    return stable_json_dumps(
        {
            "template_id": str(template_id),
            "template_version": str(template_version),
        }
    )


def _extract_principles(case: Mapping[str, Any]) -> List[str]:
    direct = case.get("principles")
    if isinstance(direct, list):
        values = [str(item) for item in direct if isinstance(item, str)]
        if values:
            return sorted(set(values))
    labels = case.get("labels")
    if isinstance(labels, list):
        values = [str(item.get("principle")) for item in labels if isinstance(item, Mapping) and isinstance(item.get("principle"), str)]
        if values:
            return sorted(set(values))
    if isinstance(case.get("principle"), str):
        return [str(case.get("principle"))]
    return []


def _compute_split_membership_digest(cases: Sequence[Mapping[str, Any]]) -> str:
    membership = {}
    for case in cases:
        if not isinstance(case, Mapping):
            continue
        split = case.get("split")
        case_id = case.get("case_id")
        if not isinstance(split, str) or not isinstance(case_id, str):
            continue
        membership.setdefault(split, []).append(case_id)
    for values in membership.values():
        values.sort()
    payload = stable_json_dumps({split: membership.get(split, []) for split in sorted(membership)})
    return _stable_digest(payload)


def _extract_dataset_entry_record(registry_manifest: Mapping[str, Any], dataset_id: str) -> Mapping[str, Any] | None:
    datasets = registry_manifest.get("datasets")
    if not isinstance(datasets, list):
        return None
    for item in datasets:
        if not isinstance(item, Mapping):
            continue
        entry_id = item.get("dataset_id")
        if entry_id == dataset_id:
            return item
    return None


def _registry_entry_equivalent(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return dict(left) == dict(right)


def _stable_digest(payload: str | bytes) -> str:
    if isinstance(payload, bytes):
        return hashlib.sha256(payload).hexdigest()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _fingerprint_value(value: Any, path_hint: str | None = None) -> Dict[str, Any]:
    if isinstance(value, (str, Path)):
        path = Path(value)
        return _fingerprint_file(path)
    if not isinstance(value, (dict, list)):
        return {
            "sha256": _stable_digest(stable_json_dumps({"value": value})),
            "size": len(stable_json_dumps({"value": value}).encode("utf-8")),
        }
    payload = stable_json_dumps(value)
    return {"sha256": _stable_digest(payload), "size": len(payload.encode("utf-8"))}


def _fingerprint_file(path: Path) -> Dict[str, Any]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise DatasetSnapshotError(f"{path}: cannot read for fingerprinting: {exc}") from exc
    return {"sha256": _stable_digest(data), "size": len(data)}


def _issue_dict(issue: DatasetSnapshotIssue) -> Dict[str, str]:
    return {"code": issue.code, "field": issue.field, "message": issue.message}


def _is_valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[a-f0-9]{64}", value))


def _read_text_digest(path_or_text: str | Path | Mapping[str, Any]) -> str:
    if isinstance(path_or_text, Mapping):
        payload = stable_json_dumps(path_or_text)
    else:
        path = Path(path_or_text)
        try:
            payload = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise DatasetSnapshotError(f"{path}: cannot read case schema: {exc}") from exc
    return _stable_digest(payload)


def _ensure_file_exists(path: Path, label: str) -> None:
    if not path.is_file():
        raise DatasetSnapshotError(f"{label} path not found: {path}")


def _is_case_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_CASE_ID_PATTERN.match(value))


def _validate_datetime(value: str) -> str:
    if not _DATE_TIME_PATTERN.match(value):
        raise DatasetSnapshotError(f"invalid date-time: {value!r}")
    return value


def _infer_dataset_id(registry_entry: Mapping[str, Any], plan: Mapping[str, Any]) -> str:
    dataset_id = registry_entry.get("dataset_id") or plan.get("dataset_id")
    if isinstance(dataset_id, str) and dataset_id.strip():
        return dataset_id
    return "synthetic"
