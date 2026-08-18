#!/usr/bin/env python3
"""Execute exactly one authorized comparative model run.

The caller must supply a live CCP gate snapshot.  Model loading is local-only,
CPU float32, and target content is opened exactly once by the analysis-boundary
reader.  This command has no generation path and supports one model per
process, making post-access retries impossible without a new invocation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.exp001_comparative_adapter import ComparativeModelContract, ComparativeTeacherForcingAdapter  # noqa: E402
from latent_triz.exp001_comparative_contract import EXPECTED_MODELS  # noqa: E402
from latent_triz.exp001_comparative_material_runner import run_comparative_material  # noqa: E402


MODEL_RECEIPTS = {
    "EleutherAI/pythia-70m-deduped": ROOT / "results/lab01/model-anatomy/model_receipt.json",
    "HuggingFaceTB/SmolLM2-360M": ROOT / "results/a0r2/preexecution/smollm2-360m-f8027fd0/integrity-receipt.json",
    "Qwen/Qwen3-0.6B-Base": ROOT / "results/exp001-comparative/preexecution/qwen-integrity-receipt.json",
}
TARGET_PATH = ROOT / "artifacts/exp001-r3/target-key/targets.jsonl"
TARGET_SHA256 = "5dd8e3e42e074439f2934db900f233508cc5671c5299516a033d815d47ccaa97"
MODEL_SHAPES = {
    "EleutherAI/pythia-70m-deduped": (6, 512),
    "HuggingFaceTB/SmolLM2-360M": (32, 960),
    "Qwen/Qwen3-0.6B-Base": (28, 1024),
}


def _sha256(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def _verify_runtime(model_id: str, root: Path) -> None:
    receipt = json.loads(MODEL_RECEIPTS[model_id].read_text(encoding="utf-8"))
    files = receipt.get("runtime_files", [])
    for item in files:
        name = item.get("name", item.get("path"))
        expected = item.get("sha256")
        if not isinstance(name, str) or not isinstance(expected, str):
            raise RuntimeError("runtime receipt is incomplete")
        path = root / name
        _size, observed = _sha256(path)
        if observed != expected:
            raise RuntimeError(f"runtime integrity mismatch: {name}")


def _target_reader(records):
    # This function is invoked once, by the analysis boundary only.
    with TARGET_PATH.open("rb") as stream:
        payload = stream.read()
    size = len(payload)
    digest = hashlib.sha256(payload).hexdigest()
    if digest != TARGET_SHA256:
        raise RuntimeError("sealed target hash mismatch")
    rows = [json.loads(line) for line in payload.decode("utf-8").splitlines() if line.strip()]
    if len(rows) != 85:
        raise RuntimeError(f"sealed target cardinality mismatch: {len(rows)}")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", required=True, choices=sorted(EXPECTED_MODELS))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ccp-gate", type=Path, required=True)
    args = parser.parse_args(argv)
    model_id = args.model_id
    model_meta = EXPECTED_MODELS[model_id]
    num_hidden_layers, hidden_size = MODEL_SHAPES[model_id]
    model_root = ROOT / {
        "EleutherAI/pythia-70m-deduped": "artifacts/models/pythia-70m-deduped-e93a9faa",
        "HuggingFaceTB/SmolLM2-360M": "artifacts/models/smollm2-360m-f8027fd0",
        "Qwen/Qwen3-0.6B-Base": "artifacts/models/qwen3-0.6b-base-da87bfb",
    }[model_id]
    _verify_runtime(model_id, model_root)
    authorization = json.loads((ROOT / "experiments/exp001-comparative-reference/execution-authorization.json").read_text(encoding="utf-8"))
    gate = json.loads(args.ccp_gate.read_text(encoding="utf-8"))
    contract = ComparativeModelContract(
        model_id=model_id,
        revision=model_meta["revision"],
        model_type=model_meta["model_type"],
        architecture=model_meta["architecture"],
        num_hidden_layers=num_hidden_layers,
        hidden_size=hidden_size,
    )
    started = time.monotonic()
    adapter = ComparativeTeacherForcingAdapter.load(model_root, contract=contract)
    result = run_comparative_material(
        root=ROOT,
        run_id=args.run_id,
        model_id=model_id,
        revision=model_meta["revision"],
        authorization=authorization,
        ccp_gate=gate,
        adapter=adapter,
        target_reader=_target_reader,
        analysis_plan=json.loads((ROOT / "experiments/exp001-comparative-reference/analysis-plan.json").read_text(encoding="utf-8")),
        resource_probe=lambda: {
            "wall_seconds": time.monotonic() - started,
            "peak_rss_bytes": _rss_bytes(),
            "new_dense_output_bytes": 0,
        },
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") in {"positive", "null", "non_interpretable", "incompatible"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
