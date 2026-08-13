from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from collections import defaultdict


STANDARD_DIMENSIONS = (
    "contradiction_resolution",
    "principle_use",
    "feasibility",
    "novelty",
    "constraint_adherence",
    "terminology_only",
)


class PilotError(RuntimeError):
    pass


def prepare_packets(cases_path: str | Sequence[str], arms: Sequence[str], seed: int) -> List[dict[str, Any]]:
    clean_arms = _normalize_arms(arms)
    case_records = _read_input_records(cases_path)
    _validate_case_records(case_records, clean_arms)

    packets = [_prepare_packet(index, case, clean_arms, seed) for index, case in enumerate(case_records)]
    return packets


def _prepare_packet(index: int, case: Dict[str, Any], arms: Sequence[str], seed: int) -> dict[str, Any]:
    case_id = str(case["case_id"])
    pair_id = str(case.get("pair_id", case_id)) if case.get("pair_id") is not None else case_id
    case_seed = f"{seed}:{case_id}:{index}".encode("utf-8")
    rng = random.Random(hashlib.sha256(case_seed).hexdigest())
    shuffled = list(arms)
    rng.shuffle(shuffled)
    blind_labels = _blind_labels(len(shuffled))
    arms_by_blind = {blind: arm for blind, arm in zip(blind_labels, shuffled)}
    packet_id = _packet_id(case_id, index, seed)
    source_fields = (
        "case_id",
        "domain",
        "problem",
        "constraints",
        "initial_state",
        "desired_improvement",
        "worsening_consequence",
    )
    source = {field: case[field] for field in source_fields if field in case}
    return {
        "packet_id": packet_id,
        "case_id": case_id,
        "pair_id": pair_id,
        "arms_by_blind": arms_by_blind,
        "blind_order": blind_labels,
        "seed": seed,
        "source": source,
    }


def _validate_case_records(case_records: Sequence[Dict[str, Any]], arms: Sequence[str]) -> None:
    seen_case_ids = set()
    for case in case_records:
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or case_id.strip() == "":
            raise PilotError("each case must have a non-empty case_id")
        if case_id in seen_case_ids:
            raise PilotError(f"duplicate case_id: {case_id}")
        seen_case_ids.add(case_id)

        case_arms = case.get("arms")
        if case_arms is None:
            continue
        if not isinstance(case_arms, list) or not case_arms:
            raise PilotError(f"case {case_id} has invalid arms")
        if sorted(map(str, case_arms)) != sorted(arms):
            raise PilotError(f"case {case_id} does not cover all required arms")


