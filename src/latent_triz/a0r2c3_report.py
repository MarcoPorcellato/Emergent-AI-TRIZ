"""Fail-closed C3 publication packaging for the analysis-only recovery.

This module deliberately does not alter the frozen A0-R2 reporter.  C3 uses
the immutable C2 dense asset in place, records its locator and digest, and
adds recovery provenance to a separate report.  It never loads a model or
opens sealed targets.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from . import a0r2_report as base
from .a0r2c3_analysis import EXPECTED_C2_INDEX_SHA256, EXPECTED_C2_RECORDS


class A0R2C3ReportError(base.A0R2ReportError):
    """Raised when a C3 publication package cannot be verified safely."""


REPORT_FILE = "report.md"
MANIFEST_FILE = "publication-manifest.json"
ACTIVATION_RECEIPT_FILE = "activation-receipt.json"
REPRESENTATION_INDEX_FILE = "representations-index.jsonl"
SOURCE_PREFIX = Path("artifacts") / "a0r2"
PACKAGE_PREFIX = Path("results") / "a0r2"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise A0R2C3ReportError(message)


def _relative_direct_child(label: str, value: str | Path, parent: Path) -> Path:
    path = base._must_be_relative(label, value)
    _require(path.parent == parent and bool(path.name), f"{label} must be a direct {parent}/<run-id> child")
    return path


def _read_index(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise A0R2C3ReportError(f"cannot read representation index: {path}") from exc
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise A0R2C3ReportError("representation index contains invalid JSON") from exc
        if not isinstance(row, dict):
            raise A0R2C3ReportError("representation index must contain JSON object rows")
        rows.append(row)
    return rows


def _validate_c3_index(index_path: Path, receipt: Mapping[str, Any]) -> str:
    """Validate the exact historical omission without rewriting source bytes."""

    index_hash = base._sha256(index_path)
    _require(index_hash == EXPECTED_C2_INDEX_SHA256, "C3 source representation index hash drift")
    bundle = receipt.get("output_bundle")
    runtime = receipt.get("runtime")
    _require(isinstance(bundle, Mapping) and isinstance(runtime, Mapping), "C3 activation receipt metadata is malformed")
    hashes = bundle.get("artifact_hashes")
    _require(isinstance(hashes, Mapping) and hashes.get("index_sha256") == index_hash, "C3 activation index receipt binding drift")
    _require(runtime.get("torch_dtype") == "float32", "C3 activation dtype binding drift")
    rows = _read_index(index_path)
    _require(len(rows) == EXPECTED_C2_RECORDS, "C3 source representation index record-count drift")
    _require(all("dtype" not in row for row in rows), "C3 source representation index recovery is inapplicable")
    return index_hash


def _validate_timestamp(created_at: str) -> None:
    _require(
        bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", created_at)),
        "created_at must be an explicit UTC timestamp",
    )


def _model_matches_protocol(payload: Mapping[str, Any], protocol: Mapping[str, Any], *, label: str) -> None:
    model = payload.get("model")
    _require(isinstance(model, Mapping), f"{label} model is malformed")
    expected = protocol["model"]
    for key in ("id", "revision", "license_id", "model_type", "architecture", "num_hidden_layers", "hidden_size", "local_locator"):
        _require(model.get(key) == expected[key], f"{label} model field mismatch: {key}")


def _result_report_advertised(result: Mapping[str, Any], result_kind: str) -> None:
    bundle = result.get("result_bundle") if result_kind == "statistical" else result.get("reports")
    reports = bundle.get("reports") if isinstance(bundle, Mapping) else bundle
    _require(isinstance(reports, list) and REPORT_FILE in reports, "C3 result package does not advertise report.md")


def _validate_result(
    *,
    result: Mapping[str, Any],
    result_kind: str,
    protocol: Mapping[str, Any],
    source_dense_locator: str,
    receipt_hash: str | None,
    index_hash: str | None,
    dense_hash: str | None,
) -> None:
    _require(result.get("protocol_id") == protocol["protocol_id"], "C3 result protocol id mismatch")
    _model_matches_protocol(result, protocol, label="C3 result")
    _result_report_advertised(result, result_kind)
    # A copied C2 receipt/index may exist for any C3 terminal outcome.  It
    # records the immutable predecessor asset; it must not be confused with
    # C3 itself having loaded a model or generated representations.
    source_artifacts_bound = receipt_hash is not None
    accessed = base._has_activation_artifacts(result)
    if result_kind == "statistical":
        _require(accessed, "C3 statistical result requires activation and target access")
        _require(receipt_hash is not None and index_hash is not None and dense_hash is not None, "C3 activation artifacts missing")
        bundle = result.get("result_bundle")
        hashes = result.get("input_hashes")
        artifact_hashes = result.get("artifact_hashes")
        _require(isinstance(bundle, Mapping) and isinstance(hashes, Mapping) and isinstance(artifact_hashes, Mapping), "C3 statistical result metadata is malformed")
        _require(bundle.get("dense_locator") == source_dense_locator, "C3 result dense locator mismatch")
        _require(bundle.get("dense_locator_sha256") == base._canonical_json_sha256({"dense_locator": source_dense_locator}), "C3 result dense locator hash mismatch")
        _require(hashes.get("protocol_sha256") == base._sha256(base.PROTOCOL_PATH), "C3 result protocol hash mismatch")
        _require(hashes.get("activation_receipt_sha256") == receipt_hash, "C3 result activation receipt hash mismatch")
        _require(hashes.get("representation_index_sha256") == index_hash, "C3 result representation index hash mismatch")
        _require(hashes.get("dense_vectors_sha256") == dense_hash, "C3 result dense hash mismatch")
        _require(artifact_hashes.get("primary_sha256") == base._canonical_json_sha256(base._primary_payload(result)), "C3 primary endpoint hash mismatch")
        _require(artifact_hashes.get("statistics_sha256") == base._canonical_json_sha256(result["statistics"]), "C3 statistics hash mismatch")
        return
    _require(result_kind == "failure", "C3 result kind is unknown")
    _require(not accessed, "C3 failure cannot claim activation artifacts")
    _require(
        (receipt_hash is None and index_hash is None and dense_hash is None)
        or (source_artifacts_bound and index_hash is not None and dense_hash is not None),
        "C3 failure source-artifact binding is incomplete",
    )
    failure = result.get("failure")
    _require(isinstance(failure, Mapping) and failure.get("stage") in {"integrity", "identity", "execution", "data", "receipt", "compatibility", "publication"}, "C3 failure stage mismatch")


def _recovery_provenance(source_dir: Path, index_hash: str) -> list[str]:
    return [
        "## C3 recovery provenance",
        "",
        "- Recovery class: `in_memory_dtype_metadata_recovery_only`",
        f"- Source activation run: `{source_dir.name}`",
        f"- Source representation index hash: `{index_hash}`",
        "- Source dtype binding: `float32`",
        f"- Source representation records: `{EXPECTED_C2_RECORDS}`",
        "- Source index bytes were not rewritten.",
        "- The external dense asset is located and hashed in place; it is not copied into this package.",
        "- C3 loads no model, performs no generation, and makes no claim promotion.",
    ]


def _report_text(
    *,
    created_at: str,
    package_dir: Path,
    result_path: Path,
    result: Mapping[str, Any],
    result_hash: str,
    protocol_hash: str,
    source_dir: Path,
    receipt_hash: str | None,
    index_hash: str | None,
    dense_hash: str | None,
    dense_bytes: int | None,
) -> str:
    lines = [
        "# Latent TRIZ A0-R2-C3 exploratory publication report",
        "",
        f"- Created: {created_at}",
        f"- Terminal status: `{result['status']}`",
        f"- Result artifact: `{result['artifact_class']}`",
        f"- Result file: `{result_path.name}`",
        f"- Result hash: `{result_hash}`",
        f"- Protocol path: `{base.PROTOCOL_PATH.relative_to(base.REPO_ROOT)}`",
        f"- Protocol hash: `{protocol_hash}`",
        f"- Publication manifest: `{MANIFEST_FILE}`",
        "",
        "## Epistemic boundary",
        "",
        "- Automated exploratory E0 packaging only; no human or expert validation is claimed.",
        "- This report does not claim TRIZ rediscovery, novelty, or general validity.",
        "- Positive, null, failed, and non-interpretable terminal outcomes are published equally.",
    ]
    if receipt_hash is not None:
        lines.extend(
            [
                "",
                "## Immutable activation bundle",
                "",
                f"- Activation receipt hash: `{receipt_hash}`",
                f"- Representation index hash: `{index_hash}`",
                f"- External dense locator: `{source_dir / 'activations.json'}`",
                f"- External dense hash: `{dense_hash}`",
                f"- External dense bytes: `{dense_bytes}`",
                "",
                *_recovery_provenance(source_dir, str(index_hash)),
            ]
        )
    if result["artifact_class"] == "a0r2-run-failure":
        failure = result["failure"]
        lines.extend(["", "## Failure summary", "", f"- Failure stage: `{failure['stage']}`", f"- Failure kind: `{failure['failure_kind']}`"])
    else:
        stats = result["statistics"]
        lines.extend(
            [
                "",
                "## Statistical summary",
                "",
                f"- Primary permutation p-value: `{float(stats['primary_permutation_p']):.6f}`",
                f"- Macro-F1 margin over surface: `{float(stats['macro_f1_margin_over_surface']):.6f}`",
                f"- Family successes: `{int(stats['family_successes'])}`",
                f"- Successful domain directions: `{int(stats['successful_domain_directions'])}`",
            ]
        )
    lines.extend(["", "## Publication manifest", "", f"- Manifest path: `{package_dir.name}/{MANIFEST_FILE}`"])
    return "\n".join(lines) + "\n"


def _prepare(
    *,
    package_dir: str | Path,
    external_dense_dir: str | Path,
    allow_external_dense_reuse: bool,
) -> dict[str, Any]:
    _require(allow_external_dense_reuse is True, "C3 requires explicit external dense reuse")
    package = _relative_direct_child("package_dir", package_dir, PACKAGE_PREFIX)
    source = _relative_direct_child("external_dense_dir", external_dense_dir, SOURCE_PREFIX)
    _require(package.is_dir(), f"C3 package directory missing: {package}")
    result_path, result, result_kind = base._find_result_path(package)
    protocol = base._load_protocol()
    _validate_schema = base._validate_schema
    _validate_schema(result, base._read_json_schema(base.SCHEMA_ROOT / ("a0r2-statistical-result.schema.json" if result_kind == "statistical" else "a0r2-run-failure.schema.json")), label="C3 result")

    receipt_path = package / ACTIVATION_RECEIPT_FILE
    index_path = package / REPRESENTATION_INDEX_FILE
    dense_path = source / "activations.json"
    source_artifacts_present = receipt_path.is_file() or index_path.is_file()
    if source_artifacts_present:
        _require(
            receipt_path.is_file() and index_path.is_file() and dense_path.is_file(),
            "C3 source activation artifacts are incomplete",
        )
    receipt_hash: str | None = None
    index_hash: str | None = None
    dense_hash: str | None = None
    dense_bytes: int | None = None
    if source_artifacts_present:
        receipt = base._read_json(receipt_path)
        _validate_schema(receipt, base._read_json_schema(base.SCHEMA_ROOT / "a0r2-activation-receipt.schema.json"), label="C3 activation receipt")
        _model_matches_protocol(receipt, protocol, label="C3 activation receipt")
        _require(receipt.get("protocol_id") == protocol["protocol_id"], "C3 activation receipt protocol id mismatch")
        _require(receipt["output_bundle"]["dense_locator"] == str(source / "activations.json"), "C3 activation dense locator mismatch")
        receipt_hash = base._sha256(receipt_path)
        index_hash = _validate_c3_index(index_path, receipt)
        dense_hash = base._sha256(dense_path)
        dense_bytes = dense_path.stat().st_size
        _require(receipt["output_bundle"]["artifact_hashes"]["dense_sha256"] == dense_hash, "C3 activation dense hash mismatch")
    _validate_result(
        result=result,
        result_kind=result_kind,
        protocol=protocol,
        source_dense_locator=str(source / "activations.json"),
        receipt_hash=receipt_hash,
        index_hash=index_hash,
        dense_hash=dense_hash,
    )
    return {
        "package": package,
        "source": source,
        "result_path": result_path,
        "result": result,
        "result_kind": result_kind,
        "protocol": protocol,
        "receipt_hash": receipt_hash,
        "index_hash": index_hash,
        "dense_hash": dense_hash,
        "dense_bytes": dense_bytes,
    }


def generate_a0r2c3_report(
    *,
    package_dir: str | Path,
    external_dense_dir: str | Path,
    created_at: str,
    allow_external_dense_reuse: bool = False,
) -> tuple[Path, Path]:
    """Create a C3 report and manifest without copying the dense asset."""

    _validate_timestamp(created_at)
    state = _prepare(
        package_dir=package_dir,
        external_dense_dir=external_dense_dir,
        allow_external_dense_reuse=allow_external_dense_reuse,
    )
    package = state["package"]
    report_path = package / REPORT_FILE
    manifest_path = package / MANIFEST_FILE
    _require(not report_path.exists() and not manifest_path.exists(), "refuse overwrite: C3 report or manifest exists")
    report = _report_text(
        created_at=created_at,
        package_dir=package,
        result_path=state["result_path"],
        result=state["result"],
        result_hash=base._sha256(state["result_path"]),
        protocol_hash=base._sha256(base.PROTOCOL_PATH),
        source_dir=state["source"],
        receipt_hash=state["receipt_hash"],
        index_hash=state["index_hash"],
        dense_hash=state["dense_hash"],
        dense_bytes=state["dense_bytes"],
    )
    manifest: dict[str, Any] = {
        "artifact_class": "a0r2-publication-manifest",
        **base.EPISTEMIC,
        "created_at": created_at,
        "protocol_id": state["protocol"]["protocol_id"],
        "status": state["result"]["status"],
        "terminal_status": state["result"]["status"],
        "protocol": {"path": str(base.PROTOCOL_PATH.relative_to(base.REPO_ROOT)), "sha256": base._sha256(base.PROTOCOL_PATH)},
        "publication": {"publish_every_terminal_outcome": True, "sensitivity_may_rescue_primary": False, "model_substitution_after_output": False, "claim_promotion": False},
        "result": {"path": state["result_path"].name, "sha256": base._sha256(state["result_path"])},
        "report": {"path": REPORT_FILE, "sha256": hashlib.sha256(report.encode("utf-8")).hexdigest()},
    }
    if state["receipt_hash"] is not None:
        manifest.update(
            {
                "receipt": {"path": ACTIVATION_RECEIPT_FILE, "sha256": state["receipt_hash"]},
                "index": {"path": REPRESENTATION_INDEX_FILE, "sha256": state["index_hash"]},
                "dense": {"path": str(state["source"] / "activations.json"), "sha256": state["dense_hash"], "records": EXPECTED_C2_RECORDS, "hidden_size": 960},
            }
        )
    base._validate_schema(manifest, base._read_json_schema(base.SCHEMA_ROOT / "a0r2-publication-manifest.schema.json"), label="C3 publication manifest")
    base._write_pair_atomic(
        (
            (report_path, report.encode("utf-8")),
            (manifest_path, (json.dumps(manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")),
        )
    )
    return report_path, manifest_path


def verify_a0r2c3_publication(
    *,
    package_dir: str | Path,
    external_dense_dir: str | Path,
    allow_external_dense_reuse: bool = False,
) -> dict[str, Any]:
    """Verify every C3 receipt, source binding, report, and manifest hash."""

    state = _prepare(
        package_dir=package_dir,
        external_dense_dir=external_dense_dir,
        allow_external_dense_reuse=allow_external_dense_reuse,
    )
    package = state["package"]
    report_path = package / REPORT_FILE
    manifest_path = package / MANIFEST_FILE
    _require(report_path.is_file() and manifest_path.is_file(), "C3 publication manifest or report is missing")
    manifest = base._read_json(manifest_path)
    base._validate_schema(manifest, base._read_json_schema(base.SCHEMA_ROOT / "a0r2-publication-manifest.schema.json"), label="C3 publication manifest")
    result_path = state["result_path"]
    _require(manifest.get("result") == {"path": result_path.name, "sha256": base._sha256(result_path)}, "C3 manifest result binding mismatch")
    _require(manifest.get("report") == {"path": REPORT_FILE, "sha256": base._sha256(report_path)}, "C3 manifest report binding mismatch")
    _require(manifest.get("status") == state["result"]["status"] == manifest.get("terminal_status"), "C3 manifest terminal status mismatch")
    _require(manifest.get("protocol") == {"path": str(base.PROTOCOL_PATH.relative_to(base.REPO_ROOT)), "sha256": base._sha256(base.PROTOCOL_PATH)}, "C3 manifest protocol binding mismatch")
    _require(manifest.get("publication") == {"publish_every_terminal_outcome": True, "sensitivity_may_rescue_primary": False, "model_substitution_after_output": False, "claim_promotion": False}, "C3 publication policy mismatch")
    if state["receipt_hash"] is None:
        _require(not any(key in manifest for key in ("receipt", "index", "dense")), "C3 package without source artifacts must not advertise them")
    else:
        _require(manifest.get("receipt") == {"path": ACTIVATION_RECEIPT_FILE, "sha256": state["receipt_hash"]}, "C3 manifest receipt binding mismatch")
        _require(manifest.get("index") == {"path": REPRESENTATION_INDEX_FILE, "sha256": state["index_hash"]}, "C3 manifest index binding mismatch")
        _require(manifest.get("dense") == {"path": str(state["source"] / "activations.json"), "sha256": state["dense_hash"], "records": EXPECTED_C2_RECORDS, "hidden_size": 960}, "C3 manifest dense binding mismatch")
        report = report_path.read_text(encoding="utf-8")
        for fragment in ("## C3 recovery provenance", state["source"].name, str(state["index_hash"]), "in_memory_dtype_metadata_recovery_only"):
            _require(fragment in report, "C3 recovery provenance is missing from report")
    return manifest
