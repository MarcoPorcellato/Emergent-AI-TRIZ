---
type: decision-record
title: ADR 0010 — Annotation ontology v1.2
description: Replace selected-label scores with operator-specific judgments before real collection.
status: active
last_verified: 2026-08-13
---

# ADR 0010 — Annotation ontology v1.2

## Status

Accepted as a development amendment. Human collection remains blocked pending
the cognitive pilot.

## Context

Ontology v1.1 used one presence and one essentiality score for the selected
label. Those fields cannot distinguish the relative strength of Segmentation
and Inversion when the rater selects Both. Other did not require a named
alternative, and Cannot determine still required numeric operator judgments.
The interface also carried values forward between cases.

No independent annotation collection has started, so this is the least costly
point to correct the contract without invalidating human observations.

## Decision

1. Record presence and essentiality separately for Segmentation and Inversion.
2. Keep contradiction resolution and feasibility as global judgments.
3. Require a named alternative_principle exactly when Other is selected.
4. Store all six scores as null for Cannot determine.
5. Render definitions, positive examples, near misses, adjacent-principle
   confusions, and the decision rule in the workbench.
6. Clear every label, score, confidence, rationale, and alternative field after
   each successful submission.
7. Keep v1.2 in development until three independent experts complete the
   six-case cognitive pilot and an amendment decision is recorded.

## Consequences

- Labels can be checked against operator-specific judgments without deriving
  human labels from generator intent.
- Cannot determine remains an explicit missing-judgment state rather than a
  synthetic zero score.
- v1.1 synthetic fixtures may be migrated for contract testing, but v1.1 and
  v1.2 human observations must never be pooled.
- This amendment changes no hypothesis claim and produces no scientific
  evidence.
