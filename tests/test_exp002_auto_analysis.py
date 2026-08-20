import unittest

from latent_triz.exp002_auto_analysis import Exp002AutoAnalysisError, analyze_combined_candidate_scores


class Exp002AutoAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.factual = [
            {"record_id": "f-1", "family": "principle_number_to_name", "candidate_scores": [0.0, 3.0, 1.0, 2.0]},
            {"record_id": "f-2", "family": "canary", "candidate_scores": [3.0, 0.0, 1.0, 2.0]},
        ]
        self.procedural = [
            {"record_id": "p-1", "domain": "agriculture", "candidate_scores": [2.0, 0.0, 1.0, 0.5]},
            {"record_id": "p-2", "domain": "energy", "candidate_scores": [0.0, 2.0, 1.0, 0.5]},
            {"record_id": "p-3", "domain": "logistics", "candidate_scores": [0.0, 1.0, 2.0, 0.5]},
            {"record_id": "p-4", "domain": "manufacturing", "candidate_scores": [0.0, 1.0, 0.5, 2.0]},
            {"record_id": "p-5", "domain": "medical", "candidate_scores": [2.0, 0.0, 1.0, 0.5]},
            {"record_id": "p-6", "domain": "software", "candidate_scores": [0.0, 2.0, 1.0, 0.5]},
            {"record_id": "p-7", "domain": "construction", "candidate_scores": [0.0, 1.0, 2.0, 0.5]},
            {"record_id": "p-8", "domain": "public_services", "candidate_scores": [0.0, 1.0, 0.5, 2.0]},
        ]
        self.key = {
            "artifact_class": "exp002-auto-combined-target-key",
            "protocol_id": "exp002-auto-v1.0.0",
            "status": "sealed",
            "record_count": 10,
            "sealed_target_accessed": False,
            "claim_ids": [],
            "records": [
                {"record_id": "f-1", "expected_candidate_index": 1},
                {"record_id": "f-2", "expected_candidate_index": 0},
                *[{"record_id": f"p-{index}", "expected_candidate_index": (index - 1) % 4} for index in range(1, 9)],
            ],
        }

    def test_analysis_reads_combined_key_once_only_after_all_asset_hashes_match(self):
        calls = []
        result = analyze_combined_candidate_scores(
            factual_rows=self.factual,
            procedural_rows=self.procedural,
            observed_asset_hashes={"factual": "a" * 64, "procedural": "b" * 64},
            expected_asset_hashes={"factual": "a" * 64, "procedural": "b" * 64},
            key_reader=lambda: calls.append("read") or self.key,
        )
        self.assertEqual(calls, ["read"])
        self.assertEqual(result["sealed_target_read_count"], 1)
        self.assertEqual(result["factual"]["accuracy"], 1.0)
        self.assertEqual(result["procedural"]["status"], "auto_proxy_signal")
        self.assertEqual(result["claim_ids"], [])

    def test_hash_mismatch_refuses_before_combined_key_read(self):
        calls = []
        with self.assertRaises(Exp002AutoAnalysisError):
            analyze_combined_candidate_scores(
                factual_rows=self.factual,
                procedural_rows=self.procedural,
                observed_asset_hashes={"factual": "0" * 64, "procedural": "b" * 64},
                expected_asset_hashes={"factual": "a" * 64, "procedural": "b" * 64},
                key_reader=lambda: calls.append("read") or self.key,
            )
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
