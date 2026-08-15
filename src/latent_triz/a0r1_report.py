"""Publication report and manifest generator for A0-R1 domain-prefix recovery."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .validator import validate
from .a0r1_recovery import _restore_prefixes

EPISTEMIC = {
    "empirical": True,
    "scientific_status": "exploratory",
    "evidence_eligible": False,
    "expert_validated": False,
    "claim_ids": [],
}

RAW_FILE = "statistical-result.raw.json"
RECOVERED_FILE = "statistical-result.json"
RECOVERY_RECEIPT_FILE = "recovery-receipt.json"
ACTIVATION_RECEIPT_FILE = "activation-receipt.json"
REPRESENTATIONS_INDEX_FILE = "representations-index.jsonl"
REPORT_FILE = "report.md"
MANIFEST_FILE = "publication-manifest.json"

class A0R1ReportError(RuntimeError):
    """Raised when the A0-R1 report cannot be produced safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise A0R1ReportError(f"{path} must contain a JSON object")
    return payload


def _read_json_schema(path: Path) -> dict[str, Any]:
    schema = _read_json(path)
    if "type" not in schema:
        raise A0R1ReportError(f"{path} is not a valid schema")
    return schema


def _validate_schema(payload: dict[str, Any], schema: dict[str, Any], *, label: str) -> None:
    issues = validate(payload, schema)
    if issues:
        raise A0R1ReportError(f"{label} schema validation failed")


def _must_be_relative(label: str, value: str | Path) -> Path:
    path = value if isinstance(value, Path) else Path(value)
    if path.is_absolute():
        raise A0R1ReportError(f"{label} must be a relative path")
    if ".." in path.parts:
        raise A0R1ReportError(f"{label} must not contain path traversal")
    return path


def _validate_path_relative(path_value: str, label: str) -> None:
    path = Path(path_value)
    if path.is_absolute() or ".." in path.parts:
        raise A0R1ReportError(f"{label} must be a repository-relative path")


def _load_results_paths(package_dir: Path) -> tuple[Path, Path, Path, Path, Path]:
    raw_path = package_dir / RAW_FILE
    recovered_path = package_dir / RECOVERED_FILE
    recovery_receipt_path = package_dir / RECOVERY_RECEIPT_FILE
    activation_receipt_path = package_dir / ACTIVATION_RECEIPT_FILE
    representations_index_path = package_dir / REPRESENTATIONS_INDEX_FILE
    for path in (
        raw_path,
        recovered_path,
        recovery_receipt_path,
        activation_receipt_path,
        representations_index_path,
    ):
        if not path.exists():
            raise A0R1ReportError(f"missing required file: {path}")
        if not path.is_file():
            raise A0R1ReportError(f"required path must be file: {path}")
    return (
        raw_path,
        recovered_path,
        recovery_receipt_path,
        activation_receipt_path,
        representations_index_path,
    )


def _build_report_text(result: dict[str, Any], created_at: str) -> str:
    status = str(result["status"])
    p = float(result["primary_permutation_p"])
    margin = float(result["macro_f1_margin_over_surface"])
    families = int(result["primary"]["family_successes"])
    observed = int(result["max_family_successes_observed"])
    domain_count = len(result["primary"]["per_domain_accuracy"])

    return (
        "# Latent TRIZ A0-R1 clerical publication report\n\n"
        f"- Created: {created_at}\n"
        f"- Result status: {status}\n"
        "- Recovery operation: domain-prefix clerical fix of 54 labels (`r1_<domain>` -> `<domain>`).\n"
        "- Metric values are unchanged by recovery (`metric_values_changed = false`).\n\n"
        "## Aggregate metrics\n\n"
        f"- primary permutation p-value: `{p:.6f}`\n"
        f"- macro-F1 margin over surface: `{margin:.6f}`\n"
        f"- primary family successes: `{families}`\n"
        f"- maximum observed family successes: `{observed}`\n"
        f"- domains represented: `{domain_count}`\n\n"
        "## Limits\n\n"
        "- This is an exploratory artifact with E0 evidence profile.\n"
        "- No TRIZ expert validation is claimed.\n"
        "- This artifact only supports reproducibility checks for a weak proxy test.\n"
        "- It does not establish TRIZ rediscovery, novelty, or expert validity.\n"
    )


