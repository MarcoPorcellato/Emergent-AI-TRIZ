---
type: Roadmap
title: Research Laboratory Roadmap
description: Phase 0 foundation and future experimental stages for Project Latent TRIZ.
status: canonical
last_verified: 2026-08-12
---

# Roadmap

This repository is at **Phase 0 foundation**.

The purpose of Phase 0 is to establish a public lab contract, not to claim experimental success.

## Phase 0 - Foundation

Completed or maintained in this repository:

- define the repository map and claim boundaries;
- define the case schema;
- define preregistration and results conventions;
- define contribution rules for provenance and leakage control;
- validate repository-owned artifacts with dependency-free CI.

## Stage 1 - Dataset assembly

Future work:

- collect or synthesize cross-domain cases;
- assign multi-label principle annotations;
- document provenance and licensing;
- freeze a dataset snapshot before confirmatory evaluation.

## Stage 2 - Surface baselines

Future work:

- benchmark lexical and shallow classifiers;
- quantify leakage and shortcut risk;
- compare against random and unrelated controls;
- revise the dataset only if the baselines show a problem.

## Stage 3 - Representation mapping

Future work:

- inspect activations and candidate directions;
- test domain transfer of the candidate operators;
- distinguish correlation from representation evidence;
- keep exploratory plots separate from confirmatory claims.

## Stage 4 - Causal intervention

Future work:

- steer activations along candidate directions;
- compare with norm-matched and unrelated controls;
- evaluate whether strategy changes without prompt leakage;
- record all intervention parameters.

## Stage 5 - Composition

Future work:

- combine candidate operators;
- test whether joint interventions behave predictably;
- compare with single-operator and random-vector baselines;
- report failures as failures.

## Stage 6 - Replication

Future work:

- repeat across models, domains, prompts, and evaluation sets;
- separate base and instruction-tuned checkpoints;
- retain earlier reports when later analyses change;
- publish versioned results only after the evidence chain is complete.
