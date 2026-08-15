"""Deterministic verifier for the tracked A0-R1 pre-output foundation."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from .a0r1_corpus import generate_a0r1_corpus
from .a0r1_preoutput import run_a0r1_preoutput_audits


class A0R1VerifyError(RuntimeError):
    """Raised when regeneration differs from tracked A0-R1 artifacts."""


CORPUS_FILES = (
    "manifest.json",
    "cases.jsonl",
    "targets/calibration.jsonl",
    "targets/sealed.jsonl",
)
PREOUTPUT_FILES = (
    "independence.json",
    "shortcuts.json",
    "summary.json",
    "preoutput-manifest.json",
)
FROZEN_DIR = Path("results/a0r1/freeze")
FREEZE_FILES = ("power.json", "protocol-planned.json", "protocol-frozen.json", "freeze-manifest.json")
REPO_PROTOCOL_PATH = Path("experiments/a0r1-independent-proxy/protocol.json")
CANDIDATE_CORPUS_DIR = Path("data/a0r1")
SOURCE_CORPUS_DIR = Path("data/a0")
PREOUTPUT_DIR = Path("results/a0r1/preoutput")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R1VerifyError(f"cannot read {label}: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise A0R1VerifyError(f"{label} is not a JSON object: {path}")
    return payload


def _require_equal(expected_root: Path, actual_root: Path, relative_paths: tuple[str, ...]) -> None:
    for relative in relative_paths:
        expected = expected_root / relative
        actual = actual_root / relative
        if not expected.is_file():
            raise A0R1VerifyError(f"tracked artifact is missing: {relative}")
        if not actual.is_file() or actual.read_bytes() != expected.read_bytes():
            raise A0R1VerifyError(f"deterministic regeneration mismatch: {relative}")


def _manifest_entry_path(manifest: dict[str, Any], root: Path, key: str, label: str) -> Path:
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise A0R1VerifyError(f"{label} manifest has no files mapping")
    entry = files.get(key)
    if not isinstance(entry, dict):
        raise A0R1VerifyError(f"{label} manifest missing {key}")

    relative = entry.get("path")
    size = entry.get("size")
    sha256 = entry.get("sha256")
    if not isinstance(relative, str) or not relative:
        raise A0R1VerifyError(f"{label} {key} has invalid path")
    if not isinstance(size, int) or size < 0:
        raise A0R1VerifyError(f"{label} {key} has invalid size")
    if not isinstance(sha256, str) or len(sha256) != 64:
        raise A0R1VerifyError(f"{label} {key} has invalid sha256")

    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise A0R1VerifyError(f"{label} {key} path escapes root: {relative}")
    root = root.resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise A0R1VerifyError(f"{label} {key} path escapes root: {relative}")
    if not path.is_file():
        raise A0R1VerifyError(f"{label} {key} artifact missing: {relative}")
    if path.stat().st_size != size:
        raise A0R1VerifyError(f"{label} {key} size mismatch: {relative}")
    if _sha256(path) != sha256:
        raise A0R1VerifyError(f"{label} {key} hash mismatch: {relative}")
    return path


def _verify_freeze_artifacts(
    repository: Path,
    protocol_id: str,
    freeze_protocol: Path,
    planned_protocol: Path,
    freeze_manifest_path: Path,
) -> tuple[dict[str, Any], int]:
    if not freeze_manifest_path.is_file():
        raise A0R1VerifyError(f"freeze manifest missing: {freeze_manifest_path}")
    if freeze_protocol.read_bytes() != (repository / REPO_PROTOCOL_PATH).read_bytes():
        raise A0R1VerifyError("live protocol does not match frozen protocol snapshot")

    candidate_manifest_path = repository / CANDIDATE_CORPUS_DIR / "manifest.json"
    source_manifest_path = repository / SOURCE_CORPUS_DIR / "manifest.json"
    preoutput_manifest_path = repository / PREOUTPUT_DIR / "preoutput-manifest.json"
    candidate_manifest = _load_json(candidate_manifest_path, "candidate corpus manifest")
    source_manifest = _load_json(source_manifest_path, "source corpus manifest")
    preoutput_manifest = _load_json(preoutput_manifest_path, "preoutput manifest")
    freeze_manifest = _load_json(freeze_manifest_path, "freeze manifest")

    if freeze_manifest.get("artifact_class") != "a0-r1-protocol-freeze-manifest":
        raise A0R1VerifyError("invalid freeze manifest artifact_class")
    if freeze_manifest.get("protocol_id") != protocol_id:
        raise A0R1VerifyError("freeze manifest protocol_id mismatch")
    if freeze_manifest.get("protocol_status") != "frozen":
        raise A0R1VerifyError("freeze manifest protocol_status must be frozen")

    verified = 0
    expected_fields = (
        "planned_protocol_snapshot_hash",
        "frozen_protocol_hash",
        "corpus_manifest_hash",
        "preoutput_manifest_hash",
        "power_hash",
        "cases_sha256",
        "calibration_targets_sha256",
        "sealed_targets_sha256",
        "independence_audit_sha256",
        "shortcuts_sha256",
        "summary_sha256",
    )
    for field in expected_fields:
        value = freeze_manifest.get(field)
        if not isinstance(value, str) or len(value) != 64:
            raise A0R1VerifyError(f"freeze manifest field invalid: {field}")
    if freeze_manifest.get("planned_protocol_snapshot_hash") != _sha256(planned_protocol):
        raise A0R1VerifyError("freeze manifest planned protocol hash mismatch")
    verified += 1
    if freeze_manifest.get("frozen_protocol_hash") != _sha256(freeze_protocol):
        raise A0R1VerifyError("freeze manifest frozen protocol hash mismatch")
    verified += 1

    if freeze_manifest.get("protocol_status") != "frozen":
        raise A0R1VerifyError("freeze manifest protocol_status not frozen")
    if freeze_manifest.get("status") != "frozen":
        raise A0R1VerifyError("freeze manifest status must be frozen")
    required_epistemic = {
        "empirical": True,
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "model_output_accessed": False,
        "sealed_model_output_accessed": False,
    }
    for field, expected in required_epistemic.items():
        if freeze_manifest.get(field) != expected:
            raise A0R1VerifyError(f"freeze manifest epistemic field mismatch: {field}")

    expected_power_path = repository / FROZEN_DIR / FREEZE_FILES[0]
    expected_protocol_planned = repository / FROZEN_DIR / FREEZE_FILES[1]
    expected_protocol_frozen = repository / FROZEN_DIR / FREEZE_FILES[2]
    for artifact in (expected_power_path, expected_protocol_planned, expected_protocol_frozen):
        if not artifact.is_file():
            raise A0R1VerifyError(f"freeze artifact missing: {artifact}")

    if _sha256(expected_protocol_planned) != freeze_manifest["planned_protocol_snapshot_hash"]:
        raise A0R1VerifyError("frozen planned hash mismatch")
    verified += 1
    if _sha256(expected_protocol_frozen) != freeze_manifest["frozen_protocol_hash"]:
        raise A0R1VerifyError("frozen hash mismatch")
    verified += 1
    if _sha256(expected_power_path) != freeze_manifest["power_hash"]:
        raise A0R1VerifyError("power hash mismatch")
    verified += 1

    if _sha256(candidate_manifest_path) != freeze_manifest["corpus_manifest_hash"]:
        raise A0R1VerifyError("corpus manifest hash mismatch")
    verified += 1
    if _sha256(preoutput_manifest_path) != freeze_manifest["preoutput_manifest_hash"]:
        raise A0R1VerifyError("preoutput manifest hash mismatch")
    verified += 1
    if preoutput_manifest.get("candidate_corpus_manifest_sha256") != _sha256(candidate_manifest_path):
        raise A0R1VerifyError("preoutput candidate corpus manifest hash mismatch")
    if preoutput_manifest.get("source_corpus_manifest_sha256") != _sha256(source_manifest_path):
        raise A0R1VerifyError("preoutput source corpus manifest hash mismatch")
    verified += 2

    candidate_cases = _manifest_entry_path(
        candidate_manifest, repository / CANDIDATE_CORPUS_DIR, "cases_jsonl", "candidate corpus"
    )
    candidate_calibration = _manifest_entry_path(
        candidate_manifest,
        repository / CANDIDATE_CORPUS_DIR,
        "calibration_targets_jsonl",
        "candidate corpus",
    )
    candidate_sealed = _manifest_entry_path(
        candidate_manifest,
        repository / CANDIDATE_CORPUS_DIR,
        "sealed_targets_jsonl",
        "candidate corpus",
    )
    verified += 3

    _manifest_entry_path(
        source_manifest,
        repository / SOURCE_CORPUS_DIR,
        "cases_jsonl",
        "source corpus",
    )
    _manifest_entry_path(
        source_manifest,
        repository / SOURCE_CORPUS_DIR,
        "calibration_targets_jsonl",
        "source corpus",
    )
    _manifest_entry_path(
        source_manifest,
        repository / SOURCE_CORPUS_DIR,
        "sealed_targets_jsonl",
        "source corpus",
    )
    verified += 3

    if freeze_manifest["cases_sha256"] != _sha256(candidate_cases):
        raise A0R1VerifyError("freeze manifest cases hash mismatch")
    if freeze_manifest["calibration_targets_sha256"] != _sha256(candidate_calibration):
        raise A0R1VerifyError("freeze manifest calibration hash mismatch")
    if freeze_manifest["sealed_targets_sha256"] != _sha256(candidate_sealed):
        raise A0R1VerifyError("freeze manifest sealed hash mismatch")
    verified += 3

    independence = repository / PREOUTPUT_DIR / "independence.json"
    shortcuts = repository / PREOUTPUT_DIR / "shortcuts.json"
    summary = repository / PREOUTPUT_DIR / "summary.json"
    for path in (independence, shortcuts, summary):
        if not path.is_file():
            raise A0R1VerifyError(f"preoutput artifact missing: {path}")
        verified += 1

    if freeze_manifest["independence_audit_sha256"] != _sha256(independence):
        raise A0R1VerifyError("freeze manifest preoutput hash mismatch: independence")
    if freeze_manifest["shortcuts_sha256"] != _sha256(shortcuts):
        raise A0R1VerifyError("freeze manifest preoutput hash mismatch: shortcuts")
    if freeze_manifest["summary_sha256"] != _sha256(summary):
        raise A0R1VerifyError("freeze manifest preoutput hash mismatch: summary")

    preoutput_independence = preoutput_manifest.get("artifacts", {}).get("independence.json", {}).get("sha256")
    preoutput_shortcuts = preoutput_manifest.get("artifacts", {}).get("shortcuts.json", {}).get("sha256")
    preoutput_summary = preoutput_manifest.get("artifacts", {}).get("summary.json", {}).get("sha256")
    if preoutput_independence != _sha256(independence):
        raise A0R1VerifyError("preoutput manifest hash mismatch for independence.json")
    if preoutput_shortcuts != _sha256(shortcuts):
        raise A0R1VerifyError("preoutput manifest hash mismatch for shortcuts.json")
    if preoutput_summary != _sha256(summary):
        raise A0R1VerifyError("preoutput manifest hash mismatch for summary.json")

    if preoutput_manifest.get("status") != "pass":
        raise A0R1VerifyError("preoutput status in manifest must be pass")
    if preoutput_manifest.get("protocol_status") != "planned":
        raise A0R1VerifyError("preoutput manifest protocol status must be planned")

    power = _load_json(expected_power_path, "power receipt")
    if power.get("status") != "pass" or power.get("protocol_id") != protocol_id:
        raise A0R1VerifyError("power receipt status or protocol_id mismatch")
    if power.get("model_output_accessed") is not False or power.get("sealed_targets_accessed") is not False:
        raise A0R1VerifyError("power receipt records forbidden output access")
    verified += 1

    return freeze_manifest, verified


def verify_a0r1_foundation(root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    protocol = repository / REPO_PROTOCOL_PATH
    tracked_corpus = repository / CANDIDATE_CORPUS_DIR
    source_corpus = repository / SOURCE_CORPUS_DIR
    tracked_preoutput = repository / "results/a0r1/preoutput"
    freeze_protocol_path = repository / FROZEN_DIR / "protocol-frozen.json"
    planned_protocol_path = repository / FROZEN_DIR / "protocol-planned.json"
    freeze_manifest_path = repository / FROZEN_DIR / "freeze-manifest.json"

    protocol_payload = _load_json(protocol, "protocol")
    protocol_status = protocol_payload.get("status")
    if protocol_payload.get("protocol_status") != protocol_status:
        raise A0R1VerifyError("protocol status and protocol_status differ")
    if protocol_status not in {"planned", "frozen"}:
        raise A0R1VerifyError(f"protocol status not verifiable: {protocol_status!r}")

    protocol_for_regen = protocol
    freeze_manifest: dict[str, Any] | None = None
    freeze_files_verified = 0

    if protocol_status == "frozen":
        if not freeze_protocol_path.is_file() or not planned_protocol_path.is_file():
            raise A0R1VerifyError("frozen protocol snapshot files missing in results/a0r1/freeze")
        if protocol.read_bytes() != freeze_protocol_path.read_bytes():
            raise A0R1VerifyError("live protocol does not byte-equal protocol-frozen.json")
        protocol_for_regen = planned_protocol_path
        freeze_manifest, freeze_files_verified = _verify_freeze_artifacts(
            repository,
            str(protocol_payload.get("protocol_id", "")),
            freeze_protocol_path,
            planned_protocol_path,
            freeze_manifest_path,
        )

    with tempfile.TemporaryDirectory() as temporary:
        temp_root = Path(temporary)
        regenerated_corpus = temp_root / "corpus"
        regenerated_preoutput = temp_root / "preoutput"
        generate_a0r1_corpus(protocol_for_regen, regenerated_corpus)
        run_a0r1_preoutput_audits(
            protocol_for_regen,
            regenerated_corpus,
            source_corpus,
            regenerated_preoutput,
        )
        _require_equal(tracked_corpus, regenerated_corpus, CORPUS_FILES)
        _require_equal(tracked_preoutput, regenerated_preoutput, PREOUTPUT_FILES)

    return {
        "artifact_class": "a0-r1-foundation-verification",
        "protocol_id": protocol_payload.get("protocol_id"),
        "protocol_status": protocol_status,
        "protocol_file_matches_frozen": protocol_status != "frozen" or protocol.read_bytes() == freeze_protocol_path.read_bytes(),
        "empirical": True,
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "model_output_accessed": False,
        "sealed_model_output_accessed": False,
        "freeze_manifest": freeze_manifest,
        "corpus_files_verified": len(CORPUS_FILES),
        "preoutput_files_verified": len(PREOUTPUT_FILES),
        "freeze_files_verified": freeze_files_verified,
        "freeze_status": freeze_manifest.get("status") if freeze_manifest else "not_applicable",
        "status": "pass",
    }
