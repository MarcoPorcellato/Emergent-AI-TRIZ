# Stage 1 blinded pilot preregistration

## Status and claim boundary

- Study ID: `stage1-pilot-001`
- Version: `0.1.0`
- Status: designed; not yet externally registered or executed
- Track: Track A, output-only precursor
- Stage: Stage 1 dataset and protocol qualification
- Created at: `2026-08-12T10:00:00Z`

This document freezes the proposed pilot design before real model responses are
collected. The tracked two-case bundle under `data/pilot/` is synthetic process
smoke only. It is excluded from every scientific analysis and supplies no
evidence for or against the Latent TRIZ hypothesis.

## Research question

Without naming TRIZ, its principles, or canonical examples, does a structured
contradiction-focused elicitation increase the use of transferable inventive
transformations relative to a generic problem-solving prompt?

## Hypotheses

### Weak hypothesis tested by this pilot

Across held-out problem domains, treatment responses will receive higher
blinded ratings than control responses on `contradiction_resolution` and
`principle_use`, without a corresponding increase in `terminology_only`.

This is an output-level signal only. Even a positive result would not establish
an internal representation, causal mechanism, or rediscovery of TRIZ.

### Strong hypothesis not tested by this pilot

A model trained without TRIZ exposure can develop domain-general internal
operators that are causally involved in producing the same transformation
families. Testing that claim requires the controlled-training, representation,
intervention, ablation, and replication stages defined in the research
protocol. Stage 1 can only establish whether the later test is operationally
viable.

## Conditions

Each case receives both conditions using the same immutable model revision,
decoding settings, and output budget.

- `control`: a generic request for a feasible solution that respects all stated
  constraints.
- `treatment`: a TRIZ-name-free request to identify the central trade-off,
  consider available resources and an ideal outcome, and propose a concrete
  transformation.

Neither prompt may contain `TRIZ`, principle names, canonical examples, or
instructions to imitate a named inventive method.

## Pilot sample

The real non-confirmatory pilot requires at least:

- 24 original cases;
- at least four domains, with at least six cases per domain;
- two responses per case, one per condition, for at least 48 responses;
- two independent blinded raters per response.

The size is a feasibility threshold, not a power calculation. No confirmatory
claim may be made from this pilot.

## Blinding and randomization

- Packet construction uses an explicit recorded seed.
- Conditions are exposed to evaluators only as `A` and `B`.
- The `arms_by_blind` key is retained separately from evaluator-facing exports.
- Response order is randomized before annotation.
- Raters receive neither hypotheses nor condition descriptions.
- Unblinding occurs only after exclusions and ratings are frozen.

## Outcomes

Primary outcomes are within-case treatment-minus-control differences in:

- `contradiction_resolution`;
- `principle_use`.

Secondary outcomes are paired differences in:

- `feasibility`;
- `novelty`;
- `constraint_adherence`;
- `terminology_only`, treated as a leakage/label-repetition diagnostic.

Every dimension uses the integer scale 0–4 defined by the annotation schema.
The pilot reports per-arm means, paired differences, counts, missingness, and
inter-rater agreement. It does not perform confirmatory significance testing.

## Exclusions

Exclude before unblinding:

- malformed or schema-invalid records;
- missing condition pairs or incomplete rater coverage;
- model/provider errors or truncated responses;
- duplicate cases or responses;
- cases containing a forbidden term, principle name, canonical example, or
  identifiable copied source template;
- responses that expose their condition label through orchestration metadata.

All exclusions and their reasons remain in a versioned ledger. Excluded records
are never silently replaced.

## Leakage checks

Before collection, scan cases and prompts for explicit TRIZ vocabulary,
principle synonyms, canonical examples, source duplicates, paraphrases, and
domain-template artifacts. After collection, report `terminology_only`
separately and inspect whether condition classification is possible from prompt
or formatting artifacts alone.

## Stopping and decision rules

Stop the run if schema validation, fingerprints, blinding, exact model revision,
or paired coverage cannot be verified. Do not repair a frozen run in place.

Progress to a larger preregistered study only if:

- all 24 cases and 48 response slots are accounted for;
- at least 90% of non-excluded responses receive two complete ratings;
- no unresolved condition leakage remains;
- the pipeline reproduces identical packet and summary bytes from the same
  inputs and seed; and
- rater disagreement is reported and judged operationally manageable.

A positive mean difference is not a progression requirement and must not be
optimized during this pilot.

## Reproducibility record

Freeze the repository commit, dataset fingerprint, prompt text, seed, model
name/family/revision, tokenizer where applicable, decoding parameters, provider
or execution environment, response timestamps, rater protocol, exclusions,
and scorer version. Provider credentials and personal information must never be
stored in repository artifacts.
