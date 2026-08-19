---
type: research-specification
title: EXP-001 Comparative Reference Study
description: Model-separated, receipt-backed comparison of the TRIZ reference-integrated automated proxy.
status: published_exploratory_results
version: 1.1.0
last_verified: 2026-08-19
---

# EXP-001 — comparative reference study

This document extends the published SmolLM2 reference-integrated experiment
without changing any A0, A0-R, C3, or R3 bytes. It is the canonical record for
testing the same authoritative TRIZ-derived task layer across seven separately
authorized model runs. Every run is independent and non-poolable.

## Scientific question and limits

The question is whether the frozen automated reference-task signal observed in
the source-aware EXP-001 design is reproduced when the exact same public
fixture, blinded/exposed strata, domain split, and teacher-forced scoring
contract are applied independently to different model families and scale
controls.

This is not a claim of TRIZ rediscovery, inventiveness, expert competence,
novelty, or human-validated reasoning. Every result remains exploratory,
`expert_validated=false`, `evidence_eligible=false`, and `claim_ids=[]`.
Scores are never pooled across models and tokenizer IDs are never compared.

## Frozen reference layer

The study reuses the published, hash-bound reference layer: all 40 principle
records, the sparse double-checked Matrix 2003 fixture, and the rights-aware
Panitz tool-edge fixture. The source PDFs remain external copyrighted sources;
the repository stores provenance, locators, paraphrases, and rights flags, not
redistributed PDF bytes or bulk tables.

The two strata remain physically and statistically separate:

- `TRIZ-blinded-transfer`: no TRIZ names, source wording, canonical examples,
  Matrix cells, or Panitz edges are shown. This is the only rediscovery-like
  transfer arm.
- `source-exposed-competence`: bounded independently authored reference
  context is shown. It measures retrieval and use, never rediscovery.

The 85-record inventory is unchanged: 72 primary records plus 13 descriptive
Matrix/Panitz records, each scored against four labels by teacher forcing.

## Model selection

Selection was made without consulting any prior result. The two already
acquired models provide the first-model retest and the prior R3 reference:

| role | exact model and revision | architecture | status |
|---|---|---|---|
| first-model retest | `EleutherAI/pythia-70m-deduped@e93a9faa9c77e5d09219f6c868bfc7a1bd65593c` | GPT-NeoX, 6 layers, width 512 | run complete: `null` |
| prior reference | `HuggingFaceTB/SmolLM2-360M@f8027fd0eaeea54caa13c31d31b9fdc459c38b49` | Llama, 32 layers, width 960 | comparative run complete: `null` |
| third model | `Qwen/Qwen3-0.6B-Base@da87bfb608c14b7cf20ba1ce41287e8de496c0cd` | Qwen3, 28 layers, width 1024 | run complete: `null` |

Qwen3 is selected for provider, architecture, training-lineage, and tokenizer
independence from Pythia and SmolLM2 while remaining a public Apache-2.0 base
model of plausible CPU size. The official configuration identifies
`Qwen3ForCausalLM`, `qwen3`, 28 layers, width 1024, and vocabulary 151936.
The exact seven-file bytes and source OIDs are now bound by the immutable
Qwen integrity receipt. Installed-runtime compatibility, CPU peak RSS/latency,
and training-data overlap remain unknown until the single authorized run and
its receipt. The older `d4e79cd...` snapshot is not substituted for the frozen
`da87bfb...` revision.

The completed extension adds four separately selected controls without
conditioning on prior scores: GPT-2 for decoder-family diversity, SmolLM2-135M
for within-family scale, GPT-Neo-125M for a GPT-Neo architecture distinct from
GPT-NeoX Pythia, and Qwen2.5-0.5B for a within-provider Qwen2/Qwen3 contrast.
Their exact revisions, official tokenizer contracts, allowlists, and SHA-256
receipts are documented in [`EXP001_ADDITIONAL_MODEL_RUNTIME.md`](./EXP001_ADDITIONAL_MODEL_RUNTIME.md),
the selection/authorization dossiers, and the execution packages. These
controls increase descriptive coverage; they do not create a pooled estimator
or independent expert replication.

Implementation details and the source-backed tokenizer safeguards are maintained
in the [official model documentation audit](./EXP001_MODEL_OFFICIAL_DOC_AUDIT.md)
and the [additional-model runtime dossier](./EXP001_ADDITIONAL_MODEL_RUNTIME.md).

## Frozen analysis

