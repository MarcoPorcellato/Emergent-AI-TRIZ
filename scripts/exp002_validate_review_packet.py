#!/usr/bin/env python3
"""Validate one complete EXP-002 expert packet without model or target access."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.exp002_expert_review import validate_review_packet  # noqa: E402
from latent_triz.exp002_question_bank import build_question_bank  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _question_ids(repository: Path) -> tuple[list[str], str]:
    principles = [json.loads(line) for line in (repository / "data/triz-reference/principles.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    fixture = repository / "experiments/exp001-reference-integrated/fixtures"
    read_jsonl = lambda name: [json.loads(line) for line in (fixture / name).read_text(encoding="utf-8").splitlines() if line.strip()]
    questions = build_question_bank(principles, read_jsonl("matrix-cells.jsonl"), read_jsonl("tool-edges.jsonl"))
    manifest = repository / "experiments/exp002-qwen3-followup/question-bank-manifest.json"
    return [record["question_id"] for record in questions], _sha256(manifest)


def validate_file(packet_path: str | Path, *, root: str | Path = ROOT) -> dict[str, Any]:
    repository = Path(root).resolve()
    packet = json.loads(Path(packet_path).read_text(encoding="utf-8"))
    question_ids, question_bank_sha256 = _question_ids(repository)
    return validate_review_packet(packet, question_ids, question_bank_sha256=question_bank_sha256)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(validate_file(args.packet), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
