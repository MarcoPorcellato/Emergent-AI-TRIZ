---
type: evidence-policy
title: Evidence Ladder
description: Canonical E0-E6 claim levels and promotion requirements for Latent TRIZ.
status: canonical
last_verified: 2026-08-13
---

# Evidence Ladder

The Evidence Ladder prevents infrastructure, exploratory observations, and attractive visualizations from being reported as discoveries. Every public scientific claim has a machine-readable entry in [`data/claims.jsonl`](../data/claims.jsonl), validated by [`schemas/claim.schema.json`](../schemas/claim.schema.json).

## Levels

| Level | Name | Required evidence |
|---|---|---|
| E0 | Hypothesis | A precise statement, model scope, falsification condition, and untested status. |
| E1 | Behavioral observation | `behavioral_effect` |
| E2 | Cross-domain decodability | `behavioral_effect`, `lexical_controls`, `cross_domain`, `decodable` |
| E3 | Causal steering | E2 + `positive_causal_intervention`, `dose_response`, `capability_preserved` |
| E4 | Bidirectional causality | E3 + `negative_causal_intervention` |
| E5 | Cross-model replication | E4 + `independent_replication`, `cross_model_replication` |
| E6 | Controlled emergence | E5 + `controlled_training` |

Levels are cumulative proof obligations, not a generic maturity score. E6 does not waive E1-E5 controls.
Evidence level is a *summary* of satisfied obligations for the claim, and `evidence_profile` axes capture specific capabilities independently.
The evidence axes are multi-dimensional and are not assumed to be linear or equivalent to one another; a claim may satisfy additional axes while still not advancing evidence level.
A claim may declare a level only when all cumulative minimum required axes for that level are true.

## Promotion rules

1. Register or update the claim before inspecting confirmatory outcomes.
2. Freeze the preregistration, dataset snapshot, study manifest, code revision, model revision, and seeds.
3. Keep exploratory artifacts labeled and outside the confirmatory result chain.
4. Attach immutable run and result references to the claim entry.
5. Record failures, weakened claims, and null results; never overwrite earlier results.
6. Require blinded evaluation where the protocol calls for human judgment.
7. Promote only to the highest level fully supported by the attached artifacts.

An E0 entry must be `untested`, have empty evidence links, and set `non_empirical` to `true`. Passing repository tests or the Stage 1 synthetic smoke does not promote a claim.

Lab 00 presentation surfaces are infrastructure-only, are not attached to scientific claims, and must not be represented as evidence.

## Claim lifecycle

Claims can be `untested`, `in-progress`, `preliminary`, `supported`, `weakened`, `falsified`, or `retracted`. Status and evidence level answer different questions: status records the present interpretation, while the level records the strongest completed evidence class.

Any promotion PR must state the contribution lane, explain the level transition, link every required artifact, and identify the falsification criterion that was evaluated.
