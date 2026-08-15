---
type: Roadmap
title: Research Laboratory Roadmap
description: Delivered foundation and staged route to a complete, visual, falsifiable Latent TRIZ laboratory.
status: canonical
last_verified: 2026-08-14
---

# Roadmap

For the canonical long-form milestone sequence, see [Laboratory Master Plan](./LABORATORY_MASTER_PLAN.md).

The laboratory foundation is operational. Lab 00 is a deterministic synthetic process smoke. Lab 01 is the first real-model instrumentation result and remains explicitly ineligible as evidence for the hypothesis. Its model-backed representation extractor now provides the hash-verified bridge from frozen cases and real residual-stream activations to Lab 04.

This roadmap stays intentionally short. It records the current delivery shape and points to the master plan for the verified chronology, dependencies, exit gates, and deferred work.

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
Stage 1 also includes a dependency-free localhost annotation workbench for
blinded dataset labeling. It is designed for human judgment capture only and is
not itself evidence for the hypothesis.

- define pilot packet, response, annotation (0-4 dimensions), and summary contracts;
- define a blinded annotation workbench with sanitized case views, local-only
  append targets, and explicit non-evidence output metadata;
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

The annotation workbench sits underneath Lab 02 as an operational aid for
collecting blinded human labels. It exposes only the fields needed for case
judgment, hides labels and provenance from the rater view, and writes validated
annotations to `artifacts/annotations/dataset-annotations.jsonl`. Default entry
points are `make annotate` and `make annotate-serve`.

Wave 1 now also has a retained audit command for batch review of per-rater
files. `make wave1-annotation-audit ANNOTATION_FILES="path/rater1.jsonl
path/rater2.jsonl"` validates the guide revision and digest, checks exact case
coverage, enforces the agreement and abstention thresholds, and writes the
retained summary to `artifacts/annotations/wave1-audit.json`. The audit output
keeps disagreements and consensus records for later adjudication, but it
remains non-evidence and cannot advance a claim on its own.

Lab 03 is implemented as the next fail-closed surface-control boundary. Its
Wave 1 audit now covers four field-specific views, bag-of-words, character
n-gram, length/punctuation, leave-one-domain-out evaluation, and provenance
metadata classifiers. The current batch is rejected for freeze: several
surface classifiers exceed the shortcut threshold, provenance diversity is not
evaluable, and conventional sentence embeddings remain `not_run`. This is a
negative readiness result, not E1 evidence.

Lab 04 is now implemented as a deterministic decodability contract run target with strict no-leakage controls and fail-closed readiness:

- one-vs-rest ridge probes on the frozen unanimous label field,
- train-only standardization,
- outer leave-one-domain-out and inner domain-aware model selection,
- shared domain-blocked permutations with inner alpha reselection and max-statistic family-wise control across layers,
- a pure-Python reference solver plus a pinned NumPy augmented-least-squares backend for empirical-scale runs,
- strict non-claim boundary in the report output.

Lab 01 representation extraction now writes one externally stored Safetensors vector per case-layer, indexed by model, tokenizer, prompt, token-position and vector receipts. Lab 04 consumes that index directly and rejects unsafe paths or any container, tensor-key, metadata or vector-hash mismatch. The first two-case Pythia smoke is an engineering qualification only; it is not a scientific recognition result.

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

1. **Delivered:** close the integrity hotfix by enforcing every JSON Schema keyword used by the repository, cross-checking tracked artifacts against Draft 2020-12 `jsonschema`, and making case-level disagreement incompatible with freeze readiness.
2. **Delivered:** replace changing branch-policy exceptions with one stable, path- and risk-aware merge gate; restore pre-merge Python 3.11 coverage for code and require CCP plus scientific artifact checks where appropriate.
3. **In delivery:** amend the unused annotation ontology to v1.2 before real collection: score Segmentation and Inversion separately, require an identified alternative for `Other`, permit null operator scores for `Cannot determine`, expose guide examples, reset every form field after submission, and complete the three-expert cognitive-pilot gate.
4. **Delivered:** run [Phase A0](./A0_AUTOMATED_WEAK_HYPOTHESIS.md) as an
   independent automated proxy test. Protocol v1.0.3 was frozen before model
   output; PR 34 published the exact-revision positive exploratory result with
   p = 0.005, 24/24 paired-family successes, and macro-F1 margin 0.188234. It
   remains ineligible for expert-validated TRIZ claims.
5. Preserve Wave 1 unchanged as a `calibration_only`, known-leaky corpus. Its
   negative audit becomes a permanent regression fixture; it is not iteratively
   optimized into an EXP-001 dataset.
6. Challenge A0 through the separate
   [A0-R replication contract](./A0_REPLICATION_AND_ROBUSTNESS.md): first an
   independent procedural corpus with the cached exact model, then an
   independent model family only after acquisition approval. R1.2 and R1.3 are
   now frozen, merged, and verified. R1.4a is also merged with fixed
   runtime/input/code hash binding, fixed
   classifier/permutation/baseline/domain-statistic specification, and
   synthetic-adapter / synthetic-vector tests only. R1.4b is the live pre-run
   checkpoint; exact-model activation and sealed inference remain blocked until
   its runner binding is reviewed, qualified, and merged.
7. Build Wave 2 from label-free counterfactual problem families, with generator targets stored separately, source/generator/template provenance, and grouped splits that keep every problem family together.
8. Store independent raw ratings, adjudications, exclusions, and canonical human labels as separate immutable artifacts. Labs 03–05 consume canonical labels, never generator intent.
9. Add a common empirical envelope without rewriting v1 fixtures, and separate pre-freeze candidate surface auditing from post-freeze Lab 03.
10. Publish a real model-backed recognition smoke with problem-only and completed-solution views, multiple token sites, versioned index/summary receipts, external Safetensors, and no promoted claim.
11. Run EXP-001-R only after surface, provenance, annotation, grouped-split, and held-out-domain gates pass. Empirical Lab 05 and Lab 06 remain deferred until an out-of-sample direction is demonstrated.

The target milestone is a complete chain of label-free paired cases, independent
canonical human labels, no detected surface shortcut, exact model activations,
and held-out-domain decodability. Wave 2 validates the rules derived from Wave
1; a later sealed Wave 3 must remain untouched by audit or dataset development.

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
