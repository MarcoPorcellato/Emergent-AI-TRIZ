---
type: research-specification
title: EXP-002-AUTO pre-expert automated evidence campaign
description: Independent, fully automated exploratory campaign for seven frozen models; it measures response-surface robustness and explicit procedural proxies without substituting for TRIZ expert validation.
status: design_approved_implementation_pending
version: 0.1.0
last_verified: 2026-08-20
---

# EXP-002-AUTO — pre-expert automated evidence campaign

## 1. Purpose and epistemic envelope

EXP-002-AUTO is an independently frozen, fully automated exploratory programme.
It exists to collect useful, reproducible behavioural data while the separate
EXP-002 expert-review and independently authored transfer-corpus gates remain
open. It must not amend, rerun, pool with, or reinterpret EXP-002A, A0-R2/C3,
R3, or any published comparative package.

The programme can distinguish a response-surface artefact from a behaviour
that survives labels, option position, and candidate-description scoring. It
can measure factual retrieval against automatically derived public-reference
keys and a deliberately procedural transfer proxy. It cannot validate TRIZ
construct correctness, establish exposure in training data, or promote a
general claim about TRIZ or the Latent TRIZ Hypothesis.

Every reported result therefore has `scientific_status: exploratory`,
`expert_validated: false`, `evidence_eligible: false`, and no claim IDs. A
favourable automated result is named `auto_proxy_signal`, never a positive
TRIZ finding.

## 2. Authoritative anchors

| Item | Anchor |
| --- | --- |
| Starting implementation checkpoint | `exp002-qwen3-followup` at `6c392ad71a272c34cfb87b86217500693abdd30a` |
| Existing programme | `docs/EXP002_QWEN3_FOLLOWUP_RESEARCH_PLAN.md` |
| Existing seven-model baseline | `results/exp002/preexecution/publication-manifest.json` |
| Existing response surface | `experiments/exp002-qwen3-followup/response-surface-plan.json` |
| Existing public direct-question bank | `experiments/exp002-qwen3-followup/question-bank-manifest.json` |
| CCP coordination contract | exact current `commit-ci-preflight` `origin/main`, verified live immediately before material work |

The implementation must verify every anchor and all referenced input hashes
before a model or tokenizer is constructed. A changed anchor is a terminal
`failed_preflight`, not a reason to repair the protocol after access.

## 3. Exact model registry

All stages use these exact, already integrity-receipted local snapshots. No
substitution, quantisation, fine-tuning, generation, network access, or
automatic fallback is permitted.

| Alias | Model and revision | Local runtime root |
| --- | --- | --- |
| Pythia | `EleutherAI/pythia-70m-deduped@e93a9faa9c77e5d09219f6c868bfc7a1bd65593c` | `artifacts/models/pythia-70m-deduped-e93a9faa` |
| Smol-360 | `HuggingFaceTB/SmolLM2-360M@f8027fd0eaeea54caa13c31d31b9fdc459c38b49` | `artifacts/models/smollm2-360m-f8027fd0` |
| Qwen3 | `Qwen/Qwen3-0.6B-Base@da87bfb608c14b7cf20ba1ce41287e8de496c0cd` | `artifacts/models/qwen3-0.6b-base-da87bfb` |
| GPT-2 | `openai-community/gpt2@607a30d783dfa663caf39e06633721c8d4cfcd7e` | `artifacts/models/gpt2-607a30d7` |
| Smol-135 | `HuggingFaceTB/SmolLM2-135M@93efa2f097d58c2a74874c7e644dbc9b0cee75a2` | `artifacts/models/smollm2-135m-93efa2f0` |
| GPT-Neo | `EleutherAI/gpt-neo-125m@21def0189f5705e2521767faed922f1f15e7d7db` | `artifacts/models/gpt-neo-125m-21def018` |
| Qwen2.5 | `Qwen/Qwen2.5-0.5B@060db6499f32faf8b98477b0a26969ef7d8b9987` | `artifacts/models/qwen2.5-0.5b-060db649` |

The implemented registry must copy, rather than retype, the existing
integrity-receipt hashes. Any missing runtime file, hash drift, non-fast
tokenizer, missing offsets, wrong padding convention, or model identity drift
fails closed before scoring.

