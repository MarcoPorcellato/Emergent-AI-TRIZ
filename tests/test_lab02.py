from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import latent_triz.lab02 as lab02


class Lab02Tests(unittest.TestCase):
    def _write_file(self, path: Path, payload: str) -> None:
        path.write_text(payload, encoding="utf-8")

    def _stable(self, payload: object) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def _build_dataset_report(self) -> dict:
        return {
            "mode": "freeze",
            "status": "pass",
            "total_cases": 4,
            "target_gaps": [],
            "issues": [],
            "targets": {
                "discovery": {"target_min": 2},
                "validation": {"target_min": 1},
                "held_out_domain": {"target_min": 1},
                "sealed_novel": {"target_min": 0},
            },
            "structural_ok": True,
        }

    def _build_snapshot_manifest(self, *, minimum_raters: int = 2, agreement_met: bool = True, extra_issues: list[dict] | None = None, evidence_eligible: bool = False, claim_ids: list[str] | None = None, evidence_payload: dict | None = None, non_empirical: bool = False) -> dict:
        if extra_issues is None:
            extra_issues = []
        if claim_ids is None:
            claim_ids = []
        if evidence_payload is None:
            evidence_payload = {}
        base = {
            "artifact_class": "dataset-instrumentation",
            "empirical": False,
            "evidence_eligible": evidence_eligible,
            "claim_ids": claim_ids,
            "dataset_id": "synthetic_lab02",
            "snapshot_id": "v1.0.0",
            "generated_at": "2026-08-13T00:00:00Z",
            "immutable_revision": "sha256:" + "0" * 64,
            "artifacts": {
                "cases_jsonl": {"path": "cases.jsonl", "sha256": "a" * 64, "size": 10},
                "annotations_jsonl": {"path": "annotations.jsonl", "sha256": "b" * 64, "size": 10},
                "registry_entry": {"sha256": "c" * 64, "size": 10},
                "registry_manifest": {"sha256": "d" * 64, "size": 10},
            },
            "counts": {
                "total_cases": 4,
                "by_split": {
                    "discovery": 2,
                    "validation": 1,
                    "held_out_domain": 1,
                    "sealed_novel": 0,
                },
                "by_domain": {"manufacturing": 2, "health": 2},
                "by_principle": {"segmentation": 2, "inversion": 2},
            },
            "split_membership_digest": "sha256:" + "f" * 64,
            "source_fingerprints": [
                {"case_id": "case_001", "split": "discovery", "fingerprint": "sha256:11", "source_type": "human_authored", "license": "CC0"},
                {"case_id": "case_002", "split": "discovery", "fingerprint": "sha256:12", "source_type": "human_authored", "license": "CC0"},
                {"case_id": "case_003", "split": "validation", "fingerprint": "sha256:13", "source_type": "human_authored", "license": "CC0"},
                {"case_id": "case_004", "split": "held_out_domain", "fingerprint": "sha256:14", "source_type": "human_authored", "license": "CC0"},
            ],
            "template_fingerprints": [
                {"case_id": "case_001", "split": "discovery", "fingerprint": "sha256:21"},
                {"case_id": "case_002", "split": "discovery", "fingerprint": "sha256:22"},
                {"case_id": "case_003", "split": "validation", "fingerprint": "sha256:23"},
                {"case_id": "case_004", "split": "held_out_domain", "fingerprint": "sha256:24"},
            ],
            "rater_coverage": {
                "minimum_distinct_raters": minimum_raters,
                "response_counts": {
                    "case_001": 2,
                    "case_002": 2,
                    "case_003": 2,
                    "case_004": 2,
                },
                "distinct_raters": ["r1", "r2"],
            },
            "agreement": {
                "metric": "exact_percent_agreement",
                "threshold": 0.8,
                "overall": 1.0 if agreement_met else 0.5,
                "minimum_met": agreement_met,
                "per_case": {"case_001": 1.0, "case_002": 1.0, "case_003": 1.0, "case_004": 1.0},
            },
            "status": "pass",
            "issues": extra_issues,
        }
        base.update(evidence_payload)
        return base

    def test_lab02_pass_report_writes_html_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            cases = Path(workdir) / "cases.jsonl"
            annotations = Path(workdir) / "annotations.jsonl"
            self._write_file(cases, "{}\n")
            self._write_file(annotations, "{}\n")
            self._write_file(workdir_path := Path(workdir) / "dataset_audit.json", json.dumps(self._build_dataset_report()))
            self._write_file(workdir_path := Path(workdir) / "snapshot.json", json.dumps(self._build_snapshot_manifest()))

            output_html = Path(workdir) / "lab02.html"
            output_summary = Path(workdir) / "lab02.json"
            dataset_report = self._build_dataset_report()
            snapshot_report = self._build_snapshot_manifest()
            # replace placeholder hashes with actual deterministic file hashes for D3 completeness.
            snapshot_report["artifacts"]["cases_jsonl"]["sha256"] = self._stable(json.dumps(self._build_dataset_report()))
            snapshot_report["artifacts"]["cases_jsonl"]["size"] = len("{}\n".encode("utf-8"))

            with self.subTest("file-backed payloads include hashes"):
                summary = lab02.build_lab02_report(
                    dataset_audit_report=self._build_dataset_report(),
                    snapshot_verification_report=snapshot_report,
                    output_html=output_html,
                    output_summary=output_summary,
                )

                html = output_html.read_text(encoding="utf-8")
                saved_summary = json.loads(output_summary.read_text(encoding="utf-8"))

                self.assertEqual(summary, saved_summary)
                self.assertTrue(output_html.is_file())
                self.assertTrue(output_summary.is_file())
                self.assertIn("No TRIZ claim is made", html)
                self.assertIn("Latent TRIZ Lab 02", html)
                self.assertEqual(summary["status"], "pass")
                self.assertEqual(summary["artifact_class"], "dataset-anatomy")
                self.assertFalse(summary["evidence_eligible"])
                self.assertEqual(summary["claim_ids"], [])
                self.assertEqual(summary["pilot_profile"]["synthetic"], True)
                self.assertEqual(summary["pilot_profile"]["non_empirical"], True)

    def test_lab02_detects_failing_gates(self) -> None:
        dataset_report = self._build_dataset_report()
        dataset_report["target_gaps"] = [
            {"split": "discovery", "metric": "split_target_min", "actual": 1, "target": 2}
        ]
        snapshot_report = self._build_snapshot_manifest(
            extra_issues=[{"code": "license_mismatch", "field": "provenance.license", "message": "license mismatch"}]
        )
        snapshot_report["issues"].append({
            "code": "duplicate_signature",
            "field": "signature",
            "message": "duplicate signature in dataset",
        })
        summary = lab02.build_lab02_report(
            dataset_audit_report=dataset_report,
            snapshot_verification_report=snapshot_report,
        )
        self.assertEqual(summary["status"], "fail")
        self.assertEqual(next(item["status"] for item in summary["gates"] if item["gate"] == "D2"), "fail")
        self.assertEqual(next(item["status"] for item in summary["gates"] if item["gate"] == "D5"), "fail")
        self.assertEqual(next(item["status"] for item in summary["gates"] if item["gate"] == "D6"), "fail")
        self.assertEqual(next(item["status"] for item in summary["gates"] if item["gate"] == "D7"), "pass")
        self.assertIn("license_mismatch", " ".join(item["details"] for item in summary["gates"] if item["gate"] == "D2"))
        self.assertIn("duplicate_signature", summary["findings"]["issue_codes"])

    def test_lab02_deterministic_render(self) -> None:
        dataset_report = self._build_dataset_report()
        snapshot_report = self._build_snapshot_manifest()
        with tempfile.TemporaryDirectory() as workdir:
            first_html = Path(workdir) / "first.html"
            first_summary = Path(workdir) / "first_summary.json"
            second_html = Path(workdir) / "second.html"
            second_summary = Path(workdir) / "second_summary.json"
            summary1 = lab02.build_lab02_report(
                dataset_audit_report=dataset_report,
                snapshot_verification_report=snapshot_report,
                output_html=first_html,
                output_summary=first_summary,
            )
            summary2 = lab02.build_lab02_report(
                dataset_audit_report=dataset_report,
                snapshot_verification_report=snapshot_report,
                output_html=second_html,
                output_summary=second_summary,
            )
            html1 = first_html.read_text(encoding="utf-8")
            html2 = second_html.read_text(encoding="utf-8")
            self.assertEqual(html1, html2)
            payload1 = json.loads(first_summary.read_text(encoding="utf-8"))
            payload2 = json.loads(second_summary.read_text(encoding="utf-8"))
            payload1.pop("summary_artifacts", None)
            payload2.pop("summary_artifacts", None)
            self.assertEqual(payload1, payload2)

    def test_lab02_enforces_no_claim_boundary(self) -> None:
        dataset_report = self._build_dataset_report()
        snapshot_report = self._build_snapshot_manifest(
            agreement_met=False,
            evidence_eligible=True,
            claim_ids=["CLM-001"],
            evidence_payload={"empirical": True},
        )
        summary = lab02.build_lab02_report(
            dataset_audit_report=dataset_report,
            snapshot_verification_report=snapshot_report,
        )
        self.assertEqual(summary["status"], "fail")
        self.assertEqual(summary["pilot_profile"]["claim_ids"], [])
        self.assertEqual(summary["pilot_profile"]["evidence_eligible"], False)
        self.assertEqual(next(item["status"] for item in summary["gates"] if item["gate"] == "D8"), "fail")


if __name__ == "__main__":
    unittest.main()