def _stable_dump(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _write_pair_atomic(items: tuple[tuple[Path, bytes], ...]) -> None:
    if any(path.exists() for path, _ in items):
        raise A0R1ReportError("refuse overwrite: publication output already exists")
    temp_paths: list[Path] = []
    linked_paths: list[Path] = []
    try:
        for path, content in items:
            with tempfile.NamedTemporaryFile(
                "wb", dir=path.parent, delete=False, suffix=".tmp"
            ) as stream:
                stream.write(content)
                temp_path = Path(stream.name)
            temp_paths.append(temp_path)
            os.link(temp_path, path)
            linked_paths.append(path)
    except Exception as exc:
        for linked_path in linked_paths:
            linked_path.unlink(missing_ok=True)
        raise A0R1ReportError("cannot atomically persist publication package") from exc
    finally:
        for temp_path in temp_paths:
            temp_path.unlink(missing_ok=True)


def generate_a0r1_report(
    *,
    package_dir: str | Path,
    external_activation_dir: str | Path,
    created_at: str,
) -> tuple[Path, Path]:
    package_dir = _must_be_relative("package_dir", package_dir)
    external_activation_dir = _must_be_relative("external_activation_dir", external_activation_dir)
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", created_at
    ):
        raise A0R1ReportError("created_at must be an explicit UTC timestamp")

    expected_external = Path("artifacts") / "a0r1" / package_dir.name
    if external_activation_dir != expected_external:
        raise A0R1ReportError(
            "external activation directory must be artifacts/a0r1/<run_id> relative to repository root"
        )

    if not package_dir.is_dir():
        raise A0R1ReportError(f"package directory missing: {package_dir}")
    if not external_activation_dir.exists() or not external_activation_dir.is_dir():
        raise A0R1ReportError(f"external activation directory missing: {external_activation_dir}")

    raw_path, recovered_path, recovery_receipt_path, activation_receipt_path, representations_index_path = _load_results_paths(
        package_dir
    )

    dense_path = external_activation_dir / "activations.json"
    if not dense_path.exists() or not dense_path.is_file():
        raise A0R1ReportError(f"missing dense activation file: {dense_path}")

    schema_root = Path(__file__).resolve().parents[2] / "schemas"
    recovery_schema = _read_json_schema(schema_root / "a0r1-recovery-receipt.schema.json")
    result_schema = _read_json_schema(schema_root / "a0r1-statistical-result.schema.json")
    activation_schema = _read_json_schema(schema_root / "a0r1-activation-receipt.schema.json")
    manifest_schema = _read_json_schema(schema_root / "a0r1-publication-manifest.schema.json")

    raw_result = _read_json(raw_path)
    recovered_result = _read_json(recovered_path)
    recovery_receipt = _read_json(recovery_receipt_path)
    activation_receipt = _read_json(activation_receipt_path)

    _validate_schema(recovered_result, result_schema, label="statistical-result")
    _validate_schema(recovery_receipt, recovery_schema, label="recovery-receipt")
    _validate_schema(activation_receipt, activation_schema, label="activation-receipt")

    status = recovered_result.get("status")
    if status not in {"positive", "null"}:
        raise A0R1ReportError("result status must be positive or null")
    if raw_result.get("status") not in {"positive", "null"}:
        raise A0R1ReportError("raw status must be positive or null")

    raw_hash = _sha256(raw_path)
    recovered_hash = _sha256(recovered_path)
    index_hash = _sha256(representations_index_path)
    dense_hash = _sha256(dense_path)
    if recovery_receipt["raw_result"]["sha256"] != raw_hash:
        raise A0R1ReportError("recovery-receipt raw hash mismatch")
    if recovery_receipt["recovered_result"]["sha256"] != recovered_hash:
        raise A0R1ReportError("recovery-receipt recovered hash mismatch")
    if activation_receipt.get("dense_vectors", {}).get("sha256") != dense_hash:
        raise A0R1ReportError("dense vector hash mismatch")
    if activation_receipt.get("representation_index", {}).get("sha256") != index_hash:
        raise A0R1ReportError("representation index hash mismatch")

    input_hashes = recovered_result.get("input_hashes")
    if not isinstance(input_hashes, dict):
        raise A0R1ReportError("result input_hashes missing or invalid")
    if input_hashes.get("activation_receipt") != _sha256(activation_receipt_path):
        raise A0R1ReportError("input_hashes.activation_receipt mismatch")
    if input_hashes.get("dense_vectors") != dense_hash:
        raise A0R1ReportError("input_hashes.dense_vectors mismatch")
    if input_hashes.get("representation_index") != index_hash:
        raise A0R1ReportError("input_hashes.representation_index mismatch")

    if recovery_receipt["transformation"]["replacements_total"] != 54:
        raise A0R1ReportError("transformation replacements_total must be 54")
    if recovery_receipt["transformation"]["domains"] != 6:
        raise A0R1ReportError("transformation domains must be 6")
    recovery_code = Path(__file__).with_name("a0r1_recovery.py")
    if recovery_receipt["transformation"]["code_sha256"] != _sha256(recovery_code):
        raise A0R1ReportError("recovery code hash mismatch")

    if _restore_prefixes(recovered_result) != raw_result:
        raise A0R1ReportError("raw and recovered artifacts differ beyond domain-prefix renaming")

    report_path = package_dir / REPORT_FILE
    manifest_path = package_dir / MANIFEST_FILE
    if report_path.exists() or manifest_path.exists():
        raise A0R1ReportError("refuse overwrite: report.md/publication-manifest.json exists")

    report_text = _build_report_text(recovered_result, created_at)
    report_sha256 = hashlib.sha256(report_text.encode("utf-8")).hexdigest()

    manifest = {
        "artifact_class": "a0r1-publication-manifest",
        **EPISTEMIC,
        "created_at": created_at,
        "status": "pass",
        "result_status": status,
        "result": {
            "path": RAW_FILE,
            "sha256": raw_hash,
        },
        "recovered_result": {
            "path": RECOVERED_FILE,
            "sha256": recovered_hash,
        },
        "recovery_receipt": {
            "path": RECOVERY_RECEIPT_FILE,
            "sha256": _sha256(recovery_receipt_path),
        },
        "activation_receipt": {
            "path": ACTIVATION_RECEIPT_FILE,
            "sha256": _sha256(activation_receipt_path),
        },
        "representation_index": {
            "path": REPRESENTATIONS_INDEX_FILE,
            "sha256": index_hash,
        },
        "activation_dense": {
            "path": str(expected_external / "activations.json"),
            "sha256": dense_hash,
            "bytes": dense_path.stat().st_size,
        },
        "report": {
            "path": REPORT_FILE,
            "sha256": report_sha256,
        },
        "verification": {
            "status": "pass",
            "recovery": "pass",
            "required": True,
        },
        "publication_access": {
            "model_output": "not_accessed",
            "sealed_model_output": "not_accessed",
            "sealed_targets": "not_accessed",
        },
        "run_access": {
            "model_output": "accessed" if recovered_result["model_output_accessed"] else "not_accessed",
            "sealed_model_output": "accessed" if recovered_result["sealed_model_output_accessed"] else "not_accessed",
            "sealed_targets": "accessed" if recovered_result["sealed_targets_accessed"] else "not_accessed",
        },
        "result_metrics": {
            "macro_f1_margin_over_surface": recovered_result["macro_f1_margin_over_surface"],
            "primary_permutation_p": recovered_result["primary_permutation_p"],
            "max_family_successes_observed": recovered_result["max_family_successes_observed"],
            "domain_direction_success_count": recovered_result["domain_direction_success_count"],
        },
    }

    for key, path_value in (
        ("result.path", manifest["result"]["path"]),
        ("recovered_result.path", manifest["recovered_result"]["path"]),
        ("recovery_receipt.path", manifest["recovery_receipt"]["path"]),
        ("activation_receipt.path", manifest["activation_receipt"]["path"]),
        ("representation_index.path", manifest["representation_index"]["path"]),
        ("activation_dense.path", manifest["activation_dense"]["path"]),
        ("report.path", manifest["report"]["path"]),
    ):
        _validate_path_relative(path_value, key)

    _validate_schema(manifest, manifest_schema, label="publication-manifest")
    _write_pair_atomic(
        (
            (report_path, report_text.encode("utf-8")),
            (manifest_path, _stable_dump(manifest)),
        )
    )
    return report_path, manifest_path


