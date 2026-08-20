#!/usr/bin/env python3
"""Preflight EXP-002B/C prerequisites without CCP, models, or targets."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.exp002_answer_key import validate_answer_key  # noqa: E402
from latent_triz.exp002_question_bank import build_question_bank  # noqa: E402
from latent_triz.exp002_power import validate_calibration  # noqa: E402
from latent_triz.exp002_stage_gate import validate_stage_dossier  # noqa: E402
from latent_triz.exp002_transfer_corpus import validate_transfer_fixture  # noqa: E402


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _question_ids(repository: Path) -> tuple[list[str], str]:
    manifest_path = repository / "experiments/exp002-qwen3-followup/question-bank-manifest.json"
    fixture_dir = repository / "experiments/exp001-reference-integrated/fixtures"
    principles = [json.loads(line) for line in (repository / "data/triz-reference/principles.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    read_jsonl = lambda name: [json.loads(line) for line in (fixture_dir / name).read_text(encoding="utf-8").splitlines() if line.strip()]
    records = build_question_bank(principles, read_jsonl("matrix-cells.jsonl"), read_jsonl("tool-edges.jsonl"))
    return [record["question_id"] for record in records], _sha256(manifest_path)


def preflight_stage(stage_id: str, *, root: str | Path = ROOT) -> dict[str, Any]:
    repository = Path(root).resolve()
    if stage_id not in {"EXP-002B", "EXP-002C"}:
        raise ValueError("stage must be EXP-002B or EXP-002C")
    dossier_path = repository / f"experiments/exp002-qwen3-followup/{stage_id.lower().replace('-', '')}-approval-dossier.json"
    dossier = _load(dossier_path)
    validate_stage_dossier(dossier, stage_id)
    if dossier["status"] != "authorized":
        return {"status": "approval_required", "stage_id": stage_id, "reason": "operator approval or frozen prerequisites are missing", "model_access": False, "sealed_target_access": False, "claim_ids": []}
    source_manifest = _load(repository / "experiments/exp002-qwen3-followup/source-proximity-manifest.json")
    if source_manifest.get("canonical_excerpts_in_blinded_primary") is not False:
        raise ValueError("source-proximity manifest permits canonical excerpts")
    power = _load(repository / "results/exp002/preexecution/power-calibration.json")
    validate_calibration(power)
    if stage_id == "EXP-002B":
        key_path = repository / "results/exp002/preexecution/direct-answer-key.json"
        key = _load(key_path)
        question_ids, question_bank_sha256 = _question_ids(repository)
        validate_answer_key(key, question_ids, question_bank_sha256=question_bank_sha256)
    else:
        corpus_path = repository / "experiments/exp002-qwen3-followup/transfer-corpus.json"
        corpus = _load(corpus_path)
        audit = validate_transfer_fixture(corpus["records"], status="frozen")
        if audit["domain_count"] != power["selected_domain_count"]:
            raise ValueError("frozen transfer corpus domain count differs from power receipt")
    return {"status": "ready_for_ccp_and_operator_gate", "stage_id": stage_id, "model_access": False, "sealed_target_access": False, "claim_ids": []}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("EXP-002B", "EXP-002C"))
    args = parser.parse_args(argv)
    print(json.dumps(preflight_stage(args.stage), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
