---
type: research-spec
title: A0 Replication and Robustness
description: Preregistered route for challenging the published A0 automated-proxy signal on independent procedural data and model families.
status: in_delivery
last_verified: 2026-08-17
---

# A0 Replication and Robustness

This document defines A0-R, the next automated experiment after the published
A0 result. It is subordinate to the
[Laboratory Master Plan](./LABORATORY_MASTER_PLAN.md). It creates a new
experiment and must never rewrite protocol `a0-automated-weak-proxy-v1.0.3`,
run `a0-v1.0.3-e93a9faa`, or their result package.

## Purpose and falsifiable outcome

A0-R asks whether the A0 decodable signal survives independent procedural data
generation and, if later authorized, an independent model family.

The first replication is successful only if a protocol frozen before model
output:

- passes every leakage, provenance, duplicate, family, and surface-shortcut
  gate;
- reproduces the direction of the preregistered A0 primary effect on an
  independently generated corpus;
- exceeds its frozen effect-size and paired-family thresholds;
- passes a shared permutation test with adequate p-value resolution;
- shows positive held-out-domain direction in the frozen minimum number of
  domains;
- publishes the same immutable evidence package for positive, null, failed, or
  non-interpretable outcomes.

A null result constrains robustness of the automated proxy observation. A
failed or non-interpretable result diagnoses the replication substrate. None of
the outcomes validates a TRIZ construct.

## Authoritative starting anchor

- repository: `MarcoPorcellato/Latent-TRIZ`;
- published A0 merge: `fc80976d3a256ed88e2d59f1a6f893e15154e3a0`;
- published A0 protocol: `a0-automated-weak-proxy-v1.0.3`;
- published A0 run: `a0-v1.0.3-e93a9faa`;
- published result: `positive`, maximum-statistic p = 0.005, 24/24
  paired-family successes, macro-F1 margin = 0.188234;
- claim registry: all claims remain E0.

These anchors are last-known facts, not permission to skip live verification.
Every delivery task must re-read `origin/main`, the active ruleset, the exact
model receipt, and the current resource-admission contract.

## Epistemic envelope

Every A0-R empirical artifact must retain:

```json
{
  "empirical": true,
  "scientific_status": "exploratory",
  "evidence_eligible": false,
  "expert_validated": false,
  "claim_ids": []
}
```

Allowed interpretation after successful same-model replication:

> The published automated-proxy signal reproduced on an independently
> generated procedural corpus for the exact model revision tested.

Disallowed interpretations include model rediscovery of TRIZ, expert validity
of Segmentation or Inversion, causal use, spontaneous pre-output selection, or
cross-model generality.

## Scope and non-goals

Inside scope:

- an independent procedural-corpus generator and manifest;
- new templates, seeds, case identifiers, and sealed targets;
- pre-output power, shortcut, and p-resolution calibration;
- same-model exact-revision replication using the already cached A0 model;
- a later cross-model replication only after explicit acquisition and hardware
  approval;
- immutable positive, null, failed, and non-interpretable publication paths.

Outside scope:

- changing or rerunning the published A0 result in place;
- using A0 cases, sealed targets, or observed errors to tune A0-R cases;
- expert substitution or synthetic completion of H1;
- Wave 2, canonical human labels, EXP-001-R, Lab 05 direction claims, or Lab 06
  causality;
- claim promotion;
- post-output changes to thresholds, sites, layers, exclusions, or stopping
  rules;
- interactive model-serving applications or LLM judges as ground truth.

## Replication tiers

### Tier R1 — independent corpus, same exact model

R1 is the immediate automated milestone and requires no new model acquisition.

- Generate entirely new problem families from versioned rules that do not
  reuse A0 case text, role pairs, template identifiers, or seeds.
- Keep procedural targets physically separate from surfaced case text.
- Freeze calibration and sealed partitions before activation extraction.
- Use `EleutherAI/pythia-70m-deduped` at exact revision
  `e93a9faa9c77e5d09219f6c868bfc7a1bd65593c` only if its runtime-file hashes
  match the published receipt.
