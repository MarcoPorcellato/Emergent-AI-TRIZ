"""Immutable report and fail-closed publication verifier for comparative runs."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


class ComparativeReportError(ValueError):
    """Raised when a comparative package or external asset is incomplete."""


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ComparativeReportError(f"invalid package JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ComparativeReportError(f"package artifact must be an object: {path}")
    return value


def _safe_package(repo: Path, package_dir: str | Path) -> Path:
    relative = Path(package_dir)
    if relative.is_absolute() or ".." in relative.parts or relative.parts[:2] != ("results", "exp001-comparative"):
        raise ComparativeReportError("package must be results/exp001-comparative/<run>")
    package = (repo / relative).resolve()
    if not package.is_dir() or not package.is_relative_to(repo):
        raise ComparativeReportError("package directory is missing or escaped")
    return package


def generate_comparative_report(*, repo_root: str | Path, package_dir: str | Path) -> dict[str, str]:
    repo = Path(repo_root).resolve()
    package = _safe_package(repo, package_dir)
    result = _json(package / "statistical-result.json")
    receipt = _json(package / "execution-receipt.json")
    if result.get("protocol_id") != "exp001-reference-comparative-v1.0.0" or receipt.get("protocol_id") != result.get("protocol_id"):
        raise ComparativeReportError("protocol identity mismatch")
    external = receipt.get("external_response_asset")
    if not isinstance(external, dict) or not isinstance(external.get("locator"), str) or not isinstance(external.get("sha256"), str):
        raise ComparativeReportError("external scalar asset binding is incomplete")
    asset_rel = Path(external["locator"])
    if asset_rel.is_absolute() or ".." in asset_rel.parts or asset_rel.parts[:2] != ("artifacts", "exp001-comparative"):
        raise ComparativeReportError("external asset locator escaped allowed root")
    asset = (repo / asset_rel).resolve()
    if not asset.is_file() or not asset.is_relative_to(repo) or _sha(asset) != external["sha256"]:
        raise ComparativeReportError("external asset is missing or mutated")
    report_rel = Path(package.relative_to(repo)) / "report.md"
    report = (
        "# EXP-001 comparative reference result\n\n"
        f"- Model: `{receipt.get('model', {}).get('id')}`\n"
        f"- Revision: `{receipt.get('model', {}).get('revision')}`\n"
        f"- Terminal status: `{result.get('status')}`\n"
        "- Scientific status: exploratory; no expert validation; no claim promotion.\n"
        "- Blinded and source-exposed strata and all model scores remain non-pooled.\n"
        f"- External scalar asset: `{asset_rel.as_posix()}` (content hash-bound, not embedded).\n"
    ).encode("utf-8")
    if (repo / report_rel).exists():
        raise ComparativeReportError("refuse overwrite: report already exists")
    (repo / report_rel).parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=(repo / report_rel).parent, prefix=".comparative-report-", delete=False) as stream:
            stream.write(report)
            temporary = Path(stream.name)
        os.link(temporary, repo / report_rel)
    except OSError as exc:
        raise ComparativeReportError("cannot persist comparative report") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"path": report_rel.as_posix(), "sha256": hashlib.sha256(report).hexdigest()}


def verify_comparative_publication(*, repo_root: str | Path, package_dir: str | Path) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    package = _safe_package(repo, package_dir)
    result = _json(package / "statistical-result.json")
    receipt = _json(package / "execution-receipt.json")
    manifest = _json(package / "publication-manifest.json")
    report = package / "report.md"
    if not report.is_file():
        raise ComparativeReportError("report is missing")
    if manifest.get("terminal_status") != result.get("status") or manifest.get("model_id") != receipt.get("model", {}).get("id"):
        raise ComparativeReportError("publication manifest identity mismatch")
    external = manifest.get("external_response_asset")
    if not isinstance(external, dict) or not isinstance(external.get("locator"), str) or not isinstance(external.get("sha256"), str):
        raise ComparativeReportError("publication external asset binding is incomplete")
    external_path = (repo / Path(external["locator"])).resolve()
    if not external_path.is_file() or not external_path.is_relative_to(repo) or _sha(external_path) != external.get("sha256"):
        raise ComparativeReportError("publication external asset missing or mutated")
    report_binding = manifest.get("report")
    if not isinstance(report_binding, dict) or report_binding.get("sha256") != _sha(report):
        raise ComparativeReportError("publication report hash mismatch")
    return {"artifact_class": "exp001-comparative-publication-verification", "status": "pass", "terminal_status": result.get("status"), "model_id": receipt.get("model", {}).get("id")}


__all__ = ["ComparativeReportError", "generate_comparative_report", "verify_comparative_publication"]
