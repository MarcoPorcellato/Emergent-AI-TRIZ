---
type: decision-record
title: ADR 0002 — Stage 1 blinded two-arm pilot contracts
description: Introduce concrete JSONL record contracts and deterministic Stage 1 pilot smoke checks.
status: active
last_verified: 2026-08-12
---

# ADR 0002 — Stage 1 blinded two-arm pilot contracts

## Status

Accepted

## Context

Stage 1 must standardize a deterministic blind pilot protocol before any confirmatory interpretation. The current workflow uses:

- packet records from blinded arm mapping
- response records tied to packet and blind label
- annotation records with fixed six-dimensional scoring
- summary records with fingerprinted provenance and arm means

## Decision

1. Keep all four Stage 1 schema records as strict one-record JSONL objects.
2. Require `A` and `B` blind labels in packet, response, and annotation records.
3. Require response model metadata and UTC timestamps.
4. Require annotation `scores` with exactly:
   `contradiction_resolution`, `principle_use`, `feasibility`, `novelty`,
   `constraint_adherence`, `terminology_only`.
5. Set summary as a single JSON object with counts, means, paired deltas,
   and sha256-prefixed fingerprints.
6. Make Stage 1 smoke deterministic via `pilot-prepare`, byte-for-byte artifact
   comparison, and `pilot-score` regeneration against tracked files.
7. Keep Stage 1 outputs as non-discovery process smoke and not evidence.

## Consequences

- Pilot artifacts are now deterministic and auditable per seed.
- Schema checks block malformed trial records in CI.
- Stage 1 can be replayed from tracked `data/pilot/*` files.
- Confirmatory claims are not derived from these artifacts.
