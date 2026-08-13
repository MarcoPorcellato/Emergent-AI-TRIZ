---
type: ResearchProtocol
title: Latent TRIZ Research Protocol
description: Experimental tracks, controls, evidence criteria, and reproducibility requirements for testing the hypothesis.
status: canonical
last_verified: 2026-08-12
---

# Research protocol

## 1. Research questions

### Recognition track

Do pretrained open models contain representations that predict the use of a TRIZ-like inventive transformation across domains and participate causally in generating that transformation?

### Controlled-emergence track

Can a model trained from scratch on problem, constraint, transformation, and outcome sequences develop the same domain-general operator without exposure to TRIZ terminology, definitions, labels, or canonical examples?

## 2. Unit of analysis

A case contains a constrained problem, initial state, desired improvement, worsening consequence or contradiction, candidate transformation, resulting state, domain, one or more independently assigned principle labels, lexical-control metadata, near misses, and alternative solutions that resolve a similar contradiction through other operators.

TRIZ principles are not assumed to be mutually exclusive. Labels and predictions are multi-label, and inter-rater disagreement is part of the data.

The canonical field names are defined by [`../schemas/case.schema.json`](../schemas/case.schema.json). Its core record includes:

- `case_id`
- `domain`
- `problem`
- `constraints`
- `initial_state`
- `desired_improvement`
- `worsening_consequence`
- `transformation`
- `resulting_state`
- `labels`
- `lexical_controls`
- `near_miss_case_ids`
- `alternative_solution_case_ids`
- `provenance`

The `labels` array preserves multiple expert assignments, annotator identifiers, rationales, and per-label confidence instead of forcing a single class.

## 2.1 Blinded annotation workbench

The repository includes a local annotation workbench for blinded human labeling
of dataset cases. It is an operational aid, not evidence. The workbench must:

- run only on localhost;
- present sanitized case fields only;
- hide labels, provenance, split metadata, lexical controls, related-case IDs,
  and allocation or outcome details from the rater view;
- accept only the curated ontology choices for this stage, currently
  Segmentation and Inversion;
- capture a confidence value and rationale for each judgment;
- persist abstentions explicitly so undecidable cases remain visible in coverage;
- append validated records to `artifacts/annotations/dataset-annotations.jsonl`;
- mark human annotation records with `non_empirical = false` because they are
  judgment metadata, not hypothesis evidence;
- reject any attempt to turn the workbench into an evidence surface.

Wave 1 also has a retained audit path for comparing per-rater files after
collection:

```text
make wave1-annotation-audit ANNOTATION_FILES="path/rater1.jsonl path/rater2.jsonl"
```

The audit checks schema validity, the exact guide revision and digest, full
case coverage, at least two distinct raters, pairwise exact percent agreement
greater than or equal to 0.8, and abstention rate less than or equal to 0.2.
It writes the retained summary to `artifacts/annotations/wave1-audit.json` and
keeps disagreements, consensus results, and digests for later adjudication. The
result is empirical human judgment metadata, but it remains
`evidence_eligible = false` with `claim_ids = []`. `ready_for_adjudication` may
be true while the freeze remains false. Independence is a procedural control,
not identity proof.
Aggregate agreement never overrides a case-level conflict: each freeze-ready
case requires a unanimous substantive label. Disagreements and unanimous
abstentions therefore remain explicit adjudication work.

Default entry points are `make annotate` for the interactive browser flow and
`make annotate-serve` for headless or externally controlled use.

## 3. Dataset design

The initial study should use a preregistered subset of relatively distinguishable principles. Each principle must appear across multiple domains, while surface words, templates, authorship, and source collections are balanced or controlled.

Required splits:

- discovery/training;
- within-domain validation;
- leave-one-domain-out evaluation;
- lexical adversarial controls;
- near-miss and alternative-principle controls; and
- a sealed novel-case set written after the discovery set is frozen.

The annotation workbench supports this freeze path by collecting blinded human
labels before any confirmatory use. The output remains non-evidence until it is
incorporated into a preregistered and versioned dataset snapshot.

Leakage analysis must cover explicit principle names, synonyms, canonical examples, source duplicates, paraphrases, and recognizable source templates.

### 3.1 Wave 1 candidate batch

Wave 1 is a discovery-only candidate batch for Segmentation and Inversion review.

Current batch facts:

- 24 cases total;
- 12 Segmentation and 12 Inversion cases;
- 4 domains: manufacturing, packaging, software operations, and healthcare devices;
- 3 or more cases per principle per domain;
- reciprocal opposite-label pairs are required by the manifest;
- the surface text must not contain the target lexical cues;
- the batch is fully model-generated, non-empirical, and not frozen;
- the batch is not evidence-eligible and cannot support confirmatory claims.

Acceptance path before this batch can contribute to a frozen dataset:

1. two independent raters annotate the batch blindly;
2. abstentions are allowed and must be retained;
3. agreement is assessed against the versioned guide and annotation policy;
4. provenance is expanded beyond model-generated material to include human-authored, adapted, and historical sources;
5. a split freeze is defined and checked for leakage across discovery, validation, held-out-domain, and sealed-novel partitions;
6. the frozen dataset must satisfy the source-policy cap and the required split counts before confirmatory use.

