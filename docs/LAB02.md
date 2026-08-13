---
type: runbook
title: Lab 02 dataset anatomy
description: One-command visual audit of dataset provenance, immutability, leakage, balance, and annotation readiness.
status: active
last_verified: 2026-08-13
---

# Lab 02 dataset anatomy

Lab 02 turns the dataset-release boundary into an observable, fail-closed artifact. It does not test whether a TRIZ-like representation exists. The current inputs are synthetic process fixtures, so every output remains `empirical = false`, `evidence_eligible = false`, and unattached to claim IDs.

## Run

```bash
make lab02
```

The command needs no model, service, API key, or optional dependency. It writes a responsive report and machine-readable records to `results/lab02/dataset-anatomy/`.

## Gates

- **D1 — contract:** the audit and snapshot payloads are structurally coherent and correctly classified.
- **D2 — provenance and license:** every case has a stable source, date, source type, and license consistent with the registry.
- **D3 — artifact integrity:** cases, annotations, registry entry, and registry manifest carry SHA-256 and size receipts.
- **D4 — immutable splits:** exact split membership has a stable digest.
- **D5 — leakage:** duplicate content, source reuse, and template reuse across splits are absent.
- **D6 — balance:** preregistered split, domain, and principle minima are met.
- **D7 — annotation reliability:** every case meets rater coverage and the declared exact-agreement floor.
- **D8 — evidence boundary:** the report remains synthetic, non-empirical, claim-ineligible, and hash-backed.

## Interpreting the current report

A red readiness gate is useful data, not a software failure. The current two-case smoke corpus is expected to expose open balance and independent-annotation gaps. The command exits successfully when the audit executes and records those gaps; malformed inputs, broken contracts, or unverifiable artifacts still fail closed.

No dataset becomes eligible for a claim merely because Lab 02 renders successfully. A release-grade snapshot must pass every gate and then be linked from a separately frozen study manifest and preregistration.
