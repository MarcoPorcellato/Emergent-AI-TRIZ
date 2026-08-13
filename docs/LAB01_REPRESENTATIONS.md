---
type: runbook
title: Lab 01 model-backed representation extraction
description: Strict, offline, reproducible extraction of layer activations for each case.
status: active
last_verified: 2026-08-13
---

# Lab 01 model-backed representation extraction

This run extracts one representation vector per case-layer from `resid_post` at the
last attended non-special token. It uses the existing local-only GPT-NeoX adapter,
verifies the pinned Lab 01 model snapshot (`EleutherAI/pythia-70m-deduped` at
`e93a9faa9c77e5d09219f6c868bfc7a1bd65593c`), and writes outputs as:

- an external `activations.safetensors` tensor payload,
- a JSONL index with vector metadata and hashes,
- a summary JSON with artifact hashes and non-claim boundary.

The extracted vectors are empirical measurements but not evidence-eligible:
`empirical = true`, `evidence_eligible = false`, `claim_ids = []`.

Each index row also includes a deterministic tokenizer receipt:

- `tokenizer.tokenizer_class`
- `tokenizer.name_or_path`
- `tokenizer.fingerprint` (stable JSON canonical hash of tokenizer metadata and file hashes)
- `tokenizer.files` (`tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`)

## Run contract

- no download path is allowed;
- offline mode is required (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`);
- `cases_path`, `model_root`, `output_dir` in config are resolved relative to the config file location;
- model identity is fixed to the pinned Lab 01 snapshot;
- canonical prompts are built from fields:
  - `problem`, `constraints`, `initial_state`, `desired_improvement`,
    `worsening_consequence`, `transformation`, `resulting_state` and optional
    `solution` when present;
- token selection is deterministic: last attended non-special token;
- token vector extraction is performed for every `resid_post_layer_*` key from
  adapter output.
- Lab 04 accepts this JSONL index directly and verifies the container hash,
  tensor metadata, tensor key and canonical vector hash before probing.

## Execute

```bash
make lab01-representations
```

Outputs are under `results/lab01/model-representations` by default:

- `activations.safetensors`
- `representations-index.jsonl`
- `summary.json`

No absolute paths are written in these artifacts.

Canonical vector hash used for each layer is:

```
sha256(
  json({"byte_order":..., "dtype":..., "shape":...}, sort_keys=True) + b"|" +
  vector.tobytes(order="C")
)
```

Run determinism contract requires `run_timestamp_utc` in config and uses it directly
as `summary.created_at`/`summary.run_timestamp_utc` (no wall-clock timestamp is used).
