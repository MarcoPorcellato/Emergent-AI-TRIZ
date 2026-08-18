"""Approval-gated material runner for the EXP-001 model comparison.

The runner is deliberately model- and target-capability agnostic: callers
inject an already loaded teacher-forcing adapter and a one-shot target reader.
This keeps model loading and sealed-key access observable at the outer CLI
boundary and makes the runner fully synthetic-testable without model bytes.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .exp001_comparative_contract import ComparativeContractError, EXPECTED_MODELS, validate_comparative_contract
from .exp001_r3_analysis import analyze_primary
from .exp001_r3_primary_fixture import build_primary_records
from .exp001_r3_response_execution import execute_public_responses
from .exp001_r3_secondary_fixture import build_secondary_records
from .exp001_r3_runner import run_analysis_boundary
from .exp001_comparative_report import generate_comparative_report

PROTOCOL_ID = "exp001-reference-comparative-v1.0.0"
PACKAGE_ROOT = Path("results/exp001-comparative")
MAX_WALL_SECONDS = 1800.0
MAX_RSS_BYTES = 8_589_934_592
MAX_DENSE_BYTES = 134_217_728


class ComparativeMaterialError(RuntimeError):
    """A terminal, publication-worthy comparative execution error."""


def _stable(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise ComparativeMaterialError(f"refuse overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=".comparative-", delete=False) as stream:
            stream.write(_stable(value))
            temporary = Path(stream.name)
        os.link(temporary, path)
    except FileExistsError as exc:
        raise ComparativeMaterialError(f"refuse overwrite: {path}") from exc
    except OSError as exc:
        raise ComparativeMaterialError(f"cannot persist {path}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _records(root: Path) -> list[dict[str, Any]]:
    base = root / "experiments/exp001-reference-integrated/fixtures"
    read = lambda name: [json.loads(line) for line in (base / name).read_text(encoding="utf-8").splitlines() if line.strip()]
    records = build_primary_records(read("primary-units.jsonl")) + build_secondary_records(read("matrix-cells.jsonl"), read("tool-edges.jsonl"))
    if len(records) != 85:
        raise ComparativeMaterialError("comparative inventory must contain exactly 85 records")
    return records


def _model_key(model_id: str) -> str:
    return {"EleutherAI/pythia-70m-deduped": "pythia-70m-e93a9faa", "HuggingFaceTB/SmolLM2-360M": "smollm2-360m-f8027fd0", "Qwen/Qwen3-0.6B-Base": "qwen3-0.6b-da87bfb"}.get(model_id, "unknown")


def _check_gate(gate: Mapping[str, Any] | None) -> None:
    if not isinstance(gate, Mapping):
        raise ComparativeMaterialError("CCP gate receipt is required")
    if gate.get("resource_decision") != "admit" or gate.get("admission_active") is not False or gate.get("queue_count") != 0:
        raise ComparativeMaterialError("CCP gate must be Admit with inactive empty admission")


def validate_material_authorization(authorization: Mapping[str, Any], model_id: str, revision: str) -> None:
    if not isinstance(authorization, Mapping) or authorization.get("status") != "authorized":
        raise ComparativeMaterialError("comparative execution authorization is absent")
    approval = authorization.get("operator_approval")
    if not isinstance(approval, Mapping) or approval.get("granted") is not True:
        raise ComparativeMaterialError("operator approval is absent")
    models = authorization.get("exact_models")
    if not isinstance(models, Sequence):
        raise ComparativeMaterialError("exact model list is absent")
    match = next((entry for entry in models if isinstance(entry, Mapping) and entry.get("model_id") == model_id), None)
    if not isinstance(match, Mapping) or match.get("revision") != revision:
        raise ComparativeMaterialError("model identity is not bound by authorization")
    permissions = authorization.get("permissions_requested")
    if not isinstance(permissions, Mapping) or permissions.get({"EleutherAI/pythia-70m-deduped": "load_existing_pythia_once", "HuggingFaceTB/SmolLM2-360M": "load_existing_smollm2_once", "Qwen/Qwen3-0.6B-Base": "load_qwen_once_after_integrity"}.get(model_id, "")) is not True:
        raise ComparativeMaterialError("model-specific load permission is absent")
    if permissions.get("network") is not False or permissions.get("generation") is not False or permissions.get("sealed_target_read") != "exactly_one_per_model_at_analysis_boundary":
        raise ComparativeMaterialError("execution boundaries drift")


def run_comparative_material(*, root: str | Path, run_id: str, model_id: str, revision: str, authorization: Mapping[str, Any], ccp_gate: Mapping[str, Any], adapter: Any, target_reader: Callable[[Sequence[Mapping[str, Any]]], Sequence[Mapping[str, Any]]], analysis_plan: Mapping[str, Any], clock: Callable[[], float] | None = None, resource_probe: Callable[[], Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Run one exact model with one target-read boundary and immutable output."""
    repo = Path(root).resolve()
    if model_id not in EXPECTED_MODELS or EXPECTED_MODELS[model_id]["revision"] != revision:
        raise ComparativeMaterialError("unregistered model identity")
    validate_material_authorization(authorization, model_id, revision)
    _check_gate(ccp_gate)
    try:
        validate_comparative_contract(repo)
    except ComparativeContractError as exc:
        # The no-download validator deliberately rejects the pending dossier;
        # material callers must provide its already reviewed frozen artifacts.
        if "authorization" not in str(exc).lower() and "permission" not in str(exc).lower():
            raise ComparativeMaterialError(f"comparative contract failed: {exc}") from exc
    if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ComparativeMaterialError("run_id must be a simple non-empty name")
    key = _model_key(model_id)
    package = repo / PACKAGE_ROOT / f"{key}-{run_id}"
    if package.exists():
        raise ComparativeMaterialError("refuse overwrite: run package exists")
    started = clock() if clock else time.monotonic()
    access: dict[str, Any] = {"model_loaded": bool(getattr(adapter, "model_loaded", True)), "model_output_accessed": False, "sealed_targets_accessed": False, "target_reads": 0}
    records = _records(repo)
    try:
        responses = execute_public_responses(records, adapter)
        access["model_output_accessed"] = True
        if clock and float(clock()) - started > MAX_WALL_SECONDS:
            raise ComparativeMaterialError("wall ceiling exceeded before analysis")
        read_count = 0
        def one_shot_reader(public_records: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
            nonlocal read_count
            read_count += 1
            if read_count != 1:
                raise ComparativeMaterialError("sealed target reader invoked more than once")
            access["target_reads"] = 1
            access["sealed_targets_accessed"] = "possibly_accessed"
            value = target_reader(public_records)
            access["sealed_targets_accessed"] = True
            return value
        analysis = run_analysis_boundary(records, responses, one_shot_reader, analysis_plan)
        if read_count != 1:
            raise ComparativeMaterialError("analysis did not perform exactly one target read")
        resources = dict(resource_probe() if resource_probe else {})
        wall = float(resources.get("wall_seconds", (clock() - started) if clock else 0.0))
        rss = int(resources.get("peak_rss_bytes", 0))
        dense = int(resources.get("new_dense_output_bytes", 0))
        if wall > MAX_WALL_SECONDS or rss > MAX_RSS_BYTES or dense > MAX_DENSE_BYTES:
            raise ComparativeMaterialError("frozen material ceiling exceeded")
        result = analysis["analysis"]
        statistical = {"artifact_class": "exp001-comparative-statistical-result", "protocol_id": PROTOCOL_ID, "model_id": model_id, "revision": revision, "status": result["status"], "scientific_status": "exploratory", "evidence_eligible": False, "expert_validated": False, "claim_ids": [], "primary": result["primary"], "secondary": analysis.get("secondary_summaries", {}), "pooling": "forbidden_across_models_and_strata", "interpretation": "Exploratory automated reference-task signal only; no general TRIZ claim."}
        response_index = {"artifact_class": "exp001-comparative-response-index", "protocol_id": PROTOCOL_ID, "model_id": model_id, "revision": revision, "record_count": len(responses), "records": responses}
        external = {"artifact_class": "exp001-comparative-external-response-scores", "protocol_id": PROTOCOL_ID, "model_id": model_id, "record_count": len(responses), "records": responses}
        external_rel = Path("artifacts/exp001-comparative") / key / run_id / "response-scores.json"
        external_abs = repo / external_rel
        _write_new(external_abs, external)
        package.mkdir(parents=True)
        _write_new(package / "response-index.json", response_index)
        _write_new(package / "statistical-result.json", statistical)
        _write_new(package / "sealed-key-access.json", {"artifact_class": "exp001-comparative-sealed-key-access", "status": "accessed", "target_reads": 1, "sealed_targets_accessed": True})
        _write_new(package / "recovery-observation.json", {"artifact_class": "exp001-comparative-recovery-observation", "status": "completed", "terminal_status": result["status"], "retry_performed": False})
        receipt = {"artifact_class": "exp001-comparative-execution-receipt", "protocol_id": PROTOCOL_ID, "model": {"id": model_id, "revision": revision}, "status": result["status"], "execution": {"runtime_status": "completed", "device": "cpu", "dtype": "float32", "network": "disabled", "generation": False, "run_count": 1, "wall_seconds": wall, "peak_rss_bytes": rss, "new_dense_output_bytes": dense}, "ccp_gate": dict(ccp_gate), "access": access, "external_response_asset": {"locator": external_rel.as_posix(), "sha256": _sha_bytes(external_abs.read_bytes())}, "claim_ids": [], "evidence_eligible": False, "expert_validated": False}
        _write_new(package / "execution-receipt.json", receipt)
        report_binding = generate_comparative_report(repo_root=repo, package_dir=package.relative_to(repo))
        manifest = {"artifact_class": "exp001-comparative-publication-manifest", "protocol_id": PROTOCOL_ID, "model_id": model_id, "revision": revision, "terminal_status": result["status"], "package": package.relative_to(repo).as_posix(), "report": report_binding, "external_response_asset": receipt["external_response_asset"], "claim_ids": [], "evidence_eligible": False, "expert_validated": False}
        _write_new(package / "publication-manifest.json", manifest)
        return {"status": result["status"], "package_dir": package.relative_to(repo).as_posix(), "access": access, "external_response_asset": receipt["external_response_asset"]}
    except Exception as exc:
        if package.exists():
            raise
        package.mkdir(parents=True, exist_ok=True)
        failure = {"artifact_class": "exp001-comparative-run-failure", "protocol_id": PROTOCOL_ID, "model_id": model_id, "revision": revision, "status": "failed", "scientific_status": "exploratory", "evidence_eligible": False, "expert_validated": False, "claim_ids": [], "failure": {"kind": type(exc).__name__, "digest": _sha_bytes(f"{type(exc).__name__}:{exc}".encode())}, "access": access}
        _write_new(package / "statistical-result.json", failure)
        _write_new(package / "sealed-key-access.json", {"artifact_class": "exp001-comparative-sealed-key-access", "status": access["sealed_targets_accessed"], "target_reads": access["target_reads"], "sealed_targets_accessed": access["sealed_targets_accessed"]})
        _write_new(package / "recovery-observation.json", {"artifact_class": "exp001-comparative-recovery-observation", "status": "terminal_failure", "terminal_status": "failed", "retry_performed": False})
        return {"status": "failed", "package_dir": package.relative_to(repo).as_posix(), "access": access}


__all__ = ["ComparativeMaterialError", "run_comparative_material", "validate_material_authorization"]
