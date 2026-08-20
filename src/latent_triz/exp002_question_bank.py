"""Deterministic, target-free EXP-002 direct-question fixtures.

The builder intentionally derives prompts from the already registered TRIZ
metadata and never stores expected answers.  Answer keys belong to a later
sealed, separately authorized boundary.  No model, tokenizer, network, or
sealed target capability is imported here.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class Exp002QuestionBankError(ValueError):
    """Raised when the direct-question inventory violates its contract."""


_MODULE_COUNTS = {
    "principle_recognition": 40,
    "self_report_metadata": 4,
    "foundational_concepts": 9,
    "matrix": 6,
    "tool_relationship": 4,
    "false_concept_canary": 8,
}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Exp002QuestionBankError(f"{field} must be non-empty text")
    return value.strip()


def _record(
    question_id: str,
    module: str,
    prompt: str,
    source_ids: Sequence[str],
    role: str,
    mode: str = "structured_completion",
    exposure: str = "direct_query_only",
) -> dict[str, Any]:
    if module not in _MODULE_COUNTS:
        raise Exp002QuestionBankError(f"unknown module: {module}")
    if not question_id.startswith("exp002-"):
        raise Exp002QuestionBankError("question_id must use the exp002 namespace")
    if not source_ids or any(not isinstance(value, str) or not value for value in source_ids):
        raise Exp002QuestionBankError("source_ids must be non-empty strings")
    return {
        "question_id": question_id,
        "module": module,
        "prompt": _text(prompt, f"{question_id}/prompt"),
        "response_mode": mode,
        "source_ids": list(source_ids),
        "source_exposure": exposure,
        "answer_key_locator": f"sealed://exp002/direct-question/{question_id}",
        "expected_answer_present": False,
        "scientific_role": role,
    }


def build_question_bank(
    principles: Sequence[Mapping[str, Any]],
    matrix_cells: Sequence[Mapping[str, Any]],
    tool_edges: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build the complete 71-record target-free direct-question inventory."""
    if len(principles) != 40:
        raise Exp002QuestionBankError("exactly 40 principle records are required")
    numbers: list[int] = []
    for index, principle in enumerate(principles, start=1):
        if not isinstance(principle, Mapping):
            raise Exp002QuestionBankError(f"principle {index} is not an object")
        number = principle.get("principle_number")
        if isinstance(number, bool) or not isinstance(number, int) or number != index:
            raise Exp002QuestionBankError("principles must be ordered 1 through 40")
        _text(principle.get("canonical_name"), f"principle {number}/canonical_name")
        _text(principle.get("abstract_operator"), f"principle {number}/abstract_operator")
        _text(principle.get("source_id"), f"principle {number}/source_id")
        numbers.append(number)
    if numbers != list(range(1, 41)):
        raise Exp002QuestionBankError("principle numbering is not complete")
    if len(matrix_cells) != 3:
        raise Exp002QuestionBankError("three verified Matrix cells are required")
    if len(tool_edges) != 4:
        raise Exp002QuestionBankError("four Panitz edge records are required")

    records: list[dict[str, Any]] = []
    self_report = (
        "Are you familiar with TRIZ? Answer yes, no, or uncertain; do not infer training-data provenance.",
        "Have you encountered the 40 Inventive Principles? Answer yes, no, or uncertain.",
        "Do you recognize the 2003 Contradiction Matrix? Answer yes, no, or uncertain.",
        "Do you recognize the TRIZ tool relationship map used by this study? Answer yes, no, or uncertain.",
    )
    for index, prompt in enumerate(self_report, start=1):
        records.append(_record(f"exp002-self-report-{index}", "self_report_metadata", prompt, ["triz-followup-self-report"], "familiarity_diagnostic", mode="bounded_completion"))

    concept_prompts = (
        "What is a technical contradiction in TRIZ? Give a short source-backed definition.",
        "What is a physical contradiction in TRIZ? Give a short source-backed definition.",
        "What does the Ideal Final Result describe in TRIZ?",
        "What is meant by resources in a TRIZ problem?",
        "What are separation principles used for?",
        "What does substance-field analysis represent?",
        "What are evolution trends used for in TRIZ?",
        "What is ARIZ?",
        "What is the nine-windows/system-operator view?",
    )
    for index, prompt in enumerate(concept_prompts, start=1):
        records.append(_record(f"exp002-foundation-{index}", "foundational_concepts", prompt, ["triz-reference-corpus"], "knowledge_endpoint", mode="bounded_completion"))

    for principle in principles:
        number = int(principle["principle_number"])
        records.append(_record(
            f"exp002-principle-{number:02d}-recognition",
            "principle_recognition",
            f"Which established TRIZ Inventive Principle is identified by number {number}? Answer with its established English name and one short abstract operator, without quoting a source example.",
            [str(principle["source_id"])],
            "knowledge_endpoint",
            mode="bounded_completion",
        ))

    for index, cell in enumerate(matrix_cells, start=1):
        cell_id = _text(cell.get("cell_id"), f"matrix {index}/cell_id")
        improving = cell.get("improving_parameter")
        worsening = cell.get("worsening_parameter")
        if not isinstance(improving, int) or not isinstance(worsening, int) or improving == worsening:
            raise Exp002QuestionBankError("Matrix parameters are malformed")
        source = _text(cell.get("source_id"), f"matrix {index}/source_id")
        records.append(_record(
            f"exp002-matrix-{index}-forward",
            "matrix",
            f"For the ordered Matrix trade-off improve parameter {improving} while avoiding deterioration of parameter {worsening}, what is the verified recommendation set or correct abstention?",
            [source, cell_id],
            "knowledge_endpoint",
        ))
        records.append(_record(
            f"exp002-matrix-{index}-reverse",
            "matrix",
            f"Reverse the ordered Matrix trade-off: improve parameter {worsening} while avoiding deterioration of parameter {improving}. State whether the original recommendation set remains established, or abstain.",
            [source, cell_id],
            "knowledge_endpoint",
        ))

    for index, edge in enumerate(tool_edges, start=1):
        edge_id = _text(edge.get("edge_id"), f"tool edge {index}/edge_id")
        source = _text(edge.get("source_id"), f"tool edge {index}/source_id")
        source_tool = _text(edge.get("from_tool"), f"tool edge {index}/from_tool")
        destination = _text(edge.get("to_tool"), f"tool edge {index}/to_tool")
        records.append(_record(
            f"exp002-tool-{index}",
            "tool_relationship",
            f"Is the proposed TRIZ tool transition from {source_tool} to {destination} established by the registered map? Answer supported, not established, or uncertain and abstain when appropriate.",
            [source, edge_id],
            "source_familiarity_diagnostic",
            mode="abstention",
        ))

    canaries = (
        "Is 'Principle 41: Recursive Equalization' an established member of the 40 Inventive Principles? Abstain if unsupported.",
        "Is 'Principle 0: Universal Reversal' an established member of the 40 Inventive Principles? Abstain if unsupported.",
        "Does Matrix parameter 49 belong to the 2003 engineering-parameter list? Abstain if unsupported.",
        "Is reversing an ordered Matrix cell guaranteed to preserve its recommendation set? Abstain if unsupported.",
        "Is the transition 'tool X to tool Y' established when no source edge is supplied? Abstain.",
        "Is 'ARIZ-X' an official TRIZ method name in this study's registered sources? Abstain if unsupported.",
        "Is a fluent engineering explanation sufficient evidence that a TRIZ tool relationship is established? Abstain if unsupported.",
        "Is every plausible combination of two Inventive Principles itself an official principle? Abstain if unsupported.",
    )
    for index, prompt in enumerate(canaries, start=1):
        records.append(_record(f"exp002-canary-{index}", "false_concept_canary", prompt, ["triz-followup-canary-controls"], "calibration_control", mode="abstention", exposure="source_blinded_control"))

    validate_question_bank(records)
    return records


