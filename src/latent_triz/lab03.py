from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Mapping

from .lab03_baselines import Lab03Error, _sha256_file, _sha256_text, run_behavioral_baselines, stable_json_dumps


def build_lab03_report(
    baseline_result: str | Path | Mapping[str, Any],
    *,
    output_html: str | Path | None = None,
    output_summary: str | Path | None = None,
) -> dict[str, Any]:
    if isinstance(baseline_result, (str, Path)):
        import json

        try:
            baseline_path = Path(baseline_result).resolve()
            payload = json.loads(baseline_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise Lab03Error(f"baseline file not found: {baseline_result}") from exc
        except Exception as exc:  # noqa: BLE001
            raise Lab03Error(f"invalid baseline payload: {baseline_result}: {exc}") from exc
        baseline_name = baseline_path.name
    else:
        payload = dict(baseline_result)
        baseline_path = None
        baseline_name = "baseline_result.json"

    if not isinstance(payload, Mapping):
        raise Lab03Error("baseline result is not an object")

    gates = payload.get("gates")
    if not isinstance(gates, list):
        raise Lab03Error("baseline payload missing gates")

    report = {
        "artifact_class": payload.get("artifact_class", "behavioral-baseline-report"),
        "empirical": False,
        "evidence_eligible": False,
        "claim_ids": [],
        "status": "pass" if all(item.get("status") == "pass" for item in gates) else "fail",
        "snapshot": payload.get("snapshot", {}),
        "cases": payload.get("cases", {}),
        "gates": gates,
        "methods": payload.get("methods", {}),
        "random_label_control": payload.get("random_label_control", {}),
        "shortcuts": payload.get("shortcuts", {}),
        "issues": payload.get("issues", []),
        "interpretation": (
            "diagnostic_only_not_scientifically_interpretable"
            if any(item.get("gate") in {"B1", "B2"} and item.get("status") != "pass" for item in gates)
            else "readiness_gates_evaluable"
        ),
        "hashes": {
            "baseline_jsonl": "",
            "report_html": "",
            "summary_json": "",
            "snapshot_hash": payload.get("provenance", {}).get("snapshot_sha256", ""),
            "config_hash": payload.get("provenance", {}).get("config_sha256", payload.get("config_hash", "")),
            "cases_hash": payload.get("provenance", {}).get("cases_sha256", ""),
        },
        "summary_artifacts": {
            "generated_by": "lab03_report_renderer",
            "readiness_statement": "No Latent TRIZ claim is made from this run. This is a deterministic baseline-only gate report.",
            "baseline": baseline_name,
        },
    }

    if baseline_path is not None:
        report["hashes"]["baseline_jsonl"] = _sha256_file(baseline_path)

    html_payload = _render_html(report)
    report["hashes"]["report_html"] = _sha256_text(html_payload)

    if output_html is not None:
        out_path = Path(output_html).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html_payload, encoding="utf-8")
        report["summary_artifacts"]["html"] = out_path.name

    if output_summary is not None:
        out_path = Path(output_summary).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        to_write = dict(report)
        to_write["hashes"] = dict(report["hashes"])
        out_path.write_text(stable_json_dumps(to_write) + "\n", encoding="utf-8")
        report["summary_artifacts"]["summary"] = out_path.name

    hash_input = dict(report)
    hashes_copy = dict(hash_input.get("hashes", {}))
    hashes_copy["summary_json"] = ""
    hash_input["hashes"] = hashes_copy
    report["hashes"]["summary_json"] = _sha256_text(stable_json_dumps(hash_input))

    if output_summary is not None:
        out_path = Path(output_summary).resolve()
        out_path.write_text(stable_json_dumps(report) + "\n", encoding="utf-8")

    return report


