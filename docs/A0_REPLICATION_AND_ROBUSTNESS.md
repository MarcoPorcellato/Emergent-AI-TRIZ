---
type: research-spec
title: A0 Replication and Robustness
description: Preregistered route for challenging the published A0 automated-proxy signal on independent procedural data and model families.
status: in_delivery
last_verified: 2026-08-15
---

# A0 Replication and Robustness

This document defines A0-R, the next automated experiment after the published
A0 result. It is subordinate to the
[Laboratory Master Plan](./LABORATORY_MASTER_PLAN.md). It creates a new
experiment and must never rewrite protocol `a0-automated-weak-proxy-v1.0.3`,
run `a0-v1.0.3-e93a9faa`, or their result package.

## Purpose and falsifiable outcome

A0-R asks whether the A0 decodable signal survives independent procedural data
generation and, if later authorized, an independent model family.

The first replication is successful only if a protocol frozen before model
output:

- passes every leakage, provenance, duplicate, family, and surface-shortcut
  gate;
- reproduces the direction of the preregistered A0 primary effect on an
  independently generated corpus;
- exceeds its frozen effect-size and paired-family thresholds;
- passes a shared permutation test with adequate p-value resolution;
- shows positive held-out-domain direction in the frozen minimum number of
  domains;
- publishes the same immutable evidence package for positive, null, failed, or
  non-interpretable outcomes.

A null result constrains robustness of the automated proxy observation. A
failed or non-interpretable result diagnoses the replication substrate. None of
the outcomes validates a TRIZ construct.

## Authoritative starting anchor

- repository: `MarcoPorcellato/Latent-TRIZ`;
- published A0 merge: `fc80976d3a256ed88e2d59f1a6f893e15154e3a0`;
- published A0 protocol: `a0-automated-weak-proxy-v1.0.3`;
- published A0 run: `a0-v1.0.3-e93a9faa`;
- published result: `positive`, maximum-statistic p = 0.005, 24/24
  paired-family successes, macro-F1 margin = 0.188234;
- claim registry: all claims remain E0.

These anchors are last-known facts, not permission to skip live verification.
Every delivery task must re-read `origin/main`, the active ruleset, the exact
model receipt, and the current resource-admission contract.

## Epistemic envelope

Every A0-R empirical artifact must retain:

```json
{
  "empirical": true,
  "scientific_status": "exploratory",
  "evidence_eligible": false,
  "expert_validated": false,
  "claim_ids": []
}
```

Allowed interpretation after successful same-model replication:

> The published automated-proxy signal reproduced on an independently
> generated procedural corpus for the exact model revision tested.

Disallowed interpretations include model rediscovery of TRIZ, expert validity
of Segmentation or Inversion, causal use, spontaneous pre-output selection, or
cross-model generality.

## Scope and non-goals

Inside scope:

- an independent procedural-corpus generator and manifest;
- new templates, seeds, case identifiers, and sealed targets;
- pre-output power, shortcut, and p-resolution calibration;
- same-model exact-revision replication using the already cached A0 model;
- a later cross-model replication only after explicit acquisition and hardware
  approval;
- immutable positive, null, failed, and non-interpretable publication paths.

Outside scope:

- changing or rerunning the published A0 result in place;
- using A0 cases, sealed targets, or observed errors to tune A0-R cases;
- expert substitution or synthetic completion of H1;
- Wave 2, canonical human labels, EXP-001-R, Lab 05 direction claims, or Lab 06
  causality;
- claim promotion;
- post-output changes to thresholds, sites, layers, exclusions, or stopping
  rules;
- interactive model-serving applications or LLM judges as ground truth.

## Replication tiers

### Tier R1 — independent corpus, same exact model

R1 is the immediate automated milestone and requires no new model acquisition.

- Generate entirely new problem families from versioned rules that do not
  reuse A0 case text, role pairs, template identifiers, or seeds.
- Keep procedural targets physically separate from surfaced case text.
- Freeze calibration and sealed partitions before activation extraction.
- Use `EleutherAI/pythia-70m-deduped` at exact revision
  `e93a9faa9c77e5d09219f6c868bfc7a1bd65593c` only if its runtime-file hashes
  match the published receipt.
- Treat the previously observed layer 6 mean-transformation-span combination as
  the replication primary endpoint. Other frozen layers, token sites, and views
  are sensitivity analyses and cannot replace a failed primary endpoint.
- Compare `problem_plus_transformation` against the problem-only surface
  baseline with family-grouped leave-one-domain-out evaluation and train-only
  preprocessing.

### Tier R2 — independent model family

R2 starts only after R1 is terminal and after explicit approval for downloads,
licenses, disk, RAM, and runtime cost.

- Freeze model and tokenizer identity before acquisition.
- Do not choose the model from observed A0-R performance.
- Repeat the same primary representation contract where architecture permits;
  record any unavoidable mapping as a preregistered compatibility decision.
