"""Deterministic, no-model-output activation extraction for R1 sealed cases."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .a0_activation_sites import TOKEN_SITES, VIEW_NAMES, build_view_texts, select_token_indices
from . import lab01_acquisition
from .lab01_transformers import GPTNeoXTransformersAdapter


class A0R1ActivationError(RuntimeError):
    """Raised when R1 activations cannot be produced under contract."""


EPISTEMIC = {
    "empirical": True,
    "scientific_status": "exploratory",
    "evidence_eligible": False,
    "expert_validated": False,
    "claim_ids": [],
}


@dataclass(frozen=True)
class A0R1ActivationArtifacts:
    dense_path: Path
    index_path: Path
    receipt_path: Path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_sha256(payload: Any) -> str:
    return _sha256_bytes(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

 
def _normalize_hex_sha(label: str, value: Any) -> str:
    sha256 = str(value or "").strip().lower()
    if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
        raise A0R1ActivationError(f"{label} must be a 64-char lowercase hex string")
    return sha256


def _normalize_int(value: Any, *, label: str) -> int:
    if not isinstance(value, int):
        raise A0R1ActivationError(f"{label} must be an integer")
    if value <= 0:
        raise A0R1ActivationError(f"{label} must be positive")
    return value


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R1ActivationError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise A0R1ActivationError(f"{label} must be an object: {path}")
    return value


def _read_jsonl(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise A0R1ActivationError(f"cannot read {label}: {path}") from exc
    if any(not isinstance(row, dict) for row in rows):
        raise A0R1ActivationError(f"{label} contains non-object records")
    return rows


def _require_epistemic(payload: Mapping[str, Any], label: str) -> None:
    for key, expected in EPISTEMIC.items():
        if payload.get(key) != expected:
            raise A0R1ActivationError(f"{label} epistemic contract mismatch: {key}")


def _require_no_escape(relative: str, label: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise A0R1ActivationError(f"{label} path missing")
    rel = Path(relative)
    if rel.is_absolute() or os.path.isabs(relative):
        raise A0R1ActivationError(f"{label} path is absolute: {relative!r}")
    normalized = rel.as_posix().lstrip("/")
    if normalized == ".." or normalized.startswith("../") or "/../" in f"/{normalized}/":
        raise A0R1ActivationError(f"{label} path escapes corpus root: {relative!r}")
    return rel


def _manifest_file(root: Path, manifest: Mapping[str, Any], key: str, label: str) -> tuple[Path, Mapping[str, Any]]:
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        raise A0R1ActivationError(f"{label} manifest has no files section")
    entry = files.get(key)
    if not isinstance(entry, Mapping):
        raise A0R1ActivationError(f"{label} manifest missing {key}")
    rel = _require_no_escape(str(entry.get("path", "")), f"{label}:{key}")
    path = root / rel
    if not path.is_file():
        raise A0R1ActivationError(f"{label} missing {key}: {rel}")
    return path, entry


def _require_no_overwrite(output_root: Path) -> None:
    if output_root.exists():
        raise A0R1ActivationError(f"refusing to overwrite output directory: {output_root}")


def _select_sealed_cases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    case_ids = set()
    for row in rows:
        if str(row.get("split")) != "sealed":
            continue
        case_id = str(row.get("case_id", "")).strip()
        if not case_id:
            raise A0R1ActivationError("sealed case missing case_id")
        if case_id in case_ids:
            raise A0R1ActivationError(f"duplicate sealed case_id: {case_id}")
        case_ids.add(case_id)
        selected.append(row)
    if not selected:
        raise A0R1ActivationError("no sealed cases in cases_jsonl")
    return sorted(selected, key=lambda row: str(row.get("case_id", "")))


def _normalize_tokenizer_output(
    payload: Mapping[str, Any],
    prompt: str,
    tokenizer: Any,
) -> tuple[list[int], list[list[int]], list[bool], list[int]]:
    encoded = tokenizer(
        prompt,
        add_special_tokens=True,
        return_attention_mask=True,
        return_offsets_mapping=True,
    )
    if not isinstance(encoded, Mapping):
        raise A0R1ActivationError("tokenizer did not return mapping")

    model_ids_raw = encoded.get("input_ids")
    if isinstance(model_ids_raw, list) and model_ids_raw and isinstance(model_ids_raw[0], list):
        model_ids = [int(v) for v in model_ids_raw[0]]
    elif isinstance(model_ids_raw, list):
        model_ids = [int(v) for v in model_ids_raw]
    else:
        raise A0R1ActivationError("tokenizer returned malformed input_ids")

    payload_ids = [int(v) for v in payload.get("token_ids", [])]
    if model_ids != payload_ids:
        raise A0R1ActivationError("token-id drift detected between payload and tokenizer")

    offsets = encoded.get("offset_mapping")
    if not isinstance(offsets, list):
        raise A0R1ActivationError("tokenizer offsets missing")
    normalized_offsets: list[list[int]] = []
    for pair in offsets:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise A0R1ActivationError("tokenizer offset malformed")
        normalized_offsets.append([int(pair[0]), int(pair[1])])

    attention = encoded.get("attention_mask")
    if isinstance(attention, list) and attention and isinstance(attention[0], list):
        attention = attention[0]
    if not isinstance(attention, list):
        raise A0R1ActivationError("tokenizer attention_mask malformed")
    attention = [int(value) for value in attention]

    if len(attention) != len(model_ids):
        raise A0R1ActivationError("tokenizer attention length mismatch")
    if "get_special_tokens_mask" in dir(tokenizer) and callable(tokenizer.get_special_tokens_mask):
        special = list(tokenizer.get_special_tokens_mask(model_ids, already_has_special_tokens=True))
    else:
        flags = payload.get("special_token_flags")
        if not isinstance(flags, list):
            raise A0R1ActivationError("tokenizer special flags missing")
        special = [bool(value) for value in flags]

    if len(special) != len(model_ids):
        raise A0R1ActivationError("tokenizer special flag length mismatch")
    return model_ids, normalized_offsets, [bool(flag) for flag in special], attention


def _extract_layer_tensor(tensor: Any) -> list[list[float]]:
    if hasattr(tensor, "detach"):
        try:
            tensor = tensor.detach().cpu().tolist()
        except Exception as exc:  # pragma: no cover - defensive for unsupported tensor objects
            raise A0R1ActivationError("hidden state tensor is not list-convertible") from exc

    if not isinstance(tensor, (list, tuple)) or not tensor:
        raise A0R1ActivationError("hidden state tensor is not sequence-like")

    if len(tensor) == 1 and isinstance(tensor[0], (list, tuple)):
        tensor = tensor[0]

    if not isinstance(tensor[0], (list, tuple)):
        raise A0R1ActivationError("hidden state tensor must be sequence-of-vectors")
    if not tensor[0]:
        raise A0R1ActivationError("hidden state sequence is empty")
    vectors = [list(vector) for vector in tensor]
    if not all(isinstance(value, (int, float)) for vector in vectors for value in vector):
        raise A0R1ActivationError("hidden state contains non-numeric values")

    if not vectors:
        raise A0R1ActivationError("hidden state sequence is empty")
    for vector in vectors:
        if not isinstance(vector, (list, tuple)) or not vector:
            raise A0R1ActivationError("hidden state contains non-vector items")
    return [list(float(v) for v in vector) for vector in vectors]


def _vector_finite(vector: list[float]) -> None:
    if not vector:
        raise A0R1ActivationError("activation vector is empty")
    if not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in vector):
        raise A0R1ActivationError("non-finite activation vector value")


def _mean_of_vectors(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        raise A0R1ActivationError("no vectors available")
    dimension = len(vectors[0])
    if dimension == 0:
        raise A0R1ActivationError("vector dimension is zero")
    for vector in vectors:
        if len(vector) != dimension:
            raise A0R1ActivationError("hidden-state vector dimension drift")
        _vector_finite(vector)
    acc = [0.0] * dimension
    for vector in vectors:
        for index, value in enumerate(vector):
            acc[index] += float(value)
    return [value / len(vectors) for value in acc]


def run_a0r1_activations(
    *,
    protocol_path: str | Path,
    implementation_path: str | Path,
    freeze_path: str | Path,
    corpus_dir: str | Path,
    model_root: str | Path,
    output_dir: str | Path,
    created_at: str,
    adapter_factory: Any = GPTNeoXTransformersAdapter,
) -> A0R1ActivationArtifacts:
    protocol_path = Path(protocol_path).resolve()
    implementation_path = Path(implementation_path).resolve()
    freeze_path = Path(freeze_path).resolve()
    corpus_root = Path(corpus_dir).resolve()
    model_root = Path(model_root).resolve()
    output_root = Path(output_dir).resolve()
    _require_no_overwrite(output_root)

    try:
        timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise A0R1ActivationError("created_at must be ISO-8601 UTC timestamp") from exc
    if timestamp.tzinfo is None:
        raise A0R1ActivationError("created_at must include a timezone")
    created_at = timestamp.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    protocol = _read_json(protocol_path, "protocol")
    implementation = _read_json(implementation_path, "implementation")
    freeze = _read_json(freeze_path, "freeze manifest")
    _require_epistemic(protocol, "protocol")
    _require_epistemic(implementation, "implementation")
    _require_epistemic(freeze, "freeze")

    protocol_id = str(protocol.get("protocol_id", "")).strip()
    if not protocol_id:
        raise A0R1ActivationError("protocol_id missing")
    if str(implementation.get("protocol_id", "")).strip() != protocol_id:
        raise A0R1ActivationError("implementation protocol_id mismatch")
    if str(freeze.get("protocol_id", "")).strip() != protocol_id:
        raise A0R1ActivationError("freeze protocol_id mismatch")
    if _sha256_file(protocol_path) != _normalize_hex_sha("frozen_protocol_hash", freeze.get("frozen_protocol_hash")):
        raise A0R1ActivationError("protocol hash does not match freeze manifest")
    if protocol.get("protocol_status") != "frozen" or protocol.get("status") != "frozen":
        raise A0R1ActivationError("protocol is not frozen")
    if implementation.get("status") != "frozen_before_model_output":
        raise A0R1ActivationError("implementation is not frozen_before_model_output")
    if freeze.get("protocol_status") != "frozen" or freeze.get("status") != "frozen":
        raise A0R1ActivationError("freeze manifest is not frozen")
    if freeze.get("model_output_accessed") is not False or freeze.get("sealed_model_output_accessed") is not False:
        raise A0R1ActivationError("freeze manifest declares model output access")

    primary_endpoint = protocol.get("primary_endpoint")
    if not isinstance(primary_endpoint, Mapping):
        raise A0R1ActivationError("protocol missing primary_endpoint")
    primary_layer = int(primary_endpoint.get("layer", -1))
    primary_view = str(primary_endpoint.get("primary_view", "")).strip()
    primary_site = str(primary_endpoint.get("token_site", "")).strip()
    baseline_view = str(primary_endpoint.get("surface_baseline_view", "")).strip()
    if primary_layer < 0:
        raise A0R1ActivationError("primary layer must be non-negative")
    sensitivity = protocol.get("sensitivity_endpoints")
    if not isinstance(sensitivity, Mapping):
        raise A0R1ActivationError("protocol sensitivity_endpoints missing")
    if primary_view not in [str(v) for v in sensitivity.get("views", [])]:
        raise A0R1ActivationError("primary_view not listed in protocol sensitivity views")
    if baseline_view not in [str(v) for v in sensitivity.get("views", [])]:
        raise A0R1ActivationError("surface_baseline_view not listed in protocol sensitivity views")
    if primary_site not in [str(v) for v in sensitivity.get("token_sites", [])]:
        raise A0R1ActivationError("primary token_site not listed in protocol sensitivity token_sites")
    if not isinstance(implementation.get("token_site_applicability"), Mapping):
        raise A0R1ActivationError("implementation token_site_applicability missing")

    baseline_sites = implementation["token_site_applicability"].get(baseline_view)
    primary_sites = implementation["token_site_applicability"].get(primary_view)
    if not isinstance(baseline_sites, list) or not isinstance(primary_sites, list):
        raise A0R1ActivationError("implementation missing baseline/primary token-site contract")
    if primary_site not in primary_sites:
        raise A0R1ActivationError("primary token site is not allowed by implementation")
    if not all(isinstance(site, str) and site in TOKEN_SITES for site in baseline_sites):
        raise A0R1ActivationError("invalid baseline token site")
    if not all(isinstance(site, str) and site in TOKEN_SITES for site in primary_sites):
        raise A0R1ActivationError("invalid primary token site")
    baseline_sites = ["sentinel"]
    primary_sites = [primary_site]

    corpus_manifest = _read_json(corpus_root / "manifest.json", "corpus manifest")
    if corpus_manifest.get("protocol_id") != protocol_id:
        raise A0R1ActivationError("corpus protocol_id mismatch")
    _require_epistemic(corpus_manifest, "corpus manifest")
    if _sha256_file(corpus_root / "manifest.json") != _normalize_hex_sha("corpus_manifest_hash", freeze.get("corpus_manifest_hash")):
        raise A0R1ActivationError("corpus manifest hash does not match freeze manifest")
    cases_path, cases_entry = _manifest_file(corpus_root, corpus_manifest, "cases_jsonl", "corpus")
    if str(cases_entry.get("split", "")) and cases_entry.get("split") != "sealed":
        raise A0R1ActivationError("cases manifest indicates non-sealed split")
    _, sealed_targets_entry = _manifest_file(corpus_root, corpus_manifest, "sealed_targets_jsonl", "corpus")
    for filename in ("calibration_targets_jsonl", "sealed_targets_jsonl"):
        rel_entry = corpus_manifest["files"].get(filename)
        if not isinstance(rel_entry, Mapping):
            raise A0R1ActivationError(f"corpus manifest missing {filename}")
        if not rel_entry.get("sha256") or not rel_entry.get("size"):
            raise A0R1ActivationError(f"{filename} metadata missing in corpus manifest")

    if _sha256_file(cases_path) != _normalize_hex_sha("corpus cases hash", cases_entry.get("sha256")):
        raise A0R1ActivationError("cases file hash mismatch")
    if _normalize_int(int(cases_entry.get("size", 0)), label="cases file size") != cases_path.stat().st_size:
        raise A0R1ActivationError("cases file size mismatch")
    if _sha256_file(cases_path) != _normalize_hex_sha("freeze cases hash", freeze.get("cases_sha256")):
        raise A0R1ActivationError("freeze manifest cases hash mismatch")
    if _normalize_hex_sha("freeze sealed targets hash", freeze.get("sealed_targets_sha256")) != _normalize_hex_sha(
        "sealed targets hash",
        sealed_targets_entry.get("sha256"),
    ):
        raise A0R1ActivationError("sealed targets hash mismatch")

    cases = _select_sealed_cases(_read_jsonl(cases_path, "cases_jsonl"))
    for case in cases:
        for key in ("case_id", "problem", "constraints", "initial_state", "desired_improvement", "worsening_consequence", "transformation"):
            if str(case.get(key, "")).strip() == "":
                raise A0R1ActivationError(f"sealed case missing {key}: {case.get('case_id')}")
        if not isinstance(case.get("constraints"), list) or not case.get("constraints"):
            raise A0R1ActivationError(f"sealed case constraints missing: {case.get('case_id')}")
    if not all("solution" in row for row in cases):
        raise A0R1ActivationError("sealed case missing solution")

    expected_snapshot_ok, snapshot_issues = lab01_acquisition.verify_expected_snapshot(model_root)
    if not expected_snapshot_ok:
        raise A0R1ActivationError("runtime snapshot verification failed: " + "; ".join(snapshot_issues))

    model_runtime = lab01_acquisition.build_runtime_file_receipts(model_root)
    runtime_payload = sorted(
        [
            {"name": value.name, "sha256": value.sha256, "size": value.size}
            for value in model_runtime.values()
        ],
        key=lambda item: item["name"],
    )
    runtime_binding_hash = _canonical_json_sha256(runtime_payload)
    runtime_contract = implementation.get("runtime")
    if not isinstance(runtime_contract, Mapping):
        raise A0R1ActivationError("implementation runtime contract missing")
    contract_items = runtime_contract.get("model_runtime_hashes")
    if not isinstance(contract_items, list) or not contract_items:
        raise A0R1ActivationError("implementation runtime model_runtime_hashes missing")
    expected_runtime_payload = sorted(
        [
            {
                "name": Path(str(item.get("path", ""))).name,
                "sha256": _normalize_hex_sha("runtime hash", item.get("sha256")),
                "size": _normalize_int(int(item.get("size", 0)), label="runtime size"),
            }
            for item in contract_items
            if isinstance(item, Mapping) and str(item.get("path", "")).strip()
        ],
        key=lambda item: item["name"],
    )
    if len(expected_runtime_payload) != len(runtime_payload):
        raise A0R1ActivationError("runtime contract size mismatch")
    if runtime_payload != expected_runtime_payload:
        raise A0R1ActivationError("runtime files do not match implementation contract")

    adapter = adapter_factory(
        model_root=model_root,
        local_files_only=True,
        device="cpu",
        torch_dtype="float32",
    )
    tokenizer = getattr(adapter, "tokenizer", None)
    if tokenizer is None:
        raise A0R1ActivationError("adapter has no tokenizer")
    if not bool(getattr(tokenizer, "is_fast", False)):
        raise A0R1ActivationError("fast tokenizer required")

    sentinel_text = str(implementation.get("sentinel_text", "")).strip()
    if not sentinel_text:
        raise A0R1ActivationError("implementation missing sentinel_text")
    layer = primary_endpoint.get("layer")
    if not isinstance(layer, int):
        raise A0R1ActivationError("primary layer must be integer")

    index_rows: list[dict[str, Any]] = []
    dense_rows: dict[str, list[float]] = {}

    for case in cases:
        case_id = str(case["case_id"]).strip()
        case_views = build_view_texts(case, sentinel_text=sentinel_text)
        views_to_run = (baseline_view, primary_view)
        expected_sites = {
            baseline_view: baseline_sites,
            primary_view: primary_sites,
        }

        for view in views_to_run:
            view_name = str(view)
            prompt = str(case_views[view_name])
            prompt_output = adapter.run_prompt(prompt=prompt, instrumented=True)
            if not isinstance(prompt_output, Mapping):
                raise A0R1ActivationError("adapter run_prompt must return mapping")

            _, offsets, special, attention = _normalize_tokenizer_output(prompt_output, prompt, tokenizer)
            token_indices_map = select_token_indices(
                view_text=prompt,
                transformation_text=str(case["transformation"]),
                sentinel_text=sentinel_text,
                offsets=offsets,
                special_flags=special,
                attention_mask=attention,
            )
            hidden_states = prompt_output.get("hidden_states")
            if not isinstance(hidden_states, (list, tuple)):
                raise A0R1ActivationError("adapter missing hidden_states")
            if layer >= len(hidden_states):
                raise A0R1ActivationError(f"hidden_states missing layer {layer}")
            layer_tensor = _extract_layer_tensor(hidden_states[layer])

            for site in expected_sites[view_name]:
                selected = token_indices_map.get(site)
                if not selected:
                    raise A0R1ActivationError(f"site {site} missing for {case_id}/{view_name}")
                try:
                    selected_vectors = [layer_tensor[int(index)] for index in selected]
                except IndexError as exc:
                    raise A0R1ActivationError("token index out of range") from exc
                if len(selected_vectors) != len(selected):
                    raise A0R1ActivationError("token index out of range")
                avg = _mean_of_vectors(selected_vectors)
                record_id = f"{case_id}::{view_name}::{site}::{primary_layer}"
                dense_rows[record_id] = avg
                index_rows.append(
                    {
                        "record_id": record_id,
                        "case_id": case_id,
                        "problem_family_id": str(case.get("problem_family_id", "")),
                        "domain": str(case.get("domain", "")),
                        "view": view_name,
                        "layer": primary_layer,
                        "token_site": site,
                        "token_indices": list(selected),
                        "vector_dim": len(avg),
                        "dtype": "float32",
                        "vector_sha256": _canonical_json_sha256(avg),
                        "token_count": len(selected),
                    }
                )

    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(output_root.parent)) as temp_root:
        staging = Path(temp_root) / output_root.name
        staging.mkdir(parents=True)

        dense_path = staging / "activations.json"
        index_path = staging / "representations-index.jsonl"
        receipt_path = staging / "activation-receipt.json"

        payload = json.dumps(
            {record_id: dense_rows[record_id] for record_id in sorted(dense_rows)},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ) + "\n"
        dense_path.write_text(payload, encoding="utf-8")
        index_payload = "".join(
            json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in index_rows
        )
        index_path.write_text(index_payload, encoding="utf-8")

        dense_hash = _sha256_file(dense_path)
        index_hash = _sha256_file(index_path)

        receipt = {
            "artifact_class": "a0r1-activation-receipt",
            **EPISTEMIC,
            "status": "pass",
            "created_at": created_at,
            "protocol": {
                "id": protocol_id,
                "protocol_status": protocol.get("protocol_status"),
                "hash": _sha256_file(protocol_path),
                "snapshot_hash": _canonical_json_sha256(protocol),
            },
            "implementation": {
                "protocol_status": implementation.get("protocol_status"),
                "status": implementation.get("status"),
                "hash": _sha256_file(implementation_path),
            },
            "freeze": {
                "protocol_status": freeze.get("protocol_status"),
                "status": freeze.get("status"),
                "protocol_id": protocol_id,
                "hash": _sha256_file(freeze_path),
            },
            "corpus": {
                "manifest_sha256": _sha256_file(corpus_root / "manifest.json"),
                "cases_sha256": _sha256_file(cases_path),
                "sealed_targets_sha256": sealed_targets_entry.get("sha256"),
                "sealed_targets_accessed": False,
                "selected_cases": len(cases),
            },
            "runtime": {
                "model": lab01_acquisition.LAB01_MODEL_ID,
                "revision": lab01_acquisition.LAB01_MODEL_REVISION,
                "files": runtime_payload,
                "binding_hash": runtime_binding_hash,
            },
            "primary_contract": {
                "primary_view": primary_view,
                "primary_token_site": primary_site,
                "primary_layer": primary_layer,
                "baseline_view": baseline_view,
                "baseline_token_sites": baseline_sites,
                "multiplicity": int(primary_endpoint.get("multiplicity", 1)),
            },
            "sealed_target_semantics_accessed": False,
            "model_output_accessed": True,
            "sealed_model_output_accessed": True,
            "records": len(index_rows),
            "dense_vectors": {
                "path": dense_path.name,
                "sha256": dense_hash,
                "format": "json-vectors",
                "bytes": dense_path.stat().st_size,
            },
            "representation_index": {
                "path": index_path.name,
                "sha256": index_hash,
            },
        }
        receipt_path.write_text(
            json.dumps(receipt, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

        staging.replace(output_root)

    return A0R1ActivationArtifacts(
        dense_path=output_root / "activations.json",
        index_path=output_root / "representations-index.jsonl",
        receipt_path=output_root / "activation-receipt.json",
    )
