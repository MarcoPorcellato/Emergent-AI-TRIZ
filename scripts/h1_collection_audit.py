#!/usr/bin/env python3
"""Audit returned v1.2 H1 expert files; never opens a model or target."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.h1_collection_audit import audit_h1_annotations  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", nargs=3, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit_h1_annotations(
        cases_path=ROOT / "experiments/h1-cognitive-pilot/cases.jsonl",
        guide_path=ROOT / "experiments/h1-cognitive-pilot/annotation-guide-v1.2.json",
        annotation_schema_path=ROOT / "schemas/h1-annotation.schema.json",
        annotation_paths=[Path(item) for item in args.annotations],
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "ready_for_freeze": result["ready_for_freeze"]}, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
