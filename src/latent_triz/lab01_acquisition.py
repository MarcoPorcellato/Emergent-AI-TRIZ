from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
import hashlib
import json
import os
import re
from datetime import datetime, timezone
import inspect
from typing import Final


LAB01_MODEL_ID: Final[str] = "EleutherAI/pythia-70m-deduped"
LAB01_MODEL_REVISION: Final[str] = "e93a9faa9c77e5d09219f6c868bfc7a1bd65593c"
LAB01_LICENSE_ID: Final[str] = "Apache-2.0"
LAB01_SOURCE_URL: Final[str] = f"https://huggingface.co/{LAB01_MODEL_ID}/tree/{LAB01_MODEL_REVISION}"
LAB01_TERMS_URL: Final[str] = f"https://huggingface.co/{LAB01_MODEL_ID}/blob/{LAB01_MODEL_REVISION}/README.md"
LAB01_REQUIRED_FILES: Final[tuple[str, ...]] = (
    "config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "README.md",
)
LAB01_EXPECTED_SHA256: Final[dict[str, str]] = {
    "README.md": "0b8eff9fd326d9089f00c4984db07f89a9dac674ae3191a9bc8ae128b8a37580",
    "config.json": "002050231a9b1ec3ac77aa6b9b3bbdc4d923f4068a7dd33b8da72a9bd6ad9a43",
    "model.safetensors": "3da388330e4549156d76b58d6d268c63cd005e9336b4f4d2d378421e7b7a33fd",
    "special_tokens_map.json": "6f50ab5a5a509a1c309d6171f339b196a900dc9c99ad0408ff23bb615fdae7ad",
    "tokenizer.json": "c24618a1b3e6a38167beff1c72cffd126c3a66254347304b50547d12c5f25624",
    "tokenizer_config.json": "70e38394e494931c6f773ba41e19460dd4436526b852207367f04341b4066d3f",
}
LAB01_STATE_ORDER: Final[tuple[str, ...]] = (
    "unselected",
    "selected",
    "acquisition_planned",
    "acquired",
    "integrity_verified",
    "load_verified",
    "instrumentation_verified",
    "lab_ready",
)

_REVISION_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{40}$")


class Lab01AcquisitionError(RuntimeError):
    """Raised when Lab 01 model acquisition or integrity steps fail."""


@dataclass(frozen=True)
class FileReceipt:
    name: str
    sha256: str
    size: int


def _snapshot_download_with_compatibility(
    *,
    call_snapshot_download: Callable[..., Any] | None = None,
    repo_id: str,
    revision: str,
    local_dir: str | os.PathLike[str],
    allow_patterns: Iterable[str],
) -> str:
    fn = call_snapshot_download or _load_snapshot_download()

    kwargs = {
        "repo_id": repo_id,
        "revision": revision,
        "local_dir": str(local_dir),
        "allow_patterns": list(allow_patterns),
    }
    if "local_dir_use_symlinks" in inspect.signature(fn).parameters:
        kwargs["local_dir_use_symlinks"] = False
    return fn(**kwargs)


def _load_snapshot_download() -> Callable[..., Any]:
    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:  # pragma: no cover
        raise Lab01AcquisitionError(
            "huggingface_hub is required for Lab 01 acquisition but not available"
        ) from exc
    return snapshot_download


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256_and_size(path: Path) -> FileReceipt:
    resolved = path.resolve()
    if not resolved.is_file():
        raise Lab01AcquisitionError(f"required runtime file not found: {resolved}")
    digest = _sha256_bytes(resolved.read_bytes())
    return FileReceipt(
        name=resolved.name,
        sha256=digest,
        size=resolved.stat().st_size,
    )


def build_runtime_file_receipts(model_dir: Path) -> dict[str, FileReceipt]:
    base = model_dir.resolve()
    if not base.is_dir():
        raise Lab01AcquisitionError(f"model directory not found: {base}")

    receipts: dict[str, FileReceipt] = {}
    for filename in LAB01_REQUIRED_FILES:
        receipts[filename] = file_sha256_and_size(base / filename)
    return receipts


def verify_expected_snapshot(model_dir: Path) -> tuple[bool, list[str]]:
    """Verify every allowlisted file against the frozen exact-revision hashes."""
    actual = build_runtime_file_receipts(model_dir)
    mismatches = [
        f"unexpected sha256 for {name}"
        for name, expected in LAB01_EXPECTED_SHA256.items()
        if actual[name].sha256 != expected
    ]
    return (not mismatches, mismatches)


def verify_runtime_file_receipts(
    model_dir: Path,
    receipts: Mapping[str, Mapping[str, str | int]],
) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    base = model_dir.resolve()
    for filename in LAB01_REQUIRED_FILES:
        received = receipts.get(filename)
        if not isinstance(received, Mapping):
            mismatches.append(f"missing receipt for {filename}")
            continue
        expected_sha = str(received.get("sha256"))
        expected_size = int(received.get("size"))
        try:
            actual = file_sha256_and_size(base / filename)
        except Lab01AcquisitionError as exc:
            mismatches.append(str(exc))
            continue
        if actual.sha256 != expected_sha:
            mismatches.append(f"sha mismatch for {filename}")
        if actual.size != expected_size:
            mismatches.append(f"size mismatch for {filename}")
    return (not mismatches, mismatches)


def runtime_receipts_to_payload(receipts: Mapping[str, FileReceipt]) -> list[dict[str, str | int]]:
    return [receipt.__dict__ for _, receipt in sorted(receipts.items(), key=lambda item: item[0])]


