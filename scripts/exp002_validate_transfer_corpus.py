#!/usr/bin/env python3
"""Audit a target-free EXP-002C corpus before any material authorization."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.exp002_transfer_corpus import validate_transfer_fixture  # noqa: E402


def audit_corpus(path: str | Path, *, root: str | Path = ROOT) -> dict[str, Any]:
    repository = Path(root).resolve()
    corpus_path = Path(path)
    if not corpus_path.is_absolute():
        corpus_path = repository / corpus_path
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("artifact_class") != "exp002-transfer-corpus":
        raise ValueError("unexpected EXP-002C corpus artifact")
    status = payload.get("status")
    if status not in {"design_ready_no_model", "frozen_no_model"}:
        raise ValueError("corpus status is unsupported")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("corpus records must be an array")
    if payload.get("model_access") is not False or payload.get("sealed_target_access") is not False:
        raise ValueError("corpus artifact crosses a forbidden boundary")
    if not records:
        if status != "design_ready_no_model":
            raise ValueError("frozen corpus cannot be empty")
        return {"status": "design_incomplete", "record_count": 0, "model_access": False, "sealed_target_access": False, "claim_ids": []}
    audit = validate_transfer_fixture(records, status="frozen" if status == "frozen_no_model" else "design")
    if status == "frozen_no_model":
        power = json.loads((repository / "results/exp002/preexecution/power-calibration.json").read_text(encoding="utf-8"))
        if power.get("status") != "pass" or power.get("selected_domain_count") != audit["domain_count"]:
            raise ValueError("frozen corpus domain count does not bind the power calibration")
        proximity = json.loads((repository / "experiments/exp002-qwen3-followup/source-proximity-manifest.json").read_text(encoding="utf-8"))
        if proximity.get("canonical_excerpts_in_blinded_primary") is not False:
            raise ValueError("source-proximity manifest permits canonical excerpts in the primary")
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(audit_corpus(args.corpus), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
