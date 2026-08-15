"""Deterministic, evidence-bounded HTML publication report for A0."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any


class A0ReportError(RuntimeError):
    """Raised when the immutable A0 report cannot be rendered."""


EPISTEMIC = {
    "empirical": True,
    "scientific_status": "exploratory",
    "evidence_eligible": False,
    "expert_validated": False,
    "claim_ids": [],
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_a0_report(
    *,
    result_path: str | Path,
    output_dir: str | Path,
    receipt_path: str | Path,
    index_path: str | Path,
) -> tuple[Path, Path]:
    result_path = Path(result_path).resolve()
    output_dir = Path(output_dir).resolve()
    receipt_path = Path(receipt_path).resolve()
    index_path = Path(index_path).resolve()
    report_path = output_dir / "report.html"
    manifest_path = output_dir / "publication-manifest.json"
    if report_path.exists() or manifest_path.exists():
        raise A0ReportError("refusing to overwrite an existing A0 publication")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise A0ReportError("statistical result must be an object")
    for key, expected in EPISTEMIC.items():
        if result.get(key) != expected:
            raise A0ReportError(f"result has invalid epistemic field {key}")

    status = html.escape(str(result["status"]))
    p_value = html.escape(f"{float(result['max_statistic_p']):.6f}")
    margin = html.escape(f"{float(result['macro_f1_margin_over_surface']):.6f}")
    interpretation = html.escape(str(result["interpretation"]))
    report = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Latent TRIZ A0 exploratory result</title>
<meta name="robots" content="noindex">
<style>body{{font:16px system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#17202a}}
table{{border-collapse:collapse}}td,th{{padding:.45rem .7rem;border:1px solid #ccd}}.boundary{{background:#fff4d6;padding:1rem}}
</style></head><body>
<h1>A0 automated weak-proxy exploration</h1>
<p><strong>Final status:</strong> {status}</p>
<table><tr><th>Max-statistic p</th><td>{p_value}</td></tr>
<tr><th>Macro-F1 margin over problem-only surface baseline</th><td>{margin}</td></tr>
<tr><th>Observed maximum paired family successes</th><td>{int(result["observed_max_family_successes"])}</td></tr></table>
<h2>Interpretation</h2><p>{interpretation}</p>
<div class="boundary"><strong>Epistemic boundary.</strong>
This is an empirical exploratory result for the frozen automated operator proxies.
It is not expert validation of TRIZ Segmentation or Inversion and is not eligible
as hypothesis evidence.</div>
<h2>Reproducibility</h2><p>Protocol: {html.escape(str(result["protocol_id"]))}.
Inputs and artifact hashes are recorded in <code>publication-manifest.json</code>.</p>
</body></html>
"""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    manifest = {
        "artifact_class": "a0-publication-manifest",
        **EPISTEMIC,
        "status": "pass",
        "result": {"path": result_path.name, "sha256": _sha256(result_path)},
        "report": {"path": report_path.name, "sha256": _sha256(report_path)},
        "activation_receipt": {"path": receipt_path.name, "sha256": _sha256(receipt_path)},
        "representation_index": {"path": index_path.name, "sha256": _sha256(index_path)},
    }
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return report_path, manifest_path
