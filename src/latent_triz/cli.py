from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Iterable, List, Optional

from .docs import load_profile, audit_docs
from .pilot import PilotError, prepare_packets, score_annotations, stable_json_dumps, write_jsonl
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
    pilot_score_parser.add_argument("--output", default="-", help="Output JSON path, '-' for stdout")

    fingerprint_parser = subparsers.add_parser("fingerprint", help="Compute SHA-256 of a file")
    fingerprint_parser.add_argument("path", help="Path to file")

    args = parser.parse_args(argv)
    if args.command == "fingerprint":
        return _run_fingerprint(args.path)
    if args.command == "validate":
        return _run_validate(args.schema, args.data)
    if args.command == "docs-audit":
        return _run_docs_audit(args.profile, args.root, args.as_of_date)
    if args.command == "pilot-prepare":
        return _run_pilot_prepare(args.cases, args.arms, args.seed, args.output, args.format)
    if args.command == "pilot-score":
        return _run_pilot_score(args.packets, args.responses, args.annotations, args.dimensions, args.output)
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
    output: str,
) -> int:
    try:
        summary = score_annotations(packets, responses, annotations, dimensions or None)
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


if __name__ == "__main__":
    raise SystemExit(main())
