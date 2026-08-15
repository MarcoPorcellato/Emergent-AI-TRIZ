from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from latent_triz.a0_activation_sites import (
    A0ActivationSitesError,
    build_view_texts,
    select_token_indices,
)


class A0ActivationSitesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = {
            "problem": "A shared device stalls.",
            "constraints": ["keep cost fixed", "reuse hardware"],
            "initial_state": "One path handles all work.",
            "desired_improvement": "stable flow",
            "worsening_consequence": "heat",
            "transformation": "Local units act before the shared unit.",
            "solution": "Local units act before the shared unit. Flow becomes stable.",
        }

    def test_four_views_and_problem_only_excludes_transformation(self) -> None:
        views = build_view_texts(self.case, sentinel_text="Analysis anchor:")
        self.assertEqual(
            list(views),
            [
                "problem_only",
                "transformation_only",
                "problem_plus_transformation",
                "problem_plus_solution",
            ],
        )
        self.assertNotIn(self.case["transformation"], views["problem_only"])
        self.assertTrue(all(text.endswith("Analysis anchor:") for text in views.values()))

    def test_offset_sites_are_deterministic(self) -> None:
        text = "Transformation:\nReverse order.\n\nAnalysis anchor:"
        offsets = [(index, index + 1) for index in range(len(text))]
        sites = select_token_indices(
            view_text=text,
            transformation_text="Reverse order.",
            sentinel_text="Analysis anchor:",
            offsets=offsets,
            special_flags=[False] * len(offsets),
            attention_mask=[1] * len(offsets),
        )
        self.assertEqual(sites["final_transformation_token"], (29,))
        self.assertEqual(sites["mean_transformation_span"], tuple(range(16, 30)))
        self.assertEqual(sites["sentinel"], (47,))

    def test_problem_only_yields_sentinel_only(self) -> None:
        text = "Problem only.\n\nAnalysis anchor:"
        offsets = [(index, index + 1) for index in range(len(text))]
        sites = select_token_indices(
            view_text=text,
            transformation_text="not present",
            sentinel_text="Analysis anchor:",
            offsets=offsets,
            special_flags=[False] * len(offsets),
            attention_mask=[1] * len(offsets),
        )
        self.assertEqual(tuple(sites), ("sentinel",))

    def test_ambiguous_sentinel_fails_closed(self) -> None:
        text = "Analysis anchor: x Analysis anchor:"
        offsets = [(index, index + 1) for index in range(len(text))]
        with self.assertRaisesRegex(A0ActivationSitesError, "exactly once"):
            select_token_indices(
                view_text=text,
                transformation_text="x",
                sentinel_text="Analysis anchor:",
                offsets=offsets,
                special_flags=[False] * len(offsets),
                attention_mask=[1] * len(offsets),
            )

    def test_malformed_or_special_only_span_fails_closed(self) -> None:
        with self.assertRaises(A0ActivationSitesError):
            select_token_indices(
                view_text="T\nS",
                transformation_text="T",
                sentinel_text="S",
                offsets=[(0, 1), (1, 2), (2, 3)],
                special_flags=[True, False, True],
                attention_mask=[1, 1, 1],
            )


if __name__ == "__main__":
    unittest.main()
