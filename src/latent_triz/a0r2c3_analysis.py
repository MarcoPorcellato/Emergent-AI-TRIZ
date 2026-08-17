"""Analysis-only C3 recovery for the exact C2 index metadata omission.

This module never loads a model.  It permits a missing ``dtype`` field only
for the immutable C2 index whose hash is bound below, then delegates the
unchanged frozen statistical procedure to :mod:`a0r2_analysis`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .a0r2_analysis import A0R2AnalysisError, analyze_a0r2


EXPECTED_C2_INDEX_SHA256 = "baa78647fcc01c1d71cf27ef1c1fd83c6e38feb2a9a54a58fab87f245c63fc58"
EXPECTED_C2_RECORDS = 1920


class A0R2C3AnalysisError(A0R2AnalysisError):
    """Raised when the narrowly permitted C2 metadata recovery drifts."""


def normalize_c2_index_dtype(
    index_rows: list[dict[str, Any]], receipt: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Return an in-memory, explicitly typed C2 index without rewriting it.

    The allowance is fail-closed: every source row must omit the field, the
    receipt must name the exact historical index hash, and its runtime must
    independently declare CPU float32.  No target data is accepted or read.
    """

    bundle = receipt.get("output_bundle")
    runtime = receipt.get("runtime")
    if not isinstance(bundle, Mapping) or not isinstance(runtime, Mapping):
        raise A0R2C3AnalysisError("C2 activation receipt metadata is malformed")
    hashes = bundle.get("artifact_hashes")
    if not isinstance(hashes, Mapping) or hashes.get("index_sha256") != EXPECTED_C2_INDEX_SHA256:
        raise A0R2C3AnalysisError("C2 index binding drift")
    if runtime.get("torch_dtype") != "float32":
        raise A0R2C3AnalysisError("C2 runtime dtype binding drift")
    if len(index_rows) != EXPECTED_C2_RECORDS:
        raise A0R2C3AnalysisError("C2 index record-count drift")

    normalized: list[dict[str, Any]] = []
    for row in index_rows:
        if not isinstance(row, dict) or "dtype" in row:
            raise A0R2C3AnalysisError("C2 index dtype recovery is inapplicable")
        recovered = dict(row)
        recovered["dtype"] = "float32"
        normalized.append(recovered)
    return normalized


def analyze_a0r2c3(**kwargs: Any) -> dict[str, Any]:
    """Run the frozen A0-R2 analysis with only the C3 in-memory recovery."""

    if "index_row_normalizer" in kwargs:
        raise A0R2C3AnalysisError("C3 index recovery cannot be overridden")
    return analyze_a0r2(index_row_normalizer=normalize_c2_index_dtype, **kwargs)
