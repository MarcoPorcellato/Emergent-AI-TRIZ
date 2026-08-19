---
type: Research Note
title: EXP-001 Official Model Documentation Audit
description: Source-backed implementation safeguards for the GPT-Neo and Qwen2.5 complementary controls.
status: metadata_only
last_verified: 2026-08-19
---

# EXP-001 official model documentation audit

This note records a read-only audit of the official Hugging Face model pages
and Transformers model/tokenizer documentation for the two complementary
controls selected by `next-model-selection.json`. It is an implementation
guardrail, not a model-access authorization and not a scientific result.

No model bytes, tokenizer assets, model outputs, or sealed targets were read
for this audit. The exact revision-tree metadata and the local selection
dossier remain authoritative for identity, file allowlists, and SHA-256
receipts.

## Primary sources

The following links are the only sources used to derive the runtime rules below:

- [GPT-Neo 125M model card](https://huggingface.co/EleutherAI/gpt-neo-125m)
- [GPT-Neo exact revision tree](https://huggingface.co/EleutherAI/gpt-neo-125m/tree/21def0189f5705e2521767faed922f1f15e7d7db)
- [GPT-Neo exact `config.json`](https://huggingface.co/EleutherAI/gpt-neo-125m/blob/21def0189f5705e2521767faed922f1f15e7d7db/config.json)
- [GPT-Neo exact `tokenizer_config.json`](https://huggingface.co/EleutherAI/gpt-neo-125m/blob/21def0189f5705e2521767faed922f1f15e7d7db/tokenizer_config.json)
- [GPT-Neo Transformers documentation](https://huggingface.co/docs/transformers/model_doc/gpt_neo)
- [Qwen2.5 0.5B model card](https://huggingface.co/Qwen/Qwen2.5-0.5B)
- [Qwen2.5 exact revision tree](https://huggingface.co/Qwen/Qwen2.5-0.5B/tree/060db6499f32faf8b98477b0a26969ef7d8b9987)
- [Qwen2.5 exact `config.json`](https://huggingface.co/Qwen/Qwen2.5-0.5B/blob/060db6499f32faf8b98477b0a26969ef7d8b9987/config.json)
- [Qwen2.5 exact `tokenizer_config.json`](https://huggingface.co/Qwen/Qwen2.5-0.5B/blob/060db6499f32faf8b98477b0a26969ef7d8b9987/tokenizer_config.json)
- [Qwen2 Transformers documentation](https://huggingface.co/docs/transformers/model_doc/qwen2)
- [Transformers tokenizer contract](https://huggingface.co/docs/transformers/en/internal/tokenization_utils)

## Exact snapshot facts and consequences

| control | exact snapshot facts | execution consequence |
| --- | --- | --- |
| `EleutherAI/gpt-neo-125m@21def0189f5705e2521767faed922f1f15e7d7db` | MIT; `GPTNeoForCausalLM`; `gpt_neo`; 12 layers; hidden size 768; vocabulary 50,257; model context 2,048; `GPT2Tokenizer`; tokenizer maximum 2,048 | Bind the exact revision config, not library defaults. Keep right-padding if padding is ever introduced because GPT-Neo uses absolute position embeddings. Keep teacher-forced logits only. |
| `Qwen/Qwen2.5-0.5B@060db6499f32faf8b98477b0a26969ef7d8b9987` | Apache-2.0; `Qwen2ForCausalLM`; `qwen2`; 24 layers; hidden size 896; vocabulary 151,936; model context 32,768; `Qwen2Tokenizer`; tokenizer maximum 131,072 | Enforce the smaller model context (32,768), never the tokenizer advertisement. Use the base-model prompt protocol, not the model-card chat-template/generation example. Bind the exact revision config before loading. |

The model cards show convenient generation examples, but generation is outside
EXP-001. The run must call the causal-LM forward path with
`output_hidden_states=false`, `output_attentions=false`, `use_cache=false`,
and must never call `generate` or `apply_chat_template`.

The Transformers documentation defines `hidden_states` as the optional tuple
containing the embedding output followed by one tensor per layer. This is a
useful semantic check for future representation work, but the current
comparative control scores teacher-forced logits and does not claim a hidden
state result.

## Preventative checks required by the official documentation

1. **Revision-first loading.** Read `config.json` and
   `tokenizer_config.json` from the already acquired local root and compare
   model type, architecture, layer count, hidden size, vocabulary, tokenizer
   class, tokenizer maximum, and model context with the frozen dossier. A
   mismatch is terminal `incompatible` before model construction.
2. **Do not infer architecture from tokenizer metadata.** GPT-Neo uses the
   GPT-2 tokenizer family; the tokenizer class is an independent contract.
   The previous SmolLM2 failure demonstrates why this check must precede
   loading weights.
3. **Context bound.** The effective maximum is
   `min(tokenizer.model_max_length, config.max_position_embeddings)`; for
   Qwen2.5 this is 32,768, not 131,072. Inputs beyond the effective maximum
   fail closed rather than being silently truncated.
4. **Padding rule.** The current protocol renders one prompt at a time and
   does not request padding. If batching or padding is introduced later, set
   GPT-Neo `padding_side="right"` and freeze that choice in a new protocol
   version; never rely on an implicit tokenizer default.
5. **Fast-tokenizer boundary.** `return_offsets_mapping` is available only
   for fast tokenizers. The current teacher-forcing scorer does not require
   offsets; any future span/site extractor must request a fast tokenizer and
   test offsets before model output.
6. **Runtime mode.** Use `local_files_only=true`,
   `trust_remote_code=false`, CPU `float32`, and offline environment flags.
   The checkpoint metadata may advertise `bfloat16`, but the approved
   experiment contract deliberately overrides that for reproducible CPU
   float32 scoring and records the choice in the receipt.
7. **No hidden assumptions from documentation defaults.** The generic GPT-Neo
   docs show a 24-layer, 2048-hidden configuration as an example default; that
   is not the 125M checkpoint contract. Always validate the exact local
   config, never instantiate an unbound default configuration.

## Evidence and licensing boundary

The official pages establish provenance, architecture metadata, and the stated
MIT/Apache-2.0 licenses. They do not establish example-level training-data
disjointness, scientific validity of the TRIZ proxy, or Apple-Silicon peak
memory. Those remain separate unknowns requiring receipts or an explicitly
labelled limitation. The model cards' generation demonstrations are not
evidence for the latent-TRIZ hypothesis and are not part of EXP-001.

## Required pre-run receipt fields

Before either material run, the integrity receipt and execution manifest must
bind:

- exact model ID and 40-character revision;
- SHA-256 and byte size for every allowlisted runtime file;
- the two source-tree URLs and the canonical metadata digests;
- observed `model_type`, `architectures`, layer count, hidden size, vocabulary,
  tokenizer class, tokenizer maximum, and effective context;
- `local_files_only`, `trust_remote_code=false`, network disabled,
  generation disabled, CPU float32, and one-shot target-read boundary;
- terminal status, peak RSS, wall time, dense-output size, and any
  incompatibility or cleanup uncertainty.

Missing, unknown, or drifted fields are not warnings: they are a fail-closed
terminal outcome and cannot be repaired by retrying after model or target
access.
