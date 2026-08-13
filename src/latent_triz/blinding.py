from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


class BlindingError(RuntimeError):
    pass


def _read_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    source = Path(path)
    records: List[Dict[str, Any]] = []
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise BlindingError(f"cannot read {source}: {exc}") from exc
    for line_number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BlindingError(f"{source}:{line_number}: invalid JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise BlindingError(f"{source}:{line_number}: record must be an object")
        records.append(record)
    return records


def build_evaluator_bundle(
    packets_path: str | Path,
    responses_path: str | Path,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    packets = _read_jsonl(packets_path)
    responses = _read_jsonl(responses_path)
    if not packets:
        raise BlindingError("no packets")
    if not responses:
        raise BlindingError("no responses")

    response_index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for response in responses:
        response_id = response.get("response_id")
        packet_id = response.get("packet_id")
        blind = response.get("blinded_arm")
        if not all(isinstance(value, str) and value for value in (response_id, packet_id, blind)):
            raise BlindingError("each response requires response_id, packet_id, and blinded_arm")
        if response.get("non_empirical") is not True:
            raise BlindingError(f"response {response_id} must declare non_empirical true for this smoke export")
        key = (packet_id, blind)
        if key in response_index:
            raise BlindingError(f"duplicate response for packet {packet_id} and blind label {blind}")
        response_index[key] = response

    evaluator_packets: List[Dict[str, Any]] = []
    allocations: List[Dict[str, Any]] = []
    expected_response_keys: set[Tuple[str, str]] = set()
    seen_packet_ids: set[str] = set()
    for packet in packets:
        packet_id = packet.get("packet_id")
        if not isinstance(packet_id, str) or not packet_id:
            raise BlindingError("each packet requires packet_id")
        if packet_id in seen_packet_ids:
            raise BlindingError(f"duplicate packet_id: {packet_id}")
        seen_packet_ids.add(packet_id)
        if packet.get("non_empirical") is not True:
            raise BlindingError(f"packet {packet_id} must declare non_empirical true for this smoke export")
        mapping = packet.get("arms_by_blind")
        blind_order = packet.get("blind_order")
        if not isinstance(mapping, dict) or set(mapping) != {"A", "B"}:
            raise BlindingError(f"packet {packet_id} has invalid allocation mapping")
        if not isinstance(blind_order, list) or set(blind_order) != {"A", "B"}:
            raise BlindingError(f"packet {packet_id} has invalid blind_order")

        blinded_responses: List[Dict[str, Any]] = []
        for blind in blind_order:
            response_key = (packet_id, blind)
            expected_response_keys.add(response_key)
            response = response_index.get(response_key)
            if response is None:
                raise BlindingError(f"missing response for packet {packet_id} and blind label {blind}")
            blinded_responses.append(
                {
                    "blind_label": blind,
                    "response_id": response["response_id"],
                    "response_text": response.get("response_text", ""),
                }
            )

        evaluator_packets.append(
            {
                "packet_id": packet_id,
                "case_id": packet.get("case_id"),
                "pair_id": packet.get("pair_id"),
                "source": packet.get("source", {}),
                "responses": blinded_responses,
                "non_empirical": True,
            }
        )
        allocations.append({"packet_id": packet_id, "arms_by_blind": mapping})

    extra = sorted(set(response_index) - expected_response_keys)
    if extra:
        packet_id, blind = extra[0]
        raise BlindingError(f"response references unknown packet/blind pair: {packet_id}/{blind}")

    allocation_key = {
        "schema_version": "1.0",
        "status": "sealed",
        "non_empirical": True,
        "allocations": allocations,
    }
    return evaluator_packets, allocation_key


def write_evaluator_bundle(
    evaluator_packets: Iterable[Dict[str, Any]],
    allocation_key: Dict[str, Any],
    evaluator_output: str | Path,
    key_output: str | Path,
) -> None:
    evaluator_path = Path(evaluator_output)
    key_path = Path(key_output)
    if evaluator_path.resolve() == key_path.resolve():
        raise BlindingError("evaluator output and allocation key output must be different paths")
    evaluator_payload = "".join(
        json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n" for record in evaluator_packets
    )
    key_payload = json.dumps(allocation_key, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    _atomic_write(evaluator_path, evaluator_payload)
    _atomic_write(key_path, key_payload)


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise
