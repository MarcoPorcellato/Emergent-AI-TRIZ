---
type: decision-record
title: ADR 0008 — Local visual laboratory suite
description: Define a one-command dashboard over maintained laboratory artifacts without recomputation or claim promotion.
status: active
last_verified: 2026-08-13
---

# ADR 0008 — Local visual laboratory suite

## Status

Accepted

## Context

Labs 00 through 04 expose separate deterministic reports, but a new contributor has no single visual entrance for understanding their order, readiness state, provenance, and evidence boundaries. Re-running every laboratory would make the entrance expensive and would incorrectly couple navigation to model availability.

## Decision

1. Make `make lab` the one-command visual entrance to all maintained Lab 00 through Lab 04 artifacts.
2. Keep `make lab-render` as its headless equivalent.
3. Render a deterministic, dependency-free index from tracked summaries and report paths.
4. Verify that every maintained result is evidence-ineligible and attached to no claim before rendering it.
5. Display empirical classification, readiness status, source hash, and a link to the detailed report for each laboratory.
6. Interpret a red readiness result as an observable scientific boundary, not as an execution failure.
7. Keep experiment reproduction in separate lab-specific targets; the dashboard performs no inference, acquisition, probing, steering, or causal analysis.

## Consequences

- A fresh clone has a useful visual experience without model downloads or API credentials.
- The exact Lab 01 result remains visible without bypassing host resource admission.
- Synthetic readiness fixtures cannot be mistaken for evidence because their classification is displayed and checked before rendering.
- Detailed laboratories can evolve independently while preserving a stable public entrance.

## Non-goals

- No scientific claim promotion.
- No model execution or acquisition.
- No replacement for preregistration or immutable run receipts.
- No aggregation of metrics across scientifically incomparable labs.
