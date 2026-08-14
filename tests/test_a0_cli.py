from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.cli import main


class A0CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.protocol = self.repo_root / "experiments/a0-automated-weak-proxy/protocol.json"

    def test_a0_corpus_cli_generates_manifest_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            output_dir = Path(workdir) / "a0"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(
                    [
                        "a0-corpus",
                        "--protocol",
                        str(self.protocol),
                        "--output-dir",
                        str(output_dir),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(stderr.getvalue(), "")
            manifest = json.loads(stdout.getvalue())
            self.assertEqual(manifest["artifact_class"], "a0-corpus-manifest")
            self.assertEqual(manifest["protocol_id"], "a0-automated-weak-proxy-v1.0.1")
            self.assertEqual(manifest["counts"]["families"], 96)
            self.assertEqual(manifest["counts"]["total_cases"], 192)
            self.assertEqual(manifest["counts"]["total_targets"], 192)
            self.assertGreater(manifest["counts"]["sealed_cases"], 0)
            self.assertTrue((output_dir / "manifest.json").is_file())
            self.assertTrue((output_dir / "cases.jsonl").is_file())
            self.assertTrue((output_dir / "procedural-targets" / "targets.jsonl").is_file())

    def test_a0_corpus_cli_refuses_existing_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            output_dir = Path(workdir) / "a0"
            output_dir.mkdir()
            (output_dir / "sentinel").write_text("preserve", encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(
                    [
                        "a0-corpus",
                        "--protocol",
                        str(self.protocol),
                        "--output-dir",
                        str(output_dir),
                    ]
                )
            self.assertEqual(code, 1)
            self.assertIn("output directory already exists", stderr.getvalue())
            self.assertEqual((output_dir / "sentinel").read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__":
    unittest.main()
