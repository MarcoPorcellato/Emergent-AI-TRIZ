from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import os

from . import lab01_acquisition
from .lab01_transformers import GPTNeoXTransformersAdapter


class RepresentationExtractorError(RuntimeError):
    """Raised when model-backed extraction cannot proceed safely."""


@dataclass(frozen=True)
class RunArtifacts:
    index_path: Path
    summary_path: Path
    tensors_path: Path


REPR_EXTRACTOR_CONFIG_VERSION = "v1"
SUPPORTED_ACTIVATION_SITE = "resid_post"
SUPPORTED_TOKEN_POLICY = "last_non_special_token"

DEFAULT_TEMPLATE = """Problem:\n{problem}\n\nConstraints:\n{constraints}\n\nInitial state:\n{initial_state}\n\nDesired improvement:\n{desired_improvement}\n\nWorsening consequence:\n{worsening_consequence}\n\nTransformation:\n{transformation}\n\nResulting state:\n{resulting_state}\n\n{solution_line}"""


CASE_REQUIRED_FIELDS = {
    "case_id",
    "domain",
    "problem",
    "constraints",
    "initial_state",
    "desired_improvement",
    "worsening_consequence",
    "transformation",
    "resulting_state",
    "provenance",
    "labels",
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _stable_dump(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n"


def _read_json(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:  # pragma: no cover
            raise ValueError(f"invalid JSONL in {path}:{line_no}: {exc}") from None
        if not isinstance(item, dict):
            raise ValueError(f"invalid case record in {path}:{line_no}")
        lines.append(item)
    if not lines:
        raise ValueError(f"no records in {path}")
    return lines


def _ensure_output_dir_clean(output_root: Path) -> None:
    output_root = output_root.resolve()
    if output_root.exists():
        if not output_root.is_dir():
            raise RepresentationExtractorError(f"output path is not a directory: {output_root}")
        if any(output_root.iterdir()):
            raise RepresentationExtractorError(f"refusing to overwrite non-empty output directory: {output_root}")


def _parse_utc_timestamp(value: Any) -> str:
    try:
        from datetime import datetime, timezone

        if not isinstance(value, str) or not value.strip():
            raise ValueError("run_timestamp_utc must be a non-empty string")
        normalized = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            raise ValueError("run_timestamp_utc must include timezone")
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception as exc:
        raise RepresentationExtractorError(f"invalid run_timestamp_utc: {value}") from exc


def _build_tokenizer_receipt(adapter: Any, model_root: Path) -> dict[str, str]:
    tokenizer = getattr(adapter, "tokenizer", None)
    if tokenizer is None:
        raise RepresentationExtractorError("adapter must expose tokenizer")

    token_paths = [
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
    ]
    files: dict[str, str] = {}
    for name in token_paths:
        file_path = model_root / name
        files[name] = _sha256_path(file_path) if file_path.is_file() else ""

    # Transformers exposes the local snapshot path through name_or_path. Public
    # receipts must identify the tokenizer without leaking machine-local paths.
    public_name = lab01_acquisition.LAB01_MODEL_ID
    fingerprint_data = {
        "class": tokenizer.__class__.__name__,
        "name_or_path": public_name,
        "files": files,
    }
    return {
        "tokenizer_class": str(tokenizer.__class__.__name__),
        "name_or_path": public_name,
        "fingerprint": _sha256_text(json.dumps(fingerprint_data, sort_keys=True, separators=(",", ":"))),
        "files": files,
    }


def _required_case_fields(case: Mapping[str, Any]) -> None:
    missing = sorted(CASE_REQUIRED_FIELDS - case.keys())
    if missing:
        raise RepresentationExtractorError(f"case record missing required fields: {missing}")


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    raise RepresentationExtractorError("constraints must be a JSON array")


def _normalize_constraints(case: Mapping[str, Any]) -> str:
    items = _as_list(case.get("constraints", []))
    if not items:
        raise RepresentationExtractorError("constraints must be a non-empty list")
    return "; ".join(str(item).strip() for item in items if str(item).strip())


def _canonical_prompt(case: Mapping[str, Any], template: str = DEFAULT_TEMPLATE) -> str:
    solution = case.get("solution")
    if solution:
        solution_line = f"Solution:\n{solution}"
    else:
        solution_line = ""

    values = {
        "problem": str(case.get("problem", "")),
        "constraints": _normalize_constraints(case),
        "initial_state": str(case.get("initial_state", "")),
        "desired_improvement": str(case.get("desired_improvement", "")),
        "worsening_consequence": str(case.get("worsening_consequence", "")),
        "transformation": str(case.get("transformation", "")),
        "resulting_state": str(case.get("resulting_state", "")),
        "solution_line": solution_line,
    }

    try:
        prompt = template.format(**values)
    except KeyError as exc:
        raise RepresentationExtractorError(f"template missing token: {exc}") from exc
    return prompt.strip("\n")


def _select_last_attended_non_special_token(payload: Mapping[str, Any]) -> int:
    token_inputs = payload.get("token_inputs")
    if not isinstance(token_inputs, list) or not token_inputs:
        raise RepresentationExtractorError("adapter payload missing token_inputs")

    attention_mask = payload.get("attention_mask")
    if not isinstance(attention_mask, list) or not attention_mask:
        raise RepresentationExtractorError("adapter payload missing attention_mask")

    mask_row = attention_mask[0]
    if not isinstance(mask_row, list):
        raise RepresentationExtractorError("invalid attention_mask shape")

    if len(mask_row) != len(token_inputs):
        raise RepresentationExtractorError("attention_mask and token_inputs length mismatch")

    for index in range(len(token_inputs) - 1, -1, -1):
        if int(mask_row[index]) != 1:
            continue
        entry = token_inputs[index]
        if not isinstance(entry, Mapping):
            continue
        if bool(entry.get("is_special", False)):
            continue
        return index

    raise RepresentationExtractorError("no attended non-special token found")


def _collect_residual_layers(payload: Mapping[str, Any]) -> dict[int, Any]:
    residuals: dict[int, Any] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        if not key.startswith("resid_post_layer_"):
            continue
        suffix = key.removeprefix("resid_post_layer_")
        # Lab 01 also publishes derived keys such as
        # resid_post_layer_0_topk; only exact residual tensors belong here.
        if not suffix.isdigit():
            continue
        layer_id = int(suffix)
        residuals[layer_id] = value
    if not residuals:
        raise RepresentationExtractorError("adapter payload contains no resid_post_layer_* tensors")
    return residuals


def _tensor_payload_hash(tensor: Any) -> tuple[str, dict[str, Any], bytes]:
    try:
        import torch
    except Exception as exc:  # pragma: no cover
        raise RepresentationExtractorError("torch is required to extract model activations") from exc

    if not hasattr(tensor, "detach"):
        raise RepresentationExtractorError("residual tensor does not support torch tensor protocol")
    t = tensor.detach().to(dtype=torch.float32).cpu().contiguous()
    if t.dim() != 1:
        raise RepresentationExtractorError("selected representation must be one-dimensional")
    if not bool(torch.isfinite(t).all()):
        raise RepresentationExtractorError("residual vector contains non-finite values")

    np_arr = t.numpy()
    shape = list(np_arr.shape)
    dtype_name = str(np_arr.dtype)
    byteorder = np_arr.dtype.byteorder or "little"
    if byteorder not in ("<", "|"):
        np_arr = np_arr.astype(np_arr.dtype.newbyteorder("<"), copy=False)
        byteorder = "<"
    payload = np_arr.tobytes(order="C")
    metadata = json.dumps(
        {
            "dtype": dtype_name,
            "shape": shape,
            "byte_order": byteorder,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = _sha256_bytes(metadata + b"|" + payload)
    return (
        digest,
        {
            "dtype": dtype_name,
            "shape": shape,
            "byte_order": byteorder or "little",
        },
        payload,
    )


def _run_with_adapter(
    *,
    cases_path: Path,
    model_root: Path,
    output_root: Path,
    created_at: str,
    prompt_template: str,
    token_policy: str,
    activation_site: str,
    adapter_factory: type[GPTNeoXTransformersAdapter] | Any = GPTNeoXTransformersAdapter,
    identity_verifier: Any = lab01_acquisition.verify_expected_snapshot,
) -> tuple[Path, Path, Path]:
    if token_policy != SUPPORTED_TOKEN_POLICY:
        raise RepresentationExtractorError(f"unsupported token policy: {token_policy}")
    if activation_site != SUPPORTED_ACTIVATION_SITE:
        raise RepresentationExtractorError(f"unsupported activation_site: {activation_site}")

    output_root = output_root.resolve()
    _ensure_output_dir_clean(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    tensors_path = output_root / "activations.safetensors"
    index_path = output_root / "representations-index.jsonl"
    summary_path = output_root / "summary.json"

    model_root = model_root.resolve()
    if not model_root.is_dir():
        raise RepresentationExtractorError(f"model root not found: {model_root}")
    if (os.getenv("HF_HUB_OFFLINE") in {"0", "false", "False", "FALSE"}) or (
        os.getenv("TRANSFORMERS_OFFLINE") in {"0", "false", "False", "FALSE"}
    ):
        raise RepresentationExtractorError("offline mode explicitly disabled")

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    if not (model_root / "config.json").is_file():
        raise RepresentationExtractorError(f"model config not found: {model_root / 'config.json'}")

    identity_match, errors = identity_verifier(model_root)
    if not identity_match:
        raise RepresentationExtractorError(f"model identity mismatch: {errors}")

    try:
        adapter = adapter_factory(
            model_root=model_root,
            local_files_only=True,
            device="cpu",
            torch_dtype="float32",
        )
    except Exception as exc:  # pragma: no cover
        raise RepresentationExtractorError(f"failed to initialize lab01 adapter: {exc}") from exc

    tokenizer_receipt = _build_tokenizer_receipt(adapter, model_root)

    cases = _read_jsonl(cases_path)
    cases_sha256 = _sha256_path(cases_path)
    try:
        import safetensors.torch
        import torch
        from safetensors.torch import save_file
    except Exception as exc:  # pragma: no cover
        raise RepresentationExtractorError("safetensors dependency is required") from exc

    safe_tensor_rows: dict[str, Any] = {}
    index_rows: list[dict[str, Any]] = []
    prompt_records: list[dict[str, Any]] = []

    prompt_template_hash = _sha256_text(prompt_template)

    for case in cases:
        _required_case_fields(case)
        case_id = str(case.get("case_id"))
        if not case_id:
            raise RepresentationExtractorError("case_id must be non-empty")

        rendered_prompt = _canonical_prompt(case, template=prompt_template)
        prompt_hash = _sha256_text(rendered_prompt)
        payload = adapter.run_prompt(prompt=rendered_prompt, instrumented=True)

        token_index = _select_last_attended_non_special_token(payload)
        residuals = _collect_residual_layers(payload)

        prompt_records.append(
            {
                "case_id": case_id,
                "prompt_hash": prompt_hash,
                "rendered_prompt": rendered_prompt,
            }
        )

        for layer_index in sorted(residuals):
            residual = residuals[layer_index]
            if not hasattr(residual, "size"):
                raise RepresentationExtractorError(f"residual for layer {layer_index} is not a tensor")

            expected_shape = residual.shape
            if not isinstance(expected_shape, torch.Size) or len(expected_shape) != 3:
                raise RepresentationExtractorError(f"invalid residual shape for layer {layer_index}: {expected_shape}")
            if expected_shape[0] != 1:
                raise RepresentationExtractorError(f"unsupported batch dimension for layer {layer_index}")
            if token_index >= int(expected_shape[1]):
                raise RepresentationExtractorError(
                    f"selected token index {token_index} exceeds prompt length {expected_shape[1]}"
                )

            vector = residual[:, token_index, :]
            vector = vector.reshape(-1)
            digest, tensor_metadata, _ = _tensor_payload_hash(vector)

            tensor_key = f"{case_id}::layer_{layer_index:04d}"
            record_id = f"{tensor_key}"
            # Each key must own its storage. Safetensors rejects aliases because
            # reloading them cannot preserve shared-memory semantics reliably.
            safe_tensor_rows[tensor_key] = vector.detach().cpu().to(torch.float32).contiguous().clone()

            index_rows.append(
                {
                    "record_id": record_id,
                    "case_id": case_id,
                    "layer_index": layer_index,
                    "representation_type": "model_activation",
                    "vector_dim": int(vector.shape[-1]),
                    "source": {
                        "kind": "instrumented_model_run",
                        "path": tensors_path.name,
                    },
                    "artifact_uri": str(tensors_path.name),
                    "artifact_sha256": "",
                    "tensor_key": tensor_key,
                    "dtype": tensor_metadata["dtype"],
                    "shape": tensor_metadata["shape"],
                    "byte_order": tensor_metadata["byte_order"],
                    "activation_site": activation_site,
                    "token_policy": token_policy,
                    "token_index": token_index,
                    "prompt_hash": prompt_hash,
                    "prompt_template_hash": prompt_template_hash,
                    "vector_sha256": digest,
                    "tokenizer": tokenizer_receipt,
                    "artifact_class": "model-activation-vector",
                    "non_claim_boundary": {
                        "empirical": True,
                        "evidence_eligible": False,
                        "claim_ids": [],
                    },
                    "provenance": {
                        "domain": str(case.get("domain", "unknown")),
                        "split": str(case.get("split", "unknown")),
                        "model": lab01_acquisition.LAB01_MODEL_ID,
                        "revision": lab01_acquisition.LAB01_MODEL_REVISION,
                        "license": str(case.get("provenance", {}).get("license", "Apache-2.0")),
                        "notes": "Model-backed resid_post extraction run",
                    },
                }
            )

    if not index_rows:
        raise RepresentationExtractorError("no index rows produced")

    save_file(safe_tensor_rows, tensors_path)
    tensor_sha = _sha256_path(tensors_path)
    for row in index_rows:
        row["artifact_sha256"] = tensor_sha

    with index_path.open("w", encoding="utf-8") as fp:
        for row in index_rows:
            fp.write(json.dumps(row, sort_keys=True, ensure_ascii=False))
            fp.write("\n")

    summary = {
        "artifact_class": "model-backed-representation",
        "artifact_format": "safetensors",
        "status": "pass",
        "empirical": True,
        "evidence_eligible": False,
        "claim_ids": [],
        "run_timestamp_utc": created_at,
        "record_count": len(index_rows),
        "case_count": len(cases),
        "created_at": created_at,
        "cases_sha256": cases_sha256,
        "cases_path": str(cases_path.name),
        "config_version": REPR_EXTRACTOR_CONFIG_VERSION,
        "model": {
            "id": lab01_acquisition.LAB01_MODEL_ID,
            "revision": lab01_acquisition.LAB01_MODEL_REVISION,
            "license": lab01_acquisition.LAB01_LICENSE_ID,
        },
        "tokenizer": tokenizer_receipt,
        "output_artifacts": {
            "tensors": {
                "path": tensors_path.name,
                "sha256": _sha256_path(tensors_path),
                "records": len(index_rows),
            },
            "index": {
                "path": index_path.name,
                "sha256": _sha256_path(index_path),
                "records": len(index_rows),
            },
        },
        "prompt_stats": {
            "template_hash": prompt_template_hash,
            "prompt_count": len(prompt_records),
            "case_records_hash": _sha256_text("\n".join(sorted(row["prompt_hash"] for row in prompt_records))),
        },
        "non_claim_boundary": {
            "empirical": True,
            "evidence_eligible": False,
            "claim_ids": [],
        },
        "index_uri": index_path.name,
        "activations_uri": tensors_path.name,
    }
    summary_text = _stable_dump(summary)
    summary_path.write_text(summary_text, encoding="utf-8")

    return index_path, summary_path, tensors_path


def run_extractor(
    *,
    cases_path: str | Path,
    model_root: str | Path,
    output_dir: str | Path,
    prompt_template: str = DEFAULT_TEMPLATE,
    token_policy: str = SUPPORTED_TOKEN_POLICY,
    activation_site: str = SUPPORTED_ACTIVATION_SITE,
    adapter_factory: Any = GPTNeoXTransformersAdapter,
    identity_verifier: Any = lab01_acquisition.verify_expected_snapshot,
    created_at: str | None = None,
) -> RunArtifacts:
    """Execute a bounded, offline model-backed extractor with strict checks."""
    if created_at is None:
        raise RepresentationExtractorError(
            "created_at is required; use a frozen UTC timestamp for deterministic output"
        )
    created_at = _parse_utc_timestamp(created_at)
    index_path, summary_path, tensors_path = _run_with_adapter(
        cases_path=Path(cases_path),
        model_root=Path(model_root),
        output_root=Path(output_dir),
        created_at=created_at,
        prompt_template=prompt_template,
        token_policy=token_policy,
        activation_site=activation_site,
        adapter_factory=adapter_factory,
        identity_verifier=identity_verifier,
    )
    return RunArtifacts(index_path=index_path, summary_path=summary_path, tensors_path=tensors_path)


def run_from_config(
    config_path: str | Path,
    *,
    output_override: str | Path | None = None,
    adapter_factory: Any = GPTNeoXTransformersAdapter,
    identity_verifier: Any = lab01_acquisition.verify_expected_snapshot,
) -> RunArtifacts:
    config_path = Path(config_path).expanduser().resolve()
    config = _read_json(config_path)

    base_dir = config_path.parent

    if str(config.get("config_version", "")) != REPR_EXTRACTOR_CONFIG_VERSION:
        raise RepresentationExtractorError("unsupported config_version")
    expected_model = {
        "id": lab01_acquisition.LAB01_MODEL_ID,
        "revision": lab01_acquisition.LAB01_MODEL_REVISION,
    }
    if config.get("model") != expected_model:
        raise RepresentationExtractorError("config model identity does not match the pinned Lab 01 snapshot")
    expected_boundary = {
        "empirical": True,
        "evidence_eligible": False,
        "claim_ids": [],
    }
    if config.get("non_claim_boundary") != expected_boundary:
        raise RepresentationExtractorError("config violates the empirical non-claim boundary")

    cases_path = (base_dir / str(config.get("cases_path", ""))).resolve()
    model_root = (base_dir / str(config.get("model_root", ""))).resolve()
    output_dir = (
        (base_dir / str(output_override)).resolve()
        if output_override is not None
        else (base_dir / str(config.get("output_dir", "results/lab01/model-backed-representations"))).resolve()
    )
    prompt_template = str(config.get("prompt_template", DEFAULT_TEMPLATE))
    token_policy = str(config.get("token_policy", SUPPORTED_TOKEN_POLICY))
    activation_site = str(config.get("activation_site", SUPPORTED_ACTIVATION_SITE))
    created_at = _parse_utc_timestamp(config.get("run_timestamp_utc"))

    if not cases_path.is_file():
        raise RepresentationExtractorError(f"cases_path not found: {cases_path}")
    if not str(model_root).strip():
        raise RepresentationExtractorError("model_root is required")
    if not str(output_dir).strip():
        raise RepresentationExtractorError("output_dir is required")

    return run_extractor(
        cases_path=cases_path,
        model_root=model_root,
        output_dir=output_dir,
        prompt_template=prompt_template,
        token_policy=token_policy,
        activation_site=activation_site,
        created_at=created_at,
        adapter_factory=adapter_factory,
        identity_verifier=identity_verifier,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract model activations as representation records.")
    parser.add_argument("--config", required=True, help="Path to extractor JSON config")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output override (defaults to config output_dir)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    artifacts = run_from_config(args.config, output_override=args.output_dir)

    print(f"index={artifacts.index_path}")
    print(f"summary={artifacts.summary_path}")
    print(f"tensors={artifacts.tensors_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
