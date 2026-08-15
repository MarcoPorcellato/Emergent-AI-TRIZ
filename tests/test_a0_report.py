from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0_report import render_a0_report


class A0ReportTests(unittest.TestCase):
    def test_report_preserves_epistemic_boundary_and_hash_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = {
                "artifact_class": "a0-sealed-statistical-result",
                "empirical": True,
                "scientific_status": "exploratory",
                "evidence_eligible": False,
                "expert_validated": False,
                "claim_ids": [],
                "status": "null",
                "protocol_id": "a0-automated-weak-proxy-v1.0.3",
                "max_statistic_p": 1.0,
                "macro_f1_margin_over_surface": 0.0,
                "observed_max_family_successes": 0,
                "interpretation": "No positive signal under the frozen A0 implementation.",
            }
            result_path = root / "statistical-result.json"
            receipt_path = root / "activation-receipt.json"
            index_path = root / "representations-index.jsonl"
            result_path.write_text(json.dumps(result), encoding="utf-8")
            receipt_path.write_text("{}", encoding="utf-8")
            index_path.write_text("", encoding="utf-8")
            report, manifest = render_a0_report(
                result_path=result_path,
                output_dir=root,
                receipt_path=receipt_path,
                index_path=index_path,
            )
            self.assertIn("not expert validation", report.read_text(encoding="utf-8"))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(
                payload["result"]["sha256"],
                hashlib.sha256(result_path.read_bytes()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
