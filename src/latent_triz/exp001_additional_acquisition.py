"""Fail-closed acquisition of the two additional EXP-001 model snapshots.

This module is download-only.  It never imports torch/transformers, never
loads a model, and streams SHA-256 digests while writing one allowlisted file
at a time.  The authorization dossier must explicitly be ``authorized``;
``approval_requested`` is intentionally refused.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


_BLOCK = 1 << 20
_TIMEOUT_SECONDS = 300
_ALLOWED_CDN_HOSTS = frozenset({
    "cdn-lfs.huggingface.co",
    "cdn-lfs-us-1.hf.co",
    "us.aws.cdn.hf.co",
    "cas-bridge.xethub.hf.co",
})


class AdditionalAcquisitionError(RuntimeError):
    """Raised when an additional-model acquisition cannot proceed safely."""


@dataclass(frozen=True)
class AdditionalModelSpec:
    model_id: str
    revision: str
    license_id: str
    root_locator: str
    disk_budget_bytes: int
    files: tuple[tuple[str, int], ...]

    @property
    def total_declared_bytes(self) -> int:
        return sum(size for _name, size in self.files)


MODEL_SPECS: dict[str, AdditionalModelSpec] = {
    "openai-community/gpt2": AdditionalModelSpec(
        model_id="openai-community/gpt2",
        revision="607a30d783dfa663caf39e06633721c8d4cfcd7e",
        license_id="MIT",
        root_locator="artifacts/models/gpt2-607a30d7",
        disk_budget_bytes=1_073_741_824,
        files=(
            ("config.json", 665),
            ("generation_config.json", 124),
            ("merges.txt", 456_318),
            ("model.safetensors", 548_105_171),
            ("tokenizer.json", 1_355_256),
            ("tokenizer_config.json", 26),
            ("vocab.json", 1_042_301),
        ),
    ),
    "HuggingFaceTB/SmolLM2-135M": AdditionalModelSpec(
        model_id="HuggingFaceTB/SmolLM2-135M",
        revision="93efa2f097d58c2a74874c7e644dbc9b0cee75a2",
        license_id="Apache-2.0",
        root_locator="artifacts/models/smollm2-135m-93efa2f0",
        disk_budget_bytes=1_073_741_824,
        files=(
            ("config.json", 704),
            ("generation_config.json", 111),
            ("merges.txt", 466_391),
            ("model.safetensors", 269_060_552),
            ("special_tokens_map.json", 831),
            ("tokenizer.json", 2_104_556),
            ("tokenizer_config.json", 3_658),
            ("vocab.json", 800_662),
        ),
    ),
    "EleutherAI/gpt-neo-125m": AdditionalModelSpec(
        model_id="EleutherAI/gpt-neo-125m",
        revision="21def0189f5705e2521767faed922f1f15e7d7db",
        license_id="MIT",
        root_locator="artifacts/models/gpt-neo-125m-21def018",
        disk_budget_bytes=1_073_741_824,
        files=(
            ("config.json", 1007),
            ("generation_config.json", 119),
            ("merges.txt", 456318),
            ("model.safetensors", 525979192),
            ("special_tokens_map.json", 357),
            ("tokenizer.json", 2107652),
            ("tokenizer_config.json", 727),
            ("vocab.json", 898669),
        ),
    ),
    "Qwen/Qwen2.5-0.5B": AdditionalModelSpec(
        model_id="Qwen/Qwen2.5-0.5B",
        revision="060db6499f32faf8b98477b0a26969ef7d8b9987",
        license_id="Apache-2.0",
        root_locator="artifacts/models/qwen2.5-0.5b-060db649",
        disk_budget_bytes=1_610_612_736,
        files=(
            ("config.json", 681),
            ("generation_config.json", 138),
            ("merges.txt", 1671839),
            ("model.safetensors", 988097824),
            ("tokenizer.json", 7031645),
            ("tokenizer_config.json", 7228),
            ("vocab.json", 2776833),
        ),
    ),
}


class _BoundedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        absolute = urljoin(req.full_url, newurl)
        parsed = urlparse(absolute)
        request_headers = {str(key).lower(): str(value) for key, value in req.headers.items()}
        model_id = request_headers.get("x-latent-triz-model", "")
        revision = request_headers.get("x-latent-triz-revision", "")
        internal = (
            parsed.hostname == "huggingface.co"
            and parsed.path.startswith(f"/api/resolve-cache/models/{model_id}/{revision}/")
        )
        if parsed.scheme != "https" or (parsed.hostname not in _ALLOWED_CDN_HOSTS and not internal):
            return None
        return super().redirect_request(req, fp, code, msg, headers, absolute)


_HTTP = build_opener(_BoundedRedirect())


def _sha256(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(_BLOCK), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _spec(model_id: str) -> AdditionalModelSpec:
    try:
        return MODEL_SPECS[model_id]
    except KeyError as exc:
        raise AdditionalAcquisitionError("model is not in the frozen additional selection") from exc


def _safe_root(root: Path, spec: AdditionalModelSpec, repository_root: Path | None = None) -> Path:
    if root.is_symlink():
        raise AdditionalAcquisitionError("runtime root must not be a symlink")
    resolved = root.resolve()
    anchor = repository_root if repository_root is not None else Path(__file__).resolve().parents[2]
    expected = (anchor / spec.root_locator).resolve()
    if resolved != expected:
        raise AdditionalAcquisitionError("runtime root does not match the frozen locator")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _assert_clean_root(root: Path, spec: AdditionalModelSpec) -> None:
    allowed = {name for name, _size in spec.files}
    extras = sorted(item.name for item in root.iterdir() if item.name not in allowed)
    if extras:
        raise AdditionalAcquisitionError("unexpected files in runtime root: " + ",".join(extras))


def _candidate_payload(authorization: Mapping[str, Any], model_id: str) -> Mapping[str, Any]:
    candidates = authorization.get("candidates")
    if not isinstance(candidates, list):
        raise AdditionalAcquisitionError("authorization candidates are missing")
    for candidate in candidates:
        if isinstance(candidate, Mapping) and candidate.get("model_id") == model_id:
            return candidate
    raise AdditionalAcquisitionError("authorization does not bind this model")


def validate_authorization(authorization: Mapping[str, Any], model_id: str) -> AdditionalModelSpec:
    spec = _spec(model_id)
    if authorization.get("status") != "authorized":
        raise AdditionalAcquisitionError("additional-model authorization is not active")
    candidate = _candidate_payload(authorization, model_id)
    expected_files = [{"path": name, "size_bytes": size} for name, size in spec.files]
    if candidate.get("revision") != spec.revision or candidate.get("license_id") != spec.license_id:
        raise AdditionalAcquisitionError("authorization identity or license mismatch")
    if candidate.get("runtime_root") != spec.root_locator or candidate.get("disk_budget_bytes") != spec.disk_budget_bytes:
        raise AdditionalAcquisitionError("authorization root or budget mismatch")
    runtime_files = candidate.get("runtime_files")
    if not isinstance(runtime_files, list):
        raise AdditionalAcquisitionError("authorization runtime file list is missing")
    normalized_files = [
        {"path": item.get("path"), "size_bytes": item.get("size_bytes")}
        for item in runtime_files
        if isinstance(item, Mapping)
    ]
    if normalized_files != expected_files or len(normalized_files) != len(runtime_files):
        raise AdditionalAcquisitionError("authorization allowlist or declared sizes mismatch")
    permissions = candidate.get("permissions")
    if (
        not isinstance(permissions, Mapping)
        or (permissions.get("download_runtime_files_only") is not True and permissions.get("download") is not True)
        or permissions.get("integrity_receipt") is not True
    ):
        raise AdditionalAcquisitionError("authorization boundary mismatch")
    if spec.total_declared_bytes > spec.disk_budget_bytes:
        raise AdditionalAcquisitionError("frozen declared files exceed the disk budget")
    return spec


def _fetch(spec: AdditionalModelSpec, name: str, opener: Callable[..., Any] | None) -> Any:
    url = f"https://huggingface.co/{spec.model_id}/resolve/{spec.revision}/{name}"
    request = Request(
        url,
        headers={
            "Accept-Encoding": "identity",
            "X-Latent-Triz-Model": spec.model_id,
            "X-Latent-Triz-Revision": spec.revision,
        },
    )
    response = opener(request, timeout=_TIMEOUT_SECONDS) if opener else _HTTP.open(request, timeout=_TIMEOUT_SECONDS)
    status = getattr(response, "status", 200)
    final_url = str(getattr(response, "url", url))
    parsed_final = urlparse(final_url)
    internal = (
        parsed_final.hostname == "huggingface.co"
        and parsed_final.path.startswith(f"/api/resolve-cache/models/{spec.model_id}/{spec.revision}/")
    )
    if status != 200 or (final_url != url and parsed_final.hostname not in _ALLOWED_CDN_HOSTS and not internal):
        response.close()
        raise AdditionalAcquisitionError(f"download failed or unsafe redirect for {name}")
    return response


def acquire_additional(
    model_id: str,
    root: Path,
    *,
    authorization: Mapping[str, Any],
    allow_download: bool,
    opener: Callable[..., Any] | None = None,
    repository_root: Path | None = None,
) -> None:
    if not allow_download:
        raise AdditionalAcquisitionError("explicit --allow-download is required")
    spec = validate_authorization(authorization, model_id)
    base = _safe_root(root, spec, repository_root)
    _assert_clean_root(base, spec)
    existing = 0
    for name, expected_size in spec.files:
        path = base / name
        if path.exists():
            if path.is_symlink() or not path.is_file():
                raise AdditionalAcquisitionError(f"invalid existing runtime file: {name}")
            observed_size, _digest = _sha256(path)
            if observed_size != expected_size:
                raise AdditionalAcquisitionError(f"existing size mismatch: {name}")
            existing += observed_size
    if existing > spec.disk_budget_bytes:
        raise AdditionalAcquisitionError("existing files exceed disk budget")
    for name, expected_size in spec.files:
        destination = base / name
        if destination.exists():
            continue
        remaining = spec.disk_budget_bytes - existing
        response = _fetch(spec, name, opener)
        temporary = base / f".{name}.tmp"
        size = 0
        digest = hashlib.sha256()
        try:
            with temporary.open("wb") as output:
                while True:
                    chunk = response.read(_BLOCK)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > expected_size or size > remaining:
                        raise AdditionalAcquisitionError(f"download budget exceeded: {name}")
                    output.write(chunk)
                    digest.update(chunk)
            if size != expected_size:
                raise AdditionalAcquisitionError(f"download size mismatch: {name}")
            temporary.replace(destination)
            existing += size
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        finally:
            response.close()


def build_receipt_from_authorized(
    model_id: str,
    root: Path,
    *,
    authorization: Mapping[str, Any],
    authorization_sha256: str,
    retrieved_at: str | None = None,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    spec = validate_authorization(authorization, model_id)
    base = _safe_root(root, spec, repository_root)
    _assert_clean_root(base, spec)
    files = []
    for name, expected_size in spec.files:
        path = base / name
        if path.is_symlink() or not path.is_file():
            raise AdditionalAcquisitionError(f"missing runtime file: {name}")
        size, digest = _sha256(path)
        if size != expected_size:
            raise AdditionalAcquisitionError(f"runtime size mismatch: {name}")
        files.append({"path": name, "size_bytes": size, "sha256": digest})
    total = sum(item["size_bytes"] for item in files)
    if total != spec.total_declared_bytes or total > spec.disk_budget_bytes:
        raise AdditionalAcquisitionError("runtime total does not satisfy frozen budget")
    return {
        "artifact_class": "exp001-additional-model-integrity-receipt",
        "status": "integrity_verified",
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "model_id": model_id,
        "revision": spec.revision,
        "license_id": spec.license_id,
        "runtime_root": spec.root_locator,
        "disk_budget_bytes": spec.disk_budget_bytes,
        "total_bytes": total,
        "model_loaded": False,
        "model_output_accessed": False,
        "sealed_targets_accessed": False,
        "authorization_sha256": authorization_sha256,
        "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(),
        "runtime_files": files,
    }


def write_receipt(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        raise AdditionalAcquisitionError("refusing to overwrite immutable receipt")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.link(temporary, path)
    temporary.unlink()


__all__ = [
    "AdditionalAcquisitionError",
    "AdditionalModelSpec",
    "MODEL_SPECS",
    "acquire_additional",
    "build_receipt_from_authorized",
    "validate_authorization",
    "write_receipt",
]
