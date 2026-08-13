from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence


_CASE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]+$")
_ALLOWED_SPLITS = {"discovery", "validation", "held_out_domain", "sealed_novel"}
_PARTICIPANT_FIELDS = (
    "problem",
    "initial_state",
    "desired_improvement",
    "worsening_consequence",
    "transformation",
    "resulting_state",
)


@dataclass(frozen=True)
class DatasetAuditIssue:
    code: str
    field: str
    message: str
    severity: str = "error"
    line: int | None = None
    case_id: str | None = None

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "code": self.code,
            "field": self.field,
            "message": self.message,
            "severity": self.severity,
        }
        if self.line is not None:
            payload["line"] = self.line
        if self.case_id is not None:
            payload["case_id"] = self.case_id
        return payload


class DatasetAuditError(RuntimeError):
    pass


def _read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as exc:
        raise DatasetAuditError(f"{path}: case not found: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DatasetAuditError(f"{path}: invalid JSON: {exc}") from exc
    except OSError as exc:
        raise DatasetAuditError(f"{path}: cannot read file: {exc}") from exc


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        raise DatasetAuditError(f"{path}: case file not found")
    records: List[Dict[str, Any]] = []
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise DatasetAuditError(f"{path}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise DatasetAuditError(f"{path}: record must be an object")
            records.append(record)
    except OSError as exc:
        raise DatasetAuditError(f"{path}: cannot read file: {exc}") from exc
    return records


def _normalize_text(value: str) -> str:
    lowered = value.strip().lower()
    collapsed = re.sub(r"\s+", " ", lowered)
    return re.sub(r"[^a-z0-9]+", " ", collapsed).strip()


def _collect_reference_values(case: Dict[str, Any]) -> Dict[str, List[Any]]:
    result = {}
    result["near_miss_case_ids"] = _ensure_string_list(case.get("near_miss_case_ids"), [])
    result["alternative_solution_case_ids"] = _ensure_string_list(case.get("alternative_solution_case_ids"), [])
    lexical = case.get("lexical_controls")
    if isinstance(lexical, dict):
        result["lexical_controls.matched_case_ids"] = _ensure_string_list(
            lexical.get("matched_case_ids"),
            [],
        )
    else:
        result["lexical_controls.matched_case_ids"] = []
    return result


def _ensure_string_list(raw: Any, default: List[Any]) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, str)]
    return default


def _find_forbidden_terms(text: str, forbidden_terms: Sequence[str]) -> List[str]:
    lowered = text.lower()
    found: List[str] = []
    for term in forbidden_terms:
        if not term:
            continue
        if re.search(re.escape(term.lower()), lowered):
            found.append(term)
    return found


