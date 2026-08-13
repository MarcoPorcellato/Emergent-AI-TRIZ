"""Fail-closed audit for pre-annotation candidate case batches."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PARTICIPANT_FIELDS = (
    "problem", "initial_state", "desired_improvement", "worsening_consequence",
    "transformation", "resulting_state",
)
SEMANTIC_FIELDS = (
    "problem",
    "transformation",
    "resulting_state",
    "problem_plus_solution",
)
SEMANTIC_DIAGNOSTIC_FIELDS = SEMANTIC_FIELDS
PAIRED_SEMANTIC_REVIEW_STATUS = "reviewed"


class CandidateBatchError(RuntimeError):
    """Raised when candidate inputs cannot be audited."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateBatchError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CandidateBatchError(f"{path}: expected an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise CandidateBatchError(f"cannot read {path}: {exc}") from exc
    for line_number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CandidateBatchError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise CandidateBatchError(f"{path}:{line_number}: expected an object")
        records.append(value)
    return records


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _required_string_list(manifest: Mapping[str, Any], field: str) -> list[str]:
    value = manifest.get(field)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise CandidateBatchError(f"manifest.{field} must be a non-empty string array")
    return value


def _principle(case: Mapping[str, Any]) -> str | None:
    labels = case.get("labels")
    if not isinstance(labels, list) or len(labels) != 1 or not isinstance(labels[0], dict):
        return None
    value = labels[0].get("principle")
    return value if isinstance(value, str) and value else None


def _cue_present(text: str, cue: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(cue.lower())}(?![a-z0-9])", text.lower()) is not None


def _normalize_text(text: str) -> str:
    lowered = text.strip().lower()
    normalized = re.sub(r"\s+", " ", lowered)
    return re.sub(r"[^a-z0-9 ]+", " ", normalized).strip()


def _word_ngrams(text: str, n: int) -> list[str]:
    words = [token for token in _normalize_text(text).split() if token]
    if n <= 0 or len(words) < n:
        return []
    return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]


def _char_ngrams(text: str, n: int) -> list[str]:
    normalized = _normalize_text(text).replace(" ", "")
    if n <= 0 or len(normalized) < n:
        return []
    return [normalized[i : i + n] for i in range(len(normalized) - n + 1)]


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _field_similarity(left: str, right: str, *, word_n_range: Iterable[int], char_n_range: Iterable[int]) -> float:
    left = left or ""
    right = right or ""
    word_scores: list[float] = []
    char_scores: list[float] = []
    for n in word_n_range:
        score = _jaccard(set(_word_ngrams(left, n)), set(_word_ngrams(right, n)))
        word_scores.append(score)
    for n in char_n_range:
        score = _jaccard(set(_char_ngrams(left, n)), set(_char_ngrams(right, n)))
        char_scores.append(score)
    all_scores = [*word_scores, *char_scores]
    if not all_scores:
        return 0.0
    return sum(all_scores) / len(all_scores)


def _case_field_value(case: Mapping[str, Any], field: str) -> str:
    if field == "problem_plus_solution":
        return f"{case.get('problem', '')} {case.get('resulting_state', '')}".strip()
    value = case.get(field)
    return value if isinstance(value, str) else ""


