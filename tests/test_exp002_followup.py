import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from latent_triz.exp002_followup import (
    EXPECTED_MODELS,
    Exp002ContractError,
    summarize_label_surface,
    validate_no_model_protocol,
    validate_tokenizer_observation,
)
from latent_triz.exp002_question_bank import build_question_bank, validate_question_bank


ROOT = Path(__file__).resolve().parents[1]


def _load(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class Exp002FollowupTests(unittest.TestCase):
    def test_frozen_protocol_is_closed(self):
        protocol = _load("experiments/exp002-qwen3-followup/protocol.json")
        validate_no_model_protocol(protocol)

        mutated = json.loads(json.dumps(protocol))
        mutated["approval_boundary"]["model_load"] = True
        with self.assertRaises(Exp002ContractError):
            validate_no_model_protocol(mutated)

    def test_question_bank_has_all_modules_and_no_answers(self):
        records = build_question_bank(
            [json.loads(line) for line in (ROOT / "data/triz-reference/principles.jsonl").read_text(encoding="utf-8").splitlines() if line],
            [json.loads(line) for line in (ROOT / "experiments/exp001-reference-integrated/fixtures/matrix-cells.jsonl").read_text(encoding="utf-8").splitlines() if line],
            [json.loads(line) for line in (ROOT / "experiments/exp001-reference-integrated/fixtures/tool-edges.jsonl").read_text(encoding="utf-8").splitlines() if line],
        )
        self.assertEqual(len(records), 71)
        validate_question_bank(records)
        self.assertTrue(all(record["expected_answer_present"] is False for record in records))

        leaked = json.loads(json.dumps(records))
        leaked[0]["expected_answer"] = "Segmentation"
        with self.assertRaises(ValueError):
            validate_question_bank(leaked)

    def test_question_schema_accepts_every_generated_record(self):
        schema = _load("schemas/exp002-direct-question.schema.json")
        records = build_question_bank(
            [json.loads(line) for line in (ROOT / "data/triz-reference/principles.jsonl").read_text(encoding="utf-8").splitlines() if line],
            [json.loads(line) for line in (ROOT / "experiments/exp001-reference-integrated/fixtures/matrix-cells.jsonl").read_text(encoding="utf-8").splitlines() if line],
            [json.loads(line) for line in (ROOT / "experiments/exp001-reference-integrated/fixtures/tool-edges.jsonl").read_text(encoding="utf-8").splitlines() if line],
        )
        validator = Draft202012Validator(schema)
        for record in records:
            self.assertEqual(list(validator.iter_errors(record)), [])

    def test_label_surface_summary_is_deterministic(self):
        rows = [{"scores": {"A": 1.0, "B": 0.0, "C": 0.0, "D": 0.0}}, {"scores": {"A": 0.0, "B": 2.0, "C": 0.0, "D": 0.0}}]
        summary = summarize_label_surface(rows)
        self.assertEqual(summary["record_count"], 2)
        self.assertEqual(summary["top_label_counts"], {"A": 1, "B": 1, "C": 0, "D": 0})

        with self.assertRaises(Exp002ContractError):
            summarize_label_surface([{"scores": {"A": 1, "B": 0, "C": 0}}])

    def test_tokenizer_observation_boundary(self):
        model_id = "Qwen/Qwen3-0.6B-Base"
        observation = {
            "model_id": model_id,
            "revision": EXPECTED_MODELS[model_id],
            "tokenizer_files_sha256": "0" * 64,
            "label_token_ids": {label: index for index, label in enumerate("ABCD")},
            "continuation_token_counts": {label: 1 for label in "ABCD"},
            "prefix_boundary_ok": True,
            "special_tokens": {},
            "runtime_versions": {},
        }
        validate_tokenizer_observation(observation)
        observation["revision"] = "0" * 40
        with self.assertRaises(Exp002ContractError):
            validate_tokenizer_observation(observation)


if __name__ == "__main__":
    unittest.main()
