---
type: research-spec
title: A0 Automated Weak Hypothesis Exploration
description: Frozen-design contract for a fully automated, evidence-bounded proxy test before expert TRIZ validation.
status: proposed
last_verified: 2026-08-14
---

# A0 Automated Weak Hypothesis Exploration

This document is the canonical Phase A0 specification for the Latent TRIZ laboratory.
It defines a fully automatic, reproducible, evidence-bounded reconnaissance run for the
Weak Latent TRIZ Hypothesis.

A short persistent goal should reference this file as its scientific source of
truth:

> Execute Phase A0 exactly as specified in `docs/A0_AUTOMATED_WEAK_HYPOTHESIS.md`.

## Purpose

Phase A0 asks one narrow question:

Can we obtain preliminary empirical evidence that a real, exact-revision language model
contains a cross-domain decodable signal for automated procedural proxies of
Segmentation and Inversion, after frozen controls for leakage, provenance, and surface
shortcuts?

A0 is exploratory. It is useful if it produces either:

- a well-controlled positive signal, or
- a well-documented negative or non-interpretable outcome that constrains the next study.

## Non-goals

A0 must not:

- claim validation of TRIZ constructs by experts;
- replace the H1 cognitive pilot;
- replace Wave 2;
- depend on an interactive local model-serving application;
- use an LLM judge as ground truth;
- promote TRIZ claims;
- widen into a new horizontal lab;
- mutate the protocol after seeing sealed evaluation results;
- use exploratory heuristics as if they were confirmatory evidence.

## Epistemic envelope

A0 operates under a strict contract:

```json
{
  "artifact_class": "automated-operator-proxy-exploration",
  "empirical": true,
  "scientific_status": "exploratory",
  "evidence_eligible": false,
  "expert_validated": false,
  "claim_ids": []
}
```

Interpretation rule:

- A positive A0 result may only support the statement that a model contains a
  decodable signal for the automated operator proxies used in A0, beyond the controls
  that passed the freeze.
- A negative A0 result only falsifies the frozen A0 setup, not the broader Weak Latent
  TRIZ Hypothesis.
- Any leakage or shortcut failure is a dataset/protocol failure, not a model result.

## Exact scope and ownership

Work only inside the A0 run substrate and its documentation outputs.

Canonical artifacts for A0 live under the existing repository roles:

- `experiments/a0-automated-weak-proxy/` for the frozen protocol and config;
- `data/a0/` for label-free calibration and sealed case artifacts;
- `data/a0/procedural-targets/` for targets that must never be embedded in cases;
- `results/a0/<run_id>/` for immutable summaries, reports, and receipts;
- `artifacts/a0/<run_id>/` for dense or locally generated assets excluded from Git.

The exact directory names used by the implementation must be listed in the manifest and
kept immutable for the sealed run.

## Scientific dependencies

A0 is independent from H1 and Wave 2.

Required ordering:

1. A0 protocol freeze
2. A0 corpus build
3. A0 leakage audit
4. A0 calibration
5. A0 sealed evaluation
6. A0 publication

H1 remains a separate human gate. Wave 2 remains a separate dataset and cannot be
backfilled from A0.

## Staged firebreaks

### A0.1 — Plan registration

Add A0 to the laboratory plan as a parallel exploratory branch that can run before H1.
The plan must state that:

- A0 does not unblock Wave 2;
- A0 does not substitute for expert validation;
- Wave 1 stays calibration-only and known-leaky;
- A0 is a new exploratory route, not a revision of prior claims.

### A0.2 — Protocol freeze

Before any result is observed, freeze:

- operator proxy definitions;
- generator rules;
- domain list and problem families;
- seeds and splits;
- model revision and tokenizer revision;
- views and token sites;
- metrics and thresholds;
- negative controls;
- permutation budget;
- exclusion rules;
- success, null, and non-interpretable criteria.

The freeze must produce a signed or hashed manifest.

### A0.3 — Deterministic counterfactual corpus

Build a label-free corpus of counterfactual problem families where the shared elements are
held constant:

- base problem;
- domain;
- constraints;
- desired improvement;
- worsening consequence.

Only the transformation changes.

Use two operator proxy families:

- segmentation-like proxies: decomposition, partitioning, distribution;
- inversion-like proxies: order reversal, direction reversal, role reversal, dependency
  reversal.

Requirements:

- no TRIZ terminology in the cases or prompts;
- no explicit label leakage in generator templates;
- each case has a `problem_family_id`;
- each solution variant has a `solution_variant_id`;
- generator provenance, template provenance, license, seed, and version are recorded;
- target labels remain separate from the surfaced case text;
- split assignment is grouped by family;
- calibration and sealed evaluation use disjoint partitions;
- duplicates and near-duplicates are rejected before freeze.

The corpus must be reproducible from the manifest and deterministic generation rules.

### A0.4 — Leakage and shortcut gate

Before extracting activations, run automatic anti-shortcut checks.
At minimum:

