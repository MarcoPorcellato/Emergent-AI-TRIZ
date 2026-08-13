from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .dataset_audit import run_dataset_audit
from .dataset_snapshot import build_dataset_snapshot_manifest
from .lab02 import build_lab02_report


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def run_lab02_bundle(
    *,
    plan_path: str | Path,
    cases_path: str | Path,
    annotations_path: str | Path,
    registry_entry_path: str | Path,
    registry_manifest_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Render the current dataset-readiness state without promoting a claim."""
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    audit_path = root / "dataset_audit.json"
    snapshot_path = root / "snapshot_manifest.json"
    report_path = root / "report.html"
    summary_path = root / "summary.json"

    audit = run_dataset_audit(plan_path, cases_path, mode="development")
    snapshot = build_dataset_snapshot_manifest(
        cases_path=cases_path,
        annotations_path=annotations_path,
        plan_path=plan_path,
        registry_entry_path=registry_entry_path,
        registry_manifest_path=registry_manifest_path,
    )
    _write_json(audit_path, audit)
    _write_json(snapshot_path, snapshot)
    summary = build_lab02_report(
        dataset_audit_report=audit_path,
        snapshot_verification_report=snapshot_path,
        output_html=report_path,
        output_summary=summary_path,
    )
    return {
        "status": summary["status"],
        "dataset_ready": summary["status"] == "pass",
        "report": str(report_path),
        "summary": str(summary_path),
        "audit": str(audit_path),
        "snapshot": str(snapshot_path),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render the dependency-free Lab 02 dataset-anatomy report")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--registry-entry", required=True)
    parser.add_argument("--registry-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_lab02_bundle(
        plan_path=args.plan,
        cases_path=args.cases,
        annotations_path=args.annotations,
        registry_entry_path=args.registry_entry,
        registry_manifest_path=args.registry_manifest,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    # A not-ready synthetic dataset is a valid observable Lab 02 result. Runtime
    # and contract errors raise; scientific readiness never changes exit status.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
