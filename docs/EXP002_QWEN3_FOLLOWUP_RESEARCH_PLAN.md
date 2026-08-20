---
type: research-plan
title: Qwen3 Outlier Follow-up Research and Test Plan
description: Staged preregistration plan for separating label bias, declarative TRIZ knowledge, source familiarity, and blinded transfer.
status: exp002a_baseline_complete_exp002bcd_pending
version: 0.1.0
last_verified: 2026-08-20
---

# EXP-002 — Qwen3 outlier follow-up research and test plan

## Current implementation checkpoint

The no-model tranche and the guarded EXP-002A baseline runner are implemented
on branch `exp002-qwen3-followup`. The operator-approved seven-model dossier
was executed once per exact snapshot under the current CCP `origin/main`
binary. Every baseline package is terminal `null`, claim-free, and published
with one analysis-boundary target read. EXP-002A's label-permutation,
label-free, tokenizer-audit, direct-knowledge, source-familiarity, and new
corpus arms remain pending; this baseline does not retroactively satisfy those
arms.

The CCP `origin/main` coordination runbook is pinned to
`5f2ef665be4dc47fd354befcba53251a4e51744f`. Its exact binary was built in an
isolated temporary checkout because the installed binary was stale. Each run
was admitted with inactive/empty admission and a responsive empty runtime;
post-run handoffs returned the slot to `free`. Manual lock or quarantine
mutation was never used.

The no-model EXP-002B/C preparation now also includes a fail-closed answer-key
gate requiring three pseudonymous reviewers and an explicit disagreement policy,
plus an EXP-002C transfer-corpus schema/validator. The public transfer template
is intentionally empty (`design_ready_no_model`): it cannot be frozen until
independent authors, source-proximity audit, held-out/sealed-novel splits, and
power calibration are supplied. The validator rejects EXP-001 reuse, TRIZ/source
cues in the blinded primary, answer-bearing fields, duplicate fingerprints, and
shared expert/generator locators. These additions perform no model load,
generation, tokenizer access, or sealed-target read.

Separate `approval_requested` dossiers now exist for EXP-002B and EXP-002C.
They enumerate all seven exact snapshots, the fixed resource envelope, and the
forbidden actions, but deliberately carry no operator approval. The stage gate
requires the frozen answer key for B, the frozen transfer corpus and passed
power calibration for C, and a fresh CCP `Admit`/inactive/queue-0 snapshot
before any material call.

The injected runner now accepts the stage-specific dossiers and exposes a
target-free direct-question scoring boundary that copies only question identity,
prediction, and abstention metadata. It still refuses an unapproved dossier or
an unknown CCP state. Actual B/C adapters, expert answer keys, and the new
corpus remain intentionally unpopulated until their respective gates close.

The independent-review collection is now an explicit tracked no-model gate:
`experiments/exp002-qwen3-followup/expert-review-collection.json` is
`ready_for_collection` with exactly three required pseudonymous reviewers and
an immutable question-bank hash. Its validator requires full question-bank
coverage, distinct reviewers, rationale hashes, and explicit attestations that
neither models nor sealed targets were accessed. Empty packets are intentional;
no expert decisions have been fabricated or inferred.

The response-surface module now emits a deterministic schedule for the original,
cyclic, all-24, numeric, neutral-symbol, label-free, and answer-boundary
conditions, and classifies only `measurement_robust`,
`measurement_artifact_supported`, or `non_interpretable`. This classifier is a
diagnostic gate; it cannot replace the frozen primary endpoint.

The cross-study interpretation matrix is also tracked as a no-model artifact;
it prevents direct knowledge, source familiarity, and blinded transfer from
being collapsed into an undefined aggregate score.

### EXP-002A baseline result (2026-08-20)

All seven exact models produced an exploratory `null` terminal result under the
original 85-record A/B/C/D surface. The packages and dense-asset hashes are
bound by `results/exp002/preexecution/publication-manifest.json`.

