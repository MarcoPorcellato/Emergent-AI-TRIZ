---
type: lab05-runbook
title: Lab 05 candidate-direction contract
description: Public overview of the Lab 05 descriptive candidate-direction boundary, controls, and publication limits.
status: canonical
last_verified: 2026-08-13
---

# Lab 05 candidate-direction contract

Lab 05 defines a bounded representation-mapping contract for descriptive candidate directions. It is intentionally claim-ineligible.

## Contract summary

- artifact class: `candidate-direction-contract`
- empirical: `false`
- evidence eligible: `false`
- claim ids: empty
- analysis kind: `descriptive candidate directions`
- target label: `segmentation`
- contrast label: `inversion`
- unrelated labels: `merging`, `universality`
- fixture: current repository fixture

## Control design

The contract uses two explicit control families:

- norm-matched seeded random controls;
- unrelated-label controls.

The seeded random controls are fixed at three seeds: `1729`, `1730`, and `1731`.
The unrelated-label control set is fixed at two labels: `merging` and `universality`.
Norm matching is exact under the declared tolerance of `1e-12`.

The candidate direction is defined as `mean(target) - mean(contrast)` per layer.
Labels come exclusively from `cases[].labels[].principle`; there are no synthetic per-case target or contrast labels.

## Publication boundary

Lab 05 does not publish dense vectors. Public artifacts are hashes, projections, norms, and metadata only.

- no dense vector publication;
- no intervention;
- no steering claim;
- no causal claim;
- no implicit uplift from the candidate directions alone.

## Gates

The contract exposes eight fail-closed gates:

- D1 predecessor Lab 04 integrity and status;
- D2 case and representation integrity;
- D3 target and contrast support;
- D4 domain support;
- D5 nonzero candidate directions;
- D6 seeded random control repeatability and norm matching;
- D7 unrelated-label control isolation;
- D8 no-dense-vector, no-intervention, no-steering, and no-causal-claim boundary.

## Exact thresholds

- `minimum_cases_per_label = 6`
- `minimum_domains_per_label = 4`
- `random_control_seeds = 3`
- `unrelated_label_controls = 2`
- `norm_match_tolerance = 1e-12`
- `public_dense_vector_count = 0`
- `intervention = false`
- `steering_claims = false`
- `causal_claims = false`

## What Lab 05 is not

- not a steering benchmark;
- not a causal intervention claim;
- not a dense-vector publication;
- not a model comparison suite;
- not evidence for the Latent TRIZ Hypothesis.

## Validation boundary

The public contract is restricted to the current repository fixture and the metadata needed to verify the contract. The expected current result is executable but not-ready: the software runs, but the fixture is still insufficient for scientific readiness and should report `fail`/`not-ready` rather than a claim-bearing success.

Any later empirical work must be registered separately and must not inherit claim status from Lab 05.
