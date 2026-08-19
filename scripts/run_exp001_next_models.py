#!/usr/bin/env python3
"""Run one authorized GPT-Neo or Qwen2.5 comparative control.

The script is intentionally inert until the exact authorization and local
integrity receipt pass. It performs no generation and opens the sealed target
only through the existing one-shot analysis boundary.
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

from latent_triz import exp001_comparative_material_runner as runner_mod  # noqa: E402
from latent_triz.exp001_comparative_adapter import ComparativeModelContract, ComparativeTeacherForcingAdapter  # noqa: E402
from latent_triz.exp001_comparative_material_runner import run_comparative_material  # noqa: E402
from latent_triz.exp001_next_model_contract import NEXT_MODELS, validate_next_model_contract  # noqa: E402


AUTH_PATH = ROOT / "experiments/exp001-comparative-reference/next-model-authorization.json"
TARGET_PATH = ROOT / "artifacts/exp001-r3/target-key/targets.jsonl"
TARGET_SHA256 = "5dd8e3e42e074439f2934db900f233508cc5671c5299516a033d815d47ccaa97"
PLAN_PATH = ROOT / "experiments/exp001-comparative-reference/analysis-plan.json"


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _candidate(model_id: str) -> dict:
    payload = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    for item in payload.get("candidates", []):
        if item.get("model_id") == model_id:
            return item
    raise RuntimeError("authorization candidate is missing")


def _verify_tokenizer_metadata(model_id: str, root: Path) -> None:
    meta = NEXT_MODELS[model_id]
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    tokenizer = json.loads((root / "tokenizer_config.json").read_text(encoding="utf-8"))
    checks = {
        "model_type": config.get("model_type") == meta["model_type"],
        "architecture": config.get("architectures") == [meta["architecture"]],
        "layers": int(config.get("num_hidden_layers", config.get("num_layers", -1))) == meta["layers"],
        "hidden": int(config.get("hidden_size", -1)) == meta["hidden"],
        "vocab": int(config.get("vocab_size", -1)) == meta["vocab"],
        "tokenizer_class": tokenizer.get("tokenizer_class") == meta["tokenizer_class"],
        "tokenizer_max_length": int(tokenizer.get("model_max_length", -1)) == meta["tokenizer_max_length"],
        "model_context": int(config.get("max_position_embeddings", -1)) == meta["model_context"],
    }
    if not all(checks.values()):
        raise RuntimeError("official config/tokenizer contract drift: " + ",".join(k for k, v in checks.items() if not v))


def _target_reader(records):
    payload = TARGET_PATH.read_bytes()
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


def _install_next_contract(model_id: str) -> None:
    meta = NEXT_MODELS[model_id]
    runner_mod.EXPECTED_MODELS[model_id] = {
        "role": "next_complementary_control",
        "revision": meta["revision"],
        "model_type": meta["model_type"],
        "architecture": meta["architecture"],
    }
    runner_mod._model_key = lambda value: NEXT_MODELS[value]["key"]  # type: ignore[assignment]
    runner_mod.validate_comparative_contract = lambda root, material_execution=False: validate_next_model_contract(root, model_id, material_execution=material_execution)  # type: ignore[assignment]

    def provenance(repo: Path, value: str) -> dict:
        paths = {
            "protocol": repo / "experiments/exp001-comparative-reference/protocol.json",
            "analysis_plan": repo / "experiments/exp001-comparative-reference/analysis-plan.json",
            "execution_authorization": AUTH_PATH,
            "model_integrity_receipt": repo / NEXT_MODELS[value]["receipt"],
        }
        output = {name: {"path": path.relative_to(repo).as_posix(), "sha256": _sha(path)} for name, path in paths.items()}
        output["execution_code_commit"] = os.popen("git rev-parse HEAD").read().strip()
        return output

    runner_mod._provenance = provenance  # type: ignore[assignment]

    def validate(authorization, value, revision):
        candidate = _candidate(value)
        if authorization.get("status") != "authorized" or authorization.get("operator_approval", {}).get("granted") is not True:
            raise runner_mod.ComparativeMaterialError("next-model authorization is not active")
        if candidate.get("revision") != revision or candidate.get("permissions", {}).get("model_load") is not True:
            raise runner_mod.ComparativeMaterialError("next-model identity/load permission mismatch")
        execution = authorization.get("execution", {})
        if execution.get("network") is not False or execution.get("generation") is not False or execution.get("sealed_target_reads") != "exactly_one_at_analysis_boundary":
            raise runner_mod.ComparativeMaterialError("next-model execution boundary drift")

    runner_mod.validate_material_authorization = validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", required=True, choices=sorted(NEXT_MODELS))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ccp-gate", type=Path, required=True)
    args = parser.parse_args(argv)
    model_id = args.model_id
    meta = NEXT_MODELS[model_id]
    auth = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    candidate = _candidate(model_id)
    root = ROOT / candidate["runtime_root"]
    validate_next_model_contract(ROOT, model_id, material_execution=True)
    _verify_tokenizer_metadata(model_id, root)
    _install_next_contract(model_id)
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
    adapter = ComparativeTeacherForcingAdapter.load(root, contract=contract)
    gate = json.loads(args.ccp_gate.read_text(encoding="utf-8"))
    result = run_comparative_material(
        root=ROOT,
        run_id=args.run_id,
        model_id=model_id,
        revision=meta["revision"],
        authorization=auth,
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
