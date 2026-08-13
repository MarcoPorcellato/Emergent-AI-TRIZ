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

The manifest records the chosen didactic model as a contract fact. The operational state is computed from the validated receipt chain, not trusted from the manifest alone.

## What Lab 01 is not

- not a TRIZ probe suite;
- not a steering benchmark;
- not a causal-tracing dashboard;
- not a quantization comparison;
- not a multi-model bake-off;
- not evidence for the Latent TRIZ Hypothesis.

## Validation boundary

Lab 01 now executes entirely from a local snapshot after acquisition. It validates eight fail-closed gates:

- G1 exact model identity, including repo, revision, config, weights, tokenizer, checksums, and license;
- G2 offline execution;
- G3 tokenization capture;
- G4 instrumentation invariance;
- G5 numerical health;
- G6 final lens parity;
- G7 repeated-run stability;
- G8 artifact integrity.

Structural prompt, token, and top-k records are byte-stable for the frozen environment. Numerical comparisons use the declared backend/dtype tolerances. Dense activations are never committed; public layer records contain only name, shape, dtype, health summaries, and hashes.

## Reproduce the published bundle

The complete setup, exact-revision acquisition or verification, resource-gated
model load, instrumentation run, and report rendering are available as one
command:

```bash
make lab01-bootstrap
```

The command defaults to
`artifacts/models/pythia-70m-deduped-e93a9faa`. Override
`LAB01_MODEL_ROOT` only when using another local location for the same frozen
snapshot. Model execution is supervised by the Commit CI Preflight host
resource guard and fails closed under unsafe memory pressure.

The sparse report and machine-readable records are written to `results/lab01/model-anatomy/`.

## Public status

The first public run passed G1-G8 for three frozen non-TRIZ prompts, six captured post-layer residuals per prompt, exact final-logit parity, and identical two-run numerical outputs. These are concrete empirical instrumentation data, but they remain `evidence_eligible = false` with no claim IDs. Any scientific claim must come from separately preregistered experiments and blinded evaluation artifacts.

The pinned revision and its Apache-2.0 model card were re-verified on
2026-08-13. The local six-file snapshot is complete and matches the frozen
SHA-256 allowlist. A new model load must still pass the host resource-admission
gate; local availability alone is not permission to run under memory pressure.
The tracked bundle records an earlier successful exact-snapshot run; the
current host-admission denial is therefore a fresh execution constraint, not a
retroactive change to that recorded result.