The primary is inherited exactly from the R3 analysis plan: 24 primary units,
six held-out domains, two families per domain, two replicates per family, an
exact two-sided sign-flip permutation over domain deltas (64 permutations),
and a 10,000-resample domain bootstrap seeded `20260818`. A positive terminal
state requires `p<=0.05`, positive mean delta, every domain delta positive, and
a positive bootstrap lower bound. Sensitivities cannot rescue a failed
primary. Matrix and Panitz outcomes are descriptive, source-family separated,
and cannot change the primary terminal state.

Each model receives one independent run. The exact model identity, local
runtime-file hashes, code hashes, fixture hashes, and protocol hash are bound
in its receipt. The model-specific tokenizer is an implementation detail, not
a cross-model outcome. No generation, chat template, or token-ID comparison is
permitted; only teacher-forced choice scores are comparable at the task level.

## Execution and publication gates

The Qwen download is complete and integrity-verified under its separate
seven-file authorization. Before each model load or sealed-target read, CCP
must report `resource decision=admit`,
`admission active=false`, and `queue_count=0`; an unknown or incompatible
admission state never authorizes execution. Each model run is local-only CPU
float32, offline, no generation, at most 1,800 seconds, 8 GiB peak RSS, and
128 MiB new dense output. The sealed target file is opened exactly once at the
analysis boundary and never before it.

Every terminal state (`positive`, `null`, `failed`, `non_interpretable`, or
`incompatible`) is published with immutable receipts, statistics, limitations,
recovery observations, and a manifest. Dense scalar content remains an
external asset identified by locator and SHA-256 unless separately authorized
for public publication. Fresh-clone verification must pass with the declared
asset and fail closed when it is absent or mutated.

## Terminal results and current checkpoint

The SmolLM2 reference-integrated R3 package is already public and terminal
`null` (PR #75 merge `4cc1c6d...`). The comparative tranche is now terminally
complete. All seven runs were authorized, CCP-gated, and independently
verified:

| Model | Status | p | Mean delta | 95% bootstrap CI | Positive domains | Wall / peak RSS |
|---|---|---:|---:|---|---:|---:|
| Pythia 70M | `null` | 0.6875 | +0.0545 | [-0.1485, +0.2956] | 3/6 | 312.4 s / 1.92 GiB |
| SmolLM2 360M | `null` | 0.65625 | -0.0247 | [-0.1095, +0.0602] | 2/6 | 365.4 s / 2.90 GiB |
| Qwen3 0.6B | `null` | 0.0625 | +0.9323 | [+0.5353, +1.2063] | 5/6 | 948.8 s / 4.66 GiB |
| GPT-2 | `null` | 0.3125 | +0.0264 | not reported | not reported | 316.7 s / 1.98 GiB |
| SmolLM2 135M | `null` | 0.5000 | +0.0420 | not reported | not reported | 341.7 s / 2.35 GiB |
| GPT-Neo 125M | `null` | 0.6875 | +0.0155 | not reported | not reported | 323.9 s / 1.73 GiB |
| Qwen2.5 0.5B | `null` | 0.96875 | -0.0059 | not reported | not reported | 935.3 s / 4.54 GiB |

The Qwen3 near-signal remains `null` because it misses `p<=0.05` and has one
slightly negative held-out domain. All seven packages pass
`verify_comparative_publication`; each records exactly one sealed-target read,
no generation/network, and the approved resource ceilings. This is automated
exploratory evidence only, not a TRIZ rediscovery or competence claim.

Packages and external dense-asset hashes are recorded in the tracked result
directories and their execution receipts. No model or target access remains
pending for this comparative tranche; the next scientific step is independent
expert review or a newly preregistered confirmatory design.

The seven immutable packages are:

- `results/exp001-comparative/pythia-70m-e93a9faa-pythia-20260818-01/`
- `results/exp001-comparative/smollm2-360m-f8027fd0-smollm2-20260818-01/`
- `results/exp001-comparative/qwen3-0.6b-da87bfb-qwen3-20260818-01/`
- `results/exp001-comparative/gpt2-607a30d7-gpt2-20260819-01/`
- `results/exp001-comparative/smollm2-135m-93efa2f0-smollm2-135m-20260819-01/`
- `results/exp001-comparative/gpt-neo-125m-21def018-gpt-neo-125m-20260819-01/`
- `results/exp001-comparative/qwen2.5-0.5b-060db649-qwen2.5-0.5b-20260819-01/`
