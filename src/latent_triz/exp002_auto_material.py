"""Fail-closed material boundary for EXP-002-AUTO.

This module is intentionally adapter-injected.  It can verify an approved
snapshot and persist one terminal package without importing ``torch`` or
``transformers``.  A command-line wrapper may construct a model only after
``prepare_auto_shard`` returns successfully.  The sealed key is exposed only
through the one-shot reader handed to the injected analysis function.
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

from .exp002_auto_contract import Exp002AutoContractError, validate_auto_dossier
from .exp002_followup import EXPECTED_MODELS


class Exp002AutoMaterialError(RuntimeError):
    """Raised when an AUTO material boundary cannot be satisfied safely."""


PROTOCOL_ID = "exp002-auto-v1.0.0"
MAX_WALL_SECONDS = 1_800.0
MAX_RSS_BYTES = 8_589_934_592
MAX_DENSE_BYTES = 134_217_728
TERMINAL_STATUSES = frozenset({"auto_proxy_signal", "null", "failed", "non_interpretable", "incompatible"})
_RUN_ID = re.compile(r"^exp002-auto-[a-z0-9-]+$")
_FORBIDDEN = frozenset({"target", "expected_candidate_index", "correct_choice", "expected_answer"})


def _stable(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> tuple[int, str]:
    """Hash a file in bounded chunks; never materialise a model file in RAM."""
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1 << 20), b""):
                size += len(block)
                digest.update(block)
    except OSError as exc:
        raise Exp002AutoMaterialError(f"cannot hash runtime file: {path.name}") from exc
    return size, digest.hexdigest()


def _safe_relative(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
        raise Exp002AutoMaterialError(f"unsafe {field}")
    return value.replace("\\", "/")


def verify_runtime_receipt(
    *, receipt: Mapping[str, Any], model_id: str, revision: str, model_root: str | Path,
) -> dict[str, Any]:
    """Verify the already acquired exact snapshot without model-library access."""
    if not isinstance(receipt, Mapping) or receipt.get("status") not in {"pass", "integrity_verified"}:
        raise Exp002AutoMaterialError("runtime integrity receipt is not verified")
    model = receipt.get("model")
    observed_id = receipt.get("model_id") or (model.get("id") if isinstance(model, Mapping) else None)
    observed_revision = receipt.get("revision") or (model.get("revision") if isinstance(model, Mapping) else None)
    if observed_id != model_id or observed_revision != revision:
        raise Exp002AutoMaterialError("runtime receipt identity drift")
    items = receipt.get("runtime_files")
    if isinstance(items, (str, bytes, bytearray)) or not isinstance(items, Sequence) or not items:
        raise Exp002AutoMaterialError("runtime receipt has no file allowlist")
    root = Path(model_root)
    checked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            raise Exp002AutoMaterialError("runtime receipt file entry is malformed")
        name = _safe_relative(item.get("path", item.get("name")), "runtime file path")
        if name in seen:
            raise Exp002AutoMaterialError("runtime receipt has duplicate files")
        seen.add(name)
        expected_hash = item.get("sha256")
        if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise Exp002AutoMaterialError("runtime receipt file digest is invalid")
        expected_size = item.get("size")
        if isinstance(expected_size, bool) or not isinstance(expected_size, int) or expected_size < 0:
            raise Exp002AutoMaterialError("runtime receipt file size is invalid")
        path = root / name
        if not path.is_file():
            raise Exp002AutoMaterialError(f"runtime file is missing: {name}")
        size, observed_hash = sha256_file(path)
        if size != expected_size or observed_hash != expected_hash:
            raise Exp002AutoMaterialError(f"runtime integrity mismatch: {name}")
        checked.append({"path": name, "size": size, "sha256": observed_hash})
    return {"model_id": model_id, "revision": revision, "runtime_files_checked": len(checked), "files": checked}


def _gate_ok(gate: Mapping[str, Any]) -> bool:
    if not isinstance(gate, Mapping):
        return False
    decision = gate.get("resource_decision", gate.get("decision"))
    active = gate.get("admission_active", gate.get("active"))
    return decision == "admit" and active is False and gate.get("queue_count") == 0


def _model_key(model_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model_id.lower()).strip("-")


def _write_new(path: Path, value: Any) -> None:
    if path.exists():
        raise Exp002AutoMaterialError(f"refuse overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=".exp002-auto-", delete=False) as stream:
            stream.write(value if isinstance(value, bytes) else _stable(value))
            stream.flush()
            os.fsync(stream.fileno())
            temporary = Path(stream.name)
        os.link(temporary, path)
    except FileExistsError as exc:
        raise Exp002AutoMaterialError(f"refuse overwrite: {path}") from exc
    except OSError as exc:
        raise Exp002AutoMaterialError(f"cannot persist {path}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def prepare_auto_shard(
    *, dossier: Mapping[str, Any], protocol_sha256: str, schedule_sha256: str,
    input_manifest_sha256: str, gate: Mapping[str, Any], model_id: str,
    stage_id: str, shard_id: str, runtime_receipt: Mapping[str, Any],
    model_root: str | Path,
) -> dict[str, Any]:
    """Validate every pre-load boundary and return a model-free execution plan."""
    try:
        validate_auto_dossier(dossier, protocol_sha256=protocol_sha256)
    except Exp002AutoContractError as exc:
        raise Exp002AutoMaterialError(str(exc)) from exc
    if dossier.get("status") != "authorized":
        raise Exp002AutoMaterialError("AUTO material dossier is not authorized")
    if dossier.get("schedule_sha256") != schedule_sha256 or dossier.get("input_manifest_sha256") != input_manifest_sha256:
        raise Exp002AutoMaterialError("AUTO schedule or input manifest hash drift")
    if not _gate_ok(gate):
        raise Exp002AutoMaterialError("CCP gate must be Admit with inactive empty admission")
    if EXPECTED_MODELS.get(model_id) is None or EXPECTED_MODELS[model_id] != next((item.get("revision") for item in dossier["exact_models"] if item.get("model_id") == model_id), None):
        raise Exp002AutoMaterialError("model identity is not frozen in the dossier")
    shards = dossier.get("shards")
    if not isinstance(shards, Sequence) or not any(isinstance(item, Mapping) and item.get("stage_id") == stage_id and item.get("shard_id") == shard_id for item in shards):
        raise Exp002AutoMaterialError("AUTO shard is not frozen in the dossier")
    revision = EXPECTED_MODELS[model_id]
    runtime = verify_runtime_receipt(receipt=runtime_receipt, model_id=model_id, revision=revision, model_root=model_root)
    return {"protocol_id": PROTOCOL_ID, "model_id": model_id, "revision": revision, "stage_id": stage_id, "shard_id": shard_id, "runtime": runtime}


def _validate_public_row(row: Mapping[str, Any]) -> None:
    if not isinstance(row, Mapping) or not isinstance(row.get("record_id"), str) or not row["record_id"].strip():
        raise Exp002AutoMaterialError("AUTO public row identity is malformed")
    if any(field in row for field in _FORBIDDEN):
        raise Exp002AutoMaterialError("AUTO scorer received target material")


def _score_rows(rows: Sequence[Mapping[str, Any]], adapter: Any) -> list[dict[str, Any]]:
    if isinstance(rows, (str, bytes, bytearray)) or not isinstance(rows, Sequence) or not rows:
        raise Exp002AutoMaterialError("AUTO public rows must be non-empty")
    output: list[dict[str, Any]] = []
    for row in rows:
        _validate_public_row(row)
        prompt = row.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise Exp002AutoMaterialError("AUTO public prompt is missing")
        candidates = row.get("candidate_descriptions")
        if candidates is not None:
            if isinstance(candidates, (str, bytes, bytearray)) or not isinstance(candidates, Sequence) or len(candidates) != 4:
                raise Exp002AutoMaterialError("AUTO candidates are malformed")
            scorer = getattr(adapter, "score_candidate_description", None)
            if not callable(scorer):
                raise Exp002AutoMaterialError("adapter lacks candidate-description scoring")
            scores = [float(scorer(prompt, candidate)) for candidate in candidates]
            if any(not (value == value and abs(value) != float("inf")) for value in scores):
                raise Exp002AutoMaterialError("AUTO candidate score is non-finite")
            output.append({"record_id": row["record_id"], "family": row.get("family"), "domain": row.get("domain"), "candidate_scores": scores})
        else:
            scorer = getattr(adapter, "score_prompt_choice", None)
            if not callable(scorer):
                raise Exp002AutoMaterialError("adapter lacks label scoring")
            scores = {label: float(scorer(prompt, label)) for label in ("A", "B", "C", "D")}
            if any(not (value == value and abs(value) != float("inf")) for value in scores.values()):
                raise Exp002AutoMaterialError("AUTO label score is non-finite")
            output.append({"record_id": row["record_id"], "condition": row.get("condition"), "scores": scores})
    return output


def run_auto_shard(
    *, root: str | Path, run_id: str, plan: Mapping[str, Any], public_rows: Sequence[Mapping[str, Any]],
    adapter_factory: Callable[[], Any], analysis: Callable[[Sequence[Mapping[str, Any]], Callable[[], Mapping[str, Any]]], Mapping[str, Any]],
    key_reader: Callable[[], Mapping[str, Any]], resource_probe: Callable[[], Mapping[str, Any]] | None = None,
    clock: Callable[[], float] | None = None,
) -> dict[str, Any]:
    """Load one injected adapter, score once, read the sealed key once, publish terminal output."""
    if not isinstance(plan, Mapping) or plan.get("protocol_id") != PROTOCOL_ID:
        raise Exp002AutoMaterialError("material execution plan is missing")
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise Exp002AutoMaterialError("run_id must use the exp002-auto namespace")
    repo = Path(root).resolve()
    model_key = _model_key(str(plan["model_id"]))
    package = repo / "results/exp002-auto" / model_key / run_id
    external = repo / "artifacts/exp002-auto" / model_key / run_id / "score-asset.json"
    if package.exists() or external.exists():
        raise Exp002AutoMaterialError("AUTO run package already exists")
    now = clock or time.monotonic
    started = now()
    access: dict[str, Any] = {"model_loaded": False, "model_output_accessed": False, "sealed_target_accessed": False, "target_reads": 0}
    scored: list[dict[str, Any]] = []
    analysis_result: Mapping[str, Any] = {"status": "failed", "reason": "not_started"}
    failure: dict[str, str] | None = None
    try:
        adapter = adapter_factory()
        access["model_loaded"] = True
        scored = _score_rows(public_rows, adapter)
        access["model_output_accessed"] = True
        reads = 0

        def one_shot_reader() -> Mapping[str, Any]:
            nonlocal reads
            if reads != 0:
                raise Exp002AutoMaterialError("sealed target reader invoked more than once")
            reads = 1
            access["target_reads"] = 1
            access["sealed_target_accessed"] = "possibly_accessed"
            value = key_reader()
            access["sealed_target_accessed"] = True
            return value

        analysis_result = analysis(scored, one_shot_reader)
        if reads != 1:
            raise Exp002AutoMaterialError("analysis did not perform exactly one sealed-target read")
    except Exception as exc:
        failure = {"kind": type(exc).__name__, "digest": _sha_bytes(f"{type(exc).__name__}:{exc}".encode())}
    terminal = analysis_result.get("status") if isinstance(analysis_result, Mapping) else None
    if terminal not in TERMINAL_STATUSES or failure is not None:
        terminal = "failed"
    resources = dict(resource_probe() if resource_probe else {})
    wall = float(resources.get("wall_seconds", now() - started))
    rss = int(resources.get("peak_rss_bytes", 0))
    external_payload = {"artifact_class": "exp002-auto-score-asset", "protocol_id": PROTOCOL_ID, "model_id": plan["model_id"], "revision": plan["revision"], "stage_id": plan["stage_id"], "shard_id": plan["shard_id"], "records": scored}
    dense = max(int(resources.get("new_dense_output_bytes", 0)), len(_stable(external_payload)))
    if wall > MAX_WALL_SECONDS or rss > MAX_RSS_BYTES or dense > MAX_DENSE_BYTES:
        terminal = "failed"
        failure = {"kind": "ResourceCeilingExceeded", "digest": _sha_bytes(f"{wall}:{rss}:{dense}".encode())}
    _write_new(external, external_payload)
    receipt = {"artifact_class": "exp002-auto-execution-receipt", "protocol_id": PROTOCOL_ID, "run_id": run_id, "model_id": plan["model_id"], "revision": plan["revision"], "status": terminal, "execution": {"device": "cpu", "dtype": "float32", "network": False, "generation": False, "run_count": 1, "wall_seconds": wall, "peak_rss_bytes": rss, "new_score_output_bytes": dense}, "access": access, "scientific_status": "exploratory", "evidence_eligible": False, "expert_validated": False, "claim_ids": [], "external_score_asset": {"locator": external.relative_to(repo).as_posix(), "sha256": _sha_bytes(_stable(external_payload))} }
    package.mkdir(parents=True)
    _write_new(package / "execution-receipt.json", receipt)
    _write_new(package / "statistical-result.json", {"artifact_class": "exp002-auto-result", "protocol_id": PROTOCOL_ID, "run_id": run_id, "model_id": plan["model_id"], "revision": plan["revision"], "status": terminal, "analysis": dict(analysis_result), "failure": failure, "scientific_status": "exploratory", "evidence_eligible": False, "expert_validated": False, "claim_ids": []})
    _write_new(package / "representation-index.json", {"artifact_class": "exp002-auto-representation-index", "protocol_id": PROTOCOL_ID, "model_id": plan["model_id"], "revision": plan["revision"], "record_count": len(scored), "asset": receipt["external_score_asset"]})
    _write_new(package / "sealed-key-access.json", {"artifact_class": "exp002-auto-sealed-key-access", "status": "accessed" if access["sealed_target_accessed"] is True else access["sealed_target_accessed"], "target_reads": access["target_reads"], "sealed_target_accessed": access["sealed_target_accessed"]})
    _write_new(package / "recovery-observation.json", {"artifact_class": "exp002-auto-recovery-observation", "terminal_status": terminal, "retry_performed": False, "cleanup_status": "not_applicable"})
    _write_new(package / "report.md", f"# EXP-002-AUTO {plan['model_id']} / {plan['shard_id']}\n\nTerminal status: `{terminal}`.\n\nExploratory automated-proxy output; no general TRIZ claim.\n")
    names = ("execution-receipt.json", "statistical-result.json", "representation-index.json", "sealed-key-access.json", "recovery-observation.json", "report.md")
    bindings = {name: {"path": (package / name).relative_to(repo).as_posix(), "sha256": _sha_bytes((package / name).read_bytes())} for name in names}
    _write_new(package / "publication-manifest.json", {"artifact_class": "exp002-auto-publication-manifest", "protocol_id": PROTOCOL_ID, "status": "published", "packages": [{"model_id": plan["model_id"], "revision": plan["revision"], "terminal_status": terminal, "package_locator": package.relative_to(repo).as_posix()}], "external_score_assets": [receipt["external_score_asset"]], "bindings": bindings, "scientific_status": "exploratory", "claim_ids": [], "evidence_eligible": False, "expert_validated": False})
    return {"status": terminal, "package": package.relative_to(repo).as_posix(), "receipt": receipt, "failure": failure}


def run_authorized_auto_shard(
    *, root: str | Path, run_id: str, dossier: Mapping[str, Any], protocol_sha256: str,
    schedule_sha256: str, input_manifest_sha256: str, gate: Mapping[str, Any], model_id: str,
    stage_id: str, shard_id: str, runtime_receipt: Mapping[str, Any], model_root: str | Path,
    public_rows: Sequence[Mapping[str, Any]], adapter_factory: Callable[[], Any],
    analysis: Callable[[Sequence[Mapping[str, Any]], Callable[[], Mapping[str, Any]]], Mapping[str, Any]],
    key_reader: Callable[[], Mapping[str, Any]], resource_probe: Callable[[], Mapping[str, Any]] | None = None,
    clock: Callable[[], float] | None = None,
) -> dict[str, Any]:
    """Preflight first, then construct the injected adapter exactly once."""
    plan = prepare_auto_shard(
        dossier=dossier, protocol_sha256=protocol_sha256, schedule_sha256=schedule_sha256,
        input_manifest_sha256=input_manifest_sha256, gate=gate, model_id=model_id,
        stage_id=stage_id, shard_id=shard_id, runtime_receipt=runtime_receipt, model_root=model_root,
    )
    return run_auto_shard(
        root=root, run_id=run_id, plan=plan, public_rows=public_rows,
        adapter_factory=adapter_factory, analysis=analysis, key_reader=key_reader,
        resource_probe=resource_probe, clock=clock,
    )


__all__ = ["Exp002AutoMaterialError", "MAX_DENSE_BYTES", "MAX_RSS_BYTES", "MAX_WALL_SECONDS", "prepare_auto_shard", "run_authorized_auto_shard", "run_auto_shard", "sha256_file", "verify_runtime_receipt"]