## 4. Model tracks

### Track A: pretrained open models

Begin with Gemma 3 270M as an inspection testbed, then scale to larger Gemma checkpoints and independently trained families such as Qwen where feasible. Base and instruction-tuned variants are reported separately. A negative result on the smallest model does not by itself falsify the general hypothesis.

### Track B: controlled models

Train a small Transformer on a fully inspectable corpus. Exclude TRIZ language and canonical examples. Hold out selected domain-operator combinations to test compositional generalization. Freeze corpus generation rules, training data, and evaluation data before final analysis.

## 5. Stage 1: Build a cross-domain dataset

The first stage is shared across both tracks, with track-specific inclusion constraints:

- Track A: include a preregistered multi-domain corpus with explicit lexical confounds.
- Track B: include only synthetic/curated non-TRIZ data and withheld domain combinations.

For each principle candidate, include multiple independent annotations and explicit `desired_improvement` and `worsening_consequence` fields.

## 6. Stage 2: Establish surface-level baselines

Before internal analyses, confirm how much of principle classification can be achieved from surface information.

Required baselines:

- bag-of-words classification
- conventional sentence embeddings
- topic classification
- keyword matching
- output-only LLM classification
- random-label controls

If shallow approaches perform too well, treat that as evidence of leakage and revise the dataset before confirmatory representation analysis.

## 7. Stage 3: Map internal representations

For each case and solution, collect residual-stream activations across layers.

Candidate analyses include linear and nonlinear probes, contrastive activation differences, representational similarity, dimensionality-reduction checks, sparse-feature analysis, layer-wise readouts, activation patching, causal tracing, and Jacobian-lens follow-up.

Dimensionality-reduction plots are exploratory visualizations, not proof of a latent operator. Probe performance remains correlational until interventions produce behavior change.

Key criterion: leave-one-domain-out performance should remain above baseline and not degrade to lexical shortcuts.

## 8. Stage 4: Perform causal steering

For a candidate direction `v` and activation `h`, interventions use:

```text
h' = h + alpha * v
```

with positive and negative strengths, including zero.

Controls:

- norm-matched random vectors
- unrelated-principle vectors
- semantically related but non-inventive vectors
- lexical and stylistic vectors
- layer and token-position controls
- activation replacement from another example
- ablation or projection removal
- controls matched for fluency degradation

The outcome is expert-rated transformation use, not target-word probability. A successful intervention should redirect solution strategy without requiring principle names in the prompt or output.

Track A and Track B report desired steering effect and opposite/ablation effect separately.

## 9. Stage 5: Test composition

After replication of single-operator effects, test pairwise and small sets of interventions.

For candidate operators `v_i` and `v_j`:

```text
h' = h + alpha * v_i + beta * v_j
```

A valid compositional effect is one in which the combined intervention yields a solution pattern consistent with both target transformations and is more informative than single-vector and random-vector baselines.

Interpretation does not assume orthogonality. Overlapping subspaces, sparse-feature combinations, nonlinear manifolds, context dependence, or families of related vectors are all allowed.

## 10. Stage 6: Replicate across models

Any convincing result must be replicated across:

- multiple problem domains
- base and instruction-tuned models
- model sizes and families
- independently generated test sets
- different prompts
- independent feature-discovery methods
- evaluator groups

Track-specific replication requirements:

- Track A: replicate across open checkpoints.
- Track B: replicate across independent controlled training runs and held-out domains.

## 11. Evaluation

Blinded judges should rate:

- whether the solution resolves the contradiction;
- principle or combination of principles used;
- feasibility;
- novelty;
- constraint adherence;
- whether the response only repeats principle terminology.

Preregister primary outcomes, exclusion rules, sample sizes, intervention layers, steering strengths or selection rules, statistical tests, multiple-comparison correction, and success thresholds before opening the sealed evaluation set.

For Wave 1 discovery work, the only acceptable use is workflow validation, cue auditing, and guide calibration. It is not acceptable to cite Wave 1 as empirical support for the Latent TRIZ Hypothesis, for operator prevalence, or for downstream model performance.

## 12. Interpretation rules

### Strong supporting evidence

Support requires converging cross-domain, lexical-control, causal, bidirectional, novel-case, compositionality, cross-model, and controlled-emergence results.

### Weakening or falsifying evidence

The hypothesis is weakened if effects disappear under vocabulary controls, remain domain-specific, alter terminology only, collapse to generic creativity, damage fluency, require explicit prompting, resist ablation, or fail independent replication.

### Claim boundary

A positive result supports reusable internal problem transformations, not consciousness, subjective experience, or a complete theory of inventive cognition.

## 13. Reproducibility record

Each run must retain model name and immutable revision, tokenizer, code commit, data snapshot, prompts, seeds, precision, device, environment, layer and token positions, intervention definition, output hashes, evaluator protocol, exclusions, and analysis version.