def _render_html(payload: Mapping[str, Any]) -> str:
    gates = payload.get("gates", [])
    cases = payload.get("cases", {})
    methods = payload.get("methods", {})
    random_control = payload.get("random_label_control", {})
    shortcut_payload = payload.get("shortcuts", {})
    provenance_shortcuts = shortcut_payload.get("provenance", {}) if isinstance(shortcut_payload, Mapping) else {}
    visible_hashes = {
        key: value
        for key, value in payload.get("hashes", {}).items()
        if key not in {"report_html", "summary_json"}
    }

    issue_items = []
    for issue in payload.get("issues", []):
        if isinstance(issue, Mapping):
            code = issue.get("code", "invalid")
            message = issue.get("message", "")
            case_id = issue.get("case_id", "")
            detail = f"{code}: {message}" if message else str(code)
            if case_id:
                detail = f"{detail} ({case_id})"
            issue_items.append(f"<li>{escape(detail)}</li>")
    if not issue_items:
        issue_items = ["<li>None</li>"]

    gate_rows = [
        f"<li><strong>{escape(str(g.get('gate')))}</strong> {escape(str(g.get('status', 'fail')))}: {escape(str(g.get('details', '')))}</li>"
        for g in gates
    ]

    method_cards = []
    for method in sorted(methods):
        row = methods[method]
        if not isinstance(row, Mapping):
            continue
        rows = []
        if row.get("status") in {"not_run", "not_completed", "invalid", "not_requested"}:
            rows.append(f"<p>status: {escape(str(row.get('status')))}</p>")
            rows.append(f"<p>{escape(str(row.get('reason', 'not requested')))}</p>")
        else:
            views = row.get("views", {})
            for view_name in sorted(views):
                view = views[view_name]
                if not isinstance(view, Mapping):
                    continue
                agg = view.get("aggregate", {})
                if not isinstance(agg, Mapping):
                    agg = {}
                accuracy = round(float(agg.get("accuracy", 0.0)), 4)
                macro_f1 = round(float(agg.get("macro_f1", 0.0)), 4)
                balanced = round(float(agg.get("balanced_accuracy", 0.0)), 4)
                rows.append(f"<h4>{escape(view_name)}</h4><p>accuracy={accuracy}, macro_f1={macro_f1}, balanced_accuracy={balanced}</p>")
                fold_rows = []
                for fold in view.get("folds", []):
                    if not isinstance(fold, Mapping):
                        continue
                    fold_rows.append(
                        "<tr>"
                        f"<td>{escape(str(fold.get('domain', '')))}</td>"
                        f"<td>{escape(str(fold.get('train_count', 0)))}</td>"
                        f"<td>{escape(str(fold.get('test_count', 0)))}</td>"
                        f"<td>{escape(str(fold.get('status', '')))}</td>"
                        "</tr>"
                    )
                if not fold_rows:
                    fold_rows = ["<tr><td colspan='4'>no folds</td></tr>"]
                rows.append(
                    "<table><thead><tr><th>Domain</th><th>Train</th><th>Test</th><th>Status</th></tr></thead><tbody>"
                    + "".join(fold_rows)
                    + "</tbody></table>"
                )
        method_cards.append("<section><h3>" + escape(method) + "</h3>" + "".join(rows) + "</section>")

    random_rows = []
    if isinstance(random_control, Mapping):
        random_rows.append(f"<p>status: {escape(str(random_control.get('status', '')))}</p>")
        random_rows.append(f"<p>seed: {escape(str(random_control.get('seed', '')))}</p>")
        random_rows.append(f"<p>permutations: {escape(str(random_control.get('permutations', '')))}</p>")

    lines = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>Latent TRIZ Lab 03 Behavioral Baselines Report</title>",
        "<style>",
        "body{margin:0;padding:1rem;font-family:Inter,system-ui,sans-serif;background:#0a1120;color:#e5e7eb;}",
        "main{max-width:1100px;margin:0 auto;display:grid;gap:1rem;}",
        "section{background:#111827;padding:1rem;border:1px solid #374151;border-radius:8px;}",
        "h1,p{margin:.25rem 0}",
        ".notice{background:#1f2937;border-left:6px solid #93c5fd;padding:0.75rem 1rem;}",
        "table{width:100%;border-collapse:collapse;margin-top:.5rem;font-size:.9rem;}",
        "th,td{padding:.4rem;border:1px solid #374151;}",
        "th{background:#1f2937;}",
        ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.8rem;}",
        "@media (max-width: 700px){body{padding:.5rem;} th,td{font-size:.8rem;}}",
        "</style>",
        "</head><body><main>",
        "<header class='notice'><h1>Latent TRIZ Lab 03 — Behavioral Baselines</h1>",
        f"<p>Status: <strong>{escape(str(payload.get('status', 'fail')))}</strong></p>",
        "<p>Experimental boundary: No Latent TRIZ claim is made from this run.</p>",
        f"<p>Interpretation: {escape(str(payload.get('interpretation', 'diagnostic_only')))}</p>",
        "</header>",
        "<section><h2>Fail-closed gates (B1–B8)</h2><ul>" + "".join(gate_rows) + "</ul></section>",
        "<section><h2>Data summary</h2><div class='grid'>"
        f"<div>Total cases: {escape(str(cases.get('total_cases', 0)))}" + "</div>"
        f"<div>Labels: {escape(str(cases.get('label_count', 0)))}" + "</div>"
        f"<div>Domains: {escape(str(cases.get('domain_count', 0)))}" + "</div>"
        "</div></section>",
        "<section><h2>Issues</h2><ul>" + "".join(issue_items) + "</ul></section>",
        "<section><h2>Method and fold results</h2>" + "".join(method_cards) + "</section>",
        "<section><h2>Random-label control</h2>" + "".join(random_rows) + "</section>",
        "<section><h2>Provenance shortcut diagnostics</h2><pre class='mono'>"
        + escape(stable_json_dumps(provenance_shortcuts)) + "</pre></section>",
        "<section><h2>Input and baseline hashes</h2><pre class='mono'>" + escape(stable_json_dumps(visible_hashes)) + "</pre>"
        "<p>The canonical summary records the report and summary digests without creating a self-hash cycle.</p></section>",
        "</main></body></html>",
    ]
    return "".join(lines)


def main(argv: list[str] | None = None) -> int:
    from .lab03_runner import run_lab03_bundle

    import argparse

    parser = argparse.ArgumentParser(description="Build Lab 03 report from a baseline JSON payload")
    parser.add_argument("baseline")
    parser.add_argument("--output-html")
    parser.add_argument("--output-summary")
    args = parser.parse_args(argv)

    build_lab03_report(
        baseline_result=args.baseline,
        output_html=args.output_html,
        output_summary=args.output_summary,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
