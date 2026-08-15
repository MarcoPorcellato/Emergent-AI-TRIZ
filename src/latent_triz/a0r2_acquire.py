from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .a0r2_acquisition import (
    A0R2_EXPECTED_SIZE_AND_OID,
    A0R2_EXPECTED_TOTAL_BYTES,
    A0R2_LICENSE_ID,
    A0R2_MAX_RUNTIME_BYTES,
    A0R2_MODEL_ID,
    A0R2_MODEL_REVISION,
    A0R2_REQUIRED_FILES,
    A0R2AcquisitionError,
    acquire_a0r2_runtime,
    build_integrity_receipt,
    verify_runtime_file_receipts,
)


CONTRACT_PATH = Path("experiments/a0r2-independent-model/acquisition-contract.json")
RECEIPT_PATH = Path("results/a0r2/preexecution/smollm2-360m-f8027fd0/integrity-receipt.json")


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _load_and_verify_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R2AcquisitionError(f"cannot read frozen acquisition contract: {exc}") from exc
    runtime = payload.get("runtime_files")
    expected_runtime = [
        {
            "name": name,
            "size": A0R2_EXPECTED_SIZE_AND_OID[name][0],
            "source_kind": "lfs_sha256" if name == "model.safetensors" else "git_blob",
            "source_oid": A0R2_EXPECTED_SIZE_AND_OID[name][1],
        }
        for name in A0R2_REQUIRED_FILES
    ]
    expected_identity = {
        "id": A0R2_MODEL_ID,
        "revision": A0R2_MODEL_REVISION,
        "license_id": A0R2_LICENSE_ID,
    }
    model = payload.get("model") if isinstance(payload.get("model"), dict) else {}
    identity = {key: model.get(key) for key in expected_identity}
    authorization = payload.get("authorization") if isinstance(payload.get("authorization"), dict) else {}
    if identity != expected_identity:
        raise A0R2AcquisitionError("frozen acquisition contract model identity mismatch")
    if runtime != expected_runtime:
        raise A0R2AcquisitionError("frozen acquisition contract runtime allowlist mismatch")
    if payload.get("expected_total_bytes") != A0R2_EXPECTED_TOTAL_BYTES:
        raise A0R2AcquisitionError("frozen acquisition contract total mismatch")
    if authorization.get("status") != "operator_authorized":
        raise A0R2AcquisitionError("operator authorization is absent")
    if authorization.get("scope") != "exact_snapshot_download_and_integrity_receipt_only":
        raise A0R2AcquisitionError("operator authorization scope mismatch")
    if authorization.get("maximum_download_bytes") != A0R2_MAX_RUNTIME_BYTES:
        raise A0R2AcquisitionError("operator budget mismatch")
    if authorization.get("not_authorized") != [
        "model_load",
        "feasibility_test",
        "model_output_access",
        "sealed_target_access",
        "sealed_r2_execution",
    ]:
        raise A0R2AcquisitionError("operator exclusion boundary mismatch")
    if payload.get("selection_observed_r1_performance") is not False:
        raise A0R2AcquisitionError("model selection independence mismatch")
    if payload.get("local_locator") != "artifacts/models/smollm2-360m-f8027fd0":
        raise A0R2AcquisitionError("local locator mismatch")
    return payload


