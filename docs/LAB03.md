---
type: runbook
title: Lab 03 behavioral baseline contract
description: Public contract for fail-closed behavioral baselines that remain claim-ineligible.
status: active
last_verified: 2026-08-13
---

# Lab 03 behavioral baseline contract

Lab 03 defines the behavioral surface of the repository without crossing into scientific claim making. It is a contract for bounded baseline checks, not evidence for the Latent TRIZ Hypothesis.

## Contract summary

- scope: behavioral surface baselines only
- empirical: `false`
- evidence_eligible: `false`
- claim_ids: empty
- current fixture: 2 cases, 1 label, 2 domains
- status: `fail` / not-ready

## What Lab 03 is for

Lab 03 exists to make the pre-claim boundary observable. It checks whether the repository can measure simple behavioral baselines against preregistered data and report readiness without overstating conclusions.

The initial public fixture remains intentionally undersized. It is useful as a contract witness and not as a scientific result.

## Required method families

The public contract names the baseline families that future implementations must cover:

- majority;
- keyword_matching;
- bag_of_words;
- conventional_sentence_embeddings;
- topic_classification;
- output_only_llm;
- random_label.

Lab 03 uses four frozen textual views for LODO baselines:

- `problem_only`
- `transformation_only`
- `resulting_state_only`
- `problem_plus_solution` (problem plus constraints/initial state/desired improvement/worsening/transformation/resulting-state/solution)

Local diagnostic methods include `char_ngram` and a length/punctuation-only
nearest-centroid classifier. They are diagnostic baselines and must not be
mislabeled as conventional embeddings.

`minimum_cases_per_label` applies to the complete dataset, while
`minimum_training_cases_per_label` is the explicit support floor inside each
leave-one-domain-out training fold.

## Readiness gates

Lab 03 uses fail-closed readiness rules:

- B1 snapshot status and integrity are valid;
- B2 at least 2 labels, at least 4 domains, and declared minimum cases per label and domain;
- B3 required LODO views are complete;
- B4 required-family coverage is present, with hash-backed adapter receipts for external methods;
- B5 leave-one-domain-out coverage is complete;
- B6 random-label calibration is deterministic and uses declared permutations;
- B7 lexical-shortcut risk is preregistered;
- B8 non-claim boundary remains enforced.

These are provisional readiness rules. They are operational thresholds, not scientific truth.

An external family counts as complete only when its config entry points to a contained relative JSON receipt, the declared SHA-256 matches the file, and the receipt preserves the non-empirical, claim-ineligible boundary. A declared hash without a verifiable receipt fails B4.

## Declared thresholds

- seed: `1729`
- random permutations: `100`
- minimum labels: `2`
- minimum domains: `4`
- minimum cases per label: `24`
- minimum cases per held-out domain: `12`
- minimum cases per label in each domain: `6`
- shortcut macro-F1 threshold: `0.80`
- shortcut margin over majority: `0.10`

## Current fixture boundary

The current synthetic 2-case fixture remains:

- empirical: `false`
- evidence_eligible: `false`
- claim_ids: empty
- status: `fail` / not-ready

That boundary is intentional. It prevents small synthetic data from being presented as a scientific validation run.

## What Lab 03 is not

- not a TRIZ claim;
- not a causal-tracing result;
- not a steering benchmark;
- not a model-comparison leaderboard;
- not a replacement for preregistered experimental execution;
- not a publication-ready result.

## Reproducibility boundary

The lab contract is valid only when:

- the config file validates against the schema;
- the result file validates against the schema;
- the readiness thresholds match this document;
- the visible status remains fail-closed until the declared minima are met.

## Public interpretation

Lab 03 is the first controlled bridge between the repository's didactic infrastructure and the behavioral evaluation surface. It is intentionally narrow: it formalizes how the repository will later support lexical controls, cross-domain checks, and random-label calibration without misrepresenting undersized data.

## Provenance shortcut diagnostics

Lab 03 adds provenance-only categorical shortcut diagnostics for:

- domain,
- provenance `source_type`,
- provenance `template_id`.

Each block reports whether evaluation is possible (`evaluable`) and includes
`macro_f1` / `accuracy` only when all required structured values are present,
at least two categories exist, and every category has leave-one-out support.
A single source family or one unique template per case is `not_evaluable`; no
synthetic template identifiers are emitted.
