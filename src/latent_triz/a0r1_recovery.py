"""Deterministic recovery utility for the A0-R1 domain-prefix clerical bug."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from .validator import validate

REQUIRED_DOMAINS = (
    ("r1_agriculture", "agriculture"),
    ("r1_energy", "energy"),
    ("r1_manufacturing", "manufacturing"),
    ("r1_medicine", "medicine"),
    ("r1_software", "software"),
    ("r1_transport", "transport"),
)
DOMAIN_PREFIXES: dict[str, str] = dict(REQUIRED_DOMAINS)
REQUIRED_LABELS = tuple(DOMAIN_PREFIXES.keys())
DOMAIN_MAP_KIND = "exact_domain_prefix_removal"
EXPECTED_REPLACEMENTS = 54
SCHEMA_VALIDATION = "pass"
RECOVERY_ID = "a0r1-domain-prefix-recovery-v1"


class A0R1RecoveryError(RuntimeError):
    """Raised when recovery cannot be completed under deterministic constraints."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError as exc:
        raise A0R1RecoveryError("cannot read required JSON input") from exc
    except json.JSONDecodeError as exc:
        raise A0R1RecoveryError("invalid JSON input") from exc
    if not isinstance(payload, dict):
        raise A0R1RecoveryError("raw result is not a JSON object")
    return payload


def _load_schema() -> dict[str, Any]:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "a0r1-statistical-result.schema.json"
    try:
        with schema_path.open("r", encoding="utf-8") as handle:
            schema = json.load(handle)
    except OSError as exc:
        raise A0R1RecoveryError("cannot load statistical schema") from exc
    except json.JSONDecodeError as exc:
        raise A0R1RecoveryError("statistical schema is invalid") from exc
    if not isinstance(schema, dict):
        raise A0R1RecoveryError("statistical schema is malformed")
    return schema


def _replace_domain_prefixes(value: str) -> tuple[str, int, str | None]:
    replaced = 0
    for source, target in REQUIRED_DOMAINS:
        if value == source:
            return target, 1, source
        if value.startswith(f"{source}/"):
            replaced += 1
            return f"{target}/{value[len(source) + 1:]}", replaced, source
    return value, 0, None


def _transform_and_replace(payload: Any) -> tuple[Any, int, set[str], set[str], set[str], set[str]]:
    """Return transformed payload and metadata.

    Metadata:
    - replacements count
    - seen labels encountered in keys/values
    - missing, unexpected, and collision diagnostics
    """
    seen_labels: set[str] = set()
    unexpected: set[str] = set()
    collisions: set[str] = set()
    missing: set[str] = set()

    def _transform(item: Any) -> Any:
        nonlocal seen_labels, unexpected, collisions
        if isinstance(item, str):
            canonical = item
            total = 0
            for source, target in REQUIRED_DOMAINS:
                if canonical == source or canonical.startswith(f"{source}/"):
                    seen_labels.add(source)
                    replacement, count, source_name = _replace_domain_prefixes(canonical)
                    canonical = replacement
                    total += count
                    if source_name is not None:
                        seen_labels.add(source_name)
                    break
            if total == 0 and canonical.startswith("r1_"):
                unexpected.add(canonical.split("/", 1)[0])
            return canonical, total

        if isinstance(item, list):
            transformed = []
            local_count = 0
            for entry in item:
                transformed_value, count = _transform(entry)
                transformed.append(transformed_value)
                local_count += count
            return transformed, local_count

        if isinstance(item, dict):
            transformed: dict[str, Any] = {}
            local_count = 0
            for key, value in item.items():
                original_key = str(key)
                transformed_key, key_count, key_label = _replace_domain_prefixes(original_key)
                if key_count and key_label is not None:
                    seen_labels.add(key_label)
                value_transformed, value_count = _transform(value)
                if key_count == 0 and original_key.startswith("r1_") and original_key not in REQUIRED_LABELS:
                    unexpected.add(original_key)
                if key_count == 0 and original_key in REQUIRED_LABELS:
                    seen_labels.add(original_key)
                if transformed_key in transformed:
                    collisions.add(str(key))
                    continue
                transformed[transformed_key] = value_transformed
                local_count += key_count + value_count
            return transformed, local_count

        return item, 0

    transformed_payload, count = _transform(payload)
    missing = set(REQUIRED_LABELS) - seen_labels
    return (
        transformed_payload,
        count,
        missing,
        unexpected,
        collisions,
        set(),
    )


def _restore_prefixes(item: Any) -> Any:
    if isinstance(item, str):
        for source, target in REQUIRED_DOMAINS:
            if item == target:
                return source
            if item.startswith(f"{target}/"):
                return f"{source}/{item[len(target) + 1:]}"
        return item
    if isinstance(item, list):
        return [_restore_prefixes(entry) for entry in item]
    if isinstance(item, dict):
        restored: dict[str, Any] = {}
        for key, value in item.items():
            restored_key = _restore_prefixes(str(key))
            if restored_key in restored:
                raise A0R1RecoveryError("inverse domain-key collision detected")
            restored[restored_key] = _restore_prefixes(value)
        return restored
    return item


def _require_status(raw: dict[str, Any]) -> None:
    status = raw.get("status")
    if status not in {"positive", "null"}:
        raise A0R1RecoveryError("raw status must be positive or null")


