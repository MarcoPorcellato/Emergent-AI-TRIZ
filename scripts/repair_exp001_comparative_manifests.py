#!/usr/bin/env python3
"""Bind existing comparative packages to their exact pre-publication provenance.

This repair reads only already-published package artifacts and public input
receipts. It never loads a model, opens sealed targets, or changes score data.
The execution commit is intentionally supplied explicitly because these
packages were produced before the provenance fields were added to the runner.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECUTION_COMMIT = "c3027216853aa66faca77d35f28d11551a67be02"
PACKAGES = {
    "pythia-70m-e93a9faa-pythia-20260818-01": "EleutherAI/pythia-70m-deduped",
    "smollm2-360m-f8027fd0-smollm2-20260818-01": "HuggingFaceTB/SmolLM2-360M",
    "qwen3-0.6b-da87bfb-qwen3-20260818-01": "Qwen/Qwen3-0.6B-Base",
}
MODEL_RECEIPTS = {
    "EleutherAI/pythia-70m-deduped": Path("results/lab01/model-anatomy/model_receipt.json"),
    "HuggingFaceTB/SmolLM2-360M": Path("results/a0r2/preexecution/smollm2-360m-f8027fd0/integrity-receipt.json"),
    "Qwen/Qwen3-0.6B-Base": Path("results/exp001-comparative/preexecution/qwen-integrity-receipt.json"),
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def binding(path: Path) -> dict[str, str]:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}


def code_hash(path: str) -> str:
    payload = subprocess.check_output(["git", "show", f"{EXECUTION_COMMIT}:{path}"], cwd=ROOT)
    return hashlib.sha256(payload).hexdigest()


def stable_write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    for name, model_id in PACKAGES.items():
        package = ROOT / "results/exp001-comparative" / name
        receipt_path = package / "execution-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        provenance_paths = {
            "protocol": ROOT / "experiments/exp001-comparative-reference/protocol.json",
            "analysis_plan": ROOT / "experiments/exp001-comparative-reference/analysis-plan.json",
            "execution_authorization": ROOT / "experiments/exp001-comparative-reference/execution-authorization.json",
            "model_integrity_receipt": ROOT / MODEL_RECEIPTS[model_id],
        }
        if model_id == "Qwen/Qwen3-0.6B-Base":
            provenance_paths["qwen_acquisition_dossier"] = ROOT / "experiments/exp001-comparative-reference/qwen-acquisition-dossier.json"
        provenance = {key: binding(path) for key, path in provenance_paths.items()}
        provenance["execution_code_commit"] = EXECUTION_COMMIT
        provenance["execution_code_files"] = {
            path: code_hash(path)
            for path in (
                "src/latent_triz/exp001_comparative_contract.py",
                "src/latent_triz/exp001_comparative_material_runner.py",
                "src/latent_triz/exp001_comparative_report.py",
                "scripts/run_exp001_comparative.py",
            )
        }
        receipt["provenance"] = provenance
        stable_write(receipt_path, receipt)
        files = {
            name: package / name
            for name in (
                "execution-receipt.json",
                "statistical-result.json",
                "response-index.json",
                "sealed-key-access.json",
                "recovery-observation.json",
                "report.md",
            )
        }
        manifest = json.loads((package / "publication-manifest.json").read_text(encoding="utf-8"))
        manifest["provenance"] = provenance
        manifest["bindings"] = {key: binding(path) for key, path in files.items()}
        stable_write(package / "publication-manifest.json", manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
