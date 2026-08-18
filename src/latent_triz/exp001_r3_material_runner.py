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


def _wall_check(clock: Callable[[], float] | None, started: float, stage: str) -> float:
    """Enforce the wall ceiling at each irreversible execution boundary."""
    if clock is None:
        return 0.0
    elapsed = float(clock()) - started
    if elapsed < 0:
        raise Exp001MaterialRunnerError(f"clock moved backwards at {stage}")
    if elapsed > MAX_WALL:
        raise Exp001MaterialRunnerError(f"wall ceiling exceeded at {stage}: {elapsed:.3f}s")
    return elapsed


def _receipt(status: str, created_at: str, runtime_status: str, access: Mapping[str, Any], resources: Mapping[str, Any], reports: Sequence[str] = (), *, provenance: Mapping[str, Any] | None = None, external_response_asset: Mapping[str, Any] | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "artifact_class": "exp001-r3-execution-receipt", "protocol_id": PROTOCOL_ID,
        "status": status, "created_at": created_at,
        "model": {"id": MODEL_ID, "revision": REVISION, "local_locator": "artifacts/models/smollm2-360m-f8027fd0"},
        "execution": {"runtime_status": runtime_status, "device": "cpu", "dtype": "float32", "network": "disabled", "generation": False, "run_count": 1, "wall_seconds": float(resources.get("wall_seconds", 0.0)), "peak_rss_bytes": int(resources.get("peak_rss_bytes", 0))},
        "access": dict(access), "claim_ids": [], "evidence_eligible": False, "expert_validated": False,
    }
    if reports:
        value["reports"] = list(reports)
    if provenance is not None:
        value["provenance"] = dict(provenance)
    if external_response_asset is not None:
        value["external_response_asset"] = dict(external_response_asset)
    return value


def _bound_artifacts(repo: Path, values: Mapping[str, Any] | None) -> dict[str, dict[str, str]]:
    """Validate caller-supplied provenance paths and bind their live hashes."""
    required = ("implementation", "authorization", "integrity", "feasibility")
    if not isinstance(values, Mapping) or set(values) != set(required):
        raise Exp001MaterialRunnerError("provenance_artifacts must provide exactly four caller-supplied artifacts")
    bound: dict[str, dict[str, str]] = {}
    for name in required:
        entry = values[name]
        if not isinstance(entry, Mapping) or set(entry) != {"path", "sha256"}:
            raise Exp001MaterialRunnerError(f"invalid provenance artifact: {name}")
        path = Path(str(entry["path"]))
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise Exp001MaterialRunnerError(f"unsafe provenance artifact: {name}")
        absolute = (repo / path).resolve()
        if not absolute.is_file() or not absolute.is_relative_to(repo):
            raise Exp001MaterialRunnerError(f"missing provenance artifact: {name}")
        digest = _sha_bytes(absolute.read_bytes())
        if str(entry["sha256"]) != digest:
            raise Exp001MaterialRunnerError(f"provenance hash mismatch: {name}")
        bound[name] = {"path": path.as_posix(), "sha256": digest}
    return bound


def _package_artifact(repo: Path, relative: Path) -> dict[str, str]:
    absolute = (repo / relative).resolve()
    if not absolute.is_file() or not absolute.is_relative_to(repo):
        raise Exp001MaterialRunnerError(f"missing package provenance artifact: {relative}")
    return {"path": relative.as_posix(), "sha256": _sha_bytes(absolute.read_bytes())}


def _external_response_asset(repo: Path, run_id: str, records: Sequence[Mapping[str, Any]], requested_path: str | Path | None) -> dict[str, str]:
    """Persist the hash-bound scalar asset, including an empty terminal one."""
    external_rel = Path(requested_path) if requested_path is not None else Path("artifacts") / "exp001-r3" / run_id / "response-scores.json"
    if external_rel.is_absolute() or ".." in external_rel.parts or external_rel.parts[:3] != ("artifacts", "exp001-r3", run_id):
        raise Exp001MaterialRunnerError("external response asset must be artifacts/exp001-r3/<run-id>/response-scores.json")
    external_absolute = (repo / external_rel).resolve()
    external_absolute.parent.mkdir(parents=True, exist_ok=True)
    _write_new(external_absolute, {
        "artifact_class": "exp001-r3-external-response-scores",
        "protocol_id": PROTOCOL_ID,
        "record_count": len(records),
        "records": list(records),
    })
    return {"locator": external_rel.as_posix(), "sha256": _sha_bytes(external_absolute.read_bytes())}


