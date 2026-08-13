from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz import lab04
from latent_triz.lab04_runner import run_lab04_bundle


class Lab04Tests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def _write_json(self, path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")

    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")

    def _predecessor(self, *, status: str = "pass") -> dict:
        return {
            "status": status,
            "hashes": {"summary_json": "0" * 64},
        }

    def _config(self) -> dict:
        return json.loads((self.ROOT / "experiments/lab04-decodability/config.json").read_text(encoding="utf-8"))

    def _minimal_cases(self) -> list[dict]:
        return [
            {
                "case_id": "pilot_case_001",
                "domain": "manufacturing",
                "label": "segmentation",
                "labels": [{"principle": "segmentation"}],
            },
            {
                "case_id": "pilot_case_002",
                "domain": "packaging",
                "label": "segmentation",
                "labels": [{"principle": "segmentation"}],
            },
        ]

    def _minimal_representations(self) -> list[dict]:
        return [
            {
                "case_id": "pilot_case_001",
                "layer_index": 0,
                "vector": [0.1, 0.2],
                "vector_dim": 2,
                "provenance": {"synthetic": True},
                "non_claim_boundary": {"empirical": False, "evidence_eligible": False, "claim_ids": []},
            },
            {
                "case_id": "pilot_case_001",
                "layer_index": 1,
                "vector": [0.3, 0.4],
                "vector_dim": 2,
                "provenance": {"synthetic": True},
                "non_claim_boundary": {"empirical": False, "evidence_eligible": False, "claim_ids": []},
            },
            {
                "case_id": "pilot_case_002",
                "layer_index": 0,
                "vector": [0.5, 0.6],
                "vector_dim": 2,
                "provenance": {"synthetic": True},
                "non_claim_boundary": {"empirical": False, "evidence_eligible": False, "claim_ids": []},
            },
            {
                "case_id": "pilot_case_002",
                "layer_index": 1,
                "vector": [0.7, 0.8],
                "vector_dim": 2,
                "provenance": {"synthetic": True},
                "non_claim_boundary": {"empirical": False, "evidence_eligible": False, "claim_ids": []},
            },
        ]

    def _four_domain_two_label_cases(self) -> list[dict]:
        return [
            {"case_id": "d0_a", "domain": "d0", "label": "alpha", "labels": [{"principle": "alpha"}]},
            {"case_id": "d0_b", "domain": "d0", "label": "beta", "labels": [{"principle": "beta"}]},
            {"case_id": "d1_a", "domain": "d1", "label": "alpha", "labels": [{"principle": "alpha"}]},
            {"case_id": "d1_b", "domain": "d1", "label": "beta", "labels": [{"principle": "beta"}]},
            {"case_id": "d2_a", "domain": "d2", "label": "alpha", "labels": [{"principle": "alpha"}]},
            {"case_id": "d2_b", "domain": "d2", "label": "beta", "labels": [{"principle": "beta"}]},
            {"case_id": "d3_a", "domain": "d3", "label": "alpha", "labels": [{"principle": "alpha"}]},
            {"case_id": "d3_b", "domain": "d3", "label": "beta", "labels": [{"principle": "beta"}]},
        ]

    def _four_domain_two_label_representations(self, layer_scores: tuple[list[float], list[float]]) -> list[dict]:
        layer0 = layer_scores[0]
        layer1 = layer_scores[1]
        records: list[dict] = []
        for case_id in ["d0_a", "d0_b", "d1_a", "d1_b", "d2_a", "d2_b", "d3_a", "d3_b"]:
            label = "alpha" if case_id.endswith("_a") else "beta"
            records.append(
                {
                    "case_id": case_id,
                    "layer_index": 0,
                    "vector": layer0 if label == "alpha" else list(layer0),
                    "vector_dim": 2,
                    "provenance": {"synthetic": True},
                    "non_claim_boundary": {"empirical": False, "evidence_eligible": False, "claim_ids": []},
                }
            )
            records.append(
                {
                    "case_id": case_id,
                    "layer_index": 1,
                    "vector": layer1 if label == "alpha" else [layer1[0] + 1.0, layer1[1]],
                    "vector_dim": 2,
                    "provenance": {"synthetic": True},
                    "non_claim_boundary": {"empirical": False, "evidence_eligible": False, "claim_ids": []},
                }
            )
        return records

    def test_current_fixture_is_fail_closed_and_non_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_jsonl(root / "cases.jsonl", self._minimal_cases())
            self._write_jsonl(root / "representations.jsonl", self._minimal_representations())
            self._write_json(root / "config.json", self._config())
            self._write_json(root / "lab01.json", self._predecessor())
            self._write_json(root / "lab02.json", self._predecessor())
            self._write_json(root / "lab03.json", self._predecessor())

            result = lab04.run_lab04_analysis(
                cases_path=root / "cases.jsonl",
                representations_path=root / "representations.jsonl",
                config_path=root / "config.json",
                predecessor_lab01_summary=root / "lab01.json",
                predecessor_lab02_summary=root / "lab02.json",
                predecessor_lab03_summary=root / "lab03.json",
            )
            self.assertEqual(result["status"], "fail")
            self.assertFalse(result["empirical"])
            self.assertFalse(result["evidence_eligible"])
            self.assertEqual(result["claim_ids"], [])

    def test_temporary_two_label_fixture_can_render_fail_closed(self) -> None:
        config = self._config()
        config["minimum_labels"] = 1
        config["readiness_thresholds"]["minimum_cases_per_label_domain_cell"] = 1
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_jsonl(root / "cases.jsonl", self._minimal_cases())
            self._write_jsonl(root / "representations.jsonl", self._minimal_representations())
            self._write_json(root / "config.json", config)
            self._write_json(root / "lab01.json", self._predecessor())
            self._write_json(root / "lab02.json", self._predecessor())
            self._write_json(root / "lab03.json", self._predecessor())

            result = run_lab04_bundle(
                cases_path=root / "cases.jsonl",
                representations_path=root / "representations.jsonl",
                config_path=root / "config.json",
                predecessor_lab01_summary=root / "lab01.json",
                predecessor_lab02_summary=root / "lab02.json",
                predecessor_lab03_summary=root / "lab03.json",
                output_dir=root / "out",
            )

            self.assertEqual(result["status"], "fail")
            html = (root / "out/report.html").read_text(encoding="utf-8")
            self.assertIn("No Latent TRIZ claim", html)
            self.assertNotIn("/private/tmp", html)
            self.assertNotIn("/Users/", html)
            self.assertEqual(json.loads((root / "out/summary.json").read_text(encoding="utf-8"))["claim_ids"], [])

    def test_case_issues_force_fail_closed_status(self) -> None:
        cases = self._minimal_cases()
        cases.append(
            {
                "case_id": "pilot_case_003",
                "domain": "service",
                "label": "local_quality",
                "labels": [{"principle": "local_quality"}, {"principle": "segmentation"}],
            }
        )
        config = self._config()
        config["minimum_labels"] = 2
        config["readiness_thresholds"]["minimum_domains"] = 2
        config["readiness_thresholds"]["minimum_cases_per_label_domain_cell"] = 1

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_jsonl(root / "cases.jsonl", cases)
            self._write_jsonl(root / "representations.jsonl", self._minimal_representations())
            self._write_json(root / "config.json", config)
            self._write_json(root / "lab01.json", self._predecessor())
            self._write_json(root / "lab02.json", self._predecessor())
            self._write_json(root / "lab03.json", self._predecessor())

            result = lab04.run_lab04_analysis(
                cases_path=root / "cases.jsonl",
                representations_path=root / "representations.jsonl",
                config_path=root / "config.json",
                predecessor_lab01_summary=root / "lab01.json",
                predecessor_lab02_summary=root / "lab02.json",
                predecessor_lab03_summary=root / "lab03.json",
            )

            self.assertEqual(result["status"], "fail")
            gates = {item["gate"]: item["status"] for item in result["gates"]}
            self.assertEqual(gates["P1"], "fail")
            p1 = next(item for item in result["gates"] if item["gate"] == "P1")
            self.assertIn("non-unanimous labels", p1["details"])
            self.assertTrue(any("non-unanimous labels" in issue for issue in result["issues"]))

    def test_representation_validation_rejects_nonfinite_dimension_mismatch_and_label_leakage(self) -> None:
        case_label = {"pilot_case_001": "segmentation", "pilot_case_002": "segmentation"}

        with self.assertRaises(lab04.Lab04Error):
            lab04._collect_representations(
                [
                    {
                        "case_id": "pilot_case_001",
                        "layer_index": 0,
                        "vector": [0.1, float("nan")],
                        "vector_dim": 2,
                        "provenance": {},
                        "non_claim_boundary": {"empirical": False, "evidence_eligible": False, "claim_ids": []},
                    },
                ],
                case_label,
            )

        layers, issues = lab04._collect_representations(
            [
                {
                    "case_id": "pilot_case_001",
                    "layer_index": 0,
                    "vector": [0.1, 0.2],
                    "vector_dim": 2,
                    "provenance": {},
                    "non_claim_boundary": {"empirical": False, "evidence_eligible": False, "claim_ids": []},
                },
                {
                    "case_id": "pilot_case_002",
                    "layer_index": 0,
                    "vector": [0.3],
                    "vector_dim": 1,
                    "provenance": {},
                    "non_claim_boundary": {"empirical": False, "evidence_eligible": False, "claim_ids": []},
                },
            ],
            case_label,
        )
        self.assertIn("non-uniform vector dimensions", " ".join(issues))
        self.assertEqual(sorted(layers[0]), ["pilot_case_001", "pilot_case_002"])

        _, issues = lab04._collect_representations(
            [
                {
                    "case_id": "pilot_case_001",
                    "layer_index": 0,
                    "vector": [0.1, 0.2],
                    "vector_dim": 2,
                    "label": "segmentation",
                    "provenance": {},
                    "non_claim_boundary": {"empirical": False, "evidence_eligible": False, "claim_ids": []},
                },
                {
                    "case_id": "pilot_case_002",
                    "layer_index": 0,
                    "vector": [0.3, 0.4],
                    "vector_dim": 2,
                    "provenance": {},
                    "non_claim_boundary": {"empirical": False, "evidence_eligible": False, "claim_ids": []},
                },
            ],
            case_label,
        )
        self.assertIn("forbidden label field", " ".join(issues))

    def test_helper_layer_parsing_and_alpha_tie_break(self) -> None:
        self.assertEqual(lab04._parse_layer("resid_post_layer_7"), 7)
        self.assertEqual(lab04._parse_layer("8"), 8)

        selected = lab04._holm_adjust([0.01, 0.01, 0.1])
        self.assertEqual(selected, [0.03, 0.03, 0.1])

    def test_max_statistic_selected_layer_uses_tie_break_to_lower_index(self) -> None:
        records = [
            {"layer": 0, "observed_layer_macro": 0.40, "permutation_null": [0.1, 0.2], "permutation_count": 2},
            {"layer": 1, "observed_layer_macro": 0.40, "permutation_null": [0.3, 0.4], "permutation_count": 2},
            {"layer": 2, "observed_layer_macro": 0.60, "permutation_null": [0.2, 0.1], "permutation_count": 2},
        ]
        self.assertEqual(lab04._select_max_stat_layer(records), 2)

        records[0]["observed_layer_macro"] = 0.60
        self.assertEqual(lab04._select_max_stat_layer(records), 0)

    def test_max_statistic_family_wise_p_is_computed_from_max_of_layer_nulls(self) -> None:
        records = [
            {"layer": 0, "observed_layer_macro": 0.2, "permutation_null": [0.2, 0.9], "permutation_count": 2},
            {"layer": 1, "observed_layer_macro": 0.8, "permutation_null": [0.8, 0.7], "permutation_count": 2},
        ]
        self.assertEqual(lab04._select_max_stat_layer(records), 1)
        self.assertEqual(lab04._compute_max_stat_p(records, 1), (1.0, 2))

    def test_alpha_reselection_receipts_are_deterministic_and_recorded_for_each_fold(self) -> None:
        labels = ["alpha", "beta"]
        case_label: dict[str, str] = {}
        case_domain: dict[str, str] = {}
        vectors: dict[str, list[float]] = {}
        for domain_index in range(4):
            for label_index, label in enumerate(labels):
                case_id = f"case_d{domain_index}_{label}"
                case_label[case_id] = label
                case_domain[case_id] = f"domain_{domain_index}"
                vectors[case_id] = [float(label_index * 4 + domain_index), 1.0]

        config = {
            "permutations": 5,
            "seed": 1729,
            "reselect_within_each_permutation": True,
        }
        result_a, _ = lab04._run_layer(
            layer=0,
            vectors=vectors,
            case_domain=case_domain,
            case_label=case_label,
            labels=labels,
            config=config,
        )
        result_b, _ = lab04._run_layer(
            layer=0,
            vectors=vectors,
            case_domain=case_domain,
            case_label=case_label,
            labels=labels,
            config=config,
        )
        receipts_a = [
            fold["permutation_receipt"]["alpha_reselection_sha256"]
            for fold in result_a["folds"]
        ]
        receipts_b = [
            fold["permutation_receipt"]["alpha_reselection_sha256"]
            for fold in result_b["folds"]
        ]
        self.assertEqual(receipts_a, receipts_b)
        for fold in result_a["folds"]:
            receipt = fold["permutation_receipt"]
            self.assertEqual(receipt["alpha_reselection_count"], 5)
            self.assertEqual(receipt["alpha_reselection_failures"], 0)
            self.assertEqual(receipt["block"], "outer_training_domain")
            self.assertTrue(receipt["block_label_counts_preserved"])

    def test_max_statistic_selected_layer_is_published_and_follows_outer_macro_tiebreak(self) -> None:
        cases = self._four_domain_two_label_cases()
        representations = [
            {
                "case_id": case["case_id"],
                "layer_index": 0,
                "vector": [0.0, 0.0],
                "vector_dim": 2,
                "provenance": {"synthetic": True},
                "non_claim_boundary": {"empirical": False, "evidence_eligible": False, "claim_ids": []},
            }
            for case in cases
        ]
        representations.extend(
            [
                {
                    "case_id": case["case_id"],
                    "layer_index": 1,
                    "vector": [0.0, 0.0] if case["case_id"].endswith("_a") else [1.0, 0.0],
                    "vector_dim": 2,
                    "provenance": {"synthetic": True},
                    "non_claim_boundary": {"empirical": False, "evidence_eligible": False, "claim_ids": []},
                }
                for case in cases
            ]
        )

        config = self._config()
        config["minimum_labels"] = 2
        config["readiness_thresholds"]["minimum_domains"] = 4
        config["readiness_thresholds"]["minimum_cases_per_label_domain_cell"] = 1
        config["readiness_thresholds"]["corrected_p_max"] = 1.0
        config["permutations"] = 3

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_jsonl(root / "cases.jsonl", cases)
            self._write_jsonl(root / "representations.jsonl", representations)
            self._write_json(root / "config.json", config)
            self._write_json(root / "lab01.json", self._predecessor())
            self._write_json(root / "lab02.json", self._predecessor())
            self._write_json(root / "lab03.json", self._predecessor())

            result = lab04.run_lab04_analysis(
                cases_path=root / "cases.jsonl",
                representations_path=root / "representations.jsonl",
                config_path=root / "config.json",
                predecessor_lab01_summary=root / "lab01.json",
                predecessor_lab02_summary=root / "lab02.json",
                predecessor_lab03_summary=root / "lab03.json",
            )
            self.assertEqual(result["random_control"]["max_statistic"]["selected_layer"], 1)

    def test_insufficient_permutations_cannot_resolve_significance_alpha(self) -> None:
        cases = self._four_domain_two_label_cases()
        representations = self._four_domain_two_label_representations(([0.0, 0.0], [0.0, 0.0]))
        config = self._config()
        config["minimum_labels"] = 2
        config["readiness_thresholds"]["minimum_domains"] = 4
        config["readiness_thresholds"]["minimum_cases_per_label_domain_cell"] = 1
        config["readiness_thresholds"]["corrected_p_max"] = 0.1
        config["permutations"] = 2

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_jsonl(root / "cases.jsonl", cases)
            self._write_jsonl(root / "representations.jsonl", representations)
            self._write_json(root / "config.json", config)
            self._write_json(root / "lab01.json", self._predecessor())
            self._write_json(root / "lab02.json", self._predecessor())
            self._write_json(root / "lab03.json", self._predecessor())
            result = lab04.run_lab04_analysis(
                cases_path=root / "cases.jsonl",
                representations_path=root / "representations.jsonl",
                config_path=root / "config.json",
                predecessor_lab01_summary=root / "lab01.json",
                predecessor_lab02_summary=root / "lab02.json",
                predecessor_lab03_summary=root / "lab03.json",
            )
            self.assertEqual(result["status"], "fail")
            self.assertIn("below minimum resolvable p", "\n".join(result["issues"]))

    def test_nested_lodo_receipts_are_leakage_free_and_train_only(self) -> None:
        labels = ["alpha", "beta"]
        case_label: dict[str, str] = {}
        case_domain: dict[str, str] = {}
        vectors: dict[str, list[float]] = {}
        for domain_index in range(4):
            for label_index, label in enumerate(labels):
                case_id = f"case_d{domain_index}_{label}"
                case_label[case_id] = label
                case_domain[case_id] = f"domain_{domain_index}"
                vectors[case_id] = [float(label_index * 4 + domain_index), float(label_index)]

        config = {"permutations": 5, "seed": 1729}
        result, issues = lab04._run_layer(
            layer=0,
            vectors=vectors,
            case_domain=case_domain,
            case_label=case_label,
            labels=labels,
            config=config,
        )
        self.assertEqual(issues, [])
        self.assertEqual(len(result["folds"]), 4)
        self.assertEqual(result["permutation_aggregate_receipt"]["null_count"], 5)
        held_fold = next(fold for fold in result["folds"] if fold["domain"] == "domain_0")
        split = held_fold["split_receipt"]
        self.assertEqual(split["overlap_case_ids"], [])
        self.assertEqual(set(split["train_domains"]) & set(split["test_domains"]), set())
        self.assertEqual(held_fold["scaler_receipt"]["fit_case_ids"], split["train_case_ids"])
        self.assertEqual(set(held_fold["scaler_receipt"]["excluded_case_ids"]), set(split["test_case_ids"]))
        self.assertTrue(held_fold["permutation_receipt"]["label_counts_preserved"])
        self.assertTrue(all(receipt["status"] == "pass" for receipt in held_fold["inner_split_receipts"]))

        changed = {case_id: list(vector) for case_id, vector in vectors.items()}
        for case_id in split["test_case_ids"]:
            changed[case_id] = [999999.0, -999999.0]
        changed_result, _ = lab04._run_layer(
            layer=0,
            vectors=changed,
            case_domain=case_domain,
            case_label=case_label,
            labels=labels,
            config=config,
        )
        changed_fold = next(
            fold for fold in changed_result["folds"] if fold["domain"] == "domain_0"
        )
        self.assertEqual(
            held_fold["scaler_receipt"]["sha256"],
            changed_fold["scaler_receipt"]["sha256"],
        )

    def test_runner_outputs_are_deterministic_and_path_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out1 = Path(directory) / "one"
            out2 = Path(directory) / "two"
            config = self._config()
            config["minimum_labels"] = 1
            config["readiness_thresholds"]["minimum_cases_per_label_domain_cell"] = 1
            root = Path(directory)
            self._write_json(root / "config.json", config)
            self._write_jsonl(root / "cases.jsonl", self._minimal_cases())
            self._write_jsonl(root / "representations.jsonl", self._minimal_representations())
            self._write_json(root / "lab01.json", self._predecessor())
            self._write_json(root / "lab02.json", self._predecessor())
            self._write_json(root / "lab03.json", self._predecessor())

            result1 = run_lab04_bundle(
                cases_path=Path(directory) / "cases.jsonl",
                representations_path=Path(directory) / "representations.jsonl",
                config_path=Path(directory) / "config.json",
                predecessor_lab01_summary=Path(directory) / "lab01.json",
                predecessor_lab02_summary=Path(directory) / "lab02.json",
                predecessor_lab03_summary=Path(directory) / "lab03.json",
                output_dir=out1,
            )
            result2 = run_lab04_bundle(
                cases_path=Path(directory) / "cases.jsonl",
                representations_path=Path(directory) / "representations.jsonl",
                config_path=Path(directory) / "config.json",
                predecessor_lab01_summary=Path(directory) / "lab01.json",
                predecessor_lab02_summary=Path(directory) / "lab02.json",
                predecessor_lab03_summary=Path(directory) / "lab03.json",
                output_dir=out2,
            )

            self.assertEqual(result1["status"], result2["status"])
            for rel in ("probe_result.json", "report.html", "summary.json"):
                self.assertEqual((out1 / rel).read_bytes(), (out2 / rel).read_bytes())
                self.assertNotIn(b"/private/tmp", (out1 / rel).read_bytes())
                self.assertNotIn(b"/Users/", (out1 / rel).read_bytes())
            self.assertIn("No Latent TRIZ claim", (out1 / "report.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
