"""Pre-output replication audit for A0-R1 candidate corpus.

Runs deterministic independence and shortcut audits against physically separate
calibration/sealed target partitions and writes immutable audit artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .a0r1_independence import run_a0r1_independence_audit
from .a0_shortcuts import audit_a0_shortcuts

EPISTEMIC = {
    "empirical": True,
    "scientific_status": "exploratory",
    "evidence_eligible": False,
    "expert_validated": False,
    "claim_ids": [],
}


class A0R1PreoutputError(RuntimeError):
    """Raised when pre-output orchestration inputs are invalid."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise A0R1PreoutputError(f"{label}: cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise A0R1PreoutputError(f"{label}: invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise A0R1PreoutputError(f"{label}: expected JSON object in {path}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _verify_no_escape(relative: str, label: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute():
        raise A0R1PreoutputError(f"{label} has absolute path {relative!r}")
    if os.path.isabs(relative):
        raise A0R1PreoutputError(f"{label} has absolute path {relative!r}")
    normalized = rel.as_posix().lstrip("/")
    if normalized.startswith("../") or normalized == ".." or "/../" in f"/{normalized}/":
        raise A0R1PreoutputError(f"{label} path escapes corpus root: {relative!r}")
    return rel


def _manifest_entry_file(
    manifest_root: Path,
    manifest: Mapping[str, Any],
    key: str,
    label: str,
) -> Path:
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        raise A0R1PreoutputError(f"{label}: manifest has no files entry")
    entry = files.get(key)
    if not isinstance(entry, Mapping):
        raise A0R1PreoutputError(f"{label}: missing or invalid {key} entry")

    path_value = entry.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        raise A0R1PreoutputError(f"{label}: {key} path missing")
    rel = _verify_no_escape(path_value, f"{label}:{key}")

    target = (manifest_root / rel).resolve()
    if not target.is_file():
        raise A0R1PreoutputError(f"{label}: missing {key} file {target}")
    if not target.is_relative_to(manifest_root):
        raise A0R1PreoutputError(f"{label}: path escapes root for {key}: {path_value!r}")

    expected_sha = entry.get("sha256")
    expected_size = entry.get("size")
    actual_sha = _sha256(target)
    actual_size = target.stat().st_size
    if expected_sha is None or expected_size is None:
        raise A0R1PreoutputError(f"{label}: incomplete {key} receipt (missing sha256/size)")
    if not isinstance(expected_sha, str) or expected_sha != actual_sha:
        raise A0R1PreoutputError(f"{label}: {key} SHA256 mismatch")
    if not isinstance(expected_size, int) or expected_size != actual_size:
        raise A0R1PreoutputError(f"{label}: {key} size mismatch")
    return target


def _load_protocol(path: Path) -> dict[str, Any]:
    protocol = _load_json(path, "protocol")
    protocol_status = protocol.get("protocol_status")
    if protocol_status != "planned":
        raise A0R1PreoutputError(f"protocol_status must be planned, got {protocol_status!r}")
    protocol_id = protocol.get("protocol_id")
    if not isinstance(protocol_id, str) or not protocol_id.strip():
        raise A0R1PreoutputError("protocol_id must be a non-empty string")
    return protocol


def run_a0r1_preoutput_audits(
    protocol_path: str | Path,
    candidate_corpus_dir: str | Path,
    source_corpus_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Run independent checks for candidate corpus pre-output.

    Fail-closed orchestration:
    - reject invalid paths (including path traversal)
    - reject protocol mismatch and manifest receipt mismatches
    - do not run audits when manifest integrity cannot be proven
    """

    protocol_file = Path(protocol_path).resolve()
    protocol = _load_protocol(protocol_file)
    protocol_id = protocol.get("protocol_id")
    if not isinstance(protocol_id, str):
        raise A0R1PreoutputError("protocol_id missing")

    candidate_root = Path(candidate_corpus_dir).resolve()
    source_root = Path(source_corpus_dir).resolve()
    output_root = Path(output_dir).resolve()

    if not candidate_root.is_dir():
        raise A0R1PreoutputError(f"candidate corpus dir missing: {candidate_root}")
    if not source_root.is_dir():
        raise A0R1PreoutputError(f"source corpus dir missing: {source_root}")
    if output_root.exists():
        if not output_root.is_dir():
            raise A0R1PreoutputError(f"output path is not a directory: {output_root}")
        if any(output_root.iterdir()):
            raise A0R1PreoutputError(f"output directory must be absent or empty: {output_root}")
        output_root.rmdir()

    candidate_manifest_path = candidate_root / "manifest.json"
    source_manifest_path = source_root / "manifest.json"
    candidate_manifest = _load_json(candidate_manifest_path, "candidate manifest")
    source_manifest = _load_json(source_manifest_path, "source manifest")

    candidate_protocol_id = candidate_manifest.get("protocol_id")
    if candidate_protocol_id != protocol_id:
        raise A0R1PreoutputError(
            "candidate manifest protocol_id does not match protocol",
        )
    if candidate_manifest.get("protocol_hash") != _sha256(protocol_file):
        raise A0R1PreoutputError("candidate manifest protocol_hash does not match protocol bytes")
    for field, expected in EPISTEMIC.items():
        if candidate_manifest.get(field) != expected:
            raise A0R1PreoutputError(f"candidate manifest has invalid epistemic field: {field}")

    candidate_cases = _manifest_entry_file(candidate_root, candidate_manifest, "cases_jsonl", "candidate")
    candidate_calibration = _manifest_entry_file(
        candidate_root, candidate_manifest, "calibration_targets_jsonl", "candidate",
    )
    candidate_sealed = _manifest_entry_file(candidate_root, candidate_manifest, "sealed_targets_jsonl", "candidate")

    source_cases = _manifest_entry_file(source_root, source_manifest, "cases_jsonl", "source")
    source_calibration = _manifest_entry_file(
        source_root, source_manifest, "calibration_targets_jsonl", "source",
    )
    source_sealed = _manifest_entry_file(source_root, source_manifest, "sealed_targets_jsonl", "source")

    try:
        independence = run_a0r1_independence_audit(
            candidate_manifest_path=candidate_manifest_path,
            candidate_cases_path=candidate_cases,
            candidate_calibration_targets_path=candidate_calibration,
            candidate_sealed_targets_path=candidate_sealed,
            source_manifest_path=source_manifest_path,
            source_cases_path=source_cases,
            source_calibration_targets_path=source_calibration,
            source_sealed_targets_path=source_sealed,
        )
        shortcuts = audit_a0_shortcuts(
            candidate_cases,
            candidate_calibration,
            protocol_path,
        )
    except Exception as exc:
        raise A0R1PreoutputError(f"audit failed: {exc}") from exc

    independence_pass = independence.get("status") == "pass"
    shortcut_status = shortcuts.get("status")
    shortcut_pass = shortcut_status == "pass"

    status = (
        "pass"
        if independence_pass and shortcut_pass
        else ("non_interpretable" if shortcut_status == "non_interpretable" else "failed")
    )

    summary = {
        "artifact_class": "a0-r1-preoutput-summary",
        "protocol_id": protocol_id,
        "protocol_status": "planned",
        "status": status,
        **EPISTEMIC,
        "independence_status": independence.get("status"),
        "shortcuts_status": shortcut_status,
        "independence_ready": independence.get("ready"),
        "shortcuts_ready": shortcut_status == "pass",
        "model_output_accessed": False,
        "candidate_sealed_targets_accessed_by_independence_audit": True,
        "candidate_sealed_targets_accessed_by_shortcut_audit": False,
    }

    preoutput_manifest = {
        "artifact_class": "a0-r1-preoutput-manifest",
        "protocol_id": protocol_id,
        "protocol_status": "planned",
        "protocol_hash": _sha256(protocol_file),
        "candidate_corpus_manifest_sha256": _sha256(candidate_manifest_path),
        "source_corpus_manifest_sha256": _sha256(source_manifest_path),
        "status": status,
        "artifacts": {
            "independence.json": {"sha256": ""},
            "shortcuts.json": {"sha256": ""},
            "summary.json": {"sha256": ""},
        },
        "counts": {
            "independence": independence.get("counts"),
            "shortcuts": shortcuts.get("counts"),
        },
        "results": {
            "independence_status": independence.get("status"),
            "shortcuts_status": shortcut_status,
        },
        "protocol_summary": {
            "protocol_id": protocol_id,
            "protocol_status": "planned",
            "empirical": EPISTEMIC["empirical"],
            "scientific_status": EPISTEMIC["scientific_status"],
            "evidence_eligible": EPISTEMIC["evidence_eligible"],
            "expert_validated": EPISTEMIC["expert_validated"],
            "claim_ids": EPISTEMIC["claim_ids"],
        },
    }

    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(output_root.parent)) as staging:
        staging_root = Path(staging) / output_root.name
        staging_root.mkdir()
        (staging_root / "independence.json").write_text(_stable(independence) + "\n", encoding="utf-8", newline="\n")
        (staging_root / "shortcuts.json").write_text(_stable(shortcuts) + "\n", encoding="utf-8", newline="\n")
        (staging_root / "summary.json").write_text(_stable(summary) + "\n", encoding="utf-8", newline="\n")
        preoutput_manifest["artifacts"]["independence.json"]["sha256"] = _sha256(staging_root / "independence.json")
        preoutput_manifest["artifacts"]["shortcuts.json"]["sha256"] = _sha256(staging_root / "shortcuts.json")
        preoutput_manifest["artifacts"]["summary.json"]["sha256"] = _sha256(staging_root / "summary.json")
        (staging_root / "preoutput-manifest.json").write_text(
            _stable(preoutput_manifest) + "\n", encoding="utf-8", newline="\n"
        )
        if output_root.exists():
            raise A0R1PreoutputError(f"output directory already exists: {output_root}")
        staging_root.replace(output_root)

    return summary
