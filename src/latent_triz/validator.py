from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import Any, Dict, List


_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_URI_SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:.*$")
_DATETIME_Z_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
_DATETIME_OFFSET_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?[+\-]\d{2}:\d{2}$")


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str


def validate(instance: Any, schema: Dict[str, Any]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    _validate(instance, schema, path="root", issues=issues)
    return issues


def _validate(instance: Any, schema: Dict[str, Any], path: str, issues: List[ValidationIssue]) -> None:
    if not isinstance(schema, dict):
        return

    _validate_type(instance, schema.get("type"), path, issues)

    _validate_enum(instance, schema, path, issues)
    _validate_pattern(instance, schema, path, issues)
    _validate_range(instance, schema, path, issues)
    _validate_format(instance, schema, path, issues)
    _validate_strings(instance, schema, path, issues)
    _validate_arrays(instance, schema, path, issues)
    _validate_objects(instance, schema, path, issues)


def _validate_type(instance: Any, expected_type: Any, path: str, issues: List[ValidationIssue]) -> None:
    if expected_type is None:
        return

    types = expected_type if isinstance(expected_type, list) else [expected_type]
    ok = False
    for typ in types:
        if typ == "null" and instance is None:
            ok = True
        elif typ == "object" and isinstance(instance, dict):
            ok = True
        elif typ == "array" and isinstance(instance, list):
            ok = True
        elif typ == "string" and isinstance(instance, str):
            ok = True
        elif typ == "boolean" and isinstance(instance, bool):
            ok = True
        elif typ == "integer" and isinstance(instance, int) and not isinstance(instance, bool):
            ok = True
        elif typ == "number" and isinstance(instance, (int, float)) and not isinstance(instance, bool):
            ok = True

    if not ok:
        issues.append(ValidationIssue(path, f"Expected type {expected_type!r}"))


def _validate_enum(instance: Any, schema: Dict[str, Any], path: str, issues: List[ValidationIssue]) -> None:
    if "enum" not in schema:
        return
    if instance not in schema["enum"]:
        issues.append(ValidationIssue(path, f"Value {instance!r} not in enum {schema['enum']!r}"))


def _validate_pattern(instance: Any, schema: Dict[str, Any], path: str, issues: List[ValidationIssue]) -> None:
    if "pattern" not in schema:
        return
    if not isinstance(instance, str):
        return
    pattern = schema["pattern"]
    if not re.search(pattern, instance):
        issues.append(ValidationIssue(path, f"String does not match pattern {pattern!r}"))


def _validate_range(instance: Any, schema: Dict[str, Any], path: str, issues: List[ValidationIssue]) -> None:
    if not isinstance(instance, (int, float)) or isinstance(instance, bool):
        return
    if "minimum" in schema and instance < schema["minimum"]:
        issues.append(ValidationIssue(path, f"Value {instance} is below minimum {schema['minimum']}"))
    if "maximum" in schema and instance > schema["maximum"]:
        issues.append(ValidationIssue(path, f"Value {instance} is above maximum {schema['maximum']}"))


def _validate_format(instance: Any, schema: Dict[str, Any], path: str, issues: List[ValidationIssue]) -> None:
    if "format" not in schema or not isinstance(instance, str):
        return

    if schema["format"] == "date":
        if not _DATE_PATTERN.fullmatch(instance):
            issues.append(ValidationIssue(path, f"Expected date format yyyy-mm-dd: {instance!r}"))
            return
        try:
            datetime.date.fromisoformat(instance)
        except ValueError:
            issues.append(ValidationIssue(path, f"Invalid date: {instance!r}"))
        return

    if schema["format"] == "uri":
        if not _URI_SCHEME_PATTERN.match(instance):
            issues.append(ValidationIssue(path, f"Expected URI format: {instance!r}"))
        return

    if schema["format"] == "date-time":
        if not (_DATETIME_Z_PATTERN.fullmatch(instance) or _DATETIME_OFFSET_PATTERN.fullmatch(instance)):
            issues.append(ValidationIssue(path, f"Expected date-time ISO-8601 with UTC timezone: {instance!r}"))
            return

        normalized = instance
        if instance.endswith("Z"):
            normalized = instance[:-1] + "+00:00"
        try:
            dt = datetime.datetime.fromisoformat(normalized)
        except ValueError:
            issues.append(ValidationIssue(path, f"Invalid date-time: {instance!r}"))
            return
        if dt.tzinfo is None or dt.utcoffset() != datetime.timedelta(0):
            issues.append(ValidationIssue(path, f"Expected UTC date-time: {instance!r}"))

def _validate_strings(instance: Any, schema: Dict[str, Any], path: str, issues: List[ValidationIssue]) -> None:
    if not isinstance(instance, str):
        return
    if "minLength" in schema and len(instance) < schema["minLength"]:
        issues.append(ValidationIssue(path, f"String shorter than minimum length {schema['minLength']}"))


def _validate_arrays(instance: Any, schema: Dict[str, Any], path: str, issues: List[ValidationIssue]) -> None:
    if not isinstance(instance, list):
        return
    if "minItems" in schema and len(instance) < schema["minItems"]:
        issues.append(ValidationIssue(path, f"Array has fewer than minItems {schema['minItems']}"))

    if "items" in schema:
        for index, item in enumerate(instance):
            _validate(item, schema["items"], f"{path}[{index}]", issues)


def _validate_objects(instance: Any, schema: Dict[str, Any], path: str, issues: List[ValidationIssue]) -> None:
    if not isinstance(instance, dict):
        return

    if "required" in schema:
        for required in schema["required"]:
            if required not in instance:
                issues.append(ValidationIssue(f"{path}.{required}", f"Missing required property {required!r}"))

    properties = schema.get("properties", {})
    for key, value in instance.items():
        sub_path = f"{path}.{key}"
        if isinstance(properties, dict) and key in properties:
            _validate(value, properties[key], sub_path, issues)
        elif schema.get("additionalProperties") is False:
            issues.append(ValidationIssue(sub_path, f"Additional property not allowed: {key!r}"))
