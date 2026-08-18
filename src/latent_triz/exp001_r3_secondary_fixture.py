"""Build the target-free secondary EXP-001 R3 reference fixtures.

The secondary endpoints are deliberately descriptive.  This module only
materialises public prompts and four-choice response surfaces; it never
derives or stores an answer key.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class Exp001SecondaryFixtureError(ValueError):
    """Raised when a Matrix or Panitz fixture violates its public boundary."""


_OPTION_IDS = ("A", "B", "C", "D")
_MATRIX_DIRECTION = "improving_row_worsening_column"
_ENDPOINT = "matrix_direction_and_nonrecommendation"
_TOOL_ENDPOINT = "tool_edge_and_abstention"


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Exp001SecondaryFixtureError(f"{field} must be non-empty text")
    return value.strip()


def _matrix_options(principles: Sequence[Any], *, include_abstain: bool = False, nonrecommendation: bool = False) -> list[dict[str, str]]:
    """Offer whole recommendation sets: a Matrix cell has no unique principle."""
    exact = tuple(int(value) for value in principles)
    replacements = [next(number for number in range(1, 41) if number not in exact)]
    variants = [exact]
    for offset in range(1, 4):
        changed = list(exact)
        changed[(offset - 1) % len(changed)] = replacements[0] + offset - 1
        if changed[(offset - 1) % len(changed)] in exact:
            changed[(offset - 1) % len(changed)] += 4
        variants.append(tuple(changed))
    descriptions = ["Recommendation set: " + ", ".join(str(number) for number in variant) for variant in variants]
    if include_abstain:
        descriptions[-1] = "Abstain: the reversed ordered cell is not established by this fixture."
    if nonrecommendation:
        exact_description = "Recommendation set: " + ", ".join(str(number) for number in exact)
        descriptions = [exact_description, exact_description + " (same members, reordered)", descriptions[2], exact_description + " (same cell, restated)"]
    return [{"id": option_id, "description": description}
            for option_id, description in zip(_OPTION_IDS, descriptions)]


def _tool_options(edge: Mapping[str, Any]) -> list[dict[str, str]]:
    destination = _text(edge.get("to_tool"), "to_tool")
    # The option surface is intentionally generic: the edge itself is never
    # encoded as an expected response or as an answer-key field.
    names = [destination, "the preceding tool", "a different TRIZ tool", "abstain"]
    return [{"id": option_id, "description": name}
            for option_id, name in zip(_OPTION_IDS, names)]


def _validate_matrix(cell: Mapping[str, Any]) -> tuple[str, list[int]]:
    cell_id = _text(cell.get("cell_id"), "cell_id")
    if not cell_id.startswith("matrix2003-cell-"):
        raise Exp001SecondaryFixtureError("matrix cell identifier is unsupported")
    if cell.get("source_id") != "triz-ref-matrix-2003":
        raise Exp001SecondaryFixtureError("matrix source identity is unsupported")
    if cell.get("direction") != _MATRIX_DIRECTION:
        raise Exp001SecondaryFixtureError("matrix direction drift detected")
    parameters = (cell.get("improving_parameter"), cell.get("worsening_parameter"))
    if any(not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 48 for value in parameters):
        raise Exp001SecondaryFixtureError("matrix parameters are malformed")
    if parameters[0] == parameters[1]:
        raise Exp001SecondaryFixtureError("matrix parameters must be distinct")
    principles = cell.get("recommended_principles")
    if not isinstance(principles, Sequence) or isinstance(principles, (str, bytes)) or len(principles) != 4:
        raise Exp001SecondaryFixtureError("matrix cell must have exactly four recommendations")
    if any(not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 40 for value in principles):
        raise Exp001SecondaryFixtureError("matrix recommendation is malformed")
    if len(set(principles)) != 4:
        raise Exp001SecondaryFixtureError("matrix recommendations must be unique")
    receipts = cell.get("transcription_receipts")
    if not isinstance(receipts, Sequence) or isinstance(receipts, (str, bytes)) or len(receipts) != 2:
        raise Exp001SecondaryFixtureError("matrix cell must have two transcription receipts")
    if cell.get("inference_prohibited") is not True:
        raise Exp001SecondaryFixtureError("matrix inference boundary is missing")
    return cell_id, [int(value) for value in principles]


def _validate_edge(edge: Mapping[str, Any]) -> tuple[str, str]:
    edge_id = _text(edge.get("edge_id"), "edge_id")
    if not edge_id.startswith("panitz-edge-") or edge.get("source_id") != "triz-ref-tools-overview-panitz":
        raise Exp001SecondaryFixtureError("Panitz edge identity is unsupported")
    status = edge.get("edge_status")
    if status not in {"supported", "uncertain", "not_established"}:
        raise Exp001SecondaryFixtureError("Panitz edge status is unsupported")
    if edge.get("selection_allowed") is not (status == "supported"):
        raise Exp001SecondaryFixtureError("Panitz selection flag does not match evidence status")
    if edge.get("abstention_allowed") is not True:
        raise Exp001SecondaryFixtureError("Panitz edge must permit abstention")
    _text(edge.get("from_tool"), "from_tool")
    _text(edge.get("to_tool"), "to_tool")
    if status != "supported" and edge.get("selection_allowed") is True:
        raise Exp001SecondaryFixtureError("not-established Panitz edge cannot be selectable")
    return edge_id, status


def build_secondary_records(matrix_cells: Sequence[Mapping[str, Any]], tool_edges: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return exactly nine Matrix and four Panitz target-free records."""
    if not isinstance(matrix_cells, Sequence) or isinstance(matrix_cells, (str, bytes)) or len(matrix_cells) != 3:
        raise Exp001SecondaryFixtureError("secondary fixture requires exactly three Matrix cells")
    if not isinstance(tool_edges, Sequence) or isinstance(tool_edges, (str, bytes)) or len(tool_edges) != 4:
        raise Exp001SecondaryFixtureError("secondary fixture requires exactly four Panitz edges")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for cell in matrix_cells:
        if not isinstance(cell, Mapping):
            raise Exp001SecondaryFixtureError("matrix cell must be an object")
        cell_id, principles = _validate_matrix(cell)
        if cell_id in seen:
            raise Exp001SecondaryFixtureError("duplicate secondary fixture identifier")
        seen.add(cell_id)
        improving, worsening = cell["improving_parameter"], cell["worsening_parameter"]
        variants = (
            ("forward", f"Preserve the ordered Matrix trade-off: improve parameter {improving} while avoiding deterioration of parameter {worsening}.", False, False),
            ("reverse", f"Reverse the ordered Matrix trade-off: improve parameter {worsening} while avoiding deterioration of parameter {improving}.", True, False),
            ("nonrecommendation", f"For the ordered trade-off from parameter {improving} to parameter {worsening}, identify the one candidate recommendation set that is not established for this Matrix cell.", False, True),
        )
        for suffix, prompt, include_abstain, nonrecommendation in variants:
            record_id = f"{cell_id}-matrix-{suffix}"
            records.append({"record_id": record_id, "endpoint_id": _ENDPOINT, "stratum": "TRIZ-blinded-transfer", "task_family": "matrix", "source_fixture_id": cell_id, "prompt": prompt, "options": _matrix_options(principles, include_abstain=include_abstain, nonrecommendation=nonrecommendation), "pooling_prohibited": True, "response_locator": f"sealed://exp001-r3/secondary/{record_id}"})
    for edge in tool_edges:
        if not isinstance(edge, Mapping):
            raise Exp001SecondaryFixtureError("Panitz edge must be an object")
        edge_id, status = _validate_edge(edge)
        if edge_id in seen:
            raise Exp001SecondaryFixtureError("duplicate secondary fixture identifier")
        seen.add(edge_id)
        record_id = f"{edge_id}-tool-abstention"
        records.append({"record_id": record_id, "endpoint_id": _TOOL_ENDPOINT, "stratum": "TRIZ-blinded-transfer", "task_family": "tool_relationship", "source_fixture_id": edge_id, "prompt": f"Given the proposed relationship from {_text(edge.get('from_tool'), 'from_tool')} to {_text(edge.get('to_tool'), 'to_tool')}, select the next tool only when the relationship is established; otherwise abstain.", "options": _tool_options(edge), "pooling_prohibited": True, "response_locator": f"sealed://exp001-r3/secondary/{record_id}"})
    if len(records) != 13 or len({record["record_id"] for record in records}) != 13:
        raise Exp001SecondaryFixtureError("secondary expansion did not yield 13 unique records")
    return records
