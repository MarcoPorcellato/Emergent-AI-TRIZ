---
type: research-specification
title: EXP-001 Comparative Reference Study
description: Model-separated retest of the TRIZ reference-integrated automated proxy.
status: authorized_acquisition_and_one_run
version: 1.0.0
last_verified: 2026-08-18
---

# EXP-001 — comparative reference study

This document extends the published SmolLM2 reference-integrated experiment
without changing any A0, A0-R, C3, or R3 bytes. It is the canonical plan for
testing the same authoritative TRIZ-derived task layer on the first model
(Pythia) and a preregistered third model (Qwen3).

## Scientific question and limits

The question is whether the frozen automated reference-task signal observed in
the source-aware EXP-001 design is reproduced when the exact same public
fixture, blinded/exposed strata, domain split, and teacher-forced scoring
contract are applied independently to different model families.

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
| first-model retest | `EleutherAI/pythia-70m-deduped@e93a9faa9c77e5d09219f6c868bfc7a1bd65593c` | GPT-NeoX, 6 layers, width 512 | local snapshot present |
| prior reference | `HuggingFaceTB/SmolLM2-360M@f8027fd0eaeea54caa13c31d31b9fdc459c38b49` | Llama, 32 layers, width 960 | R3 published `null` |
| third model | `Qwen/Qwen3-0.6B-Base@da87bfb608c14b7cf20ba1ce41287e8de496c0cd` | Qwen3, 28 layers, width 1024 | integrity verified; load/run pending CCP |

Qwen3 is selected for provider, architecture, training-lineage, and tokenizer
independence from Pythia and SmolLM2 while remaining a public Apache-2.0 base
model of plausible CPU size. The official configuration identifies
`Qwen3ForCausalLM`, `qwen3`, 28 layers, width 1024, and vocabulary 151936.
The exact seven-file bytes and source OIDs are now bound by the immutable
Qwen integrity receipt. Installed-runtime compatibility, CPU peak RSS/latency,
and training-data overlap remain unknown until the single authorized run and
its receipt. The older `d4e79cd...` snapshot is not substituted for the frozen
`da87bfb...` revision.

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

## Current checkpoint

The SmolLM2 reference-integrated R3 package is already public and terminal
`null` (PR #75 merge `4cc1c6d...`). This comparative tranche is target-free and
approval-requested: Pythia retest and Qwen acquisition/run have not occurred.
No model or sealed target was accessed while preparing this dossier.

The operator has authorized exactly one run for each exact Pythia, SmolLM2, and
Qwen3 snapshot under the stated CPU/RSS/time limits, one-read target boundary,
and publication of every terminal result. The remaining gate is exact-head CCP
qualification with inactive admission and an empty queue; no run starts before
that receipt is bound to this code and protocol.
