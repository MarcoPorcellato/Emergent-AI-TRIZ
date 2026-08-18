"""Fail-closed builder for the R3 no-model freeze manifest."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .exp001_r3_contract import Exp001ContractError, verify_contract
from .exp001_r3_implementation import Exp001ImplementationError, verify_implementation_binding
from .validator import validate

PROTOCOL_ID = "exp001-reference-integrated-r3-v1.0.0"
MODEL_ID = "HuggingFaceTB/SmolLM2-360M"
REVISION = "f8027fd0eaeea54caa13c31d31b9fdc459c38b49"
PROTOCOL = Path("experiments/exp001-reference-integrated/protocol.json")
IMPLEMENTATION = Path("experiments/exp001-reference-integrated/implementation.json")
ANALYSIS_PLAN = Path("experiments/exp001-reference-integrated/analysis-plan.json")
FIXTURES = tuple(Path("experiments/exp001-reference-integrated") / rel for rel in ("fixtures/items.jsonl", "fixtures/matrix-cells.jsonl", "fixtures/tool-edges.jsonl", "fixtures/source-exposures.jsonl", "fixtures/control-plan.json", "fixtures/option-sets.jsonl", "fixtures/split-receipt.json", "fixtures/primary-units.jsonl"))
SOURCES = tuple(Path(rel) for rel in ("data/triz-reference-sources.json", "data/triz-reference/principles.jsonl", "data/triz-consulting-web-corpus.json", "docs/reference/triz-reference-corpus.md"))
INTEGRITY = Path("results/a0r2/preexecution/smollm2-360m-f8027fd0/integrity-receipt.json")
FEASIBILITY = Path("results/a0r2/preexecution/smollm2-360m-f8027fd0/feasibility-receipt.json")
SCHEMA = Path("schemas/exp001-r3-freeze-manifest.schema.json")


class Exp001FreezeError(ValueError):
    """Raised for an incomplete or drifting no-model freeze."""


def _artifact(root: Path, relative: Path) -> dict[str, Any]:
    if relative.is_absolute() or ".." in relative.parts:
        raise Exp001FreezeError(f"unsafe freeze path: {relative}")
    path = (root / relative).resolve()
    if not path.is_file() or not path.is_relative_to(root) or (root / relative).is_symlink():
        raise Exp001FreezeError(f"missing or unsafe freeze path: {relative}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"path": relative.as_posix(), "sha256": digest, "size": path.stat().st_size}


def build_freeze_manifest(root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    try:
        contract = verify_contract(repository)
    except Exp001ContractError as exc:
        raise Exp001FreezeError("R3 contract does not verify") from exc
    protocol_path = repository / PROTOCOL
    try:
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Exp001FreezeError("protocol unavailable") from exc
    if protocol.get("protocol_id") != PROTOCOL_ID or protocol.get("protocol_status") != "frozen":
        raise Exp001FreezeError("protocol must be frozen before freeze manifest")
    implementation_path = repository / IMPLEMENTATION
    try:
        implementation = json.loads(implementation_path.read_text(encoding="utf-8"))
        verify_implementation_binding(repository, implementation)
    except (OSError, json.JSONDecodeError, Exp001ImplementationError) as exc:
        raise Exp001FreezeError("implementation binding does not verify") from exc
    return {
        "artifact_class": "exp001-r3-freeze-manifest", "protocol_id": PROTOCOL_ID,
        "status": "frozen", "protocol_status": "frozen",
        "protocol": _artifact(repository, PROTOCOL), "implementation": _artifact(repository, IMPLEMENTATION),
        "analysis_plan": _artifact(repository, ANALYSIS_PLAN),
        "fixtures": [_artifact(repository, path) for path in FIXTURES],
        "sources": [_artifact(repository, path) for path in SOURCES],
        "model": {"id": MODEL_ID, "revision": REVISION, "integrity_receipt": _artifact(repository, INTEGRITY), "feasibility_receipt": _artifact(repository, FEASIBILITY)},
        "inventory": {"primary_records": 72, "secondary_records": 13, "combined_records": 85, "score_calls": 340},
        "access": {"model_loaded": False, "model_output_accessed": "not_accessed", "sealed_targets_accessed": "not_accessed", "target_reads": 0},
        "policies": {"network_access": False, "generation": False, "sealed_target_reads": "forbidden_before_explicit_authorization", "no_model_output": True},
    }


def verify_freeze_manifest(root: str | Path, manifest: dict[str, Any]) -> dict[str, Any]:
    repository = Path(root).resolve()
    schema = json.loads((repository / SCHEMA).read_text(encoding="utf-8"))
    issues = validate(manifest, schema)
    if issues:
        raise Exp001FreezeError(issues[0].message)
    expected = build_freeze_manifest(repository)
    for field in ("protocol", "implementation", "analysis_plan", "fixtures", "sources", "model", "inventory", "access", "policies"):
        if manifest[field] != expected[field]:
            raise Exp001FreezeError(f"freeze manifest drift: {field}")
    return {"status": "verified", "combined_records": 85, "model_or_target_accessed": False}


def write_freeze_manifest(root: str | Path, output: str | Path = "results/exp001-r3/freeze-manifest.json") -> dict[str, Any]:
    repository = Path(root).resolve()
    relative = Path(output)
    if relative.is_absolute() or ".." in relative.parts:
        raise Exp001FreezeError("unsafe freeze manifest path")
    destination = repository / relative
    if destination.exists():
        raise Exp001FreezeError("refuse overwrite: freeze manifest exists")
    manifest = build_freeze_manifest(repository)
    verify_freeze_manifest(repository, manifest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=destination.parent, prefix=".r3-freeze-", delete=False) as stream:
            stream.write(payload)
            temporary = Path(stream.name)
        os.link(temporary, destination)
    except FileExistsError as exc:
        raise Exp001FreezeError("refuse overwrite: freeze manifest exists") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return manifest


__all__ = ["Exp001FreezeError", "build_freeze_manifest", "verify_freeze_manifest", "write_freeze_manifest"]