- Treat the previously observed layer 6 mean-transformation-span combination as
  the replication primary endpoint. Other frozen layers, token sites, and views
  are sensitivity analyses and cannot replace a failed primary endpoint.
- Compare `problem_plus_transformation` against the problem-only surface
  baseline with family-grouped leave-one-domain-out evaluation and train-only
  preprocessing.

### Tier R2 — independent model family

R2 starts only after R1 is terminal and after explicit approval for downloads,
licenses, disk, RAM, and runtime cost.

- Freeze model and tokenizer identity before acquisition.
- Do not choose the model from observed A0-R performance.
- Repeat the same primary representation contract where architecture permits;
  record any unavoidable mapping as a preregistered compatibility decision.
- Publish incompatibility or null performance without substituting another
  model post hoc.

R2 is still automated-proxy replication, not E5 claim replication, because the
underlying constructs remain unvalidated by experts.

## Ordered milestones and exit evidence

### R1.1 — replication protocol and independence audit

**Exit evidence:** a machine-readable protocol, independence manifest, explicit
A0 exclusion hashes, status vocabulary, primary endpoint, sensitivity family,
and positive/null/failed/non-interpretable rules are frozen before model output.

**Current checkpoint — verified complete:** the planned protocol instance and
its strict Draft 2020-12 schema fix the same-model primary endpoint,
statistical thresholds, epistemic envelope, immutable A0 anchors, and all 14
shortcut controls. R1.3 has now been merged and verified, and the protocol is
frozen before any model output.

### R1.2 — deterministic corpus and shortcut gate

**Exit evidence:** reproducible case and target files, disjoint calibration and
sealed partitions, no identifier or text overlap with A0, grouped families, and
terminal records for at least the full A0 14-control suite.

**Current checkpoint — verified complete pre-freeze:** the independent
generator produces 48 families and 96 paired cases across six domains, split as
48 calibration and 48 sealed cases with targets stored in separate files. The
independence audit compared them with all 192 published A0 cases and targets:
status `pass`, zero violations. The calibration-only shortcut audit evaluated
24 families / 48 cases and all 14 required controls passed. `make a0r1-verify`
regenerates the four corpus files and four pre-output audit files byte-for-byte.
No model output was accessed. This completes the R1.2 substrate and is frozen
together with R1.3.

### R1.3 — power and permutation freeze

**Exit evidence:** simulations report false-positive rate, power, minimum
detectable effect, sample size, family threshold, domain-direction threshold,
and a permutation budget with p-value resolution no weaker than A0.
Calibration may select these values once; sealed output cannot change them.

**Current checkpoint — verified complete:** exact-binomial calibration was
materialized as a separately hashed receipt, bound to the corpus and audit
manifests, and frozen in the same reviewed commit. R1.3 is now merged and
verified. The recorded metrics are:
  false-positive rate `0.03195732831954956`, power under family-success
  probability `0.8`
`0.9108287412264922`, minimum detectable effect `0.2597184664182352`, sample
size `24`, 100000 deterministic simulations, minimum permutation p-value
resolution `.001`, and no model or sealed-output access.

### R1.4 — exact-model activations and sealed inference

**Exit evidence:** exact runtime-file hashes match the published model receipt;
the activation export, index, environment, protocol, corpus, sealed-target, and
code hashes link end to end; the primary endpoint runs once under the guarded
resource contract.

**Verified checkpoint — R1.4a merged:** the implementation binding is fixed
around the frozen endpoint. It specifies the classifier regularization,
permutation seed and swap scheme, hidden-state index semantics, sentinel and
problem-only baseline site, domain-direction statistic, code hashes, and
terminal `failed` / `non_interpretable` packaging. The R1-specific extractor
and fixed-primary analysis are now exercised through synthetic adapters and
synthetic vectors only; no actual model or sealed-target access occurs in this
checkpoint. PR 39 merged only after exact-head local qualification and hosted
gates passed.

