"""Fail-closed audit for the no-model H1 expert collection packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class H1PacketError(ValueError):
    """Raised when the H1 packet is incomplete, contaminated, or drifted."""


_FORBIDDEN_CASE_TERMS = ("triz", "inventive principle", "matrix 2003", "panitz", "segmentation", "inversion")
_REQUIRED_CASE_FIELDS = {
    "case_id", "domain", "problem", "constraints", "initial_state",
    "desired_improvement", "worsening_consequence", "displayed_solution",
    "resulting_state", "source_type", "license", "non_empirical",
}
_REQUIRED_LABELS = {"segmentation", "inversion", "both", "other", "abstain"}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise H1PacketError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise H1PacketError(f"expected JSON object: {path}")
    return value


def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise H1PacketError(f"cannot read {path}") from exc
    records: list[dict[str, Any]] = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise H1PacketError(f"invalid JSONL at {path}:{number}") from exc
        if not isinstance(value, dict):
            raise H1PacketError(f"JSONL record is not an object at {path}:{number}")
        records.append(value)
    return records


def _safe(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise H1PacketError(f"unsafe packet path: {relative}")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise H1PacketError(f"missing packet file: {relative}")
    return resolved


def audit_h1_packet(*, repo_root: str | Path, protocol_path: str | Path = "experiments/h1-cognitive-pilot/protocol.json") -> dict[str, Any]:
    root = Path(repo_root).resolve()
    protocol_file = _safe(root, str(protocol_path))
    protocol = _json(protocol_file)
    if protocol.get("artifact_class") != "h1-cognitive-pilot-protocol":
        raise H1PacketError("wrong H1 protocol artifact class")
    if protocol.get("status") != "ready_for_collection":
        raise H1PacketError("H1 packet is not ready_for_collection")
    if protocol.get("non_empirical") is not True or protocol.get("evidence_eligible") is not False:
        raise H1PacketError("H1 packet crossed the non-empirical boundary")

    guide_file = _safe(root, protocol.get("guide", ""))
    cases_file = _safe(root, protocol.get("cases", ""))
    allocation_file = _safe(root, protocol.get("allocation", ""))
    bound = protocol.get("input_hashes")
    if not isinstance(bound, dict):
        raise H1PacketError("H1 input hashes are missing")
    hashes = {
        "guide_sha256": _sha(guide_file),
        "cases_sha256": _sha(cases_file),
        "allocation_sha256": _sha(allocation_file),
    }
    if any(bound.get(key) != value for key, value in hashes.items()):
        raise H1PacketError("H1 input hash mismatch")

    guide = _json(guide_file)
    labels = guide.get("labels")
    if guide.get("revision") != "v1.2.0" or guide.get("status") != "proposed_for_review":
        raise H1PacketError("H1 guide is not the proposed v1.2 guide")
    if {item.get("id") for item in labels or [] if isinstance(item, dict)} != _REQUIRED_LABELS:
        raise H1PacketError("H1 guide labels drifted")
    if guide.get("human_review_required_before_freeze") is not True:
        raise H1PacketError("H1 guide review gate is absent")

    cases = _jsonl(cases_file)
    expected_count = protocol.get("case_count")
    if len(cases) != expected_count:
        raise H1PacketError(f"expected {expected_count} H1 cases, found {len(cases)}")
    case_ids: list[str] = []
    for case in cases:
        if set(_REQUIRED_CASE_FIELDS) - set(case):
            raise H1PacketError(f"H1 case is incomplete: {case.get('case_id')}")
        if case.get("non_empirical") is not True:
            raise H1PacketError(f"H1 case crossed the empirical boundary: {case.get('case_id')}")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or case_id in case_ids:
            raise H1PacketError("H1 case IDs must be unique strings")
        case_ids.append(case_id)
        text = json.dumps(case, ensure_ascii=False).lower()
        if any(term in text for term in _FORBIDDEN_CASE_TERMS):
            raise H1PacketError(f"H1 case contains a forbidden source/label cue: {case_id}")
        if any(key in case for key in ("label", "labels", "answer", "expected_label", "principle", "matrix_cell", "tool_edge")):
            raise H1PacketError(f"H1 case contains an answer-key field: {case_id}")

    allocation = _json(allocation_file)
    order = allocation.get("case_order")
    if sorted(order or []) != sorted(case_ids) or len(order or []) != len(case_ids):
        raise H1PacketError("H1 allocation does not cover each case exactly once")
    if len(set(allocation.get("rater_slots") or [])) != protocol.get("required_independent_raters"):
        raise H1PacketError("H1 rater slots do not match required independent raters")

    return {
        "artifact_class": "h1-packet-audit",
        "status": "pass",
        "collection_status": "ready_for_collection",
        "case_count": len(cases),
        "required_independent_raters": protocol["required_independent_raters"],
        "case_ids": case_ids,
        "input_hashes": hashes,
        "non_empirical": True,
        "evidence_eligible": False,
        "expert_validated": False,
        "model_output_accessed": False,
        "sealed_targets_accessed": False,
    }
