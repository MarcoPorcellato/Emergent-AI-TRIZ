"""Deterministic, no-model public fixtures for EXP-002-AUTO."""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


class Exp002AutoFixtureError(ValueError):
    """Raised when a public fixture leaks a target or changes its frozen shape."""


_FACTUAL_COUNTS = {
    "principle_number_to_name": 40,
    "principle_name_to_operator": 40,
    "real_vs_invented": 40,
    "insufficient_information": 40,
    "canary": 8,
    "matrix_direction": 6,
    "tool_relationship": 4,
}
_DOMAINS = (
    "agriculture", "energy", "logistics", "manufacturing",
    "medical", "software", "construction", "public_services",
)
_FORMULATION_CONDITIONS = (
    "canonical_short_field", "structured_paraphrase", "matched_non_triz_control", "nonce_edit_control",
)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Exp002AutoFixtureError(f"{field} must be non-empty text")
    return value.strip()


def _principles(principles: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    if isinstance(principles, (str, bytes, bytearray)) or not isinstance(principles, Sequence) or len(principles) != 40:
        raise Exp002AutoFixtureError("exactly 40 principle records are required")
    copied = list(principles)
    for expected, principle in enumerate(copied, start=1):
        if not isinstance(principle, Mapping) or principle.get("principle_number") != expected:
            raise Exp002AutoFixtureError("principles must be ordered 1 through 40")
        for field in ("canonical_name", "abstract_operator", "source_id"):
            _text(principle.get(field), f"principle {expected}/{field}")
    return copied


def _record(
    *, record_id: str, stage: str, family: str, prompt: str, candidates: Sequence[str] | None,
    source_ids: Sequence[str], domain: str | None = None, condition: str | None = None,
) -> dict[str, Any]:
    output: dict[str, Any] = {
        "record_id": _text(record_id, "record_id"),
        "stage": _text(stage, "stage"),
        "family": _text(family, "family"),
        "prompt": _text(prompt, "prompt"),
        "source_ids": [_text(value, "source_id") for value in source_ids],
        "expected_answer_present": False,
    }
    if not output["record_id"].startswith("exp002-auto-"):
        raise Exp002AutoFixtureError("public record ID must use the AUTO namespace")
    if not output["source_ids"]:
        raise Exp002AutoFixtureError("public record needs source provenance")
    if candidates is not None:
        output["candidate_descriptions"] = [_text(value, "candidate description") for value in candidates]
        if len(output["candidate_descriptions"]) != 4 or len(set(output["candidate_descriptions"])) != 4:
            raise Exp002AutoFixtureError("candidate scoring records require four unique candidates")
        output["response_mode"] = "candidate_description_scoring"
    else:
        output["response_mode"] = "continuation_contrast"
    if domain is not None:
        output["domain"] = _text(domain, "domain")
    if condition is not None:
        output["condition"] = _text(condition, "condition")
    return output


def _rotated(values: Sequence[str], position: int) -> list[str]:
    return [values[(position + offset) % len(values)] for offset in range(len(values))]


def build_factual_records(
    principles: Sequence[Mapping[str, Any]], matrix_cells: Sequence[Mapping[str, Any]], tool_edges: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, int | str]]]:
    """Build 178 public factual prompts and their separate automatic indices."""
    principles = _principles(principles)
    if len(matrix_cells) != 3 or len(tool_edges) != 4:
        raise Exp002AutoFixtureError("three Matrix cells and four tool edges are required")
    names = [_text(item["canonical_name"], "canonical_name") for item in principles]
    operators = [_text(item["abstract_operator"], "abstract_operator") for item in principles]
    records: list[dict[str, Any]] = []
    key: list[dict[str, int | str]] = []

    def add(record: dict[str, Any], expected_candidate_index: int) -> None:
        if expected_candidate_index not in range(4):
            raise Exp002AutoFixtureError("automatic key index must be 0 through 3")
        records.append(record)
        key.append({"record_id": record["record_id"], "expected_candidate_index": expected_candidate_index})

    for index, principle in enumerate(principles):
        number = index + 1
        name = names[index]
        source = _text(principle["source_id"], "source_id")
        options = _rotated([name, names[(index + 7) % 40], names[(index + 19) % 40], names[(index + 31) % 40]], number % 4)
        add(_record(
            record_id=f"exp002-auto-factual-number-{number:02d}", stage="AUTO-2", family="principle_number_to_name",
            prompt=f"Which registered inventive-principle name is associated with number {number}?", candidates=options,
            source_ids=[source],
        ), options.index(name))

        operator = operators[index]
        operator_options = _rotated([operator, operators[(index + 5) % 40], operators[(index + 17) % 40], operators[(index + 29) % 40]], (number + 1) % 4)
        add(_record(
            record_id=f"exp002-auto-factual-operator-{number:02d}", stage="AUTO-2", family="principle_name_to_operator",
            prompt=f"Which abstract operation is registered for the named principle '{name}'?", candidates=operator_options,
            source_ids=[source],
        ), operator_options.index(operator))

        invented = f"Invented operation {number}: recursive equalization"
        real_options = _rotated([name, invented, f"Invented operation {number}: universal inversion", f"Invented operation {number}: static fusion"], (number + 2) % 4)
        add(_record(
            record_id=f"exp002-auto-factual-real-{number:02d}", stage="AUTO-2", family="real_vs_invented",
            prompt="Which candidate is an established member of the registered forty-item inventory?", candidates=real_options,
            source_ids=[source],
        ), real_options.index(name))

        insufficient = "Abstain: no system, conflict, or transformation has been supplied."
        abstention_options = _rotated([
            insufficient,
            f"Select {name} solely because it is principle {number}.",
            "Select the first listed operation regardless of the stated evidence.",
            "Infer a recommendation from an unspecified problem.",
        ], (number + 3) % 4)
        add(_record(
            record_id=f"exp002-auto-factual-insufficient-{number:02d}", stage="AUTO-2", family="insufficient_information",
            prompt="An unspecified system has no stated problem, contradiction, or transformation. What is the defensible response?", candidates=abstention_options,
            source_ids=[source],
        ), abstention_options.index(insufficient))

    canaries = (
        ("Is a forty-first registered inventive principle supported by this inventory?", "No: the registered inventory contains forty items."),
        ("Does index zero identify a registered inventive principle?", "No: valid registered indices begin at one."),
        ("Does parameter forty-nine appear in the registered Matrix parameter range?", "No: it is outside the registered Matrix range."),
        ("Does reversing a Matrix direction preserve its recommendations automatically?", "No: direction must be checked independently."),
        ("Can an undocumented tool connection be treated as established?", "No: unsupported connections require abstention."),
        ("Is an invented suffix alone enough to establish a named method?", "No: unsupported names require abstention."),
        ("Does fluent language establish a source relationship?", "No: a source-supported edge is required."),
        ("Does combining plausible operations create an official registered item?", "No: plausibility is not registration."),
    )
    for index, (prompt, expected) in enumerate(canaries, start=1):
        options = _rotated([expected, "Yes: infer it from plausibility.", "Yes: infer it from response fluency.", "Choose a random registered item."], index % 4)
        add(_record(record_id=f"exp002-auto-factual-canary-{index}", stage="AUTO-2", family="canary", prompt=prompt, candidates=options, source_ids=["exp002-auto-canary-control"]), options.index(expected))

    for index, cell in enumerate(matrix_cells, start=1):
        if not isinstance(cell, Mapping):
            raise Exp002AutoFixtureError("Matrix cell must be an object")
        source = _text(cell.get("source_id"), "matrix source_id")
        improving = cell.get("improving_parameter")
        worsening = cell.get("worsening_parameter")
        recommendations = cell.get("recommended_principles")
        if not isinstance(improving, int) or not isinstance(worsening, int) or not isinstance(recommendations, Sequence) or len(recommendations) != 4:
            raise Exp002AutoFixtureError("Matrix cell is malformed")
        forward = "Verified recommendation identifiers: " + ", ".join(str(value) for value in recommendations)
        forward_options = _rotated([forward, "Use the reverse direction without checking.", "Select the first number only.", "Abstain despite the registered forward cell."], index % 4)
        add(_record(record_id=f"exp002-auto-factual-matrix-forward-{index}", stage="AUTO-2", family="matrix_direction", prompt=f"For the ordered Matrix direction improve {improving} while avoiding deterioration of {worsening}, which registered response is supported?", candidates=forward_options, source_ids=[source, _text(cell.get("cell_id"), "cell_id")]), forward_options.index(forward))
        reverse = "Abstain: the reverse ordered direction is not established by this forward-cell fixture."
        reverse_options = _rotated([reverse, forward, "Reuse the forward list as a guaranteed reverse result.", "Infer a reverse list from parameter order."], (index + 1) % 4)
        add(_record(record_id=f"exp002-auto-factual-matrix-reverse-{index}", stage="AUTO-2", family="matrix_direction", prompt=f"For the reversed Matrix direction improve {worsening} while avoiding deterioration of {improving}, what follows from this fixture?", candidates=reverse_options, source_ids=[source, _text(cell.get("cell_id"), "cell_id")]), reverse_options.index(reverse))

    for index, edge in enumerate(tool_edges, start=1):
        if not isinstance(edge, Mapping):
            raise Exp002AutoFixtureError("tool edge must be an object")
        status = _text(edge.get("edge_status"), "edge_status")
        if status not in {"supported", "not_established"}:
            raise Exp002AutoFixtureError("tool edge status is unsupported")
        expected = "Supported by the registered relation fixture." if status == "supported" else "Not established by the registered relation fixture."
        options = _rotated([expected, "Treat the relation as supported because it sounds plausible.", "Treat all tool pairs as equivalent.", "Infer the relation from a missing diagram."], (index + 2) % 4)
        add(_record(record_id=f"exp002-auto-factual-tool-{index}", stage="AUTO-2", family="tool_relationship", prompt=f"What is the registered status of the relation from '{_text(edge.get('from_tool'), 'from_tool')}' to '{_text(edge.get('to_tool'), 'to_tool')}'?", candidates=options, source_ids=[_text(edge.get("source_id"), "edge source_id"), _text(edge.get("edge_id"), "edge_id")]), options.index(expected))

    if Counter(record["family"] for record in records) != _FACTUAL_COUNTS:
        raise Exp002AutoFixtureError("factual inventory count drift")
    validate_public_records(records, expected_count=178)
    return records, key


