# Results

This directory contains versioned reports for positive, negative, mixed, failed,
non-interpretable, incompatible, and null results.

Every report must link to the relevant preregistration, code commit, data snapshot, raw-output checksums, and evaluator protocol. Exploratory findings must be labeled as exploratory. Reanalysis must preserve earlier reports and explain every changed decision.

## Published EXP-001 evidence

- [Reference-integrated SmolLM2 package](./exp001-r3/smollm2-r3-20260818-01/) — terminal `null`; blinded transfer and source-exposed competence are reported separately.
- [Seven-model comparative record](../docs/EXP001_COMPARATIVE_REFERENCE_STUDY.md) — seven independent one-shot packages, all terminal `null`, with no pooled statistic or claim promotion.
- [Current status snapshot](../docs/CURRENT_STATUS.md) — compact table of model revisions, p-values, resource receipts, and package links.

Comparative dense response scores are external assets where the publication
manifest says so. Their locator and SHA-256 are public; a fresh clone must fail
closed when an asset is missing or mutated and must pass only with the exact
hash-matching asset.

## Published instrumentation results

- [Lab 01 model anatomy](./lab01/model-anatomy/report.html) — exact-revision real-model instrumentation; empirical, not evidence-eligible, and attached to no scientific claim.
- [Lab 02 dataset anatomy](./lab02/dataset-anatomy/report.html) — synthetic dataset-release readiness; non-empirical, not evidence-eligible, and attached to no scientific claim.
- [Lab 03 behavioral baselines](./lab03/behavioral-baselines/report.html) — synthetic surface-control readiness; non-empirical, not evidence-eligible, and attached to no scientific claim.
- [Lab 04 decodability](./lab04/decodability/report.html) — deterministic representation-decoding boundary (fixture is non-empirical and not evidence-eligible).
- [Lab 05 candidate directions](./lab05/candidate-directions/report.html) — descriptive direction and control diagnostics; no dense vectors, interventions, or claims.
