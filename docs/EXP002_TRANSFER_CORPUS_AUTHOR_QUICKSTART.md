---
type: contributor-quickstart
title: EXP-002C independent transfer-corpus quickstart
description: No-model handoff for independently authoring and auditing the blinded transfer corpus.
status: canonical
last_verified: 2026-08-20
---

# EXP-002C independent transfer-corpus quickstart

This guide is for independent authors and auditors of the new blinded-transfer
corpus. It does not authorize model loading, generation, tokenizer access,
sealed-target access, or CCP work.

## Corpus boundary

The corpus must be new and independent of EXP-001. The primary problem and
candidate descriptions must not contain TRIZ names, principle numbers,
canonical examples, Matrix cells, Panitz tool names, or source excerpts. Keep
expert labels and author/generator intent outside the public corpus; the public
records use sealed logical locators for those fields.

The frozen design requires at least eight domains (preferably 10–12), at least
two independent families per domain, and multiple independently authored
replicates. The power receipt fixes the domain count before any model access.

## Record contract

Each record must contain:

- a unique `case_id` matching `^exp002c-`;
- `domain`, `family_id`, and `replicate_id`;
- one of `discovery`, `validation`, `held_out_domain`, or `sealed_novel`;
- a neutral `problem` and exactly four candidate descriptions;
- `option_order: [0, 1, 2, 3]` before any diagnostic permutation;
- one of the declared exposure modes: `blinded_primary`, `lexical_control`,
  `generic_heuristic`, or `common_sense_control`;
- distinct `author_id`, `generator_intent_locator`, and
  `expert_label_locator` values;
- `source_proximity_status: "pass"` only after the independent audit.

The primary response surface is label-free candidate-description scoring. Do
not add answer labels or target values to the public fixture.

## Required controls and audit

Include the preregistered lexical/length-matched non-TRIZ controls, generic
transformation heuristics, adjacent-principle confusions, random labels or
shuffled solutions, option-order permutations, common-sense controls, and at
least one vocabulary-shifted domain. Audit near duplicates and source
proximity before freeze. Do not select domains or examples after inspecting
any model output.

Validate an authored draft from the repository root:

```sh
PYTHONPATH=src .venv/bin/python scripts/exp002_validate_transfer_corpus.py \
  --corpus /path/to/transfer-corpus.json
```

An empty design template is intentionally reported as pending. A frozen corpus
must contain records, pass the independence/source-proximity checks, satisfy
the eight-domain power receipt, and remain target-free. The validator rejects
EXP-001 reuse, TRIZ/source leakage, duplicate fingerprints, and shared
expert/generator locators.

## Freeze handoff

Send the validated corpus and its provenance/audit notes to the operator. The
operator creates the sealed target key only after the corpus is independently
reviewed and the source-proximity gate passes. Until then,
`transfer-target-key-template.json` must remain `not_ready` with no records and
no target-content hash.

Do not fabricate expert labels, reuse a public answer key, or mark a draft
`frozen_no_model` merely because its JSON schema is valid. A structurally valid
but unaudited corpus is not evidence and cannot authorize EXP-002C.
