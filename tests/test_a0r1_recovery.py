from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0r1_recovery import A0R1RecoveryError, recover_a0r1_domain_prefixes
from latent_triz.validator import validate


BASE_RESULT = (
    Path(__file__).resolve().parents[1]
    / "results"
    / "a0r1"
    / "a0r1-v1.0.0-e93a9faa-r1"
    / "statistical-result.raw.json"
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "a0r1-statistical-result.schema.json"
RECEIPT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "a0r1-recovery-receipt.schema.json"
)


def _read_base_payload() -> dict:
    return json.loads(BASE_RESULT.read_text(encoding="utf-8"))


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


DOMAINS = (
    "r1_agriculture",
    "r1_energy",
    "r1_manufacturing",
    "r1_medicine",
    "r1_software",
    "r1_transport",
)
CREATED_AT = "2026-08-15T05:31:00Z"


def _to_domain_prefixed(node):
    if isinstance(node, str):
        for domain in DOMAINS:
            if node == domain:
                return domain, 1
            if node.startswith(f"{domain}/"):
                return f"{domain}/{node[len(domain)+1:]}", 1
        return node, 0

    if isinstance(node, list):
        out = []
        count = 0
        for value in node:
            transformed, value_count = _to_domain_prefixed(value)
            out.append(transformed)
            count += value_count
        return out, count

    if isinstance(node, dict):
        out = {}
        count = 0
        for key, value in node.items():
            transformed_key, key_count = _to_domain_prefixed(str(key))
            transformed_value, value_count = _to_domain_prefixed(value)
            out[transformed_key] = transformed_value
            count += key_count + value_count
        return out, count

    return node, 0


def _with_prefixed_labels(payload: dict) -> tuple[dict, int]:
    return _to_domain_prefixed(payload)


def _replace_label(node, source_label: str, replacement_label: str):
    if isinstance(node, str):
        if node == source_label or node.startswith(f"{source_label}/"):
            return node.replace(source_label, replacement_label, 1), 1
        return node, 0
    if isinstance(node, list):
        out = []
        count = 0
        for value in node:
            transformed, added = _replace_label(value, source_label, replacement_label)
            out.append(transformed)
            count += added
        return out, count
    if isinstance(node, dict):
        out = {}
        count = 0
        for key, value in node.items():
            transformed_key, key_count = _replace_label(str(key), source_label, replacement_label)
            transformed_value, value_count = _replace_label(value, source_label, replacement_label)
            out[transformed_key] = transformed_value
            count += key_count + value_count
        return out, count
    return node, 0