**Verified checkpoint — R1.4b merged and executed once:** the guarded run used
the frozen layer 6 / mean-transformation-span primary and opened sealed targets
once at the analysis boundary. The exploratory result is positive: 23/24
family successes, primary macro-F1 0.624348, problem-only macro-F1 0.499130,
margin 0.125217, six domain-direction successes, and permutation p = 0.002.
The raw output retained an `r1_` domain prefix and failed the public schema.
R1.5 therefore preserves that raw hash and applies a deterministic 54-label
clerical recovery; its receipt proves that no metric value changed and that the
recovery accessed neither model output nor sealed targets.

### R1.5 — immutable publication

**Current checkpoint — verified complete:** PR 41 published the tracked package
on `main` at `05ba15a28442260c32951413c9128f0179573198`. It contains the raw
and recovered results, recovery receipt, activation receipt, 96-record
representation index, external dense locator, report, and publication
manifest. The declared dense asset is 944,964 bytes with SHA-256
`c49436ed505cbaea677a4f68e597714ef0dd75119a0640474ac1372fae1d2c20`.
Package verification passes when that declared asset is supplied, and fails
closed when it is absent or mismatched. The exact branch head passed the
repository check and all hosted PR gates were terminally green before merge.
The published A0 package remained byte-stable, all claim IDs remain absent,
and H1 and Wave 2 were untouched. All statements remain E0 exploratory proxy
evidence and are not expert-validated TRIZ claims.

**Exit evidence:** one command creates or verifies the result, report,
limitations, receipts, indexes, and hashes; a fresh clone plus declared external
assets can verify the package; repository tests, artifact audit, exact-head CCP
when required, hosted aggregate, and review-thread gates are terminally green.

### R2 — cross-model replication

**Current checkpoint — instrumentation only:** the operator authorized only the
download of the declared runtime files for `HuggingFaceTB/SmolLM2-360M` at
revision `f8027fd0eaeea54caa13c31d31b9fdc459c38b49`, with a maximum disk budget
of 1 GiB and integrity receipt production. The acquisition completed as a
bounded file transfer: nine files, 727,058,433 bytes total, receipt status
`integrity_verified`, and weights SHA-256
`7aaff6661428bed033abba9522bec81938678642cca3181fe752b6ca9e1e540f`. All
access flags remained false. This remains instrumentation-only and
evidence-ineligible; it makes no empirical claim and does not load the model.

**Completed bounded feasibility checkpoint:** the operator subsequently
authorized one test of the acquired model. Before any load, the repository froze
`experiments/a0r2-independent-model/feasibility-contract.json`: local-only CPU
float32, two inference passes over one fixed synthetic prompt, no generation,
at most 128 prompt tokens, a 900-second wall envelope, and an 8 GiB peak-RSS
reporting ceiling. The test may retain only shapes, finite-value checks,
repeatability difference, timings, runtime versions, and memory measurements;
it must not retain model output content. PR 44 merged that contract at
`da8f4bb0c07fe32ede438b13da80b89019cfb812` before the first load.

The one authorized run produced a schema-valid `compatible` receipt: 25 prompt
tokens, 33 hidden-state entries, final hidden shape `[1, 25, 960]`, finite
hidden states and logits, repeatability difference `0.0`, 2,540,519,424 bytes
peak RSS, and 3.813451875 seconds total runtime. It retained no output content
and accessed no sealed target. The outer CCP guard nevertheless exited 70 with
cleanup uncertain at `completed descendant seal`. Post-run inspection found
admission inactive, an empty queue, no matching process, and resource decision
`admit`; this does not retroactively qualify the guard as PASS. The run was not
repeated.

