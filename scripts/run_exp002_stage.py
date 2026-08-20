#!/usr/bin/env python3
"""Run one authorised EXP-002A stage for one exact local model snapshot.

The command is intentionally narrow: it performs no download, enables the
Transformers offline switches, never calls generation, and delegates the
single sealed-target capability to :func:`run_exp002_stage`.  A live CCP gate
snapshot must be supplied by the caller; an unreadable or non-Admit snapshot
fails before model construction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.exp001_comparative_adapter import ComparativeModelContract, ComparativeTeacherForcingAdapter  # noqa: E402
from latent_triz.exp001_r3_primary_fixture import build_primary_records  # noqa: E402
from latent_triz.exp001_r3_response_execution import execute_public_responses  # noqa: E402
from latent_triz.exp001_r3_runner import run_analysis_boundary  # noqa: E402
from latent_triz.exp001_r3_secondary_fixture import build_secondary_records  # noqa: E402
from latent_triz.exp002_execution import validate_authorized_dossier, validate_ccp_gate  # noqa: E402
from latent_triz.exp002_followup import EXPECTED_MODELS  # noqa: E402
from latent_triz.exp002_runner import run_exp002_stage  # noqa: E402
from latent_triz.exp002_surface import summarize_surface  # noqa: E402


MODEL_RECEIPTS: dict[str, Path] = {
    "EleutherAI/pythia-70m-deduped": ROOT / "results/lab01/model-anatomy/model_receipt.json",
    "HuggingFaceTB/SmolLM2-360M": ROOT / "results/a0r2/preexecution/smollm2-360m-f8027fd0/integrity-receipt.json",
    "Qwen/Qwen3-0.6B-Base": ROOT / "results/exp001-comparative/preexecution/qwen-integrity-receipt.json",
    "openai-community/gpt2": ROOT / "results/exp001-comparative/preexecution/gpt2-integrity-receipt.json",
    "HuggingFaceTB/SmolLM2-135M": ROOT / "results/exp001-comparative/preexecution/smollm2-135m-integrity-receipt.json",
    "EleutherAI/gpt-neo-125m": ROOT / "results/exp001-comparative/preexecution/gpt-neo-125m-integrity-receipt.json",
    "Qwen/Qwen2.5-0.5B": ROOT / "results/exp001-comparative/preexecution/qwen2.5-0.5b-integrity-receipt.json",
}
MODEL_ROOTS: dict[str, Path] = {
    "EleutherAI/pythia-70m-deduped": ROOT / "artifacts/models/pythia-70m-deduped-e93a9faa",
    "HuggingFaceTB/SmolLM2-360M": ROOT / "artifacts/models/smollm2-360m-f8027fd0",
    "Qwen/Qwen3-0.6B-Base": ROOT / "artifacts/models/qwen3-0.6b-base-da87bfb",
    "openai-community/gpt2": ROOT / "artifacts/models/gpt2-607a30d7",
    "HuggingFaceTB/SmolLM2-135M": ROOT / "artifacts/models/smollm2-135m-93efa2f0",
    "EleutherAI/gpt-neo-125m": ROOT / "artifacts/models/gpt-neo-125m-21def018",
    "Qwen/Qwen2.5-0.5B": ROOT / "artifacts/models/qwen2.5-0.5b-060db649",
}
MODEL_SHAPES: dict[str, tuple[str, str, int, int]] = {
    "EleutherAI/pythia-70m-deduped": ("gpt_neox", "GPTNeoXForCausalLM", 6, 512),
    "HuggingFaceTB/SmolLM2-360M": ("llama", "LlamaForCausalLM", 32, 960),
    "Qwen/Qwen3-0.6B-Base": ("qwen3", "Qwen3ForCausalLM", 28, 1024),
    "openai-community/gpt2": ("gpt2", "GPT2LMHeadModel", 12, 768),
    "HuggingFaceTB/SmolLM2-135M": ("llama", "LlamaForCausalLM", 30, 576),
    "EleutherAI/gpt-neo-125m": ("gpt_neo", "GPTNeoForCausalLM", 12, 768),
    "Qwen/Qwen2.5-0.5B": ("qwen2", "Qwen2ForCausalLM", 24, 896),
}
TARGET_PATH = ROOT / "artifacts/exp001-r3/target-key/targets.jsonl"
TARGET_SHA256 = "5dd8e3e42e074439f2934db900f233508cc5671c5299516a033d815d47ccaa97"


def _sha256(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def _runtime_items(receipt: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    items = receipt.get("runtime_files")
    if not isinstance(items, list) or not items:
        raise RuntimeError("runtime receipt has no file allowlist")
    return [item for item in items if isinstance(item, Mapping)]


def verify_runtime(model_id: str) -> dict[str, Any]:
    """Verify the already acquired snapshot without importing model libraries."""
    receipt_path = MODEL_RECEIPTS[model_id]
    root = MODEL_ROOTS[model_id]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    model_field = receipt.get("model")
    if isinstance(model_field, Mapping):
        model_from_receipt = model_field.get("id")
    elif isinstance(model_field, str):
        model_from_receipt = model_field
    else:
        model_from_receipt = None
    observed_model = receipt.get("model_id") or model_from_receipt
    if observed_model and observed_model != model_id:
        raise RuntimeError("runtime receipt model identity mismatch")
    revision_from_receipt = model_field.get("revision") if isinstance(model_field, Mapping) else None
    observed_revision = receipt.get("revision") or revision_from_receipt
    if observed_revision != EXPECTED_MODELS[model_id]:
        raise RuntimeError("runtime receipt revision mismatch")
    if receipt.get("status") not in {None, "pass", "integrity_verified"}:
        raise RuntimeError("runtime integrity receipt is not verified")
    checked = 0
    for item in _runtime_items(receipt):
        name = item.get("name", item.get("path"))
        expected = item.get("sha256")
        if not isinstance(name, str) or not name or Path(name).is_absolute() or ".." in Path(name).parts:
            raise RuntimeError("runtime receipt contains an unsafe path")
        if not isinstance(expected, str) or len(expected) != 64:
            raise RuntimeError("runtime receipt contains an invalid digest")
        path = root / name
        if not path.is_file():
            raise RuntimeError(f"runtime file is missing: {name}")
        _size, observed = _sha256(path)
        if observed != expected:
            raise RuntimeError(f"runtime integrity mismatch: {name}")
        checked += 1
    try:
        locator = receipt_path.relative_to(ROOT).as_posix()
    except ValueError:
        # Tests and external callers may provide an isolated receipt root; do
        # not leak an absolute host path into a result.
        locator = receipt_path.name
    return {"receipt": locator, "runtime_files_checked": checked}


def _records() -> list[dict[str, Any]]:
    fixture = ROOT / "experiments/exp001-reference-integrated/fixtures"
    read = lambda name: [json.loads(line) for line in (fixture / name).read_text(encoding="utf-8").splitlines() if line.strip()]
    records = build_primary_records(read("primary-units.jsonl")) + build_secondary_records(read("matrix-cells.jsonl"), read("tool-edges.jsonl"))
    if len(records) != 85:
        raise RuntimeError("EXP-002A requires the frozen 85-record public inventory")
    return records


def _render(record: Mapping[str, Any]) -> str:
    options = record.get("options")
    if not isinstance(options, list) or len(options) != 4:
        raise RuntimeError("public record options are malformed")
    lines = [f"Task: {record['prompt']}", "Options:"]
    lines.extend(f"{option['id']}. {option['description']}" for option in options)
    lines.append("Answer with exactly one option label: A, B, C, or D.")
    return "\n".join(lines)


def _target_reader(records: list[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Read and validate the sealed key once, at the analysis boundary."""
    payload = TARGET_PATH.read_bytes()
    if hashlib.sha256(payload).hexdigest() != TARGET_SHA256:
        raise RuntimeError("sealed target hash mismatch")
    rows = [json.loads(line) for line in payload.decode("utf-8").splitlines() if line.strip()]
    if len(rows) != 85:
        raise RuntimeError("sealed target cardinality mismatch")
    by_id = {row.get("record_id"): row for row in rows}
    result: list[dict[str, str]] = []
    for record in records:
        row = by_id.get(record.get("record_id"))
        if not isinstance(row, Mapping) or row.get("record_id") != record.get("record_id") or row.get("expected_choice") not in {"A", "B", "C", "D"}:
            raise RuntimeError("sealed target record mismatch")
        result.append({"record_id": str(row["record_id"]), "expected_choice": str(row["expected_choice"])})
    return result


