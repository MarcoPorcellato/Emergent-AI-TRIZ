---
type: research-specification
title: Track B — controlled emergence
description: Separate from-scratch training contract for the Strong Latent TRIZ route.
status: planned
last_verified: 2026-08-18
---

# Track B — controlled emergence

Track B is independent of Track A. It asks whether an operator-like
representation emerges in a model trained from scratch, rather than whether a
pretrained model already contains a proxy. This document is a no-training,
no-model-output plan.

## Frozen-before-training requirements

- corpus provenance, licenses, deduplication, and contamination audit;
- no TRIZ terminology, principle numbers, Matrix cells, Panitz edges, source
  wording, or canonical examples in training or validation text;
- family-grouped train, validation, held-out-domain, and sealed splits;
- no reuse of Track A outcomes to select data, operators, hyperparameters, or
  checkpoints;
- fixed architecture, tokenizer, seed set, optimizer, budget, and checkpoint
  schedule;
- matched shuffled-solution, generic-transformation, lexical, and random-label
  baselines;
- preregistered operator probes and causal intervention plan.

## Minimal emergence study

Use a small inspectable Transformer and at least two independent training seeds.
Evaluate the same frozen operator contract at initialization and at declared
early, middle, and final checkpoints. The primary test is held-out-domain
decodability above all matched controls. A candidate emergence signal must then
pass the Lab 06 causal contract without using the sealed split for selection.

## Terminal outcomes

Every training run publishes `positive`, `null`, `failed`, or
`non_interpretable`, including incomplete checkpoints and resource failures.
Positive evidence is at most controlled emergence for the registered operator;
it is not a general claim about TRIZ or intelligence.

## Required receipts

Publish immutable corpus and split hashes, training environment and seed
receipts, checkpoint registry, probe/statistical results, causal controls,
capability checks, recovery observations, external dense-asset hashes, and a
fresh-clone verifier. Training remains unauthorized until this contract is
frozen, qualified, and separately approved.
