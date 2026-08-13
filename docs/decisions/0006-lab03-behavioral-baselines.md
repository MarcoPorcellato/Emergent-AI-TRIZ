---
type: decision-record
title: ADR 0006 — Lab 03 behavioral baselines
description: Define the public contract for fail-closed behavioral baselines and preregistered readiness gates.
status: active
last_verified: 2026-08-13
---

# ADR 0006 — Lab 03 behavioral baselines

## Status

Accepted

## Context

The repository needs a public contract for behavioral baselines that is distinct from model anatomy and distinct from any scientific claim.

Lab 03 must support a future open-source laboratory for checking whether simple behavioral surfaces can replicate, falsify, or bound the Latent TRIZ Hypothesis. The contract therefore has to name the baseline families, readiness gates, and declared thresholds without letting a small synthetic fixture masquerade as evidence.

## Decision

1. Define Lab 03 as a behavioral baseline contract only.
2. Keep the public fixture empirical status at `false`.
3. Keep `evidence_eligible` at `false` and `claim_ids` empty.
4. Treat the current 2-case / 1-label fixture as `fail` / not-ready.
5. Require future implementations to cover the following method families:
   `majority`, `keyword_matching`, `bag_of_words`, `conventional_sentence_embeddings`, `topic_classification`, `output_only_llm`, and `random_label`.
6. Allow `char_ngram` only as a local diagnostic baseline and never as a substitute for conventional embeddings.
7. Require fail-closed gates B1 through B8:
   - B1 snapshot status and integrity;
   - B2 minimum labels, domains, and declared case minima;
   - B3 problem-only and problem-plus-solution view completeness;
   - B4 required-family coverage with hash-backed adapter receipts for external methods;
   - B5 leave-one-domain-out coverage;
   - B6 deterministic random-label calibration with declared permutations;
   - B7 preregistered lexical-shortcut risk rule;
   - B8 non-claim boundary.
8. Declare the following provisional readiness thresholds:
   seed `1729`, 100 random permutations, minimum 2 labels, minimum 4 domains, minimum 24 cases per label, minimum 12 cases per held-out domain, minimum 6 cases per label in every domain, shortcut macro-F1 threshold `0.80`, and shortcut margin over majority `0.10`.
9. Keep the thresholds documented as readiness rules, not scientific truth.

## Consequences

- The repository can now state the behavioral baseline surface before any implementation claims are made.
- Small synthetic fixtures remain explicit contract witnesses, not evidence.
- Future Lab 03 code and evaluation artifacts must satisfy the documented gates before they can be interpreted as readiness evidence.

## Non-goals

- No claim registry expansion here.
- No model selection.
- No scientific result framing.
- No replacement for preregistered EXP-001 execution.
