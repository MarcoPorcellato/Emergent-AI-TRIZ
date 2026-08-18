import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from latent_triz.validator import validate

ROOT = Path(__file__).parents[1]
HEX = "a" * 64
MODEL = {"id": "HuggingFaceTB/SmolLM2-360M", "revision": "f8027fd0eaeea54caa13c31d31b9fdc459c38b49", "local_locator": "artifacts/models/smollm2-360m-f8027fd0"}
ASSET = {"locator": "external/exp001-r3/response-scores.jsonl", "sha256": HEX}
PROVENANCE = {name: {"path": f"results/exp001-r3/{name}.json", "sha256": HEX} for name in ("implementation", "authorization", "integrity", "feasibility", "sealed_key_access", "recovery")}
PROTOCOL_ID = "exp001-reference-integrated-r3-v1.0.0"


def schema(name):
    return json.loads((ROOT / "schemas" / name).read_text())


def artifact(path="results/exp001-r3/report.json"):
    return {"path": path, "sha256": HEX}


class Exp001R3TerminalSchemaTests(unittest.TestCase):
    def test_execution_receipt_valid_and_fail_closed_mutations(self):
        value = {"artifact_class": "exp001-r3-execution-receipt", "protocol_id": PROTOCOL_ID, "status": "null", "created_at": "2026-08-18T12:00:00Z", "model": MODEL, "execution": {"runtime_status": "completed", "device": "cpu", "dtype": "float32", "network": "disabled", "generation": False, "run_count": 1, "wall_seconds": 4.0, "peak_rss_bytes": 1000}, "access": {"model_loaded": True, "model_output_accessed": "accessed", "sealed_targets_accessed": "accessed", "target_reads": 1}, "claim_ids": [], "evidence_eligible": False, "expert_validated": False, "reports": ["results/exp001-r3/report.md"], "external_response_asset": ASSET, "provenance": PROVENANCE}
        self.assertEqual([], validate(value, schema("exp001-r3-execution-receipt.schema.json")))
        for key, bad in (("evidence_eligible", True), ("claim_ids", ["claim"]), ("execution", dict(value["execution"], generation=True))):
            mutation = copy.deepcopy(value); mutation[key] = bad
            self.assertTrue(validate(mutation, schema("exp001-r3-execution-receipt.schema.json")))

    def test_response_index_rejects_raw_prompt_and_target(self):
        value = {"artifact_class": "exp001-r3-response-index", "protocol_id": PROTOCOL_ID, "record_count": 85, "records": [{"record_id": "exp001-r3-domain-01-transfer-blinded", "scores": {"A": 1.0, "B": 0.0, "C": 0.0, "D": 0.0}, "prompt_sha256": HEX}]}
        sch = schema("exp001-r3-response-index.schema.json")
        self.assertEqual([], validate(value, sch))
        for forbidden in ("prompt", "expected_choice", "target"):
            mutation = copy.deepcopy(value); mutation["records"][0][forbidden] = "secret"
            self.assertTrue(validate(mutation, sch))

    def test_statistical_result_and_manifest(self):
        result = {"artifact_class": "exp001-r3-statistical-result", "protocol_id": PROTOCOL_ID, "status": "null", "scientific_status": "exploratory", "empirical": True, "evidence_eligible": False, "expert_validated": False, "claim_ids": [], "design": {"units": 24, "domains": 6, "families": 12, "replicates": 2, "permutation_count": 64, "bootstrap_count": 10000}, "primary": {"metric": "transfer_minus_lexical_control", "mean_delta": 0.0, "p_value": 1.0, "bootstrap_lower": -1.0, "all_domain_deltas_positive": False}, "secondary_summary": {"pooling": "non_pooled", "matrix_2003": "descriptive", "panitz": "descriptive"}, "input_hashes": {"fixture": HEX}, "interpretation": "Exploratory null result."}
        self.assertEqual([], validate(result, schema("exp001-r3-statistical-result.schema.json")))
        manifest = {"artifact_class": "exp001-r3-publication-manifest", "protocol_id": PROTOCOL_ID, "terminal_status": "null", "publish_every_terminal_outcome": True, "claim_ids": [], "evidence_eligible": False, "expert_validated": False, "protocol": artifact("experiments/exp001-reference-integrated/protocol.json"), "receipt": artifact("results/exp001-r3/receipt.json"), "report": artifact("results/exp001-r3/report.md"), "result": artifact("results/exp001-r3/statistical-result.json"), "external_response_asset": ASSET, "provenance": PROVENANCE}
        self.assertEqual([], validate(manifest, schema("exp001-r3-publication-manifest.schema.json")))
        bad = copy.deepcopy(manifest); bad["dense_asset"] = {"locator": "../secret", "sha256": HEX}
        self.assertTrue(validate(bad, schema("exp001-r3-publication-manifest.schema.json")))


if __name__ == "__main__":
    unittest.main()
