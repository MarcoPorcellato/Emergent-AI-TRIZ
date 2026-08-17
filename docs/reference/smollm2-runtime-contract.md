---
type: runtime-contract
title: SmolLM2 Runtime Contract
description: Executable compatibility requirements for the exact A0-R2 SmolLM2 snapshot.
status: canonical
last_verified: 2026-08-17
---

# SmolLM2 Runtime Contract

This document turns the public API and model documentation for the exact
A0-R2 snapshot into fail-closed local requirements. It is an instrumentation
contract, not a scientific protocol and not evidence for the latent-TRIZ
hypothesis.

The authoritative model identity is
`HuggingFaceTB/SmolLM2-360M@f8027fd0eaeea54caa13c31d31b9fdc459c38b49`.
Only the nine receipted runtime files may be used. The frozen A0-R2 protocol
and its target-access boundary remain authoritative for scientific execution.

## Source facts and local policy

| Topic | Official fact | Local A0-R2 requirement |
| --- | --- | --- |
| Architecture | The exact configuration identifies `LlamaForCausalLM`, `model_type: llama`, 32 transformer layers and hidden size 960. | Reject any config or receipt that differs; select the semantic final-block entry, tuple index 32. |
| Hidden states | With `output_hidden_states=True`, Transformers documents embeddings plus one state per layer. Each state is `[batch, sequence, hidden]`. | Require exactly 33 states; require every selected state to be `[1, T, 960]`; only remove the singleton batch axis and reject every other batch size or rank. |
| Tokenizer result | Transformers returns a `BatchEncoding`; it is mapping-like but is not required to be a concrete `dict`. Offset mappings require a fast tokenizer. | Accept `collections.abc.Mapping`, require `input_ids`, `attention_mask` and `offset_mapping`, and require one aligned batch. Never use an `isinstance(..., dict)` gate. |
| Dtype | The source config advertises `bfloat16`. | CPU `float32` is an explicit experiment-time override, not an inferred checkpoint property. Require CPU float32 parameters/outputs and record it in the receipt and every index row. |
| Forward behavior | The model-output API returns a structured object when `return_dict=True`; generation is a separate API. | Use one local forward with `return_dict=True`, `output_hidden_states=True`, and `use_cache=False`; do not call generation; require local-only loading and no network. |

The source facts are recorded from the [exact model tree](https://huggingface.co/HuggingFaceTB/SmolLM2-360M/tree/f8027fd0eaeea54caa13c31d31b9fdc459c38b49), its [exact configuration](https://huggingface.co/HuggingFaceTB/SmolLM2-360M/blob/f8027fd0eaeea54caa13c31d31b9fdc459c38b49/config.json), the [Transformers tokenizer API](https://huggingface.co/docs/transformers/main/en/main_classes/tokenizer), the [model-output API](https://huggingface.co/docs/transformers/main/en/main_classes/output), and the [Llama API](https://huggingface.co/docs/transformers/main/en/model_doc/llama). A later Transformers release can change runtime behavior, so documentation never substitutes for the checks below.

## Mandatory compatibility ladder

No target content may be opened until all applicable pre-target stages pass.

1. **Identity and files.** Verify the exact revision, nine-file allowlist,
   byte sizes and SHA-256 receipts. Reject redirects, extras, omissions and
   configuration drift.
2. **Synthetic tokenizer ABI.** Exercise the complete adapter path with a
   real `BatchEncoding` when the installed Transformers ABI is available, and
   with dependency-free Mapping fixtures otherwise. Require aligned shapes:
   `input_ids [1,T]`, `attention_mask [1,T]`, and `offset_mapping [1,T,2]`.
   Reject missing keys, a slow tokenizer, empty values, unequal lengths and
   batches other than one.
3. **Synthetic tensor ABI.** Exercise a 33-entry rank-three Llama payload.
   It must select tuple index 32, normalize `[1,T,960]` to `[T,960]`, and
   reject rank drift, non-singleton batches, token/hidden-size mismatch and
   non-finite values. A rank-two fixture is accepted only at the C2
   normalization compatibility boundary; a real Llama forward must remain
   rank three before that boundary.
4. **Receipted bounded feasibility.** Before a material study run, confirm the
   installed tokenizer/model behavior under the frozen feasibility contract.
   The existing receipt records 33 states and final shape `[1,25,960]`; it is
   a compatibility observation, not a substitute for future exact-head checks.
5. **Pre-analysis export gate.** Before analysis, a separately versioned
   activation writer must require every representation-index record to have the
   published schema and a matching dense vector/hash. In particular, `dtype`
   must be `float32`, `hidden_states_count` 33, `hidden_size` 960 and tuple
   index one of `0, 11, 21, 32`. Historical R2 code is byte-bound and cannot be
   retrofitted; C3 handles its exact historical omission only in memory.

## Export contract

`schemas/a0r2-representation-index-record.schema.json` defines the public
JSONL record. A future versioned writer must validate row-to-vector identity,
so JSON Schema alone cannot mask a missing dense row or mismatched vector hash.

Every future A0-R2 activation package must preserve the following invariant:

```text
activation receipt runtime.torch_dtype == "float32"
    == each representation-index row dtype
    == the dtype declared by analysis
```

If any side is absent, unknown or unequal, extraction fails before publication
and before analysis. Historical packages are immutable: the narrowly bounded
C3 recovery rule for the C2 omission is documented separately in
[A0-R2-C3 analysis-only metadata recovery](../A0R2C3_ANALYSIS_ONLY_RECOVERY.md)
and must not be generalized into a permissive parser.

## Incident prevention record

| Incident | Why docs could have caught it | Permanent guardrail |
| --- | --- | --- |
| C1 tokenizer failure | `BatchEncoding` mapping semantics were documented but the adapter demanded `dict`. | Mapping acceptance plus an installed-ABI `BatchEncoding` test. |
| C2 tensor-shape failure | The output API documents rank-three hidden states, while the path assumed token-by-hidden rows. | 33-state `[1,T,960]` synthetic end-to-end contract and singleton-only normalization. |
| C2 index-metadata failure | This was a repository export-contract omission, not a SmolLM2 API fact. | A dedicated record schema, a future versioned writer-side row/vector validation, and a regression test that removes `dtype`. |

## Change control

Changing a source fact, runtime library version, tokenizer behavior, model
revision, selected tuple semantics, or export schema requires a new
compatibility receipt and a reviewed contract update before any material run.
It does not authorize a model load, target access, tuning, replacement model,
or repeat execution. Scientific claims remain governed by the frozen
[A0-R2 protocol](../../experiments/a0r2-independent-model/study-protocol.json)
and [A0 replication specification](../A0_REPLICATION_AND_ROBUSTNESS.md).
