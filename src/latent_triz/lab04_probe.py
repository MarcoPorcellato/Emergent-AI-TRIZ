from __future__ import annotations

import hashlib
import json
from html import escape
from pathlib import Path
from typing import Any, Mapping

from .lab04 import Lab04Error, stable_json_dumps


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _to_payload(source: str | Path | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    payload_path = Path(source).resolve()
    try:
        raw = payload_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise Lab04Error(f"probe payload not found: {source}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Lab04Error(f"invalid JSON in probe payload: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise Lab04Error("probe payload must be an object")
    return dict(parsed)


def _format_float(value: Any) -> str:
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return "0.000000"


def _render_html(payload: Mapping[str, Any]) -> str:
    status = str(payload.get("status", "fail"))
    non_claim = str(
        payload.get(
            "non_claim_boundary",
            "No Latent TRIZ claim is made from this run. Decodability is correlational, not causal.",
        )
    )
    gates = payload.get("gates", [])
    layers = payload.get("layers", [])
    case_summary = payload.get("case_summary", {})
    random_control = payload.get("random_control", {})

    gate_rows: list[str] = []
    for item in gates:
        name = escape(str(item.get("gate", "")))
        gate_status = escape(str(item.get("status", "")))
        gate_details = escape(str(item.get("details", "")))
        gate_rows.append(f"<li><strong>{name}</strong> [{gate_status}] {gate_details}</li>")
    if not gate_rows:
        gate_rows.append("<li>No gate records.</li>")

    layer_rows: list[str] = []
    for layer in layers:
        layer_id = escape(str(layer.get("layer", "")))
        selected_alpha = _format_float(layer.get("selected_alpha", 0.0))
        p_raw = _format_float(layer.get("p_value_raw", 1.0))
        p_holm = _format_float(layer.get("p_value_holm", 1.0))
        agg = layer.get("aggregate", {})

        fold_rows: list[str] = []
        for fold in layer.get("folds", []):
            m = fold.get("metrics", {})
            fold_rows.append(
                "<tr>"
                f"<td>{escape(str(fold.get('domain','')))}</td>"
                f"<td>{escape(str(fold.get('train_count',0)))}</td>"
                f"<td>{escape(str(fold.get('test_count',0)))}</td>"
                f"<td>{escape(str(fold.get('status','')))}</td>"
                f"<td>{_format_float(m.get('accuracy', 0.0))}</td>"
                f"<td>{_format_float(m.get('macro_f1', 0.0))}</td>"
                f"<td>{_format_float(m.get('balanced_accuracy', 0.0))}</td>"
                f"<td>{_format_float(fold.get('majority_margin', 0.0))}</td>"
                f"<td>{_format_float(fold.get('permutation_p', 1.0))}</td>"
                "<td>" + escape(str(fold.get("details", ""))) + "</td>"
                "</tr>"
            )
        if not fold_rows:
            fold_rows.append("<tr><td colspan=9>no folds</td></tr>")

        layer_rows.append(
            "<section class='card'>"
            f"<h3>Layer {layer_id}</h3>"
            f"<p>selected_alpha={selected_alpha} p_raw={p_raw} p_holm={p_holm} "+
            f"permutations={escape(str(layer.get('permutation_count', 0)))}"+"</p>"
            f"<p>accuracy={_format_float(agg.get('accuracy', 0.0))}, macro_f1={_format_float(agg.get('macro_f1', 0.0))}, balanced_accuracy={_format_float(agg.get('balanced_accuracy', 0.0))}</p>"
            "<table><thead><tr><th>Domain</th><th>Train</th><th>Test</th><th>Status</th><th>Accuracy</th><th>Macro-F1</th><th>Balanced Acc</th><th>Majority Margin</th><th>Permutation p</th><th>Details</th></tr></thead><tbody>"
            + "".join(fold_rows)
            + "</tbody></table>"
            "</section>"
        )

    html_parts: list[str] = [
        "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>Latent TRIZ Lab 04 Probe</title>",
        "<style>body{margin:0;padding:1rem;font-family:Arial,sans-serif;background:#0f172a;color:#e5e7eb}"\
        " .card{background:#111827;padding:1rem;border:1px solid #334155;border-radius:.6rem;margin:.8rem 0;}"
        "table{width:100%;border-collapse:collapse;} th,td{border:1px solid #334155;padding:.4rem;text-align:left;word-break:break-word;}"
        "th{background:#1f2937;}</style>",
        "</head><body><main>",
        "<section class='card'><h1>Latent TRIZ Lab 04</h1><p>Status: <strong>" + escape(status) + "</strong></p>",
        "<p>" + escape(non_claim) + "</p>",
        "<p>No Latent TRIZ claim.</p><p>Decodability is correlational, not causal.</p>",
        "</section>",
        "<section class='card'><h2>Case summary</h2><pre>",
        escape(stable_json_dumps(case_summary)),
        "</pre></section>",
        "<section class='card'><h2>Random control</h2><p>seed=" + escape(str(random_control.get("seed", ""))) + "</p>"
        "<p>permutations=" + escape(str(random_control.get("permutations", ""))) + "</p>"
        "<p>method=" + escape(str(random_control.get("method", ""))) + "</p>"
        "<p>formula=" + escape(str(random_control.get("formula", ""))) + "</p>"
        "</section>",
        "<section class='card'><h2>Gate checks</h2><ul>" + "".join(gate_rows) + "</ul></section>",
    ]
    html_parts.extend(["<section class='card'><h2>Layers</h2>"])
    html_parts.extend(layer_rows or ["<p>no layer data</p>"])
    html_parts.append("</section>")
    html_parts.append("<section class='card'><h2>Hashes</h2><pre class='mono'>")
    html_parts.append(escape(stable_json_dumps(payload.get("hashes", {}))))
    html_parts.append("</pre></section>")
    html_parts.append("</main></body></html>")

    return "".join(html_parts)


def build_lab04_report(
    probe_result: str | Path | Mapping[str, Any],
    *,
    output_html: str | Path | None = None,
    output_summary: str | Path | None = None,
) -> dict[str, Any]:
    payload = _to_payload(probe_result)
    report = dict(payload)
    report["artifact_class"] = "representation-decodability-instrumentation"
    report["empirical"] = False
    report["evidence_eligible"] = False
    report["claim_ids"] = []
    report["interpretation"] = "diagnostic_only_not_scientifically_interpretable"
    report["summary_artifacts"] = {
        "generated_by": "lab04_report_renderer",
        "readiness_statement": (
            "No Latent TRIZ claim is made from this run. "
            "Decodability is correlational, not causal."
        ),
        "probe_result": "probe_result.json",
        "html": "report.html",
        "summary": "summary.json",
    }
    report["hashes"] = dict(payload.get("hashes", {}))
    report["hashes"].setdefault("probe_result_json", "")
    report["hashes"]["report_html"] = ""
    report["hashes"]["summary_json"] = ""

    html = _render_html(report)
    report["hashes"]["report_html"] = _sha256_text(html)

    canonical_summary = dict(report)
    canonical_summary["hashes"] = dict(report["hashes"])
    canonical_summary["hashes"]["summary_json"] = ""
    report["hashes"]["summary_json"] = _sha256_text(
        stable_json_dumps(canonical_summary)
    )

    if output_html is not None:
        html_path = Path(output_html).resolve()
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")
    if output_summary is not None:
        summary_path = Path(output_summary).resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(stable_json_dumps(report), encoding="utf-8")
    return report


def run_lab04_probe(
    *, probe_result: str | Path | Mapping[str, Any], output_dir: str | Path
) -> dict[str, Any]:
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    result_path = output / "probe_result.json"
    report_path = output / "report.html"
    summary_path = output / "summary.json"

    payload = _to_payload(probe_result)
    result_text = stable_json_dumps(payload)
    result_path.write_text(result_text, encoding="utf-8")
    report_input = dict(payload)
    report_input["hashes"] = dict(payload.get("hashes", {}))
    report_input["hashes"]["probe_result_json"] = _sha256_text(result_text)
    report = build_lab04_report(
        report_input, output_html=report_path, output_summary=summary_path
    )
    return {
        "status": str(report.get("status", "fail")),
        "probe_result": str(result_path),
        "report": str(report_path),
        "summary": str(summary_path),
        "empirical": False,
        "evidence_eligible": False,
        "claim_ids": [],
        "gates": list(report.get("gates", [])),
    }


__all__ = ["build_lab04_report", "run_lab04_probe", "Lab04Error"]