def verify_a0r1_publication(
    *, package_dir: str | Path, external_activation_dir: str | Path
) -> dict[str, Any]:
    package_dir = _must_be_relative("package_dir", package_dir)
    external_activation_dir = _must_be_relative(
        "external_activation_dir", external_activation_dir
    )
    expected_external = Path("artifacts") / "a0r1" / package_dir.name
    if external_activation_dir != expected_external:
        raise A0R1ReportError("external activation directory does not match run id")

    manifest_path = package_dir / MANIFEST_FILE
    report_path = package_dir / REPORT_FILE
    if not manifest_path.is_file() or not report_path.is_file():
        raise A0R1ReportError("publication manifest or report is missing")
    schema_root = Path(__file__).resolve().parents[2] / "schemas"
    manifest = _read_json(manifest_path)
    _validate_schema(
        manifest,
        _read_json_schema(schema_root / "a0r1-publication-manifest.schema.json"),
        label="publication-manifest",
    )

    tracked = {
        "result": package_dir / RAW_FILE,
        "recovered_result": package_dir / RECOVERED_FILE,
        "recovery_receipt": package_dir / RECOVERY_RECEIPT_FILE,
        "activation_receipt": package_dir / ACTIVATION_RECEIPT_FILE,
        "representation_index": package_dir / REPRESENTATIONS_INDEX_FILE,
        "report": report_path,
    }
    for field, path in tracked.items():
        if not path.is_file() or manifest[field]["sha256"] != _sha256(path):
            raise A0R1ReportError(f"publication hash mismatch: {field}")
        _validate_path_relative(str(manifest[field]["path"]), f"{field}.path")

    dense_path = external_activation_dir / "activations.json"
    dense = manifest["activation_dense"]
    if dense["path"] != str(expected_external / "activations.json"):
        raise A0R1ReportError("external dense locator mismatch")
    if (
        not dense_path.is_file()
        or dense["sha256"] != _sha256(dense_path)
        or dense["bytes"] != dense_path.stat().st_size
    ):
        raise A0R1ReportError("external dense artifact mismatch")

    raw = _read_json(tracked["result"])
    result = _read_json(tracked["recovered_result"])
    recovery = _read_json(tracked["recovery_receipt"])
    activation = _read_json(tracked["activation_receipt"])
    _validate_schema(
        result,
        _read_json_schema(schema_root / "a0r1-statistical-result.schema.json"),
        label="statistical-result",
    )
    _validate_schema(
        recovery,
        _read_json_schema(schema_root / "a0r1-recovery-receipt.schema.json"),
        label="recovery-receipt",
    )
    _validate_schema(
        activation,
        _read_json_schema(schema_root / "a0r1-activation-receipt.schema.json"),
        label="activation-receipt",
    )
    if _restore_prefixes(result) != raw:
        raise A0R1ReportError("recovered result lineage mismatch")
    if recovery["raw_result"]["sha256"] != manifest["result"]["sha256"]:
        raise A0R1ReportError("raw recovery lineage mismatch")
    if recovery["recovered_result"]["sha256"] != manifest["recovered_result"]["sha256"]:
        raise A0R1ReportError("recovered lineage mismatch")
    if recovery["transformation"]["code_sha256"] != _sha256(
        Path(__file__).with_name("a0r1_recovery.py")
    ):
        raise A0R1ReportError("recovery code hash mismatch")
    if activation["dense_vectors"]["sha256"] != dense["sha256"]:
        raise A0R1ReportError("activation receipt dense hash mismatch")
    if activation["representation_index"]["sha256"] != manifest["representation_index"]["sha256"]:
        raise A0R1ReportError("activation receipt index hash mismatch")

    expected_metrics = {
        "macro_f1_margin_over_surface": result["macro_f1_margin_over_surface"],
        "primary_permutation_p": result["primary_permutation_p"],
        "max_family_successes_observed": result["max_family_successes_observed"],
        "domain_direction_success_count": result["domain_direction_success_count"],
    }
    if manifest["result_status"] != result["status"] or manifest["result_metrics"] != expected_metrics:
        raise A0R1ReportError("publication result summary mismatch")
    return {
        "artifact_class": "a0r1-publication-verification",
        "status": "pass",
        "result_status": result["status"],
        "tracked_files_verified": len(tracked),
        "external_dense_verified": True,
        "recovery_verified": True,
        **EPISTEMIC,
    }


def _run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="a0r1-report")
    parser.add_argument("--stage", choices=("generate", "verify"), default="generate")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--external-activation-dir", required=True)
    parser.add_argument("--created-at")
    args = parser.parse_args(argv)
    if args.stage == "verify":
        verify_a0r1_publication(
            package_dir=args.package_dir,
            external_activation_dir=args.external_activation_dir,
        )
        return 0
    if not args.created_at:
        raise A0R1ReportError("created_at is required for generation")
    generate_a0r1_report(
        package_dir=args.package_dir,
        external_activation_dir=args.external_activation_dir,
        created_at=args.created_at,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return _run_cli(argv)
    except A0R1ReportError:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