PR 46 then merged the R2.1 publication and receipt branch at
`1f35ba353e792aa263db7449216e3172d0306798` after exact head
`5f9c21db944f25fd1dac4a550911c85e86471e35` and public receipt publication. The
R2.1 preregistration is now verified complete. R2.2 is public and verified
complete as a local/offline SmolLM2 implementation with 192 forwards and 1920
vectors, the final-block primary plus descriptive layers, views, and sites,
fixed primary thresholds, strict single target read, failure publication, and
descriptive-only cross-model concordance and resource-envelope refusal. Fifty-five focused synthetic tests
currently pass, and the execution contract verifies 11 code files and 9
runtime files without loading a model. No real model load or sealed-target
access occurred in R2.2. PR 47 published the implementation and its first
receipt, but the hosted verifier correctly rejected a simultaneous timeout and
acceptance-digest change against the trusted base policy. PR 48 migrated only
the accepted digest at `afd4b56ae84a944dc4cd60486caabce9b9452f75`; PR 49 then
activated only the 180-second timeout at
`85180041717f336de554300dda109731b48c6b95`. Both prerequisite PRs used
base-policy exact-head receipts and terminal green gates. PR 47 subsequently
passed its refreshed exact-head receipt and hosted gates and merged at
`fa1e254ec373092278b1ab63f05504545e295b67`. R2.2 is therefore public and
verified complete. R2.3 remains separately approval-gated.

**Automated-study direction:** the operator has requested the broadest useful
SmolLM2 study that does not depend on human review. This authorizes preparation,
implementation, synthetic qualification, and ordinary repository delivery of
the R2 study. It does not silently waive the existing sealed-data/material-run
gate: the exact preregistration, resource envelope, and one-run boundary must be
merged and presented before sealed-target access or scientific output.

The automated study has one fixed primary question: whether the independent
model family reproduces the already frozen R1 automated-proxy direction at the
same semantic endpoint. Pythia tuple index 6 and SmolLM2 tuple index 32 both
mean the final transformer-block output. The primary remains
`problem_plus_transformation` / `mean_transformation_span`, compared with the
problem-only sentinel baseline. Literal layer 6 in SmolLM2 is not the primary.

The broader evidence battery is frozen before output and remains descriptive:

- tuple indices `[0, 11, 21, 32]`, all preregistered views, and every applicable
  token site;
- the same grouped leave-one-domain-out classifier, train-fold-only
  standardization, paired-family statistic, 999 shared permutations, and R1
  thresholds;
- the 14 existing surface, provenance, leakage, random-label, random-partition,
  generic-action, transformation-taxonomy, and adjacent-proxy controls;
- per-domain directions, effect sizes, uncertainty, depth profiles, surface
  baseline comparisons, and cross-model directional concordance;
- mandatory publication of positive, null, failed, non-interpretable, or
  incompatible outcomes, with no model substitution or sensitivity-based
  rescue of the primary.

No annotator, expert, LLM judge, or manual adjudication participates in the
study. That automation limits the conclusion to persistence or absence of the
procedural proxy signal; it cannot validate TRIZ constructs.

**Feasibility exit evidence:** immutable contract and receipt hashes, exact snapshot
verification, the terminal feasibility receipt, the separate guard observation,
and exact-head repository/hosted qualification. The compatibility payload is
terminal, while the outer guard remains explicitly `cleanup_uncertain`.

#### R2.1 — pre-output preregistration

**Verified complete:** the strict machine-readable protocol binds the R1
corpus, sealed-target, shortcut, protocol, and freeze hashes; the exact SmolLM2
revision and integrity/feasibility receipts; the final-block architecture
mapping; the primary endpoint; all descriptive sensitivities; terminal outcome
rules; and the no-human-review epistemic boundary. The protocol must say
`approval_required` for sealed execution until its exact budget is approved.

**Exit evidence:** schema parity, mutation tests, documentation audit, clean
exact-head repository qualification, reviewed PR, and merge before any new
model output or sealed-target access.

#### R2.2 — implementation and synthetic qualification

