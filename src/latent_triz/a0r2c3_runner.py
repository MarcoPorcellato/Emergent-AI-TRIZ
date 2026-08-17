"""One-attempt, no-model C3 analysis-only recovery runner."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from . import a0r2_runner as base_runner
from .a0r2_report import generate_a0r2_report, verify_a0r2_publication
from .a0r2c3_analysis import analyze_a0r2c3
from .a0r2c3_authorization import AUTHORIZATION_PATH, verify_a0r2c3_authorization, verify_a0r2c3_contract


RUN_ID = "a0r2c3-analysis-only-v1.0.0-f8027fd0-r1"
SOURCE_RUN_ID = "a0r2c2-v1.0.0-f8027fd0-r1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the one-attempt A0-R2-C3 analysis-only recovery")
    parser.add_argument("--root", default=".")
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--authorization-receipt", default=str(AUTHORIZATION_PATH))
    parser.add_argument("--stage", choices=("all", "verify"), default="all")
    return parser


def _source_activation_dir(root: Path) -> Path:
    path = root / "artifacts" / "a0r2" / SOURCE_RUN_ID
    if not path.is_dir():
        raise base_runner.A0R2RunnerError("C2 activation artifact directory is missing")
    return path


def _failure_payload(created_at: str, exc: Exception) -> dict[str, Any]:
    return {
        "artifact_class": "a0r2-run-failure",
        "status": "failed",
        "created_at": created_at,
        "scientific_status": "exploratory",
        "empirical": True,
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "protocol_id": "a0r2-independent-model-v1.0.0",
        "model": dict(base_runner._MODEL),
        "failure": {"stage": "data", "failure_kind": type(exc).__name__, "failure_digest": hashlib.sha256(str(exc).encode("utf-8")).hexdigest()},
        "access": {"model_loaded": False, "model_output_accessed": "not_accessed", "sealed_targets_accessed": "possibly_accessed", "claim_promotion": False},
        "reports": ["report.md"],
    }


def _run_all(root: Path, args: argparse.Namespace) -> None:
    verify_a0r2c3_authorization(root, args.authorization_receipt)
    source_dir = _source_activation_dir(root)
    package_dir = root / "results" / "a0r2" / RUN_ID
    if package_dir.exists():
        raise base_runner.A0R2RunnerError("C3 package already exists")
    package_dir.mkdir(parents=True)
    try:
        base_runner._sync_activation_package(source_dir, package_dir)
        analyze_a0r2c3(
            protocol_path=root / base_runner.PROTOCOL_PATH,
            activation_receipt_path=package_dir / "activation-receipt.json",
            activation_index_path=package_dir / "representations-index.jsonl",
            dense_path=source_dir / "activations.json",
            targets_path=base_runner._discover_targets_path(root),
            output_path=package_dir / "statistical-result.json",
            shortcut_path=root / "results" / "a0r1" / "preoutput" / "shortcuts.json",
        )
        generate_a0r2_report(
            package_dir=package_dir.relative_to(root),
            external_dense_dir=source_dir.relative_to(root),
            created_at=args.created_at,
            allow_external_dense_reuse=True,
        )
        verify_a0r2_publication(
            package_dir=package_dir.relative_to(root),
            external_dense_dir=source_dir.relative_to(root),
            allow_external_dense_reuse=True,
        )
    except Exception as exc:
        for name in ("activation-receipt.json", "representations-index.jsonl"):
            (package_dir / name).unlink(missing_ok=True)
        base_runner._write_failure(root, RUN_ID, _failure_payload(args.created_at, exc))
        generate_a0r2_report(
            package_dir=package_dir.relative_to(root),
            external_dense_dir=source_dir.relative_to(root),
            created_at=args.created_at,
            allow_external_dense_reuse=True,
        )
        raise


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.root).resolve()
    if args.run_id != RUN_ID:
        raise base_runner.A0R2RunnerError(f"C3 run-id must be {RUN_ID}")
    verify_a0r2c3_contract(root)
    if args.stage == "verify":
        source_dir = _source_activation_dir(root)
        verify_a0r2_publication(
            package_dir=(Path("results") / "a0r2" / RUN_ID),
            external_dense_dir=source_dir.relative_to(root),
            allow_external_dense_reuse=True,
        )
        return 0
    _run_all(root, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
