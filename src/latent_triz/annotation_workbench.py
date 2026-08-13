"""Dependency-free, evaluator-safe dataset annotation workbench."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from .validator import validate

MAX_REQUEST_BYTES = 16 * 1024
EXPOSED_CASE_FIELDS = (
    "case_id", "domain", "problem", "constraints", "initial_state",
    "desired_improvement", "worsening_consequence", "transformation", "resulting_state",
)


class AnnotationWorkbenchError(RuntimeError):
    """Raised when the workbench cannot fail closed."""


def stable_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AnnotationWorkbenchError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(record, dict):
                raise AnnotationWorkbenchError(f"{path}:{line_number}: record must be an object")
            records.append(record)
    if not records:
        raise AnnotationWorkbenchError(f"{path}: no records")
    return records


def load_guide(path: str | Path) -> dict[str, Any]:
    try:
        guide = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnnotationWorkbenchError(f"cannot read annotation guide {path}: {exc}") from exc
    labels = guide.get("labels") if isinstance(guide, dict) else None
    if not isinstance(labels, list) or len(labels) < 2:
        raise AnnotationWorkbenchError("annotation guide requires at least two labels")
    seen: set[str] = set()
    for item in labels:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise AnnotationWorkbenchError("each guide label requires a non-empty id")
        if item["id"] in seen:
            raise AnnotationWorkbenchError(f"duplicate guide label: {item['id']}")
        seen.add(item["id"])
        if not isinstance(item.get("definition"), str) or not item["definition"]:
            raise AnnotationWorkbenchError(f"guide label {item['id']} requires a definition")
    abstention = guide.get("abstention")
    if not isinstance(abstention, dict) or abstention.get("id") != "abstain":
        raise AnnotationWorkbenchError("annotation guide requires the abstain audit state")
    if not isinstance(guide.get("revision"), str) or not guide["revision"]:
        raise AnnotationWorkbenchError("annotation guide requires revision")
    return guide


def sanitize_cases(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, record in enumerate(records, start=1):
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise AnnotationWorkbenchError(f"case {index}: missing case_id")
        if case_id in seen:
            raise AnnotationWorkbenchError(f"duplicate case_id: {case_id}")
        seen.add(case_id)
        item = {field: record[field] for field in EXPOSED_CASE_FIELDS if field in record}
        missing = [field for field in EXPOSED_CASE_FIELDS if field not in item]
        if missing:
            raise AnnotationWorkbenchError(f"case {case_id}: missing evaluator fields: {', '.join(missing)}")
        sanitized.append(item)
    return sanitized


def order_cases_for_rater(
    cases: Sequence[Mapping[str, Any]], rater_id: str, guide_sha256: str
) -> list[dict[str, Any]]:
    """Return a stable rater-specific order without using embedded labels."""
    return [
        dict(case)
        for case in sorted(
            cases,
            key=lambda case: hashlib.sha256(
                f"{rater_id}|{guide_sha256}|{case['case_id']}".encode("utf-8")
            ).digest(),
        )
    ]


class AnnotationStore:
    def __init__(self, output_path: str | Path, schema_path: str | Path) -> None:
        self.output_path = Path(output_path)
        try:
            self.schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AnnotationWorkbenchError(f"cannot read annotation schema {schema_path}: {exc}") from exc
        self._lock = threading.Lock()
        self._pairs: set[tuple[str, str]] = set()
        if self.output_path.exists():
            for record in load_jsonl(self.output_path):
                issues = validate(record, self.schema)
                if issues:
                    details = "; ".join(f"{issue.path}: {issue.message}" for issue in issues)
                    raise AnnotationWorkbenchError(f"existing annotation does not match schema: {details}")
                pair = (str(record.get("case_id", "")), str(record.get("rater_id", "")))
                if pair in self._pairs:
                    raise AnnotationWorkbenchError(f"duplicate existing annotation pair: {pair[0]}/{pair[1]}")
                self._pairs.add(pair)

    def contains(self, case_id: str, rater_id: str) -> bool:
        return (case_id, rater_id) in self._pairs

    def append(self, record: dict[str, Any]) -> None:
        issues = validate(record, self.schema)
        if issues:
            details = "; ".join(f"{issue.path}: {issue.message}" for issue in issues)
            raise AnnotationWorkbenchError(f"annotation does not match schema: {details}")
        pair = (record["case_id"], record["rater_id"])
        payload = stable_json_dumps(record) + "\n"
        with self._lock:
            if pair in self._pairs:
                raise AnnotationWorkbenchError(f"rater {pair[1]} already annotated case {pair[0]}")
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(self.output_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            try:
                encoded = payload.encode("utf-8")
                offset = 0
                while offset < len(encoded):
                    written = os.write(descriptor, encoded[offset:])
                    if written < 1:
                        raise AnnotationWorkbenchError("annotation append made no progress")
                    offset += written
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            self._pairs.add(pair)


def build_annotation_record(
    payload: Mapping[str, Any], *, rater_id: str, case_ids: set[str], labels: set[str],
    guide_revision: str, guide_sha256: str,
) -> dict[str, Any]:
    case_id, label = payload.get("case_id"), payload.get("label")
    confidence, rationale = payload.get("confidence"), payload.get("rationale")
    if case_id not in case_ids:
        raise AnnotationWorkbenchError("unknown case_id")
    if label not in labels:
        raise AnnotationWorkbenchError("label is not permitted by the annotation guide")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise AnnotationWorkbenchError("confidence must be a number in [0,1]")
    if not isinstance(rationale, str) or not rationale.strip():
        raise AnnotationWorkbenchError("rationale is required")
    annotated_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "annotation_id": f"ann_{secrets.token_hex(12)}", "case_id": case_id,
        "rater_id": rater_id, "label": label, "confidence": float(confidence),
        "rationale": rationale.strip(), "non_empirical": False, "annotated_at": annotated_at,
        "guide_revision": guide_revision, "guide_sha256": guide_sha256,
    }


def render_workbench_html(session: Mapping[str, Any], csrf_token: str) -> str:
    data = json.dumps(session, ensure_ascii=False).replace("</", "<\\/")
    token = json.dumps(csrf_token)
    return f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\"><title>Latent TRIZ annotation workbench</title>
<style>body{{font:16px system-ui;max-width:880px;margin:2rem auto;padding:0 1rem;color:#18202a;background:#f5f7fa}}main{{background:white;padding:1.5rem;border-radius:12px}}label{{display:block;font-weight:650;margin:.8rem 0}}textarea{{width:100%;min-height:7rem}}button{{padding:.7rem 1rem;margin:.4rem}}.warning{{border-left:4px solid #a65d03;padding:.8rem;background:#fff8e8}}</style></head>
<body><main><h1>Blinded dataset annotation</h1><p class=\"warning\">Human judgment metadata only. Embedded labels, provenance, split assignments, lexical controls, related-case identifiers, allocations, and experimental results are hidden. An annotation is not evidence for the Latent TRIZ hypothesis.</p><p id=\"progress\"></p><section id=\"case\"></section><form id=\"form\"><div id=\"labels\"></div><label>Confidence (0 to 1)<input id=\"confidence\" type=\"number\" min=\"0\" max=\"1\" step=\"0.05\" value=\"0.5\" required></label><label>Rationale<textarea id=\"rationale\" required></textarea></label><button type=\"submit\">Save and continue</button><button type=\"button\" id=\"abstain\">Record abstention</button></form><pre id=\"status\"></pre>
<script>const session={data},csrf={token};let i=0;const byId=id=>document.getElementById(id),esc=s=>String(s).replace(/[&<>\"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[c]));
function show(){{if(i>=session.cases.length){{byId('case').innerHTML='<h2>Queue complete</h2>';byId('form').hidden=true;return}}const c=session.cases[i];byId('progress').textContent=`Case ${{i+1}} of ${{session.cases.length}} · rater ${{session.rater_id}}`;byId('case').innerHTML=`<h2>${{esc(c.case_id)}}</h2><p><b>Domain:</b> ${{esc(c.domain)}}</p><p><b>Problem:</b> ${{esc(c.problem)}}</p><p><b>Constraints:</b> ${{c.constraints.map(esc).join(', ')}}</p><p><b>Initial:</b> ${{esc(c.initial_state)}}</p><p><b>Desired improvement:</b> ${{esc(c.desired_improvement)}}</p><p><b>Worsening consequence:</b> ${{esc(c.worsening_consequence)}}</p><p><b>Transformation:</b> ${{esc(c.transformation)}}</p><p><b>Result:</b> ${{esc(c.resulting_state)}}</p>`;byId('labels').innerHTML=session.guide.labels.map((l,n)=>`<label><input type=\"radio\" name=\"label\" value=\"${{esc(l.id)}}\" ${{n===0?'required':''}}> <b>${{esc(l.name||l.id)}}</b> — ${{esc(l.definition)}}</label>`).join('')}}
async function save(payload){{const response=await fetch('/api/annotations',{{method:'POST',headers:{{'Content-Type':'application/json','X-CSRF-Token':csrf}},body:JSON.stringify(payload)}}),result=await response.json();byId('status').textContent=result.message||result.error;if(response.ok){{i++;byId('rationale').value='';show()}}}}
byId('abstain').onclick=()=>save({{case_id:session.cases[i].case_id,label:session.guide.abstention.id,confidence:0,rationale:'Rater abstained: neither operator fit confidently.'}});byId('form').onsubmit=e=>{{e.preventDefault();const selected=document.querySelector('input[name=label]:checked');if(selected)save({{case_id:session.cases[i].case_id,label:selected.value,confidence:Number(byId('confidence').value),rationale:byId('rationale').value}})}};show()</script></main></body></html>"""


