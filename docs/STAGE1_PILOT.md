---
type: stage1-pilot
title: Stage 1 Blinded Pilot
description: Vendor-neutral two-arm pilot packet, response, annotation, and summary records.
status: active
last_verified: 2026-08-12
---

# Stage 1 blinded pilot

This scope standardizes the Stage 1 pilot artifact workflow. The tracked bundle
is **non-empirical process smoke only**; the same contracts can later carry a
real non-confirmatory pilot after its dataset, model revision, and rater plan
are frozen.

## Contracted records

- `schemas/pilot-packet.schema.json`
- `schemas/pilot-response.schema.json`
- `schemas/pilot-annotation.schema.json`
- `schemas/pilot-summary.schema.json`

## Blinded pilot record contract

Packet records are one object per JSONL line with required fields:

- `packet_id`
- `case_id`
- `pair_id`
- `arms_by_blind` with keys `A` and `B`
- `blind_order` containing `["A","B"]` in the deterministic arm order
- `seed`
- `source`

Response records are one object per JSONL line with required fields:

- `response_id`
- `packet_id`
- `blinded_arm`
- `model.name`, `model.family`, `model.revision`
- `response_text`
- `generated_at` (UTC timestamp)
- `non_empirical`

Annotation records are one object per JSONL line with required fields:

- `annotation_id`
- `response_id`
- `packet_id`
- `blinded_arm`
- `rater_id`
- `scores`
- `annotated_at` (UTC timestamp)
- `non_empirical`

`scores` uses exactly six dimensions:

- `contradiction_resolution`
- `principle_use`
- `feasibility`
- `novelty`
- `constraint_adherence`
- `terminology_only`

Each score is an integer from `0` to `4`.

Summary is a JSON object with:

- `schema_version`
- `non_empirical`
- `dimensions`
- `counts`
- `per_arm_means`
- `paired_deltas`
- `provenance` with sha256-prefixed fingerprints

## Workflow

1. Prepare blinded packets from `data/pilot/cases.jsonl` with seed `20260812`.
2. Run the generic `control` prompt and the contradiction-focused,
   TRIZ-name-free `treatment` prompt using the self-contained case fields in
   each packet.
3. Store responses with blinded arm labels `A` and `B`; keep the arm key away
   from evaluators.
4. Annotate responses with all six pilot score dimensions.
5. Score to one summary object.
6. Validate all artifacts against the four Stage 1 schemas.

## Deterministic smoke command

```text
make stage1-pilot-smoke
```

The smoke command performs deterministic comparison against tracked artifacts:

- `data/pilot/packets.jsonl`
- `data/pilot/responses.jsonl`
- `data/pilot/annotations.jsonl`
- `data/pilot/summary.json`

It does not infer discovery claims and does not add inferential evidence.

## Evidence boundary

- The tracked two-case bundle is process smoke for reproducible protocol checks.
- Outputs and comparisons are not evidence for confirmatory claims.
- If `non_empirical` is false in any tracked artifact, the run is rejected by the stage-1 boundary checks.
- A real Stage 1 pilot remains non-confirmatory and must follow the frozen
  preregistration, minimum sample, blinding, exclusion, and provenance rules.
- Confirmatory evidence requires dedicated later-stage instrumentation and governance gates.
