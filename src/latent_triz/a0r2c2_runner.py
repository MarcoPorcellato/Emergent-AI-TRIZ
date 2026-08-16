"""Single-attempt C2 runner for the preregistered Llama shape correction."""

from __future__ import annotations

import sys
from pathlib import Path

from . import a0r2_runner as base_runner
from .a0r2_activations import run_a0r2_activations
from .a0r2c2_adapter import SmolLM2C2ShapeAdapter
from .a0r2c2_authorization import AUTHORIZATION_PATH, verify_a0r2c2_authorization, verify_a0r2c2_contract


RUN_ID = "a0r2c2-v1.0.0-f8027fd0-r1"


def _corrected_activations(**kwargs):
    return run_a0r2_activations(**kwargs, adapter_factory=SmolLM2C2ShapeAdapter)


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    parsed = base_runner._parser().parse_args(arguments)
    if parsed.run_id != RUN_ID:
        raise base_runner.A0R2RunnerError(f"C2 run-id must be {RUN_ID}")
    if parsed.stage not in {"all", "verify"}:
        raise base_runner.A0R2RunnerError("C2 runner permits only all or verify")
    root = Path(parsed.root).resolve()
    verify_a0r2c2_contract(root)
    if parsed.stage == "all" and "--authorization-receipt" not in arguments:
        arguments.extend(("--authorization-receipt", str(AUTHORIZATION_PATH)))

    original_activation = base_runner.run_a0r2_activations
    original_authorization = base_runner.verify_a0r2_sealed_execution_authorization
    try:
        base_runner.run_a0r2_activations = _corrected_activations
        base_runner.verify_a0r2_sealed_execution_authorization = verify_a0r2c2_authorization
        return base_runner.main(arguments)
    finally:
        base_runner.run_a0r2_activations = original_activation
        base_runner.verify_a0r2_sealed_execution_authorization = original_authorization


if __name__ == "__main__":
    raise SystemExit(main())
