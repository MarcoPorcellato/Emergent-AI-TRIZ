"""Build public, target-free EXP-001 R3 record stubs.

This module is deliberately a small data-boundary helper.  It does not read
prompts, model files, or sealed targets, and it has no ML/runtime imports.
Only the public control plan and option-set *identifiers* are consumed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FixtureBuilderError(ValueError):
    """Raised when the public R3 inventories cannot be joined safely."""


def _read_json(path: Path) -> dict[str, Any] | list[Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureBuilderError(f"cannot read JSON fixture: {path}") from exc
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        values = [json.loads(line) for line in lines if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureBuilderError(f"cannot read JSONL fixture: {path}") from exc
    if not all(isinstance(value, dict) for value in values):
        raise FixtureBuilderError(f"JSONL fixture contains a non-object: {path}")
    return values


def build_public_record_stubs(
    control_plan: str | Path,
    option_sets: str | Path,
) -> list[dict[str, Any]]:
    """Return the deterministic two-stratum public stub for every planned pair.

    The returned records contain only design metadata and an opaque response
    locator.  In particular, no prompt, option meaning, target, answer, or
    scoring value is read or emitted.
    """
    plan = _read_json(Path(control_plan))
    options = _read_jsonl(Path(option_sets))
    if not isinstance(plan, dict) or plan.get("target_values_present") is not False:
        raise FixtureBuilderError("control plan is not a pre-freeze no-target object")
    pairs = plan.get("pairs")
    if not isinstance(pairs, list) or len(pairs) != 10:
        raise FixtureBuilderError("expected exactly ten control pairs")
    if not isinstance(options, list):
        raise FixtureBuilderError("option sets must be a JSONL array")

    by_locator: dict[str, dict[str, Any]] = {}
    for option in options:
        if not isinstance(option, dict):
            raise FixtureBuilderError("option-set record is not an object")
        locator = option.get("target_locator")
        if not isinstance(locator, str) or locator in by_locator:
            raise FixtureBuilderError("option sets must have unique opaque locators")
        # Validate only structural option metadata; never copy option values.
        if not isinstance(option.get("options"), list) or len(option["options"]) < 2:
            raise FixtureBuilderError(f"invalid option set for {locator}")
        by_locator[locator] = option

    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pair in pairs:
        if not isinstance(pair, dict):
            raise FixtureBuilderError("control pair is not an object")
        pair_id = pair.get("pair_id")
        locator = pair.get("target_locator")
        if not isinstance(pair_id, str) or pair_id in seen:
            raise FixtureBuilderError("control pair identifiers must be unique")
        if not isinstance(locator, str) or locator not in by_locator:
            raise FixtureBuilderError(f"missing option set for {pair_id}")
        seen.add(pair_id)
        suffix = pair_id.removeprefix("exp001-r3-pair-")
        for stratum in ("TRIZ-blinded-transfer", "source-exposed-competence"):
            records.append({
                "record_id": f"{pair_id}-{stratum}",
                "pair_id": pair_id,
                "stratum": stratum,
                "task_family": pair["task_family"],
                "control_kind": pair["control_kind"],
                "source_family": pair["source_family"],
                "problem_family": pair["problem_family"],
                "domain_holdout": pair["domain_holdout"],
                "source_holdout": pair["source_holdout"],
                "family_holdout": pair["family_holdout"],
                "pooling_prohibited": True,
                "response_locator": f"sealed://exp001-r3/response/{suffix}/{stratum}",
            })
    if len(records) != 20:
        raise FixtureBuilderError("control plan did not produce twenty records")
    return records


def build_fixture_records(control_plan: str | Path, option_sets: str | Path) -> list[dict[str, Any]]:
    """Compatibility alias with an explicit, descriptive name."""
    return build_public_record_stubs(control_plan, option_sets)