**Verified complete:** the R2-only adapter, activation, analysis, runner, report,
schemas, and tests are implemented against the offline/local-only SmolLM2 study
path. Synthetic qualification currently passes 55 focused tests. The execution
contract verifies 11 code files and 9 runtime files without loading a model.
The tranche keeps the final-block primary, descriptive layers, views, and
sites; fixed primary thresholds; strict single target read; failure
publication; and descriptive-only cross-model concordance. No real model load
or sealed-target access occurs in this checkpoint.

**Exit evidence:** code hashes bound into the reviewed implementation contract;
all synthetic terminal classes and artifact mutations tested; exact-head gates
merged before material execution.

#### R2.3 — explicit sealed-execution gate

Present one exact approval dossier after R2.1 and R2.2 merge. The proposed
envelope is one local-only CPU float32 run, no network or generation, at most
30 minutes wall time, at most 8 GiB peak RSS, at most 64 MiB of new dense
output, the already acquired nine-file snapshot only, and no retry after model
or target access without a new explicit approval. These are conservative caps;
the feasibility measurement was 2.37 GiB and 3.81 seconds for the synthetic
probe.

**Current checkpoint — corrective authorization recorded, pre-run qualification pending:** the human-readable
[`A0-R2.3 sealed-execution approval dossier`](./A0R2_SEALED_EXECUTION_APPROVAL.md)
and its strict machine-readable request bind the exact model snapshot,
pre-output contracts, declared R1 input hashes, prior feasibility and guard
receipts, resource ceilings, one-run boundary, single analysis target read,
terminal publication rules, and claim limit. The request records
`operator_approval_granted=false`. Publishing or verifying the dossier does not
authorize a model load, material run, or sealed-target access.

PR 62 published the request from exact source head
`28f0b2596a273212dfc0712aaa00b5887ecce83a` and merged at
`b9260cd9743d2afd5eb7fc79339e0687fa22689c`. Its commit-bound CCP evidence is
`ccp-evidence/28f0b2596a273212dfc0712aaa00b5887ecce83a` at evidence commit
`880700a31a3f3f2a3ca639d1ab7b12a02c69ba82`; hosted run `31955588854`
attempt 2 passed the exact-head receipt, trusted scientific audit, aggregate,
and required `merge-policy/gate`. A technical hash calculation of the sealed
target file occurred outside the planned analysis boundary without emitting or
retaining its content. It therefore consumed the original one-read scope under
the laboratory's conservative access rule. The operator subsequently issued a
new explicit, one-run authorization with the unchanged scientific and resource
limits. Its tracked corrective receipt binds the original dossier, the frozen
protocol, and the exact implementation hash, and the runner verifies it before
the contract, shortcut gate, model import, or target discovery. No material
action may precede qualification of that corrective gate.

The expert TRIZ reference corpus added after the R2 freeze is ineligible for
R2.3. It must not alter prompts, cases, targets, controls, thresholds,
interpretation rules, or the one-run boundary. Its first experimental use
belongs to a separately preregistered R3/EXP-001 tranche.

#### R2.4 — one sealed automated run

Only after the exact R2.3 approval and CCP `Admit` with an inactive empty queue,
run activation extraction once, then open the exact-hash sealed targets once at
the analysis boundary. Preserve any partial artifact and publish every terminal
outcome. Verification may be repeated only when it performs no model load and
opens no sealed target.

**Terminal execution record:** the single authorized attempt ran from merged
`main` at `9a2269650380864af4932cd0403c806eb57837a1` on 2026-08-16. SmolLM2
loaded locally under the CCP guard, then the adapter rejected the tokenizer
return type with `A0R2AdapterError` before activation extraction or analysis.
The terminal package is therefore `failed`; it records model output as
`possibly_accessed` and sealed targets as `not_accessed`. No retry, tuning,
model substitution, protocol revision, target read, or statistical result is
permitted under this authorization.

#### R2.5 — immutable publication

