from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.dataset_snapshot import (
    DatasetSnapshotError,
    run_dataset_snapshot,
    stable_json_dumps,
    verify_dataset_snapshot_manifest,
)
from latent_triz.validator import validate


class DatasetSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.snapshot_schema = json.loads((self.repo_root / "schemas/dataset-snapshot.schema.json").read_text(encoding="utf-8"))
        self.annotation_schema = json.loads((self.repo_root / "schemas/dataset-annotation.schema.json").read_text(encoding="utf-8"))

    def _write_jsonl(self, path: Path, records) -> None:
        text = "\n".join(stable_json_dumps(item) for item in records)
        path.write_text(text + "\n", encoding="utf-8")

    def _write_json(self, path: Path, payload) -> None:
        path.write_text(stable_json_dumps(payload) + "\n", encoding="utf-8")

    def _base_plan(self) -> dict:
        return {
            "plan_version": "v1.0.0",
            "status": "freeze",
            "non_empirical": True,
            "target_size": 4,
            "min_domains": 2,
            "splits": {
                "discovery": {"target_min": 2, "target_exact": 2, "required": True},
                "validation": {"target_min": 1, "target_exact": 1, "required": True},
                "held_out_domain": {"target_min": 1, "target_exact": 1, "required": True},
                "sealed_novel": {"target_min": 0, "target_exact": 0, "required": False},
            },
            "forbidden_lexical_terms": [],
            "required_case_types": ["positive", "control", "matched_negative", "near_miss", "alternative_principle"],
            "source_type_policy": {
                "allowed_source_types": ["human_authored", "adapted", "historical", "model_generated", "synthetic"],
                "max_model_generated_ratio": 1.0,
            },
            "annotation_policy": {
                "minimum_distinct_raters": 2,
                "agreement_threshold": 1.0,
                "enforce_cross_split_source_fingerprints": False,
            },
            "min_cases_per_domain": 1,
            "min_cases_per_principle": 1,
            "enforce_targets": True,
        }

    def _base_cases(self) -> list[dict]:
        return [
            {
                "case_id": "case_001",
                "domain": "manufacturing",
                "split": "discovery",
                "problem": "A spindle is noisy.",
                "constraints": ["budget"],
                "initial_state": "vibration",
                "desired_improvement": "reduce noise",
                "worsening_consequence": "fatigue",
                "transformation": "damping",
                "resulting_state": "quieter",
                "principles": ["segmentation"],
                "provenance": {
                    "source_type": "human_authored",
                    "license": "CC0",
                    "created_at": "2026-08-13",
                    "source_uri": "urn:latent-triz:source:source-001",
                    "template_id": "template-a",
                    "template_version": "v1",
                },
            },
            {
                "case_id": "case_002",
                "domain": "health",
                "split": "discovery",
                "problem": "A pump is unstable.",
                "constraints": ["time"],
                "initial_state": "fluctuation",
                "desired_improvement": "stabilize",
                "worsening_consequence": "downtime",
                "transformation": "calibration",
                "resulting_state": "stable",
                "principles": ["segmentation", "extraction"],
                "provenance": {
                    "source_type": "human_authored",
                    "license": "CC0",
                    "created_at": "2026-08-13",
                    "source_uri": "urn:latent-triz:source:source-002",
                    "template_id": "template-b",
                    "template_version": "v1",
                },
            },
            {
                "case_id": "case_003",
                "domain": "manufacturing",
                "split": "validation",
                "problem": "A lever is rigid.",
                "constraints": ["cost"],
                "initial_state": "hard",
                "desired_improvement": "add flexibility",
                "worsening_consequence": "wear",
                "transformation": "replace bearing",
                "resulting_state": "flexible",
                "principles": ["extraction"],
                "provenance": {
                    "source_type": "human_authored",
                    "license": "CC0",
                    "created_at": "2026-08-13",
                    "source_uri": "urn:latent-triz:source:source-003",
                    "template_id": "template-c",
                    "template_version": "v1",
                },
            },
            {
                "case_id": "case_004",
                "domain": "health",
                "split": "held_out_domain",
                "problem": "A sensor drifts.",
                "constraints": ["safety"],
                "initial_state": "drift",
                "desired_improvement": "stability",
                "worsening_consequence": "alarm",
                "transformation": "filtering",
                "resulting_state": "calm",
                "principles": ["segmentation"],
                "provenance": {
                    "source_type": "human_authored",
                    "license": "CC0",
                    "created_at": "2026-08-13",
                    "source_uri": "urn:latent-triz:source:source-004",
                    "template_id": "template-d",
                    "template_version": "v1",
                },
            },
        ]

    def _base_annotations(self) -> list[dict]:
        return [
            {"annotation_id": "ann_001", "case_id": "case_001", "rater_id": "r1", "label": "A", "non_empirical": True, "annotated_at": "2026-08-13T00:00:00Z"},
            {"annotation_id": "ann_002", "case_id": "case_001", "rater_id": "r2", "label": "A", "non_empirical": True, "annotated_at": "2026-08-13T00:00:00Z"},
            {"annotation_id": "ann_003", "case_id": "case_002", "rater_id": "r1", "label": "B", "non_empirical": True, "annotated_at": "2026-08-13T00:00:00Z"},
            {"annotation_id": "ann_004", "case_id": "case_002", "rater_id": "r2", "label": "B", "non_empirical": True, "annotated_at": "2026-08-13T00:00:00Z"},
            {"annotation_id": "ann_005", "case_id": "case_003", "rater_id": "r1", "label": "A", "non_empirical": True, "annotated_at": "2026-08-13T00:00:00Z"},
            {"annotation_id": "ann_006", "case_id": "case_003", "rater_id": "r2", "label": "A", "non_empirical": True, "annotated_at": "2026-08-13T00:00:00Z"},
            {"annotation_id": "ann_007", "case_id": "case_004", "rater_id": "r1", "label": "C", "non_empirical": True, "annotated_at": "2026-08-13T00:00:00Z"},
            {"annotation_id": "ann_008", "case_id": "case_004", "rater_id": "r2", "label": "C", "non_empirical": True, "annotated_at": "2026-08-13T00:00:00Z"},
        ]

    def _registry_entry(self) -> dict:
        return {
            "dataset_id": "synthetic_lab02",
            "version": "v1.0.0",
            "status": "frozen",
            "artifact_uri": "https://example.org/artifact",
            "sha256": "0" * 64,
            "case_schema_revision": "v1",
            "license": "CC0",
            "created_at": "2026-08-13T00:00:00Z",
        }

    def _registry_manifest(self, registry_entry: dict | None = None) -> dict:
        entry = self._registry_entry() if registry_entry is None else registry_entry
        return {
            "registry_version": "1.0.0",
            "generated_at": "2026-08-13T00:00:00Z",
            "datasets": [entry],
        }

    def _write_registry_artifacts(
        self,
        cases_path: Path,
        registry_entry_path: Path,
        registry_manifest_path: Path,
        registry_entry: dict | None = None,
    ) -> dict:
        entry = self._registry_entry() if registry_entry is None else registry_entry
        entry["sha256"] = hashlib.sha256(cases_path.read_bytes()).hexdigest()
        self._write_json(registry_entry_path, entry)
        self._write_json(registry_manifest_path, self._registry_manifest(entry))
        return entry

    def test_schema_validates_pass_manifest_and_annotation(self) -> None:
        self.assertEqual(validate(self._base_annotations()[0], self.annotation_schema), [])
        manifest = self._build_manifest()
        self.assertEqual(validate(manifest, self.snapshot_schema), [])
        self.assertEqual(manifest["artifact_class"], "dataset-instrumentation")
        self.assertFalse(manifest["empirical"])
        self.assertFalse(manifest["evidence_eligible"])
        self.assertEqual(manifest["claim_ids"], [])

    def _build_manifest(
        self,
        generated_at: str | None = None,
        plan: dict | None = None,
        cases: list[dict] | None = None,
        annotations: list[dict] | None = None,
        fail_closed: bool = True,
    ) -> dict:
        if plan is None:
            plan = self._base_plan()
        with tempfile.TemporaryDirectory() as workdir:
            basedir = Path(workdir)
            cases_path = basedir / "cases.jsonl"
            annotations_path = basedir / "annotations.jsonl"
            plan_path = basedir / "dataset-plan.json"
            registry_entry_path = basedir / "registry-entry.json"
            registry_manifest_path = basedir / "dataset-registry.json"
            cases_payload = self._base_cases() if cases is None else cases
            self._write_jsonl(cases_path, cases_payload)
            annotations_payload = self._base_annotations() if annotations is None else annotations
            self._write_jsonl(annotations_path, annotations_payload)
            self._write_json(plan_path, plan)
            registry_entry = self._registry_entry()
            registry_entry["sha256"] = hashlib.sha256(cases_path.read_bytes()).hexdigest()
            self._write_json(registry_entry_path, registry_entry)
            self._write_json(registry_manifest_path, self._registry_manifest(registry_entry))
            return run_dataset_snapshot(
                cases_path=cases_path,
                annotations_path=annotations_path,
                plan_path=plan_path,
                registry_entry_path=registry_entry_path,
                registry_manifest_path=registry_manifest_path,
                generated_at=generated_at,
                fail_closed=fail_closed,
            )

    def test_pass_fixture_passes_and_verifies(self) -> None:
        manifest = self._build_manifest()
        self.assertEqual(manifest["status"], "pass")
        self.assertTrue(manifest["agreement"]["minimum_met"])
        self.assertEqual(manifest["agreement"]["metric"], "exact_percent_agreement")
        self.assertEqual(manifest["issues"], [])

        with tempfile.TemporaryDirectory() as workdir:
            basedir = Path(workdir)
            cases_path = basedir / "cases.jsonl"
            annotations_path = basedir / "annotations.jsonl"
            plan_path = basedir / "dataset-plan.json"
            registry_entry_path = basedir / "registry-entry.json"
            registry_manifest_path = basedir / "dataset-registry.json"
            self._write_jsonl(cases_path, self._base_cases())
            self._write_jsonl(annotations_path, self._base_annotations())
            self._write_json(plan_path, self._base_plan())
            self._write_registry_artifacts(cases_path, registry_entry_path, registry_manifest_path)

            fresh_manifest = run_dataset_snapshot(
                cases_path=cases_path,
                annotations_path=annotations_path,
                plan_path=plan_path,
                registry_entry_path=registry_entry_path,
                registry_manifest_path=registry_manifest_path,
            )
            self.assertEqual(verify_dataset_snapshot_manifest(manifest=fresh_manifest, cases_path=cases_path, annotations_path=annotations_path, plan_path=plan_path, registry_entry_path=registry_entry_path, registry_manifest_path=registry_manifest_path), [])

    def test_byte_mutation_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            basedir = Path(workdir)
            cases_path = basedir / "cases.jsonl"
            annotations_path = basedir / "annotations.jsonl"
            plan_path = basedir / "dataset-plan.json"
            registry_entry_path = basedir / "registry-entry.json"
            registry_manifest_path = basedir / "dataset-registry.json"
            self._write_jsonl(cases_path, self._base_cases())
            self._write_jsonl(annotations_path, self._base_annotations())
            self._write_json(plan_path, self._base_plan())
            self._write_registry_artifacts(cases_path, registry_entry_path, registry_manifest_path)
            manifest = run_dataset_snapshot(
                cases_path=cases_path,
                annotations_path=annotations_path,
                plan_path=plan_path,
                registry_entry_path=registry_entry_path,
                registry_manifest_path=registry_manifest_path,
            )

            original = cases_path.read_bytes()
            mutated = original.replace(b"manufacturing", b"manufactur1ng", 1)
            cases_path.write_bytes(mutated)
            mismatches = verify_dataset_snapshot_manifest(
                manifest=manifest,
                cases_path=cases_path,
                annotations_path=annotations_path,
                plan_path=plan_path,
                registry_entry_path=registry_entry_path,
                registry_manifest_path=registry_manifest_path,
            )
            self.assertTrue(any(issue["field"] in {"cases_jsonl.sha256", "cases_jsonl.size", "split_membership_digest"} for issue in mismatches))

    def test_split_change_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            basedir = Path(workdir)
            cases_path = basedir / "cases.jsonl"
            annotations_path = basedir / "annotations.jsonl"
            plan_path = basedir / "dataset-plan.json"
            registry_entry_path = basedir / "registry-entry.json"
            registry_manifest_path = basedir / "dataset-registry.json"
            self._write_jsonl(cases_path, self._base_cases())
            self._write_jsonl(annotations_path, self._base_annotations())
            self._write_json(plan_path, self._base_plan())
            self._write_registry_artifacts(cases_path, registry_entry_path, registry_manifest_path)
            manifest = run_dataset_snapshot(
                cases_path=cases_path,
                annotations_path=annotations_path,
                plan_path=plan_path,
                registry_entry_path=registry_entry_path,
                registry_manifest_path=registry_manifest_path,
            )
            cases = self._base_cases()
            cases[0]["split"] = "validation"
            self._write_jsonl(cases_path, cases)

            mismatches = verify_dataset_snapshot_manifest(
                manifest=manifest,
                cases_path=cases_path,
                annotations_path=annotations_path,
                plan_path=plan_path,
                registry_entry_path=registry_entry_path,
                registry_manifest_path=registry_manifest_path,
            )
            self.assertTrue(any(issue["field"] == "split_membership_digest" for issue in mismatches))

    def test_license_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            basedir = Path(workdir)
            cases_path = basedir / "cases.jsonl"
            annotations_path = basedir / "annotations.jsonl"
            plan_path = basedir / "dataset-plan.json"
            registry_entry_path = basedir / "registry-entry.json"
            registry_manifest_path = basedir / "dataset-registry.json"
            cases = self._base_cases()
            cases[0]["provenance"]["license"] = "Apache-2.0"
            self._write_jsonl(cases_path, cases)
            self._write_jsonl(annotations_path, self._base_annotations())
            self._write_json(plan_path, self._base_plan())
            self._write_registry_artifacts(cases_path, registry_entry_path, registry_manifest_path)
            with self.assertRaises(DatasetSnapshotError):
                run_dataset_snapshot(
                    cases_path=cases_path,
                    annotations_path=annotations_path,
                    plan_path=plan_path,
                    registry_entry_path=registry_entry_path,
                    registry_manifest_path=registry_manifest_path,
                )

    def test_inadequate_agreement_fails(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            basedir = Path(workdir)
            cases_path = basedir / "cases.jsonl"
            annotations_path = basedir / "annotations.jsonl"
            plan_path = basedir / "dataset-plan.json"
            registry_entry_path = basedir / "registry-entry.json"
            registry_manifest_path = basedir / "dataset-registry.json"
            annotations = self._base_annotations()
            annotations[1]["label"] = "B"
            self._write_jsonl(cases_path, self._base_cases())
            self._write_jsonl(annotations_path, annotations)
            self._write_json(plan_path, self._base_plan())
            self._write_registry_artifacts(cases_path, registry_entry_path, registry_manifest_path)
            with self.assertRaises(DatasetSnapshotError):
                run_dataset_snapshot(
                    cases_path=cases_path,
                    annotations_path=annotations_path,
                    plan_path=plan_path,
                    registry_entry_path=registry_entry_path,
                    registry_manifest_path=registry_manifest_path,
                )

    def test_cross_case_source_fingerprint_collision(self) -> None:
        plan = self._base_plan()
        plan["annotation_policy"]["enforce_cross_split_source_fingerprints"] = True
        cases = self._base_cases()
        cases[1]["split"] = "validation"
        cases[1]["provenance"]["source_uri"] = cases[0]["provenance"]["source_uri"]
        manifest = self._build_manifest(plan=plan, cases=cases, fail_closed=False)
        self.assertTrue(any(issue["code"] == "cross_split_source_leakage" for issue in manifest["issues"]))

    def test_zero_annotations_case_is_reflected_in_coverage(self) -> None:
        annotations = self._base_annotations()[:-2]
        manifest = self._build_manifest(annotations=annotations, fail_closed=False)
        self.assertEqual(manifest["status"], "fail")
        self.assertEqual(manifest["rater_coverage"]["response_counts"]["case_004"], 0)
        self.assertTrue(any(issue["code"] == "insufficient_raters" and "case_004" in issue["message"] for issue in manifest["issues"]))
        self.assertTrue(any(issue["code"] == "insufficient_raters" for issue in manifest["issues"]))

    def test_cross_split_template_leakage_skipped_when_template_missing(self) -> None:
        plan = self._base_plan()
        plan["annotation_policy"]["enforce_cross_split_source_fingerprints"] = True
        cases = self._base_cases()
        cases[0]["split"] = "validation"
        cases[1]["split"] = "validation"
        cases[2]["split"] = "held_out_domain"
        cases[0]["provenance"].pop("template_id", None)
        cases[0]["provenance"].pop("template_version", None)
        cases[0]["provenance"].pop("template_id", None)
        cases[0]["provenance"].pop("template_version", None)
        cases[1]["provenance"].pop("template_id", None)
        cases[1]["provenance"].pop("template_version", None)
        cases[2]["provenance"].pop("template_id", None)
        cases[2]["provenance"].pop("template_version", None)
        manifest = self._build_manifest(plan=plan, cases=cases, fail_closed=False)
        self.assertFalse(any(issue["code"] == "cross_split_template_leakage" for issue in manifest["issues"]))

    def test_manifest_includes_provenance_distributions(self) -> None:
        cases = self._base_cases()
        cases[0]["provenance"]["source_type"] = "adapted"
        cases[0]["provenance"]["source_uri"] = "urn:latent-triz:source:case-001-adapted"
        cases[1]["provenance"]["source_type"] = "model_generated"
        cases[1]["provenance"]["source_uri"] = "urn:latent-triz:source:case-002-model"
        cases[2]["provenance"]["source_type"] = "human_authored"
        manifest = self._build_manifest(cases=cases, fail_closed=False)
        counts = manifest["counts"]
        self.assertEqual(counts["by_source_type"]["human_authored"], 2)
        self.assertEqual(counts["by_source_type"]["adapted"], 1)
        self.assertEqual(counts["by_source_type"]["model_generated"], 1)
        self.assertEqual(counts["by_license"]["CC0"], 4)
        repeat = self._build_manifest(cases=cases, fail_closed=False)
        self.assertEqual(manifest["counts"]["by_source_type"], repeat["counts"]["by_source_type"])
        self.assertEqual(manifest["counts"]["by_license"], repeat["counts"]["by_license"])

    def test_deterministic_manifest_generation(self) -> None:
        manifest_a = self._build_manifest(generated_at="2026-08-13T00:00:00Z")
        manifest_b = self._build_manifest(generated_at="2026-08-13T00:00:00Z")
        self.assertEqual(manifest_a["dataset_id"], manifest_b["dataset_id"])
        self.assertEqual(manifest_a["generated_at"], manifest_b["generated_at"])
        self.assertEqual(manifest_a["immutable_revision"], manifest_b["immutable_revision"])
        self.assertEqual(manifest_a["split_membership_digest"], manifest_b["split_membership_digest"])
        for artifact in ("cases_jsonl", "annotations_jsonl", "registry_entry", "registry_manifest"):
            self.assertEqual({k: v for k, v in manifest_a["artifacts"][artifact].items() if k != "path"}, {k: v for k, v in manifest_b["artifacts"][artifact].items() if k != "path"})
        self.assertEqual(manifest_a["artifacts"]["cases_jsonl"]["path"], "cases.jsonl")
        self.assertEqual(manifest_a["artifacts"]["annotations_jsonl"]["path"], "annotations.jsonl")

    def test_registry_cases_hash_mismatch_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            basedir = Path(workdir)
            cases_path = basedir / "cases.jsonl"
            annotations_path = basedir / "annotations.jsonl"
            plan_path = basedir / "dataset-plan.json"
            registry_entry_path = basedir / "registry-entry.json"
            registry_manifest_path = basedir / "dataset-registry.json"
            self._write_jsonl(cases_path, self._base_cases())
            self._write_jsonl(annotations_path, self._base_annotations())
            self._write_json(plan_path, self._base_plan())
            bad_registry_entry = self._registry_entry()
            bad_registry_entry["sha256"] = "a" * 64
            self._write_json(registry_entry_path, bad_registry_entry)
            self._write_json(registry_manifest_path, self._registry_manifest(bad_registry_entry))

            manifest = run_dataset_snapshot(
                cases_path=cases_path,
                annotations_path=annotations_path,
                plan_path=plan_path,
                registry_entry_path=registry_entry_path,
                registry_manifest_path=registry_manifest_path,
                fail_closed=False,
            )
            self.assertTrue(any(issue["code"] == "registry_cases_hash_mismatch" for issue in manifest["issues"]))

    def test_synthetic_source_uri_is_accepted(self) -> None:
        cases = self._base_cases()
        cases[0]["provenance"]["source_type"] = "synthetic"
        cases[0]["provenance"]["source_uri"] = "urn:latent-triz:synthetic:case_001"
        manifest = self._build_manifest(cases=cases, fail_closed=False)
        self.assertFalse(any(issue["code"] == "invalid_provenance" and "source_uri" in issue["message"] for issue in manifest["issues"]))

    def test_split_target_issues_have_stable_order(self) -> None:
        plan = self._base_plan()
        for split in ("discovery", "validation", "held_out_domain", "sealed_novel"):
            plan["splits"][split]["target_min"] = 99
        manifest = self._build_manifest(plan=plan, fail_closed=False)
        split_messages = [
            issue["message"]
            for issue in manifest["issues"]
            if issue["code"] == "split_target_min"
        ]
        self.assertEqual(
            [message.split(":", 1)[0] for message in split_messages],
            ["discovery", "validation", "held_out_domain", "sealed_novel"],
        )

    def test_agreement_and_schema_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            basedir = Path(workdir)
            ann = {
                "annotation_id": "ann_001",
                "case_id": "case_001",
                "rater_id": "r1",
                "label": "A",
                "non_empirical": True,
                "annotated_at": "2026-08-13T00:00:00Z",
            }
            self.assertEqual(validate(ann, self.annotation_schema), [])
