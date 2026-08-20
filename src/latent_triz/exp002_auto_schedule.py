"""Frozen, target-free shard schedule for EXP-002-AUTO."""
from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from .exp002_auto_contract import AUTO_STAGES, Exp002AutoContractError, validate_auto_schedule as _validate_contract_schedule
from .exp002_surface import all_label_permutations, cyclic_permutations


class Exp002AutoScheduleError(ValueError):
    """Raised when the AUTO schedule is incomplete or no longer immutable."""


_DOMAINS = (
    "agriculture", "energy", "logistics", "manufacturing",
    "medical", "software", "construction", "public_services",
)
_FORMULATIONS = (
    "canonical_short_field", "structured_paraphrase", "matched_non_triz_control", "nonce_edit_control",
)


def _transfer_ids(values: Sequence[str]) -> list[str]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence) or len(values) != 24:
        raise Exp002AutoScheduleError("AUTO response surface requires exactly 24 transfer IDs")
    copied = list(values)
    if any(not isinstance(value, str) or not value.strip() for value in copied) or len(set(copied)) != 24:
        raise Exp002AutoScheduleError("AUTO transfer IDs must be unique non-empty text")
    return copied


def _shards(prefix: str, record_ids: Sequence[str], sizes: Sequence[int]) -> list[dict[str, Any]]:
    if sum(sizes) != len(record_ids):
        raise Exp002AutoScheduleError("shard sizes do not cover public records")
    output: list[dict[str, Any]] = []
    offset = 0
    for index, size in enumerate(sizes, start=1):
        selected = list(record_ids[offset:offset + size])
        output.append({"shard_id": f"{prefix}-{index:02d}", "record_ids": selected, "record_count": len(selected)})
        offset += size
    return output


def build_auto_schedule(transfer_record_ids: Sequence[str], input_bindings: Mapping[str, str]) -> dict[str, Any]:
    """Build every AUTO stage from deterministic IDs and input hashes only."""
    transfer_ids = _transfer_ids(transfer_record_ids)
    if not isinstance(input_bindings, Mapping) or not input_bindings:
        raise Exp002AutoScheduleError("AUTO input bindings are required")
    factual_ids = [f"exp002-auto-factual-{family}-{index:02d}" for family, count in (
        ("number", 40), ("operator", 40), ("real", 40), ("insufficient", 40),
    ) for index in range(1, count + 1)]
    factual_ids.extend(f"exp002-auto-factual-canary-{index}" for index in range(1, 9))
    factual_ids.extend(f"exp002-auto-factual-matrix-{direction}-{index}" for index in range(1, 4) for direction in ("forward", "reverse"))
    factual_ids.extend(f"exp002-auto-factual-tool-{index}" for index in range(1, 5))
    if len(factual_ids) != 178:
        raise Exp002AutoScheduleError("AUTO factual ID inventory drift")
    formulation_ids = {
        condition: [f"exp002-auto-formulation-{index:02d}-{condition}" for index in range(1, 41)]
        for condition in _FORMULATIONS
    }
    auto1_conditions = [
        {"condition": "balanced_cyclic_label_permutations", "mapping": mapping}
        for mapping in cyclic_permutations()
    ] + [{"condition": "label_free_candidate_description_scoring", "mapping": {}}]
    auto5_permutations = [
        {"permutation_id": f"perm-{index:02d}", "mapping": mapping}
        for index, mapping in enumerate(all_label_permutations(), start=1)
    ]
    return {
        "artifact_class": "exp002-auto-schedule",
        "protocol_id": "exp002-auto-v1.0.0",
        "status": "frozen_no_model",
        "claim_ids": [],
        "input_bindings": dict(input_bindings),
        "stages": [
            {"stage_id": "AUTO-0", "shards": [{"shard_id": "auto-0-tokenizer-audit", "record_ids": transfer_ids, "record_count": 24}]},
            {"stage_id": "AUTO-1", "shards": [{"shard_id": "auto-1-cyclic-and-label-free", "record_ids": transfer_ids, "record_count": 24, "conditions": auto1_conditions}]},
            {"stage_id": "AUTO-2", "shards": _shards("auto-2-factual", factual_ids, (45, 45, 44, 44))},
            {"stage_id": "AUTO-3", "shards": [{"shard_id": f"auto-3-{condition}", "record_ids": formulation_ids[condition], "record_count": 40, "condition": condition} for condition in _FORMULATIONS]},
            {"stage_id": "AUTO-4", "shards": [{"shard_id": f"auto-4-{domain}", "record_ids": [f"exp002-auto-procedural-{domain}-{index}" for index in range(1, 7)], "record_count": 6, "domain": domain} for domain in _DOMAINS]},
            {"stage_id": "AUTO-5", "shards": [{"shard_id": f"auto-5-permutations-{index:02d}", "record_ids": transfer_ids, "record_count": 24, "permutations": auto5_permutations[offset:offset + 4]} for index, offset in enumerate(range(0, 24, 4), start=1)]},
        ],
    }


