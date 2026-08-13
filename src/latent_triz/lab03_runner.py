from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .lab03 import build_lab03_report
from .lab03_baselines import run_behavioral_baselines


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def run_lab03_bundle(
    *,
    cases_path: str | Path,
    snapshot_path: str | Path,
    config_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline_path = output_dir / "baseline_result.json"
    report_path = output_dir / "report.html"
    summary_path = output_dir / "summary.json"

    baseline = run_behavioral_baselines(cases_path, snapshot_path, config_path)
    _write_json(baseline_path, baseline)

    summary = build_lab03_report(
        baseline_result=baseline_path,
        output_html=report_path,
        output_summary=summary_path,
    )

    return {
        "status": summary["status"],
        "summary": str(summary_path),
        "report": str(report_path),
        "baseline": str(baseline_path),
        "empirical": summary["empirical"],
        "evidence_eligible": summary["evidence_eligible"],
        "claim_ids": summary["claim_ids"],
        "gates": summary["gates"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic Lab 03 behavioral baselines")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_lab03_bundle(
        cases_path=args.cases,
        snapshot_path=args.snapshot,
        config_path=args.config,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
