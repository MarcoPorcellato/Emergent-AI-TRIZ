---
type: Research Note
title: EXP-001 Additional Model Runtime Dossier
description: Source-backed record for the authorised additional model controls and their fail-closed execution boundary.
status: active
last_verified: 2026-08-19
---

# EXP-001 additional model runtime dossier

This note is the pre-execution, source-backed record for the two additional
controls authorised on 2026-08-19. It is operational documentation, not a
scientific result and it does not alter the frozen EXP-001 protocol or any
A0-R2/C3 artifact.

## Official-source checks

The pinned snapshots are the exact verified revisions below:

| model | revision | architecture contract | tokenizer contract | license |
| --- | --- | --- | --- | --- |
| `openai-community/gpt2` | `607a30d783dfa663caf39e06633721c8d4cfcd7e` | `gpt2`, `GPT2LMHeadModel`, 12 layers, hidden 768, vocabulary 50,257, context 1,024 | GPT-2 byte-level files; the pinned `tokenizer_config.json` has no explicit `tokenizer_class` | MIT |
| `HuggingFaceTB/SmolLM2-135M` | `93efa2f097d58c2a74874c7e644dbc9b0cee75a2` | `llama`, `LlamaForCausalLM`, 30 layers, hidden 576, vocabulary 49,152, context 8,192 | **`GPT2Tokenizer`**, byte-level BPE; `tokenizer.json` is loaded through the fast AutoTokenizer path | Apache-2.0 |

Primary sources:

