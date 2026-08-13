#!/usr/bin/env python3
"""Run the complete dependency-free repository gate without requiring Make."""

from __future__ import annotations

import json
import hashlib
import os
import shutil
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
        ("schemas/dataset-plan.schema.json", "experiments/001-stage1-pilot/dataset-plan.json"),
        ("schemas/model-candidate.schema.json", "experiments/001-stage1-pilot/model-candidates.jsonl"),
        ("schemas/lab01-manifest.schema.json", "experiments/lab01-model-anatomy/manifest.json"),
        ("schemas/lab01-model-receipt.schema.json", "results/lab01/model-anatomy/model_receipt.json"),
        ("schemas/lab01-run.schema.json", "results/lab01/model-anatomy/run.json"),
        ("schemas/dataset-annotation.schema.json", "data/pilot/dataset-annotations.jsonl"),
        ("schemas/dataset-snapshot.schema.json", "results/lab02/dataset-anatomy/snapshot_manifest.json"),
        ("schemas/lab03-config.schema.json", "experiments/lab03-behavioral-baselines/config.json"),
        ("schemas/lab03-result.schema.json", "results/lab03/behavioral-baselines/summary.json"),
        ("schemas/lab04-config.schema.json", "experiments/lab04-decodability/config.json"),
        ("schemas/representation-record.schema.json", "data/pilot/representations.jsonl"),
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
        "schemas/dataset-plan.schema.json",
        "schemas/model-candidate.schema.json",
        "schemas/evaluator-packet.schema.json",
        "schemas/allocation-key.schema.json",
        "schemas/lab01-manifest.schema.json",
        "schemas/lab01-model-receipt.schema.json",
        "schemas/lab01-run.schema.json",
        "schemas/dataset-annotation.schema.json",
        "schemas/dataset-snapshot.schema.json",
        "schemas/lab03-config.schema.json",
        "schemas/lab03-result.schema.json",
        "schemas/lab04-config.schema.json",
        "schemas/lab04-result.schema.json",
        "schemas/representation-record.schema.json",
        "experiments/lab03-behavioral-baselines/config.json",
        "experiments/lab04-decodability/config.json",
    )
    for path in json_files:
        json.loads((ROOT / path).read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        packets = temporary / "packets.jsonl"
        summary = temporary / "summary.json"
        evaluator_packets = temporary / "evaluator-packets.jsonl"
        allocation_key = temporary / "sealed-allocation-key.json"
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

        run(
            PYTHON,
            "-m",
            "latent_triz.cli",
            "pilot-export-evaluator",
            "--packets",
            "data/pilot/packets.jsonl",
            "--responses",
            "data/pilot/responses.jsonl",
            "--evaluator-output",
            str(evaluator_packets),
            "--key-output",
            str(allocation_key),
        )
        evaluator_text = evaluator_packets.read_text(encoding="utf-8")
        for forbidden in ('"arms_by_blind"', '"control"', '"treatment"'):
            if forbidden in evaluator_text:
                raise RuntimeError(f"Evaluator export leaks allocation marker: {forbidden}")
        validate("schemas/evaluator-packet.schema.json", str(evaluator_packets))
        validate("schemas/allocation-key.schema.json", str(allocation_key))

    pilot_pairs = (
        ("schemas/pilot-packet.schema.json", "data/pilot/packets.jsonl"),
        ("schemas/pilot-response.schema.json", "data/pilot/responses.jsonl"),
        ("schemas/pilot-annotation.schema.json", "data/pilot/annotations.jsonl"),
        ("schemas/pilot-summary.schema.json", "data/pilot/summary.json"),
    )
    for schema, data in pilot_pairs:
        validate(schema, data)

    lab01_root = ROOT / "results/lab01/model-anatomy"
    parity = json.loads((lab01_root / "parity_report.json").read_text(encoding="utf-8"))
    if parity.get("status") != "pass":
        raise RuntimeError("Lab 01 parity report is not PASS")
    artifact_names = {
        "model_receipt": "model_receipt.json",
        "environment": "environment.json",
        "run": "run.json",
        "prompt": "prompt.json",
        "tokens": "tokens.json",
        "layer_summary": "layer_summary.jsonl",
        "topk_logits": "topk_logits.jsonl",
        "report_html": "report.html",
    }
    for key, filename in artifact_names.items():
        expected = parity.get("artifact_hashes", {}).get(key)
        actual = hashlib.sha256((lab01_root / filename).read_bytes()).hexdigest()
        if expected != actual:
            raise RuntimeError(f"Lab 01 artifact hash mismatch: {filename}")

    lab02_root = ROOT / "results/lab02/dataset-anatomy"
    lab02_summary = json.loads((lab02_root / "summary.json").read_text(encoding="utf-8"))
    if lab02_summary.get("evidence_eligible") is not False or lab02_summary.get("claim_ids") != []:
        raise RuntimeError("Lab 02 evidence boundary is invalid")
    if lab02_summary.get("status") != "fail":
        raise RuntimeError("Lab 02 smoke fixture must preserve the documented not-ready result")
    for key, filename in {
        "dataset_audit_report": "dataset_audit.json",
        "snapshot_verification_report": "snapshot_manifest.json",
    }.items():
        expected = lab02_summary.get("hashes", {}).get(key)
        actual = hashlib.sha256((lab02_root / filename).read_bytes()).hexdigest()
        if expected != actual:
            raise RuntimeError(f"Lab 02 artifact hash mismatch: {filename}")

    lab03_root = ROOT / "results/lab03/behavioral-baselines"
    lab03_summary = json.loads((lab03_root / "summary.json").read_text(encoding="utf-8"))
    if lab03_summary.get("evidence_eligible") is not False or lab03_summary.get("claim_ids") != []:
        raise RuntimeError("Lab 03 evidence boundary is invalid")
    if lab03_summary.get("empirical") is not False or lab03_summary.get("status") != "fail":
        raise RuntimeError("Lab 03 smoke fixture must remain non-empirical and not ready")
    if lab03_summary.get("interpretation") != "diagnostic_only_not_scientifically_interpretable":
        raise RuntimeError("Lab 03 smoke metrics are not clearly marked diagnostic-only")
    expected_gate_status = {
        "B1": "fail",
        "B2": "fail",
        "B3": "pass",
        "B4": "fail",
        "B5": "pass",
        "B6": "fail",
        "B7": "fail",
        "B8": "pass",
    }
    observed_gate_status = {row.get("gate"): row.get("status") for row in lab03_summary.get("gates", [])}
    if observed_gate_status != expected_gate_status:
        raise RuntimeError(f"Lab 03 gate state changed: {observed_gate_status}")
    for key, path in {
        "baseline_jsonl": lab03_root / "baseline_result.json",
        "report_html": lab03_root / "report.html",
        "cases_hash": ROOT / "data/pilot/cases.jsonl",
        "snapshot_hash": ROOT / "results/lab02/dataset-anatomy/snapshot_manifest.json",
        "config_hash": ROOT / "experiments/lab03-behavioral-baselines/config.json",
    }.items():
        expected = lab03_summary.get("hashes", {}).get(key)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected != actual:
            raise RuntimeError(f"Lab 03 artifact hash mismatch: {path.name}")

    lab04_root = ROOT / "results/lab04/decodability"
    lab04_summary_path = lab04_root / "summary.json"
    if lab04_summary_path.exists():
        run(
            PYTHON,
            "-m",
            "latent_triz.cli",
            "validate",
            "--schema",
            "schemas/lab04-result.schema.json",
            str(lab04_summary_path),
        )
        lab04_summary = json.loads(lab04_summary_path.read_text(encoding="utf-8"))
        if lab04_summary.get("empirical") is not False:
            raise RuntimeError("Lab 04 fixture is unexpectedly empirical")
        if lab04_summary.get("evidence_eligible") is not False:
            raise RuntimeError("Lab 04 evidence eligibility is incorrectly true")
        if lab04_summary.get("claim_ids") != []:
            raise RuntimeError("Lab 04 claim ids are not empty")
        if lab04_summary.get("interpretation") != "diagnostic_only_not_scientifically_interpretable":
            raise RuntimeError("Lab 04 interpretation is not diagnostic-only")
        if lab04_summary.get("status") != "fail":
            raise RuntimeError("Lab 04 smoke fixture must remain non-ready")

        for key, path in {
            "probe_result_json": lab04_root / "probe_result.json",
            "report_html": lab04_root / "report.html",
            "cases_jsonl": ROOT / "data/pilot/cases.jsonl",
            "representations_jsonl": ROOT / "data/pilot/representations.jsonl",
            "config_json": ROOT / "experiments/lab04-decodability/config.json",
        }.items():
            if not path.exists():
                continue
            expected = lab04_summary.get("hashes", {}).get(key)
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if expected and expected != actual:
                raise RuntimeError(f"Lab 04 artifact hash mismatch: {path.name}")

    with tempfile.TemporaryDirectory() as directory:
        suite_root = Path(directory) / "repository"
        suite_inputs = (
            "results/lab01/model-anatomy/parity_report.json",
            "results/lab01/model-anatomy/report.html",
            "results/lab02/dataset-anatomy/summary.json",
            "results/lab02/dataset-anatomy/report.html",
            "results/lab03/behavioral-baselines/summary.json",
            "results/lab03/behavioral-baselines/report.html",
            "results/lab04/decodability/summary.json",
            "results/lab04/decodability/report.html",
        )
        for relative in suite_inputs:
            destination = suite_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        lab_suite_output = suite_root / "artifacts/lab/index.html"
        command = (
            PYTHON, "-m", "latent_triz.cli", "lab-suite",
            "--root", str(suite_root), "--output", "artifacts/lab/index.html",
        )
        run(*command)
        first_lab_suite = lab_suite_output.read_bytes()
        run(*command)
        if lab_suite_output.read_bytes() != first_lab_suite:
            raise RuntimeError("Lab Suite dashboard is not byte-stable")

    run(
        PYTHON,
        "-m",
        "latent_triz.cli",
        "model-preflight",
        "--manifest",
        "experiments/001-stage1-pilot/model-candidates.jsonl",
    )
    run(
        PYTHON,
        "-m",
        "latent_triz.cli",
        "dataset-audit",
        "--plan",
        "experiments/001-stage1-pilot/dataset-plan.json",
        "--cases",
        "data/pilot/cases.jsonl",
        "--mode",
        "development",
    )

    print("repository-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
