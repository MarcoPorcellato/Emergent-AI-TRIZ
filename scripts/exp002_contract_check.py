#!/usr/bin/env python3
"""Validate the EXP-002 no-model tranche without loading models or targets."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.exp002_followup import (  # noqa: E402
    EXPECTED_MODELS,
    summarize_label_surface,
    validate_no_model_protocol,
    validate_tokenizer_observation,
)
from latent_triz.exp002_question_bank import build_question_bank, validate_question_bank  # noqa: E402
from latent_triz.exp002_terminal import TERMINAL_STATUSES, build_terminal_result, validate_terminal_result  # noqa: E402
from latent_triz.exp002_analysis import evaluate_transfer, validate_analysis_result  # noqa: E402


def load(relative: str) -> Any:
    with (ROOT / relative).open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_schema(schema_path: str, instance: Any) -> None:
    schema = load(schema_path)
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        raise AssertionError(f"{schema_path}: {errors[0].message}")


def sha256(relative: str) -> str:
    digest = hashlib.sha256()
    with (ROOT / relative).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonl(relative: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with (ROOT / relative).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def main() -> int:
    protocol = load("experiments/exp002-qwen3-followup/protocol.json")
    validate_schema("schemas/exp002-followup-protocol.schema.json", protocol)
    validate_no_model_protocol(protocol)

    manifest = load("experiments/exp002-qwen3-followup/question-bank-manifest.json")
    validate_schema("schemas/exp002-question-bank-manifest.schema.json", manifest)
    records = build_question_bank(
        jsonl("data/triz-reference/principles.jsonl"),
        jsonl("experiments/exp001-reference-integrated/fixtures/matrix-cells.jsonl"),
        jsonl("experiments/exp001-reference-integrated/fixtures/tool-edges.jsonl"),
    )
    validate_question_bank(records)
    for record in records:
        validate_schema("schemas/exp002-direct-question.schema.json", record)

    plan = load("experiments/exp002-qwen3-followup/tokenizer-audit-plan.json")
    validate_schema("schemas/exp002-tokenizer-audit-plan.schema.json", plan)
    response_surface = load("experiments/exp002-qwen3-followup/response-surface-plan.json")
    validate_schema("schemas/exp002-response-surface-plan.schema.json", response_surface)
    transfer_plan = load("experiments/exp002-qwen3-followup/transfer-corpus-plan.json")
    validate_schema("schemas/exp002-transfer-corpus-plan.schema.json", transfer_plan)
    analysis_contract = load("experiments/exp002-qwen3-followup/analysis-contract.json")
    validate_schema("schemas/exp002-analysis-contract.schema.json", analysis_contract)
    source_plan = load("experiments/exp002-qwen3-followup/source-familiarity-plan.json")
    validate_schema("schemas/exp002-source-familiarity-plan.schema.json", source_plan)
    source_manifest = load("experiments/exp002-qwen3-followup/source-proximity-manifest.json")
    validate_schema("schemas/exp002-source-proximity-manifest.schema.json", source_manifest)
    approval = load("experiments/exp002-qwen3-followup/approval-dossier.json")
    validate_schema("schemas/exp002-approval-dossier.schema.json", approval)
    if approval["status"] != "approval_requested" or approval["operator_approval"]["granted"] is not False:
        raise AssertionError("EXP-002 approval dossier must remain unapproved")
    publication = load("results/exp002/preexecution/publication-manifest.json")
    validate_schema("schemas/exp002-publication-manifest.schema.json", publication)
    if publication["status"] != "not_ready" or publication["packages"]:
        raise AssertionError("preexecution publication manifest crossed its boundary")
    receipt = load("results/exp002/preexecution/tokenizer-audit.json")
    validate_schema("schemas/exp002-tokenizer-audit-receipt.schema.json", receipt)
    if receipt["status"] != "not_started" or receipt["observations"]:
        raise AssertionError("tokenizer audit must remain a no-model not-started receipt")

    diagnostic = load("results/exp002/preexecution/label-surface-diagnostic.json")
    validate_schema("schemas/exp002-label-surface-diagnostic.schema.json", diagnostic)
    expected_models = set(EXPECTED_MODELS)
    actual_models = set()
    for source in diagnostic["source_response_indices"]:
        actual_models.add(source["model_id"])
        if EXPECTED_MODELS.get(source["model_id"]) != source["revision"]:
            raise AssertionError("diagnostic model revision drift")
        if sha256(source["path"]) != source["sha256"]:
            raise AssertionError(f"response-index hash drift: {source['path']}")
    if actual_models != expected_models:
        raise AssertionError("diagnostic does not cover all seven model identities")
    for source, summary in zip(diagnostic["source_response_indices"], diagnostic["summaries"]):
        if source["model_id"] != summary["model_id"]:
            raise AssertionError("diagnostic source/summary order drift")
        payload = load(source["path"])
        rows = payload.get("records") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise AssertionError(f"response-index records missing: {source['path']}")
        rows = [row for row in rows if "transfer-blinded" in str(row.get("record_id", ""))]
        observed = summarize_label_surface(rows)
        if observed != {key: summary[key] for key in ("record_count", "top_label_counts", "top_label_entropy_bits")}:
            raise AssertionError(f"label surface drift: {source['model_id']}")

    terminal_schema = "schemas/exp002-followup-result.schema.json"
    for status in TERMINAL_STATUSES:
        terminal = build_terminal_result(study_id="EXP-002A", model_id="Qwen/Qwen3-0.6B-Base", status=status)
        validate_terminal_result(terminal)
        validate_schema(terminal_schema, terminal)
    synthetic_analysis = evaluate_transfer([1.0] * 8, minimum_domains=8, margin=0.1)
    validate_analysis_result(synthetic_analysis)
    if synthetic_analysis["status"] != "positive":
        raise AssertionError("synthetic positive analysis boundary drift")

    # This fixture is deliberately invalid for the model-access boundary and must fail closed.
    invalid = {"model_id": "Qwen/Qwen3-0.6B-Base", "revision": EXPECTED_MODELS["Qwen/Qwen3-0.6B-Base"], "tokenizer_files_sha256": "0" * 64, "label_token_ids": {label: 1 for label in "ABCD"}, "continuation_token_counts": {label: 1 for label in "ABCD"}, "prefix_boundary_ok": False, "special_tokens": {}, "runtime_versions": {}}
    try:
        validate_tokenizer_observation(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid tokenizer boundary unexpectedly accepted")

    print("EXP-002 no-model contract, question bank, tokenizer gate, and label diagnostic: PASS")
    print(f"question_records={len(records)} models={len(EXPECTED_MODELS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