def _terminal_provenance(repo: Path, run_id: str, values: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Bind the observations written for either a completed or failed run."""
    if values is None:
        return None
    provenance = dict(values)
    provenance["sealed_key_access"] = _package_artifact(repo, PACKAGE_ROOT / run_id / "sealed-key-access.json")
    provenance["recovery"] = _package_artifact(repo, PACKAGE_ROOT / run_id / "recovery-observation.json")
    return provenance


def _failure(status: str, stage: str, error: BaseException, access: Mapping[str, Any]) -> dict[str, Any]:
    digest = hashlib.sha256(f"{type(error).__name__}:{error}".encode()).hexdigest()
    return {"artifact_class": "exp001-r3-run-failure", "protocol_id": PROTOCOL_ID, "status": status,
            "scientific_status": "exploratory", "empirical": True, "evidence_eligible": False,
            "expert_validated": False, "claim_ids": [], "failure": {"stage": stage, "failure_kind": type(error).__name__, "failure_digest": digest}, "access": dict(access)}


def run_material(*, root: str | Path, run_id: str, authorization: Mapping[str, Any], adapter: Any, target_reader: Callable[[Sequence[Mapping[str, Any]]], Sequence[Mapping[str, Any]]], created_at: str | None = None, clock: Callable[[], float] | None = None, resource_probe: Callable[[], Mapping[str, Any]] | None = None, preflight_fn: Callable[[str | Path, Mapping[str, Any]], Mapping[str, Any]] = preflight, report_fn: Callable[..., Any] = generate_r3_report_package, provenance_artifacts: Mapping[str, Any] | None = None, external_response_asset_path: str | Path | None = None) -> dict[str, Any]:
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
    provenance: dict[str, Any] | None = None
    try:
        # Bind independent provenance before preflight so a pre-model failure
        # can still be report-verifiable.  This reads only caller-declared,
        # non-sensitive artifacts and cannot load a model or sealed target.
        provenance = _bound_artifacts(repo, provenance_artifacts) if report_fn is generate_r3_report_package else (dict(provenance_artifacts) if isinstance(provenance_artifacts, Mapping) else None)
        preflight_fn(repo, authorization)
        records = _records(repo)
        _wall_check(clock, started, "pre_model")
        resources = _resource(resource_probe)
        responses = execute_public_responses(records, adapter)
        resources["wall_seconds"] = max(resources["wall_seconds"], _wall_check(clock, started, "after_public_scoring"))
        access["model_loaded"] = bool(getattr(adapter, "model_loaded", True))
        access["model_output_accessed"] = "accessed"
        response_index = {"artifact_class": "exp001-r3-response-index", "protocol_id": PROTOCOL_ID, "record_count": 85, "records": responses}
        plan = _json(repo / "experiments/exp001-reference-integrated/analysis-plan.json")
        target_invoked = False
        def guarded_reader(public_records: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
            nonlocal target_invoked
            if target_invoked:
                raise Exp001MaterialRunnerError("sealed target reader invoked more than once")
            target_invoked = True
            access["target_reads"] = 1
            access["sealed_targets_accessed"] = "possibly_accessed"
            try:
                value = target_reader(public_records)
            except Exception:
                # A failed reader may have opened the sealed target before failing.
                raise
            access["sealed_targets_accessed"] = "accessed"
            return value
        analysis = run_analysis_boundary(records, responses, guarded_reader, plan)
        _wall_check(clock, started, "after_analysis")
        access["sealed_targets_accessed"] = "accessed"
        observed = _resource(resource_probe)
        resources = {"wall_seconds": max(resources["wall_seconds"], observed["wall_seconds"], _wall_check(clock, started, "after_analysis")), "peak_rss_bytes": max(resources["peak_rss_bytes"], observed["peak_rss_bytes"])}
        result = analysis["analysis"]
        statistical = {"artifact_class": "exp001-r3-statistical-result", "protocol_id": PROTOCOL_ID, "status": result["status"], "scientific_status": "exploratory", "empirical": True, "evidence_eligible": False, "expert_validated": False, "claim_ids": [], "design": {"units": 24, "domains": 6, "families": 12, "replicates": 2, "permutation_count": 64, "bootstrap_count": 10000}, "primary": {"metric": "transfer_minus_lexical_control", "mean_delta": result["primary"]["mean_domain_delta"], "p_value": result["primary"]["two_sided_exact_p"], "bootstrap_lower": result["primary"]["bootstrap_95_ci"][0], "all_domain_deltas_positive": result["primary"]["all_domain_directions_positive"]}, "input_hashes": {"response_index": _sha_bytes(_stable(response_index))}, "interpretation": "Exploratory automated-proxy result; no general TRIZ claim."}
        secondary = analysis.get("secondary_summary", {"pooling": "non_pooled", "matrix_2003": "not reported", "panitz": "not reported"})
        statistical["secondary_summary"] = secondary
        package.mkdir(parents=True)
        _write_new(package / "response-index.json", response_index)
        external_asset = _external_response_asset(repo, run_id, responses, external_response_asset_path)
        _write_new(package / "statistical-result.json", statistical)
        sealed_observation = {"artifact_class": "exp001-r3-sealed-key-access-observation", "status": access["sealed_targets_accessed"], "target_reads": access["target_reads"], "sealed_targets_accessed": access["sealed_targets_accessed"]}
        recovery_observation = {"artifact_class": "exp001-r3-recovery-observation", "status": "completed", "terminal_status": result["status"], "retry_performed": False}
        _write_new(package / "sealed-key-access.json", sealed_observation)
        _write_new(package / "recovery-observation.json", recovery_observation)
        provenance = _terminal_provenance(repo, run_id, provenance)
        receipt = _receipt(result["status"], created, "completed", access, resources, provenance=provenance, external_response_asset=external_asset)
        _write_new(package / "execution-receipt.json", receipt)
        try:
            report_fn(package_dir=PACKAGE_ROOT / run_id, created_at=created, terminal_result=PACKAGE_ROOT / run_id / "statistical-result.json", execution_receipt=PACKAGE_ROOT / run_id / "execution-receipt.json", response_index=PACKAGE_ROOT / run_id / "response-index.json", repo_root=repo)
        except Exception as report_error:
            observation = {"artifact_class": "exp001-r3-publication-recovery-observation", "status": "publication_failed", "stage": "report_generation", "failure_kind": type(report_error).__name__, "failure": str(report_error), "preserved_artifacts": ["response-index.json", "statistical-result.json", "execution-receipt.json"]}
            _write_new(package / "publication-recovery-observation.json", observation)
            raise Exp001MaterialRunnerError(f"publication failed during report generation: {report_error}") from report_error
        return {"status": result["status"], "package_dir": str(PACKAGE_ROOT / run_id), "analysis": analysis}
    except Exception as error:
        if package.exists():
            raise
        status = "incompatible" if isinstance(error, Exp001MaterialRunnerError) and "ceiling" in str(error) else "failed"
        failure = _failure(status, "execution", error, access)
        package.mkdir(parents=True, exist_ok=True)
        _write_new(package / "statistical-result.json", failure)
        external_asset = _external_response_asset(repo, run_id, (), external_response_asset_path)
        sealed_observation = {"artifact_class": "exp001-r3-sealed-key-access-observation", "status": access["sealed_targets_accessed"], "target_reads": access["target_reads"], "sealed_targets_accessed": access["sealed_targets_accessed"]}
        recovery_observation = {"artifact_class": "exp001-r3-recovery-observation", "status": "terminal_failure", "terminal_status": status, "retry_performed": False}
        _write_new(package / "sealed-key-access.json", sealed_observation)
        _write_new(package / "recovery-observation.json", recovery_observation)
        provenance = _terminal_provenance(repo, run_id, provenance)
        runtime_status = "not_started" if access["model_output_accessed"] == "not_accessed" else "failed"
        receipt = _receipt(status, created, runtime_status, access, resources, provenance=provenance, external_response_asset=external_asset)
        _write_new(package / "execution-receipt.json", receipt)
        try:
            report_fn(package_dir=PACKAGE_ROOT / run_id, created_at=created, terminal_result=PACKAGE_ROOT / run_id / "statistical-result.json", execution_receipt=PACKAGE_ROOT / run_id / "execution-receipt.json", repo_root=repo)
        except Exception as report_error:
            observation = {"artifact_class": "exp001-r3-publication-recovery-observation", "status": "publication_failed", "stage": "failure_report_generation", "failure_kind": type(report_error).__name__, "failure": str(report_error), "preserved_artifacts": ["statistical-result.json", "execution-receipt.json"]}
            _write_new(package / "publication-recovery-observation.json", observation)
            return {"status": status, "package_dir": str(PACKAGE_ROOT / run_id), "failure": failure, "publication_failure": str(report_error)}
        return {"status": status, "package_dir": str(PACKAGE_ROOT / run_id), "failure": failure}


__all__ = ["Exp001MaterialRunnerError", "run_material"]
