from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.request import Request, urlopen
import hashlib
from datetime import datetime, timezone
from contextlib import AbstractContextManager
from typing import Final


_BLOCK_SIZE = 1 << 20


A0R2_MODEL_ID: Final[str] = "HuggingFaceTB/SmolLM2-360M"
A0R2_MODEL_REVISION: Final[str] = "f8027fd0eaeea54caa13c31d31b9fdc459c38b49"
A0R2_LICENSE_ID: Final[str] = "Apache-2.0"
A0R2_SOURCE_URL: Final[str] = (
    f"https://huggingface.co/{A0R2_MODEL_ID}/tree/{A0R2_MODEL_REVISION}"
)
A0R2_TERMS_URL: Final[str] = (
    f"https://huggingface.co/{A0R2_MODEL_ID}/blob/{A0R2_MODEL_REVISION}/README.md"
)
A0R2_RESOLVE_URL: Final[str] = (
    f"https://huggingface.co/{A0R2_MODEL_ID}/resolve/{A0R2_MODEL_REVISION}/{{file}}"
)

# Exact allowlist and official integrity metadata at revision f8027fd0eaeea54caa13c31d31b9fdc459c38b49
# Note: model.safetensors is LFS and uses sha256; all other entries use Git blob SHA1.
A0R2_REQUIRED_FILES: Final[tuple[str, ...]] = (
    "README.md",
    "config.json",
    "generation_config.json",
    "merges.txt",
    "model.safetensors",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
)
A0R2_EXPECTED_SIZE_AND_OID: Final[dict[str, tuple[int, str]]] = {
    "README.md": (6623, "75cae4c3d8f5f25a3f22ef6427403db2bb3dc83b"),
    "config.json": (689, "2c111af0f7d9845b3b9910d3d18f7cdd94bf16c4"),
    "generation_config.json": (111, "0fce861c328ff24830f3037d91ce773254447bf7"),
    "merges.txt": (466391, "69503b13f727ba3812b6803e97442a6de05ef5eb"),
    "model.safetensors": (723674912, "7aaff6661428bed033abba9522bec81938678642cca3181fe752b6ca9e1e540f"),
    "special_tokens_map.json": (831, "f6652f246cb895ca1edfb16d10b57917b266e335"),
    "tokenizer.json": (2104556, "f922b1797f0c88e71addc8393787831f2477a4bd"),
    "tokenizer_config.json": (3658, "d45192775d58298087a1fedf5967fe5b63b091ab"),
    "vocab.json": (800662, "0ad5ecc2035b7031b88afb544ee95e2d49baa484"),
}

A0R2_EXPECTED_TOTAL_BYTES: Final[int] = 727_058_433
A0R2_MAX_RUNTIME_BYTES: Final[int] = 1_073_741_824
A0R2_NETWORK_TIMEOUT_SECONDS: Final[int] = 60

Chunk = bytes
Headers = dict[str, str]
ResponseLike = Any
HTTPGet = Callable[[str, Headers], ResponseLike]


class A0R2AcquisitionError(RuntimeError):
    """Raised when A0R2 acquisition or integrity verification fails."""


@dataclass(frozen=True)
class RuntimeFileReceipt:
    name: str
    size: int
    sha256: str


class _StreamingHTTPResponse(AbstractContextManager["_StreamingHTTPResponse"]):
    def __init__(self, response: Any) -> None:
        self._response = response

    def iter_content(self, chunk_size: int = _BLOCK_SIZE):
        for chunk in iter(lambda: self._response.read(chunk_size), b""):
            yield chunk

    @property
    def status_code(self) -> int:
        return getattr(self._response, "status", 200)

    def close(self) -> None:
        close = getattr(self._response, "close", None)
        if callable(close):
            close()

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_blob_sha1(data: bytes) -> str:
    # Git blob format for object hash verification.
    prefix = f"blob {len(data)}\x00".encode("utf-8")
    return hashlib.sha1(prefix + data).hexdigest()