def _as_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def audit_candidate_batch(manifest_path: str | Path, cases_path: str | Path) -> dict[str, Any]:
    manifest_file, cases_file = Path(manifest_path), Path(cases_path)
    manifest, cases = _read_json(manifest_file), _read_jsonl(cases_file)
    issues: list[dict[str, Any]] = []
    required_principles: set[str] = set(_required_string_list(manifest, "required_principles"))
    required_domains: set[str] = set(_required_string_list(manifest, "required_domains"))
    allowed_sources: set[str] = set(_required_string_list(manifest, "allowed_source_types"))
    forbidden_cues: Sequence[str] = _required_string_list(manifest, "forbidden_label_cues")
    semantic_policy = manifest.get("semantic_leakage_policy") if isinstance(manifest.get("semantic_leakage_policy"), Mapping) else {}
    semantic_review_records = manifest.get("pair_semantic_review", [])
    if not isinstance(semantic_review_records, list):
        semantic_review_records = []
    policy_word_ngrams = semantic_policy.get("word_ngrams")
    if not isinstance(policy_word_ngrams, list):
        policy_word_ngrams = [2, 3]
    pair_word_ngrams = [n for n in policy_word_ngrams if isinstance(n, int) and n > 0]
    if not pair_word_ngrams:
        pair_word_ngrams = [2, 3]
    policy_char_ngrams = semantic_policy.get("char_ngrams")
    if not isinstance(policy_char_ngrams, list):
        policy_char_ngrams = [3, 5]
    pair_char_ngrams = [n for n in policy_char_ngrams if isinstance(n, int) and n > 0]
    if not pair_char_ngrams:
        pair_char_ngrams = [3, 5]
    by_id: dict[str, dict[str, Any]] = {}
    label_counts: dict[str, int] = {value: 0 for value in sorted(required_principles)}
    domain_counts: dict[str, int] = {value: 0 for value in sorted(required_domains)}
    domain_label_counts: dict[str, dict[str, int]] = {
        domain: {label: 0 for label in sorted(required_principles)} for domain in sorted(required_domains)
    }
    transformation_leads: dict[str, Counter[str]] = {
        value: Counter() for value in sorted(required_principles)
    }

    semantics: dict[str, Any] = {
        "enabled": bool(semantic_policy),
        "word_ngrams": {"sizes": list(pair_word_ngrams)},
        "char_ngrams": {"sizes": list(pair_char_ngrams)},
        "pair_similarity_threshold": float(semantic_policy.get("pair_similarity_threshold", 0.72)),
        "lodo_similarity_threshold": float(semantic_policy.get("lodo_similarity_threshold", 0.64)),
        "require_pair_semantic_review": bool(semantic_policy.get("require_pair_semantic_review", False)),
        "embedding_backend": {"status": "not_run", "reason": "explicitly optional; not in dependency-free audit"},
        "pairs_evaluated": 0,
        "pair_diagnostics": [],
        "domain_shortcuts": [],
        "lodo": {"pairs_evaluated": 0, "high_overlap_pairs": []},
        "provenance_records": [],
        "shortcut_evaluability": {},
        "issues": [],
    }

    def add(code: str, case_id: str | None, message: str) -> None:
        issue: dict[str, Any] = {"code": code, "message": message}
        if case_id is not None:
            issue["case_id"] = case_id
        issues.append(issue)

    def add_semantic_issue(code: str, case_id: str | None, message: str) -> None:
        diagnostic: dict[str, Any] = {"code": code, "message": message}
        if case_id is not None:
            diagnostic["case_id"] = case_id
        semantics["issues"].append(diagnostic)

    for index, case in enumerate(cases, start=1):
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            add("invalid_case_id", None, f"record {index} has no case_id")
            continue
        if case_id in by_id:
            add("duplicate_case_id", case_id, "case_id appears more than once")
            continue
        by_id[case_id] = case
        principle = _principle(case)
        if not isinstance(principle, str) or principle not in required_principles:
            add("invalid_principle", case_id, "exactly one required principle label is required")
        else:
            label_counts[principle] += 1
            transformation = case.get("transformation")
            lead_match = re.search(r"[a-z]+", transformation.lower()) if isinstance(transformation, str) else None
            if lead_match is None:
                add("missing_transformation_lead", case_id, "transformation must contain a word")
            else:
                transformation_leads[principle][lead_match.group(0)] += 1
        domain = case.get("domain")
        if not isinstance(domain, str) or domain not in required_domains:
            add("invalid_domain", case_id, f"domain {domain!r} is outside the batch manifest")
        else:
            domain_counts[domain] += 1
            if isinstance(principle, str) and principle in required_principles:
                domain_label_counts[domain][principle] += 1
        provenance = case.get("provenance")
        source_type = provenance.get("source_type") if isinstance(provenance, dict) else None
        if source_type not in allowed_sources:
            add("invalid_source_type", case_id, f"source_type {source_type!r} is outside the batch manifest")
        participant_text = " ".join(str(case.get(field, "")) for field in PARTICIPANT_FIELDS)
        found = sorted({cue for cue in forbidden_cues if _cue_present(participant_text, cue)})
        if found:
            add("label_cue_leakage", case_id, f"participant text contains forbidden cues: {found}")
        source_uri = ""
        if isinstance(provenance, dict):
            source_uri = _as_str(provenance.get("source_uri"))
        semantics["provenance_records"].append(
            {
                "case_id": case_id,
                "domain": _as_str(case.get("domain")),
                "source_type": _as_str(source_type) if source_type is not None else None,
                "source_uri_present": bool(source_uri),
                "source_uri": source_uri,
            }
        )

    expected_count = manifest.get("expected_count")
    if len(cases) != expected_count:
        add("unexpected_case_count", None, f"found {len(cases)} cases; expected {expected_count}")
    if label_counts and len(set(label_counts.values())) != 1:
        add("principle_imbalance", None, f"principle counts are not equal: {label_counts}")
    minimum = manifest.get("minimum_per_principle_domain")
    for domain, counts in domain_label_counts.items():
        for label, count in counts.items():
            if not isinstance(minimum, int) or count < minimum:
                add("domain_principle_minimum", None, f"{domain}/{label} has {count}; minimum is {minimum}")

    if manifest.get("require_balanced_transformation_leads") is True and required_principles:
        lead_profiles = [transformation_leads[label] for label in sorted(required_principles)]
        if any(profile != lead_profiles[0] for profile in lead_profiles[1:]):
            add(
                "transformation_lead_imbalance",
                None,
                f"lead-word profiles differ by principle: {dict((key, dict(value)) for key, value in transformation_leads.items())}",
            )
        minimum_leads = manifest.get("minimum_distinct_transformation_leads")
        for label, profile in transformation_leads.items():
            if not isinstance(minimum_leads, int) or len(profile) < minimum_leads:
                add("insufficient_transformation_leads", None, f"{label} has {len(profile)} distinct leads; minimum is {minimum_leads}")

    if manifest.get("require_opposite_label_pairs") is True:
        for case_id, case in sorted(by_id.items()):
            lexical = case.get("lexical_controls")
            targets = lexical.get("matched_case_ids") if isinstance(lexical, dict) else None
            if not isinstance(targets, list) or len(targets) != 1 or not isinstance(targets[0], str):
                add("invalid_pair", case_id, "exactly one matched_case_id is required")
                continue
            target_id = targets[0]
            target = by_id.get(target_id)
            if target is None:
                add("missing_pair", case_id, f"matched case {target_id} is absent")
                continue
            target_lexical = target.get("lexical_controls")
            reciprocal = target_lexical.get("matched_case_ids") if isinstance(target_lexical, dict) else None
            if reciprocal != [case_id]:
                add("asymmetric_pair", case_id, f"matched case {target_id} does not point back")
            if target.get("domain") != case.get("domain"):
                add("cross_domain_pair", case_id, f"matched case {target_id} has a different domain")
            if _principle(target) == _principle(case):
                add("same_principle_pair", case_id, f"matched case {target_id} has the same principle")

    issues.sort(key=lambda item: (item["code"], item.get("case_id", ""), item["message"]))

    # Field-only semantic diagnostics for opposite-label pairs.
    lodo_threshold = float(semantic_policy.get("lodo_similarity_threshold", 0.0))
    pair_threshold = float(semantic_policy.get("pair_similarity_threshold", 0.0))
    if semantic_policy:
        checked_pairs: set[str] = set()
        for case_id, case in sorted(by_id.items()):
            lexical = case.get("lexical_controls")
            target_ids = lexical.get("matched_case_ids") if isinstance(lexical, dict) else None
            if not isinstance(target_ids, list) or not target_ids:
                continue
            for target_id in target_ids:
                if not isinstance(target_id, str):
                    continue
                if target_id not in by_id:
                    continue
                edge = "|".join(sorted([case_id, target_id]))
                if edge in checked_pairs:
                    continue
                checked_pairs.add(edge)
                target = by_id[target_id]
                pair_similarity: dict[str, float] = {}
                for field in SEMANTIC_DIAGNOSTIC_FIELDS:
                    left = _case_field_value(case, field)
                    right = _case_field_value(target, field)
                    similarity = _field_similarity(
                        left, right,
                        word_n_range=pair_word_ngrams,
                        char_n_range=pair_char_ngrams,
                    )
                    pair_similarity[field] = similarity
                max_field = max(pair_similarity.values()) if pair_similarity else 0.0
                semantics["pairs_evaluated"] += 1
                if pair_similarity:
                    diagnostics_payload = {
                        "pair_id": f"{case_id}|{target_id}",
                        "field_similarities": pair_similarity,
                        "max_similarity": max_field,
                    }
                    semantics["pair_diagnostics"].append(diagnostics_payload)
                    # For declared opposite-label pairs, low lexical overlap on problem/resulting/state is a signal.
                    diagnostic_fields_for_match = ("problem", "resulting_state", "problem_plus_solution")
                    low_similarity_count = sum(
                        1 for field in diagnostic_fields_for_match if pair_similarity.get(field, 1.0) < pair_threshold
                    )
                    if low_similarity_count >= 2:
                        add_semantic_issue(
                            "semantic_field_divergence",
                            case_id,
                            (
                                f"paired cases {case_id} and {target_id} do not align on"
                                f" field-only similarity (problem/solution overlap below {pair_threshold:.3f})"
                            ),
                        )
                break

        # Minimal deterministic leave-one-domain-out style diagnostics.
        domain_groups: dict[str, list[str]] = {}
        for case_id, case in by_id.items():
            domain = _as_str(case.get("domain"))
            if not domain:
                continue
            domain_groups.setdefault(domain, []).append(case_id)

        for held_out_domain, held_out_case_ids in sorted(domain_groups.items()):
            other_case_ids = [case_id for case_id in by_id if _as_str(by_id[case_id].get("domain")) != held_out_domain]
            if not other_case_ids:
                continue
            lodo_hits = []
            for held_out_case_id in held_out_case_ids:
                held_out_case = by_id[held_out_case_id]
                held_out_text = _case_field_value(held_out_case, "problem_plus_solution")
                similarities: list[float] = []
                for other_case_id in other_case_ids:
                    other_case = by_id[other_case_id]
                    similarity = _field_similarity(
                        held_out_text,
                        _case_field_value(other_case, "problem_plus_solution"),
                        word_n_range=pair_word_ngrams,
                        char_n_range=pair_char_ngrams,
                    )
                    similarities.append(similarity)
                if similarities:
                    max_similarity = max(similarities)
                    if max_similarity >= lodo_threshold:
                        lodo_hits.append({"case_id": held_out_case_id, "max_cross_domain_similarity": max_similarity})
            if lodo_hits:
                semantics["lodo"]["high_overlap_pairs"].append(
                    {"fold_domain": held_out_domain, "high_overlap_cases": lodo_hits}
                )
                semantics["lodo"]["pairs_evaluated"] += len(lodo_hits)
        if semantics["lodo"]["high_overlap_pairs"]:
            semantics["domain_shortcuts"].append(
                {
                    "code": "lodo_cross_domain_overlap",
                    "message": "Some held-out-domain cases have high cross-domain overlap under field-only similarity.",
                }
            )

        source_types = sorted(
            {row["source_type"] for row in semantics["provenance_records"] if row["source_type"]}
        )
        domain_evaluable = len(domain_groups) >= 2
        source_evaluable = len(source_types) >= 2
        # A source URI is provenance, not a structured generator-template identifier.
        template_evaluable = False
        semantics["shortcut_evaluability"] = {
            "domain": {
                "evaluable": domain_evaluable,
                "method": "leave_one_domain_out_ngram_overlap",
                "reason": None if domain_evaluable else "fewer than two domains",
            },
            "source": {
                "evaluable": source_evaluable,
                "observed_source_types": source_types,
                "reason": None if source_evaluable else "fewer than two source types",
            },
            "template": {
                "evaluable": template_evaluable,
                "reason": "case provenance has no structured template identifier",
            },
        }
        for key, evaluable in (
            ("domain", domain_evaluable),
            ("source", source_evaluable),
            ("template", template_evaluable),
        ):
            if semantic_policy.get(f"require_{key}_shortcut_evaluation") is True and not evaluable:
                semantics["issues"].append(
                    {
                        "code": f"{key}_shortcut_not_evaluable",
                        "message": f"{key} shortcut evaluation is required for freeze but is not evaluable",
                    }
                )

    # Per-pair semantic metadata requirement for scientific freeze.
    semantic_metadata_reviewed: set[str] = set()
    if isinstance(semantic_review_records, list):
        for record in semantic_review_records:
            if not isinstance(record, Mapping):
                continue
            pair_id = record.get("pair_id")
            status = record.get("status")
            if isinstance(pair_id, str) and status == PAIRED_SEMANTIC_REVIEW_STATUS:
                semantic_metadata_reviewed.add(pair_id)
    unreviewed_pairs: list[str] = []
    checked_pairs = set()
    for case_id, case in sorted(by_id.items()):
        lexical = case.get("lexical_controls")
        target_ids = lexical.get("matched_case_ids") if isinstance(lexical, dict) else None
        if not isinstance(target_ids, list):
            continue
        for target_id in target_ids:
            if not isinstance(target_id, str):
                continue
            if target_id not in by_id:
                continue
            pair_identifier = f"{case_id}|{target_id}"
            reverse_identifier = f"{target_id}|{case_id}"
            canonical = "|".join(sorted((case_id, target_id)))
            if canonical in checked_pairs:
                continue
            checked_pairs.add(canonical)
            if pair_identifier not in semantic_metadata_reviewed and reverse_identifier not in semantic_metadata_reviewed:
                unreviewed_pairs.append(pair_identifier)
    semantics["pair_semantic_review_required"] = bool(semantic_policy.get("require_pair_semantic_review", False))
    freeze_requires_pair_review = bool(semantic_policy.get("freeze_only_with_pair_review", False))
    if freeze_requires_pair_review and not semantics["pair_semantic_review_required"]:
        semantics["pair_semantic_review_required"] = True

    if semantics["pair_semantic_review_required"]:
        if unreviewed_pairs:
            semantics["issues"].append(
                {
                    "code": "missing_semantic_pair_review",
                    "message": f"missing semantic review metadata for {len(unreviewed_pairs)} pair(s)",
                    "pairs": sorted(unreviewed_pairs),
                }
            )

    semantic_freeze_ok = bool(semantic_policy) and not bool(semantics["issues"]) and not bool(issues)
    if semantics["pair_semantic_review_required"]:
        semantic_freeze_ok = semantic_freeze_ok and not any(
            issue.get("code") == "missing_semantic_pair_review" for issue in semantics["issues"]
        )
    ready_for_freeze = semantic_freeze_ok
    return {
        "artifact_class": "candidate-batch-audit",
        "batch_id": manifest.get("batch_id"),
        "status": "pass" if not issues else "fail",
        "ready_for_blinded_review": not issues,
        "ready_for_freeze": ready_for_freeze,
        "non_empirical": True,
        "evidence_eligible": False,
        "claim_ids": [],
        "semantic_leakage": semantics,
        "counts": {
            "total": len(cases),
            "by_principle": label_counts,
            "by_domain": domain_counts,
            "by_domain_and_principle": domain_label_counts,
            "transformation_leads_by_principle": {
                label: dict(sorted(profile.items())) for label, profile in transformation_leads.items()
            },
        },
        "hashes": {"manifest_sha256": _digest(manifest_file), "cases_sha256": _digest(cases_file)},
        "issues": issues,
    }
