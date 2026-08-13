from __future__ import annotations

import hashlib
import json
import os
from html import escape
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LAB00_REPORT_PATH = Path("artifacts/lab00/index.html")
LAB01_PARITY_PATH = Path("results/lab01/model-anatomy/parity_report.json")
LAB02_SUMMARY_PATH = Path("results/lab02/dataset-anatomy/summary.json")
LAB03_SUMMARY_PATH = Path("results/lab03/behavioral-baselines/summary.json")
LAB04_SUMMARY_PATH = Path("results/lab04/decodability/summary.json")
LAB05_SUMMARY_PATH = Path("results/lab05/candidate-directions/summary.json")


class LabSuiteError(RuntimeError):
    pass


@dataclass(frozen=True)
class LabSource:
    name: str
    kind: str
    status: str
    empirical: bool
    evidence_eligible: bool
    claim_ids: list[str]
    path: Path
    sha256: str
    classification: str
    report_path: Path
    extra: dict[str, Any]


def build_lab_suite_report(repo_root: Path, output_path: Path) -> Path:
    """
    Build a deterministic, self-contained HTML dashboard for Lab00-Lab05 summaries.

    This function aggregates:
    - Lab 01 parity report
    - Lab 02 summary
    - Lab 03 summary
    - Lab 04 summary
    - Lab 00 rendered report path (process-only boundary artifact)
    """
    repo_root = Path(repo_root).resolve()
    output_path = Path(output_path)

    lab00_report = _load_lab00_report(repo_root / LAB00_REPORT_PATH)
    lab01 = _load_lab_json(
        repo_root / LAB01_PARITY_PATH,
        "lab01",
        repo_root=repo_root,
        expected_artifact_class="model-instrumentation",
        expected_empirical=True,
    )
    lab02 = _load_lab_json(
        repo_root / LAB02_SUMMARY_PATH,
        "lab02",
        repo_root=repo_root,
        expected_artifact_class="dataset-anatomy",
        expected_empirical=False,
    )
    lab03 = _load_lab_json(
        repo_root / LAB03_SUMMARY_PATH,
        "lab03",
        repo_root=repo_root,
        expected_artifact_class="behavioral-baseline-instrumentation",
        expected_empirical=False,
    )
    lab04 = _load_lab_json(
        repo_root / LAB04_SUMMARY_PATH,
        "lab04",
        repo_root=repo_root,
        expected_artifact_class="representation-decodability-instrumentation",
        expected_empirical=False,
    )
    lab05 = _load_lab_json(
        repo_root / LAB05_SUMMARY_PATH,
        "lab05",
        repo_root=repo_root,
        expected_artifact_class="candidate-direction-instrumentation",
        expected_empirical=False,
    )

    sources = sorted(
        [lab00_report, lab01, lab02, lab03, lab04, lab05],
        key=lambda item: item.name,
    )
    readiness = "ready" if all(item.status == "pass" for item in sources) else "not-ready"
    readiness_text = "All tracked labs are pass-ready" if readiness == "ready" else "Not all tracked labs are pass-ready"
    output_path = output_path.resolve()
    _repo_relative_path(repo_root, output_path)
    html = _render_html(
        repo_root=repo_root,
        output_dir=output_path.parent,
        sources=sources,
        readiness=readiness_text,
        readiness_status=readiness,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _repo_relative_path(repo_root: Path, target: Path) -> str:
    try:
        relative = target.relative_to(repo_root)
    except ValueError as exc:
        raise LabSuiteError(f"path is outside repository: {target}") from exc
    return relative.as_posix()


def _ensure_bool(payload: dict[str, Any], field: str, source: str) -> bool:
    if field not in payload:
        raise LabSuiteError(f"{source}: missing {field}")
    value = payload[field]
    if not isinstance(value, bool):
        raise LabSuiteError(f"{source}: field {field} must be bool")
    return value


def _ensure_str(payload: dict[str, Any], field: str, source: str) -> str:
    if field not in payload:
        raise LabSuiteError(f"{source}: missing {field}")
    value = payload[field]
    if not isinstance(value, str):
        raise LabSuiteError(f"{source}: field {field} must be string")
    return value


def _ensure_claim_ids(payload: dict[str, Any], source: str) -> list[str]:
    if "claim_ids" not in payload:
        raise LabSuiteError(f"{source}: missing claim_ids")
    claim_ids = payload["claim_ids"]
    if not isinstance(claim_ids, list):
        raise LabSuiteError(f"{source}: claim_ids must be a list")
    if claim_ids:
        raise LabSuiteError(f"{source}: claim_ids must be empty")
    return claim_ids


def _load_lab_json(
    path: Path,
    name: str,
    *,
    repo_root: Path,
    expected_artifact_class: str,
    expected_empirical: bool,
) -> LabSource:
    if not path.exists():
        raise LabSuiteError(f"{name}: file not found: {path}")
    if not path.is_file():
        raise LabSuiteError(f"{name}: expected a file: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LabSuiteError(f"{name}: invalid JSON in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise LabSuiteError(f"{name}: summary must be an object")

    status = _ensure_str(payload, "status", name).lower()
    if status not in {"pass", "fail"}:
        raise LabSuiteError(f"{name}: status must be pass or fail")

    artifact_class = _ensure_str(payload, "artifact_class", name)
    if artifact_class != expected_artifact_class:
        raise LabSuiteError(
            f"{name}: artifact_class must be '{expected_artifact_class}', got '{artifact_class}'"
        )

    evidence_eligible = _ensure_bool(payload, "evidence_eligible", name)
    if evidence_eligible is True:
        raise LabSuiteError(f"{name}: evidence_eligible must be false")

    empirical = _ensure_bool(payload, "empirical", name)
    if empirical != expected_empirical:
        raise LabSuiteError(f"{name}: empirical expected {expected_empirical}, got {empirical}")

    claim_ids = _ensure_claim_ids(payload, name)

    classification = (
        "Empirical instrumentation (not evidence-eligible)"
        if empirical
        else "Synthetic/process-only (not evidence-eligible)"
    )

    report_paths = {
        "lab01": Path("results/lab01/model-anatomy/report.html"),
        "lab02": Path("results/lab02/dataset-anatomy/report.html"),
        "lab03": Path("results/lab03/behavioral-baselines/report.html"),
        "lab04": Path("results/lab04/decodability/report.html"),
        "lab05": Path("results/lab05/candidate-directions/report.html"),
    }
    report_path = repo_root / report_paths[name]
    if not report_path.is_file():
        raise LabSuiteError(f"{name}: detailed report not found")

    return LabSource(
        name=name,
        kind="summary",
        status=status,
        empirical=empirical,
        evidence_eligible=evidence_eligible,
        claim_ids=claim_ids,
        path=path,
        sha256=_sha256_path(path),
        classification=classification,
        report_path=report_path,
        extra={
            "artifact_class": artifact_class,
            "evidence_eligible": evidence_eligible,
            "claim_ids": claim_ids,
        },
    )


def _load_lab00_report(path: Path) -> LabSource:
    if not path.exists():
        raise LabSuiteError(f"lab00: report not found: {path}")
    if not path.is_file():
        raise LabSuiteError(f"lab00: report path is not a file: {path}")
    try:
        payload = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LabSuiteError(f"lab00: cannot read report {path}: {exc}") from exc

    if "infrastructure" not in payload.lower():
        raise LabSuiteError("lab00: report does not contain synthetic-process boundary text")
    if "non-evidence" not in payload.lower():
        raise LabSuiteError("lab00: report does not declare non-evidence boundary")

    return LabSource(
        name="lab00",
        kind="report",
        status="pass",
        empirical=False,
        evidence_eligible=False,
        claim_ids=[],
        path=path,
        sha256=_sha256_path(path),
        classification="Synthetic/process-only (not evidence-eligible)",
        report_path=path,
        extra={},
    )


def _render_html(
    *,
    repo_root: Path,
    output_dir: Path,
    sources: list[LabSource],
    readiness: str,
    readiness_status: str,
) -> str:
    source_cards = []
    for item in sources:
        status_class = "pass" if item.status == "pass" else "fail"
        source_link = escape(_output_relative_link(repo_root, output_dir, item.path), quote=True)
        report_link = escape(_output_relative_link(repo_root, output_dir, item.report_path), quote=True)
        source_path = escape(_repo_relative_path(repo_root, item.path.resolve()))
        source_cards.append(
            "<section class='card'>"
            f"<h3>{escape(item.name.upper())} source</h3>"
            f"<p><strong>Status:</strong> <span class='pill {status_class}'>{escape(item.status)}</span></p>"
            f"<p><strong>Classification:</strong> {escape(item.classification)}</p>"
            f"<p><strong>Evidence:</strong> evidence_eligible={escape(str(item.evidence_eligible).lower())}, "
            f"claim_ids={escape(str(item.claim_ids))}</p>"
            f"<p><strong>SHA-256:</strong> <code>{escape(item.sha256)}</code></p>"
            f"<p><strong>Source:</strong> <code>{source_path}</code></p>"
            f"<a href='{report_link}'>Open detailed report</a>"
            f" <a href='{source_link}'>Open source {escape(item.kind)}</a>"
            "</section>"
        )
    summary_list = "".join(source_cards)
    dashboard_title = "Latent TRIZ Lab Suite Readiness Dashboard"
    return (
        "<!doctype html>"
        "<html lang='en'>"
        "<head>"
        "<meta charset='utf-8' />"
        "<meta name='viewport' content='width=device-width, initial-scale=1' />"
        f"<title>{dashboard_title}</title>"
        "<style>"
        "body{font-family:Trebuchet MS,Arial,sans-serif;margin:0;background:linear-gradient(135deg,#f7f7fb,#e8f6ff);color:#111}"
        ".container{max-width:1000px;margin:2rem auto;padding:1rem}"
        ".banner{padding:1rem;background:#12283b;color:#fff;border-radius:12px;margin-bottom:1rem}"
        ".banner.ready{background:#0e6b2f}"
        ".banner.not-ready{background:#613f00}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}"
        ".card{background:#ffffffcc;border:1px solid #cad4e1;border-radius:12px;padding:1rem;backdrop-filter:saturate(120%) blur(1px)}"
        "h1,h2,h3{font-family:Georgia,'Times New Roman',serif}"
        ".pill{padding:0.12rem 0.5rem;border-radius:999px;color:#fff;font-weight:700}"
        ".pill.pass{background:#2f8f4e}"
        ".pill.fail{background:#b23b34}"
        "a{color:#154f7b}"
        "code{word-break:break-all}"
        ".badge{display:inline-block;border-radius:999px;padding:0.15rem 0.5rem;background:#f0ecff;color:#2d2468;margin-right:0.4rem}"
        "</style>"
        "</head>"
        "<body>"
        "<div class='container'>"
        f"<div class='banner {readiness_status}'><h1>{dashboard_title}</h1>"
        f"<p>{escape(readiness)}</p></div>"
        f"<p><span class='badge'>Deterministic</span>"
        f"<span class='badge'>Boundary-aware</span> Synthetic vs empirical visible per lab.</p>"
        f"<p>Self-contained HTML readiness report.</p>"
        "<div class='grid'>"
        f"{summary_list}"
        "</div>"
        "</div>"
        "</body>"
        "</html>"
    )


def _output_relative_link(repo_root: Path, output_dir: Path, target: Path) -> str:
    _repo_relative_path(repo_root, target.resolve())
    return Path(os.path.relpath(target.resolve(), start=output_dir.resolve())).as_posix()