def _validate_schema(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    issues = validate(payload, schema)
    if issues:
        raise A0R1RecoveryError("schema validation failed")


def _serialize(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _write_pair_atomic(
    output_payload: dict[str, Any],
    output_path: Path,
    receipt_payload: dict[str, Any],
    receipt_path: Path,
) -> None:
    if output_path.exists() or receipt_path.exists():
        raise A0R1RecoveryError("refuse overwrite: recovery output already exists")
    temp_paths: list[Path] = []
    linked_paths: list[Path] = []
    try:
        for payload, target in (
            (output_payload, output_path),
            (receipt_payload, receipt_path),
        ):
            with tempfile.NamedTemporaryFile(
                "wb", dir=target.parent, delete=False, suffix=".tmp"
            ) as handle:
                handle.write(_serialize(payload))
                temp_path = Path(handle.name)
            temp_paths.append(temp_path)
            os.link(temp_path, target)
            linked_paths.append(target)
    except Exception as exc:
        for linked in linked_paths:
            linked.unlink(missing_ok=True)
        raise A0R1RecoveryError("cannot atomically persist recovery package") from exc
    finally:
        for temp_path in temp_paths:
            temp_path.unlink(missing_ok=True)


def _receipt(
    *, raw_result_path: Path, recovered_result_path: Path, raw_sha256: str,
    recovered_sha256: str, code_sha256: str, replacements_total: int,
    created_at: str,
) -> dict[str, Any]:
    return {
        "artifact_class": "a0r1-recovery-receipt",
        "empirical": True,
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "status": "pass",
        "created_at": created_at,
        "recovery_id": RECOVERY_ID,
        "raw_result": {
            "path": raw_result_path.name,
            "sha256": raw_sha256,
        },
        "recovered_result": {
            "path": recovered_result_path.name,
            "sha256": recovered_sha256,
        },
        "transformation": {
            "kind": DOMAIN_MAP_KIND,
            "replacements_total": replacements_total,
            "domains": len(REQUIRED_LABELS),
            "code_sha256": code_sha256,
        },
        "access": {
            "model_output": "not_accessed",
            "sealed_model_output": "not_accessed",
            "sealed_targets": "not_accessed",
        },
        "metric_values_changed": False,
        "schema_validation": SCHEMA_VALIDATION,
    }


def recover_a0r1_domain_prefixes(
    raw_result: str | Path,
    recovered_result: str | Path,
    recovery_receipt: str | Path,
    expected_raw_sha256: str,
    created_at: str,
) -> dict[str, Any]:
    raw_path = Path(raw_result).resolve()
    output_path = Path(recovered_result).resolve()
    receipt_path = Path(recovery_receipt).resolve()

    if not re.fullmatch(r"[0-9a-f]{64}", expected_raw_sha256):
        raise A0R1RecoveryError("expected raw SHA-256 is invalid")
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", created_at
    ):
        raise A0R1RecoveryError("created_at must be an explicit UTC timestamp")
    if output_path.parent != raw_path.parent or receipt_path.parent != raw_path.parent:
        raise A0R1RecoveryError("recovery files must share one package directory")
    if len({raw_path, output_path, receipt_path}) != 3:
        raise A0R1RecoveryError("recovery paths must be distinct")
    if not raw_path.is_file():
        raise A0R1RecoveryError("raw result is missing")
    if _sha256(raw_path) != expected_raw_sha256:
        raise A0R1RecoveryError("raw SHA-256 mismatch")

    raw_payload = _load_json(raw_path)
    _require_status(raw_payload)

    transformed_payload, replacements_total, missing, unexpected, collisions, _extra = _transform_and_replace(raw_payload)
    if missing:
        raise A0R1RecoveryError("missing required domain labels")
    if unexpected:
        raise A0R1RecoveryError("unexpected domain label encountered")
    if collisions:
        raise A0R1RecoveryError("domain-key collision detected")
    if replacements_total != EXPECTED_REPLACEMENTS:
        raise A0R1RecoveryError("unexpected number of domain replacements")

    _validate_schema(transformed_payload, _load_schema())
    if _restore_prefixes(transformed_payload) != raw_payload:
        raise A0R1RecoveryError("recovery changed non-domain content")

    recovered_bytes = _serialize(transformed_payload)
    recovered_sha256 = hashlib.sha256(recovered_bytes).hexdigest()
    receipt = _receipt(
        raw_result_path=raw_path,
        recovered_result_path=output_path,
        raw_sha256=_sha256(raw_path),
        recovered_sha256=recovered_sha256,
        code_sha256=_sha256(Path(__file__)),
        replacements_total=replacements_total,
        created_at=created_at,
    )
    _write_pair_atomic(transformed_payload, output_path, receipt, receipt_path)
    return receipt


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recover A0-R1 clerical domain-prefix mismatch")
    parser.add_argument("--raw-result", required=True)
    parser.add_argument("--output-result", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--expected-raw-sha256", required=True)
    parser.add_argument("--created-at", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_cli_parser()
    args = parser.parse_args(argv)
    try:
        recover_a0r1_domain_prefixes(
            args.raw_result,
            args.output_result,
            args.receipt,
            args.expected_raw_sha256,
            args.created_at,
        )
    except A0R1RecoveryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
