"""No-model execution preflight for EXP-001 R3.

The preflight is an authorization and provenance boundary only.  It imports
no ML runtime, never resolves the acquired model directory, and never opens a
sealed target.  A material runner must perform a separate, explicitly
authorized transition after this function succeeds.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .exp001_r3_contract import Exp001ContractError, verify_contract
from .exp001_r3_primary_fixture import Exp001PrimaryFixtureError, build_primary_records
from .exp001_r3_secondary_fixture import Exp001SecondaryFixtureError, build_secondary_records


class Exp001ExecutionPreflightError(ValueError):
    """Raised when R3 is not frozen, authorized, or provenance-complete."""


MODEL_ID = "HuggingFaceTB/SmolLM2-360M"
MODEL_REVISION = "f8027fd0eaeea54caa13c31d31b9fdc459c38b49"
INTEGRITY_RECEIPT = "results/a0r2/preexecution/smollm2-360m-f8027fd0/integrity-receipt.json"
FEASIBILITY_RECEIPT = "results/a0r2/preexecution/smollm2-360m-f8027fd0/feasibility-receipt.json"
PROTOCOL = "experiments/exp001-reference-integrated/protocol.json"
PRIMARY_UNITS = "experiments/exp001-reference-integrated/fixtures/primary-units.jsonl"
MATRIX_CELLS = "experiments/exp001-reference-integrated/fixtures/matrix-cells.jsonl"
TOOL_EDGES = "experiments/exp001-reference-integrated/fixtures/tool-edges.jsonl"


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Exp001ExecutionPreflightError(f"invalid or missing JSON receipt: {relative}") from exc
    if not isinstance(value, dict):
        raise Exp001ExecutionPreflightError(f"receipt is not a JSON object: {relative}")
    return value


def _read_jsonl(root: Path, relative: str, *, label: str = "fixture") -> list[dict[str, Any]]:
    path = root / relative
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise Exp001ExecutionPreflightError(f"missing {label}: {relative}") from exc
    values: list[dict[str, Any]] = []
    try:
        for line in lines:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError
                values.append(value)
    except (ValueError, json.JSONDecodeError) as exc:
        raise Exp001ExecutionPreflightError(f"invalid {label}: {relative}") from exc
    return values


def _identity(receipt: Mapping[str, Any], label: str) -> None:
    model = receipt.get("model")
    if not isinstance(model, Mapping):
        raise Exp001ExecutionPreflightError(f"{label} has no model identity")
    if model.get("id") != MODEL_ID or model.get("revision") != MODEL_REVISION:
        raise Exp001ExecutionPreflightError(f"{label} model identity mismatch")


def _check_receipts(root: Path) -> None:
    integrity = _read_json(root, INTEGRITY_RECEIPT)
    if integrity.get("status") != "pass" or integrity.get("integrity_status") != "integrity_verified":
        raise Exp001ExecutionPreflightError("A0-R2 integrity receipt is not a verified pass")
    _identity(integrity, "integrity receipt")

    feasibility = _read_json(root, FEASIBILITY_RECEIPT)
    if feasibility.get("status") != "compatible" or feasibility.get("compatibility", {}).get("compatible") is not True:
        raise Exp001ExecutionPreflightError("A0-R2 feasibility receipt is not compatible")
    _identity(feasibility, "feasibility receipt")


def preflight(root: str | Path, authorization: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the frozen R3 boundary without loading a model or target.

    ``authorization`` is intentionally supplied by the caller rather than
    read from disk: the material run requires a fresh operator authorization.
    Only the exact one-run SmolLM2 authorization is accepted.
    """
    repo = Path(root).resolve()
    try:
        summary = verify_contract(repo)
    except Exp001ContractError as exc:
        raise Exp001ExecutionPreflightError("R3 contract verification failed") from exc

    protocol = _read_json(repo, PROTOCOL)
    if protocol.get("protocol_status") != "frozen":
        raise Exp001ExecutionPreflightError("R3 protocol must be exactly frozen before execution")

    units = _read_jsonl(repo, PRIMARY_UNITS, label="primary fixture")
    try:
        records = build_primary_records(units)
    except Exp001PrimaryFixtureError as exc:
        raise Exp001ExecutionPreflightError("primary fixture expansion failed") from exc
    if len(records) != 72:
        raise Exp001ExecutionPreflightError("primary fixture must expand to exactly 72 records")

    matrix_cells = _read_jsonl(repo, MATRIX_CELLS, label="Matrix fixture")
    tool_edges = _read_jsonl(repo, TOOL_EDGES, label="Panitz fixture")
    try:
        secondary_records = build_secondary_records(matrix_cells, tool_edges)
    except Exp001SecondaryFixtureError as exc:
        raise Exp001ExecutionPreflightError("secondary fixture expansion failed") from exc
    if len(secondary_records) != 13 or len(records) + len(secondary_records) != 85:
        raise Exp001ExecutionPreflightError("combined fixture inventory must contain exactly 85 records")

    if not isinstance(authorization, Mapping):
        raise Exp001ExecutionPreflightError("authorization must be a mapping")
    if (authorization.get("status") != "authorized"
            or authorization.get("model_id") != MODEL_ID
            or authorization.get("revision") != MODEL_REVISION
            or authorization.get("one_run") is not True):
        raise Exp001ExecutionPreflightError("authorization is not the exact one-run SmolLM2 authorization")

    _check_receipts(repo)
    return {
        "status": "ready_for_material_execution",
        "protocol_status": "frozen",
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "primary_records": len(records),
        "matrix_cells": len(matrix_cells),
        "tool_edges": len(tool_edges),
        "secondary_records": len(secondary_records),
        "total_records": len(records) + len(secondary_records),
        "contract": summary,
        "model_or_target_accessed": False,
    }


verify_execution_preflight = preflight
