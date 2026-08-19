#!/usr/bin/env python3
"""Explicitly authorized, download-only Qwen3 acquisition command."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.exp001_qwen_acquisition import (  # noqa: E402
    ROOT_LOCATOR,
    QwenAcquisitionError,
    acquire_qwen,
    build_receipt,
    write_receipt,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-download", action="store_true", required=True)
    parser.add_argument("--root", type=Path, default=ROOT / ROOT_LOCATOR)
    parser.add_argument(
        "--receipt",
        type=Path,
        default=ROOT / "results/exp001-comparative/preexecution/qwen-integrity-receipt.json",
    )
    parser.add_argument(
        "--authorization",
        type=Path,
        default=ROOT / "experiments/exp001-comparative-reference/qwen-download-authorization.json",
    )
    args = parser.parse_args(argv)
    try:
        authorization = json.loads(args.authorization.read_text(encoding="utf-8"))
        acquire_qwen(args.root, allow_download=True, authorization=authorization)
        receipt = build_receipt(args.root, authorization_sha256=_sha256(args.authorization))
        write_receipt(args.receipt, receipt)
    except QwenAcquisitionError as exc:
        print(f"qwen acquisition refused: {exc}", file=sys.stderr)
        return 1
    print(f"qwen integrity receipt: {args.receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
