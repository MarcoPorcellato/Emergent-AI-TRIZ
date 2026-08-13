from __future__ import annotations

import hashlib
import json
from html import escape
from pathlib import Path
from typing import Sequence

from .pilot import PilotError, STANDARD_DIMENSIONS, score_annotations


TRACKED_PACKET_PATH = Path("data/pilot/packets.jsonl")
TRACKED_RESPONSE_PATH = Path("data/pilot/responses.jsonl")
TRACKED_ANNOTATION_PATH = Path("data/pilot/annotations.jsonl")
TRACKED_SUMMARY_PATH = Path("data/pilot/summary.json")


class Lab00Error(RuntimeError):
    pass


def build_lab00_report(
    packets_path: Path = TRACKED_PACKET_PATH,
    responses_path: Path = TRACKED_RESPONSE_PATH,
    annotations_path: Path = TRACKED_ANNOTATION_PATH,
    summary_path: Path = TRACKED_SUMMARY_PATH,
    output_path: Path | None = None,
) -> str:
    repo_root = Path(__file__).resolve().parents[2]
    packets_path = (repo_root / packets_path).resolve()
    responses_path = (repo_root / responses_path).resolve()
    annotations_path = (repo_root / annotations_path).resolve()
    summary_path = (repo_root / summary_path).resolve()

    packets = _read_jsonl_records(packets_path, "packet")
    responses = _read_jsonl_records(responses_path, "response")
    annotations = _read_jsonl_records(annotations_path, "annotation")
    summary = _read_json_object(summary_path, "summary")

    try:
        regenerated_summary = score_annotations(
            str(packets_path),
            str(responses_path),
            str(annotations_path),
        )
    except PilotError as exc:
        raise Lab00Error(f"invalid Stage 1 artifact chain: {exc}") from None
    if _trimmed_summary(regenerated_summary) != _trimmed_summary(summary):
        raise Lab00Error("summary does not match the deterministic score of its source artifacts")

    _validate_inputs_non_empirical(packets, responses, annotations, summary)

    html = _render_html(
        packets=packets,
        responses=responses,
        annotations=annotations,
        summary=summary,
        packets_path=packets_path,
        responses_path=responses_path,
        annotations_path=annotations_path,
        summary_path=summary_path,
    )

    if output_path is None:
        return html

    output = Path(output_path).resolve()
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html, encoding="utf-8")
    except OSError as exc:
        raise Lab00Error(f"cannot write report {output}: {exc}") from None
    return str(output)