## 4. Frozen stages and schedule

The schedule is ordered and model-separated. Later stages do not repair,
replace, tune, or retry earlier material output.

### AUTO-0 — tokenizer audit

For each exact tokenizer only, record token IDs, offset mappings, answer-boundary
tokens, label-token segmentations, and candidate-description boundary metadata
for the 24 existing transfer prompts. This stage never loads model weights,
opens a target key, or emits a scientific score. It detects unsupported
tokenization before a model stage starts.

### AUTO-1 — 24-record response surface

Use the immutable, target-free public descriptions of the 24 EXP-002A transfer
records. Execute exactly five conditions per model: four balanced cyclic label
permutations and one label-free candidate-description score. The original
baseline output is read only as a historical comparator and is never rerun.

This stage opens no target key. Its endpoints are top-label entropy, cyclic
semantic invariance, agreement between cyclic and label-free choice, and the
predeclared status `measurement_robust`, `measurement_artifact_supported`, or
`non_interpretable`. It is the primary discriminator for the Qwen3 anomaly.

### AUTO-2 — 178-question automatic factual block

Freeze exactly 178 records before execution:

| Family | Count | Automatic key source |
| --- | ---: | --- |
| Principle number-to-name | 40 | registered 40-principle fixture |
| Principle name-to-operator | 40 | registered 40-principle fixture |
| Real-versus-invented discrimination | 40 | deterministic matched distractor generator |
| Insufficient-information abstention | 40 | deterministic missing-evidence template |
| Canary questions | 8 | literal, non-TRIZ controls |
| Matrix direction | 6 | double-verified Matrix 2003 fixture |
| Tool-relationship facts | 4 | Panitz relation fixture with documented support status |

The automatic key is generated and sealed before model access. The scored
questions are partitioned in this frozen order into four shards of 45, 45, 44,
and 44 records. The shards are not a retry mechanism: each is one authorized
attempt per model. Exact accuracy, abstention rate, canary rejection, and
family-separated confusion matrices are descriptive automatic-reference
outcomes only.

### AUTO-3 — public-formulation sensitivity

This stage deliberately avoids claiming source familiarity. It uses 40
public-reference facts in four deterministic formulations: canonical short
field rendering, source-independent structured paraphrase, matched non-TRIZ
control, and nonce-edit control. The public fixtures contain locators and
hashes, not long copied excerpts. Endpoints are paired continuation contrast,
paraphrase stability, nonce rejection, and unsupported-attribution rate.

The result may say that a model was behaviourally sensitive to this frozen
public formulation. It must never say that a source was present in training
data or that the model possesses reliable introspective knowledge of training.

### AUTO-4 — eight-domain procedural transfer proxy

Generate exactly 48 records through a checked-in deterministic grammar: six
records in each of agriculture, energy, logistics, manufacturing, medical,
software, construction, and public services. Every record has four complete
candidate descriptions and a programmatically generated intended operation.
The blinded prompt contains no TRIZ term, principle number, canonical example,
or public-source wording.

The only primary score is label-free candidate-description scoring. The key is
sealed with the AUTO-2 key and accessed only at the shared analysis boundary.
Per-model summaries remain separated by domain and by matched control; no
cross-model pooling is permitted. The resulting construct is explicitly named
`automated_procedural_transfer_proxy`, not TRIZ transfer.

### AUTO-5 — all 24 permutations

Only after the complete schedule, inputs, keys, shard membership, and code
hashes are frozen, run all 24 label permutations for the same 24 records. The
permutations are lexicographically ordered and partitioned into six immutable
shards of four permutations each. A shard contains 96 prompt-condition records
per model and has one authorized attempt; an incomplete shard is terminal
`failed`, not repeatable.

This final diagnostic has no target-key access. It reports label-position
dependence and may strengthen or weaken AUTO-1's measurement conclusion; it
does not calculate factual or transfer accuracy.

## 5. Shared execution contract

