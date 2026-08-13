from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Mapping


class Lab02Error(RuntimeError):
    pass


_PROVENANCE_LICENSE_ISSUES = {
    "missing_provenance",
    "missing_case_license",
    "license_mismatch",
}
_DUPLICATE_LEAKAGE_ISSUES = {
    "duplicate_case_id",
    "duplicate_signature",
    "duplicate_reference_value",
    "cross_split_signature",
    "cross_split_source_leakage",
    "cross_split_template_leakage",
}
_BALANCE_ISSUES = {
    "split_target_min",
    "split_target_exact",
    "domain_minimum_not_met",
    "principle_minimum_not_met",
}
_REQUIRED_ARTIFACT_DIGEST_KEYS = ("cases_jsonl", "annotations_jsonl", "registry_entry", "registry_manifest")


@dataclass(frozen=True)
class Gate:
    gate_id: str
    pass_value: bool
    details_pass: str
    details_fail: str

    def as_dict(self) -> dict[str, str]:
        return {
            "gate": self.gate_id,
            "status": "pass" if self.pass_value else "fail",
            "details": self.details_pass if self.pass_value else self.details_fail,
        }


def stable_json_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_lab02_report(
    dataset_audit_report: str | Path | Mapping[str, Any],
    snapshot_verification_report: str | Path | Mapping[str, Any],
    *,
    output_html: str | Path | None = None,
    output_summary: str | Path | None = None,
) -> dict[str, Any]:
    dataset_payload = _load_report(dataset_audit_report, "dataset_audit_report")
    snapshot_payload = _load_report(snapshot_verification_report, "snapshot_verification_report")

    dataset_path = _as_path(dataset_audit_report, report_type="dataset_audit_report")
    snapshot_path = _as_path(snapshot_verification_report, report_type="snapshot_verification_report")

    summary = _build_summary(dataset_payload, snapshot_payload)
    if dataset_path is not None:
        summary["hashes"]["dataset_audit_report"] = _sha256_file(dataset_path)
    if snapshot_path is not None:
        summary["hashes"]["snapshot_verification_report"] = _sha256_file(snapshot_path)

    summary["status"] = "pass" if all(item["status"] == "pass" for item in summary["gates"]) else "fail"
    summary["summary_artifacts"]["generated_at"] = str(snapshot_payload.get("generated_at", "unknown"))
    if dataset_path is not None:
        summary["summary_artifacts"]["dataset_audit_report_path"] = dataset_path.name
    if snapshot_path is not None:
        summary["summary_artifacts"]["snapshot_verification_report_path"] = snapshot_path.name

    html = _render_html(dataset_payload, snapshot_payload, summary)
    summary["hashes"]["report_html"] = _sha256_text(html)

    if output_html is not None:
        output = Path(output_html).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html, encoding="utf-8")
        summary["summary_artifacts"]["html_path"] = output.name

    if output_summary is not None:
        output = Path(output_summary).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        summary["summary_artifacts"]["summary_path"] = output.name
        output.write_text(stable_json_dumps(summary), encoding="utf-8")

    return summary


