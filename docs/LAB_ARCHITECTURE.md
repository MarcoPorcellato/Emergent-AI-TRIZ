---
type: Architecture
title: Lab Architecture
description: Artifact flow, governance boundaries, and structure of the official Project Latent TRIZ laboratory.
status: canonical
last_verified: 2026-08-13
---

# Lab architecture

Project Latent TRIZ is organized as a public laboratory scaffold. The goal is to make future studies auditable before any empirical claim is made.

## Artifact flow

The expected confirmatory flow is:

1. hypothesis
2. preregistration
3. dataset snapshot
4. study manifest
5. run records
6. blinded evaluation
7. versioned results

Each artifact should be immutable once it is part of a confirmatory chain. If a plan changes, the change should become a new artifact rather than an overwrite.

## Artifact definitions

- Hypothesis: a falsifiable statement about latent representations or behavior.
- Preregistration: a frozen plan that specifies data splits, controls, metrics, exclusions, and success criteria.
- Dataset snapshot: a versioned corpus with provenance, schema conformity, and leakage controls.
- Study manifest: the frozen study-level contract, including hypothesis, preregistration, dataset snapshot, models, primary metrics, controls, and code revision.
- Run records: per-execution records containing model and tokenizer revisions, prompt hashes, seeds, environment, intervention parameters, output hashes, and evaluator protocol.
- Blinded evaluation: human or automated judgment that is insulated from discovery labels and unblinded context.
- Versioned results: a report that links all prior artifacts and records the analysis revision.

## Governance boundaries

- Discovery and confirmation are separate phases.
- Exploratory analyses may inform later plans, but they do not substitute for preregistration.
- A result report must never imply that the lab has already achieved the claimed scientific target unless the supporting chain exists.
- Dataset, model, and evaluation changes must be traceable to versioned artifacts.

## Lab structure

The repository currently supports foundation work only:

- schema definition
- protocol writing
- contribution rules
- CI validation

The future research stages are described in [`ROADMAP.md`](ROADMAP.md).
