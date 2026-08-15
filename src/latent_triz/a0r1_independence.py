"""Deterministic independence audit for A0-R1 candidate inputs."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


EPISTEMIC = {
    "empirical": True,
    "scientific_status": "exploratory",
    "evidence_eligible": False,
    "expert_validated": False,
    "claim_ids": [],
}

PARTICIPANT_TEXT_FIELDS = (
    "problem",
    "initial_state",
    "desired_improvement",
    "worsening_consequence",
    "transformation",
    "resulting_state",
)

DEFAULT_PARTITION_NAMES = ("calibration", "sealed")
DEFAULT_PARTITION_SPLIT_FIELD = "split"
DEFAULT_NEAR_DUPLICATE_THRESHOLD = 0.78
DEFAULT_NGRAM_N = 3


class A0R1IndependenceAuditError(RuntimeError):
    """Raised when audit inputs are structurally invalid."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise A0R1IndependenceAuditError(f"{path}: cannot read JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise A0R1IndependenceAuditError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise A0R1IndependenceAuditError(f"{path}: root object must be an object")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise A0R1IndependenceAuditError(f"{path}: cannot read JSONL: {exc}") from exc

    records: list[dict[str, Any]] = []
    for line_no, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise A0R1IndependenceAuditError(
                f"{path}:{line_no}: invalid JSON: {exc.msg}"
            ) from exc
        if not isinstance(payload, dict):
            raise A0R1IndependenceAuditError(
                f"{path}:{line_no}: each JSONL record must be an object"
            )
        records.append(payload)
    return records


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strip(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _normalize_text(value: str) -> str:
    lowered = value.strip().lower()
    normalized = re.sub(r"\s+", " ", lowered)
    return re.sub(r"[^a-z0-9 ]+", " ", normalized).strip()


def _text_signature(value: str) -> str:
    return hashlib.sha256(_normalize_text(value).encode("utf-8")).hexdigest()


def _participant_text(record: Mapping[str, Any]) -> str:
    return " ".join(_strip(record.get(field)) for field in PARTICIPANT_TEXT_FIELDS).strip()


def _shingles(text: str, n: int) -> set[str]:
    tokens = [token for token in _normalize_text(text).split() if token]
    if n <= 0 or len(tokens) < n:
        return set()
    return {
        " ".join(tokens[index : index + n])
        for index in range(len(tokens) - n + 1)
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _coerce_str(value: Any, field: str, violations: list[dict[str, Any]]) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    violations.append(
        {"code": "invalid_manifest_value", "field": field, "message": f"{field} must be a non-empty string"}
    )
    return None


def _coerce_int(value: Any, field: str, violations: list[dict[str, Any]]) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value):
        return int(value)
    violations.append(
        {"code": "invalid_manifest_value", "field": field, "message": f"{field} must be an integer"}
    )
    return None


def _coerce_partition_names(manifest: Mapping[str, Any], violations: list[dict[str, Any]]) -> tuple[str, str, str]:
    partitions = manifest.get("partitions")
    if not isinstance(partitions, Mapping):
        return (
            DEFAULT_PARTITION_NAMES[0],
            DEFAULT_PARTITION_NAMES[1],
            DEFAULT_PARTITION_SPLIT_FIELD,
        )

    calibration = partitions.get("calibration_split")
    sealed = partitions.get("sealed_split")
    split_field = partitions.get("split_field")
    if not isinstance(calibration, str) or not calibration.strip():
        calibration = DEFAULT_PARTITION_NAMES[0]
        violations.append(
            {
                "code": "invalid_manifest_value",
                "field": "partitions/calibration_split",
                "message": "missing calibration split; using default",
            }
        )
    if not isinstance(sealed, str) or not sealed.strip():
        sealed = DEFAULT_PARTITION_NAMES[1]
        violations.append(
            {
                "code": "invalid_manifest_value",
                "field": "partitions/sealed_split",
                "message": "missing sealed split; using default",
            }
        )
    if not isinstance(split_field, str) or not split_field.strip():
        split_field = DEFAULT_PARTITION_SPLIT_FIELD
    return calibration.strip(), sealed.strip(), split_field.strip()


def _collect_cases_by_id(records: list[dict[str, Any]], label: str, violations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records, start=1):
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            violations.append(
                {
                    "code": "invalid_case_id",
                    "message": f"{label} case_id must be non-empty",
                    "line": index,
                }
            )
            continue
        if case_id in seen:
            violations.append(
                {
                    "code": "duplicate_case_id",
                    "case_id": case_id,
                    "message": f"{label} case_id appears more than once",
                }
            )
            continue
        seen[case_id] = record
    return seen


def _collect_target_records(
    records: list[dict[str, Any]],
    expected_split: str,
    split_field: str,
    label: str,
    violations: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records, start=1):
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            violations.append(
                {
                    "code": "invalid_target_case_id",
                    "message": f"{label} target case_id must be non-empty",
                    "line": index,
                }
            )
            continue
        if case_id in seen:
            violations.append(
                {
                    "code": "duplicate_target_case_id",
                    "case_id": case_id,
                    "message": f"{label} target case_id appears more than once in file",
                }
            )
            continue
        split = _strip(record.get(split_field))
        if split != expected_split:
            violations.append(
                {
                    "code": "invalid_target_partition",
                    "case_id": case_id,
                    "message": f"{label} target split is {split!r}, expected {expected_split!r}",
                    "expected_split": expected_split,
                    "split_field": split_field,
                }
            )
        seen[case_id] = record
    return seen


def _target_family(record: Mapping[str, Any]) -> str:
    family = record.get("problem_family_id")
    return family.strip() if isinstance(family, str) else ""


def _template_id(record: Mapping[str, Any]) -> str:
    direct = _strip(record.get("template_id"))
    if direct:
        return direct
    provenance = record.get("provenance")
    if isinstance(provenance, Mapping):
        return _strip(provenance.get("template_id"))
    return ""


def _manifest_seed(manifest: Mapping[str, Any], label: str, violations: list[dict[str, Any]]) -> int | None:
    if "deterministic_seed" in manifest:
        return _coerce_int(manifest.get("deterministic_seed"), f"{label}_deterministic_seed", violations)
    return _coerce_int(manifest.get("seed"), f"{label}_seed", violations)


def run_a0r1_independence_audit(
    *,
    candidate_manifest_path: str | Path,
    candidate_cases_path: str | Path,
    candidate_calibration_targets_path: str | Path,
    candidate_sealed_targets_path: str | Path,
    source_manifest_path: str | Path,
    source_cases_path: str | Path,
    source_calibration_targets_path: str | Path,
    source_sealed_targets_path: str | Path,
) -> dict[str, Any]:
    candidate_manifest_file = Path(candidate_manifest_path).resolve()
    candidate_cases_file = Path(candidate_cases_path).resolve()
    candidate_calibration_targets_file = Path(candidate_calibration_targets_path).resolve()
    candidate_sealed_targets_file = Path(candidate_sealed_targets_path).resolve()
    source_manifest_file = Path(source_manifest_path).resolve()
    source_cases_file = Path(source_cases_path).resolve()
    source_calibration_targets_file = Path(source_calibration_targets_path).resolve()
    source_sealed_targets_file = Path(source_sealed_targets_path).resolve()

    for path in (
        candidate_manifest_file,
        candidate_cases_file,
        candidate_calibration_targets_file,
        candidate_sealed_targets_file,
        source_manifest_file,
        source_cases_file,
        source_calibration_targets_file,
        source_sealed_targets_file,
    ):
        if not path.is_file():
            raise A0R1IndependenceAuditError(f"{path}: missing required file")

    violations: list[dict[str, Any]] = []

    candidate_manifest = _read_json(candidate_manifest_file)
    source_manifest = _read_json(source_manifest_file)

    candidate_cases = _read_jsonl(candidate_cases_file)
    candidate_calibration_targets = _read_jsonl(candidate_calibration_targets_file)
    candidate_sealed_targets = _read_jsonl(candidate_sealed_targets_file)
    source_cases = _read_jsonl(source_cases_file)
    source_calibration_targets = _read_jsonl(source_calibration_targets_file)
    source_sealed_targets = _read_jsonl(source_sealed_targets_file)

    if not candidate_cases:
        raise A0R1IndependenceAuditError("candidate cases file is empty")
    if not source_cases:
        raise A0R1IndependenceAuditError("source cases file is empty")

    candidate_case_by_id = _collect_cases_by_id(candidate_cases, "candidate", violations)
    source_case_by_id = _collect_cases_by_id(source_cases, "source", violations)

    candidate_cases_set = set(candidate_case_by_id)
    source_cases_set = set(source_case_by_id)

    candidate_calibration_split, candidate_sealed_split, candidate_split_field = _coerce_partition_names(
        candidate_manifest, violations
    )
    source_calibration_split, source_sealed_split, source_split_field = _coerce_partition_names(
        source_manifest, violations
    )

    candidate_calibration_targets_by_id = _collect_target_records(
        candidate_calibration_targets, candidate_calibration_split, candidate_split_field,
        "candidate calibration", violations,
    )
    candidate_sealed_targets_by_id = _collect_target_records(
        candidate_sealed_targets, candidate_sealed_split, candidate_split_field,
        "candidate sealed", violations,
    )
    source_calibration_targets_by_id = _collect_target_records(
        source_calibration_targets, source_calibration_split, source_split_field,
        "source calibration", violations,
    )
    source_sealed_targets_by_id = _collect_target_records(
        source_sealed_targets, source_sealed_split, source_split_field,
        "source sealed", violations,
    )

    candidate_family_ids: set[str] = set()
    source_family_ids: set[str] = set()
    candidate_template_ids: set[str] = set()
    source_template_ids: set[str] = set()
    candidate_case_texts: dict[str, str] = {}
    source_case_texts: dict[str, str] = {}
    source_target_texts: set[str] = set()

    for case_id, record in candidate_case_by_id.items():
        family_id = _strip(record.get("problem_family_id"))
        if family_id:
            candidate_family_ids.add(family_id)
        template_id = _template_id(record)
        if template_id:
            candidate_template_ids.add(template_id)

        text = _participant_text(record)
        candidate_case_texts[case_id] = _normalize_text(text)

        for key, value in record.items():
            if key in PARTICIPANT_TEXT_FIELDS:
                continue
            if not isinstance(value, str):
                continue
            normalized_key = key.lower()
            if (
                "target" in normalized_key
                or "ground" in normalized_key
                or ("label" in normalized_key and "truth" in normalized_key)
            ):
                value_text = _normalize_text(value)
                if value_text:
                    violations.append(
                        {
                            "code": "target_leakage_field",
                            "case_id": case_id,
                            "message": f"candidate case has surfaced target-like field {key}",
                        }
                    )

    for case_id, record in source_case_by_id.items():
        family_id = _strip(record.get("problem_family_id"))
        if family_id:
            source_family_ids.add(family_id)
        template_id = _template_id(record)
        if template_id:
            source_template_ids.add(template_id)
        source_case_texts[case_id] = _normalize_text(_participant_text(record))

    for target in source_calibration_targets:
        for key, value in target.items():
            if not isinstance(value, str):
                continue
            key_l = key.lower()
            if key_l in {"case_id", "split", "partition"}:
                continue
            value_text = _normalize_text(value)
            if value_text:
                source_target_texts.add(value_text)
    for target in source_sealed_targets:
        for key, value in target.items():
            if not isinstance(value, str):
                continue
            key_l = key.lower()
            if key_l in {"case_id", "split", "partition"}:
                continue
            value_text = _normalize_text(value)
            if value_text:
                source_target_texts.add(value_text)

    reused_case_ids = sorted(candidate_cases_set & source_cases_set)
    for value in reused_case_ids:
        violations.append(
            {"code": "reused_case_id", "case_id": value, "message": "case_id reused from source A0 corpus"}
        )

    for value in sorted(candidate_family_ids & source_family_ids):
        violations.append(
            {
                "code": "reused_family_id",
                "field_value": value,
                "message": "problem_family_id reused from source A0 corpus",
            }
        )

    for value in sorted(candidate_template_ids & source_template_ids):
        violations.append(
            {
                "code": "reused_template_id",
                "field_value": value,
                "message": "template_id reused from source A0 corpus",
            }
        )

    source_text_index: dict[str, list[str]] = {}
    for case_id, normalized in source_case_texts.items():
        source_text_index.setdefault(normalized, []).append(case_id)
    for case_id in sorted(candidate_case_texts):
        normalized = candidate_case_texts[case_id]
        if not normalized:
            continue
        matches = source_text_index.get(normalized)
        if matches:
            violations.append(
                {
                    "code": "exact_normalized_text_reused",
                    "case_id": case_id,
                    "matches": matches,
                    "message": "exact normalized text reused from A0 source case",
                }
            )

    candidate_signatures = {
        case_id: _shingles(_participant_text(record), DEFAULT_NGRAM_N)
        for case_id, record in candidate_case_by_id.items()
    }
    source_signatures = {
        case_id: _shingles(_participant_text(record), DEFAULT_NGRAM_N)
        for case_id, record in source_case_by_id.items()
    }
    for candidate_id in sorted(candidate_signatures):
        candidate_sig = candidate_signatures[candidate_id]
        for source_id in sorted(source_signatures):
            score = _jaccard(candidate_sig, source_signatures[source_id])
            if score >= DEFAULT_NEAR_DUPLICATE_THRESHOLD:
                violations.append(
                    {
                        "code": "near_duplicate_shingles",
                        "candidate_case_id": candidate_id,
                        "source_case_id": source_id,
                        "similarity": round(score, 6),
                        "message": "near-duplicate shingles overlap with source case",
                    }
                )

    for case_id, record in candidate_case_by_id.items():
        candidate_text = _normalize_text(_participant_text(record))
        for source_target in sorted(source_target_texts):
            if len(source_target) >= 20 and source_target in candidate_text:
                violations.append(
                    {
                        "code": "target_content_leakage",
                        "case_id": case_id,
                        "target_fingerprint": _text_signature(source_target),
                        "message": "candidate surfaced fields contain source target text",
                    }
                )
                break

    candidate_calibration_ids = set(candidate_calibration_targets_by_id)
    candidate_sealed_ids = set(candidate_sealed_targets_by_id)
    source_calibration_ids = set(source_calibration_targets_by_id)
    source_sealed_ids = set(source_sealed_targets_by_id)

    for case_id in sorted(candidate_calibration_ids & candidate_sealed_ids):
        violations.append(
            {
                "code": "target_case_cross_partition",
                "case_id": case_id,
                "message": "candidate case_id appears in both calibration and sealed target partitions",
            }
        )
    for case_id in sorted(source_calibration_ids & source_sealed_ids):
        violations.append(
            {
                "code": "target_case_cross_partition",
                "case_id": case_id,
                "message": "source case_id appears in both calibration and sealed target partitions",
            }
        )

    candidate_calibration_families = {_strip(target.get("problem_family_id")) for target in candidate_calibration_targets if _strip(target.get("problem_family_id"))}
    candidate_sealed_families = {_strip(target.get("problem_family_id")) for target in candidate_sealed_targets if _strip(target.get("problem_family_id"))}
    source_calibration_families = {_strip(target.get("problem_family_id")) for target in source_calibration_targets if _strip(target.get("problem_family_id"))}
    source_sealed_families = {_strip(target.get("problem_family_id")) for target in source_sealed_targets if _strip(target.get("problem_family_id"))}

    for family_id in sorted(candidate_calibration_families & candidate_sealed_families):
        violations.append(
            {
                "code": "target_family_cross_partition",
                "field_value": family_id,
                "message": "candidate family_id appears in both calibration and sealed target partitions",
            }
        )
    for family_id in sorted(source_calibration_families & source_sealed_families):
        violations.append(
            {
                "code": "target_family_cross_partition",
                "field_value": family_id,
                "message": "source family_id appears in both calibration and sealed target partitions",
            }
            )

    candidate_target_case_ids = set(candidate_calibration_targets_by_id) | set(candidate_sealed_targets_by_id)
    source_target_case_ids = set(source_calibration_targets_by_id) | set(source_sealed_targets_by_id)

    orphan_candidate_targets = sorted(candidate_target_case_ids - candidate_cases_set)
    if orphan_candidate_targets:
        violations.append(
            {
                "code": "orphan_target_case_ids",
                "field": "candidate_targets",
                "ids": orphan_candidate_targets,
                "message": "candidate target row has no matching case",
            }
        )

    missing_candidate_targets = sorted(candidate_cases_set - candidate_target_case_ids)
    if missing_candidate_targets:
        violations.append(
            {
                "code": "missing_target_for_case",
                "field": "candidate_targets",
                "ids": missing_candidate_targets,
                "message": "candidate case is missing a target row",
            }
        )

    orphan_source_targets = sorted(source_target_case_ids - source_cases_set)
    if orphan_source_targets:
        violations.append(
            {
                "code": "orphan_target_case_ids",
                "field": "source_targets",
                "ids": orphan_source_targets,
                "message": "source target row has no matching case",
            }
        )

    if not candidate_calibration_targets:
        violations.append({"code": "missing_candidate_partition", "message": "candidate calibration target partition has no rows"})
    if not candidate_sealed_targets:
        violations.append({"code": "missing_candidate_partition", "message": "candidate sealed target partition has no rows"})
    if not source_calibration_targets:
        violations.append({"code": "invalid_source_partitioning", "message": "source calibration target partition has no rows"})
    if not source_sealed_targets:
        violations.append({"code": "invalid_source_partitioning", "message": "source sealed target partition has no rows"})

    candidate_seed = _manifest_seed(candidate_manifest, "candidate", violations)
    source_seed = _manifest_seed(source_manifest, "source", violations)
    if candidate_seed is not None and source_seed is not None and candidate_seed == source_seed:
        violations.append(
            {
                "code": "reused_seed",
                "candidate_seed": candidate_seed,
                "source_seed": source_seed,
                "message": "candidate and source deterministic_seed are identical",
            }
        )

    report = {
        "artifact_class": "a0-r1-independence-audit",
        **EPISTEMIC,
        "protocol_id": _coerce_str(candidate_manifest.get("protocol_id"), "protocol_id", violations) or "unknown",
        "status": "pass" if not violations else "fail",
        "ready": not violations,
        "counts": {
            "candidate": {
                "cases": len(candidate_cases),
                "targets": len(candidate_calibration_targets) + len(candidate_sealed_targets),
                "case_partitions": {
                    "calibration": len(candidate_calibration_targets),
                    "sealed": len(candidate_sealed_targets),
                },
            },
            "source": {
                "cases": len(source_cases),
                "targets": len(source_calibration_targets) + len(source_sealed_targets),
                "case_partitions": {
                    "calibration": len(source_calibration_targets),
                    "sealed": len(source_sealed_targets),
                },
            },
        },
        "partitions": {
            "candidate_split_field": candidate_split_field,
            "source_split_field": source_split_field,
            "required_partitions": {
                "candidate": {
                    "calibration": candidate_calibration_split,
                    "sealed": candidate_sealed_split,
                },
                "source": {
                    "calibration": source_calibration_split,
                    "sealed": source_sealed_split,
                },
            },
            "candidate_split_values": {
                "calibration": sorted(candidate_calibration_targets_by_id),
                "sealed": sorted(candidate_sealed_targets_by_id),
            },
            "source_split_values": {
                "calibration": sorted(source_calibration_targets_by_id),
                "sealed": sorted(source_sealed_targets_by_id),
            },
        },
        "hashes": {
            "candidate_manifest_sha256": _sha256(candidate_manifest_file),
            "source_manifest_sha256": _sha256(source_manifest_file),
            "candidate_cases_sha256": _sha256(candidate_cases_file),
            "candidate_calibration_targets_sha256": _sha256(candidate_calibration_targets_file),
            "candidate_sealed_targets_sha256": _sha256(candidate_sealed_targets_file),
            "source_cases_sha256": _sha256(source_cases_file),
            "source_calibration_targets_sha256": _sha256(source_calibration_targets_file),
            "source_sealed_targets_sha256": _sha256(source_sealed_targets_file),
        },
        "violations": sorted(
            violations,
            key=lambda item: (
                str(item.get("code")),
                str(item.get("case_id", "")),
                str(item.get("field_value", "")),
            ),
        ),
    }
    return report
