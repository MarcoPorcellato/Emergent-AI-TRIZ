#!/usr/bin/env python3
"""Materialize only public EXP-002-AUTO fixture records deterministically."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.exp002_auto_fixtures import (  # noqa: E402
    build_factual_records,
    build_formulation_records,
    build_procedural_records,
)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_new(path: Path, text: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite fixture: {path}")
    path.write_text(text, encoding="utf-8")


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir
    if output.exists() and any(output.iterdir()):
        expected = {"protocol.json", "model-registry.json"}
        if {entry.name for entry in output.iterdir()} - expected:
            raise SystemExit("refusing to write into a non-empty fixture directory")
    output.mkdir(parents=True, exist_ok=True)
    principles = _jsonl(ROOT / "data/triz-reference/principles.jsonl")
    matrix = _jsonl(ROOT / "experiments/exp001-reference-integrated/fixtures/matrix-cells.jsonl")
    edges = _jsonl(ROOT / "experiments/exp001-reference-integrated/fixtures/tool-edges.jsonl")
    factual, _ = build_factual_records(principles, matrix, edges)
    formulation = build_formulation_records(principles)
    procedural, _ = build_procedural_records()
    _write_new(output / "factual-public.jsonl", _jsonl_text(factual))
    _write_new(output / "formulation-public.jsonl", _jsonl_text(formulation))
    _write_new(output / "procedural-public.jsonl", _jsonl_text(procedural))
    _write_new(output / "combined-target-key-template.json", json.dumps({
        "artifact_class": "exp002-auto-combined-target-key",
        "protocol_id": "exp002-auto-v1.0.0",
        "status": "not_ready",
        "record_count": 226,
        "records": [],
        "sealed_target_accessed": False,
        "claim_ids": [],
    }, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
