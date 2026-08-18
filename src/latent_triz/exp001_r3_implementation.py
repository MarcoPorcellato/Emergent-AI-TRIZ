"""Deterministic, no-model binding for the EXP-001 R3 implementation.

The binding is deliberately a data object rather than an execution receipt.  It
binds the source tree, public fixtures, acquired-model receipts and frozen
resource policy before an operator can authorize a material run.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .validator import validate


class Exp001ImplementationError(ValueError):
    """Raised when an implementation binding is missing or has drifted."""


PROTOCOL_ID = "exp001-reference-integrated-r3-v1.0.0"
MODEL_ID = "HuggingFaceTB/SmolLM2-360M"
MODEL_REVISION = "f8027fd0eaeea54caa13c31d31b9fdc459c38b49"
CODE_PATHS = tuple(
    f"src/latent_triz/{name}.py"
    for name in (
        "exp001_r3_analysis", "exp001_r3_contract", "exp001_r3_execution",
        "exp001_r3_fixture_builder", "exp001_r3_model_adapter",
        "exp001_r3_primary_fixture", "exp001_r3_response_adapter",
        "exp001_r3_response_execution", "exp001_r3_runner",
        "exp001_r3_secondary_fixture", "exp001_r3_target_key",
        "exp001_r3_implementation", "exp001_r3_authorization", "exp001_r3_freeze", "exp001_r3_report", "exp001_r3_material_runner",
    )
)
FIXTURE_PATHS = (
    "experiments/exp001-reference-integrated/protocol.json",
    "experiments/exp001-reference-integrated/analysis-plan.json",
    "experiments/exp001-reference-integrated/fixtures/primary-units.jsonl",
    "experiments/exp001-reference-integrated/fixtures/matrix-cells.jsonl",
    "experiments/exp001-reference-integrated/fixtures/tool-edges.jsonl",
)
SOURCE_PATHS = (
    "data/triz-reference-sources.json",
    "data/triz-reference/principles.jsonl",
    "data/triz-consulting-web-corpus.json",
    "docs/reference/triz-reference-corpus.md",
)
RECEIPT_PATHS = (
    "results/a0r2/preexecution/smollm2-360m-f8027fd0/integrity-receipt.json",
    "results/a0r2/preexecution/smollm2-360m-f8027fd0/feasibility-receipt.json",
)
PROTOCOL_PATH = "experiments/exp001-reference-integrated/protocol.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _entry(repo: Path, relative: str) -> dict[str, Any]:
    path = repo / relative
    if path.is_symlink() or not path.is_file():
        raise Exp001ImplementationError(f"missing or symlinked binding path: {relative}")
    return {"path": relative, "sha256": _sha(path), "size": path.stat().st_size}


def _entries(repo: Path, paths: tuple[str, ...]) -> list[dict[str, Any]]:
    return [_entry(repo, relative) for relative in paths]


def build_implementation_binding(repo: str | Path) -> dict[str, Any]:
    """Build a canonical binding from the current no-model source tree."""
    root = Path(repo).resolve()
    try:
        protocol = json.loads((root / PROTOCOL_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Exp001ImplementationError("protocol unavailable for implementation binding") from exc
    if protocol.get("protocol_id") != PROTOCOL_ID:
        raise Exp001ImplementationError("protocol identity mismatch")
    protocol_status = protocol.get("protocol_status")
    if protocol_status not in {"ready_for_review", "frozen", "approval_requested", "authorized"}:
        raise Exp001ImplementationError("invalid protocol status")
    return {
        "artifact_class": "exp001-r3-implementation-binding",
        "implementation_id": "exp001-reference-integrated-r3-v1.0.0-impl",
        "protocol_id": PROTOCOL_ID,
        "protocol_status": protocol_status,
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "model": {"name": MODEL_ID, "revision": MODEL_REVISION, "local_only": True},
        "code_sha256": _entries(root, CODE_PATHS),
        "fixture_sha256": _entries(root, FIXTURE_PATHS),
        "source_sha256": _entries(root, SOURCE_PATHS),
        "receipt_sha256": _entries(root, RECEIPT_PATHS),
        "inventory": {"primary_records": 72, "secondary_records": 13, "combined_records": 85,
                      "teacher_forced_labels_per_record": 4, "score_calls": 340},
        "limits": {"wall_time_seconds": 1800, "peak_rss_bytes": 8589934592,
                   "new_dense_output_bytes": 134217728},
        "policies": {"network_access": False, "generation": False,
                     "single_run": True, "sealed_target_read_boundary": "analysis_only",
                     "retry_after_model_or_target_access": False,
                     "model_substitution": False, "protocol_mutation": False,
                     "publish_every_terminal_outcome": True, "general_triz_claim": False},
    }


def verify_implementation_binding(repo: str | Path, binding: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on schema, identity, inventory, policy, or file drift."""
    root = Path(repo).resolve()
    schema_path = root / "schemas/exp001-r3-implementation.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Exp001ImplementationError("implementation schema unavailable") from exc
    issues = validate(binding, schema)
    if issues:
        raise Exp001ImplementationError(issues[0].message)
    if binding["protocol_id"] != PROTOCOL_ID or binding["model"] != {"name": MODEL_ID, "revision": MODEL_REVISION, "local_only": True}:
        raise Exp001ImplementationError("protocol or model identity mismatch")
    if binding["protocol_status"] not in {"ready_for_review", "frozen", "approval_requested", "authorized"}:
        raise Exp001ImplementationError("invalid protocol status")
    expected = build_implementation_binding(root)
    for field in ("code_sha256", "fixture_sha256", "source_sha256", "receipt_sha256", "inventory", "limits", "policies"):
        if binding[field] != expected[field]:
            raise Exp001ImplementationError(f"implementation binding drift: {field}")
    return {"status": "verified", "implementation_id": binding["implementation_id"],
            "code_files": len(binding["code_sha256"]), "combined_records": 85,
            "score_calls": 340}


def write_implementation_binding(repo: str | Path, output: str | Path = "experiments/exp001-reference-integrated/implementation.json") -> dict[str, Any]:
    """Persist one verified binding atomically and refuse to overwrite it."""
    root = Path(repo).resolve()
    relative = Path(output)
    if relative.is_absolute() or ".." in relative.parts:
        raise Exp001ImplementationError("unsafe implementation binding path")
    destination = root / relative
    if destination.exists():
        raise Exp001ImplementationError("refuse overwrite: implementation binding exists")
    binding = build_implementation_binding(root)
    verify_implementation_binding(root, binding)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(binding, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=destination.parent, prefix=".implementation-", delete=False) as stream:
            stream.write(payload)
            temporary = Path(stream.name)
        os.link(temporary, destination)
    except FileExistsError as exc:
        raise Exp001ImplementationError("refuse overwrite: implementation binding exists") from exc
    except OSError as exc:
        raise Exp001ImplementationError("cannot persist implementation binding") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return binding


validate_implementation_binding = verify_implementation_binding
