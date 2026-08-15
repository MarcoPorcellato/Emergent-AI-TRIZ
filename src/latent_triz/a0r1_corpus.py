"""Deterministic generator for R1-independent A0-R1 corpus artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

SPDX_LICENSE = "Apache-2.0"
GENERATOR_ID = "latent-triz-a0-r1-corpus-v1"
DEFAULT_PROTOCOL_ID = "a0-r1-tier-r1-v1.0"
R1_SEED = 20260815
PARTITION_CALIBRATION = "calibration"
PARTITION_SEALED = "sealed"
PARTITION_FIELD = "split"

EPISTEMIC = {
    "empirical": True,
    "scientific_status": "exploratory",
    "evidence_eligible": False,
    "expert_validated": False,
    "claim_ids": [],
}

DOMAIN_BLUEPRINTS: tuple[tuple[str, Mapping[str, Any]], ...] = (
    (
        "agriculture",
        {
            "systems": ("irrigation network", "harvest line", "storage shed", "sensor mesh"),
            "goal": "yield stability",
            "risk": "crop loss",
            "constraints": ("preserve field limits", "reuse available equipment"),
        },
    ),
    (
        "energy",
        {
            "systems": ("microgrid", "battery bank", "heat network", "turbine cluster"),
            "goal": "service continuity",
            "risk": "instability",
            "constraints": ("preserve protection limits", "reuse installed capacity"),
        },
    ),
    (
        "manufacturing",
        {
            "systems": ("assembly line", "inspection cell", "mixing unit", "packaging station"),
            "goal": "throughput",
            "risk": "scrap",
            "constraints": ("preserve safety", "reuse existing tooling"),
        },
    ),
    (
        "medicine",
        {
            "systems": ("clinical workflow", "infusion schedule", "imaging queue", "sample logistics"),
            "goal": "care continuity",
            "risk": "treatment delay",
            "constraints": ("preserve safeguards", "reuse approved devices"),
        },
    ),
    (
        "software",
        {
            "systems": ("job queue", "cache cluster", "deployment pipeline", "data service"),
            "goal": "response reliability",
            "risk": "service loss",
            "constraints": ("preserve public interfaces", "reuse established components"),
        },
    ),
    (
        "transport",
        {
            "systems": ("routing hub", "cargo lane", "signal network", "fleet schedule"),
            "goal": "flow reliability",
            "risk": "congestion",
            "constraints": ("preserve safety margins", "reuse existing infrastructure"),
        },
    ),
)

CASE_TEXT_TEMPLATES = (
    {
        "template_id": "r1-opaque-order-001",
        "segmentation_like": "{local_role} cues before {collective_role}; {collective_role} cues before {local_role} at {system}.",
        "inversion_like": "{collective_role} cues before {local_role}; {local_role} cues before {collective_role} at {system}.",
    },
    {
        "template_id": "r1-opaque-order-002",
        "segmentation_like": "At {system}, {local_role} relays to {collective_role}, then {collective_role} relays to {local_role}.",
        "inversion_like": "At {system}, {collective_role} relays to {local_role}, then {local_role} relays to {collective_role}.",
    },
    {
        "template_id": "r1-opaque-order-003",
        "segmentation_like": "{local_role} gates {collective_role} while {collective_role} gates {local_role} through {system}.",
        "inversion_like": "{collective_role} gates {local_role} while {local_role} gates {collective_role} through {system}.",
    },
    {
        "template_id": "r1-opaque-order-004",
        "segmentation_like": "{local_role} follows {collective_role} after {collective_role} follows {local_role} within {system}.",
        "inversion_like": "{collective_role} follows {local_role} after {local_role} follows {collective_role} within {system}.",
    },
)

ROLE_PREFIX = (
    "amber", "cobalt", "delta", "ember", "fallow", "harbor", "ivory", "keel",
    "lattice", "merit", "noble", "opal", "quiet", "rivet", "sovereign", "zen",
)
ROLE_SUFFIX = (
    "arch", "beacon", "cove", "dial", "ember", "frame", "grove", "haze", "islet", "junction",
    "kernel", "link", "node", "orbit", "pivot", "quota",
)


class A0R1CorpusError(RuntimeError):
    """Raised when protocol or generated corpus is invalid."""


@dataclass(frozen=True)
class R1CorpusConfig:
    protocol_path: Path
    protocol: Mapping[str, Any]
    protocol_id: str
    seed: int


def generate_a0r1_corpus(
    protocol_path: str | Path,
    output_dir: str | Path,
    *,
    seed: int | None = None,
) -> dict[str, Any]:
    config = _load_config(protocol_path, seed)
    families = _build_families(config.seed)
    family_split = _assign_family_splits(families, calibration_per_domain=4)

    cases: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    for family_id in sorted(families):
        family = families[family_id]
        split = family_split[family_id]
        operator_order = _counterbalanced_operator_order(config.seed, family_id)
        template = CASE_TEXT_TEMPLATES[_template_index(config.seed, family_id)]
        for variant_index, operator_proxy_family in enumerate(operator_order):
            solution_variant_id = f"variant_{chr(ord('a') + variant_index)}"
            case_id = f"case_{family_id}_{solution_variant_id}"
            target_id = f"target_{family_id}_{solution_variant_id}"

            transformation = _render_transformation(template[operator_proxy_family], family)
            case_record = {
                "case_id": case_id,
                "problem_family_id": family_id,
                "solution_variant_id": solution_variant_id,
                "domain": family["domain"],
                "split": split,
                "problem": family["problem"],
                "constraints": list(family["constraints"]),
                "initial_state": family["initial_state"],
                "desired_improvement": family["desired_improvement"],
                "worsening_consequence": family["worsening_consequence"],
                "resulting_state": family["resulting_state"],
                "transformation": transformation,
                "solution": f"{transformation} {family['solution_suffix']}",
                "provenance": {
                    "template_id": template["template_id"],
                    "generator_id": GENERATOR_ID,
                    "seed": config.seed,
                    "license": SPDX_LICENSE,
                },
            }

            target_record = {
                "target_record_id": target_id,
                "case_id": case_id,
                "problem_family_id": family_id,
                "solution_variant_id": solution_variant_id,
                "split": split,
                "operator_proxy_family": operator_proxy_family,
                "generator_rule": template["template_id"],
                "provenance": {
                    "template_id": template["template_id"],
                    "generator_id": GENERATOR_ID,
                    "seed": config.seed,
                    "license": SPDX_LICENSE,
                },
            }
            case_record["case_content_sha256"] = _record_hash(case_record, {"case_content_sha256", "target_content_sha256"})
            target_record["target_content_sha256"] = _record_hash(target_record, {"target_content_sha256", "case_content_sha256"})
            case_record["target_content_sha256"] = target_record["target_content_sha256"]
            target_record["case_content_sha256"] = case_record["case_content_sha256"]
            cases.append(case_record)
            targets.append(target_record)

    cases.sort(key=lambda row: (row["problem_family_id"], row["solution_variant_id"], row["case_id"]))
    targets.sort(key=lambda row: (row["problem_family_id"], row["solution_variant_id"], row["case_id"]))

    manifest = _build_manifest(config, cases, targets, family_split)
    _write_bundle(Path(output_dir).resolve(), cases, targets, manifest)
    return manifest


def _load_config(protocol_path: str | Path, seed: int | None) -> R1CorpusConfig:
    path = Path(protocol_path)
    if not path.exists():
        raise A0R1CorpusError(f"protocol file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise A0R1CorpusError(f"cannot read protocol: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise A0R1CorpusError(f"protocol JSON invalid: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise A0R1CorpusError("protocol payload must be an object")

    protocol_id = str(payload.get("protocol_id", "")).strip()
    if not re.fullmatch(r"a0-r1-tier-r1-v\d+\.\d+", protocol_id):
        raise A0R1CorpusError("protocol_id is not a valid A0-R1 Tier R1 identifier")
    if payload.get("protocol_status") != "planned":
        raise A0R1CorpusError("corpus generation requires a planned protocol")

    calibration = payload.get("calibration")
    if not isinstance(calibration, Mapping):
        raise A0R1CorpusError("protocol must define calibration")
    protocol_seed = calibration.get("deterministic_seed")
    if protocol_seed != R1_SEED:
        raise A0R1CorpusError(f"protocol deterministic_seed must be {R1_SEED}")
    chosen_seed = protocol_seed if seed is None else seed
    if not isinstance(chosen_seed, int):
        raise A0R1CorpusError("seed must be integer")
    if chosen_seed != R1_SEED:
        raise A0R1CorpusError(f"seed override must equal frozen design seed {R1_SEED}")

    return R1CorpusConfig(protocol_path=path, protocol=payload, protocol_id=protocol_id, seed=chosen_seed)


def _build_families(seed: int) -> dict[str, dict[str, Any]]:
    del seed
    families: dict[str, dict[str, Any]] = {}
    slot = 0
    for domain, blueprint in DOMAIN_BLUEPRINTS:
        for local_index in range(8):
            family_id = f"r1_{domain}_{local_index:02d}"
            local_role, collective_role = _role_pair(slot)
            slot += 1
            system = blueprint["systems"][local_index % len(blueprint["systems"])]
            stress = f"{(local_index + 1) * 5}x demand fluctuation"
            families[family_id] = {
                "domain": domain,
                "system": system,
                "stress": stress,
                "goal": blueprint["goal"],
                "risk": blueprint["risk"],
                "constraints": list(blueprint["constraints"]),
                "local_role": local_role,
                "collective_role": collective_role,
                "problem": (
                    f"{local_role} in {system} experiences {stress} with {collective_role} as peer."
                ),
                "initial_state": f"{system} is currently unstable under {stress}.",
                "desired_improvement": f"sustained {blueprint['goal']}",
                "worsening_consequence": f"worse {blueprint['risk']}",
                "resulting_state": f"{system} attains {blueprint['goal']} despite {stress}.",
                "solution_suffix": f"Constraints: {'; '.join(blueprint['constraints'])}.",
            }
    return families


def _role_pair(slot: int) -> tuple[str, str]:
    a = f"{ROLE_PREFIX[slot % len(ROLE_PREFIX)]} {ROLE_SUFFIX[(slot // len(ROLE_PREFIX)) % len(ROLE_SUFFIX)]}"
    b = f"{ROLE_PREFIX[(slot + 1) % len(ROLE_PREFIX)]} {ROLE_SUFFIX[(slot // len(ROLE_PREFIX) + 4) % len(ROLE_SUFFIX)]}"
    return a, b


def _assign_family_splits(families: Mapping[str, Mapping[str, Any]], calibration_per_domain: int) -> dict[str, str]:
    if calibration_per_domain <= 0:
        raise A0R1CorpusError("calibration_per_domain must be positive")
    by_domain: dict[str, list[str]] = defaultdict(list)
    for family_id, family in families.items():
        by_domain[family["domain"]].append(family_id)

    mapping: dict[str, str] = {}
    for domain_families in by_domain.values():
        if len(domain_families) != 8:
            raise A0R1CorpusError("invalid families per domain")
        for family_id in sorted(domain_families)[:calibration_per_domain]:
            mapping[family_id] = PARTITION_CALIBRATION
        for family_id in sorted(domain_families)[calibration_per_domain:]:
            mapping[family_id] = PARTITION_SEALED
    return mapping


def _counterbalanced_operator_order(seed: int, family_id: str) -> tuple[str, str]:
    digest = hashlib.sha256(f"{seed}:{family_id}".encode("utf-8")).hexdigest()
    if int(digest[:8], 16) % 2 == 0:
        return ("segmentation_like", "inversion_like")
    return ("inversion_like", "segmentation_like")


def _template_index(seed: int, family_id: str) -> int:
    digest = hashlib.sha256(f"template:{seed}:{family_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % len(CASE_TEXT_TEMPLATES)


def _render_transformation(template: str, family: Mapping[str, Any]) -> str:
    return template.format(
        local_role=family["local_role"],
        collective_role=family["collective_role"],
        system=family["system"],
        stress=family["stress"],
        domain=family["domain"],
        risk=family["risk"],
    )


def _record_hash(record: Mapping[str, Any], hash_excludes: Iterable[str]) -> str:
    payload = {key: value for key, value in record.items() if key not in hash_excludes}
    return _sha256_text(_stable_compact_json(payload))


def _stable_compact_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(value: str | bytes | bytearray) -> str:
    payload = value if isinstance(value, (bytes, bytearray)) else str(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> tuple[str, int]:
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as reader:
        while True:
            chunk = reader.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            hasher.update(chunk)
    return hasher.hexdigest(), size


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as writer:
        for row in rows:
            writer.write(_stable_compact_json(row))
            writer.write("\n")


def _write_manifest(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as writer:
        writer.write(_stable_compact_json(payload))


def _write_bundle(output_root: Path, cases: list[dict[str, Any]], targets: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    if output_root.exists():
        raise A0R1CorpusError(f"output directory already exists: {output_root}")
    output_root.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=str(output_root.parent)) as tmp:
        staging = Path(tmp) / output_root.name
        staging.mkdir()
        cases_path = staging / "cases.jsonl"
        cal_path = staging / "targets" / "calibration.jsonl"
        sealed_path = staging / "targets" / "sealed.jsonl"
        manifest_path = staging / "manifest.json"
        cal_path.parent.mkdir(exist_ok=True)
        sealed_path.parent.mkdir(exist_ok=True)

        _write_jsonl(cases_path, cases)
        _write_jsonl(cal_path, (row for row in targets if row["split"] == PARTITION_CALIBRATION))
        _write_jsonl(sealed_path, (row for row in targets if row["split"] == PARTITION_SEALED))

        manifest["files"]["cases_jsonl"]["sha256"], manifest["files"]["cases_jsonl"]["size"] = _sha256_file(cases_path)
        manifest["files"]["calibration_targets_jsonl"]["sha256"], manifest["files"]["calibration_targets_jsonl"]["size"] = _sha256_file(cal_path)
        manifest["files"]["sealed_targets_jsonl"]["sha256"], manifest["files"]["sealed_targets_jsonl"]["size"] = _sha256_file(sealed_path)

        _write_manifest(manifest_path, manifest)
        staging.replace(output_root)


def _build_manifest(
    config: R1CorpusConfig,
    cases: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    family_split: Mapping[str, str],
) -> dict[str, Any]:
    split_count = {PARTITION_CALIBRATION: 0, PARTITION_SEALED: 0}
    family_records: defaultdict[str, int] = defaultdict(int)
    for case in cases:
        split = case["split"]
        split_count[split] = split_count.get(split, 0) + 1
        family_records[case["problem_family_id"]] += 1
        if family_split[case["problem_family_id"]] != split:
            raise A0R1CorpusError("uniform_split_by_family violated")
        if family_records[case["problem_family_id"]] > 2:
            raise A0R1CorpusError("paired_records_by_family violated")

    if split_count[PARTITION_CALIBRATION] != 48 or split_count[PARTITION_SEALED] != 48:
        raise A0R1CorpusError("unexpected split balance")
    if len(cases) != 96 or len(targets) != 96:
        raise A0R1CorpusError("unexpected total count")

    return {
        "artifact_class": "a0r1-corpus-manifest",
        "protocol_id": config.protocol_id,
        "protocol_hash": _sha256_file(config.protocol_path)[0],
        "generator_id": GENERATOR_ID,
        "generator_source_sha256": _sha256_file(Path(__file__).resolve())[0],
        "seed": config.seed,
        "deterministic_seed": config.seed,
        "partitions": {
            "calibration_split": PARTITION_CALIBRATION,
            "sealed_split": PARTITION_SEALED,
            "split_field": PARTITION_FIELD,
        },
        "counts": {
            "total_cases": len(cases),
            "total_targets": len(targets),
            "families": len(family_split),
            "domains": len(set(c["domain"] for c in cases)),
            "calibration_cases": split_count[PARTITION_CALIBRATION],
            "sealed_cases": split_count[PARTITION_SEALED],
        },
        "neutral_domains": sorted({c["domain"] for c in cases}),
        "family_integrity": {
            "paired_records_by_family": True,
            "uniform_split_by_family": True,
            "family_split_sha256": _sha256_text(_stable_compact_json({k: family_split[k] for k in sorted(family_split)})),
        },
        "files": {
            "cases_jsonl": {"path": "cases.jsonl", "sha256": "", "size": 0},
            "calibration_targets_jsonl": {"path": "targets/calibration.jsonl", "sha256": "", "size": 0},
            "sealed_targets_jsonl": {"path": "targets/sealed.jsonl", "sha256": "", "size": 0},
        },
        "preregistered_layers": list(config.protocol.get("preregistered_layers", [0, 2, 4, 6])),
        "token_sites": list(config.protocol.get("token_sites", ["sentinel", "final_transformation_token", "mean_transformation_span"])),
        "views": list(config.protocol.get("views", ["problem_only", "transformation_only", "problem_plus_transformation", "problem_plus_solution"])),
        **EPISTEMIC,
        "license": SPDX_LICENSE,
    }
