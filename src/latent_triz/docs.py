from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
import tomllib

from typing import Dict, List, Tuple


REQUIRED_PROFILE_FIELDS = {
    "required_fields",
    "max_verification_age_days",
    "entry_points",
}
ALLOWED_ENTRY_POINT_SUFFIX = ".md"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class OkfProfile:
    required_fields: tuple[str, ...]
    max_age_days: int
    entry_points: tuple[str, ...]


@dataclass(frozen=True)
class DocsIssue:
    file: str
    line: int
    code: str
    message: str


@dataclass(frozen=True)
class ParsedFrontmatter:
    path: str
    fields: Dict[str, str]
    field_lines: Dict[str, int]
    end_line: int


def load_profile(profile_path: str) -> OkfProfile:
    try:
        data = Path(profile_path).read_bytes()
    except OSError as exc:
        raise ValueError(f"unable to read profile {profile_path}: {exc}") from None

    try:
        document = tomllib.loads(data.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"invalid TOML in profile {profile_path}: {exc}") from None

    if not isinstance(document, dict):
        raise ValueError("profile must be a TOML table")

    profile = document.get("okf", document)
    if not isinstance(profile, dict):
        raise ValueError("profile section 'okf' must be a TOML table")

    if "max_age_days" in profile and "max_verification_age_days" not in profile:
        profile = dict(profile)
        profile["max_verification_age_days"] = profile["max_age_days"]

    missing = REQUIRED_PROFILE_FIELDS - set(profile)
    if missing:
        raise ValueError(f"missing profile fields: {', '.join(sorted(missing))}")

    required_fields = profile["required_fields"]
    if not isinstance(required_fields, list) or not all(isinstance(v, str) for v in required_fields):
        raise ValueError("required_fields must be a list of strings")
    if not required_fields:
        raise ValueError("required_fields must not be empty")

    max_age_days = profile["max_verification_age_days"]
    if not isinstance(max_age_days, int) or max_age_days < 1:
        raise ValueError("max_verification_age_days must be an int greater than 0")

    entry_points_raw = profile["entry_points"]
    if not isinstance(entry_points_raw, list) or not all(isinstance(v, str) for v in entry_points_raw):
        raise ValueError("entry_points must be a list of strings")
    if not entry_points_raw:
        raise ValueError("entry_points must not be empty")
    entry_points: list[str] = []
    for entry_point in entry_points_raw:
        clean = entry_point.strip()
        if not clean:
            raise ValueError("entry_points must not include empty paths")
        if clean.startswith(("/", "\\")):
            raise ValueError(f"absolute entry point is not allowed: {clean}")
        if Path(clean).is_absolute():
            raise ValueError(f"absolute entry point is not allowed: {clean}")
        if clean.startswith("..") or ".." in Path(clean).parts:
            raise ValueError(f"entry point escapes docs root: {clean}")
        if not clean.lower().endswith(ALLOWED_ENTRY_POINT_SUFFIX):
            raise ValueError(f"entry point must be Markdown: {clean}")
        entry_points.append(clean)

    return OkfProfile(
        required_fields=tuple(required_fields),
        max_age_days=max_age_days,
        entry_points=tuple(entry_points),
    )


def audit_docs(profile: OkfProfile, root: Path, as_of: date) -> List[DocsIssue]:
    issues: List[DocsIssue] = []
    canonical_seen: Dict[Tuple[str, str], str] = {}
    canonical_status = "canonical"

    for entry_point in profile.entry_points:
        path = root / entry_point
        rel = entry_point.replace("\\", "/")
        if not path.is_file():
            issues.append(
                DocsIssue(
                    file=rel,
                    line=1,
                    code="PROFILE_MISSING_ENTRY",
                    message=f"entry point missing: {entry_point}",
                )
            )
            continue

        with path.open("r", encoding="utf-8") as handle:
            text = handle.read()

        reserved_nested_index = rel.endswith("/index.md") and rel != "docs/index.md"
        frontmatter, fm_issues = _parse_frontmatter(rel, text)
        if reserved_nested_index and frontmatter is None and any(issue.code == "DOCS_MISSING_FRONTMATTER" for issue in fm_issues):
            fm_issues = []
        issues.extend(fm_issues)

        if frontmatter is None:
            if reserved_nested_index:
                issues.extend(_validate_markdown_links(path, rel, root, text))
            continue

        for field in profile.required_fields:
            if field not in frontmatter.fields or frontmatter.fields[field] == "":
                line = frontmatter.field_lines.get(field, frontmatter.end_line)
                issues.append(
                    DocsIssue(
                        file=rel,
                        line=line,
                        code="DOCS_MISSING_FIELD",
                        message=f"missing required field in frontmatter: {field}",
                    )
                )

        last_verified = frontmatter.fields.get("last_verified")
        if last_verified is not None:
            _validate_last_verified(
                rel,
                frontmatter.field_lines.get("last_verified", frontmatter.end_line),
                last_verified,
                profile,
                as_of,
                issues,
            )

        if frontmatter.fields.get("status") == canonical_status:
            type_value = frontmatter.fields.get("type")
            if type_value:
                key = (canonical_status, type_value)
                if key in canonical_seen:
                    issues.append(
                        DocsIssue(
                            file=rel,
                            line=frontmatter.field_lines.get("type", frontmatter.end_line),
                            code="DOCS_DUP_CANONICAL_TYPE",
                            message=f"duplicate canonical type '{type_value}' also used by {canonical_seen[key]}",
                        )
                    )
                else:
                    canonical_seen[key] = rel

        issues.extend(_validate_markdown_links(path, rel, root, text))

    issues.sort(key=lambda item: (item.file, item.line, item.code, item.message))
    return issues