def run_dataset_audit(
    plan_path: str | Path,
    cases_path: str | Path,
    mode: str = "development",
) -> Dict[str, Any]:
    plan = _read_json(Path(plan_path))
    if mode not in {"development", "freeze"}:
        raise DatasetAuditError(f"unsupported audit mode: {mode}")

    records = _read_jsonl(Path(cases_path))
    issues: List[DatasetAuditIssue] = []

    case_lines: Dict[str, int] = {}
    case_ids: Dict[str, Dict[str, Any]] = {}
    signature_to_cases: Dict[str, List[Dict[str, Any]]] = {}
    split_counts: Dict[str, int] = {split: 0 for split in _ALLOWED_SPLITS}
    domain_counts: Dict[str, int] = {}
    forbidden_terms: Sequence[str] = _coerce_str_list(plan.get("forbidden_lexical_terms"))

    for line_no, case in enumerate(records, start=1):
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not _CASE_ID_PATTERN.match(case_id):
            issues.append(
                DatasetAuditIssue(
                    code="invalid_case_id",
                    field="case_id",
                    message="case_id must be a lowercase identifier with alphanumerics, '.', '_' or '-'",
                    line=line_no,
                )
            )
            continue

        if case_id in case_ids:
            issues.append(
                DatasetAuditIssue(
                    code="duplicate_case_id",
                    field="case_id",
                    message=f"duplicate case_id {case_id}",
                    line=line_no,
                    case_id=case_id,
                )
            )
            continue

        case_lines[case_id] = line_no
        missing = _missing_case_fields(case)
        for field in missing:
            issues.append(
                DatasetAuditIssue(
                    code="missing_field",
                    field=field,
                    message=f"{field} is required for dataset audit checks",
                    line=line_no,
                    case_id=case_id,
                )
            )

        split = case.get("split")
        if split not in _ALLOWED_SPLITS:
            issues.append(
                DatasetAuditIssue(
                    code="invalid_split",
                    field="split",
                    message=f"split {split!r} is not allowed",
                    line=line_no,
                    case_id=case_id,
                )
            )
        else:
            split_counts[split] = split_counts.get(split, 0) + 1

        domain = case.get("domain")
        if not isinstance(domain, str) or not domain.strip():
            issues.append(
                DatasetAuditIssue(
                    code="invalid_domain",
                    field="domain",
                    message="domain must be a non-empty string",
                    line=line_no,
                    case_id=case_id,
                )
            )
        else:
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        refs = _collect_reference_values(case)
        for field, targets in refs.items():
            seen_targets = set()
            for target in targets:
                if not isinstance(target, str):
                    issues.append(
                        DatasetAuditIssue(
                            code="invalid_reference_type",
                            field=field,
                            message=f"{field} must contain only strings",
                            line=line_no,
                            case_id=case_id,
                        )
                    )
                    continue
                if target in seen_targets:
                    issues.append(
                        DatasetAuditIssue(
                            code="duplicate_reference_value",
                            field=field,
                            message=f"duplicate reference {target!r} in case {case_id}",
                            line=line_no,
                            case_id=case_id,
                        )
                    )
                    continue
                seen_targets.add(target)
                if target == case_id:
                    issues.append(
                        DatasetAuditIssue(
                            code="self_reference",
                            field=field,
                            message=f"case {case_id} references itself via {field}",
                            line=line_no,
                            case_id=case_id,
                        )
                    )

        case_ids[case_id] = case

        signature = "||".join(
            [
                _normalize_text(case.get("domain", "")),
                _normalize_text(" ".join(_as_string_list(case.get("constraints", [])))),
                *[
                    _normalize_text(case.get(_field, "")) if isinstance(case.get(_field), str) else ""
                    for _field in _PARTICIPANT_FIELDS
                ],
            ]
        )
        signature_to_cases.setdefault(signature, []).append(case)

        participant_text = []
        for field in _PARTICIPANT_FIELDS:
            if isinstance(case.get(field), str):
                participant_text.append(case[field])
        for constraint in _as_string_list(case.get("constraints", [])):
            participant_text.append(constraint)
        joined = "\n".join(participant_text)
        for term in _find_forbidden_terms(joined, forbidden_terms):
            issues.append(
                DatasetAuditIssue(
                    code="forbidden_term",
                    field="participant_text",
                    message=f"forbidden lexical term detected: {term!r} in case {case_id}",
                    line=line_no,
                    case_id=case_id,
                )
            )

    # Reference integrity checks must run after loading all ids.
    for case_id, case in case_ids.items():
        line_no = case_lines.get(case_id, 0)
        refs = _collect_reference_values(case)
        for field, targets in refs.items():
            for target in targets:
                if target not in case_ids:
                    issues.append(
                        DatasetAuditIssue(
                            code="missing_reference",
                            field=field,
                            message=f"case {case_id} references missing case_id {target!r}",
                            line=line_no,
                            case_id=case_id,
                        )
                    )

    # Matched-case symmetry checks.
    if bool(plan.get("reference_controls", {}).get("enforce_matched_case_id_symmetry")):
        for case_id, case in case_ids.items():
            line_no = case_lines.get(case_id, 0)
            refs = _collect_reference_values(case)
            for target in refs["lexical_controls.matched_case_ids"]:
                target_refs = _collect_reference_values(case_ids[target]).get("lexical_controls.matched_case_ids", [])
                if case_id not in set(target_refs):
                    issues.append(
                        DatasetAuditIssue(
                            code="asymmetric_matched_reference",
                            field="lexical_controls.matched_case_ids",
                            message=f"case {case_id} has unmatched matched_case_id relation with {target}",
                            line=line_no,
                            case_id=case_id,
                        )
                    )

    # Duplicate and leakage checks.
    for signature, records_for_signature in signature_to_cases.items():
        if len(records_for_signature) < 2:
            continue
        seen_cases: List[Dict[str, Any]] = []
        for current in records_for_signature:
            current_split = current.get("split", "")
            current_id = current.get("case_id", "")
            current_line = case_lines.get(current_id, 0)
            for other in seen_cases:
                other_id = other.get("case_id", "")
                other_line = case_lines.get(other_id if isinstance(other_id, str) else "", 0)
                other_split = other.get("split", "")
                if current_split == other_split:
                    issues.append(
                        DatasetAuditIssue(
                            code="duplicate_signature",
                            field="problem_definition",
                            message=f"duplicated normalized case content within split {current_split!r}: {current_id} and {other_id}",
                            line=current_line,
                            case_id=current_id if isinstance(current_id, str) else None,
                        )
                    )
                else:
                    issues.append(
                        DatasetAuditIssue(
                            code="cross_split_leakage",
                            field="problem_definition",
                            message=(
                                "normalized case content repeated across splits: "
                                f"{current_id} in {current_split!r} and {other_id} in {other_split!r}"
                            ),
                            line=current_line,
                            case_id=current_id if isinstance(current_id, str) else None,
                        )
                    )
            seen_cases.append(current)

    # Target gates and source policies.
    splits_plan = plan.get("splits", {})
    enforce_targets = mode == "freeze" or bool(plan.get("enforce_targets", False))
    target_gaps: List[Dict[str, Any]] = []
    target_ok = True
    total_cases = len(records)

    if not isinstance(splits_plan, dict):
        issues.append(
            DatasetAuditIssue(
                code="invalid_plan",
                field="splits",
                message="plan.splits must be an object",
                severity="error",
            )
        )
        enforce_targets = False
        target_ok = False
    else:
        for split_name in sorted(_ALLOWED_SPLITS):
            plan_for_split = splits_plan.get(split_name, {})
            if not isinstance(plan_for_split, dict):
                plan_for_split = {}
            target_min = plan_for_split.get("target_min", 0) or 0
            target_exact = plan_for_split.get("target_exact")
            actual = split_counts.get(split_name, 0)
            if actual < target_min:
                target_gaps.append(
                    {
                        "split": split_name,
                        "metric": "target_min",
                        "actual": actual,
                        "target": target_min,
                        "gap": target_min - actual,
                    }
                )
                if enforce_targets:
                    target_ok = False
            if target_exact is not None and actual != target_exact:
                target_gaps.append(
                    {
                        "split": split_name,
                        "metric": "target_exact",
                        "actual": actual,
                        "target": target_exact,
                        "gap": actual - target_exact,
                    }
                )
                if enforce_targets:
                    target_ok = False

    min_domains = int(plan.get("min_domains", 0) or 0)
    if len(domain_counts) < min_domains:
        target_gaps.append(
            {
                "metric": "min_domains",
                "actual": len(domain_counts),
                "target": min_domains,
                "gap": min_domains - len(domain_counts),
            }
        )
        if enforce_targets:
            target_ok = False

    target_size = int(plan.get("target_size", 0) or 0)
    if target_size and total_cases != target_size:
        target_gaps.append(
            {
                "metric": "target_size_exact",
                "actual": total_cases,
                "target": target_size,
                "gap": total_cases - target_size,
            }
        )
        if enforce_targets:
            target_ok = False

    source_policy = plan.get("source_type_policy")
    if isinstance(source_policy, dict):
        allowed_source_types = set(_coerce_str_list(source_policy.get("allowed_source_types")))
        max_model_ratio = source_policy.get("max_model_generated_ratio")
        if allowed_source_types:
            total_with_policy = 0
            model_generated_count = 0
            for line_no, case in enumerate(records, start=1):
                case_id = case.get("case_id")
                provenance = case.get("provenance")
                if not isinstance(provenance, dict):
                    issues.append(
                        DatasetAuditIssue(
                            code="missing_provenance_source_type",
                            field="provenance.source_type",
                            message=f"{case_id}: provenance must be an object for source policy checks",
                            line=line_no,
                            case_id=case_id if isinstance(case_id, str) else None,
                        )
                    )
                    continue
                source_type = provenance.get("source_type")
                if not isinstance(source_type, str):
                    issues.append(
                        DatasetAuditIssue(
                            code="invalid_source_type",
                            field="provenance.source_type",
                            message=f"{case_id}: source_type must be a string",
                            line=line_no,
                            case_id=case_id if isinstance(case_id, str) else None,
                        )
                    )
                    continue
                total_with_policy += 1
                if source_type == "model_generated":
                    model_generated_count += 1
                if source_type not in allowed_source_types:
                    issues.append(
                        DatasetAuditIssue(
                            code="invalid_source_type",
                            field="provenance.source_type",
                            message=f"{case_id}: source_type {source_type!r} not in allowed_source_types",
                            line=line_no,
                            case_id=case_id if isinstance(case_id, str) else None,
                        )
                    )
            if total_with_policy and isinstance(max_model_ratio, (int, float)):
                ratio = model_generated_count / total_with_policy
                if ratio > max_model_ratio:
                    issues.append(
                        DatasetAuditIssue(
                            code="max_model_generated_ratio_exceeded",
                            field="source_type_policy.max_model_generated_ratio",
                            message=(
                                "model_generated_ratio "
                                f"{ratio:.3f} exceeds maximum {max_model_ratio}"
                            ),
                            line=0,
                        )
                    )

    structural_ok = not any(
        issue.code.startswith(
            (
                "invalid_",
                "self_reference",
                "missing_reference",
                "duplicate_case_id",
                "duplicate_reference_value",
                "asymmetric_matched_reference",
            )
        )
        for issue in issues
    )

    if enforce_targets:
        freeze_ready = structural_ok and target_ok and not target_gaps
    else:
        freeze_ready = structural_ok and not target_gaps

    status = "pass"
    if not structural_ok:
        status = "fail"
    elif mode == "freeze" and target_gaps:
        status = "fail"
    elif mode == "development" and target_gaps:
        status = "pass_with_gaps"

    return {
        "mode": mode,
        "ready": bool(freeze_ready),
        "freeze_ready": bool(freeze_ready),
        "status": status,
        "structural_ok": structural_ok,
        "targets_passed": bool(not target_gaps if not enforce_targets else target_ok),
        "total_cases": total_cases,
        "counts": {
            "by_split": split_counts,
            "by_domain": dict(sorted(domain_counts.items(), key=lambda item: item[0])),
        },
        "issues": [issue.as_dict() for issue in issues],
        "target_gaps": target_gaps,
        "targets_enforced": enforce_targets,
    }


def _missing_case_fields(case: Dict[str, Any]) -> List[str]:
    required_fields = (
        "case_id",
        "domain",
        "problem",
        "constraints",
        "initial_state",
        "desired_improvement",
        "worsening_consequence",
        "transformation",
        "resulting_state",
        "split",
        "provenance",
    )
    return [field for field in required_fields if field not in case]


def _coerce_str_list(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]


def _as_string_list(raw: Any) -> List[str]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, str)]
    return []


def stable_json_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
