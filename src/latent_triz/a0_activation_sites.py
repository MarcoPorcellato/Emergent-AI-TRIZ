"""Deterministic A0 prompt views and tokenizer-offset site selection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class A0ActivationSitesError(RuntimeError):
    """Raised when a frozen A0 view or token site cannot be resolved."""


VIEW_NAMES = (
    "problem_only",
    "transformation_only",
    "problem_plus_transformation",
    "problem_plus_solution",
)
TOKEN_SITES = (
    "sentinel",
    "final_transformation_token",
    "mean_transformation_span",
)


def _text(case: Mapping[str, Any], key: str) -> str:
    value = case.get(key)
    if not isinstance(value, str) or not value.strip():
        raise A0ActivationSitesError(f"{key} must be a non-empty string")
    return value.strip()


def _problem_block(case: Mapping[str, Any]) -> str:
    constraints = case.get("constraints")
    if (
        not isinstance(constraints, list)
        or not constraints
        or any(not isinstance(item, str) or not item.strip() for item in constraints)
    ):
        raise A0ActivationSitesError("constraints must be a non-empty string list")
    return (
        f"Problem:\n{_text(case, 'problem')}\n\n"
        f"Constraints:\n{'; '.join(item.strip() for item in constraints)}\n\n"
        f"Initial state:\n{_text(case, 'initial_state')}\n\n"
        f"Desired improvement:\n{_text(case, 'desired_improvement')}\n\n"
        f"Worsening consequence:\n{_text(case, 'worsening_consequence')}"
    )


def build_view_texts(case: Mapping[str, Any], *, sentinel_text: str) -> dict[str, str]:
    """Render the four frozen A0 views with one stable terminal sentinel."""
    if not isinstance(sentinel_text, str) or not sentinel_text.strip():
        raise A0ActivationSitesError("sentinel_text must be non-empty")
    sentinel = sentinel_text.strip()
    problem = _problem_block(case)
    transformation = _text(case, "transformation")
    solution = _text(case, "solution")
    views = {
        "problem_only": f"{problem}\n\n{sentinel}",
        "transformation_only": f"Transformation:\n{transformation}\n\n{sentinel}",
        "problem_plus_transformation": (
            f"{problem}\n\nTransformation:\n{transformation}\n\n{sentinel}"
        ),
        "problem_plus_solution": f"{problem}\n\nSolution:\n{solution}\n\n{sentinel}",
    }
    if tuple(views) != VIEW_NAMES:
        raise A0ActivationSitesError("view order drift")
    return views


def _unique_span(text: str, needle: str, *, label: str) -> tuple[int, int]:
    start = text.find(needle)
    if start < 0 or text.find(needle, start + 1) >= 0:
        raise A0ActivationSitesError(f"{label} must occur exactly once")
    return start, start + len(needle)


def select_token_indices(
    *,
    view_text: str,
    transformation_text: str,
    sentinel_text: str,
    offsets: Sequence[Sequence[int]],
    special_flags: Sequence[bool],
    attention_mask: Sequence[int],
) -> dict[str, tuple[int, ...]]:
    """Resolve applicable sites from a fast-tokenizer offset mapping."""
    if len(offsets) != len(special_flags) or len(offsets) != len(attention_mask):
        raise A0ActivationSitesError("token metadata length mismatch")
    normalized: list[tuple[int, int]] = []
    for index, pair in enumerate(offsets):
        if (
            not isinstance(pair, Sequence)
            or isinstance(pair, (str, bytes))
            or len(pair) != 2
            or isinstance(pair[0], bool)
            or isinstance(pair[1], bool)
            or not isinstance(pair[0], int)
            or not isinstance(pair[1], int)
            or pair[0] < 0
            or pair[1] < pair[0]
        ):
            raise A0ActivationSitesError(f"malformed token offset at index {index}")
        normalized.append((int(pair[0]), int(pair[1])))

    def overlap(span: tuple[int, int]) -> tuple[int, ...]:
        selected = tuple(
            index
            for index, (start, end) in enumerate(normalized)
            if bool(attention_mask[index])
            and not bool(special_flags[index])
            and start < span[1]
            and end > span[0]
            and start != end
        )
        if not selected:
            raise A0ActivationSitesError("text span has no attended non-special token")
        return selected

    sentinel = overlap(_unique_span(view_text, sentinel_text, label="sentinel"))
    sites: dict[str, tuple[int, ...]] = {"sentinel": (sentinel[-1],)}
    occurrences = view_text.count(transformation_text)
    if occurrences:
        transformation = overlap(
            _unique_span(view_text, transformation_text, label="transformation")
        )
        sites["final_transformation_token"] = (transformation[-1],)
        sites["mean_transformation_span"] = transformation
    return sites
