"""Compare the live GitHub ruleset payload with the tracked governance contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


class RulesetAuditError(ValueError):
    """Raised when the live ruleset drifts from the tracked contract."""


def _rule_map(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rules = payload.get("rules")
    if not isinstance(rules, list):
        raise RulesetAuditError("live ruleset has no rules array")
    mapped: dict[str, Mapping[str, Any]] = {}
    for rule in rules:
        if not isinstance(rule, Mapping) or not isinstance(rule.get("type"), str):
            raise RulesetAuditError("live ruleset contains a malformed rule")
        mapped[str(rule["type"])] = rule
    return mapped


def audit_ruleset(expected: Mapping[str, Any], live: Mapping[str, Any]) -> None:
    errors: list[str] = []
    for key in ("name", "enforcement", "target"):
        if live.get(key) != expected.get(key):
            errors.append(f"{key}: expected {expected.get(key)!r}, got {live.get(key)!r}")

    include = live.get("conditions", {}).get("ref_name", {}).get("include")
    if include != expected.get("include_refs"):
        errors.append(f"include refs: expected {expected.get('include_refs')!r}, got {include!r}")

    rules = _rule_map(live)
    for rule_type, expected_key in (
        ("required_linear_history", "required_linear_history"),
        ("deletion", "block_deletion"),
        ("non_fast_forward", "block_non_fast_forward"),
    ):
        if bool(expected.get(expected_key)) != (rule_type in rules):
            errors.append(f"{rule_type}: presence drift")

    pull_request = rules.get("pull_request", {}).get("parameters", {})
    if pull_request.get("required_review_thread_resolution") != expected.get(
        "required_review_thread_resolution"
    ):
        errors.append("required review thread resolution drift")
    if pull_request.get("allowed_merge_methods") != expected.get("allowed_merge_methods"):
        errors.append("allowed merge methods drift")

    status = rules.get("required_status_checks", {}).get("parameters", {})
    contexts = [
        check.get("context")
        for check in status.get("required_status_checks", [])
        if isinstance(check, Mapping)
    ]
    if contexts != expected.get("required_status_checks"):
        errors.append(
            f"required status checks: expected {expected.get('required_status_checks')!r}, got {contexts!r}"
        )
    if status.get("strict_required_status_checks_policy") != expected.get(
        "strict_required_status_checks_policy"
    ):
        errors.append("strict required status policy drift")
    if errors:
        raise RulesetAuditError("; ".join(errors))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--live", type=Path, required=True)
    args = parser.parse_args(argv)
    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    live = json.loads(args.live.read_text(encoding="utf-8"))
    audit_ruleset(expected, live)
    print("ruleset-audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