def _write_json(path: Path, payload: dict) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class A0R1RecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        base_payload, replacements = _with_prefixed_labels(_read_base_payload())
        self.base_payload = base_payload
        self.base_replacements = replacements
        self.stat_schema = _load_schema()

    def test_recovery_success_exact_54_replacements_and_outputs(self) -> None:
        self.assertEqual(54, self.base_replacements)
        with tempfile.TemporaryDirectory() as workspace:
            raw_path = Path(workspace) / "statistical-result.raw.json"
            recovered_path = Path(workspace) / "statistical-result.json"
            receipt_path = Path(workspace) / "recovery-receipt.json"
            _write_json(raw_path, self.base_payload)
            expected = _sha256(raw_path)
            receipt = recover_a0r1_domain_prefixes(
                raw_result=raw_path,
                recovered_result=recovered_path,
                recovery_receipt=receipt_path,
                expected_raw_sha256=expected,
                created_at=CREATED_AT,
            )
            recovered_payload = json.loads(recovered_path.read_text(encoding="utf-8"))
            self.assertEqual("pass", receipt["status"])
            issues = validate(recovered_payload, self.stat_schema)
            self.assertEqual([], issues)
            receipt_schema = json.loads(RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
            self.assertEqual([], validate(receipt, receipt_schema))
            self.assertTrue(Path(recovered_path).is_file())
            self.assertEqual(54, receipt["transformation"]["replacements_total"])
            self.assertEqual("a0r1-recovery-receipt", receipt["artifact_class"])
            self.assertTrue(receipt_path.is_file())

            recovered_text = recovered_path.read_text(encoding="utf-8")
            self.assertNotIn('"r1_agriculture"', recovered_text)
            self.assertIn('"agriculture"', recovered_text)
            self.assertTrue(recovered_payload["macro_f1_margin_over_surface"] > 0)

    def test_recovery_fails_when_raw_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            raw_path = Path(workspace) / "raw.json"
            _write_json(raw_path, self.base_payload)
            with self.assertRaises(A0R1RecoveryError):
                recover_a0r1_domain_prefixes(
                    raw_path,
                    Path(workspace) / "recovered.json",
                    Path(workspace) / "receipt.json",
                    expected_raw_sha256="00" * 32,
                    created_at=CREATED_AT,
                )

    def test_recovery_rejects_unexpected_label(self) -> None:
        mutated = dict(self.base_payload)
        mutated["r1_unknown/domain"] = 1
        with tempfile.TemporaryDirectory() as workspace:
            raw_path = Path(workspace) / "raw.json"
            _write_json(raw_path, mutated)
            with self.assertRaises(A0R1RecoveryError):
                recover_a0r1_domain_prefixes(
                    raw_path,
                    Path(workspace) / "recovered.json",
                    Path(workspace) / "receipt.json",
                    expected_raw_sha256=_sha256(raw_path),
                    created_at=CREATED_AT,
                )

    def test_recovery_rejects_missing_domain_label(self) -> None:
        mutated, _ = _replace_label(self.base_payload, "r1_agriculture", "agriculture")
        with tempfile.TemporaryDirectory() as workspace:
            raw_path = Path(workspace) / "raw.json"
            _write_json(raw_path, mutated)
            with self.assertRaises(A0R1RecoveryError):
                recover_a0r1_domain_prefixes(
                    raw_path,
                    Path(workspace) / "recovered.json",
                    Path(workspace) / "receipt.json",
                    expected_raw_sha256=_sha256(raw_path),
                    created_at=CREATED_AT,
                )

    def test_recovery_rejects_collision(self) -> None:
        mutated = json.loads(json.dumps(self.base_payload))
        # collide r1_agriculture -> agriculture with already existing key in primary map
        primary = mutated["primary"]["per_domain_accuracy"]
        primary["agriculture"] = primary["r1_agriculture"]
        with tempfile.TemporaryDirectory() as workspace:
            raw_path = Path(workspace) / "raw.json"
            _write_json(raw_path, mutated)
            with self.assertRaises(A0R1RecoveryError):
                recover_a0r1_domain_prefixes(
                    raw_path,
                    Path(workspace) / "recovered.json",
                    Path(workspace) / "receipt.json",
                    expected_raw_sha256=_sha256(raw_path),
                    created_at=CREATED_AT,
                )

    def test_recovery_preserves_non_numeric_invariants(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            raw_path = Path(workspace) / "raw.json"
            _write_json(raw_path, self.base_payload)
            out_path = Path(workspace) / "recovered.json"
            receipt_path = Path(workspace) / "receipt.json"
            recover_a0r1_domain_prefixes(
                raw_path,
                out_path,
                receipt_path,
                expected_raw_sha256=_sha256(raw_path),
                created_at=CREATED_AT,
            )
            recovered = json.loads(out_path.read_text(encoding="utf-8"))
            base = _read_base_payload()
            self.assertEqual(base["primary"]["family_success_rate"], recovered["primary"]["family_success_rate"])
            self.assertEqual(base["primary"]["family_successes"], recovered["primary"]["family_successes"])

    def test_recovery_rejects_schema_invalid_output(self) -> None:
        mutated = json.loads(json.dumps(self.base_payload))
        mutated["artifact_class"] = "invalid"
        with tempfile.TemporaryDirectory() as workspace:
            raw_path = Path(workspace) / "raw.json"
            _write_json(raw_path, mutated)
            with self.assertRaises(A0R1RecoveryError):
                recover_a0r1_domain_prefixes(
                    raw_path,
                    Path(workspace) / "recovered.json",
                    Path(workspace) / "receipt.json",
                    expected_raw_sha256=_sha256(raw_path),
                    created_at=CREATED_AT,
                )

    def test_recovery_refuse_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            raw_path = Path(workspace) / "raw.json"
            output_path = Path(workspace) / "recovered.json"
            receipt_path = Path(workspace) / "receipt.json"
            _write_json(raw_path, self.base_payload)
            expected = _sha256(raw_path)

            first = recover_a0r1_domain_prefixes(
                raw_path,
                output_path,
                receipt_path,
                expected,
                CREATED_AT,
            )
            self.assertEqual("pass", first["status"])
            with self.assertRaises(A0R1RecoveryError):
                recover_a0r1_domain_prefixes(
                    raw_path,
                    output_path,
                    receipt_path,
                    expected,
                    CREATED_AT,
                )

    def test_recovery_reads_only_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            raw_path = Path(workspace) / "raw.json"
            _write_json(raw_path, self.base_payload)
            output = Path(workspace) / "recovered.json"
            receipt = Path(workspace) / "receipt.json"
            expected = _sha256(raw_path)
            calls = {"read_text": 0, "read_bytes": 0}

            def _read_text(*args, **kwargs):
                calls["read_text"] += 1
                raise RuntimeError("unexpected read_text usage")

            def _read_bytes(*args, **kwargs):
                calls["read_bytes"] += 1
                raise RuntimeError("unexpected read_bytes usage")

            with patch.object(Path, "read_text", _read_text), patch.object(
                Path, "read_bytes", _read_bytes
            ):
                recover_a0r1_domain_prefixes(
                    raw_path, output, receipt, expected, CREATED_AT
                )

            self.assertEqual(0, calls["read_text"])
            self.assertEqual(0, calls["read_bytes"])


if __name__ == "__main__":
    unittest.main()