def _build_summary(
    dataset_report: Mapping[str, Any],
    snapshot_report: Mapping[str, Any],
) -> dict[str, Any]:
    snapshot_issues = _as_issue_list(snapshot_report.get("issues", []))
    dataset_issues = _as_issue_list(dataset_report.get("issues", []))

    source_type_distribution, license_distribution = _collect_source_license_distribution(snapshot_report)
    by_split = _coerce_counts(snapshot_report.get("counts"), "by_split")
    by_domain = _coerce_counts(snapshot_report.get("counts"), "by_domain")
    by_principle = _coerce_counts(snapshot_report.get("counts"), "by_principle")

    artifacts = snapshot_report.get("artifacts", {})
    coverage = _coerce_mapping(snapshot_report.get("rater_coverage"), "response_counts")
    agreement = snapshot_report.get("agreement", {})
    minimum_raters = int(snapshot_report.get("rater_coverage", {}).get("minimum_distinct_raters", 0) or 0)
    case_ids = sorted({
        str(item.get("case_id")) for item in snapshot_report.get("source_fingerprints", [])
        if isinstance(item, Mapping) and str(item.get("case_id", "")).strip()
    })
    per_case_coverage = []
    for case_id in case_ids:
        got = int(coverage.get(case_id, 0))
        per_case_coverage.append(
            {
                "case_id": case_id,
                "observed_raters": got,
                "minimum_raters": minimum_raters,
                "status": got >= minimum_raters,
            }
        )
    missing_coverage_cases = [row["case_id"] for row in per_case_coverage if not row["status"]]

    d1_pass, d1_msg = _gate_d1(dataset_report, snapshot_report)
    d2_pass, d2_msg = _gate_d2(snapshot_issues)
    d3_pass, d3_msg = _gate_d3(artifacts)
    d4_pass, d4_msg = _gate_d4(snapshot_report)
    d5_pass, d5_msg = _gate_d5(dataset_issues + snapshot_issues)
    d6_pass, d6_msg = _gate_d6(dataset_report, snapshot_issues)
    d7_pass, d7_msg = _gate_d7(snapshot_report, minimum_raters, coverage, case_ids, agreement)
    d8_pass, d8_msg = _gate_d8(dataset_report, snapshot_report)

    gates = [
        Gate("D1", d1_pass, "Payloads are valid and classified", "Payload/classification is invalid or missing").as_dict(),
        Gate("D2", d2_pass, "No provenance/license issues were reported", f"Provenance/license issues found: {d2_msg}").as_dict(),
        Gate("D3", d3_pass, "All manifest artifact hashes exist", f"Missing artifact hash data: {d3_msg}").as_dict(),
        Gate("D4", d4_pass, "Split membership digest is present", f"Split membership digest invalid: {d4_msg}").as_dict(),
        Gate("D5", d5_pass, "No duplicate or leakage issue codes in audit/snapshot", f"Duplicate/leakage found: {d5_msg}").as_dict(),
        Gate("D6", d6_pass, "Split/domain/principle balance and target constraints are closed", f"Balance/target gaps open: {d6_msg}").as_dict(),
        Gate("D7", d7_pass, "Every case reaches rater minimum and agreement minimum is met", d7_msg).as_dict(),
        Gate("D8", d8_pass, "Synthetic/non-empirical/evidence-ineligible boundary set and claims empty", d8_msg).as_dict(),
    ]

    findings_codes = sorted({item["code"] for item in dataset_issues + snapshot_issues if item.get("code")})
    target_gaps = dataset_report.get("target_gaps", [])
    if not isinstance(target_gaps, list):
        target_gaps = []

    return {
        "artifact_class": "dataset-anatomy",
        "empirical": False,
        "evidence_eligible": False,
        "claim_ids": [],
        "status": "pending",
        "gates": gates,
        "dataset": {
            "mode": dataset_report.get("mode"),
            "status": dataset_report.get("status"),
            "total_cases": int(dataset_report.get("total_cases", 0)),
            "target_gaps": target_gaps,
            "issue_count": len(dataset_issues),
        },
        "snapshot": {
            "snapshot_id": snapshot_report.get("snapshot_id"),
            "dataset_id": snapshot_report.get("dataset_id"),
            "status": snapshot_report.get("status"),
            "generated_at": snapshot_report.get("generated_at"),
            "immutable_revision": snapshot_report.get("immutable_revision"),
            "split_membership_digest": snapshot_report.get("split_membership_digest"),
            "rater_coverage": {
                "minimum_distinct_raters": minimum_raters,
                "response_counts": coverage,
                "per_case": per_case_coverage,
                "distinct_raters": _coerce_list(snapshot_report.get("rater_coverage", {}).get("distinct_raters")),
            },
            "agreement": agreement,
        },
        "balance": {
            "by_split": by_split,
            "by_domain": by_domain,
            "by_principle": by_principle,
            "by_source_type": source_type_distribution,
            "by_license": license_distribution,
        },
        "findings": {
            "issue_codes": findings_codes,
            "provenance_license": [item for item in snapshot_issues if item.get("code") in _PROVENANCE_LICENSE_ISSUES],
            "duplicate_leakage": [item for item in dataset_issues + snapshot_issues if item.get("code") in _DUPLICATE_LEAKAGE_ISSUES],
            "coverage_gaps": missing_coverage_cases,
        },
        "hashes": {
            "report_html": "",
            "dataset_audit_report": "",
            "snapshot_verification_report": "",
        },
        "summary_artifacts": {
            "generated_by": "lab02_report_renderer",
            "readiness_statement": _readiness_statement(summary_hint=(
                d1_pass and d2_pass and d3_pass and d4_pass and d5_pass and d6_pass and d7_pass and d8_pass
            )),
        },
        "pilot_profile": {
            "synthetic": True,
            "non_empirical": True,
            "evidence_eligible": False,
            "claim_ids": [],
            "triz_claim": False,
        },
    }


