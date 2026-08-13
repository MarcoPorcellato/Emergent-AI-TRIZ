---
type: runbook
title: Lab 04 decodability contract
description: Fail-closed contract for representation decodability under the Latent TRIZ laboratory.
status: active
last_verified: 2026-08-13
---

# Lab 04 decodability contract

Lab 04 defines the representation-decoding surface of the repository. It is a bounded scientific contract, not a claim that the Latent TRIZ Hypothesis is true.

## Contract summary

- scope: linear probe decodability only
- probe family: one-vs-rest ridge
- representations: separate from labels and cases
- preprocessing: train-only standardization
- outer validation: leave-one-domain-out
- inner validation: domain-aware cross-validation for ridge alpha
- alpha grid: `0.01`, `0.1`, `1`, `10`
- permutations: `100` deterministic label permutations on training labels
- metrics: accuracy, macro-F1, balanced accuracy
- p-value rule: one-sided permutation test with `p = (1 + count(null >= observed)) / (1 + n)`
- multiple-comparison correction: Holm across layers
- current fixture: 2 cases, 2 layers, synthetic process-only vectors
- status: `fail` / not-ready

## What Lab 04 is for

Lab 04 makes the decodability boundary observable. It exists so the repository can later test whether internal representations carry label-aligned signal under preregistered controls. It does not interpret the current two-case fixture as empirical evidence.

## Required method and evaluation rules

The public contract is fixed as follows:

- only linear one-vs-rest ridge probes are allowed;
- representations are treated as standalone records, not as labels and not as cases;
- standardization is fit on training folds only;
- outer folds must leave one domain out;
- inner folds must search only the declared alpha grid;
- the chosen alpha must break ties toward the smallest value;
- the chosen layer must break ties toward the lowest layer index;
- the null distribution must use exactly 100 deterministic label permutations on training labels;
- all layers must be evaluated with the same declared permutation rule;
- Holm correction must be applied across layers;
- the boundary is non-claim even when numbers look favorable.

## Readiness gates

Lab 04 uses fail-closed gates:

- P1 predecessor receipts for Lab 01, Lab 02, and Lab 03 are present, pass, and are hash-backed;
- P2 representation provenance is complete, hash-backed, dimension-consistent, and aligned to the current cases;
- P3 the study has at least 2 labels, at least 4 domains, and at least 6 cases per label-domain cell;
- P4 nested domain splitting is exact and leakage-free;
- P5 preprocessing and hyperparameter selection are train-only and receipt-backed;
- P6 permutation calibration is valid and Holm correction is applied correctly;
- P7 the preregistered threshold is met only if corrected `p <= 0.05` and macro-F1 improves over majority by at least `0.10` in every outer fold;
- P8 the non-claim boundary remains enforced.

## Current fixture boundary

The current fixture is intentionally undersized and synthetic:

- empirical: `false`
- evidence_eligible: `false`
- claim_ids: empty
- status: `fail` / not-ready

The current representation records are process-only vectors for the existing two cases at layers 0 and 1. They are deterministic contract witnesses and must not be described as model activations.

## What Lab 04 is not

- not a causal-tracing result;
- not a steering result;
- not a publication-ready decodability finding;
- not a claim that the hypothesis is supported;
- not a substitute for EXP-001;
- not a proof that any representation carries scientific signal.

## Reproducibility boundary

The contract is valid only when:

- the config file validates against the schema;
- the representation records validate against the schema;
- the result file validates against the schema;
- all declared thresholds match this document;
- the output remains fail-closed until the declared minima are met.

Run the complete Lab 04 fixture and render its machine-readable and HTML reports with:

```bash
make lab04
```

The maintained outputs are `results/lab04/decodability/probe_result.json`,
`results/lab04/decodability/summary.json`, and
`results/lab04/decodability/report.html`. Two independent executions must be
byte-identical. The canonical `summary_json` hash is computed with that field
blank to avoid a self-referential digest.

## Current concrete result

The maintained two-case fixture passes P2 (representation integrity) and P8
(non-claim boundary). It fails P1 and P3–P7 because Lab 02 and Lab 03 remain
non-ready and the fixture has only one unanimous label across two domains. This
is useful laboratory instrumentation data, but it is not evidence for or against
the Latent TRIZ hypothesis.

## Public interpretation

Lab 04 is the first controlled bridge from labeled dataset structure to representation-level analysis. It narrows the question to decodability under preregistered controls and keeps the boundary between observation and claim explicit.
