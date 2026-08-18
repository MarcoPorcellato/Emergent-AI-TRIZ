from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from latent_triz.h1_collection_audit import _batch_hash, _case_hash, audit_h1_annotations


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "experiments/h1-cognitive-pilot"


class H1CollectionAuditTests(unittest.TestCase):
    def _packet(self, root: Path) -> tuple[Path, Path, Path, list[Path]]:
        cases = root / "cases.jsonl"
        guide = root / "guide.json"
        schema = root / "schema.json"
        shutil.copy2(PACKET / "cases.jsonl", cases)
        shutil.copy2(PACKET / "annotation-guide-v1.2.json", guide)
        shutil.copy2(ROOT / "schemas/h1-annotation.schema.json", schema)
        records = [json.loads(line) for line in cases.read_text().splitlines() if line.strip()]
        hashes = {record["case_id"]: _case_hash(record) for record in records}
        batch = _batch_hash(hashes)
        guide_sha = hashlib.sha256(guide.read_bytes()).hexdigest()
        outputs: list[Path] = []
        for suffix in "abc":
            output = root / f"rater_{suffix}.jsonl"
            rows = []
            for record in records:
                rows.append({
                    "annotation_id": f"rater_{suffix}_{record['case_id']}",
                    "case_id": record["case_id"], "rater_id": f"rater_{suffix}",
                    "label": "segmentation", "confidence": 0.9,
                    "rationale": "The stated solution makes the operator essential.",
                    "operator_presence": 3, "operator_essentiality": 3,
                    "contradiction_resolution": 3, "solution_feasibility": 3,
                    "alternative_principle": "", "guide_revision": "v1.2.0",
                    "guide_sha256": guide_sha, "case_payload_sha256": hashes[record["case_id"]],
                    "dataset_batch_sha256": batch, "display_view_version": "v1.2.0",
                    "session_id": f"session-{suffix}", "non_empirical": False,
                    "annotated_at": "2026-08-18T12:00:00Z",
                })
            output.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")
            outputs.append(output)
        return cases, guide, schema, outputs

    def test_three_unanimous_raters_are_freeze_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cases, guide, schema, outputs = self._packet(Path(directory))
            result = audit_h1_annotations(
                cases_path=cases, guide_path=guide, annotation_schema_path=schema,
                annotation_paths=outputs,
            )
            self.assertEqual(result["status"], "pass")
            self.assertTrue(result["ready_for_adjudication"])
            self.assertTrue(result["ready_for_freeze"])
            self.assertEqual(result["counts"]["raters"], 3)
            self.assertEqual(result["counts"]["annotations"], 18)
            self.assertFalse(result["evidence_eligible"])
            self.assertEqual(result["claim_ids"], [])

    def test_hash_mutation_is_published_as_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cases, guide, schema, outputs = self._packet(Path(directory))
            row = json.loads(outputs[0].read_text().splitlines()[0])
            row["case_payload_sha256"] = "0" * 64
            outputs[0].write_text(json.dumps(row) + "\n" + "\n".join(outputs[0].read_text().splitlines()[1:]) + "\n")
            result = audit_h1_annotations(
                cases_path=cases, guide_path=guide, annotation_schema_path=schema,
                annotation_paths=outputs,
            )
            self.assertEqual(result["status"], "fail")
            self.assertFalse(result["ready_for_freeze"])
            self.assertTrue(any(item["code"] == "invalid_case_hash" for item in result["issues"]))


if __name__ == "__main__":
    unittest.main()
