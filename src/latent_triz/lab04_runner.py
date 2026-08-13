from __future__ import annotations

import argparse
import json
from pathlib import Path

from .lab04 import Lab04Error, run_lab04_analysis
from .lab04_probe import build_lab04_report


def _write(path: Path, payload: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    return text


def run_lab04_bundle(
    *,
    cases_path: str | Path,
    representations_path: str | Path,
    config_path: str | Path,
    predecessor_lab01_summary: str | Path,
    predecessor_lab02_summary: str | Path,
    predecessor_lab03_summary: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    result = run_lab04_analysis(
        cases_path=cases_path,
        representations_path=representations_path,
        config_path=config_path,
        predecessor_lab01_summary=predecessor_lab01_summary,
        predecessor_lab02_summary=predecessor_lab02_summary,
        predecessor_lab03_summary=predecessor_lab03_summary,
    )
    from .lab04_probe import run_lab04_probe

    return run_lab04_probe(probe_result=result, output_dir=output_dir)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run dependency-free Lab04 decodability analysis")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--representations", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--predecessor-lab01-summary", required=True)
    parser.add_argument("--predecessor-lab02-summary", required=True)
    parser.add_argument("--predecessor-lab03-summary", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    try:
        output = run_lab04_bundle(
            cases_path=args.cases,
            representations_path=args.representations,
            config_path=args.config,
            predecessor_lab01_summary=args.predecessor_lab01_summary,
            predecessor_lab02_summary=args.predecessor_lab02_summary,
            predecessor_lab03_summary=args.predecessor_lab03_summary,
            output_dir=args.output_dir,
        )
    except Exception as exc:  # pragma: no cover - command path
        if isinstance(exc, Lab04Error):
            print(str(exc))
        else:
            print(f"unexpected error: {exc}")
        return 1

    print(json.dumps(output, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
