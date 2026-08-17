"""Fail-closed, no-model integrity checks for EXP-001 R3.

This module intentionally has no ML/runtime imports.  It validates only the
source and fixture boundary; model and sealed-target paths are rejected.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .validator import validate
from .exp001_r3_fixture_builder import FixtureBuilderError, build_public_record_stubs
from .exp001_r3_primary_fixture import Exp001PrimaryFixtureError, build_primary_records


class Exp001ContractError(ValueError):
    """Raised when an EXP-001 input is absent, stale, unsafe, or inconsistent."""


_HASHES = {
    "data/triz-reference-sources.json": "a3bd9283b7e73ebd723bcfab8edb9599161e37a47686b6c25e652158d2158273",
    "data/triz-reference/principles.jsonl": "7baa3b74f7a5ee7ca5fe9303baf64361a5cbcdfea0cb0c539e00bb74db764249",
    "data/triz-consulting-web-corpus.json": "e397160adfc60c534d16b5cd934deddb3e3500bb8f99f7fef26a2b6d4c2eff46",
    "docs/reference/triz-reference-corpus.md": "92429183119e463090df170f4ec29bf0f0e43ee531f47898c8071325a3b7435f",
}
_FIXTURES = {
    "items": "fixtures/items.jsonl",
    "matrix_cells": "fixtures/matrix-cells.jsonl",
    "tool_edges": "fixtures/tool-edges.jsonl",
    "source_exposures": "fixtures/source-exposures.jsonl",
    "control_plan": "fixtures/control-plan.json",
    "option_sets": "fixtures/option-sets.jsonl",
    "split_receipt": "fixtures/split-receipt.json",
    "analysis_plan": "analysis-plan.json",
    "primary_units": "fixtures/primary-units.jsonl",
}
_SCHEMAS = {
    "items": "exp001-r3-item.schema.json",
    "matrix_cells": "exp001-r3-matrix-cell.schema.json",
    "tool_edges": "exp001-r3-tool-edge.schema.json",
    "source_exposures": "exp001-r3-source-exposure.schema.json",
    "control_plan": "exp001-r3-control-plan.schema.json",
    "option_sets": "exp001-r3-option-set.schema.json",
    "split_receipt": "exp001-r3-split-receipt.schema.json",
    "analysis_plan": "exp001-r3-analysis-plan.schema.json",
    "primary_units": "exp001-r3-primary-unit.schema.json",
}


def _safe(root: Path, relative: str, *, experiment: Path | None = None) -> Path:
    """Resolve a repository-relative path, rejecting escapes and symlinks."""
    p = Path(relative)
    if p.is_absolute() or ".." in p.parts:
        raise Exp001ContractError(f"unsafe relative path: {relative}")
    candidate = root / p
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise Exp001ContractError(f"missing path: {relative}") from exc
    boundary = (experiment or root).resolve()
    if experiment is not None and boundary not in resolved.parents:
        raise Exp001ContractError(f"fixture outside experiment directory: {relative}")
    if experiment is None and root.resolve() not in resolved.parents:
        raise Exp001ContractError(f"path outside repository: {relative}")
    if candidate.is_symlink():
        raise Exp001ContractError(f"symlink is not permitted: {relative}")
    return resolved


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise Exp001ContractError(f"invalid JSONL {path}:{number}") from exc
        if not isinstance(value, dict):
            raise Exp001ContractError(f"JSONL record is not an object: {path}:{number}")
        records.append(value)
    return records


def _schema_check(root: Path, records: list[dict[str, Any]], schema_name: str) -> None:
    schema_path = _safe(root, f"schemas/{schema_name}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    # Use the repository's deliberately restricted validator, not a permissive
    # runtime validator, so unsupported schema features fail closed.
    for index, record in enumerate(records):
        issues = validate(record, schema)
        if issues:
            raise Exp001ContractError(f"schema failure {schema_name}[{index}]: {issues[0].message}")


def verify_contract(root: str | Path) -> dict[str, Any]:
    """Verify the complete no-model R3 contract and return an audit summary."""
    repo = Path(root).resolve()
    experiment = _safe(repo, "experiments/exp001-reference-integrated")
    protocol_path = _safe(repo, "experiments/exp001-reference-integrated/protocol.json", experiment=repo)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("protocol_status") not in {"ready_for_review", "frozen", "approval_requested", "authorized"}:
        raise Exp001ContractError("protocol is not in a reviewable state")
    declared = protocol.get("fixture_inputs", {})
    for name, expected in _FIXTURES.items():
        if declared.get(name) != expected:
            raise Exp001ContractError(f"unsafe or unexpected declared fixture path: {name}")
    paths = {}
    for rel, expected in _HASHES.items():
        path = _safe(repo, rel)
        actual = _sha(path)
        if actual != expected:
            raise Exp001ContractError(f"hash mismatch: {rel}")
        paths[rel] = actual
    principles = _jsonl(_safe(repo, "data/triz-reference/principles.jsonl"))
    if len(principles) != 40 or sorted(p.get("principle_number") for p in principles) != list(range(1, 41)):
        raise Exp001ContractError("principle fixture must contain exactly one record for 1..40")
    for p in principles:
        if p.get("automatic_ground_truth") is not False:
            raise Exp001ContractError("principles cannot be automatic ground truth")
    web = json.loads(_safe(repo, "data/triz-consulting-web-corpus.json").read_text(encoding="utf-8"))
    resources = web.get("resources", web.get("sources", []))
    if len(resources) != 18:
        raise Exp001ContractError("web corpus must contain exactly 18 resources")

    loaded: dict[str, list[dict[str, Any]]] = {}
    for name, rel in _FIXTURES.items():
        path = _safe(experiment, rel, experiment=experiment)
        if name in {"control_plan", "split_receipt", "analysis_plan"}:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise Exp001ContractError("control plan must be an object")
            loaded[name] = [value]
        else:
            loaded[name] = _jsonl(path)
        _schema_check(repo, loaded[name], _SCHEMAS[name])
    items = loaded["items"]
    by_id = {i["item_id"]: i for i in items}
    if len(by_id) != len(items):
        raise Exp001ContractError("duplicate item_id")
    blinded = {i["item_id"] for i in items if i["stratum"] == "TRIZ-blinded-transfer"}
    exposed = {i["item_id"] for i in items if i["stratum"] == "source-exposed-competence"}
    for item_id in blinded:
        counterpart = item_id.rsplit("-", 1)[0] + "-exposed"
        if counterpart not in exposed:
            raise Exp001ContractError(f"unpaired blinded item: {item_id}")
        if not by_id[item_id]["split"]["pooling_prohibited"] or not by_id[counterpart]["split"]["pooling_prohibited"]:
            raise Exp001ContractError("strata pooling is prohibited")
    for item_id in exposed:
        counterpart = item_id.rsplit("-", 1)[0] + "-blinded"
        if counterpart not in blinded:
            raise Exp001ContractError(f"unpaired exposed item: {item_id}")
    for edge in loaded["tool_edges"]:
        if edge["edge_status"] != "supported" and edge["selection_allowed"]:
            raise Exp001ContractError("unsupported Panitz edge is selectable")
    for cell in loaded["matrix_cells"]:
        receipts = cell["transcription_receipts"]
        if len({r["normalized_cell_sha256"] for r in receipts}) != 1:
            raise Exp001ContractError(f"Matrix visual receipts disagree: {cell['cell_id']}")
        if cell["direction"] != "improving_row_worsening_column":
            raise Exp001ContractError("Matrix reverse direction is not permitted")
    control_plan = loaded["control_plan"][0]
    pairs = control_plan.get("pairs")
    if control_plan.get("target_values_present") is not False or not isinstance(pairs, list) or len(pairs) != 10:
        raise Exp001ContractError("control plan is not the exact no-target ten-pair inventory")
    kinds = {str(pair.get("control_kind")) for pair in pairs if isinstance(pair, dict)}
    required_kinds = {"primary", "lexical_matched", "principle_near_neighbour", "matrix_direction_swap", "matrix_non_recommended_option", "tool_edge_unsupported", "explicit_abstention"}
    if not required_kinds.issubset(kinds):
        raise Exp001ContractError("control plan omits a required control")
    split_receipt = loaded["split_receipt"][0]
    if split_receipt.get("target_values_present") is not False:
        raise Exp001ContractError("split receipt cannot contain target values")
    receipt_pairs = split_receipt.get("bindings")
    if not isinstance(receipt_pairs, list) or {
        pair.get("pair_id") for pair in receipt_pairs if isinstance(pair, dict)
    } != {pair.get("pair_id") for pair in pairs if isinstance(pair, dict)}:
        raise Exp001ContractError("split receipt must bind exactly the control-plan pairs")
    if any(binding.get("pooling_prohibited") is not True for binding in receipt_pairs if isinstance(binding, dict)):
        raise Exp001ContractError("split receipt must prohibit pooling for every pair")
    try:
        stubs = build_public_record_stubs(
            _safe(experiment, _FIXTURES["control_plan"], experiment=experiment),
            _safe(experiment, _FIXTURES["option_sets"], experiment=experiment),
        )
    except FixtureBuilderError as exc:
        raise Exp001ContractError("public fixture stubs are not constructible") from exc
    if len(stubs) != 20 or any(not record["pooling_prohibited"] for record in stubs):
        raise Exp001ContractError("public fixture stubs violate the non-pooling contract")
    analysis_plan = loaded["analysis_plan"][0]
    primary = analysis_plan.get("primary")
    if not isinstance(primary, dict) or primary.get("required_units") != 24:
        raise Exp001ContractError("analysis plan must require the full primary inventory")
    if primary.get("permutation_count") != 64 or primary.get("alpha") != 0.05:
        raise Exp001ContractError("analysis plan must preserve the exact primary test")
    if analysis_plan.get("target_values_present") is not False:
        raise Exp001ContractError("analysis plan cannot contain target values")
    try:
        primary_records = build_primary_records(loaded["primary_units"])
    except Exp001PrimaryFixtureError as exc:
        raise Exp001ContractError("primary-unit inventory is not constructible") from exc
    if len(primary_records) != 72:
        raise Exp001ContractError("primary-unit expansion drift")
    return {"status": "verified", "principles": 40, "web_resources": 18,
            "items": len(items), "matrix_cells": len(loaded["matrix_cells"]),
            "tool_edges": len(loaded["tool_edges"]), "source_exposures": len(loaded["source_exposures"]),
            "public_record_stubs": len(stubs), "source_hashes": paths}


validate_contract = verify_contract
