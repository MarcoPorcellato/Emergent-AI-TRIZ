from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.validator import validate


class A0R1PreoutputSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.summary_schema = json.loads(
            (self.root / "schemas/a0r1-preoutput-summary.schema.json").read_text(encoding="utf-8")
        )
        self.manifest_schema = json.loads(
            (self.root / "schemas/a0r1-preoutput-manifest.schema.json").read_text(encoding="utf-8")
        )
        self.valid_summary = json.loads((self.root / "results/a0r1/preoutput/summary.json").read_text(encoding="utf-8"))
        self.valid_manifest = json.loads(
            (self.root / "results/a0r1/preoutput/preoutput-manifest.json").read_text(encoding="utf-8")
        )

    def test_preoutput_summary_and_manifest_validate(self) -> None:
        self.assertEqual([], validate(self.valid_summary, self.summary_schema))
        self.assertEqual([], validate(self.valid_manifest, self.manifest_schema))

    def test_preoutput_summary_rejects_mutated_envelope_and_flags(self) -> None:
        summary = dict(self.valid_summary)
        summary["evidence_eligible"] = True
        issues = validate(summary, self.summary_schema)
        self.assertTrue(issues)

        summary = dict(self.valid_summary)
        summary["model_output_accessed"] = True
        issues = validate(summary, self.summary_schema)
        self.assertTrue(issues)
        self.assertTrue(any("model_output_accessed" in issue.path for issue in issues))

        summary = dict(self.valid_summary)
        summary["protocol_status"] = "frozen"
        summary["status"] = "non_interpretable"
        summary["independence_status"] = "non_interpretable"
        summary["shortcuts_status"] = "non_interpretable"
        self.assertTrue(validate(summary, self.summary_schema))

        summary = dict(self.valid_summary)
        summary["status"] = "failed"
        summary["independence_status"] = "fail"
        summary["independence_ready"] = False
        self.assertEqual([], validate(summary, self.summary_schema))

    def test_preoutput_manifest_rejects_bad_status_and_artifact_hashes(self) -> None:
        manifest = json.loads(json.dumps(self.valid_manifest))
        manifest["status"] = "pending"
        issues = validate(manifest, self.manifest_schema)
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("status") for issue in issues))

        manifest = json.loads(json.dumps(self.valid_manifest))
        manifest["artifacts"]["shortcuts.json"]["sha256"] = "not-a-sha256"
        issues = validate(manifest, self.manifest_schema)
        self.assertTrue(issues)
        self.assertTrue(any("artifacts.shortcuts.json.sha256" in issue.path for issue in issues))

        manifest = json.loads(json.dumps(self.valid_manifest))
        manifest["results"]["independence_status"] = "invalid"
        issues = validate(manifest, self.manifest_schema)
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("results.independence_status") for issue in issues))

    def test_preoutput_summary_manifest_reject_unknown_properties(self) -> None:
        summary = json.loads(json.dumps(self.valid_summary))
        summary["unexpected_top_field"] = "forbidden"
        issues = validate(summary, self.summary_schema)
        self.assertTrue(issues)
        self.assertTrue(any("Additional property not allowed" in issue.message for issue in issues))

        manifest = json.loads(json.dumps(self.valid_manifest))
        manifest["protocol_summary"]["unexpected_nested"] = "forbidden"
        issues = validate(manifest, self.manifest_schema)
        self.assertTrue(issues)
        self.assertTrue(any("protocol_summary" in issue.path for issue in issues))


if __name__ == "__main__":
    unittest.main()
