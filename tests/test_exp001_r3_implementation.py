import copy
import unittest
from pathlib import Path

from latent_triz.exp001_r3_implementation import (
    Exp001ImplementationError,
    build_implementation_binding,
    verify_implementation_binding,
)


ROOT = Path(__file__).parents[1]


class Exp001ImplementationTests(unittest.TestCase):
    def test_binding_is_canonical_and_verified(self):
        binding = build_implementation_binding(ROOT)
        self.assertEqual(binding["inventory"]["combined_records"], 85)
        self.assertEqual(binding["limits"]["new_dense_output_bytes"], 134217728)
        self.assertEqual(verify_implementation_binding(ROOT, binding)["status"], "verified")

    def test_binding_rejects_each_bound_field_mutation(self):
        for field in ("code_sha256", "fixture_sha256", "source_sha256", "receipt_sha256", "inventory", "limits", "policies"):
            with self.subTest(field=field):
                mutated = copy.deepcopy(build_implementation_binding(ROOT))
                if isinstance(mutated[field], list):
                    mutated[field][0]["sha256"] = "0" * 64
                elif field == "inventory":
                    mutated[field]["combined_records"] = 84
                elif field == "limits":
                    mutated[field]["wall_time_seconds"] = 1801
                else:
                    mutated[field]["network_access"] = True
                with self.assertRaises(Exp001ImplementationError):
                    verify_implementation_binding(ROOT, mutated)

    def test_binding_rejects_identity_mutation(self):
        binding = build_implementation_binding(ROOT)
        binding["model"]["revision"] = "0" * 40
        with self.assertRaises(Exp001ImplementationError):
            verify_implementation_binding(ROOT, binding)
