---
type: research-specification
title: Weak and Strong Latent TRIZ Hypotheses
description: Falsification contract and evidence profile for operator-level latent TRIZ research.
status: draft_preregistration
version: 0.1.0
last_verified: 2026-08-19
---

# Weak and Strong Latent TRIZ Hypotheses

This document is the construct-validity companion to the laboratory master
plan. It does not amend A0, A0-R, or the published EXP-001 packages. It defines
what would count as progress toward the hypothesis and what would falsify each
route.

## 1. Hypotheses

### Weak Latent TRIZ (WLT)

At least one abstract inventive operator has a model-internal representation
that is decodable above preregistered controls, transfers to held-out domains,
and is not explained by lexical, template, source, or domain shortcuts.

The operator is a functional proxy until independent TRIZ experts validate that
the labeled behavior corresponds to the intended construct. A WLT result must
therefore report both the automated proxy and the human construct label.

### Strong Latent TRIZ (SLT)

A model trained from scratch on problem-solution data that contains no TRIZ
terminology, source wording, canonical examples, matrix cells, or tool-map
edges develops a functionally equivalent operator representation that transfers
to unseen domains and supports a preregistered causal intervention.

SLT is a controlled-emergence hypothesis. Pretrained-model results, source-
exposed retrieval, and post-hoc model prompting cannot establish it.

## 2. Epistemic boundaries

- A0/R1 positive packages are exploratory automated-proxy observations (E0).
- The seven-model comparative null packages are published negative evidence for
  that frozen reference-task protocol; they do not falsify WLT as a construct
  because expert labels and causal tests are still absent.
- Source-exposed competence is never pooled with blinded transfer.
- A decodable direction is not evidence of causal use.
- No claim may be promoted until the corresponding human, causal, replication,
  and controlled-training obligations are attached to the claim registry.

### Current interpretation of the published record

| Record | What it supports | What it cannot support |
|---|---|---|
| A0/R1 positive packages | exploratory decodability of frozen procedural proxies | expert-validated TRIZ, causal use, or Strong Latent TRIZ |
| Seven-model comparative nulls | no robust transfer signal for that frozen reference-task primary across the tested families | falsification of WLT as a construct, because the human label and causal gates are open |
| R3 reference-integrated package | a bounded exploratory test of blinded versus source-exposed reference tasks | rediscovery: source exposure is competence/retrieval and is never pooled with blinded transfer |

This table is a guard against two symmetrical errors: promoting an automated
proxy because it is positive, or declaring the construct impossible because a
single frozen proxy family is null. A WLT decision requires the expert,
held-out, control, and causal prerequisites below; an SLT decision additionally
requires controlled from-scratch training and independent seed evidence.

## 3. Preregistered falsification rules

Thresholds, sample sizes, and seeds must be frozen by a reviewable protocol and
power calibration before the relevant output is inspected. The following rules
define the decision logic, not post-hoc numerical values.

### WLT falsification

WLT is `null` for an operator when the frozen primary fails after all of these
conditions are met:

1. independent expert labels reach the preregistered agreement floor;
2. the held-out-domain primary is evaluated on grouped families;
3. lexical, template, source, domain, near-neighbour, generic-transformation,
   and random-label controls are available;
4. the preregistered multiplicity and permutation procedure is applied once;
5. no model family or domain meets the preregistered transfer and direction
   criteria.

The result is `non_interpretable`, rather than `null`, when labels, controls,
or runtime integrity are insufficient. A positive automated proxy without
expert agreement remains `exploratory_proxy_only`.

For planning purposes, the minimum positive WLT profile is therefore:
`expert_agreement_pass && held_out_transfer_pass && surface_controls_pass &&
decodability_pass && causal_gate_pending_or_passed`. The final conjunct is
deliberately not treated as optional for a promoted claim: before causal
testing, the package may be described only as a construct-validated
recognition signal, never as causal use or rediscovery. A failed primary cannot
be rescued by a sensitivity endpoint, a source-exposed arm, a near-threshold
model, or a post-hoc change of operator.

### SLT falsification

SLT is `null` for a controlled training protocol when, after the training data,
model family, checkpoints, and analysis are frozen:

- no unseen-domain operator signal exceeds the matched shuffled-solution and
  generic-transformation controls;
- no preregistered causal intervention changes the target behavior with dose
  response while preserving capability controls; or
- the signal appears equally in a non-inventive or lexical-matched control
  corpus.

Failure to reproduce across independent seeds is published as a robustness
failure, not silently pooled into a positive result. Any data contamination,
label leakage, or checkpoint-selection ambiguity produces `non_interpretable`.

## 4. Evidence profile

Every future claim package must record these axes independently:

| Axis | Required question |
|---|---|
| construct | Did independent experts validate the operator label? |
| surface | Do lexical/template/source controls pass? |
| transfer | Does the effect survive held-out domains and families? |
| decodability | Is the representation above the frozen null? |
| causality | Do steering, ablation, dose, and opposite-sign controls pass? |
| capability | Is the target effect preserved without broad capability loss? |
| composition | Does a two-operator or contradiction task behave predictably? |
| replication | Does an independent model, dataset, seed, or team reproduce it? |
| emergence | Does it arise in a controlled from-scratch model? |

The E0-E6 ladder remains cumulative. An evidence profile may contain positive
axes without permitting a level promotion when an earlier obligation is absent.

## 5. Required controls

Future WLT and SLT protocols must include, as applicable:

- adjacent principles and semantically similar non-principle operators;
- cosmetic and generic transformations;
- lexical- and length-matched prompts;
- source-exposed versus source-blinded strata scored separately;
- Matrix direction swaps and non-recommendation cells;
- unsupported Panitz edges and correct abstention;
- family-grouped held-out domains;
- shuffled solutions, random labels, random directions, and norm-matched vectors;
- capability-preservation tasks for every causal intervention.

## 6. Ordered gates

1. **H1 construct pilot:** three independent TRIZ experts, blinded cases,
   independent ratings, agreement and adjudication receipts.
2. **W2 canonical labels:** label-free paired corpus and sealed canonical
   labels, physically separate from generator intent.
3. **WLT decodability:** one preregistered operator, held-out domains, all
   controls, and no source exposure in the primary arm.
4. **Causal pilot:** one expert-validated operator, frozen direction, steering,
   ablation, dose-response, opposite-sign and capability controls.
5. **Composition:** contradiction and two-operator tasks only after the single
   operator causal gate passes.
6. **SLT Track B:** controlled from-scratch training with independent seeds and
   checkpoints; no pretrained result may select the corpus or checkpoint.

Every gate publishes `positive`, `null`, `failed`, and
`non_interpretable` outcomes. No retry after model or target access is allowed
without a new frozen dossier and explicit authorization.

## 7. Completion condition

The research program may claim progress toward latent TRIZ only when the
relevant evidence profile is complete and the claim registry links immutable
inputs, expert labels, controls, model/runtime receipts, statistical results,
causal packages, and replication or controlled-training evidence. Until then,
all statements remain exploratory and claim-free.
