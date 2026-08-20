# Why Qwen3-0.6B Is the EXP-001 Outlier

**Status:** exploratory analysis note
**Date:** 2026-08-20
**Protocol:** `exp001-reference-comparative-v1.0.0`
**Model:** `Qwen/Qwen3-0.6B-Base@da87bfb608c14b7cf20ba1ce41287e8de496c0cd`

## Executive conclusion

Qwen3 is a real descriptive outlier in the current seven-model comparison, but it is **not a positive confirmatory result**. Its frozen primary result is terminal `null`: mean domain delta `+0.9323`, bootstrap 95% interval `[+0.5353, +1.2063]`, but exact two-sided domain sign-flip `p = 0.0625` and one domain direction is slightly negative (`agriculture = -0.0043`). The preregistered positive rule requires both `p <= 0.05` and every domain delta to be positive.

The most important finding from the implementation audit is that EXP-001 does not score the four option descriptions directly. It renders the descriptions into a prompt, appends a label (` A`, ` B`, ` C`, or ` D`), and scores the mean teacher-forced log-probability of the label continuation. The sealed-key margin is the score of the expected label minus the mean score of the three other labels. Therefore the result can reflect semantic transfer, but it can also reflect tokenizer-, label-, formatting-, or calibration-specific behavior.

The strongest current interpretation is therefore:

> Qwen3 shows a large and reproducible-looking descriptive separation between the TRIZ-blinded transfer prompts and their lexical controls under this exact label-likelihood measurement, but the present evidence cannot distinguish a genuine latent-operator signal from a model–prompt–tokenizer interaction, label-position sensitivity, or source/task familiarity.

No general claim about TRIZ, invention, or latent rediscovery is justified.

## What was actually measured

The frozen primary contains 24 units, six domains, two problem families per domain, and two replicates per family. For each unit, the model is scored on:

1. a TRIZ-blinded transfer prompt;
2. a lexical-matched control prompt;
3. a source-exposed descriptive prompt, excluded from the primary.

Each public record presents four labelled options, `A` through `D`. The runner makes four teacher-forced score calls per record and never supplies the expected answer while generating the public response index. At the analysis boundary, the one sealed key maps each record to its expected label. For each primary unit:

```text
blinded_margin     = score(expected label) - mean(score(other three labels))
lexical_margin     = score(expected label) - mean(score(other three labels))
unit_delta         = blinded_margin - lexical_margin
domain_delta       = mean(unit_delta for the four units in that domain)
```

The final primary statistic is the mean of the six domain deltas. The exact null distribution enumerates all `2^6 = 64` domain sign flips; the positive rule is fixed in `experiments/exp001-comparative-reference/analysis-plan.json`.

The score implementation is bound by:

- [`src/latent_triz/exp001_r3_response_execution.py`](../src/latent_triz/exp001_r3_response_execution.py), which renders the prompt and calls the adapter for each label;
- [`src/latent_triz/exp001_comparative_adapter.py`](../src/latent_triz/exp001_comparative_adapter.py), which appends a label and scores its continuation;
- [`src/latent_triz/exp001_r3_response_adapter.py`](../src/latent_triz/exp001_r3_response_adapter.py), which returns the **mean** log-probability of the continuation tokens;
- [`src/latent_triz/exp001_r3_runner.py`](../src/latent_triz/exp001_r3_runner.py), which converts scores to sealed-key margins;
- [`src/latent_triz/exp001_r3_analysis.py`](../src/latent_triz/exp001_r3_analysis.py), which performs the frozen domain-level test.

This distinction is central: the task is a causal-LM choice-label likelihood test, not a direct evaluation of generated explanations or of the textual option descriptions.

## The observed comparison

All seven models are terminal `null` under the same non-pooled rule. The table reports the frozen primary only.

