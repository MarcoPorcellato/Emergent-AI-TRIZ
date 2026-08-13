from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from . import lab01
from . import lab01_acquisition
from .lab01_transformers import GPTNeoXTransformersAdapter

TOLERANCE_BY_BACKEND: dict[str, dict[str, dict[str, float]]] = {
    "torch": {
        "float32": {"rtol": 2e-5, "atol": 1e-6},
        "float64": {"rtol": 1e-8, "atol": 1e-8},
        "bfloat16": {"rtol": 0.01, "atol": 0.01},
        "float16": {"rtol": 0.01, "atol": 0.01},
        "int": {"rtol": 0.0, "atol": 0.0},
        "bool": {"rtol": 0.0, "atol": 0.0},
        "unknown": {"rtol": 1e-4, "atol": 1e-4},
    },
    "numpy": {
        "float32": {"rtol": 1e-5, "atol": 1e-6},
    },
}

# Tensor comparison reports device backends (for example ``cpu``), while the
# public run contract reports the library backend (``torch``). Bind both to the
# same frozen tolerance table so the executed policy and published policy agree.
COMPARISON_TOLERANCE_BY_DEVICE = {
    "default": TOLERANCE_BY_BACKEND["torch"],
    "cpu": TOLERANCE_BY_BACKEND["torch"],
    "cuda": TOLERANCE_BY_BACKEND["torch"],
    "mps": TOLERANCE_BY_BACKEND["torch"],
    "pytorch": TOLERANCE_BY_BACKEND["torch"],
    "numpy": TOLERANCE_BY_BACKEND["numpy"],
}


@dataclass(frozen=True)
class RunArtifacts:
    model_receipt: Path
    environment: Path
    run_record: Path
    prompt_record: Path
    token_record: Path
    layer_summary: Path
    topk_logits: Path
    parity_report: Path
    report_html: Path

    @property
    def tokens(self) -> Path:
        return self.token_record


def _classification_block() -> dict[str, Any]:
    return {
        "artifact_class": "model-instrumentation",
        "empirical": True,
        "evidence_eligible": False,
        "claim_ids": [],
    }


def _package_versions() -> dict[str, str]:
    packages = ("torch", "transformers", "safetensors", "huggingface-hub")
    resolved: dict[str, str] = {}
    for package in packages:
        try:
            resolved[package] = version(package)
        except PackageNotFoundError:
            resolved[package] = "not-installed"
    return resolved


def _read_prompt_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"prompts file not found: {path}")
    records: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL in {path}:{line_no}: {exc}") from None
        if not isinstance(record, dict):
            raise ValueError(f"invalid prompt record in {path}:{line_no}")
        records.append(record)
    if not records:
        raise ValueError(f"no prompts in {path}")
    return records


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_dump(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n"


def _write_json(path: Path, payload: Any) -> str:
    text = _stable_dump(payload)
    path.write_text(text, encoding="utf-8")
    return text


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, sort_keys=True, ensure_ascii=False))
            fp.write("\n")