def _readiness_statement(summary_hint: bool) -> str:
    return (
        "Scientifically validated evidence is not claimed. "
        "Readiness is bounded by synthetic controls and gate status."
        if summary_hint
        else "Not readiness-ready: one or more fail-closed gates are open."
    )


def _render_html(
    dataset_report: Mapping[str, Any],
    snapshot_report: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> str:
    issue_rows = [
        f"<li>{escape(str(item.get('code')))}: {escape(str(item.get('message', '')))}</li>"
        for item in dataset_report.get("issues", [])
        if isinstance(item, Mapping)
    ]
    if not issue_rows:
        issue_rows = ["<li>No issues in dataset report.</li>"]

    gates_html = [
        f"<li><strong>{escape(str(gate['gate']))}</strong> {escape(str(gate['status']))}: "
        f"{escape(str(gate['details']))}</li>"
        for gate in summary["gates"]
    ]

    artifact_rows = [
        f"<li>{escape(str(key))}: sha256={escape(str((value or {}).get('sha256', 'n/a')))} size={escape(str((value or {}).get('size', 'n/a')))}</li>"
        for key, value in snapshot_report.get("artifacts", {}).items()
    ]
    if not artifact_rows:
        artifact_rows = ["<li>artifact list unavailable</li>"]

    balance_sections = []
    for title, counts in (
        ("Split", summary["balance"]["by_split"]),
        ("Domain", summary["balance"]["by_domain"]),
        ("Principle", summary["balance"]["by_principle"]),
        ("Source type", summary["balance"]["by_source_type"]),
        ("License", summary["balance"]["by_license"]),
    ):
        body = "".join(
            f"<li>{escape(str(name))}: {escape(str(value))}</li>" for name, value in sorted(counts.items())
        ) or "<li>empty</li>"
        balance_sections.append(f"<section><h2>{escape(title)} distribution</h2><ul>{body}</ul></section>")

    coverage_rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            escape(str(row["case_id"])),
            escape(str(row["observed_raters"])),
            escape(str(row["minimum_raters"])),
            escape(str(row["status"])),
        )
        for row in summary["snapshot"]["rater_coverage"]["per_case"]
    )
    if not coverage_rows:
        coverage_rows = "<tr><td colspan='4'>no case-level coverage data</td></tr>"

    findings = summary["findings"]["duplicate_leakage"]
    finding_rows = [
        f"<li>{escape(str(item.get('code')))} on {escape(str(item.get('case_id', 'n/a')))}: {escape(str(item.get('message', '')))}</li>"
        for item in findings
    ]
    if not finding_rows:
        finding_rows = ["<li>No duplicate/leakage findings.</li>"]

    lines = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>Latent TRIZ Lab 02 Dataset Readiness Report</title>",
        "<style>",
        "body{margin:0;padding:1rem;font-family:Inter,Segoe UI,Arial,sans-serif;background:#0b1220;color:#e5e7eb;}",
        "main{max-width:1200px;margin:0 auto;display:grid;gap:1rem;}",
        "section{background:#111827;padding:1rem;border:1px solid #374151;border-radius:8px;}",
        ".notice{background:#1f2937;border-left:6px solid #93c5fd;padding:0.75rem 1rem;}",
        "table{width:100%;border-collapse:collapse;font-size:.9rem;}",
        "th,td{border:1px solid #374151;padding:.45rem;text-align:left;}",
        "th{background:#1f2937;}",
        ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.75rem;}",
        ".mono{font-family:ui-monospace,Consolas,monospace;word-break:break-word;}",
        "@media (max-width: 800px){body{padding:.6rem;}}",
        "</style>",
        "</head><body><main>",
        "<header class='notice'>"
        "<h1>Latent TRIZ Lab 02 — Synthetic Readiness Report</h1>"
        "<p>Current pilot is <strong>synthetic/non_empirical</strong> with <strong>evidence_eligible = false</strong> and <strong>claim_ids = []</strong>.</p>"
        "<p>No TRIZ claim is made from this run.</p>"
        "<p>Readiness vs scientific evidence: this report communicates gating quality and audit structure, not evidence-grade conclusions.</p>"
        "</header>",
        "<section><h2>Fail-closed gates (D1–D8)</h2><ul>" + "".join(gates_html) + "</ul></section>",
        "<section><h2>Readiness summary</h2>"
        "<p>Status: <strong>" + escape(str(summary["status"])) + "</strong></p>"
        "<p>" + escape(str(summary["summary_artifacts"]["readiness_statement"])) + "</p>"
        "</section>",
        "<section><h2>Dataset audit checks</h2>"
        f"<p>Mode: {escape(str(dataset_report.get('mode', 'n/a')))} | Status: {escape(str(dataset_report.get('status', 'n/a')))} | "
        f"Issue count: {escape(str(summary['dataset']['issue_count']))}</p><ul>" + "".join(issue_rows) + "</ul></section>",
        "<section><h2>Snapshot manifest metadata</h2><ul>"
        f"<li>snapshot_id: {escape(str(snapshot_report.get('snapshot_id', 'n/a')))}</li>"
        f"<li>dataset_id: {escape(str(snapshot_report.get('dataset_id', 'n/a')))}</li>"
        f"<li>immutable_revision: {escape(str(snapshot_report.get('immutable_revision', 'n/a')))}</li>"
        f"<li>split_membership_digest: {escape(str(snapshot_report.get('split_membership_digest', 'n/a')))}</li>"
        f"<li>status: {escape(str(snapshot_report.get('status', 'n/a')))}</li>"
        "</ul></section>",
        "<section><h2>Artifact hashes</h2><ul>" + "".join(artifact_rows) + "</ul></section>",
        "<section><h2>Balance and provenance</h2>" + "".join(balance_sections) + "</section>",
        "<section><h2>Annotation coverage by case</h2>"
        "<table><thead><tr><th>Case</th><th>Observed raters</th><th>Minimum</th><th>Coverage pass</th></tr></thead>"
        f"<tbody>{coverage_rows}</tbody></table></section>",
        "<section><h2>Agreement</h2><pre class='mono'>"
        + escape(stable_json_dumps(summary["snapshot"]["agreement"]))
        + "</pre></section>",
        "<section><h2>Duplicate/leakage findings</h2><ul>" + "".join(finding_rows) + "</ul></section>",
        "<section><h2>Output hashes</h2><pre class='mono'>"
        + escape(stable_json_dumps(summary["hashes"]))
        + "</pre></section>",
        "</main></body></html>",
    ]
    return "".join(lines)