| Model | Mean domain delta | Exact two-sided `p` | Bootstrap 95% interval | Positive-domain count |
| --- | ---: | ---: | ---: | ---: |
| Qwen3-0.6B-Base | **+0.9323** | **0.0625** | **[+0.5353, +1.2063]** | 5/6 |
| GPT-Neo 125M | +0.0155 | 0.6875 | [-0.0724, +0.0925] | 4/6 |
| GPT-2 | +0.0264 | 0.3125 | [-0.0170, +0.0648] | 4/6 |
| Pythia 70M | +0.0545 | 0.6875 | [-0.1485, +0.2956] | 3/6 |
| SmolLM2 135M | +0.0420 | 0.5000 | [-0.0621, +0.1418] | 4/6 |
| SmolLM2 360M | -0.0247 | 0.65625 | [-0.1095, +0.0602] | 3/6 |
| Qwen2.5 0.5B | -0.0059 | 0.96875 | [-0.1172, +0.1411] | 2/6 |

Qwen3's domain deltas are:

| Domain | Delta |
| --- | ---: |
| Agriculture | -0.0043 |
| Energy | +1.2747 |
| Logistics | +1.2437 |
| Manufacturing | +0.8481 |
| Medical | +1.1298 |
| Software | +1.1020 |

The effect is consequently not a uniform six-domain result. It is five large positive domain shifts plus an agriculture value effectively at zero. That pattern is compatible with a genuine task interaction, but it is also exactly the kind of concentration that requires domain-specific diagnostics before interpretation.

The exact `p = 0.0625` is four of the 64 sign-flip outcomes, so it is one discrete step above the predeclared `0.05` cutoff. The bootstrap interval and the permutation test are not interchangeable: the interval resamples the six observed domain values, while the sign-flip test evaluates the symmetry of domain directions under the frozen paired design. The positive rule intentionally requires both.

## A useful diagnostic in the public response index

Without reopening the sealed key, a read-only scan of the published response indices shows a striking label-surface difference. On the 24 blinded transfer records:

- every comparator other than Qwen3 selected `A` as the highest-scoring label on all 24 records;
- Qwen3's highest-scoring label was distributed evenly: `A=6`, `B=6`, `C=6`, `D=6`.

This does **not** prove that Qwen3 understood the intended option. It does show that Qwen3 reacted to the option surface in a way the smaller comparators did not, whereas the other models exhibited a strong fixed-label prior under this prompt format. It also makes the label/tokenizer measurement boundary the first place to investigate. The response-index scan is descriptive only and does not replace the frozen result.

## Official facts about the exact Qwen3 checkpoint