| Model | Wall s | Peak RSS | Dense bytes | Terminal |
| --- | ---: | ---: | ---: | --- |
| Pythia-70M | 312.35 | 1,823,506,432 | 15,798 | null |
| SmolLM2-360M | 367.48 | 3,011,559,424 | 15,803 | null |
| Qwen3-0.6B | 950.23 | 5,742,231,552 | 15,915 | null |
| GPT-2 | 322.30 | 1,996,898,304 | 15,805 | null |
| SmolLM2-135M | 342.61 | 2,291,466,240 | 15,775 | null |
| GPT-Neo-125M | 326.16 | 2,068,135,936 | 15,771 | null |
| Qwen2.5-0.5B | 926.15 | 4,766,613,504 | 15,871 | null |

Every receipt records CPU float32, network/generation disabled, one model run,
one sealed-target read, empty claim IDs, and `evidence_eligible=false`. These
results are baseline observations only; they do not test the remaining
response surfaces or direct TRIZ knowledge questions.

## 1. Purpose

This plan defines the next research programme motivated by the unusual
`Qwen/Qwen3-0.6B-Base` result in EXP-001. It does not amend, rerun, or reinterpret
the seven published comparative packages. It creates new, separately frozen
tests designed to distinguish four explanations that the current evidence
cannot separate:

1. a multiple-choice label or tokenizer artifact;
2. explicit, declarative knowledge of TRIZ and its public sources;
3. source familiarity or training-data overlap;
4. source-independent transfer of TRIZ-like operators to new problems.

The programme is staged so that a cheap measurement-validity failure stops an
expensive scientific run. Every stage remains exploratory until its construct,
controls, statistics, and expert-validation obligations are satisfied.

## 2. Evidence motivating the plan

The frozen Qwen3 primary is terminal `null`, not positive:

| Quantity | Qwen3 result |
| --- | ---: |
| Mean domain delta | `+0.9323` |
| Exact two-sided domain sign-flip p-value | `0.0625` |
| Bootstrap 95% interval | `[+0.5353, +1.2063]` |
| Positive domains | `5/6` |
| Non-positive domain | Agriculture, `-0.0043` |

Its effect size is much larger than that of the six comparators, but it misses
two frozen positive conditions: `p <= 0.05` and every domain direction positive.
With only six domain blocks, the exact null contains `2^6 = 64` sign patterns;
the observed `0.0625` is therefore four of 64 patterns. A later study should use
more independently held-out domains, not lower the threshold or remove the
agriculture block.

The public response indices reveal a second anomaly. Across the 24 blinded
transfer records, the highest-scoring label is:

| Model group | A | B | C | D |
| --- | ---: | ---: | ---: | ---: |
| Qwen3-0.6B-Base | 6 | 6 | 6 | 6 |
| Each of the other six models | 24 | 0 | 0 | 0 |

These are not correctness counts. They are the labels with the greatest
teacher-forced continuation score before the sealed answer key is applied.
Qwen3 may be responding to option meaning while the other models express an
`A` prior, but label tokenization, option position, prompt punctuation, and
model calibration can produce the same pattern.

The implementation audit and external methodological literature support this
concern:

- EXP-001 scores the mean log-probability of the appended answer label, not the
  full candidate description.