def _write_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise A0R2AcquisitionError(f"refusing to overwrite immutable receipt: {path.as_posix()}")
    temporary = path.with_name(f".{path.name}.tmp")
    if temporary.exists():
        temporary.unlink()
    try:
        temporary.write_text(_stable_json(payload), encoding="utf-8")
        os.link(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R2AcquisitionError(f"cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise A0R2AcquisitionError(f"{label} must be a JSON object")
    return payload


def _verify_receipt(contract_path: Path, receipt_path: Path) -> dict[str, Any]:
    contract = _load_and_verify_contract(contract_path)
    receipt = _load_json(receipt_path, "integrity receipt")
    expected_access = {
        "model_loaded": False,
        "model_output_accessed": False,
        "sealed_targets_accessed": False,
        "feasibility_tested": False,
    }
    expected_model = {
        "id": A0R2_MODEL_ID,
        "revision": A0R2_MODEL_REVISION,
        "license_id": A0R2_LICENSE_ID,
    }
    if receipt.get("artifact_class") != "a0r2-acquisition-receipt":
        raise A0R2AcquisitionError("integrity receipt artifact class mismatch")
    if receipt.get("status") != "pass" or receipt.get("integrity_status") != "integrity_verified":
        raise A0R2AcquisitionError("integrity receipt is not terminally verified")
    if receipt.get("contract_sha256") != _sha256(contract_path):
        raise A0R2AcquisitionError("integrity receipt contract hash mismatch")
    if receipt.get("model") != expected_model:
        raise A0R2AcquisitionError("integrity receipt model identity mismatch")
    if receipt.get("access") != expected_access:
        raise A0R2AcquisitionError("integrity receipt access boundary mismatch")
    if receipt.get("authorization") != {
        "scope": "exact_snapshot_download_and_integrity_receipt_only",
        "maximum_download_bytes": A0R2_MAX_RUNTIME_BYTES,
    }:
        raise A0R2AcquisitionError("integrity receipt authorization mismatch")
    if receipt.get("local_locator") != contract.get("local_locator"):
        raise A0R2AcquisitionError("integrity receipt locator mismatch")
    runtime = receipt.get("runtime_files")
    if not isinstance(runtime, list) or [item.get("name") for item in runtime if isinstance(item, dict)] != list(A0R2_REQUIRED_FILES):
        raise A0R2AcquisitionError("integrity receipt runtime allowlist mismatch")
    runtime_map = {str(item["name"]): item for item in runtime if isinstance(item, dict)}
    for name in A0R2_REQUIRED_FILES:
        item = runtime_map[name]
        expected_size, expected_oid = A0R2_EXPECTED_SIZE_AND_OID[name]
        if item.get("size") != expected_size:
            raise A0R2AcquisitionError(f"integrity receipt size mismatch: {name}")
        if item.get("source_kind") != ("lfs_sha256" if name == "model.safetensors" else "git_blob"):
            raise A0R2AcquisitionError(f"integrity receipt source kind mismatch: {name}")
        if item.get("source_oid") != expected_oid:
            raise A0R2AcquisitionError(f"integrity receipt source oid mismatch: {name}")
        expected_url = f"https://huggingface.co/{A0R2_MODEL_ID}/resolve/{A0R2_MODEL_REVISION}/{name}"
        if item.get("source_url") != expected_url:
            raise A0R2AcquisitionError(f"integrity receipt source URL mismatch: {name}")
    model_root = Path(str(contract["local_locator"]))
    try:
        actual_entries = sorted(item.name for item in model_root.iterdir())
    except OSError as exc:
        raise A0R2AcquisitionError(f"cannot inspect external snapshot: {exc}") from exc
    if actual_entries != sorted(A0R2_REQUIRED_FILES):
        raise A0R2AcquisitionError("external snapshot contains missing or unexpected entries")
    verified, errors = verify_runtime_file_receipts(model_root, runtime_map)
    if not verified:
        raise A0R2AcquisitionError("external snapshot verification failed: " + "; ".join(errors))
    if sum(int(item.get("size", -1)) for item in runtime_map.values()) != A0R2_EXPECTED_TOTAL_BYTES:
        raise A0R2AcquisitionError("integrity receipt byte total mismatch")
    if receipt.get("total_bytes") != A0R2_EXPECTED_TOTAL_BYTES:
        raise A0R2AcquisitionError("integrity receipt declared total mismatch")
    return {
        "artifact_class": "a0r2-acquisition-verification",
        "status": "pass",
        "contract_sha256": receipt["contract_sha256"],
        "receipt_sha256": _sha256(receipt_path),
        "model": expected_model,
        "runtime_file_count": len(runtime_map),
        "total_bytes": A0R2_EXPECTED_TOTAL_BYTES,
        "access": expected_access,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Acquire the exact A0-R2 snapshot without loading it")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--allow-download", action="store_true")
    mode.add_argument("--verify", action="store_true")
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--receipt-output", type=Path, default=RECEIPT_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.verify:
            verification = _verify_receipt(args.contract, args.receipt_output)
            print(_stable_json(verification), end="")
            return 0
        contract = _load_and_verify_contract(args.contract)
        model_root = Path(str(contract["local_locator"]))
        acquired = acquire_a0r2_runtime(
            model_root,
            allow_download=bool(args.allow_download),
            max_runtime_bytes=int(contract["authorization"]["maximum_download_bytes"]),
        )
        receipt = build_integrity_receipt(
            model_dir=acquired,
            contract_sha256=_sha256(args.contract),
            local_locator=str(contract["local_locator"]),
        )
        _write_exclusive(args.receipt_output, receipt)
    except A0R2AcquisitionError as exc:
        print(_stable_json({
            "artifact_class": "a0r2-acquisition-attempt",
            "status": "fail",
            "error": str(exc),
            "model": A0R2_MODEL_ID,
            "revision": A0R2_MODEL_REVISION,
            "access": {
                "model_loaded": False,
                "model_output_accessed": False,
                "sealed_targets_accessed": False,
                "feasibility_tested": False,
            },
        }), end="")
        return 1
    print(_stable_json(receipt), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