- [GPT-2 model card](https://huggingface.co/openai-community/gpt2) and
  [frozen GPT-2 tree](https://huggingface.co/openai-community/gpt2/tree/607a30d783dfa663caf39e06633721c8d4cfcd7e)
- [SmolLM2-135M model card](https://huggingface.co/HuggingFaceTB/SmolLM2-135M) and
  [frozen SmolLM2-135M tree](https://huggingface.co/HuggingFaceTB/SmolLM2-135M/tree/93efa2f097d58c2a74874c7e644dbc9b0cee75a2)
- [Transformers Llama documentation](https://huggingface.co/docs/transformers/v4.53.0/en/model_doc/llama),
  including `LlamaTokenizerFast` offset and special-token behaviour.

The official SmolLM2 page labels the model `llama`, but the exact pinned
`tokenizer_config.json` declares `GPT2Tokenizer` and uses GPT-2 vocabulary and
merge files. Architecture tags therefore cannot be used to infer tokenizer
class. The runner now binds both contracts independently before loading
weights. This is the key preventative check for the earlier tokenizer failure.

## Acquisition receipts

Only the allowlisted runtime files were downloaded, sequentially, under the
one-GiB per-model ceiling. The receipts are immutable and prove that no model
was loaded and no sealed target was read at acquisition time:

- `results/exp001-comparative/preexecution/gpt2-integrity-receipt.json`
  (`550,959,861` bytes; `model.safetensors` SHA-256
  `248dfc3911869ec493c76e65bf2fcf7f615828b0254c12b473182f0f81d3a707`)
- `results/exp001-comparative/preexecution/smollm2-135m-integrity-receipt.json`
  (`272,437,465` bytes; `model.safetensors` SHA-256
  `80521b40281d6ce74ecf9282c22539e75aa0ac8578892b2a59955ef78d55da1`)

The source tree and local receipts are re-hashed before any material run.
Unknown files, size drift, hash drift, architecture drift, tokenizer metadata
drift, network access, generation, or non-fast tokenizers fail closed before
model output is possible.

## Execution boundary

Each model gets one sequential invocation only. The runner sets
`HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, loads CPU float32 with
`local_files_only=True`, calls teacher-forced scoring only, and never calls
`generate`. The shared EXP-001 public-record fixture and statistical plan are
unchanged; scores are never pooled across models. The sealed target is opened
exactly once by the analysis boundary. A terminal `positive`, `null`,
`non_interpretable`, `incompatible`, or `failed` package is publishable; no
post-access retry, tuning, substitution, or claim promotion is permitted.

## Preventative checks added after the pre-access stop

The first GPT-2 invocation stopped before model load because the runner had
bound the approval-text digest where it needed the JSON dossier digest. No
model, output, or target was accessed. The corrective runner binds the actual
authorization dossier SHA-256 and adds `_verify_tokenizer_metadata` before the
adapter load. This makes the two failure classes observable and fail-closed:

1. authorization dossier identity/digest mismatch;
2. architecture, vocabulary, context-length, or tokenizer-class mismatch.

The correction must pass a new exact-head CCP qualification before material
execution. This document is updated with terminal receipts and results only
after that qualification and the two authorised runs complete.

## Next complementary controls: authorization and acquisition preflight

The next candidates are deliberately documented in a separate, non-authorising
request at
`experiments/exp001-comparative-reference/next-model-authorization.json`.
Official revision-tree metadata was read on 2026-08-19; the authorization was
then recorded against the exact revisions and allowlists below. Acquisition
remains a separate, receipt-producing gate.

| model | revision | loader/config | tokenizer metadata | runtime allowlist | ceiling |
| --- | --- | --- | --- | --- | --- |
| `EleutherAI/gpt-neo-125m` | `21def0189f5705e2521767faed922f1f15e7d7db` | `gpt_neo`, `GPTNeoForCausalLM`, 12 layers, hidden 768, vocab 50,257 | `GPT2Tokenizer`, `model_max_length=2048` | 8 files, 529,444,041 bytes | 1 GiB |
| `Qwen/Qwen2.5-0.5B` | `060db6499f32faf8b98477b0a26969ef7d8b9987` | `qwen2`, `Qwen2ForCausalLM`, 24 layers, hidden 896, vocab 151,936, model context 32,768 | `Qwen2Tokenizer`, `model_max_length=131072` | 7 files, 999,586,188 bytes | 1.5 GiB |

The Qwen tokenizer metadata advertises a larger tokenizer maximum than the
model's `max_position_embeddings`; the runner must bind both values and reject
inputs that exceed the model context. Both contracts require fast offsets,
`trust_remote_code=false`, offline local-only loading, CPU float32, and
teacher-forced scoring without generation. The exact operator authorization is
now recorded for these two snapshots. The earlier GPT-2 and SmolLM2-135M
authorization cannot be reused for them.

The acquisition CLI is deliberately independent of model libraries. It streams
each allowlisted file into an atomic temporary path, enforces the declared byte
ceiling and exact size, and emits no receipt until every SHA-256 digest matches.
The official CDN read timeout is bounded at 1,800 seconds so a slow large blob
is not mistaken for a corrupt snapshot. Interrupted large blobs may resume only
with an explicit byte-range response and remain inside the same exact-size
budget; a timeout, invalid range, or redirect violation still fails closed and
leaves no unverified runtime file or receipt.

Primary official sources: [GPT-Neo model card](https://huggingface.co/EleutherAI/gpt-neo-125m),
[GPT-Neo frozen tree](https://huggingface.co/EleutherAI/gpt-neo-125m/tree/21def0189f5705e2521767faed922f1f15e7d7db),
[GPT-Neo tokenizer config](https://huggingface.co/EleutherAI/gpt-neo-125m/blob/21def0189f5705e2521767faed922f1f15e7d7db/tokenizer_config.json),
[Qwen2.5 model card](https://huggingface.co/Qwen/Qwen2.5-0.5B),
[Qwen2.5 frozen config](https://huggingface.co/Qwen/Qwen2.5-0.5B/blob/060db6499f32faf8b98477b0a26969ef7d8b9987/config.json),
and [Qwen2.5 tokenizer config](https://huggingface.co/Qwen/Qwen2.5-0.5B/blob/060db6499f32faf8b98477b0a26969ef7d8b9987/tokenizer_config.json).