- [Zheng et al.](https://arxiv.org/abs/2309.03882) show that model-specific
  option-ID token priors can materially change multiple-choice results.
- [Sanz-Guerrero et al.](https://aclanthology.org/2025.emnlp-main.988/) show
  that small answer-boundary tokenization choices can change accuracy and model
  rankings.
- The official [Qwen3 Base documentation](https://github.com/QwenLM/Qwen3/blob/main/docs/source/getting_started/concepts.md)
  identifies this checkpoint as a pretrained Base model, not an instruction or
  chat model. Direct questions therefore require Base-appropriate completion
  and scoring contracts.

The detailed evidence review is maintained in
[`EXP001_QWEN3_OUTLIER_ANALYSIS.md`](./EXP001_QWEN3_OUTLIER_ANALYSIS.md).

## 3. Epistemic distinctions

The follow-up must keep five questions physically and statistically separate:

| Axis | Question | What a positive result would mean |
| --- | --- | --- |
| Self-report | Does the model say it knows TRIZ? | Only that this completion was likely; never proof of training provenance |
| Declarative knowledge | Can it retrieve names, definitions, tools, and relations? | Behavioural familiarity or memorized/learned knowledge |
| Source fingerprint | Is it unusually sensitive to canonical source wording? | Possible source familiarity; not proof of dataset membership |
| Applied competence | Can it use stated TRIZ knowledge correctly? | Source-exposed competence, not rediscovery |
| Blinded transfer | Can it apply the operator without TRIZ names or source cues? | A candidate weak latent-operator signal if all controls pass |

No answer to “Were you trained on TRIZ?” can establish training-data membership.
Language models do not have a reliable introspective inventory of their training
records. Such answers may be collected as qualitative metadata but are excluded
from every scientific endpoint.

## 4. Research questions and competing hypotheses

### RQ1 — Is the Qwen3 separation robust to the response surface?

- **H1a, semantic sensitivity:** Qwen3 retains its advantage after balanced
  label permutations, label-free candidate scoring, and answer-boundary
  normalization.
- **H1b, measurement artifact:** the advantage follows a label, position, or
  tokenization condition and collapses under a semantically equivalent response
  surface.

### RQ2 — Does Qwen3 possess explicit TRIZ knowledge?

- **H2a, declarative familiarity:** Qwen3 retrieves source-backed TRIZ concepts,
  principle names, matrix direction, and tool relationships above matched
  controls.
- **H2b, generic plausibility:** Qwen3 produces convincing engineering language
  but cannot distinguish real TRIZ concepts from matched invented concepts.

### RQ3 — Is the behaviour compatible with source familiarity?

- **H3a, source familiarity:** canonical or near-canonical formulations receive
  an advantage beyond independently paraphrased and matched non-TRIZ controls.
- **H3b, abstraction rather than wording:** performance is stable across source
  paraphrases and does not depend on canonical phrasing.

### RQ4 — Does any signal survive genuinely new blinded transfer?

- **H4a, operator transfer:** Qwen3 succeeds on independently authored problems,
  new domains, balanced positions, and label-free scoring without source cues.
- **H4b, retrieval or benchmark interaction:** performance is confined to
  explicit TRIZ questions, familiar wording, current domains, or the original
  answer format.

### RQ5 — Is Qwen3 special, or is the result explained by scale/provider lineage?

The same frozen tests must be run independently on all seven exact snapshots.
Qwen2.5-0.5B is the most informative within-provider control. SmolLM2-135M and
360M are the scale-family control. Pythia, GPT-2, and GPT-Neo expose older
decoder and tokenizer behaviours. Scores remain model-separated and are never
pooled into one estimator.

## 5. Programme structure

The programme consists of four studies with explicit stop/go gates.

```text
EXP-002A measurement validation
        |
        | label-robust signal
        v
EXP-002B direct TRIZ knowledge and source familiarity
        |
        | interpretable declarative profile
        v
EXP-002C new blinded transfer replication
        |
        | expert-valid, control-valid transfer
        v
EXP-002D representation and causal follow-up
```

EXP-002D is out of scope until the previous three studies are published.

## 6. EXP-002A — measurement-validity study

### 6.1 Goal

Determine whether the Qwen3 outlier survives changes that preserve the semantic
task while changing labels, positions, and token boundaries.

### 6.2 No-model tokenizer audit

Before any model output, record for every exact tokenizer:

- token IDs and decoded tokens for ` A`, ` B`, ` C`, and ` D`;
- continuation token count for each label;
- prefix/full token-boundary agreement;
- BOS, EOS, padding, and special-token behaviour;
- token counts for every prompt and candidate description;
- differences between transfer and lexical-control prompt lengths;
- tokenizer version and exact runtime-file hashes.

This audit must not load model weights or inspect a sealed key. Unknown or
inconsistent tokenization produces `incompatible`, not an inferred repair.

### 6.3 Response-surface conditions

Use the same public task semantics under independently frozen conditions:

1. original `A/B/C/D` labels;
2. four cyclic permutations that balance every option across every position;
3. all 24 label permutations for Qwen3, Qwen2.5, and one `A`-dominant control;
4. numeric labels `1/2/3/4`;
5. neutral symbols whose token lengths are matched per tokenizer;
6. label-free scoring of the complete candidate description;
7. answer-boundary variants defined before output, including space-plus-label
   and a tokenizer-safe delimiter.

The full 24-permutation arm is a second-stage diagnostic. The balanced cyclic
screen runs first so an obvious artifact does not trigger unnecessary material
execution.

### 6.4 Metrics

- top-label frequency and entropy;
- option-permutation invariance;
- accuracy range across label permutations;
- expected-label margin after estimating the label prior;
- divergence between raw and prior-adjusted choice distributions;
- agreement between label-only and candidate-description scoring;
- original transfer-minus-control delta under every response surface.

### 6.5 Decision rule

The Qwen3 signal is `measurement_robust` only if its direction survives the
predeclared balanced permutations and label-free condition without one label or
position explaining the result. It is `measurement_artifact_supported` if the
effect follows label identity, option position, or answer-boundary tokenization.
Intermediate or incompatible outcomes are published as such. No condition may
replace the original EXP-001 primary retrospectively.

## 7. EXP-002B — direct TRIZ knowledge and familiarity study

### 7.1 Goal

Implement the proposed direct questions while distinguishing self-report,
declarative recall, source familiarity, and applied competence.

### 7.2 Two response modes

Every knowledge module should have two separately scored modes:

1. **Teacher-forced structured probes.** Multiple-choice, completion, or ranking
   prompts with label permutation and a label-free counterpart.
2. **Bounded deterministic completion.** Greedy, no-sampling continuation with a
   fixed token ceiling and no chat template for Base models.

Generation is a new capability and requires its own frozen authorization. A
Base model's inability to follow a conversational instruction is not evidence
that the underlying knowledge is absent; the teacher-forced mode is therefore
the primary automated measure.

### 7.3 Module B1 — non-evidential self-report

Collect, but do not score as provenance:

- “Are you familiar with TRIZ?”
- “What does TRIZ stand for?”
- “Have you encountered the 40 Inventive Principles?”
- “Do you know the 2003 Contradiction Matrix?”
- “Can you identify whether this concept is part of TRIZ?”

The first, third, and fourth questions are self-report metadata. The acronym
expansion and concept-identification questions may also appear in the factual
modules with source-backed keys.

### 7.4 Module B2 — foundational TRIZ concepts

Test source-backed recognition and completion for:

- technical and physical contradictions;
- Ideal Final Result;
- resources;
- separation principles;
- substance-field analysis;
- trends of engineering-system evolution;
- ARIZ;
- nine windows/system operator;
- effects and knowledge-base use.

Include matched generic design concepts and plausible invented names. Correct
abstention on fabricated concepts is part of the score.

### 7.5 Module B3 — the 40 Inventive Principles

Use all 40 principles across balanced tasks:

- name-to-definition recognition;
- definition-to-name retrieval;
- real-principle versus invented-principle discrimination;
- adjacent-principle discrimination;
- independent example-to-principle mapping;
- short independently authored example generation;
- explicit “insufficient information” cases.

Do not use canonical source examples in the scored blind arm. Direct recall of
all 40 names is descriptive because naming traditions vary across sources and
translations. Principle application receives a separate score and requires an
expert rubric before claim promotion.

### 7.6 Module B4 — Matrix 2003

Test:

- the ordered meaning of improving-row versus worsening-column;
- reversal of the parameter direction;
- recognition of a verified sparse recommendation set;
- rejection of an unverified or reversed cell;
- abstention when the fixture does not establish a cell;
- distinction between the original matrix and Matrix 2003.

Only the existing double-checked sparse fixture may supply automatic keys.
Bulk matrix content and copyrighted PDF pages remain external.

### 7.7 Module B5 — TRIZ tool relationships

Use the rights-aware Panitz fixture to test supported, uncertain, and
not-established edges. Add broader tool-order questions only after expert
review. A model must be rewarded for abstention when a relationship is not
supported; plausible narration is not equivalent to an established edge.

### 7.8 Module B6 — hallucination and canary controls

Create source-plausible but nonexistent items, for example:

- invented principle names;
- nonexistent matrix parameter numbers;
- reversed or unsupported tool edges;
- fabricated TRIZ acronyms;
- descriptions mixing two real principles into one false entry.

Canaries must be generated and frozen without observing model responses. They
measure whether apparent knowledge is calibrated or merely fluent.

### 7.9 Knowledge metrics

Report per module and per model:

- exact or source-backed accuracy;
- precision and recall for the 40-principle inventory;
- abstention precision and recall;
- false-accept rate on invented concepts;
- label-permutation robustness;
- bounded-completion factual coverage;
- unsupported-claim rate;
- expert-adjudication status.

No aggregate “TRIZ intelligence” score is permitted. Modules remain separate
because recalling principle names, using a matrix, and applying an operator are
different constructs.

## 8. EXP-002B source-familiarity sub-study

This sub-study asks whether the model behaves as if it is familiar with the
public source family. It does not claim training-set membership.

Construct matched prompt sets containing:

1. a short source-canonical phrase within quotation limits;
2. an independently authored paraphrase preserving meaning;
3. a lexical-control sentence from a non-TRIZ design source;
4. a nonce-edited version with one key relation changed;
5. a source-attribution question with “unknown” available.

Measure normalized continuation likelihood, attribution accuracy, exact phrase
completion, paraphrase stability, and nonce-edit rejection. Compare these
quantities with matched public engineering sources not associated with TRIZ.
Any canonical advantage is reported as `behavioural_source_familiarity`; it is
not labelled contamination without externally verifiable membership evidence.

## 9. EXP-002C — new blinded transfer replication

### 9.1 Goal

Test whether the signal survives after the measurement surface has been
validated and all explicit TRIZ/source cues are removed.

### 9.2 New corpus

Build an entirely new target-free fixture with:

- at least eight, preferably ten to twelve, held-out domains;
- at least two independent problem families per domain;
- multiple independently authored replicates per family;
- no reuse of EXP-001 prompts or option descriptions;
- no TRIZ names, principle numbers, canonical examples, Matrix cells, or tool
  names in the primary arm;
- label-free candidate scoring as the primary response surface;
- balanced, randomized option order as a diagnostic surface;
- expert labels physically separated from author intent and model outputs.

Increasing the domain count improves both scientific coverage and the coarse
resolution of the exact sign-flip test. The final domain/family counts must be
set by synthetic power calibration before output, not chosen to make Qwen3
cross `0.05`.

### 9.3 Required controls

- lexical- and length-matched non-TRIZ controls;
- generic transformation heuristics;
- adjacent and easily confused principles;
- random labels and shuffled solutions;
- option-order and label permutations;
- source-exposed competence kept physically separate;
- non-inventive common-sense solutions;
- near-duplicate/source-proximity audit;
- one or more domains with vocabulary unlike the engineering-heavy source set.

### 9.4 Primary and secondary outcomes

Freeze one primary operator or one small family of operators. The primary is
held-out-domain transfer against the matched controls under label-free scoring.
Direct knowledge, source familiarity, exposed competence, Matrix, Panitz, and
generation quality are secondary and cannot rescue a failed primary.

The statistical contract must declare before model access:

- domain/family grouping;
- exact permutation procedure;
- multiplicity handling;
- bootstrap or interval procedure;
- minimum domain support;
- effect-size threshold;
- all-domain or majority-domain direction rule;
- terminal `positive`, `null`, `failed`, `non_interpretable`, and
  `incompatible` conditions.

## 10. Cross-study interpretation matrix

| Direct TRIZ knowledge | Source fingerprint | Blinded transfer | Interpretation |
| --- | --- | --- | --- |
| Low | Low | Low | No evidence under these probes |
| High | High | Low | Source familiarity/retrieval without transfer |
| High | Low or uncertain | Low | Declarative competence without operator transfer |
| High | High | High | Transfer may be source-derived; contamination/familiarity remains open |
| Low | Low | High | Most interesting latent-transfer pattern, but requires expert and causal validation |
| Low | High | High | Possible implicit source familiarity; provenance remains unresolved |

This matrix prevents direct-question success from being misreported as latent
rediscovery. It also prevents direct-question failure from erasing a genuine
blinded-transfer signal.

## 11. Model and runtime policy

The first confirmatory tranche should reuse the seven exact, integrity-receipted
Base checkpoints already studied. No model may be substituted after results are
visible. Any future instruction-tuned Qwen model is a separate condition with a
different research question and cannot be pooled with Qwen3-0.6B-Base.

Before each material run:

- freeze protocol, fixtures, target hashes, code hashes, exact model identity,
  tokenizer audit, and statistics;
- obtain explicit operator authorization bound to the dossier hash;
- require CCP resource `Admit`, inactive admission, and an empty queue;
- use local-only exact snapshots, no network, and receipted runtime limits;
- open the sealed answer key only at the declared analysis boundary;
- prohibit tuning, model substitution, and retry after model or target access;
- publish every terminal outcome.

Generation, if approved for the direct-question arm, must use deterministic
greedy decoding, a fixed maximum continuation length, and a prompt contract
appropriate to Base models. It remains separate from teacher-forced and
label-free primary scores.

## 12. Data, source, and rights policy

- The public 40-principle, Matrix 2003, and Panitz sources remain authoritative
  external references.
- Do not vendor third-party PDF bytes, screenshots, bulk Matrix tables, or long
  source passages under the repository licence.
- Store provenance, locators, independently authored paraphrases, short lawful
  excerpts when necessary, and rights flags.
- Separate source-backed keys, expert labels, generator intent, public prompts,
  and model outputs.
- Keep canonical-source exposure out of the blinded-transfer primary.
- Record every use of a source phrase in a rights and proximity receipt.

## 13. Preregistration and implementation deliverables

Each study requires:

1. a canonical Markdown specification;
2. a machine-readable protocol and analysis plan;
3. strict schemas for prompt inventory, target key, run receipt, statistical
   result, and publication manifest;
4. a source/right/proximity manifest;
5. a model/tokenizer/runtime registry with exact hashes;
6. synthetic fixtures that exercise every terminal state;
7. mutation tests for labels, options, token boundaries, hashes, and targets;
8. an approval dossier that states material limits and forbidden actions;
9. immutable per-model result packages;
10. a fresh-clone verifier that rejects missing or mutated external assets;
11. a limitations report and cross-study interpretation matrix;
12. updates to the master plan, roadmap, chronology, and persistent goal.

## 14. Efficient execution order

1. Publish this plan and the Qwen3 outlier analysis as documentation only.
2. Complete the no-model tokenizer and response-index audit.
3. Build and synthetically validate EXP-002A.
4. Freeze and run the balanced cyclic label screen.
5. Run the full permutation and label-free diagnostics only if the screen is
   informative and material limits are approved.
6. Build the direct TRIZ question bank, false-concept canaries, and source
   familiarity controls without model access.
7. Obtain expert review of factual keys and application rubrics.
8. Freeze and run EXP-002B independently per model.
9. Decide whether evidence justifies the larger EXP-002C corpus.
10. Build, freeze, authorize, and run EXP-002C once per model.
11. Consider representation or causal work only if measurement robustness,
    construct validity, and blinded transfer all pass.

## 15. Stop/go criteria

- **Stop latent interpretation** if the Qwen3 effect follows labels, positions,
  or token boundaries in EXP-002A.
- **Continue as competence research only** if direct TRIZ knowledge is strong
  but blinded transfer is null.
- **Escalate source audit** if canonical wording strongly outperforms
  independently authored paraphrases.
- **Proceed to EXP-002C** only when the response surface is measurement-robust
  and the new corpus is independently reviewed.
- **Proceed to causal analysis** only after a preregistered, expert-valid,
  control-valid blinded-transfer result.

Every stop decision is a publishable result. A near-threshold value, attractive
model narrative, or post-hoc domain selection must never override a failed
gate.

## 16. Completion criteria

This research programme is complete only when:

- label/tokenizer explanations have been directly tested;
- direct TRIZ knowledge has been measured with factual, false-concept, and
  abstention controls;
- source familiarity has been reported without unsupported training-provenance
  claims;
- a new independently authored blinded-transfer study has reached a terminal
  state or a documented stop gate;
- all seven model outcomes and limitations are published separately;
- expert-validation status is explicit;
- no result is promoted beyond its evidence profile.

Until those conditions are met, the Qwen3 result remains a scientifically
valuable anomaly and hypothesis generator, not evidence that the model has
rediscovered TRIZ.