def _read_jsonl_records(path: Path, label: str) -> list[dict]:
    if not path.exists():
        raise Lab00Error(f"{label} file not found: {path}")

    records: list[dict] = []
    try:
        with path.open("r", encoding="utf-8") as fp:
            for line_no, raw in enumerate(fp, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise Lab00Error(f"invalid JSONL in {path}:{line_no}: {exc}") from None
                if not isinstance(record, dict):
                    raise Lab00Error(f"invalid JSONL record in {path}:{line_no}: expected object")
                records.append(record)
    except OSError as exc:
        raise Lab00Error(f"cannot read {label} file {path}: {exc}") from None
    return records



def _read_json_object(path: Path, label: str) -> dict:
    if not path.exists():
        raise Lab00Error(f"{label} file not found: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Lab00Error(f"invalid JSON in {label}: {path}: {exc}") from None
    except OSError as exc:
        raise Lab00Error(f"cannot read {label} file {path}: {exc}") from None

    if not isinstance(payload, dict):
        raise Lab00Error(f"invalid {label}: expected JSON object")
    return payload



def _validate_inputs_non_empirical(
    packets: Sequence[dict],
    responses: Sequence[dict],
    annotations: Sequence[dict],
    summary: dict,
) -> None:
    if summary.get("non_empirical") is not True:
        raise Lab00Error("summary non_empirical must be true")

    for response in responses:
        if response.get("non_empirical") is not True:
            raise Lab00Error(
                f"response {response.get('response_id', 'unknown')} is empirical; lab00 is non-evidence only"
            )

    for annotation in annotations:
        if annotation.get("non_empirical") is not True:
            raise Lab00Error(
                f"annotation {annotation.get('annotation_id', 'unknown')} is empirical; lab00 is non-evidence only"
            )

    for packet in packets:
        packet_id = packet.get("packet_id")
        non_empirical = packet.get("non_empirical")
        if packet_id is None:
            continue
        if non_empirical is not None and non_empirical is not True:
            raise Lab00Error(f"packet {packet_id} is empirical; lab00 is non-evidence only")



def _render_html(
    packets: list[dict],
    responses: list[dict],
    annotations: list[dict],
    summary: dict,
    packets_path: Path,
    responses_path: Path,
    annotations_path: Path,
    summary_path: Path,
) -> str:
    counts = summary.get("counts", {})
    per_arm_means = summary.get("per_arm_means", {})
    paired_deltas = summary.get("paired_deltas", {})
    metric_directions = _metric_directions(summary.get("metric_directions", {}), dimensions=STANDARD_DIMENSIONS)
    normalized_pair_deltas = _normalized_paired_deltas(
        paired_deltas,
        metric_directions,
    )
    dimensions = [
        dim
        for dim in STANDARD_DIMENSIONS
        if dim in summary.get("dimensions", STANDARD_DIMENSIONS)
    ]
    if not dimensions:
        dimensions = list(STANDARD_DIMENSIONS)

    packets_by_id = {str(packet.get("packet_id", "")): packet for packet in packets}
    packet_rows = []
    for packet_id in sorted(packets_by_id):
        packet = packets_by_id[packet_id]
        blind_order = packet.get("blind_order", [])
        source = packet.get("source", {})
        source_bits = []
        for field in ("domain", "problem", "initial_state", "desired_improvement", "worsening_consequence"):
            value = source.get(field)
            if value is None:
                continue
            source_bits.append(f"{field}: {value}")
        source_text = " | ".join(str(bit) for bit in source_bits)
        constraints = source.get("constraints", [])
        if isinstance(constraints, list):
            constraints_text = ", ".join(str(item) for item in constraints)
        else:
            constraints_text = ""
        packet_rows.append(
            {
                "packet_id": packet_id,
                "case_id": str(packet.get("case_id", "")),
                "pair_id": str(packet.get("pair_id", "")),
                "blind_order": ", ".join(str(item) for item in blind_order)
                if isinstance(blind_order, list)
                else "",
                "arms_by_blind": packet.get("arms_by_blind", {}),
                "constraints": constraints_text,
                "source": source_text,
            }
        )

    response_rows = []
    for response in sorted(responses, key=lambda item: str(item.get("response_id", ""))):
        packet_id = str(response.get("packet_id", ""))
        blind = str(response.get("blinded_arm", ""))
        model = response.get("model", {})
        model_name = " / ".join(
            str(value)
            for value in (
                model.get("name", ""),
                model.get("family", ""),
                model.get("revision", ""),
            )
            if value
        )
        response_rows.append(
            {
                "response_id": str(response.get("response_id", "")),
                "packet_id": packet_id,
                "blinded_arm": blind,
                "arm": str(
                    packets_by_id.get(packet_id, {}).get("arms_by_blind", {}).get(blind, "")
                ),
                "model": model_name,
                "generated_at": str(response.get("generated_at", "")),
                "non_empirical": bool(response.get("non_empirical")),
                "response_text": str(response.get("response_text", "")),
            }
        )

    annotation_rows = []
    for annotation in sorted(
        annotations,
        key=lambda item: (str(item.get("annotation_id", "")), str(item.get("response_id", ""))),
    ):
        scores = _coerce_annotation_scores(annotation.get("scores", {}))
        annotation_rows.append(
            {
                "annotation_id": str(annotation.get("annotation_id", "")),
                "response_id": str(annotation.get("response_id", "")),
                "packet_id": str(annotation.get("packet_id", "")),
                "blinded_arm": str(annotation.get("blinded_arm", "")),
                "rater_id": str(annotation.get("rater_id", "")),
                "annotated_at": str(annotation.get("annotated_at", "")),
                "scores": scores,
            }
        )

    lines: list[str] = []
    lines.append("<!DOCTYPE html><html><head><meta charset='utf-8'>")
    lines.append("<title>Latent TRIZ Lab 00 Report</title>")
    lines.append(
        "<style>"
        "body{font-family:Inter,system-ui,Segoe UI,Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:1.25rem;}"
        "main{max-width:1200px;margin:0 auto;display:grid;gap:1rem;}"
        "section{background:#111827;border:1px solid #334155;padding:0.9rem 1rem;border-radius:0.65rem;}"
        "h1{margin-top:0;font-size:1.5rem;}"
        "h2{margin-top:0.2rem;}"
        ".banner{background:#7f1d1d;border-left:0.5rem solid #fecaca;padding:0.75rem 0.9rem;border-radius:0.4rem;}"
        "table{width:100%;border-collapse:collapse;overflow:auto;display:block;}"
        "th,td{border:1px solid #334155;padding:0.5rem;font-size:0.85rem;vertical-align:top;}"
        "th{background:#1e293b;text-align:left;}"
        ".mono{font-family:Menlo,Consolas,monospace;font-size:0.8rem;white-space:pre-wrap;word-break:break-word;}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:0.9rem;}"
        "@media (max-width: 900px){body{padding:0.6rem;} th,td{font-size:0.74rem;}}"
        "</style></head><body>"
    )

    lines.append("<main>")
    lines.append("<header class='banner'>")
    lines.append(
        "<h1>Latent TRIZ Lab 00 — Non-Evidence Stage-1 Smoke Report</h1><p>"
        "This report renders synthetic process artifacts only and does not infer empirical support.</p>"
        "<p><strong>Boundary:</strong> non_empirical gate must remain true for packets, responses, annotations, and summary.</p>"
        "<p><strong>Unblinded administrative audit view — never use this page for annotation.</strong></p>"
        "<p><strong>Infrastructure-only. Not attached to any scientific claim.</strong></p>"
        "</header>"
    )

    lines.append("<section><h2>Artifact fingerprints</h2><div class='grid'>")
    lines.append(
        f"<div><strong>Packets</strong><br><span class='mono'>{escape(summary.get('provenance', {}).get('packets_fingerprint', _fingerprint_file(packets_path)))}</span></div>"
    )
    lines.append(
        f"<div><strong>Responses</strong><br><span class='mono'>{escape(summary.get('provenance', {}).get('responses_fingerprint', _fingerprint_file(responses_path)))}</span></div>"
    )
    lines.append(
        f"<div><strong>Annotations</strong><br><span class='mono'>{escape(summary.get('provenance', {}).get('annotations_fingerprint', _fingerprint_file(annotations_path)))}</span></div>"
    )
    lines.append(
        f"<div><strong>Summary</strong><br><span class='mono'>{escape(_fingerprint_file(summary_path))}</span></div>"
    )
    lines.append("</div></section>")

    lines.append("<section><h2>Cases and blind allocations</h2>")
    lines.append("<table><thead><tr><th>packet_id</th><th>case_id</th><th>pair_id</th><th>blind order</th><th>arms by blind</th><th>constraints</th><th>source summary</th></tr></thead><tbody>")
    for row in packet_rows:
        arms = row.get("arms_by_blind", {})
        arms_text = ", ".join(f"{escape(str(k))}:{escape(str(v))}" for k, v in sorted(arms.items()))
        lines.append(
            "<tr>"
            f"<td>{escape(row['packet_id'])}</td>"
            f"<td>{escape(row['case_id'])}</td>"
            f"<td>{escape(row['pair_id'])}</td>"
            f"<td>{escape(row['blind_order'])}</td>"
            f"<td>{arms_text}</td>"
            f"<td>{escape(row['constraints'])}</td>"
            f"<td><span class='mono'>{escape(row['source'])}</span></td>"
            "</tr>"
        )
    lines.append("</tbody></table></section>")

    lines.append("<section><h2>Responses</h2>")
    lines.append("<table><thead><tr><th>response_id</th><th>packet_id</th><th>blinded_arm</th><th>arm</th><th>model</th><th>generated_at</th><th>non_empirical</th><th>response_text</th></tr></thead><tbody>")
    for row in response_rows:
        lines.append(
            "<tr>"
            f"<td>{escape(row['response_id'])}</td>"
            f"<td>{escape(row['packet_id'])}</td>"
            f"<td>{escape(row['blinded_arm'])}</td>"
            f"<td>{escape(row['arm'])}</td>"
            f"<td>{escape(row['model'])}</td>"
            f"<td>{escape(row['generated_at'])}</td>"
            f"<td>{'true' if row['non_empirical'] else 'false'}</td>"
            f"<td><span class='mono'>{escape(row['response_text'])}</span></td>"
            "</tr>"
        )
    lines.append("</tbody></table></section>")

    lines.append("<section><h2>Annotations (6 dimensions)</h2>")
    lines.append("<table><thead><tr><th>annotation_id</th><th>response_id</th><th>packet_id</th><th>blinded_arm</th><th>rater</th><th>annotated_at</th><th>scores</th></tr></thead><tbody>")
    for row in annotation_rows:
        bars = [
            f"{escape(dim)}: {row['scores'].get(dim, 0)} {render_score_bar(row['scores'].get(dim, 0))}"
            for dim in dimensions
        ]
        lines.append(
            "<tr>"
            f"<td>{escape(row['annotation_id'])}</td>"
            f"<td>{escape(row['response_id'])}</td>"
            f"<td>{escape(row['packet_id'])}</td>"
            f"<td>{escape(row['blinded_arm'])}</td>"
            f"<td>{escape(row['rater_id'])}</td>"
            f"<td>{escape(row['annotated_at'])}</td>"
            f"<td><span class='mono'>{escape(' | '.join(bars))}</span></td>"
            "</tr>"
        )
    lines.append("</tbody></table></section>")

    lines.append("<section><h2>Summary</h2><div class='grid'>")
    lines.append(f"<div><strong>counts</strong><span class='mono'><br>{escape(json.dumps(counts, sort_keys=True))}</span></div>")
    lines.append(f"<div><strong>per-arm means</strong><span class='mono'><br>{escape(json.dumps(per_arm_means, sort_keys=True))}</span></div>")
    lines.append(f"<div><strong>paired deltas (raw treatment-control)</strong><span class='mono'><br>{escape(json.dumps(paired_deltas, sort_keys=True))}</span></div>")
    lines.append(f"<div><strong>paired deltas (normalized treatment-control)</strong><span class='mono'><br>{escape(json.dumps(normalized_pair_deltas, sort_keys=True))}</span></div>")
    lines.append(f"<div><strong>metric directions</strong><span class='mono'><br>{escape(json.dumps(metric_directions, sort_keys=True))}</span></div>")
    lines.append("</div></section>")

    # inline score bars for every dimension on summary means
    lines.append("<section><h2>Per-arm score bars (0-4)</h2>")
    lines.append("<div class='grid'>")
    for arm in sorted(per_arm_means):
        lines.append(f"<div><strong>{escape(str(arm))}</strong>")
        for dim in dimensions:
            value = float(per_arm_means.get(arm, {}).get(dim, 0.0))
            direction = metric_directions.get(dim, "maximize")
            direction_label = "↑" if direction == "maximize" else "↓"
            lines.append(
                f"<div>{escape(dim)} ({direction_label}): {value:.2f} {render_score_bar(value)}</div>"
            )
        lines.append("</div>")
    lines.append("</div></section>")

    lines.append("</main></body></html>")
    return "\n".join(lines)


def _coerce_annotation_scores(raw: object) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {dim: 0.0 for dim in STANDARD_DIMENSIONS}
    values: dict[str, float] = {}
    for dim in STANDARD_DIMENSIONS:
        value = raw.get(dim, 0)
        try:
            values[dim] = float(value)
        except (TypeError, ValueError):
            values[dim] = 0.0
    return values


def _trimmed_summary(summary: dict) -> dict:
    trimmed = dict(summary)
    for field in ("metric_directions", "paired_deltas_normalized"):
        trimmed.pop(field, None)
    return trimmed


def _metric_directions(raw_directions: object, dimensions: Sequence[str]) -> dict[str, str]:
    directions: dict[str, str] = {
        dim: ("minimize" if dim == "terminology_only" else "maximize")
        for dim in dimensions
    }
    if not isinstance(raw_directions, dict):
        return directions

    for dim in dimensions:
        direction = raw_directions.get(dim)
        if direction in {"maximize", "minimize"}:
            directions[dim] = direction
    return directions


def _normalized_paired_deltas(
    paired_deltas: object,
    metric_directions: dict[str, str],
) -> dict[str, dict[str, dict[str, float]]]:
    normalized: dict[str, dict[str, dict[str, float]]] = {}
    if not isinstance(paired_deltas, dict):
        return normalized

    for pair_id, pair_values in paired_deltas.items():
        if not isinstance(pair_values, dict):
            continue
        normalized_pair: dict[str, dict[str, float]] = {}
        for relation, values in pair_values.items():
            if not isinstance(values, dict):
                continue
            normalized_values: dict[str, float] = {}
            for dim in values:
                raw_value = _coerce_float(values.get(dim, 0.0))
                direction = metric_directions.get(dim, "maximize")
                normalized_values[dim] = -raw_value if direction == "minimize" else raw_value
            for dim in metric_directions:
                normalized_values.setdefault(dim, 0.0)
            normalized_pair[str(relation)] = normalized_values
        if normalized_pair:
            normalized[str(pair_id)] = normalized_pair
    return normalized


def _coerce_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def render_score_bar(value: object) -> str:
    value_num = 0.0
    try:
        value_num = float(value)
    except (TypeError, ValueError):
        value_num = 0.0
    if value_num < 0:
        value_num = 0.0
    if value_num > 4:
        value_num = 4.0
    block_count = int(round(value_num))
    return f"[{ '█' * block_count}{'·' * (4 - block_count)}]"


def _fingerprint_file(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