def score_annotations(
    packets_path: str,
    responses_path: str,
    annotations_path: str,
    dimensions: Sequence[str] | None = None,
) -> dict[str, Any]:
    packets = _read_input_records(packets_path)
    if not packets:
        raise PilotError("no packets")
    packet_by_id = _index_packets(packets)

    responses = _read_input_records(responses_path)
    if not responses:
        raise PilotError("no responses")

    response_by_id, response_pair_map = _index_responses(responses, packet_by_id)

    annotations = _read_input_records(annotations_path)
    if not annotations:
        raise PilotError("no annotations")

    fingerprint_packets = _fingerprint_file(packets_path)
    fingerprint_responses = _fingerprint_file(responses_path)
    fingerprint_annotations = _fingerprint_file(annotations_path)

    dim_list = list(dimensions or STANDARD_DIMENSIONS)
    if dim_list != list(STANDARD_DIMENSIONS):
        raise PilotError("dimensions must match the standard Stage 1 rubric")

    aggregates: dict[str, dict[str, list[float]]] = defaultdict(lambda: {dim: [] for dim in dim_list})
    pair_aggregates: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: {dim: [] for dim in dim_list})
    )
    seen_annotation_ids: set[str] = set()
    seen_response_annotations: set[str] = set()
    packet_annotations: dict[str, set[str]] = defaultdict(set)
    annotation_count = 0
    non_empirical = True

    for response_id, response in response_by_id.items():
        if response.get("non_empirical") is not True:
            non_empirical = False

    for annotation in annotations:
        annotation_count += 1
        _reject_extra_fields(
            annotation,
            {"annotation_id", "response_id", "packet_id", "blinded_arm", "rater_id", "scores", "annotated_at", "non_empirical"},
            "annotation",
        )
        annotation_id = _require_nonempty_string(annotation, "annotation_id", "annotation")
        if annotation_id in seen_annotation_ids:
            raise PilotError(f"duplicate annotation_id: {annotation_id}")
        seen_annotation_ids.add(annotation_id)
        _require_nonempty_string(annotation, "rater_id", f"annotation {annotation_id}")
        _validate_utc_timestamp(annotation.get("annotated_at"), f"annotation {annotation_id} annotated_at")
        if not isinstance(annotation.get("non_empirical"), bool):
            raise PilotError(f"annotation {annotation_id} has invalid non_empirical")

        response_id = annotation.get("response_id")
        if not isinstance(response_id, str) or response_id == "":
            raise PilotError("each annotation must include response_id")
        response = response_by_id.get(response_id)
        if response is None:
            raise PilotError(f"annotation for unknown response: {response_id}")

        packet_id = annotation.get("packet_id")
        if not isinstance(packet_id, str) or not packet_id:
            raise PilotError(f"annotation {annotation_id}: missing packet_id")
        response_packet_id = response["packet_id"]
        if packet_id != response_packet_id:
            raise PilotError(f"annotation for response {response_id} does not match packet_id")

        blind_label = annotation.get("blinded_arm")
        if not isinstance(blind_label, str):
            raise PilotError(f"annotation on packet {packet_id} missing blinded_arm")
        response_blind_label = response["blinded_arm"]
        if blind_label != response_blind_label:
            raise PilotError(f"annotation for response {response_id} does not match blinded_arm")

        packet = packet_by_id[packet_id]
        arm_label = packet["arms_by_blind"].get(blind_label)
        if arm_label is None:
            raise PilotError(f"unknown blinded_arm '{blind_label}' for packet {packet_id}")

        score_payload = annotation.get("scores")
        if score_payload is None:
            score_payload = {dim: annotation.get(dim) for dim in dim_list}
        if not isinstance(score_payload, dict):
            raise PilotError(f"invalid scores for annotation {annotation_id}")
        if set(score_payload) != set(dim_list):
            raise PilotError(f"annotation {annotation_id} scores must contain exactly the configured dimensions")

        for dim in dim_list:
            if dim not in score_payload:
                raise PilotError(f"missing dimension '{dim}' for annotation {annotation_id}")
            value = score_payload[dim]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 4:
                raise PilotError(f"invalid score for {dim} in annotation {annotation_id}")
            aggregates[arm_label][dim].append(value)
            pair_key = str(packet.get("pair_id", ""))
            pair_aggregates[pair_key][arm_label][dim].append(value)

        seen_response_annotations.add(response_id)
        packet_annotations[packet_id].add(arm_label)

        if annotation.get("non_empirical") is not True:
            non_empirical = False

    _validate_coverage(packet_by_id, response_pair_map, response_by_id, seen_response_annotations)

    per_arm_means: dict[str, dict[str, float]] = {}
    for arm, dim_values in sorted(aggregates.items(), key=lambda item: item[0]):
        per_arm_means[arm] = {}
        for dim in dim_list:
            values = dim_values.get(dim, [])
            per_arm_means[arm][dim] = sum(values) / len(values) if values else 0.0

    pair_deltas = _compute_paired_deltas_from_aggregates(pair_aggregates, dim_list)

    return {
        "schema_version": "1.0",
        "counts": {
            "cases": len(_unique_case_ids(packets)),
            "packets": len(packets),
            "responses": len(response_by_id),
            "annotations": annotation_count,
            "dimensions": len(dim_list),
        },
        "dimensions": dim_list,
        "per_arm_means": per_arm_means,
        "paired_deltas": pair_deltas,
        "non_empirical": non_empirical,
        "provenance": {
            "packets_fingerprint": _prefixed_fingerprint(fingerprint_packets),
            "responses_fingerprint": _prefixed_fingerprint(fingerprint_responses),
            "annotations_fingerprint": _prefixed_fingerprint(fingerprint_annotations),
        },
    }


def _validate_coverage(
    packets_by_id: Dict[str, Dict[str, Any]],
    response_pair_map: Dict[tuple[str, str], str],
    response_by_id: Dict[str, Dict[str, Any]],
    seen_response_annotations: set[str],
) -> None:
    required_pairs: set[tuple[str, str]] = set()
    for packet_id, packet in packets_by_id.items():
        for blind_label in packet["arms_by_blind"]:
            required_pairs.add((packet_id, blind_label))

    seen_pairs = set(response_pair_map.keys())
    if seen_pairs != required_pairs:
        missing = sorted(f"{packet}:{blind}" for packet, blind in sorted(required_pairs - seen_pairs))
        extra = sorted(f"{packet}:{blind}" for packet, blind in sorted(seen_pairs - required_pairs))
        if missing and extra:
            raise PilotError(f"response coverage mismatch; missing responses for {missing}; extra responses for {extra}")
        if missing:
            raise PilotError(f"missing responses for packets/blinded_arms: {missing}")
        if extra:
            raise PilotError(f"extra responses for packets/blinded_arms: {extra}")

    for pair, response_id in response_pair_map.items():
        if response_id in seen_response_annotations:
            continue
        raise PilotError(f"missing annotations for response: {response_id} ({pair[0]}:{pair[1]})")

    if len(response_by_id) != len(seen_response_annotations):
        extra_annotations = sorted(set(response_by_id) - seen_response_annotations)
        if extra_annotations:
            raise PilotError(f"extra annotations for unknown responses: {extra_annotations}")


