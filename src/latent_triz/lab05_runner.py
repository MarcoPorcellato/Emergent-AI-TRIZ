from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence

from .lab04 import stable_json_dumps
from .lab05 import run_lab05_analysis


@dataclass(frozen=True)
class RunArtifacts:
    direction_result: Path
    summary: Path
    report_html: Path


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_object(source: str | Path | Mapping[str, Any], label: str) -> dict[str, Any]:
    if isinstance(source, Mapping):
        return dict(source)
    path = Path(source).resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {label}: {path}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be an object")
    return dict(payload)


def _verify_predecessor(summary: Mapping[str, Any]) -> tuple[bool, bool, str]:
    classification_ok = (
        summary.get("artifact_class") == "representation-decodability-instrumentation"
        and summary.get("empirical") is False
        and summary.get("evidence_eligible") is False
        and summary.get("claim_ids") == []
    )
    hashes = summary.get("hashes")
    integrity_ok = False
    if isinstance(hashes, Mapping) and isinstance(hashes.get("summary_json"), str):
        canonical = dict(summary)
        canonical["hashes"] = dict(hashes)
        canonical["hashes"]["summary_json"] = ""
        integrity_ok = _sha256_text(stable_json_dumps(canonical)) == hashes["summary_json"]
    ready = classification_ok and integrity_ok and summary.get("status") == "pass"
    if not classification_ok:
        detail = "Lab 04 classification boundary is invalid"
    elif not integrity_ok:
        detail = "Lab 04 canonical summary hash is invalid"
    elif summary.get("status") != "pass":
        detail = "Lab 04 is integrity-checked but its scientific readiness status is fail"
    else:
        detail = "Lab 04 classification, integrity, and readiness pass"
    return integrity_ok, ready, detail


def _render_html(payload: Mapping[str, Any]) -> str:
    status = escape(str(payload.get("status", "fail")))
    gates = "".join(
        "<li><strong>{}</strong> [{}] {}</li>".format(
            escape(str(row.get("gate", ""))),
            escape(str(row.get("status", ""))),
            escape(str(row.get("details", ""))),
        )
        for row in payload.get("gates", [])
    )
    issues = "".join(f"<li>{escape(str(item))}</li>" for item in payload.get("issues", []))
    layer_rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            escape(str(row.get("layer_index", ""))),
            escape(str(row.get("case_count", 0))),
            escape(str(row.get("candidate_direction", {}).get("available", False))),
            escape(str(row.get("candidate_direction", {}).get("l2_norm", 0.0))),
        )
        for row in payload.get("layers", [])
    )
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\">
<title>Lab 05 candidate directions</title><style>
body{{font:16px/1.5 system-ui,sans-serif;max-width:900px;margin:auto;padding:2rem;color:#172033}}
.boundary{{border:2px solid #b42318;background:#fff1f0;padding:1rem}} table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccd2dc;padding:.5rem;text-align:left}} code{{background:#eef1f5;padding:.1rem .3rem}}
</style></head><body><h1>Lab 05 — candidate directions</h1>
<div class=\"boundary\"><strong>Status: {status}</strong><br>
Diagnostic instrumentation only. This run is non-empirical, not evidence-eligible, and supports no Latent TRIZ, causal, intervention, or steering claim.</div>
<h2>Readiness gates</h2><ul>{gates or '<li>No gate records.</li>'}</ul>
<h2>Open issues</h2><ul>{issues or '<li>None.</li>'}</ul>
<h2>Layer diagnostics</h2><table><thead><tr><th>Layer</th><th>Cases</th><th>Direction available</th><th>L2 norm</th></tr></thead><tbody>{layer_rows}</tbody></table>
<p>Dense directions are never published. Public artifacts contain only norms, hashes, projections, and control summaries.</p>
</body></html>"""


def run_lab05_bundle(
    cases_path: str | Path,
    representations_path: str | Path,
    config: str | Path | Mapping[str, Any],
    predecessor_summary: str | Path | Mapping[str, Any],
    *,
    output_dir: str | Path,
) -> RunArtifacts:
    cases_file = Path(cases_path).resolve()
    representations_file = Path(representations_path).resolve()
    config_map = _load_object(config, "Lab 05 config")
    predecessor = _load_object(predecessor_summary, "Lab 04 summary")
    predecessor_path = Path(predecessor_summary).resolve() if not isinstance(predecessor_summary, Mapping) else None
    config_path = Path(config).resolve() if not isinstance(config, Mapping) else None
    integrity_ok, predecessor_ready, predecessor_detail = _verify_predecessor(predecessor)

    analysis_config = dict(config_map)
    analysis_config["predecessor_ready"] = predecessor_ready
    analysis = run_lab05_analysis(cases_file, representations_file, analysis_config, predecessor)
    analysis["input_hashes"]["config"] = (
        _sha256_path(config_path)
        if config_path
        else _sha256_text(stable_json_dumps(config_map))
    )
    analysis["predecessor"] = {
        "status": predecessor.get("status", "fail"),
        "integrity_verified": integrity_ok,
        "scientifically_ready": predecessor_ready,
        "details": predecessor_detail,
        "summary_sha256": _sha256_path(predecessor_path) if predecessor_path else _sha256_text(stable_json_dumps(predecessor)),
    }

    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    direction_path = output / "direction_result.json"
    summary_path = output / "summary.json"
    report_path = output / "report.html"
    direction_text = stable_json_dumps(analysis)
    direction_path.write_text(direction_text, encoding="utf-8")

    summary = dict(analysis)
    summary["hashes"] = {
        "cases_jsonl": _sha256_path(cases_file),
        "representations_jsonl": _sha256_path(representations_file),
        "config_json": _sha256_path(config_path) if config_path else _sha256_text(stable_json_dumps(config_map)),
        "predecessor_lab04_summary": analysis["predecessor"]["summary_sha256"],
        "direction_result_json": _sha256_text(direction_text),
        "report_html": "",
        "summary_json": "",
    }
    summary["summary_artifacts"] = {
        "generated_by": "lab05_candidate_direction_runner",
        "readiness_statement": "Candidate directions are descriptive diagnostics, not causal or steering evidence.",
        "direction_result": "direction_result.json",
        "html": "report.html",
        "summary": "summary.json",
    }
    html = _render_html(summary)
    report_path.write_text(html, encoding="utf-8")
    summary["hashes"]["report_html"] = _sha256_text(html)
    canonical = dict(summary)
    canonical["hashes"] = dict(summary["hashes"])
    canonical["hashes"]["summary_json"] = ""
    summary["hashes"]["summary_json"] = _sha256_text(stable_json_dumps(canonical))
    summary_path.write_text(stable_json_dumps(summary), encoding="utf-8")
    return RunArtifacts(direction_path, summary_path, report_path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run fail-closed Lab 05 candidate-direction diagnostics")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--representations", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--predecessor-lab04-summary", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    artifacts = run_lab05_bundle(
        args.cases,
        args.representations,
        args.config,
        args.predecessor_lab04_summary,
        output_dir=args.output_dir,
    )
    payload = json.loads(artifacts.summary.read_text(encoding="utf-8"))
    print(stable_json_dumps({"status": payload["status"], "summary": str(artifacts.summary)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