- Publish incompatibility or null performance without substituting another
  model post hoc.

R2 is still automated-proxy replication, not E5 claim replication, because the
underlying constructs remain unvalidated by experts.

## Ordered milestones and exit evidence

### R1.1 — replication protocol and independence audit

**Exit evidence:** a machine-readable protocol, independence manifest, explicit
A0 exclusion hashes, status vocabulary, primary endpoint, sensitivity family,
and positive/null/failed/non-interpretable rules are frozen before model output.

**Current checkpoint — in delivery:** the planned protocol instance and its
strict Draft 2020-12 schema now fix the same-model primary endpoint, statistical
thresholds, epistemic envelope, and immutable A0 anchors. A separate
fail-closed independence auditor compares candidate and A0 manifests, case
files, calibration targets, and sealed targets without joining those physical
target files. This checkpoint is not a protocol freeze: the independent corpus,
its manifest-derived hashes, the audit report, and calibration evidence still
have to be generated and reviewed before `protocol_status` may become `frozen`.

### R1.2 — deterministic corpus and shortcut gate

**Exit evidence:** reproducible case and target files, disjoint calibration and
sealed partitions, no identifier or text overlap with A0, grouped families, and
terminal records for at least the full A0 14-control suite.

### R1.3 — power and permutation freeze

**Exit evidence:** simulations report false-positive rate, power, minimum
detectable effect, sample size, family threshold, domain-direction threshold,
and a permutation budget with p-value resolution no weaker than A0. Calibration
may select these values once; sealed output cannot change them.

### R1.4 — exact-model activations and sealed inference

**Exit evidence:** exact runtime-file hashes match the published model receipt;
the activation export, index, environment, protocol, corpus, sealed-target, and
code hashes link end to end; the primary endpoint runs once under the guarded
resource contract.

### R1.5 — immutable publication

**Exit evidence:** one command creates or verifies the result, report,
limitations, receipts, indexes, and hashes; a fresh clone plus declared external
assets can verify the package; repository tests, artifact audit, exact-head CCP
when required, hosted aggregate, and review-thread gates are terminally green.

### R2 — cross-model replication

**Dependency:** R1 is published and the user has approved the selected model
acquisition and material resource use.

**Exit evidence:** a separate frozen model-selection decision, exact acquisition
receipt, architecture mapping, sealed run, and immutable result package.

## Statistical and missing-data rules

- The R1 primary endpoint is fixed from A0 and is not selected from R1 output.
- Families, not individual cases, are the resampling and split unit.
- Shared permutations preserve the frozen grouping and multiplicity contract.
- Surface, provenance, generic-action, adjacent-proxy, random-label, and
  random-partition controls remain mandatory.
- Missing, stale, mismatched, or inconclusive identity and integrity evidence is
  a failure, never a pass.
- Any shortcut gate at or above its frozen refusal threshold makes the run
  non-interpretable rather than negative evidence about the model.
- Domain results, uncertainty intervals, effect sizes, and all sensitivity
  outcomes are published even when the primary rule fails.

## Delegation and cost policy

Use deterministic tools first. Delegate independent inventory, documentation,
mechanical implementation, focused tests, and log distillation to the cheapest
suitable bounded worker. Keep protocol architecture, independence judgments,
statistics, epistemic interpretation, security, qualification, and merge
authorization with the primary agent. Assign one owner per file group and stop
a low-cost attempt after one failed try and one focused correction.

## Approval boundaries

Human approval is required for:

- any R2 model download or material hardware use;
- paid or credentialed services;
- destructive cleanup;
- external releases or archives beyond normal repository pull-request delivery;
- changing a frozen A0-R protocol after sealed output;
- any assertion that an automated target has become expert-validated TRIZ.

Normal isolated worktrees, branches, commits, pull requests, exact-head
qualification, and merges remain authorized within the repository workflow.

## Interruption and recovery

At every interruption record repository, worktree, branch, exact HEAD and base,
dirty state, active workers and runners, completed terminal checks, unproven
gates, remote branch/PR state, external asset hashes, and the exact resume
command. A temporary path without a saved branch or commit is not a checkpoint.

## Completion checklist

R1 is complete only when:

- the replication protocol and primary endpoint were frozen before output;
- every A0 input and target is excluded by hash and provenance;
- the new corpus is deterministic, label-free, grouped, and partitioned;
- shortcut and independence gates are terminal;
- calibration justifies sample size, thresholds, and permutation resolution;
- exact cached-model identity is reverified;
- the sealed primary endpoint is run once and classified without post hoc
  replacement;
- every result class has an immutable public package;
- the one-command verification path works;
- exact-head repository and hosted gates pass;
- A0 remains byte-stable;
- all claim IDs remain absent and H1/Wave 2 remain untouched.

R2 is complete only after its separate acquisition approval, frozen model
decision, exact receipts, sealed run, immutable publication, and the same
no-claim boundary are all proven.
