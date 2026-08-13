from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .lab01_acquisition import (
    LAB01_MODEL_ID,
    LAB01_LICENSE_ID,
    LAB01_MODEL_REVISION,
    LAB01_SOURCE_URL,
    LAB01_TERMS_URL,
    Lab01AcquisitionError,
    build_runtime_file_receipts,
    ensure_lab01_model,
    runtime_receipts_to_payload,
)


def _stable_dump(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def _repository_relative_path(path: Path) -> str:
    resolved = path.resolve()
    cwd = Path.cwd().resolve()
    try:
        return str(resolved.relative_to(cwd))
    except ValueError:
        return resolved.name


def _receipt_payload(model_root: Path, verified_root: Path) -> dict[str, Any]:
    receipts = runtime_receipts_to_payload(build_runtime_file_receipts(verified_root))
    return {
        "artifact_class": "model-instrumentation",
        "empirical": True,
        "evidence_eligible": False,
        "claim_ids": [],
        "status": "integrity_verified",
        "model": LAB01_MODEL_ID,
        "revision": LAB01_MODEL_REVISION,
        "license_id": LAB01_LICENSE_ID,
        "model_root": _repository_relative_path(model_root),
        "source_url": LAB01_SOURCE_URL,
        "terms_url": LAB01_TERMS_URL,
        "runtime_files": receipts,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Acquire or verify the Lab 01 model snapshot")
    parser.add_argument(
        "--model-root",
        default="artifacts/models/pythia-70m-deduped-e93a9faa",
        help="Model directory to verify or acquire",
    )
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help="Authorize snapshot download when the model root is incomplete",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    model_root = Path(args.model_root)

    try:
        verified_root = ensure_lab01_model(model_root, allow_download=bool(args.allow_download))
        payload = _receipt_payload(model_root, verified_root)
    except Lab01AcquisitionError as exc:
        print(
            _stable_dump(
                {
                    "artifact_class": "model-instrumentation",
                    "empirical": True,
                    "evidence_eligible": False,
                    "claim_ids": [],
                    "status": "fail",
                    "error": str(exc),
                    "model": LAB01_MODEL_ID,
                    "revision": LAB01_MODEL_REVISION,
                    "license_id": LAB01_LICENSE_ID,
                }
            ),
            end="",
        )
        return 1

    print(_stable_dump(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
