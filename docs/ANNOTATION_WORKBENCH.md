---
type: guide
title: Blinded Annotation Workbench
description: Local workflow for blinded Segmentation and Inversion dataset judgments.
status: active
last_verified: 2026-08-13
---

# Blinded annotation workbench

The workbench collects independent human judgments for dataset construction. It
runs with the Python standard library, binds only to a loopback address, and
serves no external assets.

Start an interactive session with a pseudonymous rater identifier:

```text
make annotate ANNOTATION_RATER_ID=rater_01
```

For a headless session, use `make annotate-serve`. Override
`ANNOTATION_OUTPUT` or `ANNOTATION_PORT` when separate rater files or ports are
needed. The default output is ignored by Git and remains under
`artifacts/annotations/dataset-annotations.jsonl`.

The browser receives only the case fields needed for judgment. Embedded labels,
provenance, split assignments, lexical controls, related-case identifiers,
allocation keys, and results are excluded. Submissions require the page's
session token, match the dataset annotation schema, and are appended with an
`fsync` before success is reported. Duplicate case/rater pairs are rejected.
Case order is deterministically randomized from the pseudonymous rater ID and
guide digest, preventing tracked-file order from becoming a label cue while
keeping each session reproducible.
Restarting with the same rater and output path resumes at the remaining cases;
previously saved case/rater pairs are omitted from the queue.
An annotator who cannot make a defensible forced choice records an explicit
`abstain` audit state; the case never disappears silently from coverage.
The interface does not manufacture a rationale for that state: an abstention
records only the explicit label and zero confidence, while substantive choices
still require rater-authored rationale text.

The guide at
`experiments/001-stage1-pilot/annotation-guide.json` is versioned and hashed
into every saved annotation. A human record uses `non_empirical: false` because
the judgment itself is observed data. It remains `evidence_eligible: false` at
the workbench boundary: collection alone cannot support or promote a hypothesis
claim. Dataset freeze, agreement, leakage, preregistration, and claim gates are
separate steps.

Ontology v1.2 replaces the selected-label presence and essentiality fields with
independent Segmentation and Inversion judgments. A substantive annotation
records four operator-specific scores plus global contradiction-resolution and
feasibility scores. Cannot determine stores all six scores as null. Other is
valid only with a named alternative principle. The interface exposes the guide
definition, positive examples, near misses, adjacent-principle confusions, and
decision rule, then clears every control after a successful save to prevent
carry-over anchoring.

Version 1.2 remains a development ontology until three independent TRIZ experts
complete the six-case cognitive pilot described in
`experiments/annotation-ontology-v1-2-cognitive-pilot/protocol.json`. The
protocol is ready, but no expert responses or result are claimed. Wave 2 human
collection remains blocked until the ambiguity synthesis and keep-or-amend
decision are recorded.

For Wave 1 audit runs, the repository also supports a batched check that reads
per-rater files, validates the guide revision and digest, and writes a retained
audit summary at `artifacts/annotations/wave1-audit.json`:

```text
make wave1-annotation-audit ANNOTATION_FILES="path/rater1.jsonl path/rater2.jsonl"
```

This audit surface requires one file per pseudonymous rater, at least two
distinct raters, complete case coverage, exact pairwise percent agreement and
nominal Krippendorff alpha of at least 0.8, and abstention rate at or below 0.2.
The frozen policy also reports deterministic 95% case-bootstrap percentile
intervals for raw agreement and nominal alpha using 2,000 resamples and seed
1729; interval bounds are descriptive until a gate is preregistered.
Ordinal Krippendorff alpha is retained per score dimension as descriptive
calibration metadata. The audit preserves disagreements, unanimous abstentions,
consensus calls, and digests for later adjudication. The resulting audit record
is empirical human judgment metadata, but it remains `evidence_eligible: false`
and must keep `claim_ids: []`. `ready_for_adjudication` may be true while the
freeze remains false.
Even above the aggregate agreement threshold, any disagreement or unanimous
abstention prevents freeze readiness until the case is adjudicated.

Guide v1.0 and v1.1 records are discovery-only. They must not be combined with
v1.2 records in a freeze audit; v1.2 binds each judgment to the exact displayed
case, dataset batch, guide digest, display version, and collection session.
