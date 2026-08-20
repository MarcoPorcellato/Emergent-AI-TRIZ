#!/usr/bin/env python3
"""Freeze the EXP-002 direct answer key from three independent packets.

This command is target-free and model-free. It refuses incomplete packets and
never overwrites an existing key.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.exp002_answer_key import freeze_answer_key_from_packets  # noqa: E402
from latent_triz.exp002_question_bank import build_question_bank  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_packets(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    packets = payload.get("packets") if isinstance(payload, dict) else payload
    if isinstance(packets, (str, bytes, bytearray)) or not isinstance(packets, list):
        raise ValueError("packet input must be a JSON array or an object with packets")
    return packets


def freeze_from_files(*, packets_path: str | Path, output_path: str | Path, root: str | Path = ROOT) -> dict[str, Any]:
    repository = Path(root).resolve()
    question_bank_path = repository / "experiments/exp002-qwen3-followup/question-bank-manifest.json"
    packets_file = Path(packets_path).resolve()
    output = Path(output_path)
    if not output.is_absolute():
        output = repository / output
    if output.exists():
        raise FileExistsError(f"refuse overwrite: {output}")
    manifest = json.loads(question_bank_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "ready_no_model":
        raise ValueError("question bank is not the frozen no-model manifest")
    fixture_dir = repository / "experiments/exp001-reference-integrated/fixtures"
    read_jsonl = lambda name: [json.loads(line) for line in (fixture_dir / name).read_text(encoding="utf-8").splitlines() if line.strip()]
    principles = [json.loads(line) for line in (repository / "data/triz-reference/principles.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    questions = build_question_bank(principles, read_jsonl("matrix-cells.jsonl"), read_jsonl("tool-edges.jsonl"))
    question_ids = [record["question_id"] for record in questions]
    key = freeze_answer_key_from_packets(
        _read_packets(packets_file), question_ids,
        question_bank="experiments/exp002-qwen3-followup/question-bank-manifest.json",
        question_bank_sha256=_sha256(question_bank_path),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(key, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {"status": "frozen", "question_count": len(question_ids), "output": output.relative_to(repository).as_posix() if output.is_relative_to(repository) else output.name, "model_access": False, "sealed_target_access": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packets", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(freeze_from_files(packets_path=args.packets, output_path=args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
