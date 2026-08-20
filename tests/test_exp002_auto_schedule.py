import unittest

from latent_triz.exp002_auto_schedule import Exp002AutoScheduleError, build_auto_schedule, validate_auto_schedule


class Exp002AutoScheduleTests(unittest.TestCase):
    def setUp(self):
        self.transfer_ids = [f"transfer-{index:02d}" for index in range(1, 25)]
        self.bindings = {
            "experiments/exp002-auto/factual-public.jsonl": "a" * 64,
            "experiments/exp002-auto/formulation-public.jsonl": "b" * 64,
            "experiments/exp002-auto/procedural-public.jsonl": "c" * 64,
            "results/exp002/preexecution/label-surface-diagnostic.json": "d" * 64,
        }

    def test_schedule_freezes_all_stage_shapes_and_exact_shards(self):
        schedule = build_auto_schedule(self.transfer_ids, self.bindings)
        validate_auto_schedule(schedule)
        stages = {stage["stage_id"]: stage for stage in schedule["stages"]}
        self.assertEqual(len(stages["AUTO-1"]["shards"]), 1)
        self.assertEqual(len(stages["AUTO-1"]["shards"][0]["conditions"]), 5)
        self.assertEqual(stages["AUTO-2"]["shards"][0]["record_count"], 45)
        self.assertEqual([shard["record_count"] for shard in stages["AUTO-2"]["shards"]], [45, 45, 44, 44])
        self.assertEqual(len(stages["AUTO-3"]["shards"]), 4)
        self.assertEqual([shard["record_count"] for shard in stages["AUTO-4"]["shards"]], [6] * 8)
        self.assertEqual([len(shard["permutations"]) for shard in stages["AUTO-5"]["shards"]], [4] * 6)

    def test_schedule_rejects_duplicate_or_non_twenty_four_transfer_ids(self):
        with self.assertRaises(Exp002AutoScheduleError):
            build_auto_schedule(self.transfer_ids[:-1], self.bindings)
        with self.assertRaises(Exp002AutoScheduleError):
            build_auto_schedule(self.transfer_ids[:-1] + [self.transfer_ids[-2]], self.bindings)

    def test_schedule_rejects_mutated_permutation_or_unsafe_binding(self):
        schedule = build_auto_schedule(self.transfer_ids, self.bindings)
        schedule["stages"][5]["shards"][0]["permutations"][0]["mapping"]["A"] = "B"
        with self.assertRaises(Exp002AutoScheduleError):
            validate_auto_schedule(schedule)
        schedule = build_auto_schedule(self.transfer_ids, self.bindings)
        schedule["input_bindings"]["../unsafe.json"] = "f" * 64
        with self.assertRaises(Exp002AutoScheduleError):
            validate_auto_schedule(schedule)


if __name__ == "__main__":
    unittest.main()
