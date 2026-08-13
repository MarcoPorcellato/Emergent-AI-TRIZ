from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz import lab01_acquire
from latent_triz import lab01_acquisition as acquisition


class Lab01AcquireTests(unittest.TestCase):
    def _write_required_files(self, directory: Path) -> None:
        for filename in acquisition.LAB01_REQUIRED_FILES:
            (directory / filename).write_text(f"{filename}:verified", encoding="utf-8")

    def test_existing_verified_snapshot_emits_stable_json_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            model_root = Path(workdir) / "artifacts/models/pythia-70m-deduped-e93a9faa"
            model_root.mkdir(parents=True)
            self._write_required_files(model_root)

            receipts = acquisition.build_runtime_file_receipts(model_root)
            with patch("latent_triz.lab01_acquire.ensure_lab01_model") as mocked_ensure:
                mocked_ensure.return_value = model_root.resolve()
                output = StringIO()
                with redirect_stdout(output):
                    code = lab01_acquire.main(["--model-root", str(model_root)])

            self.assertEqual(code, 0)
            mocked_ensure.assert_called_once_with(model_root, allow_download=False)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["status"], "integrity_verified")
            self.assertEqual(payload["license_id"], "Apache-2.0")
            self.assertEqual(len(payload["runtime_files"]), 6)
            self.assertNotIn("/private/tmp", output.getvalue())
            self.assertNotIn("/Users/", output.getvalue())

    def test_failure_is_nonzero_and_contains_no_absolute_paths(self) -> None:
        with patch(
            "latent_triz.lab01_acquire.ensure_lab01_model",
            side_effect=acquisition.Lab01AcquisitionError("operator authorization is required"),
        ):
            with patch("builtins.print") as mocked_print:
                code = lab01_acquire.main(["--model-root", "artifacts/models/pythia-70m-deduped-e93a9faa"])

        self.assertEqual(code, 1)
        printed = "\n".join(str(call.args[0]) for call in mocked_print.call_args_list)
        self.assertIn('"status":"fail"', printed)
        self.assertNotIn("/Users/", printed)
        self.assertNotIn("/private/tmp", printed)

    def test_download_requires_explicit_authorization(self) -> None:
        with patch("latent_triz.lab01_acquire.ensure_lab01_model") as mocked_ensure:
            mocked_ensure.return_value = Path("artifacts/models/pythia-70m-deduped-e93a9faa")
            with redirect_stdout(StringIO()):
                lab01_acquire.main(["--model-root", "artifacts/models/pythia-70m-deduped-e93a9faa", "--allow-download"])
            mocked_ensure.assert_called_once_with(
                Path("artifacts/models/pythia-70m-deduped-e93a9faa"),
                allow_download=True,
            )


if __name__ == "__main__":
    unittest.main()
