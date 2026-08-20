import unittest

from latent_triz.exp002_power import Exp002PowerError, calibrate_domain_count, validate_calibration


class Exp002PowerTests(unittest.TestCase):
    def test_selection_is_deterministic_and_model_free(self):
        receipt = calibrate_domain_count([12, 8, 10])
        self.assertEqual(receipt["selected_domain_count"], 8)
        self.assertFalse(receipt["model_access"])
        validate_calibration(receipt)

    def test_insufficient_candidates_fail_closed(self):
        with self.assertRaises(Exp002PowerError):
            calibrate_domain_count([4, 6])
        receipt = calibrate_domain_count([8])
        receipt["selected_power"] = 0.1
        with self.assertRaises(Exp002PowerError):
            validate_calibration(receipt)


if __name__ == "__main__":
    unittest.main()