def validate_auto_schedule(schedule: Mapping[str, Any]) -> None:
    """Reject changed stage order, record sets, and response-surface mappings."""
    try:
        _validate_contract_schedule(schedule)
    except Exp002AutoContractError as exc:
        raise Exp002AutoScheduleError(str(exc)) from exc
    stages = schedule.get("stages")
    if not isinstance(stages, Sequence) or tuple(stage.get("stage_id") for stage in stages if isinstance(stage, Mapping)) != AUTO_STAGES or len(stages) != len(AUTO_STAGES):
        raise Exp002AutoScheduleError("AUTO schedule stage inventory drift")
    stage_map = {stage["stage_id"]: stage for stage in stages}
    auto0 = stage_map["AUTO-0"].get("shards")
    auto1 = stage_map["AUTO-1"].get("shards")
    if not isinstance(auto0, Sequence) or len(auto0) != 1 or not isinstance(auto1, Sequence) or len(auto1) != 1:
        raise Exp002AutoScheduleError("AUTO response-surface screen shards drift")
    transfer_ids = _transfer_ids(auto0[0].get("record_ids"))
    if auto0[0].get("record_count") != 24 or auto1[0].get("record_ids") != transfer_ids or auto1[0].get("record_count") != 24:
        raise Exp002AutoScheduleError("AUTO response-surface record binding drift")
    expected_auto1 = [
        {"condition": "balanced_cyclic_label_permutations", "mapping": mapping}
        for mapping in cyclic_permutations()
    ] + [{"condition": "label_free_candidate_description_scoring", "mapping": {}}]
    if auto1[0].get("conditions") != expected_auto1:
        raise Exp002AutoScheduleError("AUTO cyclic/label-free condition drift")
    auto2 = stage_map["AUTO-2"].get("shards")
    if not isinstance(auto2, Sequence) or [shard.get("record_count") for shard in auto2 if isinstance(shard, Mapping)] != [45, 45, 44, 44] or len(auto2) != 4:
        raise Exp002AutoScheduleError("AUTO factual shard drift")
    auto2_ids = [record_id for shard in auto2 for record_id in shard.get("record_ids", [])]
    if len(auto2_ids) != 178 or len(set(auto2_ids)) != 178:
        raise Exp002AutoScheduleError("AUTO factual schedule coverage drift")
    auto3 = stage_map["AUTO-3"].get("shards")
    if not isinstance(auto3, Sequence) or len(auto3) != 4 or [shard.get("condition") for shard in auto3 if isinstance(shard, Mapping)] != list(_FORMULATIONS) or any(shard.get("record_count") != 40 for shard in auto3 if isinstance(shard, Mapping)):
        raise Exp002AutoScheduleError("AUTO formulation schedule drift")
    auto4 = stage_map["AUTO-4"].get("shards")
    if not isinstance(auto4, Sequence) or len(auto4) != 8 or [shard.get("domain") for shard in auto4 if isinstance(shard, Mapping)] != list(_DOMAINS) or any(shard.get("record_count") != 6 for shard in auto4 if isinstance(shard, Mapping)):
        raise Exp002AutoScheduleError("AUTO procedural-domain schedule drift")
    auto5 = stage_map["AUTO-5"].get("shards")
    if not isinstance(auto5, Sequence) or len(auto5) != 6 or any(shard.get("record_ids") != transfer_ids or shard.get("record_count") != 24 for shard in auto5 if isinstance(shard, Mapping)):
        raise Exp002AutoScheduleError("AUTO full-permutation shard binding drift")
    observed_permutations = [entry for shard in auto5 for entry in shard.get("permutations", [])]
    expected_permutations = [{"permutation_id": f"perm-{index:02d}", "mapping": mapping} for index, mapping in enumerate(all_label_permutations(), start=1)]
    if observed_permutations != expected_permutations or any(len(shard.get("permutations", [])) != 4 for shard in auto5 if isinstance(shard, Mapping)):
        raise Exp002AutoScheduleError("AUTO full-permutation schedule drift")


__all__ = ["Exp002AutoScheduleError", "build_auto_schedule", "validate_auto_schedule"]
