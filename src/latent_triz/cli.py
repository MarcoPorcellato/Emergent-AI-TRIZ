from __future__ import annotations

import argparse
import hashlib
import json
import sys
import webbrowser
from datetime import date
from pathlib import Path
from typing import Iterable, List, Optional

from .docs import load_profile, audit_docs
from .dataset_audit import DatasetAuditError, run_dataset_audit, stable_json_dumps as dataset_stable_json_dumps
from .model_preflight import ModelPreflightError, run_model_preflight, stable_json_dumps as model_stable_json_dumps
from .blinding import BlindingError, build_evaluator_bundle, write_evaluator_bundle
from .pilot import PilotError, prepare_packets, score_annotations, stable_json_dumps, write_jsonl
from .lab00 import Lab00Error, build_lab00_report
from .lab_suite import LAB00_REPORT_PATH, LabSuiteError, build_lab_suite_report
from .validator import ValidationIssue, validate


class CliError(RuntimeError):
    pass


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="latent-triz")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate JSON data against a schema")
    validate_parser.add_argument("--schema", required=True, help="Path to schema file")
    validate_parser.add_argument("data", nargs="+", help="JSON or JSONL document path(s)")

    docs_parser = subparsers.add_parser("docs-audit", help="Audit Markdown documentation against OKF profile")
    docs_parser.add_argument("--profile", required=True, help="Path to OKF TOML profile")
    docs_parser.add_argument("--root", default=".", help="Documentation root for link resolution")
    docs_parser.add_argument(
        "--as-of-date",
        required=True,
        help="Reference date for stale-date checks (YYYY-MM-DD)",
    )

    claims_parser = subparsers.add_parser("claims-audit", help="Audit claim evidence references")
    claims_parser.add_argument("--registry", required=True, help="Path to claim registry JSONL")
    claims_parser.add_argument("--root", default=".", help="Repository root for evidence references")

    pilot_prepare_parser = subparsers.add_parser("pilot-prepare", help="Prepare randomized, blinded pilot packets")
    pilot_prepare_parser.add_argument("--seed", type=int, required=True, help="Deterministic seed")
    pilot_prepare_parser.add_argument("--arms", nargs="+", required=True, help="Arm labels")
    pilot_prepare_parser.add_argument("--cases", nargs="+", required=True, help="Case JSON/JSONL file(s)")
    pilot_prepare_parser.add_argument("--output", default="-", help="Output JSONL path, '-' for stdout")
    pilot_prepare_parser.add_argument("--format", choices=["json", "jsonl"], default="jsonl")

    pilot_score_parser = subparsers.add_parser("pilot-score", help="Aggregate blinded pilot annotations")
    pilot_score_parser.add_argument("--packets", required=True, help="Packet JSON/JSONL file")
    pilot_score_parser.add_argument("--responses", required=True, help="Response JSON/JSONL file")
    pilot_score_parser.add_argument("--annotations", required=True, help="Annotation JSON/JSONL file")
    pilot_score_parser.add_argument("--dimensions", nargs="+", default=list(), help="Optional custom dimensions")
    pilot_score_parser.add_argument(
        "--minimum-distinct-raters",
        type=int,
        default=1,
        help="Minimum distinct raters required per response (confirmatory runs should use 2 or more)",
    )
    pilot_score_parser.add_argument("--output", default="-", help="Output JSON path, '-' for stdout")

    lab00_parser = subparsers.add_parser("lab00", help="Build deterministic Stage-1 non-evidence HTML report")
    lab00_parser.add_argument("--output", required=True, help="Output HTML path")
    lab00_parser.add_argument("--open", action="store_true", help="Open the report in a browser")

    lab_suite_parser = subparsers.add_parser(
        "lab-suite",
        help="Build the deterministic Lab 00-04 visual index",
    )
    lab_suite_parser.add_argument("--root", default=".", help="Repository root")
    lab_suite_parser.add_argument("--output", required=True, help="Output HTML path relative to the repository")
    lab_suite_parser.add_argument("--open", action="store_true", help="Open the dashboard in a browser")

    model_preflight_parser = subparsers.add_parser(
        "model-preflight",
        help="Check the offline EXP-001 model candidate manifest",
    )
    model_preflight_parser.add_argument("--manifest", required=True, help="Path to the model candidate manifest")
    model_preflight_parser.add_argument("--output", default="-", help="Output JSON path, '-' for stdout")

    dataset_audit_parser = subparsers.add_parser(
        "dataset-audit",
        help="Audit the EXP-001 dataset plan against cases",
    )
    dataset_audit_parser.add_argument("--plan", required=True, help="Path to the dataset plan")
    dataset_audit_parser.add_argument("--cases", required=True, help="Path to the JSONL case corpus")
    dataset_audit_parser.add_argument(
        "--mode",
        choices=["development", "freeze"],
        default="development",
        help="Development reports gaps; freeze enforces all targets",
    )
    dataset_audit_parser.add_argument("--output", default="-", help="Output JSON path, '-' for stdout")

    evaluator_export_parser = subparsers.add_parser(
        "pilot-export-evaluator",
        help="Export evaluator-safe packets and a separate sealed allocation key",
    )
    evaluator_export_parser.add_argument("--packets", required=True, help="Administrative packet JSONL")
    evaluator_export_parser.add_argument("--responses", required=True, help="Blinded response JSONL")
    evaluator_export_parser.add_argument("--evaluator-output", required=True, help="Evaluator-safe JSONL output")
    evaluator_export_parser.add_argument("--key-output", required=True, help="Separate sealed allocation key output")

    fingerprint_parser = subparsers.add_parser("fingerprint", help="Compute SHA-256 of a file")
    fingerprint_parser.add_argument("path", help="Path to file")

    args = parser.parse_args(argv)
    if args.command == "fingerprint":
        return _run_fingerprint(args.path)
    if args.command == "validate":
        return _run_validate(args.schema, args.data)
    if args.command == "docs-audit":
        return _run_docs_audit(args.profile, args.root, args.as_of_date)
    if args.command == "claims-audit":
        return _run_claims_audit(args.registry, args.root)
    if args.command == "pilot-prepare":
        return _run_pilot_prepare(args.cases, args.arms, args.seed, args.output, args.format)
    if args.command == "pilot-score":
        return _run_pilot_score(
            args.packets,
            args.responses,
            args.annotations,
            args.dimensions,
            args.minimum_distinct_raters,
            args.output,
        )
    if args.command == "lab00":
        return _run_lab00(args.output, args.open)
    if args.command == "lab-suite":
        return _run_lab_suite(args.root, args.output, args.open)
    if args.command == "model-preflight":
        return _run_model_preflight(args.manifest, args.output)
    if args.command == "dataset-audit":
        return _run_dataset_audit(args.plan, args.cases, args.mode, args.output)
    if args.command == "pilot-export-evaluator":
        return _run_pilot_export_evaluator(
            args.packets,
            args.responses,
            args.evaluator_output,
            args.key_output,
        )
    parser.error("Unknown command")
    return 1


