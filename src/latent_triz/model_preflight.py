from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from .validator import validate


_REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_MODEL_ROLES = ("primary", "replication", "fallback")


@dataclass(frozen=True)
class ModelPreflightIssue:
    code: str
    field: str
    message: str

    def as_dict(self) -> Dict[str, str]:
        return {
            "code": self.code,
            "field": self.field,
            "message": self.message,
        }


class ModelPreflightError(RuntimeError):
    pass


def _read_manifest(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            records = [json.loads(line) for line in file.read().splitlines() if line.strip()]
    except FileNotFoundError as exc:
        raise ModelPreflightError(f"{path}: file not found") from exc
    except json.JSONDecodeError as exc:
        raise ModelPreflightError(f"{path}: invalid JSONL: {exc}") from exc
    except OSError as exc:
        raise ModelPreflightError(f"{path}: cannot read file: {exc}") from exc

    if len(records) == 1 and isinstance(records[0], dict) and "candidates" in records[0]:
        manifest = records[0]
        if not isinstance(manifest.get("candidates"), list):
            raise ModelPreflightError(f"{path}: candidates must be an array")
    elif len(records) == 1 and isinstance(records[0], dict):
        if not _looks_like_candidate(records[0]):
            raise ModelPreflightError(f"{path}: expected a candidate object or a manifest with candidates")
        manifest = {"candidates": records}
    else:
        manifest = {"candidates": records}

    if not manifest["candidates"]:
        raise ModelPreflightError(f"{path}: candidates array must not be empty")
    return manifest


def _coerce_str_list(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]


def _looks_like_candidate(record: Dict[str, Any]) -> bool:
    return "role" in record or "model_id" in record


def _candidate_sources(candidate: Dict[str, Any]) -> Dict[str, str]:
    return {
        "model_card_url": candidate.get("model_card_url", ""),
        "terms_url": candidate.get("terms_url", ""),
        "evidence_url": candidate.get("evidence_url", ""),
    }


def _load_schema() -> Dict[str, Any]:
    schema_path = Path(__file__).resolve().parents[2] / "schemas/model-candidate.schema.json"
    try:
        with schema_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as exc:
        raise ModelPreflightError(f"{schema_path}: schema not found") from exc
    except json.JSONDecodeError as exc:
        raise ModelPreflightError(f"{schema_path}: invalid schema JSON: {exc}") from exc
    except OSError as exc:
        raise ModelPreflightError(f"{schema_path}: cannot read schema: {exc}") from exc


def _validate_candidate(candidate: Dict[str, Any], index: int) -> List[ModelPreflightIssue]:
    issues: List[ModelPreflightIssue] = []
    for field in ("role", "model_id", "revision", "license_id", "acquisition_status", "weights_present"):
        if field not in candidate:
            issues.append(ModelPreflightIssue("missing_field", field, f"{field} is required for model preflight"))
    role = candidate.get("role")
    if role not in _MODEL_ROLES:
        issues.append(ModelPreflightIssue("invalid_role", "role", f"candidate {index} role {role!r} is not supported"))
    revision = candidate.get("revision")
    if not isinstance(revision, str) or not _REVISION_PATTERN.match(revision):
        issues.append(ModelPreflightIssue("invalid_revision", "revision", f"candidate {index} revision must be an exact 40-hex digest"))
    if candidate.get("acquisition_status") != "not_acquired":
        issues.append(
            ModelPreflightIssue(
                "invalid_acquisition_status",
                "acquisition_status",
                f"candidate {index} must remain not_acquired until an operator receipts the acquisition",
            )
        )
    if candidate.get("weights_present") is not False:
        issues.append(
            ModelPreflightIssue(
                "invalid_weights_state",
                "weights_present",
                f"candidate {index} weights_present must be false in a no-download preflight",
            )
        )
    for field, value in _candidate_sources(candidate).items():
        if not isinstance(value, str) or not value.strip():
            issues.append(ModelPreflightIssue("missing_provenance", field, f"{field} is required"))
    required_capabilities = _coerce_str_list(candidate.get("required_capabilities"))
    if not required_capabilities:
        issues.append(
            ModelPreflightIssue(
                "missing_capabilities",
                "required_capabilities",
                f"candidate {index} must declare required capabilities",
            )
        )
    return issues


def run_model_preflight(path: str | Path) -> Dict[str, Any]:
    manifest = _read_manifest(Path(path))
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list):
        raise ModelPreflightError("model candidate manifest must contain a candidates array")

    issues: List[ModelPreflightIssue] = []
    seen_roles: set[str] = set()
    seen_model_ids: set[str] = set()
    accepted_candidates: List[Dict[str, Any]] = []
    schema = _load_schema()

    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            issues.append(ModelPreflightIssue("invalid_candidate", "candidates", f"candidate {index} must be an object"))
            continue
        schema_issues = validate(candidate, schema)
        for issue in schema_issues:
            issues.append(
                ModelPreflightIssue(
                    "schema_validation_error",
                    issue.path,
                    f"candidate {index}: {issue.message}",
                )
            )
        issues.extend(_validate_candidate(candidate, index))
        role = candidate.get("role")
        model_id = candidate.get("model_id")
        if isinstance(role, str):
            if role in seen_roles:
                issues.append(ModelPreflightIssue("duplicate_role", "role", f"duplicate role {role!r}"))
            seen_roles.add(role)
        if isinstance(model_id, str):
            if model_id in seen_model_ids:
                issues.append(ModelPreflightIssue("duplicate_model_id", "model_id", f"duplicate model_id {model_id!r}"))
            seen_model_ids.add(model_id)
        accepted_candidates.append(candidate)

    missing_roles = [role for role in _MODEL_ROLES if role not in seen_roles]
    for role in missing_roles:
        issues.append(ModelPreflightIssue("missing_role", "role", f"missing required role {role!r}"))

    manifest_valid = not issues
    acquisition_ready = False
    experiment_ready = False
    status = "decision_recorded" if manifest_valid else "pass_with_blockers"

    report = {
        "status": status,
        "manifest_valid": manifest_valid,
        "acquisition_ready": acquisition_ready,
        "experiment_ready": experiment_ready,
        "ready": experiment_ready,
        "candidate_count": len(accepted_candidates),
        "roles": sorted(seen_roles),
        "issues": [issue.as_dict() for issue in issues],
        "candidates": [
            {
                "role": candidate.get("role"),
                "model_id": candidate.get("model_id"),
                "revision": candidate.get("revision"),
                "license_id": candidate.get("license_id"),
                "acquisition_status": candidate.get("acquisition_status"),
                "weights_present": candidate.get("weights_present"),
                "required_capabilities": _coerce_str_list(candidate.get("required_capabilities")),
            }
            for candidate in accepted_candidates
        ],
        "next_gates": [
            "recheck model card and terms at acquisition time",
            "record operator acceptance before any download",
            "capture local file hashes and tokenizer revision after acquisition",
        ],
    }
    return report


def stable_json_dumps(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
