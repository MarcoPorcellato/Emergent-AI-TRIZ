"""Synthetic-only qualification of the C3 index metadata recovery."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.a0r2c3_analysis import (  # noqa: E402
    A0R2C3AnalysisError,
    EXPECTED_C2_INDEX_SHA256,
    EXPECTED_C2_RECORDS,
    normalize_c2_index_dtype,
)


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


if __name__ == "__main__":
    unittest.main()
