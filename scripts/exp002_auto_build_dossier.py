#!/usr/bin/env python3
"""Build the unapproved, hash-bound EXP-002-AUTO material dossier."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.exp002_auto_contract import validate_auto_dossier  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    root = ROOT / "experiments/exp002-auto"
    destination = root / "approval-dossier.json"
    if destination.exists():
        raise SystemExit("refusing to overwrite approval dossier")
    protocol_path = root / "protocol.json"
    schedule_path = root / "schedule.json"
    manifest_path = root / "input-manifest.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    dossier = {
        "artifact_class": "exp002-auto-approval-dossier",
        "protocol_id": "exp002-auto-v1.0.0",
        "protocol_sha256": _sha256(protocol_path),
        "schedule_sha256": _sha256(schedule_path),
        "input_manifest_sha256": _sha256(manifest_path),
        "status": "approval_requested",
        "operator_approval": {"granted": False, "operator_id": "MarcoPorcellato", "approval_text_sha256": None},
        "exact_models": protocol["models"],
        "permissions": {"model_load": True, "network": False, "generation": False, "sealed_target_read": "exactly_one_at_analysis_boundary"},
        "limits": {"wall_time_seconds_per_shard": 1800, "peak_rss_bytes_per_shard": 8589934592, "new_score_output_bytes_per_model": 134217728},
        "shards": [{"stage_id": stage["stage_id"], "shard_id": shard["shard_id"]} for stage in schedule["stages"] for shard in stage["shards"]],
        "claim_ids": [],
    }
    validate_auto_dossier(dossier, protocol_sha256=dossier["protocol_sha256"])
    destination.write_text(json.dumps(dossier, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
