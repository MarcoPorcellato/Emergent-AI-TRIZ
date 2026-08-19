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