def build_formulation_records(principles: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Build 40 x 4 deterministic public-formulation observations without a key."""
    records: list[dict[str, Any]] = []
    for principle in _principles(principles):
        number = int(principle["principle_number"])
        name = _text(principle["canonical_name"], "canonical_name")
        operator = _text(principle["abstract_operator"], "abstract_operator")
        source = _text(principle["source_id"], "source_id")
        prompts = {
            "canonical_short_field": f"Registered item {number}; name: {name}; abstract operation: {operator}",
            "structured_paraphrase": f"Index {number} has the title {name}. Its stated general action is: {operator}",
            "matched_non_triz_control": f"Catalogue item {number}; label: {name}; generic action: {operator}",
            "nonce_edit_control": f"Index {number} has the title {name}. Its stated general axiom is: {operator}",
        }
        for condition in _FORMULATION_CONDITIONS:
            records.append(_record(record_id=f"exp002-auto-formulation-{number:02d}-{condition}", stage="AUTO-3", family="public_formulation_sensitivity", prompt=prompts[condition], candidates=None, source_ids=[source], condition=condition))
    validate_public_records(records, expected_count=160)
    return records


def build_procedural_records() -> tuple[list[dict[str, Any]], list[dict[str, int | str]]]:
    """Build eight-domain, label-free procedural proxy records without TRIZ cues."""
    candidates = (
        "Split the workflow into independent parts that can be handled separately.",
        "Use the same undifferentiated process for every component.",
        "Add a fixed delay before every action without changing the workflow.",
        "Remove all monitoring and retain only the final output.",
    )
    records: list[dict[str, Any]] = []
    key: list[dict[str, int | str]] = []
    for domain_index, domain in enumerate(_DOMAINS):
        for case_index in range(1, 7):
            option_rotation = (domain_index + case_index) % 4
            options = _rotated(candidates, option_rotation)
            expected = candidates[0]
            prompt = (
                f"In {domain.replace('_', ' ')}, a mixed workflow couples six independently variable tasks. "
                f"A safe action must let task group {case_index} change without forcing the other groups to change. "
                "Which complete candidate action best follows that stated constraint?"
            )
            record = _record(record_id=f"exp002-auto-procedural-{domain}-{case_index}", stage="AUTO-4", family="automated_procedural_transfer_proxy", prompt=prompt, candidates=options, source_ids=["exp002-auto-procedural-grammar-v1"], domain=domain)
            records.append(record)
            key.append({"record_id": record["record_id"], "expected_candidate_index": options.index(expected)})
    validate_public_records(records, expected_count=48)
    return records, key


def validate_public_records(records: Sequence[Mapping[str, Any]], *, expected_count: int) -> None:
    """Reject key leakage, malformed candidates, and duplicate public identities."""
    if isinstance(records, (str, bytes, bytearray)) or not isinstance(records, Sequence) or len(records) != expected_count:
        raise Exp002AutoFixtureError("public record count drift")
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, Mapping):
            raise Exp002AutoFixtureError("public record must be an object")
        record_id = _text(record.get("record_id"), "record_id")
        if record_id in seen:
            raise Exp002AutoFixtureError("duplicate public record ID")
        seen.add(record_id)
        if record.get("expected_answer_present") is not False or any(field in record for field in ("expected_candidate_index", "target", "correct_choice", "expected_answer")):
            raise Exp002AutoFixtureError("public record leaked answer material")
        if record.get("response_mode") == "candidate_description_scoring":
            candidates = record.get("candidate_descriptions")
            if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes, bytearray)) or len(candidates) != 4 or any(not isinstance(value, str) or not value.strip() for value in candidates):
                raise Exp002AutoFixtureError("candidate scoring record is malformed")
        elif record.get("response_mode") == "continuation_contrast":
            if "candidate_descriptions" in record:
                raise Exp002AutoFixtureError("continuation contrast cannot carry candidate scores")
        else:
            raise Exp002AutoFixtureError("public record response mode is unknown")


def build_combined_key(
    factual_records: Sequence[Mapping[str, Any]], factual_key: Sequence[Mapping[str, Any]],
    procedural_records: Sequence[Mapping[str, Any]], procedural_key: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Join automatic indices privately while proving public records carry none."""
    validate_public_records(factual_records, expected_count=178)
    validate_public_records(procedural_records, expected_count=48)
    public_ids = {record["record_id"] for record in factual_records} | {record["record_id"] for record in procedural_records}
    combined_rows = list(factual_key) + list(procedural_key)
    if len(combined_rows) != 226:
        raise Exp002AutoFixtureError("combined automatic key count drift")
    seen: set[str] = set()
    copied: list[dict[str, int | str]] = []
    for row in combined_rows:
        if not isinstance(row, Mapping):
            raise Exp002AutoFixtureError("automatic key row must be an object")
        record_id = row.get("record_id")
        index = row.get("expected_candidate_index")
        if not isinstance(record_id, str) or record_id not in public_ids or record_id in seen or isinstance(index, bool) or not isinstance(index, int) or index not in range(4):
            raise Exp002AutoFixtureError("automatic key is malformed or not private")
        seen.add(record_id)
        copied.append({"record_id": record_id, "expected_candidate_index": index})
    if seen != public_ids:
        raise Exp002AutoFixtureError("automatic key does not cover the exact public inventory")
    return {
        "artifact_class": "exp002-auto-combined-target-key",
        "protocol_id": "exp002-auto-v1.0.0",
        "status": "not_materialized",
        "record_count": len(copied),
        "records": copied,
        "sealed_target_accessed": False,
        "claim_ids": [],
    }


__all__ = [
    "Exp002AutoFixtureError", "build_combined_key", "build_factual_records",
    "build_formulation_records", "build_procedural_records", "validate_public_records",
]
