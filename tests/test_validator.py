from __future__ import annotations

import json
import io
import sys
import tempfile
import hashlib
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.cli import main
from latent_triz.validator import validate


class ValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo = Path(__file__).resolve().parents[1]
        cls.schema = json.loads((cls.repo / "schemas/case.schema.json").read_text(encoding="utf-8"))
        cls.valid_case = json.loads((cls.repo / "tests/fixtures/case_valid.json").read_text(encoding="utf-8"))
        cls.study_schema = json.loads((cls.repo / "schemas/study.schema.json").read_text(encoding="utf-8"))
        cls.study_manifest = json.loads((cls.repo / "experiments/000-template/manifest.json").read_text(encoding="utf-8"))
        cls.claim_schema = json.loads((cls.repo / "schemas/claim.schema.json").read_text(encoding="utf-8"))
        cls.claim = json.loads((cls.repo / "data/claims.jsonl").read_text(encoding="utf-8").splitlines()[0])

    def test_valid_nested_case(self) -> None:
        issues = validate(self.valid_case, self.schema)
        self.assertEqual(issues, [])

    def test_invalid_nested_case(self) -> None:
        invalid = dict(self.valid_case)
        invalid["labels"] = [dict(invalid["labels"][0], confidence=-0.1)]
        issues = validate(invalid, self.schema)
        self.assertGreaterEqual(len(issues), 1)
        self.assertTrue(any("below minimum" in issue.message for issue in issues))

    def test_study_manifest_is_valid(self) -> None:
        issues = validate(self.study_manifest, self.study_schema)
        self.assertEqual(issues, [])

    def test_e0_claim_registry_entry_is_valid(self) -> None:
        self.assertEqual(validate(self.claim, self.claim_schema), [])

    def test_e0_claim_cannot_attach_empirical_evidence(self) -> None:
        invalid = dict(self.claim, results=["results/CLM-001-v1.json"])
        issues = validate(invalid, self.claim_schema)
        self.assertTrue(any("maxItems" in issue.message for issue in issues))

    def test_e0_claim_requires_evidence_profile(self) -> None:
        invalid = dict(self.claim)
        invalid.pop("evidence_profile", None)
        issues = validate(invalid, self.claim_schema)
        self.assertTrue(any("Missing required property 'evidence_profile'" in issue.message for issue in issues))

    def test_e0_claim_rejects_malformed_evidence_profile(self) -> None:
        invalid = dict(
            self.claim,
            evidence_profile={
                "behavioral_effect": "no",
                "lexical_controls": False,
                "cross_domain": False,
                "decodable": False,
                "positive_causal_intervention": False,
                "negative_causal_intervention": False,
                "dose_response": False,
                "capability_preserved": False,
                "independent_replication": False,
                "cross_model_replication": False,
                "controlled_training": False,
            },
        )
        issues = validate(invalid, self.claim_schema)
        self.assertTrue(any(
            "Expected type" in issue.message and issue.path == "root.evidence_profile.behavioral_effect"
            for issue in issues
        ))

    def test_e0_claim_must_remain_untested_and_non_empirical(self) -> None:
        invalid = dict(self.claim, status="supported", non_empirical=False)
        issues = validate(invalid, self.claim_schema)
        self.assertEqual(sum("constant" in issue.message for issue in issues), 2)

    def test_empirical_claim_cannot_be_marked_non_empirical(self) -> None:
        invalid = dict(self.claim, evidence_level="E1", non_empirical=True)
        issues = validate(invalid, self.claim_schema)
        self.assertTrue(any("constant" in issue.message for issue in issues))

    def test_empirical_claim_requires_core_evidence_links(self) -> None:
        invalid = dict(self.claim, evidence_level="E3", status="preliminary", non_empirical=False)
        issues = validate(invalid, self.claim_schema)
        self.assertEqual(sum("minItems" in issue.message for issue in issues), 4)

    def test_e4_claim_accepts_well_formed_core_evidence(self) -> None:
        valid = dict(
            self.claim,
            evidence_level="E4",
            status="supported",
            non_empirical=False,
            preregistrations=["preregistrations/CLM-001-v1.md"],
            dataset_snapshots=["data/snapshots/CLM-001-v1.json"],
            experiments=["experiments/CLM-001-v1/manifest.json"],
            results=["results/CLM-001-v1.json"],
        )
        self.assertEqual(validate(valid, self.claim_schema), [])

    def test_e5_claim_requires_replication(self) -> None:
        invalid = dict(
            self.claim,
            evidence_level="E5",
            status="supported",
            non_empirical=False,
            preregistrations=["preregistrations/CLM-001-v1.md"],
            dataset_snapshots=["data/snapshots/CLM-001-v1.json"],
            experiments=["experiments/CLM-001-v1/manifest.json"],
            results=["results/CLM-001-v1.json"],
        )
        issues = validate(invalid, self.claim_schema)
        self.assertTrue(any(issue.path == "root.replications" and "minItems" in issue.message for issue in issues))

    def test_evidence_links_must_be_repository_paths(self) -> None:
        invalid = dict(
            self.claim,
            evidence_level="E1",
            status="preliminary",
            non_empirical=False,
            preregistrations=["trust me"],
            dataset_snapshots=["data/snapshot.json"],
            experiments=["experiments/001/manifest.json"],
            results=["results/001.json"],
        )
        issues = validate(invalid, self.claim_schema)
        self.assertTrue(any(issue.path == "root.preregistrations[0]" and "pattern" in issue.message for issue in issues))

    def test_claims_audit_accepts_current_e0_registry(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(
                [
                    "claims-audit",
                    "--registry",
                    str(self.repo / "data/claims.jsonl"),
                    "--root",
                    str(self.repo),
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(err.getvalue(), "")

    def test_claims_audit_rejects_missing_evidence_file(self) -> None:
        claim = dict(self.claim, results=["results/missing.json"])
        with tempfile.TemporaryDirectory() as workdir:
            registry = Path(workdir) / "claims.jsonl"
            registry.write_text(json.dumps(claim) + "\n", encoding="utf-8")
            err = io.StringIO()
            with redirect_stderr(err):
                code = main(["claims-audit", "--registry", str(registry), "--root", workdir])
        self.assertEqual(code, 1)
        self.assertIn("evidence file not found", err.getvalue())

    def test_jsonl_validation_reports_record(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(
                [
                    "validate",
                    "--schema",
                    str(self.repo / "schemas/case.schema.json"),
                    str(self.repo / "tests/fixtures/case_invalid.jsonl"),
                ]
            )
        self.assertEqual(code, 1)
        err_output = err.getvalue().splitlines()
        self.assertTrue(any(":2:" in line for line in err_output))

    def test_jsonl_malformed_record_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            path = Path(workdir) / "broken.jsonl"
            path.write_text('{"case_id": "case-1"}\n{invalid}\n', encoding="utf-8")
            out = io.StringIO()
            err = io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = main(
                    [
                        "validate",
                        "--schema",
                        str(self.repo / "schemas/case.schema.json"),
                        str(path),
                    ]
                )
            self.assertEqual(code, 1)
            err_output = err.getvalue()
            self.assertIn(":2:", err_output)
            self.assertIn("invalid JSON", err_output)
            self.assertNotIn("Traceback", err_output)

    def test_cli_error_on_missing_schema(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(
                [
                    "validate",
                    "--schema",
                    str(self.repo / "schemas/does-not-exist.schema.json"),
                    str(self.repo / "tests/fixtures/case_valid.json"),
                ]
            )
        self.assertEqual(code, 1)
        self.assertIn("latent-triz:", err.getvalue())

    def test_cli_error_on_invalid_schema_json(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            path = Path(workdir) / "bad.schema"
            path.write_text('{ "type": ', encoding="utf-8")
            out = io.StringIO()
            err = io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = main(
                    [
                        "validate",
                        "--schema",
                        str(path),
                        str(self.repo / "tests/fixtures/case_valid.json"),
                    ]
                )
            self.assertEqual(code, 1)
            self.assertIn("invalid schema JSON", err.getvalue())

    def test_cli_error_on_invalid_json_data(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            path = Path(workdir) / "invalid.json"
            path.write_text("{invalid}", encoding="utf-8")
            out = io.StringIO()
            err = io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = main(
                    [
                        "validate",
                        "--schema",
                        str(self.repo / "schemas/case.schema.json"),
                        str(path),
                    ]
                )
            self.assertEqual(code, 1)
            self.assertIn("invalid JSON", err.getvalue())

    def test_cli_error_on_missing_json_data_is_not_parse_error(self) -> None:
        missing = self.repo / "tests/fixtures/does-not-exist.json"
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(
                [
                    "validate",
                    "--schema",
                    str(self.repo / "schemas/case.schema.json"),
                    str(missing),
                ]
            )
        self.assertEqual(code, 1)
        self.assertIn("data file not found", err.getvalue())
        self.assertNotIn("invalid JSON", err.getvalue())

    def test_date_time_format_validation(self) -> None:
        schema = {"type": "object", "properties": {"created_at": {"type": "string", "format": "date-time"}}, "required": ["created_at"]}
        valid = {"created_at": "2026-08-13T10:15:30Z"}
        invalid = {"created_at": "2026-08-13 10:15:30"}
        invalid_tz = {"created_at": "2026-08-13T10:15:30+01:00"}

        self.assertEqual(validate(valid, schema), [])
        self.assertTrue(any("date-time" in issue.message for issue in validate(invalid, schema)))
        self.assertTrue(any("UTC" in issue.message for issue in validate(invalid_tz, schema)))

    def test_array_schema_behavior(self) -> None:
        schema = {"type": "array", "minItems": 2, "items": {"type": "integer", "minimum": 0}}
        valid = [1, 2, 3]
        too_short = [1]
        wrong_type = ["bad"]
        self.assertEqual(validate(valid, schema), [])
        self.assertTrue(any("minItems" in issue.message for issue in validate(too_short, schema)))
        self.assertTrue(any("Expected type" in issue.message for issue in validate(wrong_type, schema)))

    def test_fingerprint_matches_known_digest(self) -> None:
        expected = hashlib.sha256(b"lab core\n").hexdigest()
        with tempfile.TemporaryDirectory() as workdir:
            path = Path(workdir) / "payload.txt"
            path.write_text("lab core\n", encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["fingerprint", str(path)])
            self.assertEqual(code, 0)
            self.assertEqual(out.getvalue().strip(), expected)


if __name__ == "__main__":
    unittest.main()