Each material shard is local-only CPU float32, `local_files_only=True`, with
network and generation disabled. Before every heavy shard, the exact current
CCP binary must report `resource.decision=admit`, `admission.active=false`,
and `admission.queue_count=0`; any unknown, deny, busy, stale binary, or
unresponsive runtime fails closed.

The future authorization dossier shall bind the exact protocol hash, code hash,
all input and key hashes, shard list, models, runtime receipts, and an explicit
resource envelope. The default requested upper bounds are 1,800 seconds and
8 GiB peak RSS per shard, plus 128 MiB of new score/index output per model.
The eventual operator may approve stricter bounds. A model or target accessed
in a failed attempt is never retried without a new explicit authorization.

AUTO-1, AUTO-3, and AUTO-5 never open target content. AUTO-2 and AUTO-4 share
one combined sealed key. After all score-writing work is terminal, the analysis
process verifies every index and external score-asset hash, opens that combined
key exactly once, derives all seven models' automatic-reference results, and
records `sealed_target_read_count: 1`. A missing or mutated score asset blocks
the read and is terminal `failed`.

## 6. Statistics and interpretation

There is no pooled seven-model score. Every model receives a separate result
package and every stage receives a separate interpretation section.

| Stage | Primary descriptive endpoint | Permitted conclusion |
| --- | --- | --- |
| AUTO-1/5 | semantic invariance and label-free agreement | measurement behaviour only |
| AUTO-2 | automatic-reference accuracy and abstention by family | automated factual retrieval only |
| AUTO-3 | canonical/paraphrase/nonce contrasts | public-formulation sensitivity only |
| AUTO-4 | eight domain-separated label-free proxy margins | automated procedural proxy only |

For AUTO-4, the frozen descriptive threshold is a positive mean matched margin
in all eight domains and exact two-sided domain sign-flip `p <= 0.05`; failure
is `null`. Passing it is `auto_proxy_signal`, not evidence that a TRIZ expert
would validate either the cases or the claimed operator mapping. Sensitivity
analyses cannot replace the stated primary endpoints.

## 7. Required no-model implementation and validation

Before an authorization dossier can be emitted, implementation must provide:

1. independent AUTO protocol, model registry, schedule, key manifest, and
   approval-dossier schemas under `experiments/exp002-auto/` and `schemas/`;
2. deterministic fixture builders for the 178 factual records, four public
   formulations, eight-domain grammar, and six permutation shards;
3. target-free tokenizer and response-surface runners plus a sealed-key
   boundary that rejects any pre-analysis read;
4. synthetic adapters/tests proving no model, generation, network, or target
   access in no-model validation; wrong hashes, missing offsets, duplicate
   permutations, shard drift, and non-finite scores must fail closed;
5. immutable receipt/result/report/manifest builders and fresh-clone verifier
   that rejects missing or one-byte-mutated external score assets;
6. schema-cross-validation, repository-check registration, documentation audit,
   and an exact-head CCP qualification before material publication.

## 8. Publication, recovery, and completion

Every terminal state—`auto_proxy_signal`, `null`, `failed`, or
`non_interpretable`—is published with runtime, recovery, score-index, external
asset locator/hash, analysis, report, limitations, and manifest receipts.
Historical baseline results retain their original bytes and policy versions.

The no-model milestone is complete only after its public exact-head package
passes synthetic, schema, repository, and documentation gates. The material
milestone is complete only after a fresh clone verifies every published AUTO
package and rejects absent or mutated external assets. The entire programme is
complete only after all seven models have terminal packages for every approved
stage, or an explicit unavailable model/shard is recorded as terminal without
substitution.

## 9. Explicit non-goals and external gates

- This programme does not replace the three independent EXP-002 expert review
  packets, their answer key, or the independently authored EXP-002C corpus.
- It does not infer training-data membership from self-report or wording
  sensitivity.
- It does not permit model download, model execution, target-key creation from
  model output, tuning, retries, or publication before an exact hash-bound
  operator authorization.
- It does not authorize destructive disk cleanup, cache deletion, or OrbStack
  reset; these are operationally separate decisions.

The immediate next milestone is implementation and qualification of the
no-model contract. The next human gate after that is one explicit authorization
for the exact AUTO dossier, including its model/shard list and resource limits.
