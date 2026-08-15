"""Deterministic verifier for the tracked A0-R1 pre-output foundation."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from .a0r1_corpus import generate_a0r1_corpus
from .a0r1_preoutput import run_a0r1_preoutput_audits


class A0R1VerifyError(RuntimeError):
    """Raised when regeneration differs from tracked A0-R1 artifacts."""


CORPUS_FILES = (
    "manifest.json",
    "cases.jsonl",
    "targets/calibration.jsonl",
    "targets/sealed.jsonl",
)
PREOUTPUT_FILES = (
    "independence.json",
    "shortcuts.json",
    "summary.json",
    "preoutput-manifest.json",
)


def _require_equal(expected_root: Path, actual_root: Path, relative_paths: tuple[str, ...]) -> None:
    for relative in relative_paths:
        expected = expected_root / relative
        actual = actual_root / relative
        if not expected.is_file():
            raise A0R1VerifyError(f"tracked artifact is missing: {relative}")
        if not actual.is_file() or actual.read_bytes() != expected.read_bytes():
            raise A0R1VerifyError(f"deterministic regeneration mismatch: {relative}")


def verify_a0r1_foundation(root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    protocol = repository / "experiments/a0r1-independent-proxy/protocol.json"
    tracked_corpus = repository / "data/a0r1"
    source_corpus = repository / "data/a0"
    tracked_preoutput = repository / "results/a0r1/preoutput"

    with tempfile.TemporaryDirectory() as temporary:
        temp_root = Path(temporary)
        regenerated_corpus = temp_root / "corpus"
        regenerated_preoutput = temp_root / "preoutput"
        generate_a0r1_corpus(protocol, regenerated_corpus)
        run_a0r1_preoutput_audits(
            protocol,
            regenerated_corpus,
            source_corpus,
            regenerated_preoutput,
        )
        _require_equal(tracked_corpus, regenerated_corpus, CORPUS_FILES)
        _require_equal(tracked_preoutput, regenerated_preoutput, PREOUTPUT_FILES)

    return {
        "artifact_class": "a0-r1-foundation-verification",
        "protocol_id": "a0-r1-tier-r1-v1.0",
        "protocol_status": "planned",
        "empirical": True,
        "scientific_status": "exploratory",
        "evidence_eligible": False,
        "expert_validated": False,
        "claim_ids": [],
        "model_output_accessed": False,
        "corpus_files_verified": len(CORPUS_FILES),
        "preoutput_files_verified": len(PREOUTPUT_FILES),
        "status": "pass",
    }
