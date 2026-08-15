"""Command-line orchestration for the immutable A0 sealed run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .a0_activations import A0ActivationError, run_a0_activations
from .a0_analysis import A0AnalysisError, analyze_a0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the frozen A0 activation and analysis stages")
    parser.add_argument("--root", default=".")
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--stage", choices=("activations", "analysis", "all"), default="all")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.root).resolve()
    protocol_path = root / "experiments/a0-automated-weak-proxy/protocol.json"
    implementation_path = root / "experiments/a0-automated-weak-proxy/implementation.json"
    implementation = json.loads(implementation_path.read_text(encoding="utf-8"))
    run_id = str(implementation["run_id"])
    result_dir = root / "results/a0" / run_id
    dense_dir = root / "artifacts/a0" / run_id

    try:
        if args.stage in {"activations", "all"}:
            artifacts = run_a0_activations(
                protocol_path=protocol_path,
                implementation_path=implementation_path,
                freeze_path=root / "results/a0/calibration/freeze-manifest.json",
                corpus_dir=root / "data/a0",
                model_root=Path(args.model_root),
                dense_output_dir=dense_dir,
                result_output_dir=result_dir,
                created_at=str(implementation["run_timestamp_utc"]),
            )
            print(f"a0-activations: PASS ({artifacts.receipt_path})")
        if args.stage in {"analysis", "all"}:
            result = analyze_a0(
                protocol_path=protocol_path,
                implementation_path=implementation_path,
                shortcut_path=root / "results/a0/calibration/shortcuts.json",
                activation_receipt_path=result_dir / "activation-receipt.json",
                activation_index_path=result_dir / "representations-index.jsonl",
                dense_path=dense_dir / "activations.safetensors",
                targets_path=root / "data/a0/sealed-targets/targets.jsonl",
                output_path=result_dir / "statistical-result.json",
            )
            print(
                "a0-analysis: "
                f"{str(result['status']).upper()} "
                f"(p={result['max_statistic_p']:.6f}, "
                f"margin={result['macro_f1_margin_over_surface']:.6f})"
            )
    except (A0ActivationError, A0AnalysisError, OSError, KeyError, ValueError) as exc:
        print(f"a0-run: FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