def validate_question_bank(records: Sequence[Mapping[str, Any]]) -> None:
    """Fail closed on missing modules, duplicate IDs, or leaked answer keys."""
    if len(records) != sum(_MODULE_COUNTS.values()):
        raise Exp002QuestionBankError("question bank must contain exactly 71 records")
    seen: set[str] = set()
    counts = {module: 0 for module in _MODULE_COUNTS}
    for record in records:
        if not isinstance(record, Mapping):
            raise Exp002QuestionBankError("question record must be an object")
        question_id = _text(record.get("question_id"), "question_id")
        if question_id in seen:
            raise Exp002QuestionBankError(f"duplicate question ID: {question_id}")
        seen.add(question_id)
        module = record.get("module")
        if module not in _MODULE_COUNTS:
            raise Exp002QuestionBankError(f"unknown question module: {module}")
        counts[module] += 1
        if record.get("expected_answer_present") is not False:
            raise Exp002QuestionBankError(f"answer leaked in public question: {question_id}")
        if not str(record.get("answer_key_locator", "")).startswith("sealed://exp002/direct-question/"):
            raise Exp002QuestionBankError(f"answer key locator is not sealed: {question_id}")
        if "expected_answer" in record or "correct_choice" in record:
            raise Exp002QuestionBankError(f"answer field leaked in public question: {question_id}")
    if counts != _MODULE_COUNTS:
        raise Exp002QuestionBankError(f"question module counts drift: {counts}")


__all__ = ["Exp002QuestionBankError", "build_question_bank", "validate_question_bank"]
