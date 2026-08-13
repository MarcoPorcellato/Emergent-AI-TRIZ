---
type: Roadmap
title: Research Laboratory Roadmap
description: Delivered foundation and staged route to a complete, visual, falsifiable Latent TRIZ laboratory.
status: canonical
last_verified: 2026-08-13
---

# Roadmap

The laboratory foundation is operational. Lab 00 is a deterministic synthetic process smoke. Lab 01 is the first real-model instrumentation result and remains explicitly ineligible as evidence for the hypothesis.

The maintained Lab 00 through Lab 05 artifacts now have a single local visual entrance. `make lab` opens the dashboard and `make lab-render` produces the same deterministic page for headless use. The dashboard is a navigation and integrity surface; it does not recompute experiments or promote scientific claims.

## Foundation — delivered

Completed or maintained in this repository:

- define the repository map and claim boundaries;
- define the case schema;
- define preregistration and results conventions;
- define contribution rules for provenance and leakage control;
- validate repository-owned artifacts with dependency-free CI.
- maintain an E0-E6 claim registry and promotion policy;
- use Commit CI Preflight receipts to avoid unnecessary GitHub Actions runs.

## Stage 1 — protocol path operational, dataset assembly in progress

In progress:

- collect or synthesize cross-domain cases;
- assign multi-label principle annotations;
- document provenance and licensing;
- freeze a dataset snapshot before confirmatory evaluation.

Stage 1 now includes a blinded two-arm pilot contract for reproducible process smoke.
These artifacts are not confirmatory evidence.

- define pilot packet, response, annotation (0-4 dimensions), and summary contracts;
- add schema-level and optional smoke validation for Stage 1 artifacts;
- add explicit documentation gates that Stage 1 smoke artifacts are not evidence.

### Lab 00 - public smoke view

Delivered, infrastructure-only, and not attached to any scientific claim:

- render the tracked synthetic Stage 1 smoke artifacts as a one-command visual report;
- reuse the frozen packet, response, annotation, and summary files;
- show the non-empirical boundary prominently in the output;
- avoid any model, representation, or empirical claim;
- keep the dependency-free validation core separate from the optional visual surface.

`make lab00` reproduces the frozen smoke, renders its responsive local HTML report, and opens it through the operating system. `make lab00-render` provides the same deterministic Lab 00 output for headless environments; `make lab` opens the combined Lab 00–05 dashboard.

## Model-backed laboratory sequence

Lab 01 establishes the trustworthy measurement substrate. Later labs may add scientific complexity only after their predecessor gates pass:

1. **Lab 01 — Model anatomy:** exact identity, offline load, tokens, masks, positions, residual stream, norms, logit lens, final-logit parity, repeat stability, and artifact integrity.
2. **Lab 02 — Dataset anatomy:** provenance, leakage, balance, frozen splits, and annotation reliability.
3. **Lab 03 — Behavioral baselines:** lexical and shallow controls before representation claims.
4. **Lab 04 — Decodability:** linear probes with label permutation and cross-domain transfer.
5. **Lab 05 — Candidate directions:** contrastive directions with norm-matched controls.
6. **Lab 06 — Causal intervention:** steering, ablation, dose response, and capability preservation.
7. **Lab 07 — Mechanism localization:** sparse features and activation patching where justified.
8. **Lab 08 — Replication:** independent model families, datasets, implementations, or teams.

Lab 02 is now implemented against the synthetic Stage 1 fixture. Its first report intentionally records the corpus as not release-ready because split/domain/principle targets and independent-rater coverage remain open. This is a readiness result, not evidence for or against the hypothesis.

Lab 03 is implemented as the next fail-closed surface-control boundary. It renders deterministic local diagnostics while refusing behavioral interpretation until Lab 02 passes, label/domain support is adequate, every required baseline family is present, and leave-one-domain-out plus random-label controls are complete. Its synthetic fixture output is a readiness result, not E1 evidence.

Lab 04 is now implemented as a deterministic decodability contract run target with strict no-leakage controls and fail-closed readiness:

- one-vs-rest ridge probes on the frozen unanimous label field,
- train-only standardization,
- outer leave-one-domain-out and inner domain-aware model selection,
- deterministic training-label permutation control with Holm-corrected layer adjustment,
- strict non-claim boundary in the report output.

Lab 05 is implemented as deterministic, fail-closed candidate-direction instrumentation. It computes `mean(segmentation) - mean(inversion)` per layer, compares it with norm-matched seeded random controls and unrelated-label controls, and publishes only hashes, norms, and projections. The current fixture intentionally remains `fail`: Lab 04 is not scientifically ready and the dataset has insufficient label/domain support. No dense direction, intervention, steering claim, or causal claim is published.

The interface should remain optional so that the dependency-free validation core stays lightweight. A concrete model, revision, interpretability library, and sparse-feature resource will be selected only after their current availability, license, and hardware requirements are independently verified.

## EXP-001 — proposed Segmentation pilot

The first model-backed experiment is proposed, not preregistered or executed. It is now explicitly separated into three non-interchangeable questions:

1. **Recognition** - whether operator labels are cross-domain decodable from problem-plus-solution representations.
2. **Pre-output selection** - whether problem-only activations predict the operator expressed by a later generation.
3. **Causal control** - whether steering and ablation change operator-consistent generation while preserving general capability.

Recognition alone cannot promote a claim about operator selection or causal use.

The proposed design includes:

- primary operator: TRIZ Segmentation;
- negative/operator control: Inversion;
- four substantially different domains;
- approximately 120 exploratory cases before any confirmatory freeze;
- lexical, matched-negative, random-direction, label-permutation, and domain-transfer controls;
- blinded evaluation with a versioned annotation guide;
- explicit model and dataset commitments sealed before confirmatory runs.

The provisional model roles are now recorded in [ADR 0003](./decisions/0003-exp-001-model-selection.md): Gemma 3 270M pretrained is the primary mechanistic candidate because an official Gemma Scope 2 suite covers it, while SmolLM2 360M pretrained is the independent architecture replication candidate under Apache 2.0. This selects the study design, not permission to download models or freeze the preregistration. Exact feasibility and licensing must be rechecked at acquisition time.

The repository now exposes two offline readiness gates for that decision: `make model-preflight` checks the exact candidate manifest and `make dataset-audit` checks the development corpus against the current plan. Both are deterministic, no-download gates. The freeze step remains separate and must still be backed by operator receipts, local hashes, and an immutable run record.

### Evidence profiles

The public E0-E6 ladder remains the concise communication layer. Before claim promotion, each result will also carry a machine-readable evidence profile covering behavioral effect, lexical controls, cross-domain transfer, decodability, positive and negative interventions, dose response, capability preservation, independent/cross-model replication, and controlled training. The ladder level will be derived from satisfied profile fields rather than used as the sole description of evidence.

### Immediate sequence

1. Finish evidence-integrity and readiness gates, including evaluator-safe exports and rater coverage.
2. Apply a ruleset to `main` with pull-request and verified-check requirements.
3. Publish and preserve Lab 01 with a didactic model role distinct from the primary and replication roles.
4. Define the Segmentation/Inversion annotation ontology and freeze criteria.
5. Execute recognition, selection, and causal-control experiments as separate claim paths.

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
