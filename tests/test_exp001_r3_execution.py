import json
import tempfile
import unittest
from pathlib import Path
from shutil import copytree

from latent_triz.exp001_r3_execution import (
    Exp001ExecutionPreflightError,
    MODEL_ID,
    MODEL_REVISION,
    preflight,
)


ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = {
    "status": "authorized",
    "model_id": MODEL_ID,
    "revision": MODEL_REVISION,
    "one_run": True,
}


def _copy_repo() -> Path:
    temp = Path(tempfile.mkdtemp(prefix="exp001-r3-preflight-"))
    destination = temp / "repo"
    copytree(ROOT, destination, ignore=lambda _path, names: {".git", ".venv", "__pycache__"}.intersection(names))
    return destination


def _edit_protocol(repo: Path, status: str) -> None:
    path = repo / "experiments/exp001-reference-integrated/protocol.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["protocol_status"] = status
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class Exp001ExecutionPreflightTests(unittest.TestCase):
    def test_module_has_no_ml_runtime_imports(self):
        source = (ROOT / "src/latent_triz/exp001_r3_execution.py").read_text(encoding="utf-8")
        self.assertNotIn("import torch", source)
        self.assertNotIn("import transformers", source)

    def test_current_review_protocol_fails_closed(self):
        with self.assertRaises(Exp001ExecutionPreflightError):
            preflight(ROOT, AUTHORIZATION)

    def test_frozen_authorized_boundary_passes_without_model_or_target(self):
        repo = _copy_repo()
        _edit_protocol(repo, "frozen")
        result = preflight(repo, AUTHORIZATION)
        self.assertEqual(result["status"], "ready_for_material_execution")
        self.assertEqual(result["primary_records"], 72)
        self.assertFalse(result["model_or_target_accessed"])

    def test_non_authorized_status_fails_closed(self):
        repo = _copy_repo()
        _edit_protocol(repo, "frozen")
        authorization = {**AUTHORIZATION, "status": "approval_requested"}
        with self.assertRaises(Exp001ExecutionPreflightError):
            preflight(repo, authorization)

    def test_wrong_revision_fails_closed(self):
        repo = _copy_repo()
        _edit_protocol(repo, "frozen")
        authorization = {**AUTHORIZATION, "revision": "0" * 40}
        with self.assertRaises(Exp001ExecutionPreflightError):
            preflight(repo, authorization)

    def test_multiple_runs_fail_closed(self):
        repo = _copy_repo()
        _edit_protocol(repo, "frozen")
        authorization = {**AUTHORIZATION, "one_run": False}
        with self.assertRaises(Exp001ExecutionPreflightError):
            preflight(repo, authorization)

    def test_mutated_integrity_identity_fails_closed(self):
        repo = _copy_repo()
        _edit_protocol(repo, "frozen")
        path = repo / "results/a0r2/preexecution/smollm2-360m-f8027fd0/integrity-receipt.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["model"]["revision"] = "0" * 40
        path.write_text(json.dumps(value) + "\n", encoding="utf-8")
        with self.assertRaises(Exp001ExecutionPreflightError):
            preflight(repo, AUTHORIZATION)

    def test_mutated_feasibility_status_fails_closed(self):
        repo = _copy_repo()
        _edit_protocol(repo, "frozen")
        path = repo / "results/a0r2/preexecution/smollm2-360m-f8027fd0/feasibility-receipt.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["status"] = "incompatible"
        path.write_text(json.dumps(value) + "\n", encoding="utf-8")
        with self.assertRaises(Exp001ExecutionPreflightError):
            preflight(repo, AUTHORIZATION)


if __name__ == "__main__":
    unittest.main()
