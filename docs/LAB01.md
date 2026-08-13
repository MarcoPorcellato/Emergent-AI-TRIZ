---
type: runbook
title: Lab 01 didactic model contract
description: Public overview of the Lab 01 model anatomy, receipts, and validation boundary.
status: canonical
last_verified: 2026-08-13
---

# Lab 01 didactic model contract

Lab 01 is the first model-instrumentation laboratory in this repository. Its purpose is to make the model boundary observable before any scientific interpretation is attempted.

## Contract summary

- model: `EleutherAI/pythia-70m-deduped`
- revision: `e93a9faa9c77e5d09219f6c868bfc7a1bd65593c`
- license: `Apache-2.0`
- artifact class: `model-instrumentation`
- empirical: `true`
- evidence eligible: `false`
- claim ids: empty

## Receipt-derived states

`unselected -> selected -> acquisition_planned -> acquired -> integrity_verified -> load_verified -> instrumentation_verified -> lab_ready`

State changes are accepted only when the matching receipt schema validates and the record remains internally consistent.

## What Lab 01 is not

- not a TRIZ probe suite;
- not a steering benchmark;
- not a causal-tracing dashboard;
- not a quantization comparison;
- not a multi-model bake-off;
- not evidence for the Latent TRIZ Hypothesis.

## Validation boundary

Lab 01 now executes entirely from a local snapshot after acquisition. It validates eight fail-closed gates:

- G1 exact model identity and runtime-file hashes;
- G2 offline CPU load;
- G3 coherent tokenization, masks, and positions;
- G4 instrumentation invariance;
- G5 finite numerical summaries;
- G6 final logit-lens parity with the model's native logits;
- G7 repeated-run stability;
- G8 hashes for every non-self-referential public artifact.

Structural prompt, token, and top-k records are byte-stable for the frozen environment. Numerical comparisons use the declared backend/dtype tolerances. Dense activations are never committed; public layer records contain only name, shape, dtype, health summaries, and hashes.

## Reproduce the published bundle

Create Python 3.11 environment `.venv`, install `requirements-lab01.lock`, and place the exact model snapshot at a local path. Then run:

```bash
make lab01 LAB01_MODEL_ROOT=/path/to/pythia-70m-deduped-e93a9faa
```

The sparse report and machine-readable records are written to `results/lab01/model-anatomy/`.

## Public status

The first public run passed G1-G8 for three frozen non-TRIZ prompts, six captured post-layer residuals per prompt, exact final-logit parity, and identical two-run numerical outputs. These are concrete empirical instrumentation data, but they remain `evidence_eligible = false` with no claim IDs. Any scientific claim must come from separately preregistered experiments and blinded evaluation artifacts.
