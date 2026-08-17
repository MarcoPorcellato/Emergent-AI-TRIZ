"""Guarded material orchestrator for EXP-001 R3.

This module is intentionally an orchestration boundary.  It never imports a
model runtime and never discovers a target key: both capabilities are passed
in by the caller after the independent approval and resource gates.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .exp001_r3_execution import preflight
from .exp001_r3_primary_fixture import build_primary_records
from .exp001_r3_secondary_fixture import build_secondary_records
from .exp001_r3_report import generate_r3_report_package
from .exp001_r3_response_execution import execute_public_responses
from .exp001_r3_runner import run_analysis_boundary

PROTOCOL_ID = "exp001-reference-integrated-r3-v1.0.0"
MODEL_ID = "HuggingFaceTB/SmolLM2-360M"
REVISION = "f8027fd0eaeea54caa13c31d31b9fdc459c38b49"
PACKAGE_ROOT = Path("results/exp001-r3")
MAX_WALL = 1800.0
MAX_RSS = 8_589_934_592


class Exp001MaterialRunnerError(RuntimeError):
    """A terminal, publication-worthy material-run error."""


def _utc(value: str | None) -> str:
    if value is not None:
        return value
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _stable(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    """Create one JSON file atomically and refuse an existing path."""
    if path.exists():
        raise Exp001MaterialRunnerError(f"refuse overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _stable(value)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=".r3-", delete=False) as stream:
            stream.write(data)
            temporary = Path(stream.name)
        os.link(temporary, path)
    except FileExistsError as exc:
        raise Exp001MaterialRunnerError(f"refuse overwrite: {path}") from exc
    except OSError as exc:
        raise Exp001MaterialRunnerError(f"cannot persist {path.name}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _records(root: Path) -> list[dict[str, Any]]:
    base = root / "experiments/exp001-reference-integrated"
    primary = [json.loads(line) for line in (base / "fixtures/primary-units.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    matrix = [json.loads(line) for line in (base / "fixtures/matrix-cells.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    edges = [json.loads(line) for line in (base / "fixtures/tool-edges.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    records = build_primary_records(primary) + build_secondary_records(matrix, edges)
    if len(records) != 85:
        raise Exp001MaterialRunnerError("material inventory must contain exactly 85 records")
    return records


def _resource(resource_probe: Callable[[], Mapping[str, Any]] | None) -> dict[str, Any]:
    if resource_probe is None:
        return {"wall_seconds": 0.0, "peak_rss_bytes": 0}
    observed = dict(resource_probe())
    wall = float(observed.get("wall_seconds", 0.0))
    rss = int(observed.get("peak_rss_bytes", 0))
    if wall < 0 or rss < 0:
        raise Exp001MaterialRunnerError("resource probe returned negative values")
    if wall > MAX_WALL or rss > MAX_RSS:
        raise Exp001MaterialRunnerError("frozen resource ceiling exceeded")
    return {"wall_seconds": wall, "peak_rss_bytes": rss}


def _receipt(status: str, created_at: str, runtime_status: str, access: Mapping[str, Any], resources: Mapping[str, Any], reports: Sequence[str] = ()) -> dict[str, Any]:
    value: dict[str, Any] = {
        "artifact_class": "exp001-r3-execution-receipt", "protocol_id": PROTOCOL_ID,
        "status": status, "created_at": created_at,
        "model": {"id": MODEL_ID, "revision": REVISION, "local_locator": "artifacts/models/smollm2-360m-f8027fd0"},
        "execution": {"runtime_status": runtime_status, "device": "cpu", "dtype": "float32", "network": "disabled", "generation": False, "run_count": 1, "wall_seconds": float(resources.get("wall_seconds", 0.0)), "peak_rss_bytes": int(resources.get("peak_rss_bytes", 0))},
        "access": dict(access), "claim_ids": [], "evidence_eligible": False, "expert_validated": False,
    }
    if reports:
        value["reports"] = list(reports)
    return value


def _failure(status: str, stage: str, error: BaseException, access: Mapping[str, Any]) -> dict[str, Any]:
    digest = hashlib.sha256(f"{type(error).__name__}:{error}".encode()).hexdigest()
    return {"artifact_class": "exp001-r3-run-failure", "protocol_id": PROTOCOL_ID, "status": status,
            "scientific_status": "exploratory", "empirical": True, "evidence_eligible": False,
            "expert_validated": False, "claim_ids": [], "failure": {"stage": stage, "failure_kind": type(error).__name__, "failure_digest": digest}, "access": dict(access)}


def run_material(*, root: str | Path, run_id: str, authorization: Mapping[str, Any], adapter: Any, target_reader: Callable[[Sequence[Mapping[str, Any]]], Sequence[Mapping[str, Any]]], created_at: str | None = None, clock: Callable[[], float] | None = None, resource_probe: Callable[[], Mapping[str, Any]] | None = None, preflight_fn: Callable[[str | Path, Mapping[str, Any]], Mapping[str, Any]] = preflight, report_fn: Callable[..., Any] = generate_r3_report_package) -> dict[str, Any]:
    """Execute one injected SmolLM2 run and publish its terminal package.

    ``preflight_fn`` and ``report_fn`` are injectable solely for deterministic
    tests; production callers use the defaults.  The function refuses any
    pre-existing package and never retries a capability after it is called.
    """
    repo = Path(root).resolve()
    package = repo / PACKAGE_ROOT / run_id
    if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise Exp001MaterialRunnerError("run_id must be a simple non-empty directory name")
    if package.exists():
        raise Exp001MaterialRunnerError("refuse overwrite: run package exists")
    started = clock() if clock else 0.0
    created = _utc(created_at)
    access: dict[str, Any] = {"model_loaded": False, "model_output_accessed": "not_accessed", "sealed_targets_accessed": "not_accessed", "target_reads": 0}
    resources: dict[str, Any] = {"wall_seconds": 0.0, "peak_rss_bytes": 0}
    try:
        preflight_fn(repo, authorization)
        records = _records(repo)
        resources = _resource(resource_probe)
        responses = execute_public_responses(records, adapter)
        access["model_loaded"] = bool(getattr(adapter, "model_loaded", True))
        access["model_output_accessed"] = "accessed"
        response_index = {"artifact_class": "exp001-r3-response-index", "protocol_id": PROTOCOL_ID, "record_count": 85, "records": responses}
        plan = _json(repo / "experiments/exp001-reference-integrated/analysis-plan.json")
        access["sealed_targets_accessed"] = "possibly_accessed"
        access["target_reads"] = 1
        analysis = run_analysis_boundary(records, responses, target_reader, plan)
        access["sealed_targets_accessed"] = "accessed"
        resources = _resource(resource_probe)
        result = analysis["analysis"]
        statistical = {"artifact_class": "exp001-r3-statistical-result", "protocol_id": PROTOCOL_ID, "status": result["status"], "scientific_status": "exploratory", "empirical": True, "evidence_eligible": False, "expert_validated": False, "claim_ids": [], "design": {"units": 24, "domains": 6, "families": 12, "replicates": 2, "permutation_count": 64, "bootstrap_count": 10000}, "primary": {"metric": "transfer_minus_lexical_control", "mean_delta": result["primary"]["mean_domain_delta"], "p_value": result["primary"]["two_sided_exact_p"], "bootstrap_lower": result["primary"]["bootstrap_95_ci"][0], "all_domain_deltas_positive": result["primary"]["all_domain_directions_positive"]}, "input_hashes": {"response_index": _sha_bytes(_stable(response_index))}, "interpretation": "Exploratory automated-proxy result; no general TRIZ claim."}
        receipt = _receipt(result["status"], created, "completed", access, resources)
        package.mkdir(parents=True)
        _write_new(package / "response-index.json", response_index)
        _write_new(package / "statistical-result.json", statistical)
        _write_new(package / "execution-receipt.json", receipt)
        report_fn(package_dir=PACKAGE_ROOT / run_id, created_at=created, terminal_result=PACKAGE_ROOT / run_id / "statistical-result.json", execution_receipt=PACKAGE_ROOT / run_id / "execution-receipt.json", response_index=PACKAGE_ROOT / run_id / "response-index.json", repo_root=repo)
        return {"status": result["status"], "package_dir": str(PACKAGE_ROOT / run_id), "analysis": analysis}
    except Exception as error:
        if package.exists():
            raise
        status = "incompatible" if isinstance(error, Exp001MaterialRunnerError) and "ceiling" in str(error) else "failed"
        failure = _failure(status, "execution", error, access)
        receipt = _receipt(status, created, "failed", access, resources)
        package.mkdir(parents=True, exist_ok=True)
        _write_new(package / "statistical-result.json", failure)
        _write_new(package / "execution-receipt.json", receipt)
        try:
            report_fn(package_dir=PACKAGE_ROOT / run_id, created_at=created, terminal_result=PACKAGE_ROOT / run_id / "statistical-result.json", execution_receipt=PACKAGE_ROOT / run_id / "execution-receipt.json", repo_root=repo)
        except Exception:
            pass
        return {"status": status, "package_dir": str(PACKAGE_ROOT / run_id), "failure": failure}


__all__ = ["Exp001MaterialRunnerError", "run_material"]
