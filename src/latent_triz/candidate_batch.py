"""Fail-closed audit for pre-annotation candidate case batches."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


PARTICIPANT_FIELDS = (
    "problem", "initial_state", "desired_improvement", "worsening_consequence",
    "transformation", "resulting_state",
)


class CandidateBatchError(RuntimeError):
    """Raised when candidate inputs cannot be audited."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateBatchError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CandidateBatchError(f"{path}: expected an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise CandidateBatchError(f"cannot read {path}: {exc}") from exc
    for line_number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CandidateBatchError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise CandidateBatchError(f"{path}:{line_number}: expected an object")
        records.append(value)
    return records


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _required_string_list(manifest: Mapping[str, Any], field: str) -> list[str]:
    value = manifest.get(field)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise CandidateBatchError(f"manifest.{field} must be a non-empty string array")
    return value


def _principle(case: Mapping[str, Any]) -> str | None:
    labels = case.get("labels")
    if not isinstance(labels, list) or len(labels) != 1 or not isinstance(labels[0], dict):
        return None
    value = labels[0].get("principle")
    return value if isinstance(value, str) and value else None


def _cue_present(text: str, cue: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(cue.lower())}(?![a-z0-9])", text.lower()) is not None


def audit_candidate_batch(manifest_path: str | Path, cases_path: str | Path) -> dict[str, Any]:
    manifest_file, cases_file = Path(manifest_path), Path(cases_path)
    manifest, cases = _read_json(manifest_file), _read_jsonl(cases_file)
    issues: list[dict[str, Any]] = []
    required_principles: set[str] = set(_required_string_list(manifest, "required_principles"))
    required_domains: set[str] = set(_required_string_list(manifest, "required_domains"))
    allowed_sources: set[str] = set(_required_string_list(manifest, "allowed_source_types"))
    forbidden_cues: Sequence[str] = _required_string_list(manifest, "forbidden_label_cues")
    by_id: dict[str, dict[str, Any]] = {}
    label_counts: dict[str, int] = {value: 0 for value in sorted(required_principles)}
    domain_counts: dict[str, int] = {value: 0 for value in sorted(required_domains)}
    domain_label_counts: dict[str, dict[str, int]] = {
        domain: {label: 0 for label in sorted(required_principles)} for domain in sorted(required_domains)
    }
    transformation_leads: dict[str, Counter[str]] = {
        value: Counter() for value in sorted(required_principles)
    }

    def add(code: str, case_id: str | None, message: str) -> None:
        issue: dict[str, Any] = {"code": code, "message": message}
        if case_id is not None:
            issue["case_id"] = case_id
        issues.append(issue)

    for index, case in enumerate(cases, start=1):
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            add("invalid_case_id", None, f"record {index} has no case_id")
            continue
        if case_id in by_id:
            add("duplicate_case_id", case_id, "case_id appears more than once")
            continue
        by_id[case_id] = case
        principle = _principle(case)
        if not isinstance(principle, str) or principle not in required_principles:
            add("invalid_principle", case_id, "exactly one required principle label is required")
        else:
            label_counts[principle] += 1
            transformation = case.get("transformation")
            lead_match = re.search(r"[a-z]+", transformation.lower()) if isinstance(transformation, str) else None
            if lead_match is None:
                add("missing_transformation_lead", case_id, "transformation must contain a word")
            else:
                transformation_leads[principle][lead_match.group(0)] += 1
        domain = case.get("domain")
        if not isinstance(domain, str) or domain not in required_domains:
            add("invalid_domain", case_id, f"domain {domain!r} is outside the batch manifest")
        else:
            domain_counts[domain] += 1
            if isinstance(principle, str) and principle in required_principles:
                domain_label_counts[domain][principle] += 1
        provenance = case.get("provenance")
        source_type = provenance.get("source_type") if isinstance(provenance, dict) else None
        if source_type not in allowed_sources:
            add("invalid_source_type", case_id, f"source_type {source_type!r} is outside the batch manifest")
        participant_text = " ".join(str(case.get(field, "")) for field in PARTICIPANT_FIELDS)
        found = sorted({cue for cue in forbidden_cues if _cue_present(participant_text, cue)})
        if found:
            add("label_cue_leakage", case_id, f"participant text contains forbidden cues: {found}")

    expected_count = manifest.get("expected_count")
    if len(cases) != expected_count:
        add("unexpected_case_count", None, f"found {len(cases)} cases; expected {expected_count}")
    if label_counts and len(set(label_counts.values())) != 1:
        add("principle_imbalance", None, f"principle counts are not equal: {label_counts}")
    minimum = manifest.get("minimum_per_principle_domain")
    for domain, counts in domain_label_counts.items():
        for label, count in counts.items():
            if not isinstance(minimum, int) or count < minimum:
                add("domain_principle_minimum", None, f"{domain}/{label} has {count}; minimum is {minimum}")

    if manifest.get("require_balanced_transformation_leads") is True and required_principles:
        lead_profiles = [transformation_leads[label] for label in sorted(required_principles)]
        if any(profile != lead_profiles[0] for profile in lead_profiles[1:]):
            add(
                "transformation_lead_imbalance",
                None,
                f"lead-word profiles differ by principle: {dict((key, dict(value)) for key, value in transformation_leads.items())}",
            )
        minimum_leads = manifest.get("minimum_distinct_transformation_leads")
        for label, profile in transformation_leads.items():
            if not isinstance(minimum_leads, int) or len(profile) < minimum_leads:
                add("insufficient_transformation_leads", None, f"{label} has {len(profile)} distinct leads; minimum is {minimum_leads}")

    if manifest.get("require_opposite_label_pairs") is True:
        for case_id, case in sorted(by_id.items()):
            lexical = case.get("lexical_controls")
            targets = lexical.get("matched_case_ids") if isinstance(lexical, dict) else None
            if not isinstance(targets, list) or len(targets) != 1 or not isinstance(targets[0], str):
                add("invalid_pair", case_id, "exactly one matched_case_id is required")
                continue
            target_id = targets[0]
            target = by_id.get(target_id)
            if target is None:
                add("missing_pair", case_id, f"matched case {target_id} is absent")
                continue
            target_lexical = target.get("lexical_controls")
            reciprocal = target_lexical.get("matched_case_ids") if isinstance(target_lexical, dict) else None
            if reciprocal != [case_id]:
                add("asymmetric_pair", case_id, f"matched case {target_id} does not point back")
            if target.get("domain") != case.get("domain"):
                add("cross_domain_pair", case_id, f"matched case {target_id} has a different domain")
            if _principle(target) == _principle(case):
                add("same_principle_pair", case_id, f"matched case {target_id} has the same principle")

    issues.sort(key=lambda item: (item["code"], item.get("case_id", ""), item["message"]))
    return {
        "artifact_class": "candidate-batch-audit",
        "batch_id": manifest.get("batch_id"),
        "status": "pass" if not issues else "fail",
        "ready_for_blinded_review": not issues,
        "non_empirical": True,
        "evidence_eligible": False,
        "claim_ids": [],
        "counts": {
            "total": len(cases),
            "by_principle": label_counts,
            "by_domain": domain_counts,
            "by_domain_and_principle": domain_label_counts,
            "transformation_leads_by_principle": {
                label: dict(sorted(profile.items())) for label, profile in transformation_leads.items()
            },
        },
        "hashes": {"manifest_sha256": _digest(manifest_file), "cases_sha256": _digest(cases_file)},
        "issues": issues,
    }