The official [pinned Qwen3 configuration](https://huggingface.co/Qwen/Qwen3-0.6B-Base/blob/da87bfb608c14b7cf20ba1ce41287e8de496c0cd/config.json) identifies `Qwen3ForCausalLM`, `model_type: qwen3`, 28 transformer layers, hidden size 1024, 16 query heads and 8 key/value heads, tied word embeddings, a 32,768-token context, and vocabulary size 151,936. The experiment deliberately loaded the already acquired snapshot in local CPU `float32`; the published config's `bfloat16` metadata was not used as the runtime dtype.

The [official Qwen3 model card](https://huggingface.co/Qwen/Qwen3-0.6B-Base) describes this checkpoint as a 0.6B **pretrained base** causal LM and reports a Qwen3 corpus of approximately 36 trillion tokens across 119 languages, with increased coding, STEM, reasoning, book, multilingual, and synthetic data. The [Qwen3 technical report](https://arxiv.org/abs/2505.09388) additionally describes Qwen3 dense architecture changes including grouped-query attention, RoPE, RMSNorm, removal of QKV bias, and QK normalization. The [official release article](https://qwenlm.github.io/blog/qwen3/) describes three pretraining stages: broad language/general knowledge, increased STEM/coding/reasoning data, and long-context training.

These facts make real model differences plausible, but they do not identify which difference caused this result. Qwen3 is not an isolated size control against Qwen2.5: the two checkpoints differ in architecture, tokenizer/configuration, data, training recipe, and release generation.

The official [Qwen3 concepts documentation](https://github.com/QwenLM/Qwen3/blob/main/docs/source/getting_started/concepts.md) is especially important for interpreting this run:

- `-Base` means pretrained and **not trained to use the predefined chat template**;
- Qwen uses byte-level BPE and a large vocabulary;
- Qwen's training conventions do not prepend a fixed BOS token to each packed sequence.

The comparative runner uses plain text prompts and does not apply a chat template, which is consistent with a Base checkpoint. It also explicitly verifies the tokenizer prefix boundary before scoring. This rules out one common accidental misuse, but it does not rule out all tokenization or label-surface effects.

## Relevant external methodological evidence

The concern about the label surface is not specific to this repository. Two primary studies are directly relevant:

- [Zheng et al., *Large Language Models Are Not Robust Multiple Choice Selectors*](https://arxiv.org/abs/2309.03882) report systematic option-ID selection bias across models and benchmarks. Their analysis attributes much of the effect to token-level prior mass on labels such as `A`, `B`, `C`, and `D`, with additional position effects. They propose estimating the label prior under option permutations rather than treating the raw label likelihood as a pure content signal.
- [Sanz-Guerrero et al., *Mind the Gap: A Closer Look at Tokenization for Multiple-Choice Question Answering with LLMs*](https://aclanthology.org/2025.emnlp-main.988/) report accuracy changes up to 11% and reshuffled model rankings from seemingly minor differences in how the answer-space and answer letter are tokenized. Their result is especially relevant here because the adapter explicitly scores the continuation after a space-plus-label boundary.

These papers do not invalidate EXP-001. They change the burden of interpretation: before treating the Qwen3 separation as evidence of a latent TRIZ operator, the study must show that the separation survives label-prior estimation, option permutation, and exact tokenizer diagnostics. The current `A=24` pattern in the six comparator indices and Qwen3's `A=B=C=D=6` pattern make those controls empirically necessary rather than merely theoretical.

## Plausible explanations, ranked

### 1. Measurement and label-surface interaction — highest priority

The primary score is a label continuation score, not a score of the candidate description. A model can improve the primary margin by assigning the expected letter a higher conditional probability, even when its internal reason is unknown. Because the four option descriptions are present immediately before the answer-label instruction, label probabilities can depend on:

- the position and wording of each option;
- repeated `A.`, `B.`, `C.`, `D.` markers;
- punctuation and whitespace before the answer label;
- whether a label is one token or multiple tokens for that tokenizer;
- model-specific priors over answer letters;
- the interaction between the answer instruction and the preceding option list.

The public index is consistent with this concern: all non-Qwen3 models choose `A` on every blinded transfer row, while Qwen3 varies across all four labels. This could mean better semantic use of the options, but it could equally mean that Qwen3 has a different calibration/label prior.

### 2. Tokenization and continuation-length effects — high priority

The adapter verifies that the full prompt begins with the tokenized prefix, then scores the appended label continuation. The score is averaged over continuation tokens, which prevents a simple sum-length advantage but does not make different tokenizations equivalent. Qwen3's vocabulary and special-token inventory differ substantially from GPT-2/Pythia/GPT-Neo and from SmolLM2. The exact Qwen config has 151,936 vocabulary entries; the official Qwen documentation describes the underlying byte-level BPE and its large multilingual vocabulary.

Consequences that must be measured, not assumed:

- the space-plus-label strings may have different token counts across models;
- the same English word may split differently in prompt and option text;
- special-token insertion may change the first-token context;
- the final label may be represented by a different token boundary;
- the mean log-probability may have different variance when a label is one token versus several.

The prefix-drift guard prevents silent misalignment, but it does not make token boundaries cross-model comparable.

### 3. Qwen3 pretraining mixture and scale-efficient recipe — plausible

Official Qwen sources explicitly report a much larger and broader Qwen3 pretraining corpus than Qwen2.5, including STEM, coding, reasoning, multilingual, book, and synthetic data. The release article also reports a staged pretraining process and scaling-law-guided tuning. Those changes could make Qwen3 more sensitive to abstract relations such as “localize control”, “counterbalance”, “use another dimension”, or “adapt to changing conditions”.

This is a credible explanation for the five-domain pattern, especially because the domains are engineering-flavoured. It is not a causal conclusion: the comparison changes many variables simultaneously, and no training-data membership audit has been performed.

### 4. Architecture and representation geometry — plausible, not isolated

Qwen3 has 28 layers, 1024 hidden dimensions, GQA, tied embeddings, and QK normalization; Pythia is GPT-NeoX, GPT-2/GPT-Neo use older decoder designs, and SmolLM2 uses a Llama-family architecture. A deeper/wider model with a different attention normalization can produce cleaner conditional distinctions in a label-choice surface.

However, model size alone is not enough: Qwen2.5-0.5B is close in scale and remains null. The Qwen3-versus-Qwen2.5 contrast points toward a combination of recipe, tokenizer, architecture, and data rather than a simple parameter-count law.

### 5. Domain and fixture interaction — high priority for follow-up

The public fixture uses six domains and TRIZ-derived transfer concepts, while the lexical control changes the surface wording. The transfer prompts contain regular engineering language (local control, nesting, compensation, dimensional access, adaptation, porous structures, phase changes, and copying/proxies). Qwen3's reported STEM/coding/reasoning mixture may interact especially well with this vocabulary or with familiar problem-solution templates.

The agriculture domain is the exception: its delta is essentially zero. That could reflect domain-specific lexical mismatch, a different option distribution, or an actual absence of transfer. It could also be a chance sign at the domain-block level. No post-hoc domain removal or retuning is allowed for the current result.

### 6. Source familiarity or contamination — possible, currently unproven

The fixture records are derived from public TRIZ reference material. A large pretraining corpus may contain TRIZ, engineering, or near-duplicate problem descriptions. The Qwen3 sources do not provide enough public information to prove or disprove example-level overlap with this exact fixture. A near-duplicate search and source-membership audit are therefore required before treating a positive-looking result as latent rediscovery.

### 7. Runtime and numerical differences — lower priority

The Qwen3 receipt records a local CPU `float32` run, disabled network and generation, one model execution, one sealed-target read, 948.8 seconds wall time, and 4,995,792,896 bytes peak RSS. These values are within the frozen ceilings. Since the comparator protocol also specifies CPU `float32`, runtime dtype is not an obvious Qwen3-only confound. A `bfloat16` versus `float32` replication would be a separate, preregistered numerical-sensitivity study, not a repair of this run.

## Why the secondary endpoints do not explain the outlier

The descriptive Matrix endpoint is 6/9 for Qwen3, the same as most comparators, and the Panitz tool-edge endpoint is 4/4, which is a ceiling for every model. These endpoints therefore do not independently establish a Qwen3 advantage. The primary outlier comes from the blinded-transfer-minus-lexical-control margin, not from a broad improvement across every TRIZ reference task.

## Discriminating tests for a future dossier

These are proposals only. They require a new frozen dossier and authorization; they must not be applied retroactively to the consumed one-shot run.

1. **Tokenizer audit without model output.** For every exact tokenizer, record token IDs, token counts, special tokens, prefix/full boundary, and the tokenization of ` A`, ` B`, ` C`, and ` D`. Report per-model continuation lengths and domain/condition distributions.
2. **Label randomization.** Reassign the same option descriptions to randomized labels in a new public fixture. A genuine semantic effect should survive label permutations; a label-prior effect should move with the labels.
3. **Description scoring.** Add a separately preregistered condition that scores the full candidate description (or a normalized continuation) rather than only the answer letter. Do not substitute it for the current primary.
4. **Length-normalization sensitivity.** Compare mean log-probability, summed log-probability, and a fixed first-label-token score. These are descriptive diagnostics only; they must be frozen before model access.
5. **Option-order controls.** Randomize option order while preserving the correct semantic choice. This tests positional and formatting artifacts.
6. **Prompt-format control.** Keep Qwen3-Base on plain causal prompts, as required by the official Base documentation; test any chat-template condition only as a separate model/condition, never as an unannounced repair.
7. **Domain holdout replication.** Freeze a new set of domains and problem families before access. The agriculture near-zero result makes domain replication more informative than adding more variants to the same six domains.
8. **Qwen2.5/Qwen3 paired comparison.** Use identical prompt/label randomization and tokenizer diagnostics to separate the provider-generation change from the generic size effect. Do not pool the two models' scores.
9. **Calibration diagnostics.** Record entropy, top-label margin, and label-frequency concentration. The current Qwen3 transfer top-label count is `6/6/6/6`, while other models are `24/0/0/0`; this is a key predeclared diagnostic.
10. **Contamination audit.** Perform public near-duplicate and n-gram/MinHash searches against the fixture and cited sources. Report overlap as unknown when the training corpus cannot be audited.
11. **Independent TRIZ-neutral controls.** Add relation-transfer tasks with no TRIZ source exposure and no TRIZ vocabulary. This tests whether the effect is general relational reasoning rather than source familiarity.
12. **Fresh-model replication.** Only after the above contract is reviewed should a new exact model run be authorized. No retry or tuning of the current sealed run is permitted.

## Scientific interpretation

The current evidence supports one narrow statement:

> Under the frozen EXP-001 automated choice-label protocol, Qwen3-0.6B-Base produced a much larger descriptive blinded-transfer-minus-lexical-control signal than the six comparator models, but the predeclared terminal result remains `null` because `p=0.0625` and the agriculture domain was not positive.

It does **not** support any of the following:

- that Qwen3 rediscovered TRIZ;
- that Qwen3 learned the 40 inventive principles;
- that the result is independent of tokenizer, option labels, or prompt format;
- that the signal generalizes beyond these six domains and this fixture;
- that a positive bootstrap interval overrides the frozen permutation gate;
- that Qwen3 is generally better at inventive problem solving.

The correct next step is measurement validation and a preregistered replication, not a post-hoc rescue of the current `null` package.

## Reproducibility anchors

- Qwen3 execution package: `results/exp001-comparative/qwen3-0.6b-da87bfb-qwen3-20260818-01/`
- Qwen3 execution receipt SHA-bound model revision: `da87bfb608c14b7cf20ba1ce41287e8de496c0cd`
- External response-score asset: `artifacts/exp001-comparative/qwen3-0.6b-da87bfb/qwen3-20260818-01/response-scores.json`
- External response-score SHA-256: `4a4fb307e0953b5638460d3deacd219a005dcba1b29596f8d4b5a3b03c6ec866`
- Frozen protocol: `experiments/exp001-comparative-reference/protocol.json`
- Frozen analysis plan: `experiments/exp001-comparative-reference/analysis-plan.json`
- Statistical implementation: `src/latent_triz/exp001_r3_analysis.py`
- Public response implementation: `src/latent_triz/exp001_r3_response_execution.py`
- Model adapter: `src/latent_triz/exp001_comparative_adapter.py`

The current note is documentation derived from already-published receipts and public response indices. It performs no model load, no generation, no target read, and no modification of A0-R2/C3 or the EXP-001 result packages.

## Official references

- [Qwen/Qwen3-0.6B-Base model card](https://huggingface.co/Qwen/Qwen3-0.6B-Base)
- [Qwen3 exact pinned `config.json`](https://huggingface.co/Qwen/Qwen3-0.6B-Base/blob/da87bfb608c14b7cf20ba1ce41287e8de496c0cd/config.json)
- [Qwen3 tokenizer JSON at the exact pinned revision](https://huggingface.co/Qwen/Qwen3-0.6B-Base/blob/da87bfb608c14b7cf20ba1ce41287e8de496c0cd/tokenizer.json)
- [Qwen3 concepts: Base models, BPE, control tokens, and chat templates](https://github.com/QwenLM/Qwen3/blob/main/docs/source/getting_started/concepts.md)
- [Qwen3 technical report](https://arxiv.org/abs/2505.09388)
- [Official Qwen3 release article](https://qwenlm.github.io/blog/qwen3/)
- [Hugging Face Transformers Qwen3 documentation](https://github.com/huggingface/transformers/blob/main/docs/source/en/model_doc/qwen3.md)
- [Qwen/Qwen2.5-0.5B base model repository](https://huggingface.co/Qwen/Qwen2.5-0.5B)
- [Zheng et al., *Large Language Models Are Not Robust Multiple Choice Selectors*](https://arxiv.org/abs/2309.03882)
- [Sanz-Guerrero et al., *Mind the Gap: A Closer Look at Tokenization for Multiple-Choice Question Answering with LLMs*](https://aclanthology.org/2025.emnlp-main.988/)
