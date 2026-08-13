from __future__ import annotations

import json
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from latent_triz.annotation_workbench import (
    AnnotationStore,
    AnnotationWorkbenchError,
    build_annotation_record,
    create_server,
    order_cases_for_rater,
    sanitize_cases,
)
from latent_triz.validator import validate


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data/pilot/cases.jsonl"
GUIDE = ROOT / "experiments/001-stage1-pilot/annotation-guide.json"
SCHEMA = ROOT / "schemas/dataset-annotation.schema.json"


class AnnotationWorkbenchTests(unittest.TestCase):
    def test_sanitized_cases_do_not_expose_administrative_fields(self) -> None:
        raw = [json.loads(CASES.read_text(encoding="utf-8").splitlines()[0])]
        sanitized = sanitize_cases(raw)
        for hidden in (
            "labels", "provenance", "split", "lexical_controls",
            "near_miss_case_ids", "alternative_solution_case_ids",
        ):
            self.assertNotIn(hidden, sanitized[0])

    def test_case_order_is_stable_and_rater_specific(self) -> None:
        cases = [{"case_id": f"case_{index:03d}"} for index in range(20)]
        first = order_cases_for_rater(cases, "rater_1", "a" * 64)
        repeated = order_cases_for_rater(cases, "rater_1", "a" * 64)
        second = order_cases_for_rater(cases, "rater_2", "a" * 64)
        self.assertEqual(first, repeated)
        self.assertNotEqual(first, second)

    def test_human_record_is_schema_valid_but_not_evidence(self) -> None:
        record = build_annotation_record(
            {"case_id": "pilot_case_001", "label": "segmentation", "confidence": 0.75, "rationale": "The transformation creates separately managed zones."},
            rater_id="rater_1", case_ids={"pilot_case_001"}, labels={"segmentation", "inversion"},
            guide_revision="v1.0.0", guide_sha256="a" * 64,
        )
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual([], validate(record, schema))
        self.assertFalse(record["non_empirical"])

    def test_store_rejects_duplicate_rater_case_pair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "annotations.jsonl"
            store = AnnotationStore(output, SCHEMA)
            record = build_annotation_record(
                {"case_id": "pilot_case_001", "label": "segmentation", "confidence": 0.5, "rationale": "Separate zones."},
                rater_id="rater_1", case_ids={"pilot_case_001"}, labels={"segmentation"},
                guide_revision="v1.0.0", guide_sha256="b" * 64,
            )
            store.append(record)
            self.assertTrue(store.contains("pilot_case_001", "rater_1"))
            with self.assertRaisesRegex(AnnotationWorkbenchError, "already annotated"):
                store.append({**record, "annotation_id": "ann_duplicate"})

    def test_abstention_is_a_persisted_audit_state(self) -> None:
        record = build_annotation_record(
            {"case_id": "pilot_case_001", "label": "abstain", "confidence": 0, "rationale": "Neither operator fits."},
            rater_id="rater_3", case_ids={"pilot_case_001"}, labels={"segmentation", "inversion", "abstain"},
            guide_revision="v1.0.0", guide_sha256="c" * 64,
        )
        self.assertEqual("abstain", record["label"])
        self.assertFalse(record["non_empirical"])
        self.assertNotIn("rationale", record)

    def test_loopback_server_hides_labels_and_accepts_csrf_guarded_post(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "annotations.jsonl"
            server = create_server(
                cases_path=CASES, guide_path=GUIDE, output_path=output, schema_path=SCHEMA,
                rater_id="rater_2", port=0,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                session = json.loads(urllib.request.urlopen(base + "/api/session").read())
                self.assertNotIn("labels", session["cases"][0])
                html = urllib.request.urlopen(base + "/").read().decode()
                token = re.search(r'csrf=("[^"]+")', html)
                if token is None:
                    self.fail("CSRF token was not embedded in the workbench page")
                payload = json.dumps({"case_id": "pilot_case_001", "label": "segmentation", "confidence": 0.8, "rationale": "Independent thermal zones."}).encode()
                request = urllib.request.Request(base + "/api/annotations", data=payload, method="POST", headers={"Content-Type": "application/json", "X-CSRF-Token": json.loads(token.group(1))})
                self.assertEqual(201, urllib.request.urlopen(request).status)
                saved = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual("rater_2", saved["rater_id"])
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_server_refuses_non_loopback_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AnnotationWorkbenchError, "loopback"):
                create_server(cases_path=CASES, guide_path=GUIDE, output_path=Path(directory) / "out.jsonl", schema_path=SCHEMA, rater_id="rater", host="0.0.0.0")


if __name__ == "__main__":
    unittest.main()
