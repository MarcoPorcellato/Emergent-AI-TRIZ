"""Protocol freeze orchestration for A0-R1."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .a0r1_power import calibrate_a0r1_power


class A0R1FreezeError(RuntimeError):
    """Raised when freeze inputs or artifacts fail integrity checks."""


EPISTEMIC = {
    "empirical": True,
    "scientific_status": "exploratory",
    "evidence_eligible": False,
    "expert_validated": False,
    "claim_ids": [],
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R1FreezeError(f"cannot read {label}: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise A0R1FreezeError(f"{label} must be a JSON object: {path}")
    return payload


def _verify_no_escape(relative: str, label: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or os.path.isabs(relative):
        raise A0R1FreezeError(f"{label} path is absolute: {relative!r}")
    normalized = rel.as_posix().lstrip("/")
    if normalized.startswith("../") or normalized == ".." or "/../" in f"/{normalized}/":
        raise A0R1FreezeError(f"{label} path escapes root: {relative!r}")
    return rel


def _manifest_entry_file(
    root: Path,
    manifest: Mapping[str, Any],
    key: str,
    label: str,
) -> Path:
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        raise A0R1FreezeError(f"{label} manifest has no files entry")
    entry = files.get(key)
    if not isinstance(entry, Mapping):
        raise A0R1FreezeError(f"{label} missing {key} entry")

    path_value = entry.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        raise A0R1FreezeError(f"{label} {key} path missing")
    rel = _verify_no_escape(path_value, f"{label}:{key}")
    target = (root / rel).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise A0R1FreezeError(f"{label} {key} is missing or escapes root: {path_value!r}")

    expected_sha = entry.get("sha256")
    expected_size = entry.get("size")
    actual_sha = _sha256(target)
    actual_size = target.stat().st_size
    if not isinstance(expected_sha, str) or expected_sha != actual_sha:
        raise A0R1FreezeError(f"{label} {key} SHA256 mismatch")
    if not isinstance(expected_size, int) or expected_size != actual_size:
        raise A0R1FreezeError(f"{label} {key} size mismatch")
    return target


def _require_epistemic(manifest: Mapping[str, Any], label: str) -> None:
    for field, expected in EPISTEMIC.items():
        if manifest.get(field) != expected:
            raise A0R1FreezeError(f"{label} has invalid epistemic field: {field}")


def _build_frozen_protocol(planned_payload: dict[str, Any]) -> bytes:
    frozen = dict(planned_payload)
    frozen["protocol_status"] = "frozen"
    frozen["status"] = "frozen"
    return json.dumps(frozen, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"


def _verify_preoutput_manifest(
    preoutput_root: Path,
    preoutput_manifest: Mapping[str, Any],
    protocol_id: str,
    protocol_hash: str,
) -> tuple[str, dict[str, Path]]:
    if preoutput_manifest.get("artifact_class") != "a0-r1-preoutput-manifest":
        raise A0R1FreezeError("invalid preoutput artifact class")
    if preoutput_manifest.get("protocol_id") != protocol_id:
        raise A0R1FreezeError("preoutput manifest protocol_id mismatch")
    if preoutput_manifest.get("protocol_hash") != protocol_hash:
        raise A0R1FreezeError("preoutput manifest protocol_hash mismatch")
    if preoutput_manifest.get("protocol_status") != "planned":
        raise A0R1FreezeError("preoutput protocol_status must be planned")
    if preoutput_manifest.get("status") != "pass":
        raise A0R1FreezeError("preoutput status is not pass")

    artifacts = preoutput_manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise A0R1FreezeError("preoutput manifest has no artifacts mapping")

    required = {
        "independence.json": "independence_audit_sha256",
        "shortcuts.json": "shortcuts_sha256",
        "summary.json": "summary_sha256",
    }
    artifact_paths: dict[str, Path] = {}
    for filename, field in required.items():
        entry = artifacts.get(filename)
        if not isinstance(entry, Mapping):
            raise A0R1FreezeError(f"preoutput manifest missing artifact entry: {filename!r}")
        expected = entry.get("sha256")
        artifact_path = preoutput_root / filename
        if not artifact_path.is_file():
            raise A0R1FreezeError(f"missing preoutput artifact: {filename}")
        if not isinstance(expected, str) or expected != _sha256(artifact_path):
            raise A0R1FreezeError(f"preoutput artifact hash mismatch: {filename}")
        artifact_paths[field] = artifact_path

    return "pass", artifact_paths


def run_a0r1_freeze(
    protocol_path: str | Path,
    candidate_corpus_dir: str | Path,
    source_corpus_dir: str | Path,
    preoutput_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Run final freeze only when protocol is planned and dependencies are verified."""

    protocol_file = Path(protocol_path).resolve()
    planned_protocol_bytes = protocol_file.read_bytes()
    planned_payload = _load_json(protocol_file, "protocol")
    protocol_id = planned_payload.get("protocol_id")
    if not isinstance(protocol_id, str) or not protocol_id.strip():
        raise A0R1FreezeError("protocol_id must be a non-empty string")

    if planned_payload.get("protocol_status") != "planned" or planned_payload.get("status") != "planned":
        raise A0R1FreezeError("protocol must be planned")

    candidate_root = Path(candidate_corpus_dir).resolve()
    source_root = Path(source_corpus_dir).resolve()
    preoutput_root = Path(preoutput_dir).resolve()
    output_root = Path(output_dir).resolve()

    if output_root.exists():
        if not output_root.is_dir():
            raise A0R1FreezeError(f"output path is not a directory: {output_root}")
        if any(output_root.iterdir()):
            raise A0R1FreezeError(f"output directory must be absent or empty: {output_root}")
        output_root.rmdir()

    candidate_manifest_path = candidate_root / "manifest.json"
    source_manifest_path = source_root / "manifest.json"
    preoutput_manifest_path = preoutput_root / "preoutput-manifest.json"

    candidate_manifest = _load_json(candidate_manifest_path, "candidate manifest")
    source_manifest = _load_json(source_manifest_path, "source manifest")
    preoutput_manifest = _load_json(preoutput_manifest_path, "preoutput manifest")

    if candidate_manifest.get("protocol_id") != protocol_id:
        raise A0R1FreezeError("candidate manifest protocol_id does not match protocol")
    planned_protocol_hash = _sha256_bytes(planned_protocol_bytes)
    if candidate_manifest.get("protocol_hash") != planned_protocol_hash:
        raise A0R1FreezeError("candidate manifest protocol_hash mismatch")

    _require_epistemic(candidate_manifest, "candidate manifest")
    _require_epistemic(source_manifest, "source manifest")

    _manifest_entry_file(candidate_root, candidate_manifest, "cases_jsonl", "candidate")
    _manifest_entry_file(candidate_root, candidate_manifest, "calibration_targets_jsonl", "candidate")
    _manifest_entry_file(candidate_root, candidate_manifest, "sealed_targets_jsonl", "candidate")

    _manifest_entry_file(source_root, source_manifest, "cases_jsonl", "source")
    _manifest_entry_file(source_root, source_manifest, "calibration_targets_jsonl", "source")
    _manifest_entry_file(source_root, source_manifest, "sealed_targets_jsonl", "source")

    preoutput_status, preoutput_artifacts = _verify_preoutput_manifest(
        preoutput_root,
        preoutput_manifest,
        protocol_id,
        planned_protocol_hash,
    )
    candidate_manifest_hash = _sha256(candidate_manifest_path)
    source_manifest_hash = _sha256(source_manifest_path)
    preoutput_manifest_hash = _sha256(preoutput_manifest_path)
    if preoutput_manifest.get("candidate_corpus_manifest_sha256") != candidate_manifest_hash:
        raise A0R1FreezeError("preoutput candidate manifest hash mismatch")
    if preoutput_manifest.get("source_corpus_manifest_sha256") != source_manifest_hash:
        raise A0R1FreezeError("preoutput source manifest hash mismatch")

    power = calibrate_a0r1_power(protocol_file)
    if preoutput_status != "pass" or power.get("status") != "pass":
        raise A0R1FreezeError("freeze prerequisites did not pass; no freeze package was written")
    freeze_status = "frozen"

    protocol_frozen_bytes = _build_frozen_protocol(planned_payload)
    frozen_protocol_hash = _sha256_bytes(protocol_frozen_bytes)

    primary_endpoint = planned_payload.get("primary_endpoint")
    if not isinstance(primary_endpoint, Mapping):
        raise A0R1FreezeError("protocol missing primary_endpoint")

    summary = {
        "artifact_class": "a0-r1-protocol-freeze-summary",
        "protocol_id": protocol_id,
        "protocol_status": "frozen" if freeze_status == "frozen" else "planned",
        "status": freeze_status,
        **EPISTEMIC,
        "model_output_accessed": False,
        "sealed_model_output_accessed": False,
    }

    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(output_root.parent)) as temporary:
        staging_root = Path(temporary) / output_root.name
        staging_root.mkdir()

        (staging_root / "protocol-planned.json").write_bytes(planned_protocol_bytes)
        (staging_root / "protocol-frozen.json").write_bytes(protocol_frozen_bytes)

        (staging_root / "power.json").write_text(
            json.dumps(power, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        power_hash = _sha256(staging_root / "power.json")

        (staging_root / "protocol-frozen.json").write_bytes(protocol_frozen_bytes)

        freeze_manifest = {
            "artifact_class": "a0-r1-protocol-freeze-manifest",
            "protocol_id": protocol_id,
            "protocol_status": "frozen",
            "planned_protocol_snapshot_hash": planned_protocol_hash,
            "frozen_protocol_hash": frozen_protocol_hash,
            "corpus_manifest_hash": candidate_manifest_hash,
            "preoutput_manifest_hash": preoutput_manifest_hash,
            "power_hash": power_hash,
            "cases_sha256": candidate_manifest["files"]["cases_jsonl"]["sha256"],
            "calibration_targets_sha256": candidate_manifest["files"]["calibration_targets_jsonl"]["sha256"],
            "sealed_targets_sha256": candidate_manifest["files"]["sealed_targets_jsonl"]["sha256"],
            "independence_audit_sha256": _sha256(preoutput_artifacts["independence_audit_sha256"]),
            "shortcuts_sha256": _sha256(preoutput_artifacts["shortcuts_sha256"]),
            "summary_sha256": _sha256(preoutput_artifacts["summary_sha256"]),
            "primary_endpoint": primary_endpoint,
            "status": freeze_status,
            **EPISTEMIC,
            "model_output_accessed": False,
            "sealed_model_output_accessed": False,
        }
        (staging_root / "freeze-manifest.json").write_text(
            json.dumps(freeze_manifest, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        if output_root.exists():
            raise A0R1FreezeError(f"output directory already exists: {output_root}")
        staging_root.replace(output_root)

    return summary