def _gate_d1(dataset_report: Mapping[str, Any], snapshot_report: Mapping[str, Any]) -> tuple[bool, str]:
    if not isinstance(dataset_report, Mapping):
        return False, "dataset report is not an object"
    if not isinstance(snapshot_report, Mapping):
        return False, "snapshot report is not an object"
    if snapshot_report.get("artifact_class") != "dataset-instrumentation":
        return False, "snapshot artifact_class is not dataset-instrumentation"
    if snapshot_report.get("empirical") is not False:
        return False, "snapshot empirical must be false"
    if not isinstance(snapshot_report.get("counts"), Mapping):
        return False, "snapshot counts missing"
    if not isinstance(snapshot_report.get("rater_coverage"), Mapping):
        return False, "snapshot rater_coverage missing"
    if not isinstance(snapshot_report.get("agreement"), Mapping):
        return False, "snapshot agreement missing"
    if snapshot_report.get("status") not in {"pass", "fail"}:
        return False, "snapshot status must be pass/fail"
    if "issues" not in snapshot_report:
        return False, "snapshot issues missing"
    return True, ""


def _gate_d2(issues: list[dict[str, Any]]) -> tuple[bool, str]:
    found = [item["code"] for item in issues if item.get("code") in _PROVENANCE_LICENSE_ISSUES]
    return (not found, ", ".join(found))


def _gate_d3(artifacts: Any) -> tuple[bool, str]:
    if not isinstance(artifacts, Mapping):
        return False, "artifacts not a mapping"
    missing: list[str] = []
    for key in _REQUIRED_ARTIFACT_DIGEST_KEYS:
        entry = artifacts.get(key)
        if not isinstance(entry, Mapping):
            missing.append(f"{key}.missing")
            continue
        if "sha256" not in entry:
            missing.append(f"{key}.sha256")
        if "size" not in entry:
            missing.append(f"{key}.size")
        if key.endswith("_jsonl"):
            if "path" not in entry:
                missing.append(f"{key}.path")
            elif not str(entry.get("path")):
                missing.append(f"{key}.path")
    return (not missing, ", ".join(missing))


def _gate_d4(snapshot_report: Mapping[str, Any]) -> tuple[bool, str]:
    digest = snapshot_report.get("split_membership_digest")
    if not isinstance(digest, str):
        return False, "missing split_membership_digest"
    if not digest.startswith("sha256:"):
        return False, "split_membership_digest has invalid format"
    return True, ""


def _gate_d5(issues: list[dict[str, Any]]) -> tuple[bool, str]:
    codes = {item.get("code") for item in issues if isinstance(item, Mapping) and item.get("code")}
    hits = sorted(code for code in codes if code in _DUPLICATE_LEAKAGE_ISSUES)
    return (not hits, ", ".join(hits))