def _rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", required=True, choices=sorted(EXPECTED_MODELS))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ccp-gate", required=True, type=Path)
    parser.add_argument("--study-id", default="EXP-002A", choices=("EXP-002A",))
    args = parser.parse_args(argv)

    model_id = args.model_id
    revision = EXPECTED_MODELS[model_id]
    dossier = json.loads((ROOT / "experiments/exp002-qwen3-followup/approval-dossier.json").read_text(encoding="utf-8"))
    gate = json.loads(args.ccp_gate.read_text(encoding="utf-8"))
    # These checks intentionally precede model construction and target access.
    validate_authorized_dossier(dossier, model_id)
    validate_ccp_gate(gate)
    runtime_receipt = verify_runtime(model_id)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    model_type, architecture, layers, hidden = MODEL_SHAPES[model_id]
    contract = ComparativeModelContract(model_id=model_id, revision=revision, model_type=model_type, architecture=architecture, num_hidden_layers=layers, hidden_size=hidden)
    adapter = ComparativeTeacherForcingAdapter.load(MODEL_ROOTS[model_id], contract=contract)
    records = _records()
    by_id = {record["record_id"]: record for record in records}

    def scorer(prompt: str) -> Mapping[str, float]:
        # The runner supplies the rendered public prompt; no target content is
        # available here.  This scorer is deliberately label-only and never
        # calls ``generate``.
        if time.monotonic() >= deadline:
            raise TimeoutError("EXP-002A wall-time ceiling reached before scoring")
        scores: dict[str, float] = {}
        for label in ("A", "B", "C", "D"):
            if time.monotonic() >= deadline:
                raise TimeoutError("EXP-002A wall-time ceiling reached during scoring")
            scores[label] = float(adapter.score_prompt_choice(prompt, label))
        return scores

    public_rows = [{"record_id": record["record_id"], "condition": record.get("condition", "original_abcd"), "prompt": _render(record)} for record in records]

    def analysis(scored: list[Mapping[str, Any]], reader: Any) -> dict[str, Any]:
        response_rows = [{"record_id": row["record_id"], "scores": row["scores"]} for row in scored]
        boundary = run_analysis_boundary(records, response_rows, lambda _ignored: reader(), json.loads((ROOT / "experiments/exp001-reference-integrated/analysis-plan.json").read_text(encoding="utf-8")))
        return {"status": boundary["analysis"]["status"], "exp002a_surface": summarize_surface(response_rows), "reference_boundary": boundary}

    started = time.monotonic()
    deadline = started + 1_800.0
    result = run_exp002_stage(
        root=ROOT, run_id=args.run_id, study_id=args.study_id, model_id=model_id, revision=revision,
        dossier=dossier, ccp_gate=gate, public_rows=public_rows, scorer=scorer,
        target_reader=lambda rows: _target_reader([by_id[row["record_id"]] for row in rows]),
        analysis=analysis, adapter=adapter,
        resource_probe=lambda: {"wall_seconds": time.monotonic() - started, "peak_rss_bytes": _rss_bytes(), "new_dense_output_bytes": 0},
    )
    result["runtime_receipt"] = runtime_receipt
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in {"positive", "null", "non_interpretable", "incompatible"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
