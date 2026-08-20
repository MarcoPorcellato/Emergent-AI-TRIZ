---
type: contributor-quickstart
title: EXP-002 independent expert review quickstart
description: No-model instructions for producing one complete, blinded TRIZ review packet.
status: canonical
last_verified: 2026-08-20
---

# EXP-002 independent expert review quickstart

This guide is for one of the three independent TRIZ reviewers required by
EXP-002B. It produces a review packet only; it does not authorize model
execution, tokenizer access, sealed-target access, or CCP work.

## Scope and independence

Each reviewer must work independently under a distinct pseudonymous
`reviewer_id`. Reviewers must not see model outputs, sealed targets, another
reviewer's decisions, or copied answer text from the TRIZ source files. The
public question bank contains 351 records covering the 40 principles,
foundational concepts, Matrix direction, Panitz relationships, self-report,
and false-concept controls.

The review is a construct-validity and answer-key task, not a prediction task.
Use your TRIZ expertise and the public protocol; do not infer what a model
would answer.

## Required packet contract

Submit one JSON object with:

- `artifact_class`: `exp002-expert-review-packet`;
- a distinct 2–64 character pseudonymous `reviewer_id`;
- the exact `question_bank_sha256` from the manifest;
- `status: "submitted"`;
- `independence_attestation: true`;
- `model_access: false` and `sealed_target_access: false`;
- exactly one decision for every question ID;
- for every decision, a `rationale_sha256` over the reviewer's private rationale.

Allowed `key_type` values are:

- `exact`: include the expected answer in `answer`;
- `abstention`: include the justified abstention value in `answer`;
- `rubric_required`: use when a binary key would be scientifically unsafe;
- `non_evidential`: use when the item cannot support a factual key.

Every decision must also contain `decision: "reviewed"`. Do not add source
excerpts, model outputs, sealed labels, or private filesystem paths to the
public packet.

## Procedure

1. Read the frozen protocol and question-bank manifest.
2. Compute and record the manifest SHA-256; do not edit the manifest.
3. Review all 351 question IDs exactly once.
4. For each item, write a private rationale, hash it with SHA-256, and record
   only the digest in the packet. Keep the private rationale outside the public
   repository unless the operator separately approves its disclosure.
5. Run the packet validator locally before handoff. A packet with missing,
   duplicate, or extra IDs must be corrected rather than silently repaired.
6. Send the packet to the operator without sharing it with the other reviewers.

Useful no-model checks from the repository root:

```sh
shasum -a 256 experiments/exp002-qwen3-followup/question-bank-manifest.json
PYTHONPATH=src .venv/bin/python scripts/exp002_freeze_answer_key.py \
  --packets /path/to/three-independent-packets.json \
  --output results/exp002/preexecution/direct-answer-key.json
```

The freeze command must be run only after all three real packets are present.
It refuses incomplete coverage, duplicate reviewers, hash drift, missing exact
answers, and access-boundary violations. It does not load a model or open a
sealed target.

## What happens after handoff

The operator validates all three packets, preserves disagreement as
`rubric_required` under the frozen policy, and creates an immutable answer-key
artifact. Until that artifact exists, the EXP-002B dossier remains
`approval_requested` and `make exp002-stage-preflight` must continue to report
`approval_required`.

Do not fill missing packets with placeholders, synthetic reviewers, majority
guesses, or copied source text. If a question is unclear, use `rubric_required`
or `non_evidential` and explain the issue privately in the rationale.
