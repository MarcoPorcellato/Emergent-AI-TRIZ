from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.cli import main
from latent_triz.docs import audit_docs, load_profile


class DocsAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(__file__).resolve().parents[1]

    def test_docs_audit_passes_for_fixture_profile(self) -> None:
        profile = load_profile(str(self.repo / "tests/fixtures/docs/conformant/profile.toml"))
        issues = audit_docs(profile, self.repo / "tests/fixtures/docs/conformant", date.fromisoformat("2026-08-13"))
        self.assertEqual(issues, [])

    def test_cli_docs_audit_no_findings_returns_zero(self) -> None:
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(
                [
                    "docs-audit",
                    "--profile",
                    str(self.repo / "tests/fixtures/docs/conformant/profile.toml"),
                    "--root",
                    str(self.repo / "tests/fixtures/docs/conformant"),
                    "--as-of-date",
                    "2026-08-13",
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(err.getvalue(), "")

    def test_load_profile_rejects_absolute_entry_point(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            profile = Path(workdir) / "profile.toml"
            profile.write_text(
                """
[okf]
required_fields = ["type", "title", "description", "status", "last_verified"]
max_verification_age_days = 180
entry_points = ["/docs/README.md"]
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "absolute entry point"):
                load_profile(str(profile))

    def test_load_profile_rejects_root_escape_entry_point(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            profile = Path(workdir) / "profile.toml"
            profile.write_text(
                """
[okf]
required_fields = ["type", "title", "description", "status", "last_verified"]
max_verification_age_days = 180
entry_points = ["../docs/README.md"]
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "entry point escapes docs root"):
                load_profile(str(profile))

    def test_load_profile_rejects_non_markdown_entry_point(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            profile = Path(workdir) / "profile.toml"
            profile.write_text(
                """
[okf]
required_fields = ["type", "title", "description", "status", "last_verified"]
max_verification_age_days = 180
entry_points = ["docs/README.txt"]
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "must be Markdown"):
                load_profile(str(profile))

    def test_load_profile_rejects_zero_or_negative_max_verification_age(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            profile = Path(workdir) / "profile.toml"
            profile.write_text(
                """
[okf]
required_fields = ["type", "title", "description", "status", "last_verified"]
max_verification_age_days = 0
entry_points = ["docs/README.md"]
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "greater than 0"):
                load_profile(str(profile))

    def test_load_profile_accepts_legacy_max_age_days(self) -> None:
        legacy_path = self.repo / "tests/fixtures/docs/fail_stale_last_verified/profile.toml"
        profile = load_profile(str(legacy_path))
        self.assertEqual(profile.max_age_days, 1)

    def test_missing_frontmatter_is_reported(self) -> None:
        profile = load_profile(str(self.repo / "tests/fixtures/docs/fail_missing_frontmatter/profile.toml"))
        issues = audit_docs(profile, self.repo / "tests/fixtures/docs/fail_missing_frontmatter", date.fromisoformat("2026-08-13"))
        self.assertTrue(any(issue.code == "DOCS_MISSING_FRONTMATTER" for issue in issues))

    def test_unterminated_frontmatter_is_reported(self) -> None:
        profile = load_profile(str(self.repo / "tests/fixtures/docs/fail_unterminated_frontmatter/profile.toml"))
        issues = audit_docs(profile, self.repo / "tests/fixtures/docs/fail_unterminated_frontmatter", date.fromisoformat("2026-08-13"))
        self.assertTrue(any(issue.code == "DOCS_UNTERMINATED_FRONTMATTER" for issue in issues))

    def test_missing_required_field_is_reported(self) -> None:
        profile = load_profile(str(self.repo / "tests/fixtures/docs/fail_missing_required_field/profile.toml"))
        issues = audit_docs(profile, self.repo / "tests/fixtures/docs/fail_missing_required_field", date.fromisoformat("2026-08-13"))
        self.assertTrue(any(issue.code == "DOCS_MISSING_FIELD" for issue in issues))

    def test_invalid_last_verified_is_reported(self) -> None:
        profile = load_profile(str(self.repo / "tests/fixtures/docs/fail_invalid_last_verified/profile.toml"))
        issues = audit_docs(profile, self.repo / "tests/fixtures/docs/fail_invalid_last_verified", date.fromisoformat("2026-08-13"))
        self.assertTrue(any(issue.code == "DOCS_LAST_VERIFIED_FORMAT" for issue in issues))

    def test_future_last_verified_is_reported(self) -> None:
        profile = load_profile(str(self.repo / "tests/fixtures/docs/fail_future_last_verified/profile.toml"))
        issues = audit_docs(profile, self.repo / "tests/fixtures/docs/fail_future_last_verified", date.fromisoformat("2026-08-13"))
        self.assertTrue(any(issue.code == "DOCS_LAST_VERIFIED_FUTURE" for issue in issues))

    def test_stale_last_verified_is_reported(self) -> None:
        profile = load_profile(str(self.repo / "tests/fixtures/docs/fail_stale_last_verified/profile.toml"))
        issues = audit_docs(profile, self.repo / "tests/fixtures/docs/fail_stale_last_verified", date.fromisoformat("2026-08-13"))
        self.assertTrue(any(issue.code == "DOCS_LAST_VERIFIED_STALE" for issue in issues))

    def test_missing_link_target_is_reported(self) -> None:
        profile = load_profile(str(self.repo / "tests/fixtures/docs/fail_missing_target/profile.toml"))
        issues = audit_docs(profile, self.repo / "tests/fixtures/docs/fail_missing_target", date.fromisoformat("2026-08-13"))
        self.assertTrue(any(issue.code == "DOCS_LINK_TARGET_MISSING" for issue in issues))

    def test_missing_anchor_is_reported(self) -> None:
        profile = load_profile(str(self.repo / "tests/fixtures/docs/fail_missing_anchor/profile.toml"))
        issues = audit_docs(profile, self.repo / "tests/fixtures/docs/fail_missing_anchor", date.fromisoformat("2026-08-13"))
        self.assertTrue(any(issue.code == "DOCS_LINK_ANCHOR_MISSING" for issue in issues))

    def test_root_escape_is_reported(self) -> None:
        profile = load_profile(str(self.repo / "tests/fixtures/docs/fail_root_escape/profile.toml"))
        issues = audit_docs(profile, self.repo / "tests/fixtures/docs/fail_root_escape", date.fromisoformat("2026-08-13"))
        self.assertTrue(any(issue.code == "DOCS_ROOT_ESCAPE" for issue in issues))

    def test_missing_entry_point_directory_counts_missing_entry(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            root = Path(workdir)
            entry_dir = root / "docs"
            entry_dir.mkdir()
            (entry_dir / "README.md").mkdir()
            profile_path = root / "profile.toml"
            profile_path.write_text(
                """
[okf]
required_fields = ["type", "title", "description", "status", "last_verified"]
max_verification_age_days = 10
entry_points = ["docs/README.md"]
""",
                encoding="utf-8",
            )
            profile = load_profile(str(profile_path))
            issues = audit_docs(profile, root, date.fromisoformat("2026-08-13"))
            self.assertTrue(any(issue.code == "PROFILE_MISSING_ENTRY" for issue in issues))

    def test_duplicate_canonical_type_is_reported(self) -> None:
        profile = load_profile(str(self.repo / "tests/fixtures/docs/fail_duplicate_type/profile.toml"))
        issues = audit_docs(profile, self.repo / "tests/fixtures/docs/fail_duplicate_type", date.fromisoformat("2026-08-13"))
        self.assertTrue(any(issue.code == "DOCS_DUP_CANONICAL_TYPE" for issue in issues))

    def test_cli_command_returns_findings_and_formats_codes(self) -> None:
        errors = io.StringIO()
        with redirect_stderr(errors):
            code = main(
                [
                    "docs-audit",
                    "--profile",
                    str(self.repo / "tests/fixtures/docs/fail_missing_frontmatter/profile.toml"),
                    "--root",
                    str(self.repo / "tests/fixtures/docs/fail_missing_frontmatter"),
                    "--as-of-date",
                    "2026-08-13",
                ]
            )
        self.assertEqual(code, 1)
        out = errors.getvalue()
        self.assertIn("DOCS_MISSING_FRONTMATTER", out)

    def test_cli_docs_audit_broken_profile_is_clean_error(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            profile = Path(workdir) / "profile.toml"
            profile.write_text("{ required_fields = [ ", encoding="utf-8")
            errors = io.StringIO()
            with redirect_stderr(errors):
                code = main(
                    [
                        "docs-audit",
                        "--profile",
                        str(profile),
                        "--root",
                        str(self.repo),
                        "--as-of-date",
                        "2026-08-13",
                    ]
                )
            err = errors.getvalue()
            self.assertEqual(code, 1)
            self.assertIn("invalid profile", err)
            self.assertNotIn("Traceback", err)

    def test_cli_docs_audit_missing_profile_is_clean_error(self) -> None:
        missing = self.repo / "tests/fixtures/docs/does-not-exist.toml"
        errors = io.StringIO()
        with redirect_stderr(errors):
            code = main(
                [
                    "docs-audit",
                    "--profile",
                    str(missing),
                    "--root",
                    str(self.repo),
                    "--as-of-date",
                    "2026-08-13",
                ]
            )
        err = errors.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("invalid profile", err)
        self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
