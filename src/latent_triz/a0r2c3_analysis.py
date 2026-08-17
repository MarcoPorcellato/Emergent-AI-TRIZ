"""Analysis-only C3 recovery for the exact C2 index metadata omission.

This module never loads a model.  It permits a missing ``dtype`` field only
for the immutable C2 index whose hash is bound below, then delegates the
unchanged frozen statistical procedure to :mod:`a0r2_analysis`.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import a0r2_analysis as base_analysis
from .a0r2_analysis import A0R2AnalysisError


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
    """Run frozen A0-R2 analysis with one C3-only in-memory index recovery.

    The historical analyzer remains byte-identical to its frozen R2 binding.
    This wrapper temporarily narrows its private index reader only for the
    exact C2 representation index; target rows retain the original reader and
    remain unopened until the historical analyzer reaches its analysis gate.
    """

    if "index_row_normalizer" in kwargs:
        raise A0R2C3AnalysisError("C3 index recovery cannot be overridden")
    try:
        expected_index_path = Path(kwargs["activation_index_path"]).resolve()
    except (KeyError, TypeError) as exc:
        raise A0R2C3AnalysisError("C3 activation index path is required") from exc

    original_reader = base_analysis._read_jsonl
    normalized_once = False

    def _c3_reader(path: Path) -> list[dict[str, Any]]:
        nonlocal normalized_once
        rows = original_reader(path)
        if Path(path).resolve() != expected_index_path:
            return rows
        if normalized_once:
            raise A0R2C3AnalysisError("C3 activation index was read more than once")
        normalized_once = True
        return normalize_c2_index_dtype(rows, _activation_receipt(kwargs))

    base_analysis._read_jsonl = _c3_reader
    try:
        result = base_analysis.analyze_a0r2(**kwargs)
    finally:
        base_analysis._read_jsonl = original_reader
    if not normalized_once:
        raise A0R2C3AnalysisError("C3 activation index was not read")
    return result


def _activation_receipt(kwargs: Mapping[str, Any]) -> Mapping[str, Any]:
    """Read only the already-bound receipt before the historical target gate."""

    receipt_path = kwargs.get("activation_receipt_path")
    if receipt_path is None:
        raise A0R2C3AnalysisError("C3 activation receipt path is required")
    receipt = base_analysis._read_json(Path(receipt_path).resolve())
    return receipt