Publish the statistical result, receipt, representation index, external dense
asset locator/hash, report, limitations, guard/recovery observation if needed,
and manifest. Verification from a fresh clone plus the declared external asset
must fail closed on every missing or mutated dependency. A positive result may
say only that the frozen automated-proxy signal persisted across the two exact
model families tested.

For a pre-activation terminal failure, no representation index or external dense
asset exists; the failure receipt, report, and manifest are the complete
immutable package. The package verifier must continue to reject a fabricated
mixed failure/activation package.

**Historical R2.3–R2.5 closeout:** PR 64 merged the corrective authorization gate at
`9a2269650380864af4932cd0403c806eb57837a1`. PR 65 then published the first and
only terminal execution package at `1112bc31e388c5c6857ecfd96542466cf613ea52`.
The source package passed fresh-clone verification; its exact-head CCP receipt
and hosted `merge-policy/gate` were terminal PASS. This closes R2.3–R2.5 as a
published failed outcome, without an R2 signal estimate or a general TRIZ
claim. Any future corrective execution requires a newly preregistered protocol
and explicit operator authorization.

#### A0-R2-C1 — isolated tokenizer correction

**Current checkpoint — pre-output correction, approval not yet granted:** the
published R2 failure remains immutable and terminal under its consumed
authorization. The failure was an adapter container-type defect, not a null
scientific result: Transformers returned a valid `BatchEncoding`, which is a
`collections.abc.Mapping` but not a concrete `dict`. The feasibility path did
not exercise this adapter predicate, and the synthetic tokenizer returned only
a plain `dict`; therefore the defect was predictable but not covered.

The separately versioned [A0-R2-C1 correction dossier](./A0R2C1_TOKENIZER_CORRECTION.md)
binds a tokenizer-only receipt and changes only the accepted container
interface from `dict` to `Mapping`. It does not modify the frozen model,
revision, corpus, targets, prompts, representation sites, statistics,
thresholds, resource limits, or publication rules. The probe loaded no model
and accessed no sealed target. C1 must be merged and exact-head qualified
before a new exact operator authorization may permit one material attempt.

**Terminal C1 execution record:** the one authorized C1 attempt ran from
public main `8b1a693e832bc753dfee8cbded947eadc1be03cc`. SmolLM2 loaded locally,
then the shared activation normalizer attempted to coerce a nested Llama
hidden-state token vector to `float`. The normalizer assumed a rank-two
`[token, hidden]` shape, while the runtime retained rank three
`[batch, token, hidden]`. The run stopped before analysis, the sealed targets
were not accessed, and no activation bundle or statistical result exists. The
terminal status is `failed`; the C1 authorization is consumed and any C2
correction requires a fresh preregistration and explicit operator approval.

#### A0-R2-C2 — singleton-batch shape correction

**Terminal C2 execution record:** C2 preserved the C1 terminal package and
changed only the handling of the Llama singleton batch dimension. The one
explicitly authorized execution ran from public main
`183cb20654dbdac0d7ad2ce97f184e3286b03a14` after exact-head qualification.
It successfully extracted 1,920 indexed 960-dimensional representations with
33 hidden-state entries, then failed with `A0R2AnalysisError` at the data
stage. The failure receipt conservatively records model output and sealed
target access as `possibly_accessed`; no statistical result exists, no claim is
promoted, and the C2 authorization is consumed. Any future model run requires
a separately preregistered protocol and explicit authorization.

#### A0-R2-C3 — analysis-only index metadata recovery

**Current checkpoint — C3.0 complete; C3.1 in delivery:** the published C2 failure digest
resolves deterministically to `activation dtype drift`. The 1,920 historical
C2 index rows omit `dtype`, while the activation receipt independently binds
the run to CPU `float32`; the analyzer rejects the omission before target
content is read. C3 is constrained to an in-memory, exact-index-hash metadata
recovery and a prospective analysis-only path over the immutable C2 activation
bundle. It must not load or query a model, generate output, alter the source
index/dense bytes, tune statistics, or substitute any input.

