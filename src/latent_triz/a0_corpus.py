"""Generator for deterministic A0 corpora.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Mapping

__all__ = [
    "A0CorpusError",
    "A0CorpusManifest",
    "generate_a0_corpus",
    "load_protocol_mapping",
]


class A0CorpusError(RuntimeError):
    """Raised when the protocol or generated corpus is invalid."""


@dataclass(frozen=True)
class A0CorpusManifest:
    payload: Mapping[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.payload[key]


_FORBIDDEN_CASE_TOKENS = {
    "triz",
    "segmentation",
    "segmentation-like",
    "segmentation_like",
    "inversion",
    "inversion-like",
    "inversion_like",
    "operator_proxy_family",
    "label",
}


_CASE_FIELDS_WITH_HASHES = {
    "case_content_sha256",
    "target_content_sha256",
}

_TARGET_FIELDS_WITH_HASHES = {
    "target_content_sha256",
    "case_content_sha256",
}

GENERATOR_ID = "latent-triz-a0-corpus-v1"

_DOMAIN_BLUEPRINTS = {
    "manufacturing": {
        "systems": ["assembly line", "inspection cell", "mixing unit", "packaging station"],
        "stresses": ["load bursts", "timing drift", "resource contention", "quality variation"],
        "goal": "throughput",
        "risk": "scrap",
        "constraints": ["preserve safety interlocks", "reuse installed equipment"],
    },
    "energy": {
        "systems": ["microgrid", "battery bank", "heat network", "turbine array"],
        "stresses": ["demand spikes", "timing drift", "storage imbalance", "weather variation"],
        "goal": "service continuity",
        "risk": "instability",
        "constraints": ["preserve protection limits", "reuse installed capacity"],
    },
    "software": {
        "systems": ["job queue", "cache cluster", "deployment pipeline", "data service"],
        "stresses": ["traffic bursts", "timing races", "resource contention", "request variation"],
        "goal": "response reliability",
        "risk": "service loss",
        "constraints": ["preserve public interfaces", "reuse deployed components"],
    },
    "medicine": {
        "systems": ["clinical workflow", "infusion schedule", "imaging queue", "sample process"],
        "stresses": ["arrival bursts", "timing drift", "resource contention", "case variation"],
        "goal": "care continuity",
        "risk": "treatment delay",
        "constraints": ["preserve clinical safeguards", "reuse approved equipment"],
    },
    "transport": {
        "systems": ["routing hub", "cargo lane", "signal network", "fleet schedule"],
        "stresses": ["arrival bursts", "timing drift", "capacity contention", "route variation"],
        "goal": "flow reliability",
        "risk": "congestion",
        "constraints": ["preserve safety margins", "reuse existing infrastructure"],
    },
    "agriculture": {
        "systems": ["irrigation network", "harvesting line", "storage facility", "sensor mesh"],
        "stresses": ["demand bursts", "timing drift", "resource contention", "weather variation"],
        "goal": "yield stability",
        "risk": "crop loss",
        "constraints": ["preserve resource limits", "reuse installed equipment"],
    },
}

_ROLE_ADJECTIVES = (
    "amber", "brisk", "cobalt", "dappled", "ember", "fallow", "gentle", "harbor",
    "indigo", "juniper", "kindred", "lucid", "mellow", "noble", "opal", "quiet",
)
_ROLE_NOUNS = (
    "arch", "beacon", "circuit", "delta", "engine", "frame", "grove", "hinge",
    "island", "junction", "keystone", "lattice", "module", "node", "orbit", "relay",
)


def generate_a0_corpus(
    mapping_path: str | Path,
    output_dir: str | Path,
    *,
    seed: int | None = None,
) -> dict[str, Any]:
    """Generate deterministic corpus artifacts.

    Parameters
    ----------
    mapping_path:
        Kept for API compatibility; if it is a protocol JSON file it is used.
        Otherwise the implementation resolves
        ``experiments/a0-automated-weak-proxy/protocol.json`` relative to the
        project root.
    output_dir:
        Output directory to write ``cases.jsonl``, split target files, and
        ``manifest.json``.
    seed:
        Overrides protocol seed used for deterministic family split fallback.
    """

    protocol = load_protocol_mapping(mapping_path)
    generation = protocol.get("corpus_generation")
    if not isinstance(generation, Mapping):
        raise A0CorpusError("protocol must define corpus_generation")
    if seed is None:
        seed = int(generation.get("seed", 0))

    protocol_sha = _sha256_text(_stable_compact_json(protocol))

    families = _extract_families(protocol)
    if len(families) < 1:
        raise A0CorpusError("protocol must define at least one family")

    templates = _extract_templates(protocol)

    split_by_family = _assign_family_splits(protocol, families, seed)
    seen_normalized: list[tuple[str, str]] = []
    cases: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []

    for family_id, family in sorted(families.items(), key=lambda item: item[0]):
        split = split_by_family[family_id]
        operator_order = _counterbalanced_operator_order(seed, family_id)
        for variant_index, operator_proxy_family in enumerate(operator_order):
            solution_variant_id = f"variant_{chr(ord('a') + variant_index)}"
            case_id = f"case_{family_id}_{solution_variant_id}"
            target_record_id = f"target_{family_id}_{solution_variant_id}"
            template = templates[family["template_index"]]
            case_record = {
                "case_id": case_id,
                "problem_family_id": family_id,
                "solution_variant_id": solution_variant_id,
                "domain": family["domain"],
                "split": split,
                "problem": family["problem"],
                "constraints": family["constraints"],
                "initial_state": family["initial_state"],
                "desired_improvement": family["desired_improvement"],
                "worsening_consequence": family["worsening_consequence"],
                "resulting_state": family["resulting_state"],
                "transformation": _render_from_template(template[operator_proxy_family], family),
                "solution": (
                    _render_from_template(template[operator_proxy_family], family)
                    + f" The arrangement aims to improve {family['desired_improvement']} "
                    + f"without increasing {family['worsening_consequence']}."
                ),
                "provenance": {
                    "template_id": template["template_id"],
                    "generator_id": GENERATOR_ID,
                    "license": protocol.get("provenance", {}).get("license", "Apache-2.0"),
                    "seed": seed,
                },
            }

            _ensure_forbidden_text(case_record)
            normalized_surface = _normalize_case_text(case_record)
            _reject_duplicate_surface(family_id, normalized_surface, seen_normalized)
            seen_normalized.append((family_id, normalized_surface))

            target_record = {
                "target_record_id": target_record_id,
                "case_id": case_id,
                "problem_family_id": family_id,
                "solution_variant_id": solution_variant_id,
                "operator_proxy_family": operator_proxy_family,
                "generator_rule": template["template_id"],
                "split": split,
                "provenance": {
                    "template_id": template["template_id"],
                    "generator_id": GENERATOR_ID,
                    "license": protocol.get("provenance", {}).get("license", "Apache-2.0"),
                    "seed": seed,
                },
            }

            case_record["case_content_sha256"] = _record_hash(case_record, _CASE_FIELDS_WITH_HASHES)
            target_record["target_content_sha256"] = _record_hash(target_record, _TARGET_FIELDS_WITH_HASHES)
            case_record["target_content_sha256"] = target_record["target_content_sha256"]
            target_record["case_content_sha256"] = case_record["case_content_sha256"]

            cases.append(case_record)
            targets.append(target_record)

    cases.sort(key=lambda row: (row["problem_family_id"], row["solution_variant_id"]))
    targets.sort(key=lambda row: (row["problem_family_id"], row["solution_variant_id"]))

    output_root = Path(output_dir).resolve()
    if output_root.exists():
        if not output_root.is_dir() or any(output_root.iterdir()):
            raise A0CorpusError(f"output directory already exists: {output_root}")
        output_root.rmdir()

    manifest = _build_manifest(cases, targets, split_by_family, seed, protocol_sha, protocol)
    _write_atomic_bundle(output_root, cases, targets, manifest)
    return manifest


def load_protocol_mapping(mapping_path: str | Path) -> dict[str, Any]:
    path = _resolve_protocol_path(mapping_path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise A0CorpusError(f"cannot read protocol: {exc}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise A0CorpusError(f"protocol JSON invalid: {exc}") from exc

    if not isinstance(payload, Mapping):
        raise A0CorpusError("protocol must be a JSON object")
    return dict(payload)


def _resolve_protocol_path(mapping_path: str | Path) -> Path:
    provided = Path(mapping_path)
    if provided.exists() and provided.suffix == ".json":
        return provided

    candidates = [
        Path(__file__).resolve().parents[2] / "experiments/a0-automated-weak-proxy/protocol.json",
        provided.resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise A0CorpusError("protocol file not found at experiments/a0-automated-weak-proxy/protocol.json")


def _extract_families(protocol: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    domains = protocol.get("neutral_domains")
    if not isinstance(domains, list):
        raise A0CorpusError("protocol must define neutral_domains as a list")
    if len(domains) != 6:
        raise A0CorpusError(f"protocol must define exactly 6 domains, found {len(domains)}")
    calibration_count = int(protocol.get("calibration_families_per_domain", 0))
    sealed_count = int(protocol.get("sealed_families_per_domain", 0))
    total_per_domain = calibration_count + sealed_count
    if calibration_count < 1 or sealed_count < 1:
        raise A0CorpusError("calibration and sealed family counts must be positive")
    if total_per_domain > 16:
        raise A0CorpusError("the frozen generator supports at most 16 families per domain")

    families: dict[str, dict[str, Any]] = {}
    global_family_index = 0
    for domain in domains:
        blueprint = _DOMAIN_BLUEPRINTS.get(str(domain))
        if blueprint is None:
            raise A0CorpusError(f"no frozen generator blueprint for domain {domain}")
        family_index = 0
        for system in blueprint["systems"]:
            for stress in blueprint["stresses"]:
                if family_index >= total_per_domain:
                    break
                family_index += 1
                first_role = _neutral_role_name(global_family_index * 2)
                second_role = _neutral_role_name(global_family_index * 2 + 1)
                global_family_index += 1
                family_id = f"{domain}_{family_index:03d}"
                if int(hashlib.sha256(family_id.encode("utf-8")).hexdigest()[:2], 16) % 2:
                    local_role, collective_role = second_role, first_role
                else:
                    local_role, collective_role = first_role, second_role
                families[family_id] = {
                    "problem_family_id": family_id,
                    "domain": str(domain),
                    "problem": (
                        f"For this case, {local_role} coordinates local work while "
                        f"{collective_role} integrates shared outputs. The {system} experiences {stress}."
                    ),
                    "constraints": list(blueprint["constraints"]),
                    "initial_state": f"The {system} handles {stress} through one shared sequence.",
                    "desired_improvement": str(blueprint["goal"]),
                    "worsening_consequence": str(blueprint["risk"]),
                    "resulting_state": f"The {system} maintains {blueprint['goal']} under {stress}.",
                    "local_role": local_role,
                    "collective_role": collective_role,
                    "template_index": (family_index - 1) % 4,
                    "declared_split": "calibration" if family_index <= calibration_count else "sealed",
                }
    return families


def _neutral_role_name(slot: int) -> str:
    capacity = len(_ROLE_ADJECTIVES) * len(_ROLE_NOUNS)
    if not 0 <= slot < capacity:
        raise A0CorpusError("neutral role vocabulary exhausted")
    return f"{_ROLE_ADJECTIVES[slot // len(_ROLE_NOUNS)]} {_ROLE_NOUNS[slot % len(_ROLE_NOUNS)]}"


def _extract_templates(protocol: Mapping[str, Any]) -> list[dict[str, str]]:
    raw = protocol.get("paired_syntax_templates")
    if not isinstance(raw, list) or len(raw) < 4:
        raise A0CorpusError("protocol must include paired_syntax_templates")
    templates: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise A0CorpusError("paired syntax template must be an object")
        parsed = {
            "template_id": str(item.get("template_id", "")).strip(),
            "segmentation_like": str(item.get("segmentation_like", "")).strip(),
            "inversion_like": str(item.get("inversion_like", "")).strip(),
        }
        if not all(parsed.values()):
            raise A0CorpusError("paired syntax template fields must be non-empty")
        templates.append(parsed)
    return templates


def _assign_family_splits(
    protocol: Mapping[str, Any],
    families: Mapping[str, Mapping[str, Any]],
    seed: int,
) -> dict[str, str]:
    del protocol, seed
    return {
        family_id: str(family["declared_split"])
        for family_id, family in families.items()
    }


def _counterbalanced_operator_order(seed: int, family_id: str) -> tuple[str, str]:
    value = int(hashlib.sha256(f"{seed}:{family_id}".encode("utf-8")).hexdigest()[:8], 16)
    if value % 2 == 0:
        return ("segmentation_like", "inversion_like")
    return ("inversion_like", "segmentation_like")


def _render_from_template(template: str, family: Mapping[str, Any]) -> str:
    return template.format(
        problem=family["problem"],
        initial_state=family["initial_state"],
        desired_improvement=family["desired_improvement"],
        worsening_consequence=family["worsening_consequence"],
        resulting_state=family["resulting_state"],
        domain=family["domain"],
        family_id=family["problem_family_id"],
        local_role=family["local_role"],
        collective_role=family["collective_role"],
    )


def _normalize_case_text(case_record: Mapping[str, Any]) -> str:
    concatenated = " ".join(
        [
            case_record["problem"],
            case_record["initial_state"],
            case_record["desired_improvement"],
            case_record["worsening_consequence"],
            case_record["resulting_state"],
            case_record["transformation"],
            case_record["solution"],
        ]
    )
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", concatenated.lower())).strip()


def _reject_duplicate_surface(
    family_id: str,
    candidate: str,
    seen: Iterable[tuple[str, str]],
) -> None:
    for prior_family_id, prior in seen:
        if family_id == prior_family_id:
            continue
        if candidate == prior:
            raise A0CorpusError("duplicate surfaced text detected")
        if SequenceMatcher(None, candidate, prior).ratio() >= 0.995:
            raise A0CorpusError("near-duplicate surfaced text detected")


def _ensure_forbidden_text(case_record: Mapping[str, Any]) -> None:
    payload = " ".join(
        [
            case_record["problem"],
            case_record["initial_state"],
            case_record["desired_improvement"],
            case_record["worsening_consequence"],
            case_record["resulting_state"],
            case_record["transformation"],
            case_record["solution"],
        ]
    ).lower()

    for token in _FORBIDDEN_CASE_TOKENS:
        if token in payload:
            raise A0CorpusError(f"forbidden token in surfaced case text: {token}")


def _record_hash(record: Mapping[str, Any], hash_keys: Iterable[str]) -> str:
    payload = {
        key: value
        for key, value in record.items()
        if key not in hash_keys
    }
    return _sha256_text(_stable_compact_json(payload))


def _sha256_text(value: str | bytes | bytearray) -> str:
    payload = value if isinstance(value, (bytes, bytearray)) else str(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _stable_compact_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_record(record: Mapping[str, Any]) -> str:
    return _sha256_text(_stable_compact_json(record))


def _sha256_file(path: Path) -> tuple[str, int]:
    hasher = hashlib.sha256()
    total = 0
    with path.open("rb") as reader:
        while True:
            chunk = reader.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            hasher.update(chunk)
    return hasher.hexdigest(), total


def _jsonl_line(record: Mapping[str, Any]) -> str:
    return _stable_compact_json(record)


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as writer:
        for row in rows:
            writer.write(_jsonl_line(row))
            writer.write("\n")


def _write_manifest(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as writer:
        writer.write(_stable_compact_json(payload))


def _write_atomic_bundle(
    output_root: Path,
    case_rows: list[dict[str, Any]],
    target_rows: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    parent = output_root.parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(parent)) as tmp_dir:
        staging_root = Path(tmp_dir) / output_root.name
        staging_root.mkdir()

        cases_path = staging_root / "cases.jsonl"
        calibration_targets_path = staging_root / "procedural-targets" / "calibration-targets.jsonl"
        sealed_targets_path = staging_root / "sealed-targets" / "targets.jsonl"
        manifest_path = staging_root / "manifest.json"

        calibration_targets_path.parent.mkdir()
        sealed_targets_path.parent.mkdir()
        _write_jsonl(cases_path, case_rows)
        _write_jsonl(calibration_targets_path, (row for row in target_rows if row["split"] == "calibration"))
        _write_jsonl(sealed_targets_path, (row for row in target_rows if row["split"] == "sealed"))

        case_sha, case_size = _sha256_file(cases_path)
        calibration_sha, calibration_size = _sha256_file(calibration_targets_path)
        sealed_sha, sealed_size = _sha256_file(sealed_targets_path)

        manifest["files"]["cases_jsonl"].update({"path": "cases.jsonl", "sha256": case_sha, "size": case_size})
        manifest["files"]["calibration_targets_jsonl"].update(
            {"path": "procedural-targets/calibration-targets.jsonl", "sha256": calibration_sha, "size": calibration_size}
        )
        manifest["files"]["sealed_targets_jsonl"].update(
            {"path": "sealed-targets/targets.jsonl", "sha256": sealed_sha, "size": sealed_size}
        )

        _write_manifest(manifest_path, manifest)

        if output_root.exists():
            raise A0CorpusError(f"output directory already exists: {output_root}")
        staging_root.replace(output_root)


def _build_manifest(
    case_rows: list[dict[str, Any]],
    target_rows: list[dict[str, Any]],
    family_split: Mapping[str, str],
    seed: int,
    protocol_sha: str,
    protocol: Mapping[str, Any],
) -> dict[str, Any]:
    split_counts: dict[str, int] = {"calibration": 0, "sealed": 0}
    family_counts: dict[str, int] = defaultdict(int)
    family_integrity = {
        "paired_records_by_family": True,
        "uniform_split_by_family": True,
    }

    for case in case_rows:
        split_counts[case["split"]] = split_counts.get(case["split"], 0) + 1
        family_counts[case["problem_family_id"]] += 1
        if family_split[case["problem_family_id"]] != case["split"]:
            family_integrity["uniform_split_by_family"] = False
        if family_counts[case["problem_family_id"]] > 2:
            family_integrity["paired_records_by_family"] = False

    if set(split_counts) != {"calibration", "sealed"}:
        raise A0CorpusError("split counts must include calibration and sealed")

    family_integrity["family_split_sha256"] = _sha256_text(
        _stable_compact_json(dict(sorted(family_split.items())))
    )
    generator_sha, _ = _sha256_file(Path(__file__).resolve())
    return {
        "artifact_class": "a0-corpus-manifest",
        "protocol_id": protocol.get("protocol_id"),
        "protocol_hash": protocol_sha,
        "generator_id": GENERATOR_ID,
        "generator_source_sha256": generator_sha,
        "seed": seed,
        "empirical": bool(protocol.get("empirical", False)),
        "scientific_status": protocol.get("scientific_status"),
        "evidence_eligible": bool(protocol.get("evidence_eligible", False)),
        "expert_validated": bool(protocol.get("expert_validated", False)),
        "claim_ids": list(protocol.get("claim_ids", [])),
        "neutral_domains": sorted({row["domain"] for row in case_rows}),
        "counts": {
            "total_cases": len(case_rows),
            "total_targets": len(target_rows),
            "families": len(family_counts),
            "domains": len({row["domain"] for row in case_rows}),
            "calibration_cases": split_counts["calibration"],
            "sealed_cases": split_counts["sealed"],
        },
        "splits": ["calibration", "sealed"],
        "family_integrity": family_integrity,
        "preregistered_layers": list(protocol.get("preregistered_layers", [])),
        "token_sites": list(protocol.get("token_sites", [])),
        "views": list(protocol.get("views", [])),
        "license": protocol.get("provenance", {}).get("license", "Apache-2.0"),
        "files": {
            "cases_jsonl": {"path": "cases.jsonl", "sha256": "", "size": 0},
            "calibration_targets_jsonl": {
                "path": "procedural-targets/calibration-targets.jsonl",
                "sha256": "",
                "size": 0,
            },
            "sealed_targets_jsonl": {
                "path": "sealed-targets/targets.jsonl",
                "sha256": "",
                "size": 0,
            },
        },
    }
