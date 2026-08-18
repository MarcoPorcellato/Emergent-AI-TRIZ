---
type: human-validation-protocol
title: H1 — three-expert TRIZ cognitive pilot
description: Human-only construct-validation gate preceding canonical labels and causal work.
status: blocked_by_human_work
last_verified: 2026-08-18
---

# H1 — three-expert TRIZ cognitive pilot

This is the operational handoff for the first real human validation. Existing
`data/pilot/*` files are synthetic calibration artifacts and must remain
`non_empirical: true`; they cannot close H1.

The public collection packet is now available under
`experiments/h1-cognitive-pilot/`. It contains six unlabeled cases, a proposed
v1.2 guide, deterministic display allocation, and no answer key. Its status is
`ready_for_collection`; it is not human evidence until three independent expert
sessions are returned and audited.

## Frozen design

- six human-authored, TRIZ-name-free paired cases;
- blinded presentation with randomized arm order;
- three independent qualified TRIZ experts with pseudonymous IDs;
- v1.2 annotation guide and session hash in every raw record;
- labels for Segmentation, Inversion, adjacent principle, contradiction
  resolution, feasibility, and abstention;
- no model output, source-exposed context, or sealed target is shown to raters.

## Required evidence

1. packet, guide, allocation, and case-payload hashes;
2. one immutable raw file per expert;
3. exact coverage of all six cases by all three experts;
4. agreement, abstention, and bootstrap receipts using the frozen policy;
5. additive disagreement, exclusion, and adjudication ledgers;
6. a versioned `keep` or `amend` decision.

The existing guide declares a minimum of two raters, raw agreement and nominal
alpha floors of 0.8, abstention at most 0.2, 2,000 bootstrap resamples, and
seed 1729. These values must be reviewed and frozen in the v1.2 amendment
before collection; the synthetic summary's one-rater smoke coverage is not
evidence.

## Closure rule

H1 closes only when the three independent sessions, audit, adjudication, and
keep/amend decision are all present and valid. A missing expert, insufficient
coverage, or unresolved guide ambiguity leaves H1 `blocked_by_human_work`.
Wave 2 canonical labels and any Lab 06 causal dossier remain gated on closure.
