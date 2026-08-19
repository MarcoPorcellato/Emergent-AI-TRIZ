"""Bounded, receipt-backed acquisition of the frozen Qwen3 snapshot.

This module is deliberately independent of torch/transformers.  It downloads
only the seven preregistered runtime files, streams hashes without retaining
model bytes in memory, refuses redirects/revision drift, and never loads or
executes the model.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
import hashlib
import json
import os
from datetime import datetime, timezone


MODEL_ID = "Qwen/Qwen3-0.6B-Base"
REVISION = "da87bfb608c14b7cf20ba1ce41287e8de496c0cd"
LICENSE_ID = "Apache-2.0"
ROOT_LOCATOR = "artifacts/models/qwen3-0.6b-base-da87bfb"
DISK_BUDGET_BYTES = 1_610_612_736
BASE_URL = f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}"

# Values come from the official immutable revision tree.  Non-LFS files are
# checked with their Git blob SHA-1; the safetensors file is checked with the
# published LFS SHA-256.  The receipt always records a SHA-256 as well.
FILES: dict[str, tuple[int, str, str]] = {
    "config.json": (727, "43c79dcb3766612b23cbed17d0a56ce63efe4e74", "git_blob"),
    "generation_config.json": (138, "cbbb3133034e192527e5321b4c679154e4819ab8", "git_blob"),
    "merges.txt": (1_671_853, "31349551d90c7606f325fe0f11bbb8bd5fa0d7c7", "git_blob"),
    "model.safetensors": (1_192_135_096, "cd2a512003e2f9f3cd3c32a9c3573f820bb28c940f73c57b1ddaa983d9223eba", "lfs_sha256"),
    "tokenizer.json": (7_031_645, "443909a61d429dff23010e5bddd28ff530edda00", "git_blob"),
    "tokenizer_config.json": (9_678, "6a3829ee9491f36113e64df37573be81df0366f5", "git_blob"),
    "vocab.json": (2_776_833, "4783fe10ac3adce15ac8f358ef5462739852c569", "git_blob"),
}
TOTAL_BYTES = sum(size for size, _oid, _kind in FILES.values())
_BLOCK = 1 << 20
_NETWORK_TIMEOUT_SECONDS = 300
CANONICAL_ROOT = Path(__file__).resolve().parents[2] / ROOT_LOCATOR


_ALLOWED_CDN_HOSTS = {
    "cdn-lfs.huggingface.co",
    "cdn-lfs-us-1.hf.co",
    "us.aws.cdn.hf.co",
    "cas-bridge.xethub.hf.co",
}


class _BoundedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        absolute = urljoin(req.full_url, newurl)
        parsed = urlparse(absolute)
        allowed_internal = (
            parsed.hostname == "huggingface.co"
            and parsed.path.startswith(f"/api/resolve-cache/models/{MODEL_ID}/{REVISION}/")
        )
        if parsed.scheme != "https" or (parsed.hostname not in _ALLOWED_CDN_HOSTS and not allowed_internal):
            return None
        return super().redirect_request(req, fp, code, msg, headers, absolute)


_HTTP = build_opener(_BoundedRedirect())


class QwenAcquisitionError(RuntimeError):
    pass


@dataclass(frozen=True)
class FileReceipt:
    path: str
    size: int
    sha256: str
    source_oid: str
    source_kind: str


def _blob_sha1(path: Path, size: int) -> str:
    digest = hashlib.sha1(f"blob {size}\x00".encode())
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(_BLOCK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(_BLOCK), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _verify_file(path: Path, name: str) -> FileReceipt:
    if name not in FILES:
        raise QwenAcquisitionError(f"unexpected runtime file: {name}")
    expected_size, expected_oid, source_kind = FILES[name]
    if path.is_symlink() or not path.is_file():
        raise QwenAcquisitionError(f"missing runtime file: {name}")
    size, digest = _sha256(path)
    if size != expected_size:
        raise QwenAcquisitionError(f"size mismatch: {name}")
    observed_oid = digest if source_kind == "lfs_sha256" else _blob_sha1(path, size)
    if observed_oid != expected_oid:
        raise QwenAcquisitionError(f"source integrity mismatch: {name}")
    return FileReceipt(name, size, digest, expected_oid, source_kind)


def _safe_root(root: Path) -> Path:
    if root.is_symlink():
        raise QwenAcquisitionError("Qwen runtime root must not be a symlink")
    resolved = root.resolve()
    if resolved != CANONICAL_ROOT:
        raise QwenAcquisitionError("unsafe Qwen runtime root")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _assert_clean_root(root: Path) -> None:
    extras = sorted(p.name for p in root.iterdir() if p.name not in FILES)
    if extras:
        raise QwenAcquisitionError("unexpected files in Qwen runtime root: " + ",".join(extras))


def validate_authorization(payload: Mapping[str, Any]) -> None:
    if payload.get("status") != "operator_authorized":
        raise QwenAcquisitionError("Qwen download authorization is not active")
    if payload.get("model_id") != MODEL_ID or payload.get("revision") != REVISION:
        raise QwenAcquisitionError("Qwen authorization identity mismatch")
    if payload.get("license_id") != LICENSE_ID or payload.get("disk_budget_bytes") != DISK_BUDGET_BYTES:
        raise QwenAcquisitionError("Qwen authorization license or budget mismatch")
    expected_files = [
        {"path": name, "size_bytes": size, "source_oid": oid, "source_kind": kind}
        for name, (size, oid, kind) in FILES.items()
    ]
    if payload.get("runtime_files") != expected_files:
        raise QwenAcquisitionError("Qwen allowlist or source metadata mismatch")
    if payload.get("permissions") != {
        "download_runtime_files_only": True,
        "integrity_receipt": True,
        "model_load": False,
        "feasibility": False,
        "sealed_execution": False,
        "sealed_targets": False,
    }:
        raise QwenAcquisitionError("Qwen authorization boundary mismatch")


def acquire_qwen(root: Path, *, allow_download: bool, authorization: Mapping[str, Any], opener: Callable[[str], Any] | None = None) -> list[FileReceipt]:
    if not allow_download:
        raise QwenAcquisitionError("explicit --allow-download is required")
    validate_authorization(authorization)
    base = _safe_root(root)
    _assert_clean_root(base)
    existing_bytes = 0
    for name in FILES:
        path = base / name
        if path.exists():
            receipt = _verify_file(path, name)
            existing_bytes += receipt.size
    if existing_bytes > DISK_BUDGET_BYTES:
        raise QwenAcquisitionError("existing runtime exceeds disk budget")

    def fetch(url: str):
        request = Request(url, headers={"Accept-Encoding": "identity"})
        response = opener(url) if opener else _HTTP.open(request, timeout=_NETWORK_TIMEOUT_SECONDS)
        status = getattr(response, "status", 200)
        final_url = str(getattr(response, "url", url))
        final_host = urlparse(final_url).hostname
        final_internal = (
            final_host == "huggingface.co"
            and urlparse(final_url).path.startswith(f"/api/resolve-cache/models/{MODEL_ID}/{REVISION}/")
        )
        if status != 200 or (final_url != url and final_host not in _ALLOWED_CDN_HOSTS and not final_internal):
            response.close()
            raise QwenAcquisitionError(f"download failed or redirected: HTTP {status}")
        return response

    for name, (expected_size, expected_oid, source_kind) in FILES.items():
        destination = base / name
        if destination.exists():
            continue
        remaining = DISK_BUDGET_BYTES - existing_bytes
        response = fetch(f"{BASE_URL}/{name}")
        temporary = base / f".{name}.tmp"
        size = 0
        sha256 = hashlib.sha256()
        blob = hashlib.sha1(f"blob {expected_size}\x00".encode())
        try:
            with temporary.open("wb") as out:
                while True:
                    chunk = response.read(_BLOCK)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > expected_size or size > remaining:
                        raise QwenAcquisitionError(f"download budget exceeded: {name}")
                    out.write(chunk)
                    sha256.update(chunk)
                    blob.update(chunk)
            observed = sha256.hexdigest() if source_kind == "lfs_sha256" else blob.hexdigest()
            if size != expected_size or observed != expected_oid:
                raise QwenAcquisitionError(f"download integrity mismatch: {name}")
            temporary.replace(destination)
            existing_bytes += size
        except BaseException:
            if temporary.exists():
                temporary.unlink()
            raise
        finally:
            response.close()

    return [_verify_file(base / name, name) for name in FILES]


def build_receipt(root: Path, *, authorization_sha256: str, retrieved_at: str | None = None) -> dict[str, Any]:
    base = _safe_root(root)
    _assert_clean_root(base)
    files = [_verify_file(base / name, name) for name in FILES]
    total = sum(item.size for item in files)
    if total != TOTAL_BYTES or total > DISK_BUDGET_BYTES:
        raise QwenAcquisitionError("runtime total does not satisfy the frozen budget")
    return {
        "artifact_class": "exp001-comparative-qwen-integrity-receipt",
        "status": "integrity_verified",
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "model_loaded": False,
        "model_output_accessed": False,
        "sealed_targets_accessed": False,
        "model_id": MODEL_ID,
        "revision": REVISION,
        "license_id": LICENSE_ID,
        "source_url": f"https://huggingface.co/{MODEL_ID}/tree/{REVISION}",
        "runtime_root": ROOT_LOCATOR,
        "disk_budget_bytes": DISK_BUDGET_BYTES,
        "total_bytes": total,
        "authorization_sha256": authorization_sha256,
        "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
        "runtime_files": [
            {
                "path": item.path,
                "size_bytes": item.size,
                "sha256": item.sha256,
                "source_oid": item.source_oid,
                "source_kind": item.source_kind,
                "source_url": f"{BASE_URL}/{item.path}",
            }
            for item in files
        ],
    }


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise QwenAcquisitionError("refusing to overwrite immutable Qwen receipt")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.link(temporary, path)
    temporary.unlink()


__all__ = ["FILES", "TOTAL_BYTES", "MODEL_ID", "REVISION", "QwenAcquisitionError", "acquire_qwen", "build_receipt", "write_receipt", "validate_authorization"]
