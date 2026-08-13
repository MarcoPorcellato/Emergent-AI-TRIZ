---
type: decision-record
title: ADR 0009 - Lab 05 candidate directions
description: Define the claim-ineligible public contract for Lab 05 descriptive candidate directions and control families.
status: active
last_verified: 2026-08-13
---

# ADR 0009 - Lab 05 candidate directions

## Status

Accepted

## Context

The roadmap calls for representation-mapping work that inspects activations and descriptive candidate directions before any causal intervention or steering claim is considered.

The repository needs a public contract for that work that stays vendor-neutral, English, and claim-ineligible. The contract must be compatible with the roadmap language while avoiding dense-vector publication or any implied causal result.

## Decision

1. Define Lab 05 as a current-fixture contract for descriptive candidate directions.
2. Derive each case label exclusively from `cases[].labels[].principle`; do not introduce synthetic per-case target or contrast labels.
3. Use `segmentation` as the target label and `inversion` as the contrast label.
4. Use `merging` and `universality` as the unrelated-label controls.
5. Require two control families: norm-matched seeded random controls and unrelated-label controls.
6. Fix the seeded random control count at three (`1729`, `1730`, `1731`) and the unrelated-label control count at two.
7. Set norm matching tolerance to `1e-12` for the public contract.
8. Publish hashes, projections, norms, and metadata only; do not publish dense vectors.
9. Keep `empirical` false, `evidence_eligible` false, and `claim_ids` empty.
10. Forbid intervention, steering claims, and causal claims in the Lab 05 public contract.
11. Expose eight fail-closed gates, D1 through D8, as contract checks rather than scientific evidence.

## Gates

- D1 predecessor Lab 04 integrity and status;
- D2 case and representation integrity;
- D3 target and contrast support;
- D4 domain support;
- D5 nonzero candidate directions;
- D6 seeded random control repeatability and norm matching;
- D7 unrelated-label control isolation;
- D8 no-dense-vector, no-intervention, no-steering, and no-causal-claim boundary.

## Consequences

- Lab 05 can describe representation-mapping preparation without collapsing into a steering benchmark.
- The public artifacts remain reviewable and bounded to norms, hashes, and projections.
- The current fixture is expected to execute but remain not-ready for scientific claim-bearing publication.
- Later empirical or causal work must be registered as a separate contract and cannot inherit claim status from Lab 05.