def create_server(
    *, cases_path: str | Path, guide_path: str | Path, output_path: str | Path,
    schema_path: str | Path, rater_id: str, host: str = "127.0.0.1", port: int = 8765,
) -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "::1"}:
        raise AnnotationWorkbenchError("workbench must bind to a loopback address")
    if not rater_id or any(character.isspace() for character in rater_id):
        raise AnnotationWorkbenchError("rater_id must be non-empty and contain no whitespace")
    cases, guide = sanitize_cases(load_jsonl(cases_path)), load_guide(guide_path)
    guide_sha256 = hashlib.sha256(Path(guide_path).read_bytes()).hexdigest()
    cases = order_cases_for_rater(cases, rater_id, guide_sha256)
    store, csrf_token = AnnotationStore(output_path, schema_path), secrets.token_urlsafe(32)
    cases = [case for case in cases if not store.contains(case["case_id"], rater_id)]
    case_ids = {case["case_id"] for case in cases}
    allowed_labels = {item["id"] for item in guide["labels"]} | {guide["abstention"]["id"]}
    session = {"rater_id": rater_id, "cases": cases, "guide": guide, "guide_sha256": guide_sha256, "evidence_eligible": False}
    html = render_workbench_html(session, csrf_token).encode()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
            self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store"); self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
            self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("Referrer-Policy", "no-referrer"); self.end_headers(); self.wfile.write(body)

        def _json(self, status: HTTPStatus, payload: Mapping[str, Any]) -> None:
            self._send(status, "application/json; charset=utf-8", stable_json_dumps(payload).encode())

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/": self._send(HTTPStatus.OK, "text/html; charset=utf-8", html)
            elif path == "/api/session": self._json(HTTPStatus.OK, session)
            else: self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/api/annotations": self._json(HTTPStatus.NOT_FOUND, {"error": "not found"}); return
            if self.headers.get("X-CSRF-Token") != csrf_token: self._json(HTTPStatus.FORBIDDEN, {"error": "invalid CSRF token"}); return
            if self.headers.get_content_type() != "application/json": self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "application/json required"}); return
            try: length = int(self.headers.get("Content-Length", "0"))
            except ValueError: length = 0
            if length < 1 or length > MAX_REQUEST_BYTES: self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "invalid request size"}); return
            try:
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict): raise AnnotationWorkbenchError("request body must be an object")
                record = build_annotation_record(payload, rater_id=rater_id, case_ids=case_ids, labels=allowed_labels, guide_revision=guide["revision"], guide_sha256=guide_sha256)
                store.append(record)
            except (json.JSONDecodeError, AnnotationWorkbenchError) as exc: self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)}); return
            self._json(HTTPStatus.CREATED, {"message": f"saved {record['annotation_id']}"})

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer((host, port), Handler); server.daemon_threads = True; return server


def serve_annotation_workbench(*, open_browser: bool = False, **kwargs: Any) -> None:
    server = create_server(**kwargs); host, port = server.server_address[:2]; url = f"http://{host}:{port}/"
    print(f"annotation workbench: {url}"); print(f"annotations: {kwargs['output_path']}")
    if open_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
