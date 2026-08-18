"""Deterministically expand target-free primary units into non-pooled prompts."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class Exp001PrimaryFixtureError(ValueError):
    """Raised when public R3 primary units do not meet their strict boundary."""


_STRATA = ("TRIZ-blinded-transfer", "source-exposed-competence")
_OPTION_IDS = ("A", "B", "C", "D")


def _options(value: Any, field: str) -> list[dict[str, str]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 4:
        raise Exp001PrimaryFixtureError(f"{field} must have four options")
    parsed: list[dict[str, str]] = []
    for option in value:
        if not isinstance(option, Mapping):
            raise Exp001PrimaryFixtureError(f"{field} option must be an object")
        option_id = option.get("id")
        description = option.get("description")
        if not isinstance(option_id, str) or not isinstance(description, str) or not description.strip():
            raise Exp001PrimaryFixtureError(f"{field} option is malformed")
        parsed.append({"id": option_id, "description": description})
    if tuple(option["id"] for option in parsed) != _OPTION_IDS:
        raise Exp001PrimaryFixtureError(f"{field} option IDs must be A through D")
    return parsed


def build_primary_records(units: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Build 72 target-free records: blinded transfer/control plus exposed transfer."""
    if len(units) != 24:
        raise Exp001PrimaryFixtureError("primary unit inventory must contain 24 units")
    records: list[dict[str, Any]] = []
    seen_units: set[str] = set()
    for unit in units:
        if not isinstance(unit, Mapping):
            raise Exp001PrimaryFixtureError("primary unit must be an object")
        unit_id = unit.get("unit_id")
        domain = unit.get("domain")
        family = unit.get("problem_family")
        replicate = unit.get("replicate")
        transfer = unit.get("transfer_prompt")
        control = unit.get("lexical_control_prompt")
        exposed = unit.get("exposed_context")
        if not all(isinstance(value, str) and value.strip() for value in (unit_id, domain, family, transfer, control, exposed)):
            raise Exp001PrimaryFixtureError("primary unit identity or text is malformed")
        if unit_id in seen_units or not isinstance(replicate, int) or replicate not in {1, 2}:
            raise Exp001PrimaryFixtureError("primary unit identity is not unique")
        if transfer == control:
            raise Exp001PrimaryFixtureError("lexical control cannot duplicate transfer prompt")
        seen_units.add(unit_id)
        transfer_options = _options(unit.get("transfer_options"), "transfer_options")
        control_options = _options(unit.get("lexical_control_options"), "lexical_control_options")
        shared = {"unit_id": unit_id, "domain": domain, "problem_family": family, "replicate": replicate,
                  "pooling_prohibited": True}
        records.extend((
            {**shared, "record_id": f"{unit_id}-transfer-blinded", "stratum": _STRATA[0],
             "condition": "transfer", "prompt": transfer, "options": transfer_options,
             "response_locator": f"sealed://exp001-r3/primary/{unit_id}/transfer"},
            {**shared, "record_id": f"{unit_id}-lexical-control", "stratum": _STRATA[0],
             "condition": "lexical_control", "prompt": control, "options": control_options,
             "response_locator": f"sealed://exp001-r3/primary/{unit_id}/lexical-control"},
            {**shared, "record_id": f"{unit_id}-transfer-exposed", "stratum": _STRATA[1],
             "condition": "transfer", "prompt": f"Reference context: {exposed}\n\n{transfer}", "options": transfer_options,
             "response_locator": f"sealed://exp001-r3/primary/{unit_id}/transfer-exposed"},
        ))
    if len(records) != 72:
        raise Exp001PrimaryFixtureError("primary expansion did not yield 72 records")
    return records
