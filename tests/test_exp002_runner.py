import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from latent_triz.exp002_runner import Exp002RunnerError, run_exp002_stage


ROOT = Path(__file__).resolve().parents[1]


class _FakeAdapter:
    model_loaded = True


def _dossier():
    return json.loads((ROOT / "experiments/exp002-qwen3-followup/approval-dossier.json").read_text(encoding="utf-8"))


class Exp002RunnerTests(unittest.TestCase):
    def test_authorization_and_gate_fail_before_scorer(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(Exp002RunnerError):
                run_exp002_stage(
                    root=directory,
                    run_id="exp002-qwen3-a",
                    study_id="EXP-002A",
                    model_id="Qwen/Qwen3-0.6B-Base",
                    revision="da87bfb608c14b7cf20ba1ce41287e8de496c0cd",
                    dossier={"status": "approval_requested"},
                    ccp_gate={"decision": "admit", "active": False, "queue_count": 0},
                    public_rows=[{"record_id": "r1", "prompt": "x"}],
                    scorer=lambda prompt: calls.append(prompt) or {"A": 0, "B": 0, "C": 0, "D": 0},
                    target_reader=lambda rows: [],
                    analysis=lambda rows, reader: {"status": "null"},
                    adapter=_FakeAdapter(),
                )
        self.assertEqual(calls, [])

    def test_one_shot_boundary_and_immutable_package(self):
        target_reads = []
        with tempfile.TemporaryDirectory() as directory:
            result = run_exp002_stage(
                root=directory,
                run_id="exp002-qwen3-a",
                study_id="EXP-002A",
                model_id="Qwen/Qwen3-0.6B-Base",
                revision="da87bfb608c14b7cf20ba1ce41287e8de496c0cd",
                dossier=_dossier(),
                ccp_gate={"decision": "admit", "active": False, "queue_count": 0},
                public_rows=[{"record_id": "r1", "prompt": "x"}],
                scorer=lambda prompt: {"A": 1, "B": 0, "C": -1, "D": -2},
                target_reader=lambda rows: target_reads.append(rows) or [{"record_id": "r1", "expected": "A"}],
                analysis=lambda rows, reader: {"status": "null", "target_count": len(reader())},
                adapter=_FakeAdapter(),
            )
            self.assertEqual(result["status"], "null")
            self.assertEqual(len(target_reads), 1)
            package = Path(directory) / result["package"]
            self.assertTrue((package / "publication-manifest.json").is_file())
            self.assertEqual(json.loads((package / "execution-receipt.json").read_text())["access"]["target_reads"], 1)
            for schema_name, artifact_name in (
                ("exp002-execution-receipt.schema.json", "execution-receipt.json"),
                ("exp002-statistical-result.schema.json", "statistical-result.json"),
                ("exp002-response-index.schema.json", "response-index.json"),
                ("exp002-sealed-key-access.schema.json", "sealed-key-access.json"),
                ("exp002-recovery-observation.schema.json", "recovery-observation.json"),
                ("exp002-publication-manifest.schema.json", "publication-manifest.json"),
            ):
                schema = json.loads((ROOT / "schemas" / schema_name).read_text())
                instance = json.loads((package / artifact_name).read_text())
                self.assertEqual(list(Draft202012Validator(schema).iter_errors(instance)), [], schema_name)
            with self.assertRaises(Exp002RunnerError):
                run_exp002_stage(
                    root=directory,
                    run_id="exp002-qwen3-a",
                    study_id="EXP-002A",
                    model_id="Qwen/Qwen3-0.6B-Base",
                    revision="da87bfb608c14b7cf20ba1ce41287e8de496c0cd",
                    dossier=_dossier(),
                    ccp_gate={"resource_decision": "admit", "admission_active": False, "queue_count": 0},
                    public_rows=[{"record_id": "r1", "prompt": "x"}],
                    scorer=lambda prompt: {"A": 1, "B": 0, "C": -1, "D": -2},
                    target_reader=lambda rows: [],
                    analysis=lambda rows, reader: {"status": "null"},
                    adapter=_FakeAdapter(),
                )


if __name__ == "__main__":
    unittest.main()
