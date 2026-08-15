"""Deterministic publication report and manifest generator for A0-R2."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .validator import validate


class A0R2ReportError(RuntimeError):
    """Raised when an A0-R2 publication report cannot be produced safely."""


EPISTEMIC = {
    "empirical": True,
    "scientific_status": "exploratory",
    "evidence_eligible": False,
    "expert_validated": False,
    "claim_ids": [],
}

REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = REPO_ROOT / "experiments/a0r2-independent-model/study-protocol.json"
SCHEMA_ROOT = REPO_ROOT / "schemas"
RESULT_STATISTICAL_FILE = "statistical-result.json"
RESULT_FAILURE_FILE = "run-failure.json"
ACTIVATION_RECEIPT_FILE = "activation-receipt.json"
REPRESENTATION_INDEX_FILE = "representations-index.jsonl"
REPORT_FILE = "report.md"
MANIFEST_FILE = "publication-manifest.json"
TERMINAL_STATUSES = ("positive", "null", "failed", "non_interpretable", "incompatible")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _primary_payload(result: Mapping[str, Any]) -> Mapping[str, Any]:
    descriptive_results = result.get("descriptive_results")
    if isinstance(descriptive_results, Mapping):
        primary = descriptive_results.get("primary")
        if isinstance(primary, Mapping):
            return primary
    primary_endpoint = result.get("primary_endpoint")
    if isinstance(primary_endpoint, Mapping):
        return primary_endpoint
    raise A0R2ReportError("statistical result is missing a primary payload")


def _has_activation_artifacts(result: Mapping[str, Any]) -> bool:
    access = result.get("access")
    if not isinstance(access, Mapping):
        return False
    return access.get("model_output_accessed") is True and access.get("sealed_targets_accessed") is True


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R2ReportError(f"cannot read JSON object: {path}") from exc
    if not isinstance(payload, dict):
        raise A0R2ReportError(f"{path.name} must contain a JSON object")
    return payload


def _read_json_schema(path: Path) -> dict[str, Any]:
    schema = _read_json(path)
    if schema.get("$schema") is None:
        raise A0R2ReportError(f"{path} is not a valid JSON schema")
    return schema


def _validate_schema(payload: dict[str, Any], schema: dict[str, Any], *, label: str) -> None:
    issues = validate(payload, schema)
    if issues:
        raise A0R2ReportError(f"{label} schema validation failed")


def _must_be_relative(label: str, value: str | Path) -> Path:
    path = value if isinstance(value, Path) else Path(value)
    if path.is_absolute():
        raise A0R2ReportError(f"{label} must be a relative path")
    if ".." in path.parts:
        raise A0R2ReportError(f"{label} must not contain path traversal")
    return path


def _validate_relative_path(label: str, value: str) -> None:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise A0R2ReportError(f"{label} must be a repository-relative path")


def _write_pair_atomic(items: tuple[tuple[Path, bytes], ...]) -> None:
    if any(path.exists() for path, _ in items):
        raise A0R2ReportError("refuse overwrite: publication output already exists")
    temp_paths: list[Path] = []
    linked_paths: list[Path] = []
    try:
        for path, content in items:
            with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False, suffix=".tmp") as stream:
                stream.write(content)
                temp_path = Path(stream.name)
            temp_paths.append(temp_path)
            os.link(temp_path, path)
            linked_paths.append(path)
    except Exception as exc:  # pragma: no cover
        for linked_path in linked_paths:
            linked_path.unlink(missing_ok=True)
        raise A0R2ReportError("cannot atomically persist publication package") from exc
    finally:
        for temp_path in temp_paths:
            temp_path.unlink(missing_ok=True)


def _load_protocol() -> dict[str, Any]:
    protocol = _read_json(PROTOCOL_PATH)
    _validate_schema(protocol, _read_json_schema(SCHEMA_ROOT / "a0r2-study-protocol.schema.json"), label="protocol")
    return protocol


def _find_result_path(package_dir: Path) -> tuple[Path, dict[str, Any], str]:
    candidates = [package_dir / RESULT_STATISTICAL_FILE, package_dir / RESULT_FAILURE_FILE]
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        raise A0R2ReportError("missing required result file")
    if len(existing) > 1:
        raise A0R2ReportError("ambiguous result file set")
    result_path = existing[0]
    result = _read_json(result_path)
    artifact_class = str(result.get("artifact_class", ""))
    status = str(result.get("status", ""))
    if artifact_class == "a0r2-statistical-result":
        _validate_schema(result, _read_json_schema(SCHEMA_ROOT / "a0r2-statistical-result.schema.json"), label="statistical-result")
        if status not in {"positive", "null", "non_interpretable", "incompatible"}:
            raise A0R2ReportError("status mismatch for statistical result")
        return result_path, result, "statistical"
    if artifact_class == "a0r2-run-failure":
        _validate_schema(result, _read_json_schema(SCHEMA_ROOT / "a0r2-run-failure.schema.json"), label="run-failure")
        if status != "failed":
            raise A0R2ReportError("status mismatch for run failure")
        return result_path, result, "failure"
    raise A0R2ReportError("unknown result artifact class")


def _access_label(value: Any) -> str:
    if isinstance(value, bool):
        return "accessed" if value else "not_accessed"
    return str(value)


def _build_report_text(
    *,
    created_at: str,
    package_name: str,
    protocol: dict[str, Any],
    result: dict[str, Any],
    result_path: Path,
    result_hash: str,
    protocol_hash: str,
    activation_receipt: dict[str, Any] | None = None,
    activation_receipt_hash: str | None = None,
    index_hash: str | None = None,
    dense_path: Path | None = None,
    dense_hash: str | None = None,
    dense_bytes: int | None = None,
) -> str:
    terminal_status = str(result["status"])
    result_kind = str(result["artifact_class"])
    run_access = result.get("access", {})
    publication_access = "not_accessed"

    lines = [
        "# Latent TRIZ A0-R2 exploratory publication report",
        "",
        f"- Created: {created_at}",
        f"- Terminal status: `{terminal_status}`",
        f"- Result artifact: `{result_kind}`",
        f"- Result file: `{result_path.name}`",
        f"- Result hash: `{result_hash}`",
        f"- Protocol path: `{str(PROTOCOL_PATH.relative_to(REPO_ROOT))}`",
        f"- Protocol hash: `{protocol_hash}`",
        f"- Publication manifest: `{MANIFEST_FILE}`",
        "",
        "## Access states",
        "",
        f"- Result model output access: `{_access_label(run_access.get('model_output_accessed'))}`",
        f"- Result sealed-target access: `{_access_label(run_access.get('sealed_targets_accessed'))}`",
        f"- Publication access: `{publication_access}`",
        "",
        "## Epistemic boundary",
        "",
        "- Automated exploratory E0 packaging only.",
        "- No human or expert validation is claimed.",
        "- Null and failed outcomes are published equally with positive and incompatible outcomes.",
        "- This report does not claim TRIZ rediscovery, novelty, or expert validity.",
    ]

    if activation_receipt is not None:
        dense_locator = str(activation_receipt["output_bundle"]["dense_locator"])
        lines.extend(
            [
                "",
                "## Activation bundle",
                "",
                f"- Activation receipt hash: `{activation_receipt_hash}`",
                f"- Representation index hash: `{index_hash}`",
                f"- External dense locator: `{dense_locator}`",
                f"- External dense hash: `{dense_hash}`",
                f"- External dense bytes: `{dense_bytes}`",
            ]
        )

    if result_kind == "a0r2-run-failure":
        failure = result["failure"]
        lines.extend(
            [
                "",
                "## Failure summary",
                "",
                f"- Failure stage: `{failure['stage']}`",
                f"- Failure kind: `{failure['failure_kind']}`",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Statistical summary",
                "",
                f"- Primary permutation p-value: `{float(result['statistics']['primary_permutation_p']):.6f}`",
                f"- Macro-F1 margin over surface: `{float(result['statistics']['macro_f1_margin_over_surface']):.6f}`",
                f"- Family successes: `{int(result['statistics']['family_successes'])}`",
                f"- Successful domain directions: `{int(result['statistics']['successful_domain_directions'])}`",
                f"- Primary report hash: `{result['artifact_hashes']['primary_sha256']}`",
                f"- Statistics report hash: `{result['artifact_hashes']['statistics_sha256']}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Publication manifest",
            "",
            f"- Manifest file: `{MANIFEST_FILE}`",
            f"- Manifest path: `{package_name}/{MANIFEST_FILE}`",
        ]
    )
    return "\n".join(lines) + "\n"


def generate_a0r2_report(
    *,
    package_dir: str | Path,
    external_dense_dir: str | Path,
    created_at: str,
) -> tuple[Path, Path]:
    package_dir = _must_be_relative("package_dir", package_dir)
    external_dense_dir = _must_be_relative("external_dense_dir", external_dense_dir)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", created_at):
        raise A0R2ReportError("created_at must be an explicit UTC timestamp")

    expected_external = Path("artifacts") / "a0r2" / package_dir.name
    if external_dense_dir != expected_external:
        raise A0R2ReportError("external dense directory must be artifacts/a0r2/<run_id>")

    if not package_dir.is_dir():
        raise A0R2ReportError(f"package directory missing: {package_dir}")

    result_path, result, result_kind = _find_result_path(package_dir)

    protocol = _load_protocol()
    result_hash = _sha256(result_path)
    protocol_hash = _sha256(PROTOCOL_PATH)
    activation_accessed = _has_activation_artifacts(result)
    if result_kind == "statistical" and not activation_accessed:
        raise A0R2ReportError("statistical result requires activation artifacts")
    if result_kind == "failure" and activation_accessed:
        raise A0R2ReportError("run failure must not claim activation artifacts")

    activation_receipt_path = package_dir / ACTIVATION_RECEIPT_FILE
    representation_index_path = package_dir / REPRESENTATION_INDEX_FILE
    activation_receipt: dict[str, Any] | None = None
    activation_receipt_hash: str | None = None
    index_hash: str | None = None
    dense_hash: str | None = None
    dense_bytes: int | None = None
    dense_path: Path | None = None

    if activation_accessed:
        if not activation_receipt_path.is_file():
            raise A0R2ReportError(f"missing required file: {activation_receipt_path}")
        if not representation_index_path.is_file():
            raise A0R2ReportError(f"missing required file: {representation_index_path}")

        dense_path = external_dense_dir / "activations.json"
        if not external_dense_dir.is_dir():
            raise A0R2ReportError(f"external dense directory missing: {external_dense_dir}")
        if not dense_path.is_file():
            raise A0R2ReportError(f"missing dense artifact: {dense_path}")

        activation_receipt = _read_json(activation_receipt_path)
        _validate_schema(
            activation_receipt,
            _read_json_schema(SCHEMA_ROOT / "a0r2-activation-receipt.schema.json"),
            label="activation-receipt",
        )
        activation_receipt_hash = _sha256(activation_receipt_path)
        index_hash = _sha256(representation_index_path)
        dense_hash = _sha256(dense_path)
        dense_bytes = dense_path.stat().st_size

    if str(result["protocol_id"]) != str(protocol["protocol_id"]):
        raise A0R2ReportError("result protocol id mismatch")
    model_keys = ("id", "revision", "license_id", "model_type", "architecture", "num_hidden_layers", "hidden_size", "local_locator")
    for key in model_keys:
        if result["model"][key] != protocol["model"][key]:
            raise A0R2ReportError(f"result model field mismatch: {key}")
        if activation_receipt is not None and activation_receipt["model"][key] != protocol["model"][key]:
            raise A0R2ReportError(f"activation model field mismatch: {key}")

    expected_locator = str(expected_external / "activations.json")
    if activation_accessed:
        if activation_receipt is None:
            raise A0R2ReportError("activation receipt missing")
        if activation_receipt["output_bundle"]["dense_locator"] != expected_locator:
            raise A0R2ReportError("activation dense locator mismatch")
    if result_kind == "statistical":
        if result["result_bundle"]["dense_locator"] != expected_locator:
            raise A0R2ReportError("result dense locator mismatch")
        if result["result_bundle"]["dense_locator_sha256"] != _canonical_json_sha256({"dense_locator": expected_locator}):
            raise A0R2ReportError("result dense locator hash mismatch")

        input_hashes = result.get("input_hashes", {})
        if input_hashes.get("protocol_sha256") != _sha256(PROTOCOL_PATH):
            raise A0R2ReportError("protocol hash mismatch")
        if input_hashes.get("activation_receipt_sha256") != activation_receipt_hash:
            raise A0R2ReportError("activation receipt hash mismatch")
        if input_hashes.get("representation_index_sha256") != index_hash:
            raise A0R2ReportError("representation index hash mismatch")
        if input_hashes.get("dense_vectors_sha256") != dense_hash:
            raise A0R2ReportError("dense hash mismatch")
        if result["artifact_hashes"]["primary_sha256"] != _canonical_json_sha256(_primary_payload(result)):
            raise A0R2ReportError("primary endpoint hash mismatch")
        if result["artifact_hashes"]["statistics_sha256"] != _canonical_json_sha256(result["statistics"]):
            raise A0R2ReportError("statistics hash mismatch")
    elif activation_accessed:
        raise A0R2ReportError("activation artifacts require a statistical result")
    else:
        if result["failure"]["stage"] not in {"integrity", "identity", "execution", "data", "receipt", "compatibility", "publication"}:
            raise A0R2ReportError("failure stage mismatch")

    if activation_accessed:
        if activation_receipt is None or index_hash is None or dense_hash is None or dense_path is None or activation_receipt_hash is None:
            raise A0R2ReportError("activation artifacts missing")
        if activation_receipt["output_bundle"]["artifact_hashes"]["index_sha256"] != index_hash:
            raise A0R2ReportError("activation index hash mismatch")
        if activation_receipt["output_bundle"]["artifact_hashes"]["dense_sha256"] != dense_hash:
            raise A0R2ReportError("activation dense hash mismatch")

    report_path = package_dir / REPORT_FILE
    manifest_path = package_dir / MANIFEST_FILE
    if report_path.exists() or manifest_path.exists():
        raise A0R2ReportError("refuse overwrite: report.md/publication-manifest.json exists")

    report_manifest = {
        "artifact_class": "a0r2-publication-manifest",
        **EPISTEMIC,
        "created_at": created_at,
        "protocol_id": protocol["protocol_id"],
        "status": str(result["status"]),
        "terminal_status": str(result["status"]),
        "protocol": {"path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)), "sha256": protocol_hash},
        "publication": {
            "publish_every_terminal_outcome": True,
            "sensitivity_may_rescue_primary": False,
            "model_substitution_after_output": False,
            "claim_promotion": False,
        },
        "result": {"path": result_path.name, "sha256": result_hash},
        "report": {"path": REPORT_FILE, "sha256": ""},
    }
    if activation_accessed:
        if activation_receipt_hash is None or index_hash is None or dense_hash is None:
            raise A0R2ReportError("activation artifacts missing for manifest")
        report_manifest["receipt"] = {"path": activation_receipt_path.name, "sha256": activation_receipt_hash}
        report_manifest["index"] = {"path": representation_index_path.name, "sha256": index_hash}
        report_manifest["dense"] = {
            "path": expected_locator,
            "sha256": dense_hash,
            "records": 1920,
            "hidden_size": int(protocol["model"]["hidden_size"]),
        }

    if result_kind == "statistical":
        report_present = REPORT_FILE in result["result_bundle"]["reports"]
    else:
        report_present = REPORT_FILE in result["reports"]
    if not report_present:
        raise A0R2ReportError("result package does not advertise report.md")

    _validate_relative_path("result.path", report_manifest["result"]["path"])
    _validate_relative_path("report.path", report_manifest["report"]["path"])
    _validate_relative_path("protocol.path", report_manifest["protocol"]["path"])
    if report_manifest["protocol"]["path"] != str(PROTOCOL_PATH.relative_to(REPO_ROOT)):
        raise A0R2ReportError("protocol path mismatch")
    if report_manifest["protocol"]["sha256"] != protocol_hash:
        raise A0R2ReportError("protocol hash mismatch")
    if activation_accessed:
        _validate_relative_path("receipt.path", report_manifest["receipt"]["path"])
        _validate_relative_path("index.path", report_manifest["index"]["path"])
        _validate_relative_path("dense.path", report_manifest["dense"]["path"])
        if report_manifest["dense"]["path"] != expected_locator:
            raise A0R2ReportError("dense locator mismatch")
    elif any(key in report_manifest for key in ("receipt", "index", "dense")):
        raise A0R2ReportError("activation artifacts must not be published for pre-activation failure")

    report_text = _build_report_text(
        created_at=created_at,
        package_name=package_dir.name,
        protocol=protocol,
        result=result,
        result_path=result_path,
        result_hash=result_hash,
        protocol_hash=protocol_hash,
        activation_receipt=activation_receipt,
        activation_receipt_hash=activation_receipt_hash,
        index_hash=index_hash,
        dense_path=dense_path,
        dense_hash=dense_hash,
        dense_bytes=dense_bytes,
    )
    report_manifest["report"]["sha256"] = hashlib.sha256(report_text.encode("utf-8")).hexdigest()
    _validate_schema(report_manifest, _read_json_schema(SCHEMA_ROOT / "a0r2-publication-manifest.schema.json"), label="publication-manifest")

    _write_pair_atomic(
        (
            (report_path, report_text.encode("utf-8")),
            (manifest_path, (json.dumps(report_manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")),
        )
    )
    return report_path, manifest_path


def verify_a0r2_publication(
    *,
    package_dir: str | Path,
    external_dense_dir: str | Path,
) -> dict[str, Any]:
    package_dir = _must_be_relative("package_dir", package_dir)
    external_dense_dir = _must_be_relative("external_dense_dir", external_dense_dir)
    expected_external = Path("artifacts") / "a0r2" / package_dir.name
    if external_dense_dir != expected_external:
        raise A0R2ReportError("external dense directory does not match run id")

    manifest_path = package_dir / MANIFEST_FILE
    report_path = package_dir / REPORT_FILE
    if not manifest_path.is_file() or not report_path.is_file():
        raise A0R2ReportError("publication manifest or report is missing")

    manifest = _read_json(manifest_path)
    _validate_schema(manifest, _read_json_schema(SCHEMA_ROOT / "a0r2-publication-manifest.schema.json"), label="publication-manifest")

    result_path = package_dir / manifest["result"]["path"]

    for field, path in (
        ("result", result_path),
        ("report", report_path),
    ):
        if not path.is_file():
            raise A0R2ReportError(f"publication path missing: {field}")

    result = _read_json(result_path)
    report_hash = _sha256(report_path)

    if manifest["result"]["sha256"] != _sha256(result_path):
        raise A0R2ReportError("result hash mismatch")
    if manifest["report"]["sha256"] != report_hash:
        raise A0R2ReportError("report hash mismatch")
    if manifest["publication"] != {
        "publish_every_terminal_outcome": True,
        "sensitivity_may_rescue_primary": False,
        "model_substitution_after_output": False,
        "claim_promotion": False,
    }:
        raise A0R2ReportError("publication policy mismatch")
    if manifest["status"] != manifest["terminal_status"]:
        raise A0R2ReportError("terminal status mismatch")

    protocol = _load_protocol()
    if manifest["protocol_id"] != protocol["protocol_id"]:
        raise A0R2ReportError("protocol id mismatch")
    if manifest["protocol"]["path"] != str(PROTOCOL_PATH.relative_to(REPO_ROOT)):
        raise A0R2ReportError("protocol path mismatch")
    if manifest["protocol"]["sha256"] != _sha256(PROTOCOL_PATH):
        raise A0R2ReportError("protocol hash mismatch")
    if result["protocol_id"] != protocol["protocol_id"]:
        raise A0R2ReportError("result protocol id mismatch")

    activation_accessed = _has_activation_artifacts(result)
    receipt_path: Path | None = None
    index_path: Path | None = None
    dense_path: Path | None = None
    activation_receipt: dict[str, Any] | None = None
    if activation_accessed:
        if any(key not in manifest for key in ("receipt", "index", "dense")):
            raise A0R2ReportError("activation artifacts missing for statistical result")
        receipt_path = package_dir / manifest["receipt"]["path"]
        index_path = package_dir / manifest["index"]["path"]
        dense_path = Path(manifest["dense"]["path"])

        for field, path in (("receipt", receipt_path), ("index", index_path)):
            if not path.is_file():
                raise A0R2ReportError(f"publication path missing: {field}")

        if dense_path != external_dense_dir / "activations.json":
            raise A0R2ReportError("external dense locator mismatch")
        if not dense_path.is_file():
            raise A0R2ReportError("dense publication artifact is missing")

        activation_receipt = _read_json(receipt_path)
        _validate_schema(activation_receipt, _read_json_schema(SCHEMA_ROOT / "a0r2-activation-receipt.schema.json"), label="activation-receipt")
        activation_receipt_hash = _sha256(receipt_path)
        index_hash = _sha256(index_path)
        dense_hash = _sha256(dense_path)

    if result["artifact_class"] == "a0r2-statistical-result":
        if result["status"] != manifest["terminal_status"]:
            raise A0R2ReportError("statistical result status mismatch")
        if result["input_hashes"]["protocol_sha256"] != _sha256(PROTOCOL_PATH):
            raise A0R2ReportError("protocol hash mismatch")
        if receipt_path is None or index_path is None or dense_path is None:
            raise A0R2ReportError("activation artifacts missing for statistical result")
        if result["input_hashes"]["activation_receipt_sha256"] != activation_receipt_hash:
            raise A0R2ReportError("activation receipt input hash mismatch")
        if result["input_hashes"]["representation_index_sha256"] != index_hash:
            raise A0R2ReportError("representation index input hash mismatch")
        if result["input_hashes"]["dense_vectors_sha256"] != dense_hash:
            raise A0R2ReportError("dense input hash mismatch")
        expected_locator = manifest["dense"]["path"]
        if result["result_bundle"]["dense_locator"] != expected_locator:
            raise A0R2ReportError("result dense locator mismatch")
        if result["result_bundle"]["dense_locator_sha256"] != _canonical_json_sha256({"dense_locator": expected_locator}):
            raise A0R2ReportError("result dense locator hash mismatch")
    elif result["artifact_class"] == "a0r2-run-failure":
        if result["status"] not in {"failed", "incompatible"} or manifest["terminal_status"] != result["status"]:
            raise A0R2ReportError("run failure status mismatch")
        if any(key in manifest for key in ("receipt", "index", "dense")):
            raise A0R2ReportError("activation artifacts must not be published for run failure")
    else:
        raise A0R2ReportError("unknown result artifact class")

    if activation_accessed:
        if activation_receipt is None or receipt_path is None or index_path is None or dense_path is None:
            raise A0R2ReportError("activation artifacts missing")
        if manifest["receipt"]["sha256"] != activation_receipt_hash:
            raise A0R2ReportError("activation receipt hash mismatch")
        if manifest["index"]["sha256"] != index_hash:
            raise A0R2ReportError("representation index hash mismatch")
        if manifest["dense"]["sha256"] != dense_hash:
            raise A0R2ReportError("dense hash mismatch")
        if manifest["dense"]["path"] != str(dense_path):
            raise A0R2ReportError("dense path mismatch")
        if manifest["dense"]["records"] != 1920:
            raise A0R2ReportError("dense record count mismatch")
        if manifest["dense"]["hidden_size"] != 960:
            raise A0R2ReportError("dense hidden size mismatch")
        if activation_receipt["output_bundle"]["dense_locator"] != manifest["dense"]["path"]:
            raise A0R2ReportError("activation dense locator mismatch")
        if activation_receipt["output_bundle"]["artifact_hashes"]["index_sha256"] != _sha256(index_path):
            raise A0R2ReportError("activation index hash mismatch")
        if activation_receipt["output_bundle"]["artifact_hashes"]["dense_sha256"] != _sha256(dense_path):
            raise A0R2ReportError("activation dense hash mismatch")
    elif any(key in manifest for key in ("receipt", "index", "dense")):
        raise A0R2ReportError("pre-activation failure cannot publish activation artifacts")

    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate and verify the A0-R2 publication package.")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--external-dense-dir", required=True)
    parser.add_argument("--created-at", default=None)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)

    if args.verify_only:
        verify_a0r2_publication(package_dir=args.package_dir, external_dense_dir=args.external_dense_dir)
    else:
        if args.created_at is None:
            raise SystemExit("--created-at is required unless --verify-only is set")
        generate_a0r2_report(
            package_dir=args.package_dir,
            external_dense_dir=args.external_dense_dir,
            created_at=args.created_at,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