def _index_packets(packets: Sequence[Dict[str, Any]]) -> dict[str, Dict[str, Any]]:
    packet_by_id: dict[str, Dict[str, Any]] = {}
    for packet in packets:
        _reject_extra_fields(
            packet,
            {"packet_id", "case_id", "pair_id", "arms_by_blind", "blind_order", "seed", "source"},
            "packet",
        )
        packet_id = packet.get("packet_id")
        if not isinstance(packet_id, str):
            raise PilotError("each packet must have a packet_id")
        if packet_id in packet_by_id:
            raise PilotError("duplicate packet_id in packets")

        case_id = packet.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise PilotError(f"packet {packet_id} has invalid case_id")

        arms_by_blind = packet.get("arms_by_blind")
        if not isinstance(arms_by_blind, dict) or set(arms_by_blind) != {"A", "B"}:
            raise PilotError(f"packet {packet_id} has invalid arms_by_blind")

        for blind_label, arm_label in arms_by_blind.items():
            if not isinstance(blind_label, str) or not blind_label:
                raise PilotError(f"packet {packet_id} has invalid blinded arm")
            if not isinstance(arm_label, str) or not arm_label:
                raise PilotError(f"packet {packet_id} has invalid arm label")
        if set(arms_by_blind.values()) != {"control", "treatment"}:
            raise PilotError(f"packet {packet_id} must map A/B to control/treatment")

        if packet.get("blind_order") not in (["A", "B"], ["B", "A"]):
            raise PilotError(f"packet {packet_id} has invalid blind_order")

        pair_id = packet.get("pair_id")
        if not isinstance(pair_id, str) or not pair_id:
            raise PilotError(f"packet {packet_id} has invalid pair_id")

        seed = packet.get("seed")
        if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
            raise PilotError(f"packet {packet_id} has invalid seed")

        source = packet.get("source")
        if not isinstance(source, dict) or source.get("case_id") != case_id:
            raise PilotError(f"packet {packet_id} has invalid source")

        packet_by_id[packet_id] = packet
    return packet_by_id


def _index_responses(
    responses: Sequence[Dict[str, Any]],
    packet_by_id: Dict[str, Dict[str, Any]],
) -> tuple[dict[str, Dict[str, Any]], dict[tuple[str, str], str]]:
    response_by_id: dict[str, Dict[str, Any]] = {}
    response_pair_map: dict[tuple[str, str], str] = {}

    for response in responses:
        _reject_extra_fields(
            response,
            {"response_id", "packet_id", "blinded_arm", "model", "response_text", "generated_at", "non_empirical"},
            "response",
        )
        response_id = response.get("response_id")
        if not isinstance(response_id, str) or response_id == "":
            raise PilotError("each response must include response_id")
        if response_id in response_by_id:
            raise PilotError(f"duplicate response_id: {response_id}")

        model = response.get("model")
        if not isinstance(model, dict):
            raise PilotError(f"response {response_id} has invalid model")
        for field in ("name", "family", "revision"):
            _require_nonempty_string(model, field, f"response {response_id} model")
        _require_nonempty_string(response, "response_text", f"response {response_id}")
        _validate_utc_timestamp(response.get("generated_at"), f"response {response_id} generated_at")
        if not isinstance(response.get("non_empirical"), bool):
            raise PilotError(f"response {response_id} has invalid non_empirical")

        packet_id = response.get("packet_id")
        if not isinstance(packet_id, str):
            raise PilotError(f"response {response_id} missing packet_id")

        packet = packet_by_id.get(packet_id)
        if packet is None:
            raise PilotError(f"response for unknown packet: {packet_id}")

        blind_label = response.get("blinded_arm")
        if not isinstance(blind_label, str) or blind_label == "":
            raise PilotError(f"response {response_id} missing blinded_arm")

        if blind_label not in packet["arms_by_blind"]:
            raise PilotError(f"response {response_id} has invalid blinded_arm '{blind_label}'")

        pair = (packet_id, blind_label)
        if pair in response_pair_map:
            raise PilotError(f"multiple responses for packet {packet_id} and blinded_arm {blind_label}")

        response_pair_map[pair] = response_id
        response_by_id[response_id] = response

    return response_by_id, response_pair_map