- bag-of-words baselines;
- character n-gram baselines;
- length and punctuation baselines;
- style and template baselines;
- provenance classifiers;
- problem-only label prediction;
- leave-one-domain-out surface evaluation;
- duplicate and near-duplicate detection;
- family leakage detection;
- random-label controls;
- random-partition controls;
- generic action taxonomy controls;
- generic transformation taxonomy controls;
- adjacent-principle proxy controls.

If any shortcut gate exceeds the frozen threshold, the A0 run must stop and publish the
failure as a protocol failure.

### A0.5 — Power and calibration simulation

Before the sealed run, simulate:

- null signal;
- known positive signal across multiple effect sizes;
- lexical confound only;
- domain confound only;
- template confound only;
- false-positive rate;
- power;
- minimum detectable effect;
- sample size;
- permutation budget.

The sealed A0 sample size and permutation budget must be derived from these simulations,
not from smoke fixtures.

### A0.6 — Exact-model activation extraction

Use a real model revision that is verified live before the run.

Requirements:

- exact model revision recorded;
- exact tokenizer revision recorded;
- environment receipt recorded;
- integrity and residual-parity checks recorded;
- run directory is immutable after write;
- atomic writes only;
- no interactive local model-serving application;
- no unverified model substitution.

Extract at least these views when the implementation supports them:

- `problem_only`
- `transformation_only`
- `problem_plus_transformation`
- `problem_plus_solution`
- stable sentinel token view
- final transformation token view
- mean transformation span view
- a preregistered set of layers

### A0.7 — Statistical analysis

Run only pre-registered analyses.

Required analysis family:

- regularized linear probes;
- grouped leave-one-domain-out evaluation;
- grouped split by problem family;
- train-only preprocessing;
- shared label permutations;
- max-statistic correction across layers and token sites;
- baseline comparison against surface controls;
- paired representation-difference checks;
- stability checks across domains, paraphrases, views, and token sites;
- sensitivity analysis and uncertainty intervals.

Do not reselect the best layer, token site, or view after seeing the sealed result unless
that rule was frozen before evaluation.

### A0.8 — Public result package

The run must produce a single command UX, preferably:

```bash
make a0
```

or an equivalent canonical wrapper documented in the repository.

The command must create or verify:

- corpus manifest;
- protocol freeze manifest;
- leakage report;
- calibration report;
- model and environment receipts;
- representation index;
- statistical result;
- compact human summary;
- HTML report;
- machine-readable limitations;
- artifact hashes;
- fresh-clone instructions;
- final status: positive, null, failed, or non-interpretable.

Dense assets should not be committed directly into Git if a release or archival asset is
the better publication channel. Git should hold indexes, summaries, manifests, and hashes.

## Deterministic corpus design

The corpus must be built from immutable generation rules.

Recommended case schema fields:

- `case_id`
- `problem_family_id`
- `solution_variant_id`
- `domain`
- `problem`
- `constraints`
- `initial_state`
- `desired_improvement`
- `worsening_consequence`
- `transformation`
- `resulting_state`
- `provenance`
- `seed`
- `template_id`
- `license`
- `split`

The generator should keep the case text label-free and reserve the operator target for the
sealed metadata. Human-readable case text must not expose the proxy label or the desired
classification.

The separate procedural-target record should contain only identifiers and the
by-construction target, for example `case_id`, `problem_family_id`,
`solution_variant_id`, `operator_proxy_family`, generator rule, and hashes.

## Calibration versus sealed evaluation

A0 must separate:

- calibration data, used to estimate leakage and power;
- sealed evaluation data, used once for the frozen result.

Rules:

- calibration may inform thresholds and sample size before the freeze;
- sealed evaluation may not change thresholds, prompts, or sample selection;
- any post hoc redesign requires a new versioned protocol and a new sealed set.

## Exact-model activations

The implementation must record, at minimum:

- model name and revision;
- tokenizer name and revision;
- device and environment receipt;
- hash of the model artifact if available;
- hash of the activation export;
- shape, dtype, and batch metadata;
- extraction command;
- run timestamp;
- exact input manifest.

If the model cannot be verified exactly, the run must stop and report the blocker.

## Multi-view and token-site analysis

A0 should examine multiple representation views without improvising after the fact.

Suggested views:

- problem only
- transformation only
- problem plus transformation
- problem plus solution
- sentinel view
- transformation boundary token
- last transformation token

Suggested token-site treatment:

- preregister the token sites to inspect;
- keep token-site selection fixed across calibration and sealed evaluation;
- use max-statistic correction across sites and layers.

## Grouped statistical plan

The statistical plan must be grouped and family-safe.

Minimum requirements:

- group splits by `problem_family_id`;
- avoid leakage across families;
- use cross-validation or holdout splits that preserve family grouping;
- report permutation-based nulls;
- report correction across layers and token sites;
- report uncertainty intervals;
- report effect sizes alongside p-values;
- report all negative controls.

If the problem-only baseline is too strong, the run is not interpretable as a
representation result.

## One-command UX

The canonical user-facing workflow should be discoverable through one command.

Expected behavior:

