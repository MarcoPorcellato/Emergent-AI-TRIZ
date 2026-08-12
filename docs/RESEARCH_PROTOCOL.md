# Research protocol

## 1. Research questions

### Recognition track

Do pretrained open models contain representations that predict the use of a TRIZ-like inventive transformation across domains and participate causally in generating that transformation?

### Controlled-emergence track

Can a model trained from scratch on problem, constraint, transformation, and outcome sequences develop the same domain-general operator without exposure to TRIZ terminology, definitions, labels, or canonical examples?

## 2. Unit of analysis

A case contains a constrained problem, initial state, candidate transformation, resulting state, domains, one or more independently assigned principle labels, lexical-control metadata, near misses, and alternative solutions that resolve a similar contradiction through other operators.

TRIZ principles are not assumed to be mutually exclusive. Labels and predictions are multi-label, and inter-rater disagreement is part of the data.

## 3. Dataset design

The initial study should use a preregistered subset of relatively distinguishable principles. Each principle must appear across multiple domains, while surface words, templates, authorship, and source collections are balanced or controlled.

Required splits:

- discovery/training;
- within-domain validation;
- leave-one-domain-out evaluation;
- lexical adversarial controls;
- near-miss and alternative-principle controls; and
- a sealed novel-case set written after the discovery set is frozen.

Leakage analysis must cover explicit principle names, synonyms, canonical examples, source duplicates, paraphrases, and recognizable source templates.

## 4. Model tracks

### Track A: pretrained open models

Begin with models small enough for full layer-wise activation capture, then replicate across sizes and independently trained families. Base and instruction-tuned variants must be reported separately.

### Track B: controlled models

Train a small Transformer on a fully inspectable corpus. Exclude TRIZ language and canonical examples. Hold out selected domain-operator combinations to test compositional generalization. Freeze corpus generation rules, training data, and evaluation data before final analysis.

## 5. Representation mapping

Candidate analyses include linear and nonlinear probes, contrastive activation differences, representational similarity, sparse-feature analysis, layer-wise readouts, activation patching, and causal tracing.

Dimensionality-reduction plots are exploratory visualizations, not proof of a latent operator. Probe performance is correlational until an intervention changes behavior specifically and reproducibly.

## 6. Causal interventions

For a candidate direction `v` and activation `h`, evaluate interventions of the form:

```text
h' = h + alpha * v
```

Use multiple positive and negative strengths, including zero. Compare against:

- norm-matched random vectors;
- unrelated-principle vectors;
- lexical and stylistic vectors;
- layer and token-position controls;
- activation ablation or projection removal; and
- interventions matched for fluency degradation.

The outcome is expert-rated transformation use, not target-word probability. A successful intervention should redirect the solution strategy without requiring principle names in the prompt or output.

## 7. Composition

After single-operator replication, preregister pairwise interventions such as Segmentation plus Dynamics. Test whether combined interventions create independently judged solutions using both operators and whether the effect exceeds single-vector and random-vector baselines.

Do not assume operators are orthogonal. Candidate representations may be overlapping directions, sparse feature combinations, nonlinear manifolds, context-dependent circuits, or families of related vectors.

## 8. Evaluation

Blinded judges should rate:

- whether the solution resolves the contradiction;
- principle or combination of principles used;
- feasibility;
- novelty;
- constraint adherence; and
- whether the response only repeats principle terminology.

Preregister primary outcomes, exclusion rules, sample sizes, intervention layers, steering strengths or selection rules, statistical tests, multiple-comparison correction, and success thresholds before opening the sealed evaluation set.

## 9. Interpretation rules

### Strong supporting evidence

Support requires converging cross-domain, lexical-control, causal, bidirectional, novel-case, cross-model, and controlled-emergence results.

### Weakening or falsifying evidence

The hypothesis is weakened if effects disappear under vocabulary controls, remain domain-specific, only alter terminology, collapse to generic creativity or compliance, damage fluency, require explicit prompting, appear only after instruction tuning, resist ablation, or fail replication.

### Claim boundary

A positive result would support the existence of reusable internal problem transformations. It would not by itself establish consciousness, subjective experience, human-identical understanding, or a complete theory of inventive cognition.

## 10. Reproducibility record

Every run must retain model name and immutable revision, tokenizer, code commit, data snapshot, prompts, seeds, precision, device, environment, layer and token positions, intervention definition, output hashes, evaluator protocol, exclusions, and analysis version.

