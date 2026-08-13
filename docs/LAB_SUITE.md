---
type: lab-suite-runbook
title: Local Visual Laboratory Suite
description: One-command visual index for the maintained Lab 00 through Lab 05 artifacts and their scientific boundaries.
status: canonical
last_verified: 2026-08-13
---

# Local Visual Laboratory Suite

The laboratory suite is the public local entrance to the maintained Latent TRIZ artifacts. It provides one page for navigating Lab 00 through Lab 05 while keeping each artifact's scientific status explicit.

## Run it

From a fresh clone with Python 3.11 or newer:

```bash
make lab
```

This validates the deterministic Stage 1 smoke chain, renders Lab 00, builds `artifacts/lab/index.html`, and opens the suite in the default browser. The headless equivalent is:

```bash
make lab-render
```

Neither command downloads or loads a model. The suite reads the versioned reports already tracked in the repository and verifies their classification boundary before linking them.

## What the suite shows

- Lab 00: synthetic blinded-process smoke;
- Lab 01: exact-revision real-model instrumentation;
- Lab 02: synthetic dataset-readiness audit;
- Lab 03: synthetic behavioral-control readiness;
- Lab 04: synthetic decodability-contract readiness;
- Lab 05: descriptive candidate-direction readiness with no dense-vector publication.

Each card exposes its status, empirical classification, claim eligibility, source fingerprint, and detailed report. A red `fail` status means a scientific readiness gate is intentionally not satisfied; it does not mean that the dashboard failed to execute.

## Scientific boundary

The dashboard is a navigation and integrity surface, not an experiment. It never promotes a claim, never assigns an Evidence Ladder level, and refuses to render a maintained result that is evidence-eligible or attached to a claim ID.

Lab 01 is empirical model instrumentation but remains claim-ineligible. The current Lab 00 and Lab 02–05 fixtures are synthetic, descriptive, or process-only and must not be interpreted as evidence for or against the Latent TRIZ Hypothesis.

## Reproducing individual laboratories

The suite does not replace the individual run targets:

```bash
make lab00
make lab02
make lab03
make lab04
make lab05
```

Lab 01 has a separate exact-model acquisition and resource-admission boundary documented in [Lab 01 model anatomy](./LAB01.md). Running or refreshing a detailed experiment remains separate from viewing its tracked result.