def _compute_paired_deltas_from_aggregates(
    pair_aggregates: dict[str, dict[str, dict[str, list[float]]]],
    dimensions: Sequence[str],
) -> dict[str, dict[str, dict[str, float]]]:
    pair_deltas: dict[str, dict[str, dict[str, float]]] = {}
    for pair_key in sorted(pair_aggregates):
        if pair_key == "":
            continue
        arms = sorted(pair_aggregates[pair_key].keys())
        if len(arms) < 2:
            continue

        def _mean(values: list[float]) -> float:
            return sum(values) / len(values) if values else 0.0

        pair_deltas[str(pair_key)] = {}
        pair_delta = pair_deltas[str(pair_key)]
        pair_means: dict[str, dict[str, float]] = {}
        for arm in arms:
            pair_means[arm] = {
                dim: _mean(pair_aggregates[pair_key][arm].get(dim, []))
                for dim in dimensions
            }

        for i in range(len(arms)):
            for j in range(i + 1, len(arms)):
                left = arms[i]
                right = arms[j]
                pair_key_label = f"{left}|{right}"
                pair_delta[pair_key_label] = {
                    dim: pair_means[right][dim] - pair_means[left][dim]
                    for dim in dimensions
                }

    return pair_deltas


def _unique_case_ids(packets: Sequence[Dict[str, Any]]) -> set[str]:
    return {str(packet["case_id"]) for packet in packets}


def _normalize_arms(arms: Sequence[str]) -> list[str]:
    normalized = [str(arm).strip() for arm in arms]
    if any(not arm for arm in normalized):
        raise PilotError("arm names must be non-empty")
    if len(set(normalized)) != len(normalized):
        raise PilotError("arm names must be unique")
    if set(normalized) != {"control", "treatment"} or len(normalized) != 2:
        raise PilotError("arms must be exactly 'control' and 'treatment'")
    return normalized


def _require_nonempty_string(record: Dict[str, Any], field: str, context: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PilotError(f"{context} has invalid {field}")
    return value


def _reject_extra_fields(record: Dict[str, Any], allowed: set[str], context: str) -> None:
    extra = sorted(set(record) - allowed)
    if extra:
        raise PilotError(f"{context} has unsupported fields: {extra}")


def _validate_utc_timestamp(value: Any, context: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise PilotError(f"{context} must be a UTC date-time")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise PilotError(f"{context} must be a UTC date-time") from None


def _packet_id(case_id: str, index: int, seed: int) -> str:
    payload = f"{seed}:{index}:{case_id}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:12]
    return f"packet-{index + 1:03d}-{digest}"


def _blind_labels(count: int) -> list[str]:
    if count > 26:
        raise PilotError("more than 26 arms not supported")
    return [chr(ord("A") + idx) for idx in range(count)]


def _fingerprint_file(path: str) -> str:
    data = Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest()


def _prefixed_fingerprint(digest: str) -> str:
    return f"sha256:{digest}"


def _read_input_records(path_or_records: str | Sequence[str]) -> list[Dict[str, Any]]:
    if isinstance(path_or_records, (list, tuple)):
        all_records: list[Dict[str, Any]] = []
        for path in path_or_records:
            all_records.extend(_read_input_records(str(path)))
        return all_records
    path = Path(path_or_records)
    if not path.is_file():
        raise PilotError(f"file not found: {path}")
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        return _read_jsonl(path)
    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        if isinstance(data, list):
            records: list[Dict[str, Any]] = []
            for index, item in enumerate(data, start=1):
                if not isinstance(item, dict):
                    raise PilotError(f"non-object JSON array record in {path}:{index}")
                records.append(item)
            return records
        raise PilotError(f"expected JSON array in {path}")
    return _read_jsonl(path)


def _read_jsonl(path: Path) -> list[Dict[str, Any]]:
    records: list[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fp:
        for line_no, raw in enumerate(fp, start=1):
            value = raw.strip()
            if not value:
                continue
            try:
                obj = json.loads(value)
            except json.JSONDecodeError as exc:
                raise PilotError(f"invalid JSONL record in {path}:{line_no}: {exc}") from None
            if not isinstance(obj, dict):
                raise PilotError(f"non-object JSONL record in {path}:{line_no}")
            records.append(obj)
    return records


def write_jsonl(path: str, records: Iterable[dict[str, Any]]) -> None:
    output = Path(path)
    with output.open("w", encoding="utf-8") as fp:
        for record in records:
            json.dump(record, fp, ensure_ascii=False, sort_keys=True)
            fp.write("\n")


def stable_json_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)