- generate or verify all A0 artifacts;
- write outputs to the dedicated A0 run area;
- render a compact report;
- fail closed if any freeze, leakage, or receipt condition is missing;
- avoid re-running the sealed analysis implicitly after a failure.

The command name may be `make a0` or a documented equivalent, but it must remain stable
once published.

## Immutable publication contract

A0 publication must preserve immutability:

- manifests and summaries are versioned;
- run directories are write-once;
- hashes are recorded for inputs and outputs;
- the sealed result is not overwritten;
- a fresh clone can reproduce the published path from the documented artifacts.

Publication outputs should distinguish:

- engineering readiness;
- calibration quality;
- leak-free status;
- sealed result;
- interpretation.

## Claim interpretation

Allowed interpretation after a positive result:

> The model contains a decodable signal for the automated operator proxies used in A0,
> after the specified leakage and shortcut controls.

Disallowed interpretation:

> The model has validated TRIZ Segmentation or Inversion as expert-defined constructs.

A null result does not falsify the broader Weak Latent TRIZ Hypothesis. It only constrains
the frozen A0 setup.

## GitHub, CCP, and merge gates

A0 follows the repository’s existing qualification policy.

Minimum gates:

- exact repository base verified before work;
- clean or explicitly preserved worktree state;
- relevant tests and receipts terminally green before merge;
- ruleset and merge-policy gate re-read at qualification time;
- exact-head CCP or equivalent project gate where required by repository policy;
- no unresolved review threads for the published branch;
- no promotion from exploratory A0 to hypothesis claim without the documented gate.

Before any official local guarded qualification, apply the installed
[`macos-v3` resource-admission contract](./reference/commit-ci-preflight.md#installed-macos-v3-resource-admission).
Run both JSON status probes and start the runner only on `Admit` with no active
or queued run. `Unknown` or `Deny` stops the attempt.

If the repository policy requires a stronger gate than this document, the repository policy
wins.

## Delegation and cost policy

Use the cheapest reliable tool first.

Recommended order:

1. deterministic shell tools and repository scripts;
2. bounded local checks;
3. cheaper LLM lanes for mechanical or bounded work;
4. primary agent only for scientific framing, integration, and final interpretation.

Rules:

- keep prompts lean and task-specific;
- delegate only bounded work;
- do not ask cheaper lanes to rediscover the whole protocol;
- do not use LLMs as truth sources for labels or ground truth;
- do not use an interactive local model-serving application;
- stop a delegated attempt after one clear failure and escalate if needed.

## Agent execution interface

The long scientific and delivery contract stays in this file. Do not duplicate
it in the persistent goal or in `AGENTS.md`.

Use the execution agent in this order:

1. start with a planning step so the agent verifies live repository state and decomposes the
   current milestone before editing;
2. load a concise persistent goal that names this file, the intended outcome,
   the non-negotiable boundaries, and the completion check;
3. use `AGENTS.md` only for durable repository-wide operating instructions, not
   for this phase-specific scientific specification;
4. delegate independent exploration, tests, and documentation to bounded
   subagents, while keeping overlapping writes serialized;
5. require the agent to report the exact commands and terminal validation results.

Keep phase-specific contracts in this file, durable repository-wide rules in
the repository instruction file, and bounded worker assignments in task-local
prompts.

## Human approval boundaries

Human approval is required for:

- expert substitution;
- H1-style validation;
- any claim that the A0 proxy has become TRIZ-validated;
- external publication steps that change repository or release state;
- downloads or installations not already authorized by the repo policy;
- credentialed or paid external services;
- destructive operations;
- any protocol revision after the sealed evaluation result.

## Recovery and handoff rules

If A0 is interrupted, the next agent must be able to resume from:

- the frozen protocol manifest;
- the corpus manifest;
- the leakage report;
- the calibration report;
- the model and environment receipts;
- the sealed evaluation record;
- the final result summary.

Every milestone handoff should report:

- what completed;
- what was frozen;
- what evidence exists;
- what remains blocked;
- whether the current state is pre-freeze, frozen, sealed, or published.

## Completion checklist

A0 is complete only when all of the following are true:

- the protocol was frozen before the sealed run;
- the corpus is label-free and reproducible;
- calibration and sealed evaluation are separate;
- leakage and provenance gates are recorded;
- power simulation justifies the sealed design;
- activations were extracted from a real exact-revision model;
- the statistical run is terminal and reproducible;
- the result, even if null or failed, is published with explicit limits;
- the one-command UX works as documented;
- the Lab Suite or equivalent status surface shows A0 without upgrading it to expert TRIZ evidence;
- the repository can reproduce the path from hashes and manifests alone;
- H1 and Wave 2 remain independent and untouched.

## Status note

The A0 foundation is in delivery with a proposed adaptive protocol, strict
schemas, a deterministic label-free corpus generator, and a bounded
`a0-corpus` command. These artifacts are engineering readiness only: no
protocol freeze, sealed corpus access, activation extraction, statistic, or
result has occurred.

This document remains `proposed` until the protocol freeze is executed and recorded.
After freeze, update only the status and the corresponding run manifests; do not rewrite the
scientific contract based on the observed result.
