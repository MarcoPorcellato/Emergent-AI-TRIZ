#!/usr/bin/env python3
"""Run exactly one authorized additional EXP-001 model locally.

This extension deliberately reuses the frozen public-record protocol and
statistics, but keeps the two added models in separate packages.  It loads
only the already integrity-verified local snapshot, never generates text or
uses the network, and delegates the single sealed-target read to the existing
analysis boundary.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz import exp001_comparative_contract as contract_mod  # noqa: E402
from latent_triz import exp001_comparative_material_runner as runner_mod  # noqa: E402
from latent_triz.exp001_comparative_adapter import ComparativeModelContract, ComparativeTeacherForcingAdapter  # noqa: E402
from latent_triz.exp001_comparative_material_runner import run_comparative_material  # noqa: E402


AUTH_PATH = ROOT / "experiments/exp001-comparative-reference/additional-model-authorization.json"
TARGET_PATH = ROOT / "artifacts/exp001-r3/target-key/targets.jsonl"
TARGET_SHA256 = "5dd8e3e42e074439f2934db900f233508cc5671c5299516a033d815d47ccaa97"
PLAN_PATH = ROOT / "experiments/exp001-comparative-reference/analysis-plan.json"
AUTH_SHA256 = "e284ed8152afb767746773d55aee5dd4bf437d6315450ac3dc307a81196ebfd8"

MODELS = {
    "openai-community/gpt2": {
        "revision": "607a30d783dfa663caf39e06633721c8d4cfcd7e",
        "model_type": "gpt2",
        "architecture": "GPT2LMHeadModel",
        "layers": 12,
        "hidden": 768,
        "root": ROOT / "artifacts/models/gpt2-607a30d7",
        "key": "gpt2-607a30d7",
        "receipt": ROOT / "results/exp001-comparative/preexecution/gpt2-integrity-receipt.json",
        "tokenizer_class": None,
        "vocab_size": 50257,
        "max_length": 1024,
    },
    "HuggingFaceTB/SmolLM2-135M": {
        "revision": "93efa2f097d58c2a74874c7e644dbc9b0cee75a2",
        "model_type": "llama",
        "architecture": "LlamaForCausalLM",
        "layers": 30,
        "hidden": 576,
        "root": ROOT / "artifacts/models/smollm2-135m-93efa2f0",
        "key": "smollm2-135m-93efa2f0",
        "receipt": ROOT / "results/exp001-comparative/preexecution/smollm2-135m-integrity-receipt.json",
        "tokenizer_class": "GPT2Tokenizer",
        "vocab_size": 49152,
        "max_length": 8192,
    },
}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_snapshot(model_id: str) -> dict:
    meta = MODELS[model_id]
    receipt = json.loads(meta["receipt"].read_text(encoding="utf-8"))
    if receipt.get("status") != "integrity_verified" or receipt.get("model_loaded") is not False or receipt.get("sealed_targets_accessed") is not False:
        raise RuntimeError("additional snapshot receipt is not pre-execution integrity_verified")
    if receipt.get("model_id") != model_id or receipt.get("revision") != meta["revision"]:
        raise RuntimeError("additional snapshot identity drift")
    for item in receipt.get("runtime_files", []):
        path = meta["root"] / item["path"]
        if not path.is_file() or _sha(path) != item["sha256"]:
            raise RuntimeError(f"additional snapshot hash mismatch: {item.get('path')}")
    return receipt


def _verify_tokenizer_metadata(model_id: str) -> None:
    """Check the pinned tokenizer contract before importing model weights.

    SmolLM2-135M is a Llama architecture with a GPT-2 byte-level tokenizer;
    the model card's ``llama`` tag must not be used to infer tokenizer class.
    """
    meta = MODELS[model_id]
    config = json.loads((meta["root"] / "config.json").read_text(encoding="utf-8"))
    tokenizer = json.loads((meta["root"] / "tokenizer_config.json").read_text(encoding="utf-8"))
    if config.get("model_type") != meta["model_type"] or config.get("architectures") != [meta["architecture"]]:
        raise RuntimeError("model config architecture drift")
    if int(config.get("vocab_size", -1)) != meta["vocab_size"]:
        raise RuntimeError("model/tokenizer vocabulary contract drift")
    if int(tokenizer.get("vocab_size", meta["vocab_size"])) != meta["vocab_size"]:
        raise RuntimeError("tokenizer vocabulary metadata drift")
    if int(tokenizer.get("model_max_length", meta["max_length"])) != meta["max_length"]:
        raise RuntimeError("tokenizer maximum length drift")
    if tokenizer.get("tokenizer_class") != meta["tokenizer_class"]:
        raise RuntimeError("tokenizer class drift from frozen official snapshot")


def _target_reader(records):
    with TARGET_PATH.open("rb") as stream:
        payload = stream.read()
    if hashlib.sha256(payload).hexdigest() != TARGET_SHA256:
        raise RuntimeError("sealed target hash mismatch")
    rows = [json.loads(line) for line in payload.decode("utf-8").splitlines() if line.strip()]
    if len(rows) != 85:
        raise RuntimeError("sealed target cardinality mismatch")
    by_id = {row.get("record_id"): row for row in rows}
    result = []
    for record in records:
        item = by_id.get(record.get("record_id"))
        if not isinstance(item, dict) or item.get("record_id") != record.get("record_id"):
            raise RuntimeError("sealed target record mismatch")
        result.append({"record_id": item["record_id"], "expected_choice": item["expected_choice"]})
    return result


def _rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _install_extension_contract(model_id: str) -> None:
    meta = MODELS[model_id]
    contract_mod.EXPECTED_MODELS[model_id] = {
        "role": "additional_control",
        "revision": meta["revision"],
        "model_type": meta["model_type"],
        "architecture": meta["architecture"],
    }
    runner_mod.EXPECTED_MODELS[model_id] = contract_mod.EXPECTED_MODELS[model_id]
    runner_mod._model_key = lambda value: MODELS[value]["key"]  # type: ignore[assignment]

    def provenance(repo: Path, value: str) -> dict:
        paths = {
            "protocol": repo / "experiments/exp001-comparative-reference/protocol.json",
            "analysis_plan": repo / "experiments/exp001-comparative-reference/analysis-plan.json",
            "execution_authorization": repo / "experiments/exp001-comparative-reference/additional-model-authorization.json",
            "model_integrity_receipt": MODELS[value]["receipt"],
        }
        out = {name: {"path": path.relative_to(repo).as_posix(), "sha256": _sha(path)} for name, path in paths.items()}
        out["execution_code_commit"] = os.popen("git rev-parse HEAD").read().strip()
        return out

    runner_mod._provenance = provenance  # type: ignore[assignment]

    def validate(authorization, value, revision):
        if authorization.get("status") != "authorized" or authorization.get("operator_approval", {}).get("granted") is not True:
            raise runner_mod.ComparativeMaterialError("additional authorization is not active")
        candidate = next((item for item in authorization.get("candidates", []) if item.get("model_id") == value), None)
        if not isinstance(candidate, dict) or candidate.get("revision") != revision or candidate.get("permissions", {}).get("model_load") is not True:
            raise runner_mod.ComparativeMaterialError("additional model identity/load permission mismatch")
        execution = authorization.get("execution", {})
        if execution.get("network") is not False or execution.get("generation") is not False or execution.get("sealed_target_reads") != "exactly_one_at_analysis_boundary":
            raise runner_mod.ComparativeMaterialError("additional execution boundary drift")

    runner_mod.validate_material_authorization = validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", required=True, choices=sorted(MODELS))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ccp-gate", type=Path, required=True)
    args = parser.parse_args(argv)
    model_id = args.model_id
    meta = MODELS[model_id]
    authorization = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    if _sha(AUTH_PATH) != AUTH_SHA256:
        raise RuntimeError("additional authorization hash drift")
    gate = json.loads(args.ccp_gate.read_text(encoding="utf-8"))
    _verify_snapshot(model_id)
    _verify_tokenizer_metadata(model_id)
    _install_extension_contract(model_id)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    contract = ComparativeModelContract(
        model_id=model_id,
        revision=meta["revision"],
        model_type=meta["model_type"],
        architecture=meta["architecture"],
        num_hidden_layers=meta["layers"],
        hidden_size=meta["hidden"],
    )
    started = time.monotonic()
    adapter = ComparativeTeacherForcingAdapter.load(meta["root"], contract=contract)
    result = run_comparative_material(
        root=ROOT,
        run_id=args.run_id,
        model_id=model_id,
        revision=meta["revision"],
        authorization=authorization,
        ccp_gate=gate,
        adapter=adapter,
        target_reader=_target_reader,
        analysis_plan=json.loads(PLAN_PATH.read_text(encoding="utf-8")),
        resource_probe=lambda: {"wall_seconds": time.monotonic() - started, "peak_rss_bytes": _rss_bytes(), "new_dense_output_bytes": 0},
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") in {"positive", "null", "non_interpretable", "incompatible"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
