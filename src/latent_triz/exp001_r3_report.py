"""Fail-closed writer and verifier for an EXP-001 R3 publication package.

This module is deliberately target/model agnostic.  It only binds already
written JSON artifacts by hash; it never copies dense output or reads a model.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .validator import validate

PROTOCOL_ID = "exp001-reference-integrated-r3-v1.0.0"
STATUSES = {"positive", "null", "failed", "non_interpretable", "incompatible"}
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")


class R3ReportError(RuntimeError):
    """Raised when a package cannot be generated or verified safely."""


def _root(repo_root: str | Path | None) -> Path:
    return Path(repo_root or Path.cwd()).resolve()


def _relative(value: str | Path, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise R3ReportError(f"{label} must be a safe relative path")
    return path


def _package_path(package_dir: str | Path, root: Path) -> tuple[Path, Path]:
    rel = _relative(package_dir, "package_dir")
    expected = Path("results") / "exp001-r3"
    if rel.parent != expected or len(rel.name) < 1 or rel.name in {".", ".."}:
        raise R3ReportError("package_dir must be results/exp001-r3/<run-id>")
    absolute = (root / rel).resolve()
    if absolute.parent != (root / expected).resolve():
        raise R3ReportError("package_dir escapes the R3 results directory")
    return rel, absolute


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise R3ReportError(f"cannot read {label}") from exc
    if not isinstance(value, dict):
        raise R3ReportError(f"{label} must be a JSON object")
    return value


def _schema(root: Path, name: str) -> dict[str, Any]:
    return _json(root / "schemas" / name, name)


def _check_schema(value: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    if validate(value, schema):
        raise R3ReportError(f"{label} schema validation failed")


def _artifact(root: Path, path: Path, label: str) -> dict[str, str]:
    if path.is_absolute() or ".." in path.parts:
        raise R3ReportError(f"{label} has unsafe path")
    absolute = (root / path).resolve()
    if not absolute.is_file() or not absolute.is_relative_to(root):
        raise R3ReportError(f"{label} is missing or outside the repository")
    return {"path": path.as_posix(), "sha256": _sha256(absolute)}


def _verify_artifact_entry(root: Path, entry: Mapping[str, Any], label: str) -> None:
    """Require a provenance hash object to name an existing exact file."""
    if not isinstance(entry, Mapping) or not isinstance(entry.get("path"), str) or not isinstance(entry.get("sha256"), str):
        raise R3ReportError(f"{label} must be a path/SHA-256 artifact object")
    path = _relative(entry["path"], label)
    absolute = (root / path).resolve()
    if not absolute.is_file() or not absolute.is_relative_to(root):
        raise R3ReportError(f"{label} is missing or outside the repository")
    if _sha256(absolute) != entry["sha256"]:
        raise R3ReportError(f"{label} hash mismatch")


def _verify_provenance(root: Path, provenance: Mapping[str, Any], label: str = "provenance") -> None:
    required = ("implementation", "authorization", "integrity", "feasibility", "sealed_key_access", "recovery")
    if not isinstance(provenance, Mapping):
        raise R3ReportError(f"{label} must be an object")
    for name in required:
        if name not in provenance:
            raise R3ReportError(f"{label}.{name} is missing")
        _verify_artifact_entry(root, provenance[name], f"{label}.{name}")


def _under(path: Path, directory: Path, label: str) -> None:
    if path.parts[: len(directory.parts)] != directory.parts:
        raise R3ReportError(f"{label} must be inside the package directory")


def _input_path(value: str | Path | Mapping[str, Any], default: Path, root: Path, label: str) -> Path:
    if isinstance(value, Mapping):
        path = default
    else:
        path = _relative(value, label)
    absolute = (root / path).resolve()
    if not absolute.is_relative_to(root) or not absolute.is_file():
        raise R3ReportError(f"{label} is missing or outside the repository")
    if isinstance(value, Mapping):
        actual = _json(absolute, label)
        if dict(value) != actual:
            raise R3ReportError(f"{label} object differs from its on-disk artifact")
    return path


def _stable_json(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _atomic_pair(items: list[tuple[Path, bytes]]) -> None:
    if any(path.exists() for path, _ in items):
        raise R3ReportError("refuse overwrite: publication output already exists")
    temps: list[Path] = []
    linked: list[Path] = []
    try:
        for path, content in items:
            with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False, suffix=".tmp") as stream:
                stream.write(content)
                temp = Path(stream.name)
            temps.append(temp)
            os.link(temp, path)
            linked.append(path)
    except Exception as exc:
        for path in linked:
            path.unlink(missing_ok=True)
        raise R3ReportError("cannot atomically persist publication package") from exc
    finally:
        for path in temps:
            path.unlink(missing_ok=True)


def _validate_common(root: Path, protocol_path: Path, result_path: Path, receipt_path: Path, response_path: Path | None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    protocol = _json(root / protocol_path, "protocol")
    result = _json(root / result_path, "statistical result")
    receipt = _json(root / receipt_path, "execution receipt")
    _check_schema(protocol, _schema(root, "exp001-r3-protocol.schema.json"), "protocol")
    result_schema = "exp001-r3-statistical-result.schema.json" if result.get("artifact_class") == "exp001-r3-statistical-result" else "exp001-r3-run-failure.schema.json"
    _check_schema(result, _schema(root, result_schema), "terminal result")
    _check_schema(receipt, _schema(root, "exp001-r3-execution-receipt.schema.json"), "execution receipt")
    response = None if response_path is None else _json(root / response_path, "response index")
    if response is not None:
        _check_schema(response, _schema(root, "exp001-r3-response-index.schema.json"), "response index")
    if protocol.get("protocol_id") != PROTOCOL_ID or protocol.get("protocol_status") != "frozen":
        raise R3ReportError("protocol must be the frozen EXP-001 R3 protocol")
    for label, value in (("statistical result", result), ("execution receipt", receipt)):
        if value.get("protocol_id") != PROTOCOL_ID:
            raise R3ReportError(f"{label} protocol_id mismatch")
        if value.get("claim_ids") != [] or value.get("evidence_eligible") is not False or value.get("expert_validated") is not False:
            raise R3ReportError(f"{label} violates exploratory no-claim boundary")
    if result["status"] != receipt["status"]:
        raise R3ReportError("statistical result and execution receipt status mismatch")
    return protocol, result, receipt, response


def generate_r3_report_package(*, package_dir: str | Path, created_at: str, terminal_result: str | Path | Mapping[str, Any], execution_receipt: str | Path | Mapping[str, Any], response_index: str | Path | Mapping[str, Any] | None = None, protocol_path: str | Path = "experiments/exp001-reference-integrated/protocol.json", repo_root: str | Path | None = None) -> tuple[Path, Path]:
    root = _root(repo_root)
    rel_dir, directory = _package_path(package_dir, root)
    if not _UTC.fullmatch(created_at):
        raise R3ReportError("created_at must be an explicit UTC timestamp")
    if not directory.is_dir():
        raise R3ReportError("package directory is missing")
    protocol_rel = _relative(protocol_path, "protocol_path")
    result_rel = _input_path(terminal_result, rel_dir / "statistical-result.json", root, "terminal_result")
    receipt_rel = _input_path(execution_receipt, rel_dir / "execution-receipt.json", root, "execution_receipt")
    response_rel = None if response_index is None else _input_path(response_index, rel_dir / "response-index.json", root, "response_index")
    _under(result_rel, rel_dir, "terminal_result")
    _under(receipt_rel, rel_dir, "execution_receipt")
    if response_rel is not None:
        _under(response_rel, rel_dir, "response_index")
    protocol, result, receipt, response = _validate_common(root, protocol_rel, result_rel, receipt_rel, response_rel)
    if response is not None and response.get("record_count") != len(response.get("records", [])):
        raise R3ReportError("response index record_count mismatch")
    report_rel = rel_dir / "report.md"
    manifest_rel = rel_dir / "publication-manifest.json"
    protocol_art = _artifact(root, protocol_rel, "protocol")
    result_art = _artifact(root, result_rel, "statistical result")
    receipt_art = _artifact(root, receipt_rel, "execution receipt")
    response_art = None if response_rel is None else _artifact(root, response_rel, "response index")
    secondary = result.get("secondary_summary", {})
    report_text = (f"# EXP-001 R3 publication report\n\n- Created: {created_at}\n- Terminal status: `{result['status']}`\n- Protocol: `{PROTOCOL_ID}`\n- Records: `85` (primary and TRIZ-source secondary strata remain unpooled).\n\n## Scientific boundary\n\nThis is an exploratory automated-proxy result. `claim_ids` is empty; `evidence_eligible` and `expert_validated` are false. It does not establish a general TRIZ claim.\n\n## Secondary strata (descriptive, non-pooled)\n\n- Matrix 2003: {secondary.get('matrix_2003', 'not reported')}\n- Panitz: {secondary.get('panitz', 'not reported')}\n\n## Integrity\n\nThe publication manifest binds the frozen protocol, execution receipt, statistical result, response index, and provenance artifacts by SHA-256. Scalar response assets remain external and are referenced by locator and SHA-256; they are not copied into this package.\n\n## Limitations\n\nInterpretation is limited to the frozen protocol, exact model revision, and terminal outcome recorded here. Matrix 2003 and Panitz-derived controls are descriptive and are never pooled with the primary test.\n")
    report_bytes = report_text.encode("utf-8")
    external_asset = receipt.get("external_response_asset")
    provenance = receipt.get("provenance")
    if not isinstance(external_asset, Mapping) or not isinstance(provenance, Mapping):
        raise R3ReportError("receipt must bind external_response_asset and provenance before publication")
    _verify_provenance(root, provenance, "receipt.provenance")
    manifest: dict[str, Any] = {"artifact_class": "exp001-r3-publication-manifest", "protocol_id": PROTOCOL_ID, "terminal_status": result["status"], "publish_every_terminal_outcome": True, "claim_ids": [], "evidence_eligible": False, "expert_validated": False, "protocol": protocol_art, "receipt": receipt_art, "report": {"path": report_rel.as_posix(), "sha256": hashlib.sha256(report_bytes).hexdigest()}, "result": result_art, "external_response_asset": dict(external_asset), "provenance": dict(provenance)}
    if response_art is not None:
        manifest["response_index"] = response_art
    _check_schema(manifest, _schema(root, "exp001-r3-publication-manifest.schema.json"), "publication manifest")
    _atomic_pair([(root / report_rel, report_bytes), (root / manifest_rel, _stable_json(manifest))])
    return root / report_rel, root / manifest_rel


def verify_r3_report_package(*, package_dir: str | Path, repo_root: str | Path | None = None) -> dict[str, Any]:
    root = _root(repo_root)
    rel_dir, directory = _package_path(package_dir, root)
    manifest_path = directory / "publication-manifest.json"
    if not manifest_path.is_file():
        raise R3ReportError("publication manifest is missing")
    manifest = _json(manifest_path, "publication manifest")
    _check_schema(manifest, _schema(root, "exp001-r3-publication-manifest.schema.json"), "publication manifest")
    if manifest["protocol_id"] != PROTOCOL_ID or manifest["claim_ids"] != [] or manifest["evidence_eligible"] is not False or manifest["expert_validated"] is not False:
        raise R3ReportError("publication manifest violates exploratory boundary")
    artifacts = ["protocol", "receipt", "report", "result"] + (["response_index"] if "response_index" in manifest else [])
    for name in artifacts:
        entry = manifest[name]
        path = _relative(entry["path"], name)
        if name in {"report", "result", "receipt", "response_index"}:
            _under(path, rel_dir, name)
        absolute = (root / path).resolve()
        if not absolute.is_file() or not absolute.is_relative_to(root):
            raise R3ReportError(f"manifest artifact missing or unsafe: {name}")
        if _sha256(absolute) != entry["sha256"]:
            raise R3ReportError(f"manifest artifact hash mismatch: {name}")
    _verify_provenance(root, manifest["provenance"], "manifest.provenance")
    result = _json(root / _relative(manifest["result"]["path"], "result"), "statistical result")
    receipt = _json(root / _relative(manifest["receipt"]["path"], "receipt"), "execution receipt")
    if result.get("status") != receipt.get("status") or result.get("status") != manifest["terminal_status"]:
        raise R3ReportError("terminal status drift")
    if "response_index" in manifest:
        response = _json(root / _relative(manifest["response_index"]["path"], "response_index"), "response index")
        _check_schema(response, _schema(root, "exp001-r3-response-index.schema.json"), "response index")
        if response.get("record_count") != len(response.get("records", [])):
            raise R3ReportError("response index record_count mismatch")
    return manifest


# Short aliases keep CLI/integration call sites readable.
generate_report_package = generate_r3_report_package
verify_report_package = verify_r3_report_package
