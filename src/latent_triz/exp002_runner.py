"""Fail-closed, injected runner and publisher for EXP-002 material stages.

The runner owns the observable boundaries around one model/study package but
does not import a model library, discover files, or open targets itself.  A
CLI must verify the exact local snapshot and construct the adapter before
calling it.  Scores are produced before the single analysis-boundary target
reader can be invoked; every terminal state is persisted without overwrite.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any

from .exp002_execution import Exp002ExecutionError, authorize_material_run, score_injected_surface
from .exp002_followup import EXPECTED_MODELS
from .exp002_stage_gate import Exp002StageGateError, authorize_stage


class Exp002RunnerError(RuntimeError):
    """Raised when an EXP-002 run cannot be safely materialised."""


_RUN_ID = re.compile(r"^exp002-[a-z0-9-]+$")
_TERMINAL = {"positive", "null", "failed", "non_interpretable", "incompatible"}
_MAX_WALL = 1_800.0
_MAX_RSS = 8_589_934_592
_MAX_DENSE = 134_217_728


def _stable(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_new(path: Path, value: Any) -> None:
    """Atomically create one new JSON/text path and refuse overwrite."""
    if path.exists():
        raise Exp002RunnerError(f"refuse overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=".exp002-", delete=False) as stream:
            payload = value if isinstance(value, bytes) else _stable(value)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            temporary = Path(stream.name)
        os.link(temporary, path)
    except FileExistsError as exc:
        raise Exp002RunnerError(f"refuse overwrite: {path}") from exc
    except OSError as exc:
        raise Exp002RunnerError(f"cannot persist {path}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _model_key(model_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model_id.lower()).strip("-")


def _validate_identity(model_id: str, revision: str) -> None:
    if EXPECTED_MODELS.get(model_id) != revision:
        raise Exp002RunnerError("model identity or revision is not frozen")


def _terminal_status(value: Any) -> str:
    status = value.get("status") if isinstance(value, Mapping) else None
    return status if status in _TERMINAL else "non_interpretable"


def _resource_values(resource_probe: Callable[[], Mapping[str, Any]] | None, started: float, clock: Callable[[], float]) -> tuple[float, int, int]:
    values = dict(resource_probe() if resource_probe is not None else {})
    wall = float(values.get("wall_seconds", clock() - started))
    rss = int(values.get("peak_rss_bytes", 0))
    dense = int(values.get("new_dense_output_bytes", 0))
    if wall < 0 or rss < 0 or dense < 0:
        raise Exp002RunnerError("resource receipt contains a negative value")
    return wall, rss, dense


def run_exp002_stage(
    *,
    root: str | Path,
    run_id: str,
    study_id: str,
    model_id: str,
    revision: str,
    dossier: Mapping[str, Any],
    ccp_gate: Mapping[str, Any],
    public_rows: Sequence[Mapping[str, Any]],
    scorer: Callable[[str], Mapping[str, Any]],
    target_reader: Callable[[Sequence[Mapping[str, Any]]], Sequence[Mapping[str, Any]]],
    analysis: Callable[[Sequence[Mapping[str, Any]], Callable[[], Sequence[Mapping[str, Any]]]], Mapping[str, Any]],
    adapter: Any,
    resource_probe: Callable[[], Mapping[str, Any]] | None = None,
    clock: Callable[[], float] | None = None,
) -> dict[str, Any]:
    """Execute and publish exactly one injected EXP-002 stage.

    ``analysis`` receives scored public rows and a zero-argument one-shot
    reader.  It must call that reader exactly once at its declared boundary.
    The reader itself is the only capability that may expose sealed targets.
    """
    if study_id not in {"EXP-002A", "EXP-002B", "EXP-002C", "EXP-002D"}:
        raise Exp002RunnerError("unknown study id")
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise Exp002RunnerError("run_id must use the exp002 namespace")
    _validate_identity(model_id, revision)
    try:
        if dossier.get("artifact_class") == "exp002-study-approval-dossier":
            authorize_stage(dossier, study_id, ccp_gate)
        else:
            authorize_material_run(dossier, ccp_gate, model_id)
    except (Exp002ExecutionError, Exp002StageGateError) as exc:
        raise Exp002RunnerError(str(exc)) from exc
    if not isinstance(public_rows, Sequence) or isinstance(public_rows, (str, bytes, bytearray)) or not public_rows:
        raise Exp002RunnerError("public rows must be a non-empty sequence")
    repo = Path(root).resolve()
    package = repo / "results" / "exp002" / _model_key(model_id) / run_id
    external = repo / "artifacts" / "exp002" / _model_key(model_id) / run_id / "response-scores.json"
    if package.exists() or external.exists():
        raise Exp002RunnerError("run package already exists")
    now = clock or time.monotonic
    started = now()
    access = {
        "model_loaded": bool(getattr(adapter, "model_loaded", True)),
        "model_output_accessed": False,
        "sealed_target_accessed": False,
        "target_reads": 0,
    }
    scored: list[dict[str, Any]] = []
    terminal = "failed"
    analysis_result: Mapping[str, Any] = {"status": "failed", "reason": "not_started"}
    failure: dict[str, str] | None = None
    try:
        scored = score_injected_surface(public_rows, scorer)
        access["model_output_accessed"] = True
        read_count = 0

        def one_shot_reader() -> Sequence[Mapping[str, Any]]:
            nonlocal read_count
            if read_count != 0:
                raise Exp002RunnerError("sealed target reader invoked more than once")
            read_count = 1
            access["target_reads"] = 1
            access["sealed_target_accessed"] = True
            return target_reader(public_rows)

        analysis_result = analysis(scored, one_shot_reader)
        if read_count != 1:
            raise Exp002RunnerError("analysis did not perform exactly one target read")
        terminal = _terminal_status(analysis_result)
    except Exception as exc:
        terminal = "failed"
        failure = {"kind": type(exc).__name__, "digest": _sha_bytes(f"{type(exc).__name__}:{exc}".encode())}
    wall, rss, measured_dense = _resource_values(resource_probe, started, now)
    external_payload = {
        "artifact_class": "exp002-external-response-scores",
        "protocol_id": "exp002-qwen3-followup-v1.0.0",
        "study_id": study_id,
        "model_id": model_id,
        "revision": revision,
        "records": scored,
    }
    dense_bytes = max(measured_dense, len(_stable(external_payload)))
    if wall > _MAX_WALL or rss > _MAX_RSS or dense_bytes > _MAX_DENSE:
        terminal = "failed"
        failure = {"kind": "ResourceCeilingExceeded", "digest": _sha_bytes(f"{wall}:{rss}:{dense_bytes}".encode())}
    external.parent.mkdir(parents=True, exist_ok=True)
    _write_new(external, external_payload)
    receipt = {
        "artifact_class": "exp002-execution-receipt",
        "protocol_id": "exp002-qwen3-followup-v1.0.0",
        "run_id": run_id,
        "model_id": model_id,
        "revision": revision,
        "status": terminal,
        "execution": {"device": "cpu", "dtype": "float32", "network": False, "generation": False, "run_count": 1, "wall_seconds": wall, "peak_rss_bytes": rss, "new_dense_output_bytes": dense_bytes},
        "access": access,
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "external_response_asset": {"locator": external.relative_to(repo).as_posix(), "sha256": _sha_file(external)},
    }
    statistical = {
        "artifact_class": "exp002-statistical-result",
        "protocol_id": "exp002-qwen3-followup-v1.0.0",
        "study_id": study_id,
        "model_id": model_id,
        "revision": revision,
        "status": terminal,
        "analysis": dict(analysis_result),
        "failure": failure,
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "pooling": "forbidden_across_models_and_studies",
    }
    response_index = {"artifact_class": "exp002-response-index", "protocol_id": "exp002-qwen3-followup-v1.0.0", "study_id": study_id, "model_id": model_id, "revision": revision, "record_count": len(scored), "records": scored}
    package.mkdir(parents=True, exist_ok=False)
    _write_new(package / "execution-receipt.json", receipt)
    _write_new(package / "statistical-result.json", statistical)
    _write_new(package / "response-index.json", response_index)
    _write_new(package / "sealed-key-access.json", {"artifact_class": "exp002-sealed-key-access", "target_reads": access["target_reads"], "sealed_target_accessed": access["sealed_target_accessed"]})
    _write_new(package / "recovery-observation.json", {"artifact_class": "exp002-recovery-observation", "terminal_status": terminal, "retry_performed": False, "cleanup_status": "not_applicable"})
    _write_new(package / "report.md", f"# EXP-002 {study_id}\n\nTerminal status: `{terminal}`.\n\nThis exploratory package carries no promoted TRIZ claim.\n")
    bindings = {name: {"path": (package / name).relative_to(repo).as_posix(), "sha256": _sha_file(package / name)} for name in ("execution-receipt.json", "statistical-result.json", "response-index.json", "sealed-key-access.json", "recovery-observation.json", "report.md")}
    manifest = {"artifact_class": "exp002-publication-manifest", "protocol_id": "exp002-qwen3-followup-v1.0.0", "status": "published", "packages": [{"model_id": model_id, "revision": revision, "terminal_status": terminal, "package_locator": package.relative_to(repo).as_posix()}], "external_dense_assets": [receipt["external_response_asset"]], "bindings": bindings, "claim_ids": [], "evidence_eligible": False, "expert_validated": False}
    _write_new(package / "publication-manifest.json", manifest)
    return {"status": terminal, "package": package.relative_to(repo).as_posix(), "receipt": receipt, "failure": failure}


__all__ = ["Exp002RunnerError", "run_exp002_stage"]