def build_integrity_receipt(
    *,
    model_dir: Path,
    state_before: str,
    notes: str = "",
) -> dict[str, Any]:
    if state_before != "acquired":
        raise Lab01AcquisitionError("integrity receipt is valid only after acquired state")
    runtime = build_runtime_file_receipts(model_dir)
    payload = {
        "artifact_class": "model-instrumentation",
        "empirical": True,
        "evidence_eligible": False,
        "claim_ids": [],
        "receipt_type": "integrity",
        "state_before": "acquired",
        "state_after": "integrity_verified",
        "model": LAB01_MODEL_ID,
        "revision": LAB01_MODEL_REVISION,
        "license_id": LAB01_LICENSE_ID,
        "receipt_time": datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_url": LAB01_SOURCE_URL,
        "terms_url": LAB01_TERMS_URL,
        "runtime_files": runtime_receipts_to_payload(runtime),
        "notes": notes,
    }
    return payload


def _is_valid_model_identity(receipt: Mapping[str, Any]) -> bool:
    return (
        str(receipt.get("model")) == LAB01_MODEL_ID
        and str(receipt.get("revision")) == LAB01_MODEL_REVISION
    )


def _is_valid_revision(value: str) -> bool:
    return bool(_REVISION_RE.match(value))


def _is_supported_receipt(receipt: Mapping[str, Any], *, expected_type: str, expected_from: str, expected_to: str) -> bool:
    if not isinstance(receipt, Mapping):
        return False
    if str(receipt.get("receipt_type")) != expected_type:
        return False
    if str(receipt.get("state_before")) != expected_from or str(receipt.get("state_after")) != expected_to:
        return False
    if not _is_valid_model_identity(receipt):
        return False
    if not _is_valid_revision(str(receipt.get("revision"))):
        return False
    return True


def _required_runtime_files_present(model_dir: Path) -> bool:
    if not model_dir.exists() or not model_dir.is_dir():
        return False
    return all((model_dir / filename).is_file() for filename in LAB01_REQUIRED_FILES)


def derive_lab01_state(
    model_dir: Path,
    selection_receipt: Mapping[str, Any] | None = None,
    acquisition_receipt: Mapping[str, Any] | None = None,
    integrity_receipt: Mapping[str, Any] | None = None,
    load_receipt: Mapping[str, Any] | None = None,
    instrumentation_receipt: Mapping[str, Any] | None = None,
) -> str:
    """Derive Lab 01 state only from evidence payloads and required files."""

    state = "unselected"
    if _is_supported_receipt(
        selection_receipt or {},
        expected_type="selection",
        expected_from="unselected",
        expected_to="selected",
    ):
        state = "selected"
    else:
        return state

    if _is_supported_receipt(
        acquisition_receipt or {},
        expected_type="acquisition",
        expected_from="selected",
        expected_to="acquisition_planned",
    ):
        state = "acquisition_planned"
    else:
        return state

    if not _required_runtime_files_present(model_dir):
        return state
    state = "acquired"

    if _is_supported_receipt(
        integrity_receipt or {},
        expected_type="integrity",
        expected_from="acquired",
        expected_to="integrity_verified",
    ):
        runtime_payload = integrity_receipt.get("runtime_files")
        if isinstance(runtime_payload, list):
            payload_map: dict[str, dict[str, str | int]] = {}
            for item in runtime_payload:
                if not isinstance(item, Mapping):
                    return state
                name = str(item.get("name"))
                if name not in LAB01_REQUIRED_FILES:
                    return state
                payload_map[name] = {
                    "sha256": item.get("sha256"),
                    "size": item.get("size"),
                }
            matched, _errors = verify_runtime_file_receipts(model_dir, payload_map)
            if not matched:
                return state
        state = "integrity_verified"
    else:
        return state

    if _is_supported_receipt(
        load_receipt or {},
        expected_type="load",
        expected_from="integrity_verified",
        expected_to="load_verified",
    ):
        state = "load_verified"
    else:
        return state

    if _is_supported_receipt(
        instrumentation_receipt or {},
        expected_type="instrumentation",
        expected_from="load_verified",
        expected_to="instrumentation_verified",
    ):
        state = "instrumentation_verified"
    else:
        return state

    if state == "instrumentation_verified":
        return "lab_ready"
    return state


def ensure_lab01_model(
    model_dir: Path,
    *,
    allow_download: bool,
    call_snapshot_download: Callable[..., Any] | None = None,
    identity_verifier: Callable[[Path], tuple[bool, list[str]]] = verify_expected_snapshot,
) -> Path:
    """Ensure required runtime files are available locally."""
    resolved = model_dir.resolve()
    if _required_runtime_files_present(resolved):
        verified, mismatches = identity_verifier(resolved)
        if not verified:
            raise Lab01AcquisitionError(
                "local snapshot failed frozen hash verification: " + "; ".join(mismatches)
            )
        return resolved

    if not allow_download:
        raise Lab01AcquisitionError(
            f"acquisition denied: operator authorization is required to download {LAB01_MODEL_ID}"
        )

    resolved.mkdir(parents=True, exist_ok=True)
    _snapshot_download_with_compatibility(
        call_snapshot_download=call_snapshot_download,
        repo_id=LAB01_MODEL_ID,
        revision=LAB01_MODEL_REVISION,
        local_dir=resolved,
        allow_patterns=LAB01_REQUIRED_FILES,
    )

    if not _required_runtime_files_present(resolved):
        raise Lab01AcquisitionError(
            "download completed but required runtime files are missing from the snapshot allowlist"
        )
    verified, mismatches = identity_verifier(resolved)
    if not verified:
        raise Lab01AcquisitionError("downloaded snapshot failed frozen hash verification: " + "; ".join(mismatches))
    return resolved
