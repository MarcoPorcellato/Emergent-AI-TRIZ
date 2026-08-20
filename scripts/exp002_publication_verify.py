#!/usr/bin/env python3
"""Fail-closed verification of EXP-002 publication manifests and assets."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]


class PublicationVerificationError(ValueError):
    """Raised when a publication package is incomplete or mutated."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationVerificationError(f"cannot read manifest: {path}") from exc
    if not isinstance(value, dict):
        raise PublicationVerificationError("publication manifest must be an object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise PublicationVerificationError(f"cannot read external asset: {path}") from exc
    return digest.hexdigest()


def _relative_asset(root: Path, locator: Any) -> Path:
    if not isinstance(locator, str) or not locator or locator.startswith("/"):
        raise PublicationVerificationError("asset locator must be a relative repository path")
    candidate = Path(locator)
    if ".." in candidate.parts:
        raise PublicationVerificationError("asset locator escapes repository root")
    return root / candidate


def verify_publication_manifest(manifest_path: str | Path, *, root: str | Path = ROOT) -> dict[str, Any]:
    """Verify tracked manifest and every declared external dense asset."""
    repo = Path(root).resolve()
    manifest_file = Path(manifest_path)
    if not manifest_file.is_absolute():
        manifest_file = repo / manifest_file
    manifest = _load(manifest_file)
    schema_file = repo / "schemas/exp002-publication-manifest.schema.json"
    schema = _load(schema_file)
    errors = list(Draft202012Validator(schema).iter_errors(manifest))
    if errors:
        raise PublicationVerificationError(errors[0].message)
    for package in manifest["packages"]:
        package_path = _relative_asset(repo, package["package_locator"])
        if not package_path.is_dir():
            raise PublicationVerificationError(f"publication package is missing: {package_path}")
    verified_assets = []
    for asset in manifest["external_dense_assets"]:
        asset_path = _relative_asset(repo, asset["locator"])
        if not asset_path.is_file():
            raise PublicationVerificationError(f"external dense asset is missing: {asset_path}")
        observed = _sha256(asset_path)
        if observed != asset["sha256"]:
            raise PublicationVerificationError(f"external dense asset hash mismatch: {asset['locator']}")
        verified_assets.append(asset["locator"])
    return {"status": "pass", "packages": len(manifest["packages"]), "verified_external_assets": verified_assets, "model_access": False, "sealed_target_access": False}


def main(argv: list[str]) -> int:
    manifest = argv[1] if len(argv) > 1 else "results/exp002/preexecution/publication-manifest.json"
    result = verify_publication_manifest(manifest)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
