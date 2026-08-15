from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import unittest

try:
    import numpy as np
except Exception:  # pragma: no cover - local env may omit numpy
    np = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.validator import validate  # noqa: E402
from latent_triz.a0r1_analysis import (  # noqa: E402
    _family_successes,
    _family_permutation_null,
    _interpret,
    _run_sensitivity,
    analyze_a0r1,
)


def _np() -> any:
    if np is None:
        raise unittest.SkipTest("numpy is required for this test")
    return np


class A0R1AnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.statistical_schema = json.loads(
            (root / "schemas/a0r1-statistical-result.schema.json").read_text(encoding="utf-8")
        )

    def _protocol_payload(self, *, selected_family_count: int = 24, domain_count: int = 4) -> dict:
        return {
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "protocol_id": "a0-r1-tier-r1-v1.0",
            "protocol_status": "frozen",
            "status": "frozen",
            "primary_endpoint": {
                "layer": 6,
                "token_site": "mean_transformation_span",
                "primary_view": "problem_plus_transformation",
                "surface_baseline_view": "problem_only",
                "is_max_statistic_selection": False,
                "multiplicity": 1,
            },
            "sensitivity_endpoints": {
                "may_replace_primary": False,
                "layers": [0, 2, 4, 6],
                "views": ["problem_only", "transformation_only", "problem_plus_transformation"],
                "token_sites": ["sentinel", "mean_transformation_span", "final_transformation_token"],
            },
            "thresholds": {
                "critical_successes": 17,
                "family_successes_at_least": 17,
                "primary_permutation_p_at_most": 0.05,
                "macro_f1_margin_at_least": 0.10,
                "domain_direction_successes_minimum": 4,
            },
            "calibration": {
                "selection_mode": "deterministic_predeclared",
                "selected_permutation_budget": 999,
                "deterministic_seed": 20260815,
                "selected_family_count": selected_family_count,
            },
            "epistemic_boundary": {
                "empirical": True,
                "scientific_status": "exploratory",
                "evidence_eligible": False,
                "expert_validated": False,
                "claim_ids": [],
            },
            "domain_count": domain_count,
        }

    def _implementation_payload(self) -> dict:
        return {
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "status": "frozen_before_model_output",
            "protocol": {"sealed_targets_sha256": "pending"},
            "epistemic_boundary": {
                "empirical": True,
                "scientific_status": "exploratory",
                "evidence_eligible": False,
                "expert_validated": False,
                "claim_ids": [],
            },
            "classifier": {
                "name": "l2_regularized_linear_least_squares",
                "solver": "dual_kernel_closed_form",
                "alpha": 1.0,
                "standardization": True,
                "standardization_scope": "within_train_folds",
            },
            "permutations": {
                "seed": 20260815,
                "budget": 999,
                "pairing": "paired_within_family_swaps",
                "correction": "fixed_primary_no_multiplicity",
            },
            "domain_direction": {
                "statistic": "mean_paired_primary_score_difference_strictly_positive_in_held_out_domain",
                "minimum_successful_domains": 4,
            },
            "surface_baseline_token_site": "sentinel",
            "sensitivity_may_replace_primary": False,
        }

    def _shortcuts_payload(self, status: str = "pass") -> dict:
        return {
            "artifact_class": "a0r1-shortcuts",
            "status": status,
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
        }

    def _write_targets(
        self,
        root: Path,
        family_count: int,
        domain_count: int,
    ) -> tuple[list[str], dict[str, int]]:
        domain_names = (
            "agriculture",
            "energy",
            "manufacturing",
            "medicine",
            "software",
            "transport",
        )
        if domain_count > len(domain_names):
            raise ValueError("synthetic analysis fixture exceeds the frozen domain set")
        case_ids: list[str] = []
        rows = []
        label_by_case: dict[str, int] = {}
        family_in_domain = family_count // domain_count
        for domain_index, domain in enumerate(domain_names[:domain_count]):
            for family_idx in range(family_in_domain):
                family_id = f"{domain}_f{family_idx}"
                for offset, label in ((0, 1), (1, 0)):
                    case_id = f"{family_id}_{offset}"
                    case_ids.append(case_id)
                    rows.append(
                        {
                            "case_id": case_id,
                            "problem_family_id": family_id,
                            "operator_proxy_family": "segmentation_like" if label == 1 else "inversion_like",
                        }
                    )
                    label_by_case[case_id] = label

        targets_path = root / "targets.jsonl"
        targets_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        return case_ids, label_by_case

    def _write_index(self, root: Path, case_ids: list[str], vectors: dict[str, list[float]]) -> Path:
        rows = []
        for case_id in case_ids:
            rows.append(
                {
                    "case_id": case_id,
                    "view": "problem_plus_transformation",
                    "layer": 6,
                    "token_site": "mean_transformation_span",
                    "record_id": f"{case_id}_p",
                    "vector_sha256": hashlib.sha256(json.dumps(vectors[f"{case_id}_p"], sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
                }
            )
            rows.append(
                {
                    "case_id": case_id,
                    "view": "problem_only",
                    "layer": 6,
                    "token_site": "sentinel",
                    "record_id": f"{case_id}_s",
                    "vector_sha256": hashlib.sha256(json.dumps(vectors[f"{case_id}_s"], sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
                }
            )
        path = root / "index.jsonl"
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        return path

    def _write_activation_receipt(
        self,
        root: Path,
        protocol: dict,
        implementation: Path,
        targets: Path,
        index: Path,
        cases: int,
        *,
        status: str = "pass",
        sealed: bool = False,
    ) -> Path:
        empty = root / "vectors.ste"
        empty.write_bytes(b"")
        receipt = {
            "empirical": True,
            "scientific_status": "exploratory",
            "evidence_eligible": False,
            "expert_validated": False,
            "claim_ids": [],
            "status": status,
            "protocol": {
                "hash": hashlib.sha256((root / "protocol.json").read_bytes()).hexdigest(),
            },
            "implementation": {"hash": hashlib.sha256(implementation.read_bytes()).hexdigest()},
            "dense_vectors": {"sha256": hashlib.sha256(b"").hexdigest()},
            "representation_index": {"sha256": hashlib.sha256(index.read_bytes()).hexdigest()},
            "corpus": {
                "selected_cases": cases,
                "sealed_targets_accessed": sealed,
                "sealed_targets_sha256": hashlib.sha256(targets.read_bytes()).hexdigest(),
            },
            "sealed_target_semantics_accessed": False,
            "model_output_accessed": True,
            "sealed_model_output_accessed": True,
        }
        path = root / "activation-receipt.json"
        path.write_text(json.dumps(receipt), encoding="utf-8")
        return path

    def _patch_score_operator(self, case_count: int, successful_domain_directions: int):
        np_module = _np()

        def score_operator(matrix, _domains, alpha: float):
            del alpha
            if matrix.mean() > 0.5:
                operator = np_module.eye(case_count)
                for domain in range(successful_domain_directions, 6):
                    first_family_start = domain * 8
                    operator[first_family_start, first_family_start] = -10.0
                    operator[first_family_start + 1, first_family_start + 1] = -10.0
                return operator
            return np_module.zeros((case_count, case_count))

        return score_operator

    def _run_analysis_case(
        self,
        family_count: int = 24,
        domain_count: int = 6,
        *,
        shortcut_status: str = "pass",
        successful_domain_directions: int = 6,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            numpy = _np()
            protocol_path = root / "protocol.json"
            implementation_path = root / "impl.json"
            shortcuts_path = root / "shortcuts.json"
            targets_path = root / "targets.jsonl"

            case_ids, _ = self._write_targets(root, family_count=family_count, domain_count=domain_count)
            vectors = {}
            for i, case_id in enumerate(case_ids):
                vectors[f"{case_id}_p"] = [1.0 + i]
                vectors[f"{case_id}_s"] = [0.0]
            self._write_index(root, case_ids, vectors)
            index_path = root / "index.jsonl"
            vectors_path = root / "vectors.json"
            vectors_path.write_bytes(b"")

            protocol = self._protocol_payload(selected_family_count=family_count, domain_count=domain_count)
            protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
            implementation_payload = self._implementation_payload()
            implementation_payload["protocol"]["sealed_targets_sha256"] = hashlib.sha256(targets_path.read_bytes()).hexdigest()
            implementation_path.write_text(json.dumps(implementation_payload), encoding="utf-8")
            shortcuts_payload = self._shortcuts_payload(shortcut_status)
            shortcuts_path.write_text(json.dumps(shortcuts_payload), encoding="utf-8")
            receipt_path = self._write_activation_receipt(
                root,
                protocol,
                implementation_path,
                targets_path,
                index_path,
                cases=len(case_ids),
            )

            with patch(
                "latent_triz.a0r1_analysis._read_dense_vectors",
                return_value=vectors,
            ), patch(
                "latent_triz.a0r1_analysis._score_operator",
                side_effect=self._patch_score_operator(len(case_ids), successful_domain_directions),
            ), patch(
                "latent_triz.a0r1_analysis._family_permutation_null",
                return_value=[0] * 999,
            ):
                    return analyze_a0r1(
                        protocol_path=protocol_path,
                        implementation_path=implementation_path,
                        shortcut_path=shortcuts_path,
                        activation_receipt_path=receipt_path,
                        activation_index_path=index_path,
                    dense_path=vectors_path,
                    targets_path=targets_path,
                    output_path=root / "analysis.json",
                )

    def _run_analysis_case_with_activation_status(
        self,
        family_count: int = 24,
        domain_count: int = 4,
        *,
        activation_status: str = "pass",
        shortcut_status: str = "pass",
        successful_domain_directions: int = 6,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol_path = root / "protocol.json"
            implementation_path = root / "impl.json"
            shortcuts_path = root / "shortcuts.json"
            targets_path = root / "targets.jsonl"

            case_ids, _ = self._write_targets(root, family_count=family_count, domain_count=domain_count)
            vectors = {}
            for i, case_id in enumerate(case_ids):
                vectors[f"{case_id}_p"] = [1.0 + i]
                vectors[f"{case_id}_s"] = [0.0]
            self._write_index(root, case_ids, vectors)
            index_path = root / "index.jsonl"
            vectors_path = root / "vectors.json"
            vectors_path.write_bytes(b"")

            protocol = self._protocol_payload(selected_family_count=family_count, domain_count=domain_count)
            protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
            implementation_payload = self._implementation_payload()
            implementation_payload["protocol"]["sealed_targets_sha256"] = hashlib.sha256(targets_path.read_bytes()).hexdigest()
            implementation_path.write_text(json.dumps(implementation_payload), encoding="utf-8")
            shortcuts_payload = self._shortcuts_payload(shortcut_status)
            shortcuts_path.write_text(json.dumps(shortcuts_payload), encoding="utf-8")
            receipt_path = self._write_activation_receipt(
                root,
                protocol,
                implementation_path,
                targets_path,
                index_path,
                cases=len(case_ids),
                status=activation_status,
            )

            with patch(
                "latent_triz.a0r1_analysis._read_dense_vectors",
                return_value=vectors,
            ), patch(
                "latent_triz.a0r1_analysis._score_operator",
                side_effect=self._patch_score_operator(len(case_ids), successful_domain_directions),
            ), patch(
                "latent_triz.a0r1_analysis._family_permutation_null",
                return_value=[0] * 999,
            ):
                return analyze_a0r1(
                    protocol_path=protocol_path,
                    implementation_path=implementation_path,
                    shortcut_path=shortcuts_path,
                    activation_receipt_path=receipt_path,
                    activation_index_path=index_path,
                    dense_path=vectors_path,
                    targets_path=targets_path,
                    output_path=root / "analysis.json",
                )

    def test_positive_contract_met_for_24_families_and_at_least_4_domains(self) -> None:
        result = self._run_analysis_case(
            family_count=24,
            domain_count=6,
            successful_domain_directions=4,
        )
        self.assertEqual(result["status"], "positive")
        self.assertGreaterEqual(result["max_family_successes_observed"], 17)
        self.assertGreaterEqual(result["domain_direction_success_count"], 4)

    def test_family_success_boundary_is_exactly_17_of_24(self) -> None:
        labels = [value for _ in range(24) for value in (1, 0)]
        families = [f"family_{family:02d}" for family in range(24) for _ in range(2)]

        def scores_with_successes(count: int) -> list[float]:
            scores: list[float] = []
            for family in range(24):
                scores.extend((1.0, -1.0) if family < count else (-1.0, 1.0))
            return scores

        self.assertEqual(17, _family_successes(scores_with_successes(17), labels, families)[0])
        self.assertEqual(16, _family_successes(scores_with_successes(16), labels, families)[0])

    def test_reject_non_exactly_24_selected_families(self) -> None:
        _np()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol_path = root / "protocol.json"
            protocol = self._protocol_payload(selected_family_count=16)
            protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
            implementation_path = root / "impl.json"
            implementation_path.write_text(json.dumps(self._implementation_payload()), encoding="utf-8")
            shortcuts_path = root / "shortcuts.json"
            shortcuts_path.write_text(json.dumps(self._shortcuts_payload()), encoding="utf-8")
            targets = root / "targets.jsonl"
            case_ids, _ = self._write_targets(root, family_count=16, domain_count=4)
            vectors = {f"{case_id}_p": [1.0] for case_id in case_ids}
            vectors.update({f"{case_id}_s": [0.0] for case_id in case_ids})
            index_path = self._write_index(root, case_ids, vectors)
            vectors_path = root / "vectors.safetensors"
            vectors_path.write_bytes(b"")
            receipt_path = self._write_activation_receipt(root, protocol, implementation_path, targets, index_path, len(case_ids))
            with self.assertRaises(Exception):
                self._run_analysis_case(family_count=16, domain_count=4)

    def test_domain_gate_3_successful_domains_is_null_even_if_family_successes_high(self) -> None:
        result = self._run_analysis_case(
            family_count=24,
            domain_count=6,
            successful_domain_directions=3,
        )
        self.assertEqual(result["status"], "null")
        self.assertLess(result["domain_direction_success_count"], 4)
        self.assertGreaterEqual(result["max_family_successes_observed"], 17)
        self.assertEqual([], validate(result, self.statistical_schema))

    def test_positive_result_validates_against_schema(self) -> None:
        result = self._run_analysis_case(
            family_count=24,
            domain_count=6,
            successful_domain_directions=4,
        )
        self.assertEqual([], validate(result, self.statistical_schema))

    def test_sensitivity_is_descriptive_never_rescues_primary(self) -> None:
        np_module = _np()
        labels = [1, 0] * 12
        families = [f"d{i // 2}_f{i // 2}" for i in range(24)]
        domains = [f"d{i // 2}" for i in range(24)]
        combos = {
            ("problem_plus_transformation", 6, "mean_transformation_span"): np_module.eye(24),
            ("problem_only", 6, "sentinel"): np_module.zeros((24, 24)),
        }
        sensitivity = _run_sensitivity(
            combos=combos,
            labels=labels,
            families=families,
            domains=domains,
            layers=[6],
            views=["problem_only", "transformation_only", "problem_plus_transformation"],
            token_sites=["sentinel", "mean_transformation_span", "final_transformation_token"],
        )
        self.assertTrue(all(not value["rescues_primary"] for value in sensitivity.values()))

    def test_deterministic_permutation_seed_and_budget(self) -> None:
        np_module = _np()
        n = 24
        labels = [1, 0] * (n // 2)
        operator = np_module.eye(n)
        families = [f"d{i // 2}_f{i // 2}" for i in range(n)]
        p1 = _family_permutation_null(operator, labels, families, seed=20260815, budget=999)
        p2 = _family_permutation_null(operator, labels, families, seed=20260815, budget=999)
        self.assertEqual(p1, p2)
        self.assertEqual(len(p1), 999)
        self.assertTrue(all(0 <= value <= 24 for value in p1))

    def test_analysis_status_failures(self) -> None:
        _np()
        case = self._run_analysis_case(shortcut_status="non_interpretable")
        self.assertEqual(case["status"], "non_interpretable")
        self.assertEqual(_interpret("non_interpretable", False), "Non-interpretable status from surface-control boundary.")
        self.assertEqual([], validate(case, self.statistical_schema))

    def test_analysis_failed_status_validates_against_schema(self) -> None:
        _np()
        case = self._run_analysis_case_with_activation_status(activation_status="failed")
        self.assertEqual(case["status"], "failed")
        self.assertEqual([], validate(case, self.statistical_schema))


if __name__ == "__main__":
    unittest.main()