def _gate_d6(dataset_report: Mapping[str, Any], snapshot_issues: list[dict[str, Any]]) -> tuple[bool, str]:
    target_gaps = dataset_report.get("target_gaps", [])
    if target_gaps and isinstance(target_gaps, list):
        open_gaps = [item for item in target_gaps if isinstance(item, Mapping)]
    elif target_gaps:
        return False, "target_gaps type invalid"
    else:
        open_gaps = []
    issue_codes = {item.get("code") for item in snapshot_issues if isinstance(item, Mapping) and item.get("code")}
    fail_codes = sorted(code for code in issue_codes if code in _BALANCE_ISSUES)
    if fail_codes:
        return False, ", ".join(fail_codes)
    if open_gaps:
        return False, "dataset target_gaps present"
    return True, ""


def _gate_d7(
    snapshot_report: Mapping[str, Any],
    minimum_raters: int,
    coverage_counts: Mapping[str, int],
    case_ids: list[str],
    agreement: Mapping[str, Any],
) -> tuple[bool, str]:
    # Every case in manifest must satisfy minimum rater requirement.
    if minimum_raters < 1:
        return False, "minimum_raters must be >=1"
    missing = [
        case_id for case_id in case_ids
        if int(coverage_counts.get(case_id, 0)) < minimum_raters
    ]
    if missing:
        return False, "missing coverage for: " + ", ".join(sorted(missing))
    if not bool(agreement.get("minimum_met")):
        return False, "agreement.minimum_met is false"
    return True, ""


def _gate_d8(dataset_report: Mapping[str, Any], snapshot_report: Mapping[str, Any]) -> tuple[bool, str]:
    reasons: list[str] = []
    if dataset_report.get("empirical", False) is not False:
        reasons.append("dataset payload empirical flag not false")
    if dataset_report.get("evidence_eligible", False) is not False:
        reasons.append("dataset evidence_eligible not false")
    claim_ids = dataset_report.get("claim_ids", [])
    if isinstance(claim_ids, list) and claim_ids:
        reasons.append("dataset claim_ids not empty")
    if snapshot_report.get("empirical") is not False:
        reasons.append("snapshot empirical flag not false")
    if snapshot_report.get("evidence_eligible") is not False:
        reasons.append("snapshot evidence_eligible not false")
    if snapshot_report.get("claim_ids"):
        reasons.append("snapshot claim_ids not empty")
    return (not reasons, " ".join(reasons))


def _collect_source_license_distribution(snapshot_report: Mapping[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
    counts = snapshot_report.get("counts", {})
    return _coerce_counts(counts, "by_source_type"), _coerce_counts(counts, "by_license")


def _collect_distribution_by_field(snapshot_report: Mapping[str, Any], key_path: tuple[str, str]) -> dict[str, int]:
    # Retained for compatibility with report rendering expectations.
    field_values = _coerce_list(snapshot_report.get(key_path[0]))
    result: dict[str, int] = {}
    for value in field_values:
        if not isinstance(value, Mapping):
            continue
        case_id = str(value.get("case_id", "")).strip()
        if not case_id:
            continue
        key = str(value.get(key_path[1], "unknown"))
        result[key] = result.get(key, 0) + 1
    return result


def _coerce_counts(source: Any, key: str) -> dict[str, int]:
    value = source.get(key) if isinstance(source, Mapping) else None
    if not isinstance(value, Mapping):
        return {}
    return {str(name): int(v) for name, v in value.items() if isinstance(v, int)}


def _coerce_mapping(value: Any, key: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    raw = value.get(key, {}) if key else value
    return {str(name): int(count) for name, count in raw.items() if isinstance(count, int)}


def _coerce_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _as_issue_list(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def _load_report(report: str | Path | Mapping[str, Any], label: str) -> dict[str, Any]:
    if isinstance(report, Mapping):
        return dict(report)
    path = Path(report)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise Lab02Error(f"{label}: report file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise Lab02Error(f"{label}: invalid JSON: {exc}") from exc
    except OSError as exc:
        raise Lab02Error(f"{label}: cannot read report: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise Lab02Error(f"{label}: expected JSON object")
    return payload


def _as_path(report: str | Path | Mapping[str, Any], report_type: str) -> Path | None:
    if isinstance(report, (str, Path)):
        path = Path(report).resolve()
        if not path.is_file():
            raise Lab02Error(f"{report_type}: file not found: {path}")
        return path
    return None


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
