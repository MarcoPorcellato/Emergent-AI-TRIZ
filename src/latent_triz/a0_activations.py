"""Exact-revision activation extraction for the frozen A0 sealed tranche."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import lab01_acquisition
from .a0_activation_sites import TOKEN_SITES, VIEW_NAMES, build_view_texts, select_token_indices
from .lab01_transformers import GPTNeoXTransformersAdapter


class A0ActivationError(RuntimeError):
    """Raised when sealed activation extraction cannot proceed safely."""


EPISTEMIC = {
    "empirical": True,
    "scientific_status": "exploratory",
    "evidence_eligible": False,
    "expert_validated": False,
    "claim_ids": [],
}


@dataclass(frozen=True)
class A0ActivationArtifacts:
    dense_path: Path
    index_path: Path
    receipt_path: Path


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0ActivationError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise A0ActivationError(f"{label} must be an object")
    return value


def _read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise A0ActivationError(f"cannot read {label}: {exc}") from exc
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise A0ActivationError(f"{label} must contain object records")
    return rows


def _require_epistemic(payload: Mapping[str, Any], label: str) -> None:
    for key, expected in EPISTEMIC.items():
        if payload.get(key) != expected:
            raise A0ActivationError(f"{label} has invalid epistemic field {key}")


def _select_records(
    cases: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    *,
    domains: list[str],
    families_per_domain: int,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    targets_by_case: dict[str, dict[str, Any]] = {}
    families: dict[str, set[str]] = defaultdict(set)
    for target in targets:
        if target.get("split") != "sealed":
            raise A0ActivationError("sealed target file contains a non-sealed record")
        case_id = str(target.get("case_id", ""))
        if not case_id or case_id in targets_by_case:
            raise A0ActivationError("sealed targets contain a missing or duplicate case_id")
        targets_by_case[case_id] = target
        family_id = str(target.get("problem_family_id", ""))
        domain = family_id.rsplit("_", 1)[0]
        families[domain].add(family_id)

    selected_families = {
        domain: set(sorted(families.get(domain, set()))[:families_per_domain])
        for domain in domains
    }
    if any(len(values) != families_per_domain for values in selected_families.values()):
        raise A0ActivationError("sealed family selection is incomplete")

    selected = [
        case
        for case in cases
        if case.get("split") == "sealed"
        and str(case.get("problem_family_id")) in selected_families.get(str(case.get("domain")), set())
    ]
    selected.sort(key=lambda row: (str(row.get("problem_family_id")), str(row.get("solution_variant_id"))))
    expected = len(domains) * families_per_domain * 2
    if len(selected) != expected:
        raise A0ActivationError(f"expected {expected} selected cases, found {len(selected)}")

    selected_targets: dict[str, dict[str, Any]] = {}
    family_counts: dict[str, int] = defaultdict(int)
    for case in selected:
        case_id = str(case.get("case_id", ""))
        target = targets_by_case.get(case_id)
        if target is None:
            raise A0ActivationError(f"missing sealed target for {case_id}")
        if case.get("case_content_sha256") != target.get("case_content_sha256"):
            raise A0ActivationError(f"case receipt mismatch for {case_id}")
        if case.get("target_content_sha256") != target.get("target_content_sha256"):
            raise A0ActivationError(f"target receipt mismatch for {case_id}")
        if case.get("problem_family_id") != target.get("problem_family_id"):
            raise A0ActivationError(f"family mismatch for {case_id}")
        family_counts[str(case.get("problem_family_id"))] += 1
        selected_targets[case_id] = target
    if any(count != 2 for count in family_counts.values()):
        raise A0ActivationError("selected families are not paired")
    return selected, selected_targets


def _token_metadata(adapter: Any, prompt: str, payload: Mapping[str, Any]) -> tuple[list[list[int]], list[bool], list[int]]:
    encoded = adapter.tokenizer(
        prompt,
        add_special_tokens=True,
        return_attention_mask=True,
        return_offsets_mapping=True,
    )
    input_ids = [int(value) for value in encoded["input_ids"]]
    payload_ids = [int(value) for value in payload.get("token_ids", [])]
    if input_ids != payload_ids:
        raise A0ActivationError("tokenizer identity drift between offset and model encodings")
    offsets = [[int(pair[0]), int(pair[1])] for pair in encoded["offset_mapping"]]
    attention = [int(value) for value in encoded["attention_mask"]]
    flags = [
        bool(value)
        for value in adapter.tokenizer.get_special_tokens_mask(
            input_ids,
            already_has_special_tokens=True,
        )
    ]
    return offsets, flags, attention


def _environment_receipt() -> dict[str, Any]:
    versions: dict[str, str] = {}
    for name in ("numpy", "safetensors", "torch", "transformers"):
        module = __import__(name)
        versions[name] = str(getattr(module, "__version__", "unknown"))
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": versions,
        "device": "cpu",
        "dtype": "float32",
        "offline": True,
    }


def run_a0_activations(
    *,
    protocol_path: str | Path,
    implementation_path: str | Path,
    freeze_path: str | Path,
    corpus_dir: str | Path,
    model_root: str | Path,
    dense_output_dir: str | Path,
    result_output_dir: str | Path,
    created_at: str,
    adapter_factory: Any = GPTNeoXTransformersAdapter,
) -> A0ActivationArtifacts:
    protocol_path = Path(protocol_path).resolve()
    implementation_path = Path(implementation_path).resolve()
    freeze_path = Path(freeze_path).resolve()
    corpus_dir = Path(corpus_dir).resolve()
    model_root = Path(model_root).resolve()
    dense_output_dir = Path(dense_output_dir).resolve()
    result_output_dir = Path(result_output_dir).resolve()

    try:
        timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise A0ActivationError("created_at must be an ISO-8601 timestamp") from exc
    if timestamp.tzinfo is None:
        raise A0ActivationError("created_at must include a timezone")
    created_at = timestamp.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for output in (dense_output_dir, result_output_dir):
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise A0ActivationError(f"refusing to overwrite output directory: {output}")

    protocol = _read_json(protocol_path, "protocol")
    implementation = _read_json(implementation_path, "implementation contract")
    freeze = _read_json(freeze_path, "freeze manifest")
    manifest_path = corpus_dir / "manifest.json"
    manifest = _read_json(manifest_path, "corpus manifest")
    _require_epistemic(protocol, "protocol")
    _require_epistemic(implementation["epistemic_boundary"], "implementation contract")
    _require_epistemic(freeze, "freeze manifest")
    _require_epistemic(manifest, "corpus manifest")

    if protocol.get("protocol_status") != "frozen" or freeze.get("status") != "frozen":
        raise A0ActivationError("protocol is not frozen")
    if implementation.get("status") != "frozen_before_model_output":
        raise A0ActivationError("implementation contract is not frozen before model output")
    if freeze.get("protocol_hash") != _sha256(protocol_path):
        raise A0ActivationError("protocol hash does not match freeze manifest")
    if freeze.get("corpus_manifest_sha256") != _sha256(manifest_path):
        raise A0ActivationError("corpus manifest hash does not match freeze manifest")

    files = manifest.get("files")
    if not isinstance(files, Mapping):
        raise A0ActivationError("corpus manifest has no file receipts")
    cases_path = corpus_dir / str(files["cases_jsonl"]["path"])
    targets_path = corpus_dir / str(files["sealed_targets_jsonl"]["path"])
    if _sha256(cases_path) != files["cases_jsonl"]["sha256"] or _sha256(cases_path) != freeze.get("cases_sha256"):
        raise A0ActivationError("case corpus receipt mismatch")
    if _sha256(targets_path) != files["sealed_targets_jsonl"]["sha256"] or _sha256(targets_path) != freeze.get("sealed_targets_sha256"):
        raise A0ActivationError("sealed target receipt mismatch")

    frozen = protocol.get("frozen_analysis")
    if not isinstance(frozen, Mapping):
        raise A0ActivationError("protocol has no frozen analysis")
    families_per_domain = int(frozen.get("selected_families_per_domain", 0))
    domains = [str(value) for value in protocol.get("neutral_domains", [])]
    cases, targets_by_case = _select_records(
        _read_jsonl(cases_path, "cases"),
        _read_jsonl(targets_path, "sealed targets"),
        domains=domains,
        families_per_domain=families_per_domain,
    )

    identity_ok, identity_errors = lab01_acquisition.verify_expected_snapshot(model_root)
    if not identity_ok:
        raise A0ActivationError(f"exact model identity failed: {identity_errors}")
    runtime_files = lab01_acquisition.runtime_receipts_to_payload(
        lab01_acquisition.build_runtime_file_receipts(model_root)
    )
    adapter = adapter_factory(
        model_root=model_root,
        local_files_only=True,
        device="cpu",
        torch_dtype="float32",
    )
    if not bool(getattr(adapter.tokenizer, "is_fast", False)):
        raise A0ActivationError("a fast tokenizer with offset mappings is required")

    try:
        import torch
        from safetensors.torch import save_file
    except Exception as exc:  # pragma: no cover
        raise A0ActivationError("torch and safetensors are required") from exc

    layers = [int(value) for value in protocol.get("preregistered_layers", [])]
    if layers != [0, 2, 4, 6]:
        raise A0ActivationError("preregistered layer contract drift")
    sentinel_text = str(implementation.get("sentinel_text", ""))
    tensor_rows: dict[str, Any] = {}
    index_rows: list[dict[str, Any]] = []

    for case in cases:
        case_id = str(case["case_id"])
        target = targets_by_case[case_id]
        views = build_view_texts(case, sentinel_text=sentinel_text)
        for view_name in VIEW_NAMES:
            prompt = views[view_name]
            payload = adapter.run_prompt(prompt=prompt, instrumented=True)
            hidden_states = payload.get("hidden_states")
            if not isinstance(hidden_states, tuple) or len(hidden_states) <= max(layers):
                raise A0ActivationError("adapter did not expose all preregistered hidden states")
            offsets, special_flags, attention = _token_metadata(adapter, prompt, payload)
            sites = select_token_indices(
                view_text=prompt,
                transformation_text=str(case["transformation"]),
                sentinel_text=sentinel_text,
                offsets=offsets,
                special_flags=special_flags,
                attention_mask=attention,
            )
            expected_sites = implementation["token_site_applicability"][view_name]
            if list(sites) != list(expected_sites):
                raise A0ActivationError(f"token-site applicability drift for {view_name}")
            for layer in layers:
                residual = hidden_states[layer]
                if not isinstance(residual, torch.Tensor) or residual.ndim != 3 or residual.shape[0] != 1:
                    raise A0ActivationError(f"invalid hidden state at layer {layer}")
                for site_name in expected_sites:
                    positions = sites[site_name]
                    vector = residual[0, list(positions), :].to(dtype=torch.float32).mean(dim=0)
                    if vector.ndim != 1 or not bool(torch.isfinite(vector).all()):
                        raise A0ActivationError("activation vector is invalid")
                    tensor_key = f"{case_id}::{view_name}::layer_{layer:02d}::{site_name}"
                    tensor_rows[tensor_key] = vector.detach().cpu().contiguous().clone()
                    raw = tensor_rows[tensor_key].numpy().tobytes(order="C")
                    vector_sha = hashlib.sha256(raw).hexdigest()
                    index_rows.append(
                        {
                            "record_id": tensor_key,
                            "case_id": case_id,
                            "problem_family_id": case["problem_family_id"],
                            "domain": case["domain"],
                            "view": view_name,
                            "layer": layer,
                            "token_site": site_name,
                            "token_indices": list(positions),
                            "vector_dim": int(vector.shape[0]),
                            "dtype": "float32",
                            "vector_sha256": vector_sha,
                            "tensor_key": tensor_key,
                            "target_record_sha256": target["target_content_sha256"],
                        }
                    )

    dense_output_dir.parent.mkdir(parents=True, exist_ok=True)
    result_output_dir.parent.mkdir(parents=True, exist_ok=True)
    dense_stage = Path(tempfile.mkdtemp(prefix=".a0-dense-", dir=dense_output_dir.parent))
    result_stage = Path(tempfile.mkdtemp(prefix=".a0-result-", dir=result_output_dir.parent))
    try:
        dense_path = dense_stage / "activations.safetensors"
        save_file(tensor_rows, dense_path)
        dense_sha = _sha256(dense_path)
        index_path = result_stage / "representations-index.jsonl"
        index_path.write_text(
            "".join(_stable_json(row) for row in index_rows),
            encoding="utf-8",
        )
        receipt = {
            "artifact_class": "a0-activation-receipt",
            **EPISTEMIC,
            "status": "pass",
            "created_at": created_at,
            "protocol": {
                "id": protocol["protocol_id"],
                "sha256": _sha256(protocol_path),
                "freeze_manifest_sha256": _sha256(freeze_path),
                "implementation_sha256": _sha256(implementation_path),
            },
            "corpus": {
                "manifest_sha256": _sha256(manifest_path),
                "cases_sha256": _sha256(cases_path),
                "sealed_targets_sha256": _sha256(targets_path),
                "sealed_targets_accessed": True,
                "selected_cases": len(cases),
                "selected_families": len(cases) // 2,
            },
            "model": {
                "id": lab01_acquisition.LAB01_MODEL_ID,
                "revision": lab01_acquisition.LAB01_MODEL_REVISION,
                "runtime_files": runtime_files,
            },
            "tokenizer": {
                "id": lab01_acquisition.LAB01_MODEL_ID,
                "revision": lab01_acquisition.LAB01_MODEL_REVISION,
                "class": adapter.tokenizer.__class__.__name__,
                "is_fast": True,
            },
            "environment": _environment_receipt(),
            "views": list(VIEW_NAMES),
            "token_sites": list(TOKEN_SITES),
            "layers": layers,
            "layer_index_semantics": implementation["layer_index_semantics"],
            "records": len(index_rows),
            "dense_vectors": {
                "locator": f"artifacts/a0/{dense_output_dir.name}/activations.safetensors",
                "sha256": dense_sha,
                "format": "safetensors",
                "bytes": dense_path.stat().st_size,
            },
            "representation_index": {
                "path": "representations-index.jsonl",
                "sha256": _sha256(index_path),
            },
        }
        receipt_path = result_stage / "activation-receipt.json"
        receipt_path.write_text(_stable_json(receipt), encoding="utf-8")
        if dense_output_dir.exists():
            dense_output_dir.rmdir()
        if result_output_dir.exists():
            result_output_dir.rmdir()
        os.replace(dense_stage, dense_output_dir)
        os.replace(result_stage, result_output_dir)
    except Exception:
        shutil.rmtree(dense_stage, ignore_errors=True)
        shutil.rmtree(result_stage, ignore_errors=True)
        raise

    return A0ActivationArtifacts(
        dense_path=dense_output_dir / "activations.safetensors",
        index_path=result_output_dir / "representations-index.jsonl",
        receipt_path=result_output_dir / "activation-receipt.json",
    )