def _parse_frontmatter(path: str, text: str) -> tuple[ParsedFrontmatter | None, List[DocsIssue]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, [
            DocsIssue(
                file=path,
                line=1,
                code="DOCS_MISSING_FRONTMATTER",
                message="missing YAML frontmatter block",
            )
        ]

    try:
        end_index = lines[1:].index("---") + 2
    except ValueError:
        return None, [
            DocsIssue(
                file=path,
                line=1,
                code="DOCS_UNTERMINATED_FRONTMATTER",
                message="unterminated YAML frontmatter block",
            )
        ]

    fields: Dict[str, str] = {}
    field_lines: Dict[str, int] = {}
    for idx in range(1, end_index - 1):
        raw = lines[idx].strip()
        if raw == "" or raw.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", raw)
        if match:
            key, value = match.groups()
            fields[key] = value.strip()
            field_lines[key] = idx + 1
    return ParsedFrontmatter(path=path, fields=fields, field_lines=field_lines, end_line=end_index), []


def _validate_last_verified(
    path: str,
    line: int,
    value: str,
    profile: OkfProfile,
    as_of: date,
    issues: List[DocsIssue],
) -> None:
    if not DATE_PATTERN.match(value):
        issues.append(
            DocsIssue(
                file=path,
                line=line,
                code="DOCS_LAST_VERIFIED_FORMAT",
                message=f"invalid last_verified date: {value}",
            )
        )
        return
    try:
        verified = date.fromisoformat(value)
    except ValueError:
        issues.append(
            DocsIssue(
                file=path,
                line=line,
                code="DOCS_LAST_VERIFIED_FORMAT",
                message=f"invalid last_verified date: {value}",
            )
        )
        return
    if verified > as_of:
        issues.append(
            DocsIssue(
                file=path,
                line=line,
                code="DOCS_LAST_VERIFIED_FUTURE",
                message="last_verified is in the future",
            )
        )
        return
    age = (as_of - verified).days
    if age > profile.max_age_days:
        issues.append(
            DocsIssue(
                file=path,
                line=line,
                code="DOCS_LAST_VERIFIED_STALE",
                message=f"last_verified is stale by {age} days",
            )
        )


def _validate_markdown_links(
    path: Path,
    rel: str,
    root: Path,
    text: str,
) -> List[DocsIssue]:
    issues: List[DocsIssue] = []
    link_re = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
    heading_cache: Dict[Path, set[str]] = {}
    root_path = root.resolve()

    lines = text.splitlines()
    in_fence: str | None = None
    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        fence = _fence_token(line)
        if fence is not None:
            if in_fence is None:
                in_fence = fence
            elif in_fence == fence:
                in_fence = None
            continue
        if in_fence is not None:
            continue

        for match in link_re.findall(line):
            target = match.strip()
            if _is_external(target):
                continue

            target_path, anchor = _split_link_target(target)
            if target_path is None and not anchor:
                continue

            if target_path is None:
                target_file = path
            else:
                target_file = (path.parent / target_path).resolve()
                if not target_file.is_relative_to(root_path):
                    issues.append(
                        DocsIssue(
                            file=rel,
                            line=line_no,
                            code="DOCS_ROOT_ESCAPE",
                            message=f"link escapes docs root: {target}",
                        )
                    )
                    continue

            if not target_file.is_file():
                issues.append(
                    DocsIssue(
                        file=rel,
                        line=line_no,
                        code="DOCS_LINK_TARGET_MISSING",
                        message=f"missing link target: {target_path or path.name}",
                    )
                )
                continue

            if anchor:
                if target_file not in heading_cache:
                    heading_cache[target_file] = _collect_heading_anchors(target_file)
                if anchor not in heading_cache[target_file]:
                    issues.append(
                        DocsIssue(
                            file=rel,
                            line=line_no,
                            code="DOCS_LINK_ANCHOR_MISSING",
                            message=f"missing link anchor: {anchor}",
                        )
                    )

    return issues


def _split_link_target(raw: str) -> tuple[str | None, str | None]:
    if "#" not in raw:
        return raw, None
    path_text, anchor = raw.split("#", 1)
    anchor = anchor.strip()
    if path_text == "":
        return None, _normalize_anchor(anchor)
    return path_text.strip(), _normalize_anchor(anchor)


def _is_external(raw: str) -> bool:
    lowered = raw.lower()
    return lowered.startswith(("http://", "https://", "ftp://", "mailto:", "//"))


def _normalize_anchor(anchor: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"\s+", "-", re.sub(r"[^\w\s-]", "", anchor.strip().lower()))).strip("-")


def _collect_heading_anchors(path: Path) -> set[str]:
    anchor_re = re.compile(r"^#{1,6}\s+(.+)$")
    headings: set[str] = set()
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        match = anchor_re.match(line.strip())
        if match:
            headings.add(_normalize_anchor(match.group(1)))
    return headings


def _fence_token(line: str) -> str | None:
    if line.startswith("```"):
        return "```"
    if line.startswith("~~~"):
        return "~~~"
    return None