def _make_default_opener() -> HTTPGet:
    def _open(url: str, headers: dict[str, str]) -> _StreamingHTTPResponse:
        request = Request(url, headers=headers)
        return _StreamingHTTPResponse(urlopen(request, timeout=A0R2_NETWORK_TIMEOUT_SECONDS))

    return _open


def _iter_response_chunks(response: Any, chunk_size: int = _BLOCK_SIZE):
    reader = getattr(response, "iter_content", None)
    if callable(reader):
        yield from reader(chunk_size=chunk_size)
        return

    read_fn = getattr(response, "read", None)
    if not callable(read_fn):
        raise A0R2AcquisitionError("response object does not support iter_content or read")

    while True:
        chunk = read_fn(chunk_size)
        if not chunk:
            break
        yield chunk


def _close_response(response: Any) -> None:
    closer = getattr(response, "close", None)
    if callable(closer):
        closer()


def _stream_file_hashes(path: Path, *, expected_size: int | None = None) -> tuple[int, str, str]:
    sha256_digest = hashlib.sha256()
    blob_digest = hashlib.sha1()
    if expected_size is not None:
        blob_digest.update(f"blob {expected_size}\x00".encode("utf-8"))

    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_BLOCK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            sha256_digest.update(chunk)
            blob_digest.update(chunk)

    return size, sha256_digest.hexdigest(), blob_digest.hexdigest()


def _validate_allowlist(allowlist: tuple[str, ...]) -> None:
    allowed = set(A0R2_REQUIRED_FILES)
    if set(allowlist) != allowed:
        raise A0R2AcquisitionError("allowlist must be exactly the required runtime files")
    for entry in allowlist:
        if "/" in entry or entry in {"..", "../", "/..", "./", "."}:
            raise A0R2AcquisitionError(f"invalid allowlist entry: {entry}")


def _check_no_unexpected_files(model_dir: Path, allowlist: tuple[str, ...]) -> None:
    allowed = set(allowlist)
    unexpected: list[str] = []
    for item in model_dir.iterdir():
        if item.name not in allowed:
            unexpected.append(item.name)
    if unexpected:
        raise A0R2AcquisitionError("unexpected file in snapshot: " + ",".join(sorted(unexpected)))


def _clean_authorized_partials(model_dir: Path, allowlist: tuple[str, ...]) -> None:
    for file_name in allowlist:
        partial = model_dir / f".{file_name}.tmp"
        if partial.is_file():
            partial.unlink()


def _build_url(file: str) -> str:
    return A0R2_RESOLVE_URL.format(file=file)


def _expected_identity(file: str) -> tuple[int, str]:
    try:
        return A0R2_EXPECTED_SIZE_AND_OID[file]
    except KeyError as exc:
        raise A0R2AcquisitionError(f"unexpected runtime file requested: {file}") from exc


