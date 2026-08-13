---
type: decision-record
title: ADR 0004 — Lab 01 didactic model anatomy
description: Define the public, vendor-neutral contract for Lab 01 around a single didactic model and explicit receipt-gated states.
status: active
last_verified: 2026-08-13
---

# ADR 0004 — Lab 01 didactic model anatomy

## Status

Accepted

## Context

Lab 01 is a public, model-instrumentation laboratory. It is not a TRIZ claim engine, a probe benchmark, a steering dashboard, a Jacobian study, or a multi-model comparison suite.

The lab needs a single didactic model contract that can be verified offline before any acquisition or execution. The contract must preserve a strict boundary between:

- structural artifacts that can be checked byte-for-byte;
- numerical artifacts that may vary by backend or dtype within declared tolerances;
- receipts that authorize state transitions;
- empirical outputs that remain claim-ineligible unless separately registered.

## Decision

1. Define the didactic model for Lab 01 as `EleutherAI/pythia-70m-deduped` pinned to revision `e93a9faa9c77e5d09219f6c868bfc7a1bd65593c`.
2. Record the model as Apache-2.0 licensed, with its model-card and source URLs preserved in the manifest and receipt chain.
3. Use the following receipt-derived state machine:
   `unselected -> selected -> acquisition_planned -> acquired -> integrity_verified -> load_verified -> instrumentation_verified -> lab_ready`.
4. Treat the manifest state as a contract fact only; the operational state is computed from the validated receipt chain.
5. Require every Lab 01 manifest and receipt to classify itself as empirical, but not evidence-eligible.
6. Keep `claim_ids` empty for the Lab 01 contracts in this repository.
7. Keep the observable scope didactic and frozen: no TRIZ naming, no probes, no steering, no SAE/Jacobian analysis, no dashboard semantics, and no quantization or multi-model branching in this contract.

## Gates

The contract exposes the following gate sequence:

- G1: model identity is fixed, including repo, revision, config, weights, tokenizer, checksums, and license;
- G2: offline execution is verified;
- G3: tokenization capture is verified;
- G4: instrumentation invariance is verified;
- G5: numerical health is verified;
- G6: final lens parity is verified;
- G7: repeated-run stability is verified;
- G8: artifact integrity is verified.

G1 through G8 are contract gates. They are not scientific claims.

## Consequences

- The repository can now express a single-model, receipt-gated Lab 01 path without conflating it with EXP-001.
- Future operational receipts can promote the state machine without rewriting the contract.
- If a later lab needs probes, steering, causal tracing, or replication, it must define those as separate contracts.
- Availability and license were re-verified on 2026-08-13 at the exact pinned
  Hugging Face revision. The model card identifies Apache-2.0 and the local
  snapshot matches the six frozen file hashes.
