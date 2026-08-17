import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from latent_triz.exp001_r3_report import R3ReportError, generate_r3_report_package, verify_r3_report_package

ROOT = Path(__file__).parents[1]
HEX = "a" * 64
PID = "exp001-reference-integrated-r3-v1.0.0"
MODEL = {"id": "HuggingFaceTB/SmolLM2-360M", "revision": "f8027fd0eaeea54caa13c31d31b9fdc459c38b49", "local_locator": "artifacts/models/smollm2-360m-f8027fd0"}


def _protocol():
    value = json.loads((ROOT / "experiments/exp001-reference-integrated/protocol.json").read_text())
    value["protocol_status"] = "frozen"
    return value


def _result():
    return {"artifact_class":"exp001-r3-statistical-result","protocol_id":PID,"status":"null","scientific_status":"exploratory","empirical":True,"evidence_eligible":False,"expert_validated":False,"claim_ids":[],"design":{"units":24,"domains":6,"families":12,"replicates":2,"permutation_count":64,"bootstrap_count":10000},"primary":{"metric":"transfer_minus_lexical_control","mean_delta":0.0,"p_value":1.0,"bootstrap_lower":-1.0,"all_domain_deltas_positive":False},"input_hashes":{"fixture":HEX},"interpretation":"Exploratory null result."}


def _receipt():
    return {"artifact_class":"exp001-r3-execution-receipt","protocol_id":PID,"status":"null","created_at":"2026-08-18T12:00:00Z","model":MODEL,"execution":{"runtime_status":"completed","device":"cpu","dtype":"float32","network":"disabled","generation":False,"run_count":1,"wall_seconds":1.0,"peak_rss_bytes":1000},"access":{"model_loaded":True,"model_output_accessed":"accessed","sealed_targets_accessed":"accessed","target_reads":1},"claim_ids":[],"evidence_eligible":False,"expert_validated":False}


class ReportPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "schemas").mkdir()
        for name in ("exp001-r3-protocol.schema.json","exp001-r3-statistical-result.schema.json","exp001-r3-execution-receipt.schema.json","exp001-r3-response-index.schema.json","exp001-r3-publication-manifest.schema.json"):
            (root / "schemas" / name).write_text((ROOT / "schemas" / name).read_text())
        (root / "experiments/exp001-reference-integrated").mkdir(parents=True)
        (root / "experiments/exp001-reference-integrated/protocol.json").write_text(json.dumps(_protocol()))
        self.package = root / "results/exp001-r3/run-001"
        self.package.mkdir(parents=True)
        (self.package / "statistical-result.json").write_text(json.dumps(_result()))
        (self.package / "execution-receipt.json").write_text(json.dumps(_receipt()))
        self.root = root

    def tearDown(self): self.tmp.cleanup()

    def test_generate_verify_and_refuse_overwrite(self):
        generate_r3_report_package(package_dir="results/exp001-r3/run-001", created_at="2026-08-18T12:00:00Z", terminal_result="results/exp001-r3/run-001/statistical-result.json", execution_receipt="results/exp001-r3/run-001/execution-receipt.json", repo_root=self.root)
        self.assertEqual("null", verify_r3_report_package(package_dir="results/exp001-r3/run-001", repo_root=self.root)["terminal_status"])
        with self.assertRaises(R3ReportError):
            generate_r3_report_package(package_dir="results/exp001-r3/run-001", created_at="2026-08-18T12:00:00Z", terminal_result="results/exp001-r3/run-001/statistical-result.json", execution_receipt="results/exp001-r3/run-001/execution-receipt.json", repo_root=self.root)

    def test_verify_fails_hash_drift_status_and_traversal(self):
        generate_r3_report_package(package_dir="results/exp001-r3/run-001", created_at="2026-08-18T12:00:00Z", terminal_result="results/exp001-r3/run-001/statistical-result.json", execution_receipt="results/exp001-r3/run-001/execution-receipt.json", repo_root=self.root)
        (self.package / "report.md").write_text("mutated")
        with self.assertRaises(R3ReportError): verify_r3_report_package(package_dir="results/exp001-r3/run-001", repo_root=self.root)
        (self.package / "report.md").write_text("# EXP-001 R3 publication report\n")
        with self.assertRaises(R3ReportError): verify_r3_report_package(package_dir="results/exp001-r3/../run-001", repo_root=self.root)
        manifest = json.loads((self.package / "publication-manifest.json").read_text())
        manifest["terminal_status"] = "positive"
        (self.package / "publication-manifest.json").write_text(json.dumps(manifest))
        with self.assertRaises(R3ReportError): verify_r3_report_package(package_dir="results/exp001-r3/run-001", repo_root=self.root)


if __name__ == "__main__": unittest.main()
