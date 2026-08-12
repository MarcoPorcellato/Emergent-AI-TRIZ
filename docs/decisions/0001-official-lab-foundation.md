---
type: decision-record
title: ADR 0001 — Official Lab Foundation
description: Define a dependency-free, foundation-only scope for the repository and set evidence boundaries for claims and exports.
status: canonical
last_verified: 2026-08-12
---

# ADR 0001 — Official Lab Foundation

## Status

Accepted

## Context

The repository is currently a public foundation scaffold for TRIZ-style study workflows.
No empirical dataset, preregistered hypothesis, blinded run records, or replicated results
exist in this checkout yet.

## Decision

1. Maintain the repo as an **official-lab foundation** with zero hard runtime dependencies
   beyond Python 3.11+ standard-library validation and fingerprint workflows.
2. Treat only the entry points declared in `docs/okf-profile.toml` as the maintained documentation bundle; `docs/ARTICLE.md` is a preserved motivating artifact with its verification boundary recorded separately.
3. Require explicit evidence boundaries in `docs/index.md` and linked references so that
   exploratory statements are not mixed with confirmatory records.
4. Require any maintained documentation change to update `last_verified`.

## Evidence boundaries

- **Inside scope:** schema contracts, artifact flow, governance expectations, and process checks.
- **Outside scope:** empirical claims, model performance, discovery outcomes, and benchmark wins.
- **Rule:** if evidence is missing, the claim is excluded from protocol-facing output and
  labeled as scope, intent, or method.

## Consequences

- Changes to conclusions or claims must add or update the appropriate ADR and log entries.
- PRs must include a documentation audit and `last_verified` updates before merge.
- This repository remains reusable as an interoperability and reproducibility scaffold until
  it accumulates evidence-bound artifacts in preregistration, dataset, and results tracks.
