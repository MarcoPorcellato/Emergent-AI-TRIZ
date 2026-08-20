#!/usr/bin/env python3
"""Verify the complete EXP-002-AUTO no-model checkpoint fail closed."""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.exp002_auto_contract import validate_auto_dossier, validate_auto_protocol  # noqa: E402
from latent_triz.exp002_auto_fixtures import validate_public_records  # noqa: E402
from latent_triz.exp002_auto_schedule import validate_auto_schedule  # noqa: E402
from latent_triz.validator import validate  # noqa: E402


def _load(relative: str) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _jsonl(relative: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (ROOT / relative).read_text(encoding="utf-8").splitlines() if line]


def _sha256(relative: str) -> str:
    digest = hashlib.sha256()
    with (ROOT / relative).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _schema(schema_relative: str, instance: Any) -> None:
    issues = validate(instance, _load(schema_relative))
    if issues:
        raise AssertionError(f"{schema_relative}: {issues[0].path}: {issues[0].message}")


def _assert_no_ml_imports() -> None:
    for relative in (
        "src/latent_triz/exp002_auto_contract.py",
        "src/latent_triz/exp002_auto_fixtures.py",
        "src/latent_triz/exp002_auto_schedule.py",
        "src/latent_triz/exp002_auto_execution.py",
        "src/latent_triz/exp002_auto_stage_gate.py",
        "src/latent_triz/exp002_auto_analysis.py",
        "src/latent_triz/exp002_auto_report.py",
    ):
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"), filename=relative)
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if any(name == "torch" or name.startswith("torch.") or name == "transformers" or name.startswith("transformers.") for name in names):
                raise AssertionError(f"no-model module imports ML runtime: {relative}")


def main() -> int:
    protocol_relative = "experiments/exp002-auto/protocol.json"
    protocol = _load(protocol_relative)
    _schema("schemas/exp002-auto-protocol.schema.json", protocol)
    validate_auto_protocol(protocol)
    factual_relative = "experiments/exp002-auto/factual-public.jsonl"
    formulation_relative = "experiments/exp002-auto/formulation-public.jsonl"
    procedural_relative = "experiments/exp002-auto/procedural-public.jsonl"
    for relative, count in ((factual_relative, 178), (formulation_relative, 160), (procedural_relative, 48)):
        records = _jsonl(relative)
        validate_public_records(records, expected_count=count)
        for record in records:
            _schema("schemas/exp002-auto-public-record.schema.json", record)
    key_template = _load("experiments/exp002-auto/combined-target-key-template.json")
    _schema("schemas/exp002-auto-combined-target-key.schema.json", key_template)
    if key_template["status"] != "not_ready" or key_template["records"]:
        raise AssertionError("public combined target key template must remain unmaterialized")
    schedule_relative = "experiments/exp002-auto/schedule.json"
    schedule = _load(schedule_relative)
    _schema("schemas/exp002-auto-schedule.schema.json", schedule)
    validate_auto_schedule(schedule)
    manifest_relative = "experiments/exp002-auto/input-manifest.json"
    manifest = _load(manifest_relative)
    if manifest.get("artifact_class") != "exp002-auto-input-manifest" or manifest.get("status") != "frozen_no_model" or manifest.get("model_access") is not False or manifest.get("sealed_target_access") is not False or manifest.get("claim_ids") != []:
        raise AssertionError("AUTO input manifest crossed no-model boundary")
    if manifest.get("input_bindings") != schedule.get("input_bindings") or manifest.get("schedule_sha256") != _sha256(schedule_relative):
        raise AssertionError("AUTO schedule/input-manifest binding drift")
    for relative, digest in manifest["input_bindings"].items():
        if _sha256(relative) != digest:
            raise AssertionError(f"AUTO input hash drift: {relative}")
    dossier_relative = "experiments/exp002-auto/approval-dossier.json"
    dossier = _load(dossier_relative)
    _schema("schemas/exp002-auto-approval-dossier.schema.json", dossier)
    validate_auto_dossier(dossier, protocol_sha256=_sha256(protocol_relative))
    if dossier["status"] != "approval_requested" or dossier["operator_approval"]["granted"] is not False:
        raise AssertionError("AUTO dossier must remain unapproved in the no-model checkpoint")
    receipt = _load("results/exp002-auto/preexecution/execution-receipt-template.json")
    _schema("schemas/exp002-auto-execution-receipt.schema.json", receipt)
    if receipt["status"] != "not_started" or receipt["access"] != {
        "model_loaded": False,
        "model_output_accessed": False,
        "sealed_target_accessed": False,
        "target_reads": 0,
    }:
        raise AssertionError("AUTO execution template crosses the no-model boundary")
    publication = _load("results/exp002-auto/preexecution/publication-manifest.json")
    _schema("schemas/exp002-auto-publication-manifest.schema.json", publication)
    if publication["status"] != "not_ready" or publication["packages"] or publication["external_score_assets"]:
        raise AssertionError("AUTO publication template is not a safe preexecution record")
    _assert_no_ml_imports()
    print("exp002-auto contract: PASS model_access=false sealed_target_access=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
