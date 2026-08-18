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


BASE_PACKAGE_FILES = (
    "execution-receipt.json",
    "statistical-result.json",
    "sealed-key-access.json",
    "recovery-observation.json",
    "report.md",
)
SUCCESS_PACKAGE_FILES = BASE_PACKAGE_FILES + ("response-index.json",)
MAX_WALL_SECONDS = 1800.0
MAX_RSS_BYTES = 8_589_934_592
MAX_DENSE_BYTES = 134_217_728


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


def _binding(repo: Path, path: Path) -> dict[str, str]:
    return {"path": path.relative_to(repo).as_posix(), "sha256": _sha(path)}


def _verify_binding(repo: Path, binding: Any, *, expected_path: Path | None = None) -> None:
    if not isinstance(binding, dict) or not isinstance(binding.get("path"), str) or not isinstance(binding.get("sha256"), str):
        raise ComparativeReportError("artifact binding is incomplete")
    relative = Path(binding["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ComparativeReportError("artifact binding escaped repository")
    path = (repo / relative).resolve()
    if not path.is_file() or not path.is_relative_to(repo):
        raise ComparativeReportError(f"bound artifact is missing: {relative}")
    if expected_path is not None and path != expected_path.resolve():
        raise ComparativeReportError("artifact binding points to the wrong path")
    if _sha(path) != binding["sha256"]:
        raise ComparativeReportError(f"bound artifact hash mismatch: {relative}")


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
    required_files = SUCCESS_PACKAGE_FILES if result.get("status") != "failed" else BASE_PACKAGE_FILES
    for name in required_files:
        if not (package / name).is_file():
            raise ComparativeReportError(f"package artifact is missing: {name}")
    if manifest.get("terminal_status") != result.get("status") or manifest.get("model_id") != receipt.get("model", {}).get("id") or manifest.get("revision") != receipt.get("model", {}).get("revision"):
        raise ComparativeReportError("publication manifest identity mismatch")
    if receipt.get("artifact_class") != "exp001-comparative-execution-receipt" or result.get("artifact_class") not in {"exp001-comparative-statistical-result", "exp001-comparative-run-failure"}:
        raise ComparativeReportError("comparative artifact class drift")
    if receipt.get("protocol_id") != "exp001-reference-comparative-v1.0.0" or result.get("protocol_id") != receipt.get("protocol_id"):
        raise ComparativeReportError("comparative protocol identity drift")
    execution = receipt.get("execution")
    if not isinstance(execution, dict) or execution.get("runtime_status") != "completed" or execution.get("device") != "cpu" or execution.get("dtype") != "float32" or execution.get("network") != "disabled" or execution.get("generation") is not False or execution.get("run_count") != 1:
        raise ComparativeReportError("execution boundary drift")
    if float(execution.get("wall_seconds", MAX_WALL_SECONDS + 1)) > MAX_WALL_SECONDS or int(execution.get("peak_rss_bytes", MAX_RSS_BYTES + 1)) > MAX_RSS_BYTES or int(execution.get("new_dense_output_bytes", MAX_DENSE_BYTES + 1)) > MAX_DENSE_BYTES:
        raise ComparativeReportError("execution ceiling exceeded")
    gate = receipt.get("ccp_gate")
    if not isinstance(gate, dict) or gate.get("resource_decision") != "admit" or gate.get("admission_active") is not False or gate.get("queue_count") != 0:
        raise ComparativeReportError("CCP gate is not Admit/inactive/empty")
    access = receipt.get("access")
    if not isinstance(access, dict) or access.get("target_reads") != 1 or access.get("sealed_targets_accessed") is not True or access.get("model_loaded") is not True or access.get("model_output_accessed") is not True:
        raise ComparativeReportError("access boundary is incomplete")
    if result.get("evidence_eligible") is not False or result.get("expert_validated") is not False or result.get("claim_ids") != []:
        raise ComparativeReportError("scientific claim envelope drift")
    if result.get("status") != "failed":
        response_index = _json(package / "response-index.json")
        if response_index.get("record_count") != 85 or not isinstance(response_index.get("records"), list) or len(response_index["records"]) != 85:
            raise ComparativeReportError("response index cardinality drift")
    sealed = _json(package / "sealed-key-access.json")
    if sealed.get("target_reads") != 1 or sealed.get("sealed_targets_accessed") is not True:
        raise ComparativeReportError("sealed-key receipt drift")
    recovery = _json(package / "recovery-observation.json")
    if recovery.get("retry_performed") is not False:
        raise ComparativeReportError("retry boundary drift")
    bindings = manifest.get("bindings")
    if not isinstance(bindings, dict):
        raise ComparativeReportError("publication bindings are missing")
    for name in required_files:
        _verify_binding(repo, bindings.get(name), expected_path=package / name)
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        raise ComparativeReportError("execution provenance is missing")
    for key in ("protocol", "analysis_plan", "execution_authorization", "model_integrity_receipt"):
        _verify_binding(repo, provenance.get(key))
    if receipt.get("model", {}).get("id") == "Qwen/Qwen3-0.6B-Base":
        _verify_binding(repo, provenance.get("qwen_acquisition_dossier"))
        qwen = _json(repo / Path(provenance["qwen_acquisition_dossier"]["path"]))
        if qwen.get("model_load_authorized") is not False or qwen.get("sealed_execution_authorized") is not False:
            raise ComparativeReportError("Qwen acquisition dossier crossed its authorization boundary")
    if not isinstance(provenance.get("execution_code_commit"), str) or len(provenance["execution_code_commit"]) != 40:
        raise ComparativeReportError("execution code commit binding is missing")
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