def _run_fingerprint(path: str) -> int:
    file_path = Path(path)
    try:
        hash_obj = hashlib.sha256()
        with file_path.open("rb") as file:
            for chunk in iter(lambda: file.read(65536), b""):
                hash_obj.update(chunk)
        print(hash_obj.hexdigest())
        return 0
    except (OSError, IOError) as exc:
        _print_error(f"{path}: cannot read file: {exc}")
        return 1


def _load_schema(path: str) -> dict:
    schema_path = Path(path)
    try:
        with schema_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        _raise_cli_error(f"schema not found: {path}")
    except json.JSONDecodeError as exc:
        _raise_cli_error(f"invalid schema JSON in {path}: {exc}")
    except OSError as exc:
        _raise_cli_error(f"unable to read schema {path}: {exc}")


def _run_validate(schema_path: str, data_paths: Iterable[str]) -> int:
    try:
        schema = _load_schema(schema_path)
    except CliError as exc:
        _print_error(f"schema: {exc}")
        return 1

    had_errors = False

    for data_path in data_paths:
        path = Path(data_path)
        if path.suffix.lower() in {".jsonl", ".ndjson"}:
            if not _validate_jsonl(path, schema):
                had_errors = True
        else:
            if not _validate_json(path, schema):
                had_errors = True

    return 1 if had_errors else 0


def _validate_json(path: Path, schema: dict) -> bool:
    if not path.is_file():
        _print_error(f"{path.as_posix()}:0:0: data file not found")
        return False
    try:
        data = _read_json(path)
    except CliError as exc:
        _print_error(f"{path.as_posix()}:0:0: invalid JSON: {exc}")
        return False
    issues = validate(data, schema)
    if issues:
        for issue in issues:
            print(_fmt_issue(path.as_posix(), None, issue), file=sys.stderr)
        return False
    return True


