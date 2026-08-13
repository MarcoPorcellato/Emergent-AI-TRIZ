---
type: decision-record
title: ADR 0007 — Lab 04 decodability
description: Define the public contract for representation decodability under fail-closed controls.
status: active
last_verified: 2026-08-13
---

# ADR 0007 — Lab 04 decodability

## Status

Accepted

## Context

The repository needs a public contract for representation decodability that is distinct from dataset anatomy, distinct from behavioral baselines, and distinct from scientific claim making.

Lab 04 must support a future open-source laboratory for testing whether latent representations can be decoded under conservative, preregistered controls. The contract therefore has to specify probe family, split policy, permutation calibration, and readiness thresholds without letting a small synthetic fixture masquerade as evidence.

## Decision

1. Define Lab 04 as a linear decodability contract only.
2. Restrict probes to linear one-vs-rest ridge.
3. Keep representations separate from labels and cases.
4. Standardize using training folds only.
5. Use leave-one-domain-out as the outer split.
6. Use domain-aware cross-validation inside the training fold to choose ridge alpha from `0.01`, `0.1`, `1`, and `10`.
7. Break alpha ties toward the smallest value and layer ties toward the lowest layer index.
8. Use exactly 100 deterministic training-label permutations, blocked by outer-training domain and shared across layers.
9. Evaluate accuracy, macro-F1, and balanced accuracy.
10. Repeat domain-aware inner alpha selection inside every permutation so the null calibrates the complete selection pipeline.
11. Select the layer with the highest observed outer-fold mean macro-F1, breaking ties toward the lowest index, and use the maximum layer statistic in each shared permutation for family-wise control.
12. Fail closed before interpretation when `1 / (permutations + 1)` exceeds the configured family-wise alpha.
13. Apply the preregistered majority-margin requirement only to every outer fold of the selected layer, rather than requiring every layer to be significant.
14. Require P1 through P8 fail-closed readiness gates before treating the result as ready.
15. Keep the current two-case representation fixture empirical `false`, evidence-eligible `false`, and claim-ineligible.

## Consequences

- The repository now has a decodability contract that is observable and bounded.
- Small synthetic representation records remain contract witnesses, not model activations and not evidence.
- Future Lab 04 code must satisfy the documented split, preprocessing, calibration, and threshold rules before the result can be read as readiness evidence.
- Dense permutation null draws remain internal; public results retain their count and SHA-256 digest together with the selected layer and family-wise p-value.

## Non-goals

- No causal tracing.
- No steering benchmark.
- No model selection.
- No scientific conclusion.
- No replacement for preregistered EXP-001 execution.
