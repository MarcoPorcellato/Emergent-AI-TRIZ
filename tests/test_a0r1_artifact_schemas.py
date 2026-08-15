from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.validator import validate


class A0R1ArtifactSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.corpus_schema = json.loads(
            (self.repo_root / "schemas/a0r1-corpus-manifest.schema.json").read_text(encoding="utf-8")
        )
        self.independence_schema = json.loads(
            (self.repo_root / "schemas/a0r1-independence-audit.schema.json").read_text(encoding="utf-8")
        )

    def _valid_corpus_manifest(self) -> dict:
        return {
            "artifact_class": "a0r1-corpus-manifest",
            "protocol_id": "a0-r1-tier-r1-v1.0",
            "protocol_hash": "f" * 64,
            "generator_id": "latent-triz-a0-r1-corpus-v1",
            "generator_source_sha256": "a" * 64,
            "seed": 20260815,
            "deterministic_seed": 20260815,
            "partitions": {
                "calibration_split": "calibration",
                "sealed_split": "sealed",
                "split_field": "split",
            },
            "counts": {
                "total_cases": 96,
                "total_targets": 96,
                "families": 48,
                "domains": 6,
                "calibration_cases": 48,
                "sealed_cases": 48,
            },
            "neutral_domains": [
                "agriculture",
                "energy",
                "manufacturing",
                "medicine",
                "software",
                "transport",
            ],
            "family_integrity": {
                "paired_records_by_family": True,
                "uniform_split_by_family": True,
                "family_split_sha256": "b" * 64,
            },
            "files": {
                "cases_jsonl": {"path": "cases.jsonl", "sha256": "c" * 64, "size": 1234},
                "calibration_targets_jsonl": {
                    "path": "targets/calibration.jsonl",
                    "sha256": "d" * 64,
                    "size": 2345,
                },
                "sealed_targets_jsonl": {
                    "path": "targets/sealed.jsonl",
                    "sha256": "e" * 64,
                    "size": 3456,
                },
            },
            "preregistered_layers": [0, 2, 4, 6],
            "token_sites": ["sentinel", "final_transformation_token", "mean_transformation_span"],
            "views": [
                "problem_only",
                "transformation_only",
                "problem_plus_transformation",
                "problem_plus_solution",
            ],
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "license": "Apache-2.0",
        }

    def _valid_independence_report(self) -> dict:
        return {
            "artifact_class": "a0-r1-independence-audit",
            "protocol_id": "a0-r1-tier-r1-v1.0",
            "status": "pass",
            "ready": True,
            "counts": {
                "candidate": {
                    "cases": 96,
                    "targets": 96,
                    "case_partitions": {"calibration": 48, "sealed": 48},
                },
                "source": {
                    "cases": 192,
                    "targets": 192,
                    "case_partitions": {"calibration": 96, "sealed": 96},
                },
            },
            "partitions": {
                "candidate_split_field": "split",
                "source_split_field": "split",
                "required_partitions": {
                    "candidate": {"calibration": "calibration", "sealed": "sealed"},
                    "source": {"calibration": "calibration", "sealed": "sealed"},
                },
                "candidate_split_values": {
                    "calibration": ["case_a", "case_b"],
                    "sealed": ["case_c"],
                },
                "source_split_values": {"calibration": ["case_d"], "sealed": ["case_e"]},
            },
            "hashes": {
                "candidate_manifest_sha256": "1" * 64,
                "source_manifest_sha256": "2" * 64,
                "candidate_cases_sha256": "3" * 64,
                "candidate_calibration_targets_sha256": "4" * 64,
                "candidate_sealed_targets_sha256": "5" * 64,
                "source_cases_sha256": "6" * 64,
                "source_calibration_targets_sha256": "7" * 64,
                "source_sealed_targets_sha256": "8" * 64,
            },
            "violations": [],
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
        }

    def test_a0r1_corpus_manifest_and_independence_report_validate(self) -> None:
        issues = validate(self._valid_corpus_manifest(), self.corpus_schema)
        self.assertEqual([], issues)

        issues = validate(self._valid_independence_report(), self.independence_schema)
        self.assertEqual([], issues)

    def test_a0r1_schema_rejects_epistemic_envelope_mutation(self) -> None:
        corpus_manifest = self._valid_corpus_manifest()
        corpus_manifest["evidence_eligible"] = True
        issues = validate(corpus_manifest, self.corpus_schema)
        self.assertTrue(issues)

        audit = self._valid_independence_report()
        audit["expert_validated"] = True
        issues = validate(audit, self.independence_schema)
        self.assertTrue(issues)

    def test_a0r1_schema_rejects_bad_hash_count_status_fields(self) -> None:
        corpus_manifest = self._valid_corpus_manifest()
        corpus_manifest["counts"]["total_targets"] = 97
        issues = validate(corpus_manifest, self.corpus_schema)
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("total_targets") for issue in issues))

        manifest_hash_broken = self._valid_corpus_manifest()
        manifest_hash_broken["files"]["cases_jsonl"]["sha256"] = "not-a-sha256"
        issues = validate(manifest_hash_broken, self.corpus_schema)
        self.assertTrue(issues)
        self.assertTrue(any("cases_jsonl.sha256" in issue.path for issue in issues))

        report = self._valid_independence_report()
        report["status"] = "invalid"
        issues = validate(report, self.independence_schema)
        self.assertTrue(issues)
        self.assertTrue(any(issue.path.endswith("status") for issue in issues))

        inconsistent = self._valid_independence_report()
        inconsistent["ready"] = False
        issues = validate(inconsistent, self.independence_schema)
        self.assertTrue(issues)

    def test_a0r1_schema_rejects_unknown_properties(self) -> None:
        corpus_manifest = self._valid_corpus_manifest()
        corpus_manifest["unknown_root_field"] = "forbidden"
        issues = validate(corpus_manifest, self.corpus_schema)
        self.assertTrue(issues)
        self.assertTrue(any("Additional property not allowed" in issue.message for issue in issues))

        audit = self._valid_independence_report()
        audit["unknown_root_property"] = {"foo": "bar"}
        issues = validate(audit, self.independence_schema)
        self.assertTrue(issues)
        self.assertTrue(any("Additional property not allowed" in issue.message for issue in issues))


if __name__ == "__main__":
    unittest.main()
