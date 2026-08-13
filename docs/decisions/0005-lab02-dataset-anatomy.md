---
type: decision-record
title: ADR 0005 — Lab 02 dataset anatomy
description: Establish a hash-backed dataset release boundary before behavioral or representation experiments.
status: active
last_verified: 2026-08-13
---

# ADR 0005 — Lab 02 dataset anatomy

## Status

Accepted for implementation.

## Decision

The laboratory will not treat a mutable JSONL collection as an experimental dataset. Lab 02 introduces a dedicated snapshot manifest that binds cases, dataset annotations, the selected registry entry, the complete registry, and exact split membership.

Release readiness is evaluated independently across provenance/licensing, integrity, leakage, balance, and annotation reliability. The agreement statistic is deliberately transparent exact pairwise label agreement; more sophisticated reliability statistics belong in a preregistered empirical analysis and must not be inferred from the synthetic smoke fixture.

The current Stage 1 fixture remains synthetic and claim-ineligible. Its expected gaps are published rather than hidden or automatically repaired.

## Consequences

- byte changes and split reassignment invalidate the snapshot;
- source/template reuse can be detected across splits;
- registry and case licenses must agree;
- cases without sufficient independent annotations remain not ready;
- Lab 03 cannot claim a behavioral baseline against an unfrozen dataset;
- null, mixed, and negative readiness results remain versioned artifacts.
