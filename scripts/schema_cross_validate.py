#!/usr/bin/env python3
"""Cross-check tracked schemas and instances with the reference validator."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.validator import validate as validate_minimal  # noqa: E402


VALIDATION_PAIRS = (
    ("schemas/case.schema.json", "tests/fixtures/case_valid.json"),
    ("schemas/study.schema.json", "experiments/000-template/manifest.json"),
    ("schemas/study.schema.json", "experiments/001-stage1-pilot/manifest.json"),
    ("schemas/run.schema.json", "experiments/000-template/run.json"),
    ("schemas/dataset-registry.schema.json", "data/registry.json"),
    ("schemas/claim.schema.json", "data/claims.jsonl"),
    ("schemas/dataset-plan.schema.json", "experiments/001-stage1-pilot/dataset-plan.json"),
    ("schemas/model-candidate.schema.json", "experiments/001-stage1-pilot/model-candidates.jsonl"),
    ("schemas/lab01-manifest.schema.json", "experiments/lab01-model-anatomy/manifest.json"),
    ("schemas/lab01-model-receipt.schema.json", "results/lab01/model-anatomy/model_receipt.json"),
    ("schemas/lab01-run.schema.json", "results/lab01/model-anatomy/run.json"),
    ("schemas/dataset-annotation.schema.json", "data/pilot/dataset-annotations.jsonl"),
    ("schemas/annotation-guide.schema.json", "experiments/001-stage1-pilot/annotation-guide.json"),
    ("schemas/candidate-batch.schema.json", "data/candidates/wave1-manifest.json"),
    ("schemas/case.schema.json", "data/candidates/wave1-model-generated.jsonl"),
    ("schemas/dataset-snapshot.schema.json", "results/lab02/dataset-anatomy/snapshot_manifest.json"),
    ("schemas/lab03-config.schema.json", "experiments/lab03-behavioral-baselines/config.json"),
    ("schemas/lab03-config.schema.json", "experiments/wave1-surface-audit/config.json"),
    ("schemas/lab03-result.schema.json", "results/lab03/behavioral-baselines/summary.json"),
    ("schemas/lab03-result.schema.json", "results/wave1/surface-audit/summary.json"),
    ("schemas/lab04-config.schema.json", "experiments/lab04-decodability/config.json"),
    ("schemas/lab04-result.schema.json", "results/lab04/decodability/summary.json"),
    ("schemas/representation-record.schema.json", "data/pilot/representations.jsonl"),
    ("schemas/lab05-config.schema.json", "experiments/lab05-candidate-directions/config.json"),
    ("schemas/lab05-result.schema.json", "results/lab05/candidate-directions/summary.json"),
    ("schemas/a0-protocol.schema.json", "experiments/a0-automated-weak-proxy/protocol.json"),
    ("schemas/a0r1-protocol.schema.json", "experiments/a0r1-independent-proxy/protocol.json"),
    ("schemas/a0-corpus-manifest.schema.json", "data/a0/manifest.json"),
    ("schemas/a0-case.schema.json", "data/a0/cases.jsonl"),
    ("schemas/a0-procedural-target.schema.json", "data/a0/procedural-targets/calibration-targets.jsonl"),
    ("schemas/a0-procedural-target.schema.json", "data/a0/sealed-targets/targets.jsonl"),
    ("schemas/a0-power-calibration.schema.json", "results/a0/calibration/power.json"),
    ("schemas/a0-shortcut-audit.schema.json", "results/a0/calibration/shortcuts.json"),
    ("schemas/a0-calibration-summary.schema.json", "results/a0/calibration/summary.json"),
    ("schemas/a0-freeze-manifest.schema.json", "results/a0/calibration/freeze-manifest.json"),
    ("schemas/a0-activation-receipt.schema.json", "results/a0/a0-v1.0.3-e93a9faa/activation-receipt.json"),
    ("schemas/a0-statistical-result.schema.json", "results/a0/a0-v1.0.3-e93a9faa/statistical-result.json"),
    ("schemas/a0-publication-manifest.schema.json", "results/a0/a0-v1.0.3-e93a9faa/publication-manifest.json"),
)


def _lab04_mutations(instance: Any) -> Iterable[tuple[str, Any]]:
    short_hash = deepcopy(instance)
    short_hash["hashes"]["cases_jsonl"] = "a" * 63
    yield "sha256_63_characters", short_hash

    missing_predecessor_hash = deepcopy(instance)
    missing_predecessor_hash["predecessors"]["lab01"].pop("summary_sha256")
    yield "predecessor_missing_summary_sha256", missing_predecessor_hash

    zero_alpha = deepcopy(instance)
    zero_alpha["random_control"]["max_statistic"]["configured_alpha"] = 0
    yield "exclusive_minimum_zero", zero_alpha

    mismatched_solver = deepcopy(instance)
    mismatched_solver["config"].update(
        numeric_backend="numpy",
        numeric_solver="pure_python_normal_equations_reference",
        numeric_library_version="2.4.3",
    )
    yield "numpy_backend_python_solver", mismatched_solver


def _instances(path: Path) -> Iterable[tuple[int, Any]]:
    if path.suffix == ".jsonl":
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.strip():
                yield line_number, json.loads(line)
        return
    yield 1, json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    for schema_path in sorted((ROOT / "schemas").glob("*.json")):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            errors.append(f"{schema_path.relative_to(ROOT)}: invalid Draft 2020-12 schema: {exc}")

    for schema_name, instance_name in VALIDATION_PAIRS:
        schema = json.loads((ROOT / schema_name).read_text(encoding="utf-8"))
        reference = Draft202012Validator(schema)
        for line_number, instance in _instances(ROOT / instance_name):
            minimal_errors = validate_minimal(instance, schema)
            reference_errors = list(reference.iter_errors(instance))
            if minimal_errors or reference_errors:
                errors.append(
                    f"{instance_name}:{line_number}: minimal={len(minimal_errors)} "
                    f"reference={len(reference_errors)}"
                )

    lab04_schema = json.loads((ROOT / "schemas/lab04-result.schema.json").read_text(encoding="utf-8"))
    lab04_result = json.loads((ROOT / "results/lab04/decodability/summary.json").read_text(encoding="utf-8"))
    lab04_reference = Draft202012Validator(lab04_schema)
    for mutation_name, mutation in _lab04_mutations(lab04_result):
        minimal_rejects = bool(validate_minimal(mutation, lab04_schema))
        reference_rejects = bool(list(lab04_reference.iter_errors(mutation)))
        if not minimal_rejects or not reference_rejects:
            errors.append(
                f"mutation {mutation_name}: minimal_rejects={minimal_rejects} "
                f"reference_rejects={reference_rejects}"
            )

    if errors:
        for error in errors:
            print(f"schema-cross-validate: {error}", file=sys.stderr)
        return 1
    print(
        f"schema-cross-validate: {len(VALIDATION_PAIRS)} tracked pairs agree; "
        "4 mutations rejected by both validators"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