def _validate_jsonl(path: Path, schema: dict) -> bool:
    ok = True
    try:
        file = path.open("r", encoding="utf-8")
    except OSError as exc:
        _print_error(f"{path.as_posix()}:0:0: cannot open JSONL file: {exc}")
        return False

    with file:
        for index, line in enumerate(file, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                print(
                    _fmt_parse_error(path.as_posix(), index, exc),
                    file=sys.stderr,
                )
                ok = False
                continue
            issues = validate(data, schema)
            if issues:
                ok = False
                for issue in issues:
                    print(_fmt_issue(path.as_posix(), index, issue), file=sys.stderr)
    return ok


def _read_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        _raise_cli_error(f"file not found: {path}")
    except json.JSONDecodeError as exc:
        _raise_cli_error(str(exc))
    except OSError as exc:
        _raise_cli_error(str(exc))


def _print_error(message: str) -> None:
    print(f"latent-triz: {message}", file=sys.stderr)


def _raise_cli_error(message: str) -> None:
    raise CliError(message)


def _fmt_issue(path: str, record: Optional[int], issue: ValidationIssue) -> str:
    if record is None:
        return f"{path}:0:{issue.path}: {issue.message}"
    return f"{path}:{record}:{issue.path}: {issue.message}"


def _fmt_parse_error(path: str, record: int, exc: Exception) -> str:
    return f"{path}:{record}:0: invalid JSON: {exc}"


def _run_docs_audit(profile_path: str, root: str, as_of_date: str) -> int:
    try:
        as_of = date.fromisoformat(as_of_date)
    except ValueError as exc:
        _print_error(f"invalid --as-of-date: {exc}")
        return 1

    try:
        profile = load_profile(profile_path)
    except ValueError as exc:
        _print_error(f"invalid profile {profile_path}: {exc}")
        return 1

    issues = audit_docs(profile, Path(root), as_of)
    if issues:
        for issue in issues:
            print(f"{issue.file}:{issue.line}:{issue.code}: {issue.message}", file=sys.stderr)
        return 1
    return 0


def _run_claims_audit(registry_path: str, root: str) -> int:
    registry = Path(registry_path)
    repo_root = Path(root).resolve()
    reference_fields = (
        "preregistrations",
        "dataset_snapshots",
        "experiments",
        "results",
        "replications",
    )
    profile_requirements = {
        "E0": (),
        "E1": ("behavioral_effect",),
        "E2": ("behavioral_effect", "lexical_controls", "cross_domain", "decodable"),
        "E3": (
            "behavioral_effect",
            "lexical_controls",
            "cross_domain",
            "decodable",
            "positive_causal_intervention",
            "dose_response",
            "capability_preserved",
        ),
        "E4": (
            "behavioral_effect",
            "lexical_controls",
            "cross_domain",
            "decodable",
            "positive_causal_intervention",
            "dose_response",
            "capability_preserved",
            "negative_causal_intervention",
        ),
        "E5": (
            "behavioral_effect",
            "lexical_controls",
            "cross_domain",
            "decodable",
            "positive_causal_intervention",
            "dose_response",
            "capability_preserved",
            "negative_causal_intervention",
            "independent_replication",
            "cross_model_replication",
        ),
        "E6": (
            "behavioral_effect",
            "lexical_controls",
            "cross_domain",
            "decodable",
            "positive_causal_intervention",
            "dose_response",
            "capability_preserved",
            "negative_causal_intervention",
            "independent_replication",
            "cross_model_replication",
            "controlled_training",
        ),
    }
    ok = True

    try:
        lines = registry.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _print_error(f"{registry_path}: cannot read claim registry: {exc}")
        return 1

    for line_number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            claim = json.loads(raw)
        except json.JSONDecodeError as exc:
            _print_error(f"{registry_path}:{line_number}: invalid JSON: {exc}")
            ok = False
            continue

        claim_id = claim.get("claim_id", "unknown") if isinstance(claim, dict) else "unknown"
        if not isinstance(claim, dict):
            _print_error(f"{registry_path}:{line_number}: claim must be an object")
            ok = False
            continue

        for field in reference_fields:
            references = claim.get(field, [])
            if not isinstance(references, list):
                continue
            for reference in references:
                if not isinstance(reference, str):
                    continue
                target = (repo_root / reference).resolve()
                try:
                    target.relative_to(repo_root)
                except ValueError:
                    _print_error(
                        f"{registry_path}:{line_number}:{claim_id}:{field}: reference escapes repository: {reference}"
                    )
                    ok = False
                    continue
                if not target.is_file():
                    _print_error(
                        f"{registry_path}:{line_number}:{claim_id}:{field}: evidence file not found: {reference}"
                    )
                    ok = False

        evidence_level = claim.get("evidence_level")
        evidence_profile = claim.get("evidence_profile")

        if not isinstance(evidence_level, str):
            _print_error(f"{registry_path}:{line_number}:{claim_id}: evidence_level must be a string")
            ok = False
            continue

        required_axes = profile_requirements.get(evidence_level)
        if required_axes is None:
            _print_error(f"{registry_path}:{line_number}:{claim_id}: unsupported evidence_level: {evidence_level}")
            ok = False
            continue

        if not isinstance(evidence_profile, dict):
            _print_error(
                f"{registry_path}:{line_number}:{claim_id}: evidence_profile must be an object for evidence_level {evidence_level}"
            )
            ok = False
            continue

        missing_axis = [axis for axis in required_axes if evidence_profile.get(axis) is not True]
        if missing_axis:
            _print_error(
                f"{registry_path}:{line_number}:{claim_id}: evidence_profile incompatible with evidence_level {evidence_level}; "
                f"missing true axes: {', '.join(missing_axis)}"
            )
            ok = False

    return 0 if ok else 1


def _run_pilot_prepare(case_files: List[str], arms: List[str], seed: int, output: str, output_format: str) -> int:
    try:
        packets = prepare_packets(case_files, arms, seed)
    except PilotError as exc:
        _print_error(f"invalid pilot input: {exc}")
        return 1

    if output == "-":
        if output_format == "jsonl":
            for packet in packets:
                print(stable_json_dumps(packet))
        else:
            print(stable_json_dumps(packets))
        return 0

    if output_format == "jsonl":
        try:
            write_jsonl(output, packets)
            return 0
        except OSError as exc:
            _print_error(f"unable to write packets: {exc}")
            return 1
    try:
        Path(output).write_text(stable_json_dumps(packets) + "\n", encoding="utf-8")
    except OSError as exc:
        _print_error(f"unable to write packets: {exc}")
        return 1
    return 0


def _run_pilot_score(
    packets: str,
    responses: str,
    annotations: str,
    dimensions: List[str],
    minimum_distinct_raters: int,
    output: str,
) -> int:
    try:
        summary = score_annotations(
            packets,
            responses,
            annotations,
            dimensions or None,
            minimum_distinct_raters=minimum_distinct_raters,
        )
    except PilotError as exc:
        _print_error(f"invalid pilot scoring: {exc}")
        return 1

    if output == "-":
        print(stable_json_dumps(summary))
        return 0

    try:
        Path(output).write_text(stable_json_dumps(summary) + "\n", encoding="utf-8")
    except OSError as exc:
        _print_error(f"unable to write summary: {exc}")
        return 1
    return 0


def _run_lab00(output: str, open_report: bool) -> int:
    try:
        report_path = build_lab00_report(output_path=Path(output))
    except Lab00Error as exc:
        _print_error(f"lab00: {exc}")
        return 1
    resolved = Path(report_path).resolve()
    print(f"lab00: rendered {resolved}")
    if open_report:
        webbrowser.open(resolved.as_uri())
    return 0


def _run_lab_suite(root: str, output: str, open_report: bool) -> int:
    repo_root = Path(root).resolve()
    output_path = Path(output)
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    try:
        build_lab00_report(output_path=repo_root / LAB00_REPORT_PATH)
        report_path = build_lab_suite_report(repo_root=repo_root, output_path=output_path)
    except (Lab00Error, LabSuiteError, OSError) as exc:
        _print_error(f"lab-suite: {exc}")
        return 1
    print(f"lab-suite: rendered {report_path}")
    if open_report:
        webbrowser.open(report_path.as_uri())
    return 0


def _run_model_preflight(manifest: str, output: str) -> int:
    try:
        report = run_model_preflight(manifest)
    except ModelPreflightError as exc:
        _print_error(str(exc))
        return 1
    write_result = _write_json_output(report, output, model_stable_json_dumps)
    if write_result != 0:
        return write_result
    return 0 if report.get("manifest_valid") is True else 1


def _run_dataset_audit(plan: str, cases: str, mode: str, output: str) -> int:
    try:
        report = run_dataset_audit(plan, cases, mode=mode)
    except DatasetAuditError as exc:
        _print_error(str(exc))
        return 1
    write_result = _write_json_output(report, output, dataset_stable_json_dumps)
    if write_result != 0:
        return write_result
    if report.get("structural_ok") is not True:
        return 1
    if mode == "freeze" and report.get("freeze_ready") is not True:
        return 1
    return 0


def _run_pilot_export_evaluator(
    packets: str,
    responses: str,
    evaluator_output: str,
    key_output: str,
) -> int:
    try:
        evaluator_packets, allocation_key = build_evaluator_bundle(packets, responses)
        write_evaluator_bundle(evaluator_packets, allocation_key, evaluator_output, key_output)
    except (BlindingError, OSError) as exc:
        _print_error(str(exc))
        return 1
    print(f"evaluator packets: {evaluator_output}")
    print(f"sealed allocation key: {key_output}")
    return 0


def _write_json_output(payload: dict, output: str, dumper) -> int:
    rendered = dumper(payload)
    if output == "-":
        print(rendered, end="")
        return 0
    try:
        Path(output).write_text(rendered, encoding="utf-8")
    except OSError as exc:
        _print_error(f"cannot write {output}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
