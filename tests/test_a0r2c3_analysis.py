"""Synthetic-only qualification of the C3 index metadata recovery."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.a0r2c3_analysis import (  # noqa: E402
    A0R2C3AnalysisError,
    EXPECTED_C2_INDEX_SHA256,
    EXPECTED_C2_RECORDS,
    analyze_a0r2c3,
    normalize_c2_index_dtype,
)
from latent_triz import a0r2_analysis as base_analysis  # noqa: E402


def _receipt() -> dict[str, object]:
    return {
        "runtime": {"torch_dtype": "float32"},
        "output_bundle": {"artifact_hashes": {"index_sha256": EXPECTED_C2_INDEX_SHA256}},
    }


class A0R2C3AnalysisTests(unittest.TestCase):
    def test_recovers_only_the_bound_missing_dtype_field(self) -> None:
        rows = [{"record_id": str(index)} for index in range(EXPECTED_C2_RECORDS)]
        recovered = normalize_c2_index_dtype(rows, _receipt())
        self.assertEqual("float32", recovered[0]["dtype"])
        self.assertNotIn("dtype", rows[0])

    def test_rejects_unbound_index(self) -> None:
        receipt = _receipt()
        receipt["output_bundle"]["artifact_hashes"]["index_sha256"] = "0" * 64  # type: ignore[index]
        with self.assertRaisesRegex(A0R2C3AnalysisError, "binding drift"):
            normalize_c2_index_dtype([{} for _ in range(EXPECTED_C2_RECORDS)], receipt)

    def test_rejects_existing_or_wrong_dtype(self) -> None:
        rows = [{"record_id": str(index)} for index in range(EXPECTED_C2_RECORDS)]
        rows[17]["dtype"] = "float16"
        with self.assertRaisesRegex(A0R2C3AnalysisError, "inapplicable"):
            normalize_c2_index_dtype(rows, _receipt())

    def test_rejects_wrong_runtime_or_count(self) -> None:
        receipt = copy.deepcopy(_receipt())
        receipt["runtime"]["torch_dtype"] = "float16"  # type: ignore[index]
        with self.assertRaisesRegex(A0R2C3AnalysisError, "runtime dtype"):
            normalize_c2_index_dtype([{} for _ in range(EXPECTED_C2_RECORDS)], receipt)
        with self.assertRaisesRegex(A0R2C3AnalysisError, "record-count"):
            normalize_c2_index_dtype([], _receipt())

    def test_wrapper_normalizes_only_the_index_reader_and_restores_base(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index_path = root / "index.jsonl"
            targets_path = root / "targets.jsonl"
            receipt_path = root / "receipt.json"
            index_path.write_text('{"record_id":"index"}\n', encoding="utf-8")
            targets_path.write_text('{"record_id":"target"}\n', encoding="utf-8")
            receipt_path.write_text(json.dumps(_receipt()), encoding="utf-8")
            original_reader = base_analysis._read_jsonl
            observed: dict[str, object] = {}

            def fake_analyze(**kwargs):  # noqa: ANN003
                observed["index"] = base_analysis._read_jsonl(Path(kwargs["activation_index_path"]))
                observed["targets"] = base_analysis._read_jsonl(Path(kwargs["targets_path"]))
                return {"status": "synthetic"}

            def normalize(rows, receipt):  # noqa: ANN001
                observed["receipt"] = receipt
                return [{**row, "dtype": "float32"} for row in rows]

            with (
                patch.object(base_analysis, "analyze_a0r2", side_effect=fake_analyze),
                patch("latent_triz.a0r2c3_analysis.normalize_c2_index_dtype", side_effect=normalize) as recovery,
            ):
                result = analyze_a0r2c3(
                    activation_index_path=index_path,
                    activation_receipt_path=receipt_path,
                    targets_path=targets_path,
                )

            self.assertEqual({"status": "synthetic"}, result)
            self.assertEqual("float32", observed["index"][0]["dtype"])  # type: ignore[index]
            self.assertNotIn("dtype", observed["targets"][0])  # type: ignore[index]
            recovery.assert_called_once()
            self.assertIs(base_analysis._read_jsonl, original_reader)


if __name__ == "__main__":
    unittest.main()
