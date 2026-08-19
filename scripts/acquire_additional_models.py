#!/usr/bin/env python3
"""Acquire one explicitly authorized additional EXP-001 model snapshot."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.exp001_additional_acquisition import (  # noqa: E402
    MODEL_SPECS,
    AdditionalAcquisitionError,
    acquire_additional,
    build_receipt_from_authorized,
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
    parser.add_argument("--model-id", required=True, choices=sorted(MODEL_SPECS))
    parser.add_argument("--allow-download", action="store_true", required=True)
    parser.add_argument("--authorization", type=Path, default=ROOT / "experiments/exp001-comparative-reference/additional-model-authorization.json")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    spec = MODEL_SPECS[args.model_id]
    root = args.root or ROOT / spec.root_locator
    receipt_path = args.receipt or ROOT / f"results/exp001-comparative/preexecution/{args.model_id.split('/')[-1].lower()}-integrity-receipt.json"
    try:
        authorization = json.loads(args.authorization.read_text(encoding="utf-8"))
        acquire_additional(args.model_id, root, authorization=authorization, allow_download=args.allow_download)
        receipt = build_receipt_from_authorized(
            args.model_id,
            root,
            authorization=authorization,
            authorization_sha256=_sha256(args.authorization),
        )
        write_receipt(receipt_path, receipt)
    except (OSError, json.JSONDecodeError, AdditionalAcquisitionError) as exc:
        print(f"additional acquisition refused: {exc}", file=sys.stderr)
        return 1
    print(f"integrity receipt: {receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