The detailed C3 contract is
[A0-R2-C3 analysis-only metadata recovery](./A0R2C3_ANALYSIS_ONLY_RECOVERY.md).
The [SmolLM2 runtime contract](./reference/smollm2-runtime-contract.md)
separately makes the official tokenizer, Llama shape, and export-metadata
requirements executable before future analysis.
Only C3.0 synthetic qualification is currently authorized. A fresh explicit
operator authorization remains mandatory before one later analysis-boundary
sealed-target read; C2's authorization remains consumed.

## Statistical and missing-data rules

- The R1 primary endpoint is fixed from A0 and is not selected from R1 output.
- Families, not individual cases, are the resampling and split unit.
- Shared permutations preserve the frozen grouping and multiplicity contract.
- Surface, provenance, generic-action, adjacent-proxy, random-label, and
  random-partition controls remain mandatory.
- Missing, stale, mismatched, or inconclusive identity and integrity evidence is
  a failure, never a pass.
- A predictive shortcut makes the run non-interpretable when its aggregate
  macro-F1 is at least `0.65` and its margin over the majority baseline is at
  least `0.10`; any required structural control whose status is not `pass`
  has the same terminal effect. These frozen refusal rules cannot be relaxed
  after model or target access.
- Domain results, uncertainty intervals, effect sizes, and all sensitivity
  outcomes are published even when the primary rule fails.

## Delegation and cost policy

Use deterministic tools first. Delegate independent inventory, documentation,
mechanical implementation, focused tests, and log distillation to the cheapest
suitable bounded worker. Keep protocol architecture, independence judgments,
statistics, epistemic interpretation, security, qualification, and merge
authorization with the primary agent. Assign one owner per file group and stop
a low-cost attempt after one failed try and one focused correction.

## Approval boundaries

Human approval is required for:

- any R2 model download or material hardware use;
- paid or credentialed services;
- destructive cleanup;
- external releases or archives beyond normal repository pull-request delivery;
- changing a frozen A0-R protocol after sealed output;
- any assertion that an automated target has become expert-validated TRIZ.

Normal isolated worktrees, branches, commits, pull requests, exact-head
qualification, and merges remain authorized within the repository workflow.

## Interruption and recovery

At every interruption record repository, worktree, branch, exact HEAD and base,
dirty state, active workers and runners, completed terminal checks, unproven
gates, remote branch/PR state, external asset hashes, and the exact resume
command. A temporary path without a saved branch or commit is not a checkpoint.

## Completion checklist

R1 is complete only when:

- the replication protocol and primary endpoint were frozen before output;
- every A0 input and target is excluded by hash and provenance;
- the new corpus is deterministic, label-free, grouped, and partitioned;
- shortcut and independence gates are terminal;
- calibration justifies sample size, thresholds, and permutation resolution;
- exact cached-model identity is reverified;
- the sealed primary endpoint is run once and classified without post hoc
  replacement;
- every result class has an immutable public package;
- the one-command verification path works;
- exact-head repository and hosted gates pass;
- A0 remains byte-stable;
- all claim IDs remain absent and H1/Wave 2 remain untouched.

R2 is complete only after its separate acquisition approval, frozen model
decision, exact receipts, sealed run, immutable publication, and the same
no-claim boundary are all proven.

The no-human-review R2 completion checklist additionally requires:

- the R2 protocol and architecture mapping merged before output;
- the primary rule to remain singular and unchanged after output;
- every sensitivity to remain descriptive and unable to rescue the primary;
- all 14 controls and the surface baseline to be published;
- model, runtime, code, corpus, target, shortcut, and protocol hashes to link
  end to end;
- one material run at most under the approved CCP envelope;
- no human label, expert judgment, LLM judge, generation, or model substitution;
- positive, null, failed, non-interpretable, and incompatible publication paths;
- exact-head local evidence, hosted gates, and immutable package verification;
- all claim IDs absent and every conclusion kept at automated exploratory E0.
