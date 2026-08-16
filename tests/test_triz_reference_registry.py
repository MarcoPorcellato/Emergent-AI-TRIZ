import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]


class TrizReferenceRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((ROOT / "schemas/triz-reference-registry.schema.json").read_text())
        cls.registry = json.loads((ROOT / "data/triz-reference-sources.json").read_text())

    def test_registry_is_valid_and_exactly_three_sources(self):
        errors = list(Draft202012Validator(self.schema).iter_errors(self.registry))
        self.assertEqual(errors, [])
        self.assertEqual(len(self.registry["sources"]), 3)

    def test_sources_have_no_local_paths_or_tracked_binaries(self):
        serialized = json.dumps(self.registry)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("\\\\", serialized)
        self.assertTrue(all(not (ROOT / s["artifact"]["filename"]).exists() for s in self.registry["sources"]))

    def test_hash_and_size_facts_are_frozen(self):
        expected = {
            "triz-ref-inventive-principles-2023": ("066e12e00dbab2e514029439bbf849bffb5c6516981f0fe3192d84406f25b7cb", 1152379),
            "triz-ref-matrix-2003": ("65fc567d9d76b95d462fa0e89bddac8d0db481780691d90ec11a06c9e75b32c8", 230191),
            "triz-ref-tools-overview-panitz": ("9e3f916a4801db039912e4a93b8778704703f9a94354c46db8961d36f7568c43", 78578),
        }
        for source in self.registry["sources"]:
            self.assertEqual((source["artifact"]["sha256"], source["artifact"]["size_bytes"]), expected[source["id"]])

    def test_fail_closed_for_r2_and_rights(self):
        for source in self.registry["sources"]:
            self.assertFalse(source["automatic_ground_truth"])
            self.assertFalse(source["r2_frozen_protocol_eligible"])
            self.assertFalse(source["rights"]["open_license"])
            self.assertEqual(source["future_tranche"], "R3/EXP-001")


if __name__ == "__main__":
    unittest.main()
