from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from latent_triz.h1_packet_audit import H1PacketError, audit_h1_packet


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "experiments" / "h1-cognitive-pilot"


class H1PacketAuditTests(unittest.TestCase):
    def test_public_packet_is_ready_but_not_empirical(self) -> None:
        result = audit_h1_packet(repo_root=ROOT)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["collection_status"], "ready_for_collection")
        self.assertEqual(result["case_count"], 6)
        self.assertFalse(result["evidence_eligible"])
        self.assertFalse(result["expert_validated"])

    def test_hash_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "experiments" / "h1-cognitive-pilot"
            target.mkdir(parents=True)
            for path in PACKET.iterdir():
                target.joinpath(path.name).write_bytes(path.read_bytes())
            protocol = json.loads((target / "protocol.json").read_text())
            protocol["input_hashes"]["cases_sha256"] = "0" * 64
            (target / "protocol.json").write_text(json.dumps(protocol), encoding="utf-8")
            with self.assertRaises(H1PacketError):
                audit_h1_packet(repo_root=root)

    def test_label_cue_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "experiments" / "h1-cognitive-pilot"
            target.mkdir(parents=True)
            for path in PACKET.iterdir():
                target.joinpath(path.name).write_bytes(path.read_bytes())
            cases = target / "cases.jsonl"
            first = json.loads(cases.read_text().splitlines()[0])
            first["displayed_solution"] += " Apply TRIZ."
            lines = [json.dumps(first)] + cases.read_text().splitlines()[1:]
            cases.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaises(H1PacketError):
                audit_h1_packet(repo_root=root)

    def test_v12_human_record_schema_rejects_synthetic_flag(self) -> None:
        from latent_triz.validator import validate

        schema = json.loads((ROOT / "schemas/h1-annotation.schema.json").read_text())
        record = {
            "annotation_id": "rater_a_h1_case_01", "case_id": "h1_case_01", "rater_id": "rater_a",
            "label": "segmentation", "confidence": 0.9, "rationale": "The parts are independently managed.",
            "operator_presence": 3, "operator_essentiality": 3, "contradiction_resolution": 3,
            "solution_feasibility": 3, "alternative_principle": "", "guide_revision": "v1.2.0",
            "guide_sha256": "a" * 64, "case_payload_sha256": "b" * 64, "dataset_batch_sha256": "c" * 64,
            "display_view_version": "v1.2.0", "session_id": "session-a", "non_empirical": False,
            "annotated_at": "2026-08-18T12:00:00Z",
        }
        self.assertEqual([], validate(record, schema))
        record["non_empirical"] = True
        self.assertTrue(validate(record, schema))
