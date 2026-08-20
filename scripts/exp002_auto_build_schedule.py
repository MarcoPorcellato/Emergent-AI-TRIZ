#!/usr/bin/env python3
"""Freeze the EXP-002-AUTO public schedule from already published inputs."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.exp002_auto_schedule import build_auto_schedule, validate_auto_schedule  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_new(path: Path, payload: dict) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite frozen schedule artifact: {path}")
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> int:
    output = ROOT / "experiments/exp002-auto"
    diagnostic_path = ROOT / "results/exp002/preexecution/label-surface-diagnostic.json"
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    sources = diagnostic.get("source_response_indices")
    if not isinstance(sources, list) or not sources:
        raise SystemExit("published response-index diagnostic is malformed")
    source_path = ROOT / sources[0]["path"]
    response_index = json.loads(source_path.read_text(encoding="utf-8"))
    transfer_ids = [row["record_id"] for row in response_index["records"] if "transfer-blinded" in str(row.get("record_id", ""))]
    input_paths = (
        "experiments/exp002-auto/factual-public.jsonl",
        "experiments/exp002-auto/formulation-public.jsonl",
        "experiments/exp002-auto/procedural-public.jsonl",
        "results/exp002/preexecution/label-surface-diagnostic.json",
        sources[0]["path"],
    )
    bindings = {path: _sha256(ROOT / path) for path in input_paths}
    schedule = build_auto_schedule(transfer_ids, bindings)
    validate_auto_schedule(schedule)
    _write_new(output / "schedule.json", schedule)
    _write_new(output / "input-manifest.json", {
        "artifact_class": "exp002-auto-input-manifest",
        "protocol_id": "exp002-auto-v1.0.0",
        "status": "frozen_no_model",
        "input_bindings": bindings,
        "schedule_sha256": _sha256(output / "schedule.json"),
        "model_access": False,
        "sealed_target_access": False,
        "claim_ids": [],
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
