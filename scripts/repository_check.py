#!/usr/bin/env python3
"""Run the complete dependency-free repository gate without requiring Make."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
ENV = dict(os.environ, PYTHONPATH=str(ROOT / "src"))


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, env=ENV, check=True)


def validate(schema: str, data: str) -> None:
    run(PYTHON, "-m", "latent_triz.cli", "validate", "--schema", schema, data)


def main() -> int:
    run(PYTHON, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py")

    validation_pairs = (
        ("schemas/case.schema.json", "tests/fixtures/case_valid.json"),
        ("schemas/study.schema.json", "experiments/000-template/manifest.json"),
        ("schemas/study.schema.json", "experiments/001-stage1-pilot/manifest.json"),
        ("schemas/run.schema.json", "experiments/000-template/run.json"),
        ("schemas/dataset-registry.schema.json", "data/registry.json"),
        ("schemas/claim.schema.json", "data/claims.jsonl"),
        ("schemas/case.schema.json", "tests/fixtures/case_valid.jsonl"),
        ("schemas/case.schema.json", "data/pilot/cases.jsonl"),
    )
    for schema, data in validation_pairs:
        validate(schema, data)

    run(PYTHON, "-m", "latent_triz.cli", "claims-audit", "--registry", "data/claims.jsonl", "--root", ".")
    run(
        PYTHON,
        "-m",
        "latent_triz.cli",
        "docs-audit",
        "--profile",
        "docs/okf-profile.toml",
        "--root",
        ".",
        "--as-of-date",
        date.today().isoformat(),
    )

    json_files = (
        "schemas/case.schema.json",
        "schemas/study.schema.json",
        "schemas/run.schema.json",
        "schemas/dataset-registry.schema.json",
        "schemas/claim.schema.json",
        "schemas/pilot-packet.schema.json",
        "schemas/pilot-response.schema.json",
        "schemas/pilot-annotation.schema.json",
        "schemas/pilot-summary.schema.json",
    )
    for path in json_files:
        json.loads((ROOT / path).read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        packets = temporary / "packets.jsonl"
        summary = temporary / "summary.json"
        run(
            PYTHON,
            "-m",
            "latent_triz.cli",
            "pilot-prepare",
            "--seed",
            "20260812",
            "--arms",
            "control",
            "treatment",
            "--cases",
            "data/pilot/cases.jsonl",
            "--output",
            str(packets),
            "--format",
            "jsonl",
        )
        if packets.read_bytes() != (ROOT / "data/pilot/packets.jsonl").read_bytes():
            raise RuntimeError("Stage 1 packets differ from the frozen expected artifact")

        run(
            PYTHON,
            "-m",
            "latent_triz.cli",
            "pilot-score",
            "--packets",
            "data/pilot/packets.jsonl",
            "--responses",
            "data/pilot/responses.jsonl",
            "--annotations",
            "data/pilot/annotations.jsonl",
            "--output",
            str(summary),
        )
        if summary.read_bytes() != (ROOT / "data/pilot/summary.json").read_bytes():
            raise RuntimeError("Stage 1 summary differs from the frozen expected artifact")

    pilot_pairs = (
        ("schemas/pilot-packet.schema.json", "data/pilot/packets.jsonl"),
        ("schemas/pilot-response.schema.json", "data/pilot/responses.jsonl"),
        ("schemas/pilot-annotation.schema.json", "data/pilot/annotations.jsonl"),
        ("schemas/pilot-summary.schema.json", "data/pilot/summary.json"),
    )
    for schema, data in pilot_pairs:
        validate(schema, data)

    print("repository-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