def _extract_topk(payload: Mapping[str, Any], prompt_id: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for key, value in payload.items():
        if not key.endswith("_topk"):
            continue
        if not isinstance(value, Mapping):
            continue
        records.append(
            {
                "prompt_id": prompt_id,
                "layer": key,
                "token_ids": list(value.get("token_ids", [])),
                "token_pieces": list(value.get("token_pieces", [])),
                "values": [float(v) for v in value.get("values", [])],
            }
        )
    return records


def _gate(status: bool, gate_id: str, passing: str, failing: str) -> dict[str, str]:
    return {
        "gate": gate_id,
        "status": "pass" if status else "fail",
        "details": passing if status else failing,
    }


def run_lab01_bundle(
    *,
    model_root: str | Path,
    prompts_jsonl: str | Path,
    output_dir: str | Path,
    repeats: int = 2,
    adapter_factory: Callable[..., Any] = GPTNeoXTransformersAdapter,
    identity_verifier: Callable[[Path], tuple[bool, list[str]]] = lab01_acquisition.verify_expected_snapshot,
    top_k: int = 3,
) -> RunArtifacts:
    if repeats < 1:
        raise ValueError("repeats must be >= 1")

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    prompts = _read_prompt_records(Path(prompts_jsonl).resolve())
    model_root_path = Path(model_root).resolve()

    identity_gate = model_root_path.exists() and lab01_acquisition.LAB01_MODEL_ID == "EleutherAI/pythia-70m-deduped"
    identity_gate = identity_gate and len(lab01_acquisition.LAB01_MODEL_REVISION) == 40

    try:
        receipts = lab01_acquisition.build_runtime_file_receipts(model_root_path)
        runtime_receipts = lab01_acquisition.runtime_receipts_to_payload(receipts)
        expected_match, _identity_errors = identity_verifier(model_root_path)
        identity_gate = identity_gate and bool(runtime_receipts) and expected_match
    except Exception:
        runtime_receipts = []
        identity_gate = False

    try:
        adapter = adapter_factory(
            model_root=model_root_path,
            local_files_only=True,
            device="cpu",
            torch_dtype="float32",
            top_k=top_k,
        )
        offline_gate = True
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"local CPU float32 adapter initialization failed: {exc}") from exc

    tokenization_gate = True
    instrumentation_gate = True
    finite_health_gate = True
    logits_gate = True
    repeat_gate = True

    prompt_rows: list[dict[str, Any]] = []
    token_rows: list[dict[str, Any]] = []
    layer_rows: list[dict[str, Any]] = []
    topk_rows: list[dict[str, Any]] = []

    for item in prompts:
        prompt_id = str(item.get("prompt_id", "unknown"))
        prompt = str(item.get("prompt", ""))
        if "TRIZ" in prompt.upper():
            raise ValueError("TRIZ claim text is not allowed in prompts")

        baseline_payload = adapter.run_prompt(prompt=prompt, instrumented=True)
        topk_rows.extend(_extract_topk(baseline_payload, prompt_id))

        artifact = lab01.run_lab01(
            adapter,
            prompt,
            repeats=repeats,
            tolerance_by_backend=COMPARISON_TOLERANCE_BY_DEVICE,
        )

        tokenization_gate = (
            tokenization_gate
            and len(artifact.token_ids) == len(artifact.token_pieces) == len(artifact.special_flags)
            and all(isinstance(token, int) for token in artifact.token_ids)
        )

        instrumentation_gate = instrumentation_gate and artifact.instrumentation_parity.get("status") == "pass"

        finite_health_gate = finite_health_gate and all(
            meta.finite_ratio >= 1.0 for meta in artifact.canonical_tensors.values()
        )

        repeat_gate = repeat_gate and (repeats == 1 or artifact.repeatability.get("status") == "pass")

        final_gate = artifact.instrumentation_parity.get("status")
        final_status = artifact.instrumentation_parity.get("final_lens_parity_status")
        final_max_abs = float(
            artifact.instrumentation_parity.get("final_lens_parity_max_abs_diff", float("inf"))
        )
        if final_status != "pass":
            logits_gate = False

        prompt_rows.append(
            {
                "prompt_id": prompt_id,
                "prompt": prompt,
                "token_count": len(artifact.token_ids),
                "raw_prompt": artifact.raw_prompt,
                "rendered_prompt": artifact.rendered_prompt,
                "non_triz": True,
                "instrumentation_status": artifact.instrumentation_parity.get("status"),
                "repeatability": artifact.repeatability,
                "final_to_logits_max_abs_diff": final_max_abs,
                "topk_count": len(_extract_topk(baseline_payload, prompt_id)),
            }
        )
        token_rows.append(
            {
                "prompt_id": prompt_id,
                "token_ids": artifact.token_ids,
                "token_pieces": artifact.token_pieces,
                "special_flags": artifact.special_flags,
            }
        )
        for name, meta in artifact.canonical_tensors.items():
            layer_rows.append(
                {
                    "prompt_id": prompt_id,
                    "layer": name,
                    "shape": meta.shape,
                    "dtype": meta.dtype,
                    "backend": meta.backend,
                    "finite_ratio": meta.finite_ratio,
                    "max_abs": meta.max_abs,
                    "mean_abs": meta.mean_abs,
                    "l2": meta.l2,
                    "digest": meta.digest,
                }
            )

    run_record = _classification_block().copy()
    run_record.update(
        {
            "model": lab01_acquisition.LAB01_MODEL_ID,
            "revision": lab01_acquisition.LAB01_MODEL_REVISION,
            "license_id": lab01_acquisition.LAB01_LICENSE_ID,
            "backend": "torch",
            "dtype": "float32",
            "run_state": "instrumentation_verified",
            "structural_artifacts": [{"name": item["name"], "sha256": item["sha256"]} for item in runtime_receipts],
            "byte_identical_structures": [
                "prompt.json",
                "tokens.json",
                "topk_logits.jsonl",
            ],
            "numeric_tolerance_by_backend_dtype": TOLERANCE_BY_BACKEND,
            "notes": "No TRIZ claim; sparse artifacts only.",
        }
    )

    artifacts = RunArtifacts(
        model_receipt=output_dir / "model_receipt.json",
        environment=output_dir / "environment.json",
        run_record=output_dir / "run.json",
        prompt_record=output_dir / "prompt.json",
        token_record=output_dir / "tokens.json",
        layer_summary=output_dir / "layer_summary.jsonl",
        topk_logits=output_dir / "topk_logits.jsonl",
        parity_report=output_dir / "parity_report.json",
        report_html=output_dir / "report.html",
    )

    receipt = _classification_block().copy()
    receipt.update(
        {
            "receipt_type": "load",
            "state_before": "integrity_verified",
            "state_after": "load_verified",
            "model": lab01_acquisition.LAB01_MODEL_ID,
            "revision": lab01_acquisition.LAB01_MODEL_REVISION,
            "license_id": lab01_acquisition.LAB01_LICENSE_ID,
            "receipt_time": datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "source_url": lab01_acquisition.LAB01_SOURCE_URL,
            "terms_url": lab01_acquisition.LAB01_TERMS_URL,
            "runtime_files": runtime_receipts,
            "notes": "Local load receipt, CPU-only, no dense activations stored.",
        }
    )

    environment = _classification_block().copy()
    environment.update(
        {
            "model_id": lab01_acquisition.LAB01_MODEL_ID,
            "local_model": True,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "packages": _package_versions(),
            "generated_at": datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "notes": "No TRIZ claim.",
        }
    )

    # G8 starts fail-closed and is replaced only after every public,
    # non-self-referential artifact has been written and hashed below.
    gates = [
        _gate(identity_gate, "G1", "identity and local-file receipts match", "identity mismatch or receipt missing"),
        _gate(offline_gate, "G2", "offline local adapter initialised with CPU float32", "offline local adapter failed"),
        _gate(tokenization_gate, "G3", "tokenization metadata is coherent", "tokenization metadata is inconsistent"),
        _gate(instrumentation_gate, "G4", "instrumentation invariance passes", "instrumentation variance detected"),
        _gate(finite_health_gate, "G5", "finite tensor summaries are fully healthy", "non-finite tensor summary encountered"),
        _gate(logits_gate, "G6", "final-lens and logits are numerically consistent", "final-lens and logits mismatch"),
        _gate(repeat_gate, "G7", "repeat runs stable", "repeat drift observed"),
        _gate(False, "G8", "artifact hashes computed", "artifact hash computation failed"),
    ]

    # write core artifacts
    _write_json(artifacts.model_receipt, receipt)
    _write_json(artifacts.environment, environment)
    _write_json(artifacts.prompt_record, prompt_rows)
    _write_json(artifacts.token_record, token_rows)
    _write_jsonl(artifacts.layer_summary, layer_rows)
    _write_jsonl(artifacts.topk_logits, topk_rows)
    _write_json(artifacts.run_record, run_record)

    # compute hashes before final parity record
    artifact_hashes = {
        "model_receipt": _sha256_path(artifacts.model_receipt),
        "environment": _sha256_path(artifacts.environment),
        "run": _sha256_path(artifacts.run_record),
        "prompt": _sha256_path(artifacts.prompt_record),
        "tokens": _sha256_path(artifacts.token_record),
        "layer_summary": _sha256_path(artifacts.layer_summary),
        "topk_logits": _sha256_path(artifacts.topk_logits),
    }

    gates[-1] = _gate(
        all(artifact_hashes.values()),
        "G8",
        "all non-self-referential public artifact hashes computed",
        "artifact hash computation failed",
    )

    report_rows = [
        f"<li>{item['gate']}: {item['status']} — {item['details']}</li>" for item in gates
    ]
    report = """<!doctype html>
<html>
  <head><title>Lab 01 Runner Report</title></head>
  <body>
    <h1>Lab 01 Runner Report</h1>
    <p><strong>No TRIZ claim is made in this run.</strong></p>
    <p>Overall: <strong>{overall}</strong></p>
    <ul>{rows}</ul>
  </body>
</html>
""".format(
        overall="pass" if all(item["status"] == "pass" for item in gates) else "fail",
        rows="".join(report_rows),
    )
    artifacts.report_html.write_text(report, encoding="utf-8")
    artifact_hashes["report_html"] = _sha256_path(artifacts.report_html)

    parity = _classification_block().copy()
    parity.update(
        {
            "gates": gates,
            "artifact_hashes": artifact_hashes,
            "status": "pass" if all(item["status"] == "pass" for item in gates) else "fail",
            "timestamp": datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
    )
    _write_json(artifacts.parity_report, parity)

    return artifacts


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Lab01 without dense tensors and write sparse artifacts.")
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--prompts", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--top-k", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    artifacts = run_lab01_bundle(
        model_root=args.model_root,
        prompts_jsonl=args.prompts,
        output_dir=args.output_dir,
        repeats=args.repeats,
        top_k=args.top_k,
    )
    parity = json.loads(artifacts.parity_report.read_text(encoding="utf-8"))
    print(f"lab01: {parity['status']} ({artifacts.report_html})")
    return 0 if parity["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