def verify_runtime_file(path: Path, file_name: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    expected_size, expected_oid = _expected_identity(file_name)

    if not path.exists():
        return False, [f"missing file: {file_name}"]

    size, actual_sha256, actual_blob = _stream_file_hashes(path, expected_size=expected_size)
    if size != expected_size:
        errors.append(f"size mismatch: {file_name}")

    if file_name == "model.safetensors":
        if actual_sha256 != expected_oid:
            errors.append(f"sha256 mismatch: {file_name}")
    else:
        if actual_blob != expected_oid:
            errors.append(f"blob sha1 mismatch: {file_name}")

    return len(errors) == 0, errors


def build_runtime_file_receipts(model_dir: Path, *, allowlist: tuple[str, ...] | None = None) -> list[RuntimeFileReceipt]:
    _validate_allowlist(allowlist or A0R2_REQUIRED_FILES)
    base = model_dir.resolve()
    if not base.is_dir():
        raise A0R2AcquisitionError(f"model directory not found: {base}")

    receipts: list[RuntimeFileReceipt] = []
    for file_name in (allowlist or A0R2_REQUIRED_FILES):
        path = base / file_name
        if not path.is_file():
            raise A0R2AcquisitionError(f"required runtime file not found: {file_name}")
        expected_size, _ = _expected_identity(file_name)
        size, file_sha256, file_blob = _stream_file_hashes(path, expected_size=expected_size)
        if size != expected_size:
            raise A0R2AcquisitionError(f"size mismatch for {file_name}: expected {expected_size}, got {size}")
        expected_oid = _expected_identity(file_name)[1]
        if file_name == "model.safetensors" and file_sha256 != expected_oid:
            raise A0R2AcquisitionError(f"sha256 mismatch for {file_name}")
        if file_name != "model.safetensors" and file_blob != expected_oid:
            raise A0R2AcquisitionError(f"blob sha1 mismatch for {file_name}")
        receipts.append(RuntimeFileReceipt(name=file_name, size=size, sha256=file_sha256))
    return receipts


def verify_runtime_file_receipts(model_dir: Path, receipts: Mapping[str, Mapping[str, Any]]) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    try:
        _validate_allowlist(tuple(receipts.keys()))
    except A0R2AcquisitionError as exc:
        return False, [str(exc)]

    base = model_dir.resolve()
    for file_name in A0R2_REQUIRED_FILES:
        entry = receipts.get(file_name, {})
        path = base / file_name

        if not path.is_file():
            mismatches.append(f"missing file: {file_name}")
            continue

        expected_size, expected_oid = _expected_identity(file_name)
        size, actual_sha256, actual_blob = _stream_file_hashes(path, expected_size=expected_size)
        expected_blob_oid = str(entry.get("sha1", "")).lower() or expected_oid
        if int(entry.get("size", -1)) != expected_size:
            mismatches.append(f"size mismatch: {file_name}")
        if file_name == "model.safetensors":
            expected_sha = str(entry.get("sha256", "")).lower()
            if expected_sha != actual_sha256:
                mismatches.append(f"sha256 mismatch: {file_name}")
            if actual_sha256 != expected_oid:
                mismatches.append(f"official sha256 mismatch: {file_name}")
            continue

        receipt_sha256 = str(entry.get("sha256", "")).lower()
        if receipt_sha256 and receipt_sha256 != actual_sha256:
            mismatches.append(f"sha256 mismatch: {file_name}")
        if actual_blob != expected_blob_oid:
            mismatches.append(f"sha1 mismatch: {file_name}")

    return len(mismatches) == 0, mismatches


def _stream_and_write_download(
    *,
    file_name: str,
    opener: HTTPGet,
    destination_dir: Path,
    expected_size: int,
    expected_oid: str,
    budget_remaining: int,
) -> int:
    url = _build_url(file_name)
    try:
        response = opener(url, {"Accept-Encoding": "identity"})
    except Exception as exc:
        raise A0R2AcquisitionError(f"download transport failed for {file_name}: {exc}") from exc

    if getattr(response, "status_code", 200) >= 400:
        status = response.status_code
        _close_response(response)
        raise A0R2AcquisitionError(f"download failed for {file_name}: status {status}")

    downloaded = 0
    tmp_path = destination_dir / f".{file_name}.tmp"
    destination = destination_dir / file_name

    def _cleanup_tmp() -> None:
        if tmp_path.exists():
            tmp_path.unlink()

    sha256_digest = hashlib.sha256()
    blob_digest = hashlib.sha1(f"blob {expected_size}\x00".encode("utf-8"))

    try:
        with tmp_path.open("wb") as handle:
            for chunk in _iter_response_chunks(response, chunk_size=_BLOCK_SIZE):
                if not isinstance(chunk, (bytes, bytearray)):
                    raise A0R2AcquisitionError(f"invalid chunk type for {file_name}")
                downloaded += len(chunk)
                if downloaded > expected_size or downloaded > budget_remaining:
                    raise A0R2AcquisitionError(f"runtime budget exceeded while downloading {file_name}")
                handle.write(chunk)
                sha256_digest.update(chunk)
                blob_digest.update(chunk)

        if downloaded != expected_size:
            raise A0R2AcquisitionError(f"size mismatch after download for {file_name}")

        if file_name == "model.safetensors":
            if sha256_digest.hexdigest() != expected_oid:
                raise A0R2AcquisitionError(f"integrity mismatch (sha256) for {file_name}")
        else:
            if blob_digest.hexdigest() != expected_oid:
                raise A0R2AcquisitionError(f"integrity mismatch (blob sha1) for {file_name}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.replace(destination)
    except BaseException:
        _cleanup_tmp()
        raise
    finally:
        _close_response(response)

    return downloaded


def _verify_or_clean_existing_files(
    *,
    model_dir: Path,
    allowlist: tuple[str, ...],
) -> tuple[list[str], int, int]:
    missing: list[str] = []
    verified = 0
    existing_size = 0
    for file_name in allowlist:
        resolved = model_dir / file_name
        if not resolved.exists():
            missing.append(file_name)
            continue
        ok, _errors = verify_runtime_file(resolved, file_name)
        if ok:
            expected_size, _ = _expected_identity(file_name)
            verified += 1
            existing_size += expected_size
            continue

        if resolved.is_file():
            resolved.unlink()
        missing.append(file_name)
    return missing, verified, existing_size


def build_integrity_receipt(
    *,
    model_dir: Path,
    contract_sha256: str,
    local_locator: str,
    receipt_time: str | None = None,
    allowlist: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    if (allowlist is None) or not allowlist:
        allowlist = A0R2_REQUIRED_FILES
    _validate_allowlist(allowlist)

    runtime = build_runtime_file_receipts(model_dir, allowlist=allowlist)
    runtime_by_name = {item.name: item for item in runtime}
    records = []
    for name in A0R2_REQUIRED_FILES:
        item = runtime_by_name[name]
        expected_size, expected_oid = _expected_identity(name)
        records.append(
            {
                "name": name,
                "size": item.size,
                "sha256": item.sha256,
                "source_kind": "lfs_sha256" if name == "model.safetensors" else "git_blob",
                "source_oid": expected_oid,
                "source_url": _build_url(name),
            }
        )

    return {
        "artifact_class": "a0r2-acquisition-receipt",
        "status": "pass",
        "integrity_status": "integrity_verified",
        "state_before": "acquisition_authorized",
        "state_after": "integrity_verified",
        "scientific_status": "instrumentation_only",
        "empirical": False,
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "contract_sha256": contract_sha256,
        "model": {
            "id": A0R2_MODEL_ID,
            "revision": A0R2_MODEL_REVISION,
            "license_id": A0R2_LICENSE_ID,
        },
        "source_url": A0R2_SOURCE_URL,
        "terms_url": A0R2_TERMS_URL,
        "receipt_time": receipt_time or datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "authorization": {
            "scope": "exact_snapshot_download_and_integrity_receipt_only",
            "maximum_download_bytes": A0R2_MAX_RUNTIME_BYTES,
        },
        "local_locator": local_locator,
        "total_bytes": sum(item.size for item in runtime),
        "runtime_files": records,
        "access": {
            "model_loaded": False,
            "model_output_accessed": False,
            "sealed_targets_accessed": False,
            "feasibility_tested": False,
        },
    }


def acquire_a0r2_runtime(
    model_dir: Path,
    *,
    allow_download: bool,
    open_url: HTTPGet | None = None,
    allowlist: tuple[str, ...] = A0R2_REQUIRED_FILES,
    max_runtime_bytes: int = A0R2_MAX_RUNTIME_BYTES,
) -> Path:
    """Acquire the exact R2 runtime snapshot without loading the model."""
    resolved = model_dir.resolve()
    _validate_allowlist(allowlist)
    required_total = sum(A0R2_EXPECTED_SIZE_AND_OID[name][0] for name in allowlist)
    if max_runtime_bytes > A0R2_MAX_RUNTIME_BYTES:
        raise A0R2AcquisitionError("runtime budget exceeds the frozen 1 GiB ceiling")
    if max_runtime_bytes < required_total:
        raise A0R2AcquisitionError(
            f"download exceeds allowed budget: need {required_total} bytes, max {max_runtime_bytes}"
        )
    opener = open_url or _make_default_opener()

    resolved.mkdir(parents=True, exist_ok=True)
    _clean_authorized_partials(resolved, allowlist)
    _check_no_unexpected_files(resolved, allowlist)
    missing, _, verified_size = _verify_or_clean_existing_files(
        model_dir=resolved,
        allowlist=allowlist,
    )
    if not missing:
        errors: list[str] = []
        for file_name in allowlist:
            ok, file_errors = verify_runtime_file(resolved / file_name, file_name)
            if not ok:
                errors.extend(file_errors)
        verified = not errors
        if not verified:
            raise A0R2AcquisitionError("verified existing files but payload is inconsistent: " + "; ".join(errors))
        _check_no_unexpected_files(resolved, allowlist)
        return resolved

    bytes_needed = sum(A0R2_EXPECTED_SIZE_AND_OID[file_name][0] for file_name in missing)
    if bytes_needed > max_runtime_bytes:
        raise A0R2AcquisitionError(
            f"download exceeds allowed budget: need {bytes_needed} bytes, max {max_runtime_bytes}"
        )
    if verified_size + bytes_needed > max_runtime_bytes:
        raise A0R2AcquisitionError("runtime budget exceeded by requested files")

    if not allow_download:
        raise A0R2AcquisitionError(
            f"acquisition denied: operator authorization is required to download {A0R2_MODEL_ID}"
        )

    budget_remaining = max_runtime_bytes - verified_size
    for file_name in allowlist:
        if file_name not in missing:
            continue
        expected_size, expected_oid = _expected_identity(file_name)
        _stream_and_write_download(
            file_name=file_name,
            opener=opener,
            destination_dir=resolved,
            expected_size=expected_size,
            expected_oid=expected_oid,
            budget_remaining=budget_remaining,
        )
        budget_remaining -= expected_size

    verified, errors = verify_runtime_file_receipts(
        resolved,
        {
            name: {
                "size": A0R2_EXPECTED_SIZE_AND_OID[name][0],
                **(
                    {"sha1": A0R2_EXPECTED_SIZE_AND_OID[name][1]}
                    if name != "model.safetensors"
                    else {"sha256": A0R2_EXPECTED_SIZE_AND_OID[name][1]}
                ),
            }
            for name in allowlist
        },
    )
    if not verified:
        raise A0R2AcquisitionError("post-download integrity verification failed: " + "; ".join(errors))

    _check_no_unexpected_files(resolved, allowlist)
    return resolved


def build_integrity_report_payload(
    model_dir: Path,
    *,
    contract_sha256: str,
    local_locator: str,
) -> dict[str, Any]:
    """Alias used by CI recipes: returns the integrity payload and normalized model manifest."""
    return {
        "integrity_receipt": build_integrity_receipt(
            model_dir=model_dir,
            contract_sha256=contract_sha256,
            local_locator=local_locator,
        ),
        "manifest": {
            "status": "integrity_verified",
            "model": A0R2_MODEL_ID,
            "revision": A0R2_MODEL_REVISION,
            "total_expected_bytes": A0R2_EXPECTED_TOTAL_BYTES,
            "files": [
                {"name": name, "size": A0R2_EXPECTED_SIZE_AND_OID[name][0], "oid": A0R2_EXPECTED_SIZE_AND_OID[name][1]}
                for name in A0R2_REQUIRED_FILES
            ],
        },
        "access": {
            "model_loaded": False,
            "model_output_accessed": False,
            "sealed_targets_accessed": False,
            "feasibility_tested": False,
        },
    }
