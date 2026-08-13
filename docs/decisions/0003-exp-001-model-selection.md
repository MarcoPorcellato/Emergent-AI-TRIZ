---
type: decision-record
title: ADR 0003 — EXP-001 model selection
description: Provisional, evidence-backed model roles for EXP-001 before preregistration or model acquisition.
status: active
last_verified: 2026-08-13
---

# ADR 0003 — EXP-001 model selection

## Status

Accepted as a provisional engineering decision. This is not a preregistration, model acquisition, experiment, or scientific result.

## Decision

EXP-001 will be designed around two pretrained base-model roles:

1. **Primary mechanistic candidate:** `google/gemma-3-270m`, pinned to revision `9b0cfec892e2bc2afd938c98eabe4e4a7b1e0ca1` when acquired.
2. **Independent architecture replication candidate:** `HuggingFaceTB/SmolLM2-360M`, pinned to revision `f8027fd0eaeea54caa13c31d31b9fdc459c38b49` when acquired.

`Qwen/Qwen3-0.6B-Base` at revision `da87bfb608c14b7cf20ba1ce41287e8de496c0cd` remains a documented fallback or later replication candidate. It is not part of the minimum EXP-001 execution path.

No weights are vendored by this repository. Acquisition, license acceptance, storage, and compute remain separate operator actions.

## Evidence recorded on 2026-08-13

### Gemma 3 270M pretrained

- The official Google model card identifies the 270M text model, pretrained and instruction-tuned variants, and a 32K-token context for the 270M size.
- The official Hugging Face repository reports 268,098,176 parameters, Transformers support, revision `9b0cfec892e2bc2afd938c98eabe4e4a7b1e0ca1`, and gated access requiring acceptance of the Gemma usage terms.
- Google publishes Gemma Scope 2 for Gemma 3 270M pretrained. Its official repository reports SAEs and transcoders for residual-stream, attention-output, and MLP-output sites, including all-layer and cross-layer variants. The repository revision observed was `b218cd5d69dc2fa71cff448b68d625e6c9702d49`, under CC BY 4.0.

These facts make Gemma the strongest current fit for the staged path from activations and probes to sparse features and causal tracing. They do not imply that a TRIZ-like feature exists.

### SmolLM2 360M pretrained

- The official Hugging Face model repository is public and ungated, reports 361,821,120 parameters, Transformers support, Apache 2.0 licensing, and revision `f8027fd0eaeea54caa13c31d31b9fdc459c38b49`.
- Its model card documents a pretrained compact language model and an openly described training stack.

SmolLM2 is selected for architecture-level replication because it avoids the Gemma-specific license and feature-tooling path. No official pretrained sparse-feature suite was established during this decision review, so replication initially targets behavioral, activation, probe, contrastive-direction, and steering layers.

### Qwen3 0.6B Base

- The official repository is public and ungated, reports 596,049,920 parameters, Transformers support, Apache 2.0 licensing, and revision `da87bfb608c14b7cf20ba1ce41287e8de496c0cd`.

Qwen3 Base is retained as a fallback because it is materially larger than the two selected candidates and does not improve the minimum two-family design.

## External sources

- [Google Gemma 3 model card](https://ai.google.dev/gemma/docs/core/model_card_3)
- [Google Gemma terms](https://ai.google.dev/gemma/terms)
- [Google Gemma 3 270M pretrained repository](https://huggingface.co/google/gemma-3-270m)
- [Google Gemma Scope 2 270M pretrained repository](https://huggingface.co/google/gemma-scope-2-270m-pt)
- [Hugging Face SmolLM2 360M repository](https://huggingface.co/HuggingFaceTB/SmolLM2-360M)
- [Qwen3 0.6B Base repository](https://huggingface.co/Qwen/Qwen3-0.6B-Base)

## Constraints before acquisition or execution

1. Recheck every repository revision and terms page on the acquisition date.
2. Require explicit operator acceptance for gated Gemma access; never automate acceptance.
3. Preserve a dated, immutable evidence anchor for the applicable model, dataset, and tooling terms. Record source URL, retrieval time, content hash, and the exact accepted terms identifier in the preregistration/run chain without redistributing material that the terms prohibit.
4. Record exact downloaded-file hashes and tokenizer revisions in the run manifest.
5. Measure memory, latency, hidden-state access, and deterministic inference in a non-empirical feasibility run before freezing EXP-001.
6. Pin a narrow Gemma Scope artifact rather than acquiring the full collection; the published collection is far larger than the base model.
7. Keep model-generated cases out of the sealed human-authored dataset unless separately disclosed and controlled.

## Dataset decision

Use a synthetic-first, human-authored case corpus with strict provenance. External patents or other materials may be reference-only anchors unless redistribution rights are established per item. This reduces licensing uncertainty and pretrained-corpus contamination risk, but does not eliminate it.

Before preregistration, freeze all of the following in the dataset contract:

- four substantially different domains with balanced operator and source coverage;
- separate discovery, validation, sealed evaluation, and lexical-adversarial splits;
- Segmentation positives, Inversion/operator controls, matched negatives, near misses, and alternative-principle cases;
- forbidden-term, lexical-overlap, exact-duplicate, near-duplicate, and reference-contamination audits;
- per-item provenance, redistribution status, human authorship, annotator independence, and disagreement-preserving adjudication;
- immutable snapshot hashes and an amendment-only change policy.

## Claim boundary

Model selection does not change `CLM-001`, `CLM-002`, or `CLM-003`. They remain E0, untested, and non-empirical. The selected revisions must not be written into a preregistered study manifest until feasibility, dataset, controls, rater plan, and statistical decision rules are frozen.

## Revisit conditions

Reopen this ADR if a candidate becomes unavailable, its terms change materially, exact hidden-state access fails, the measured local resource envelope is unacceptable, or a better-supported base model materially improves the two-family design.
