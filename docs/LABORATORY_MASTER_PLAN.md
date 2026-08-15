---
type: master-plan
title: Laboratory Master Plan
description: Canonical evolution ledger and gated route from the verified laboratory foundation to falsifiable, reproducible Latent TRIZ experiments.
status: canonical
last_verified: 2026-08-15
---

# Laboratory Master Plan

This is the canonical long-form plan for Latent TRIZ. It records the verified
repository evolution, the current scientific bottleneck, the dependency-ordered
delivery sequence, and the proof required to close each milestone. The shorter
[Roadmap](./ROADMAP.md) remains the public overview.

This plan is operational metadata. It is not evidence for the Latent TRIZ
Hypothesis.

Long-running Codex work should use [the persistent execution goal](./PERSISTENT_GOAL.txt)
as a short pointer to this plan rather than duplicating its milestones.

## Status vocabulary

- **Verified:** supported by a tracked artifact, exact commit, merged pull
  request, or terminal validation receipt.
- **In delivery:** saved implementation exists but the milestone has not passed
  its complete qualification and merge gate.
- **Blocked by human work:** software may be ready, but a real independent human
  activity is still required.
- **Planned:** ordered work with an explicit predecessor and exit gate.
- **Deferred:** intentionally excluded until a stronger predecessor result
  justifies it.

## Verified planning anchor

| Item | Verified state | Authoritative anchor |
|---|---|---|
| Public repository | `MarcoPorcellato/Latent-TRIZ` | GitHub repository and tracked `LICENSE` / `NOTICE` |
| Protected `main` | `e2fd611d3d7a70778bde83f7936cdbc8a5ef8d0d` | live GitHub state verified 2026-08-15 after PR 38 |
| Required merge context | strict `merge-policy/gate` | active GitHub ruleset and `.github/expected-main-ruleset.json` |
| Completed automated milestone | A0 sealed proxy exploration | PR 34, protocol `v1.0.3`, run `a0-v1.0.3-e93a9faa` |
| Current authentic-TRIZ milestone | annotation ontology v1.2 | draft PR 30; live state must be rebased and requalified before delivery |
| Claim state | all registered claims remain E0 | `data/claims.jsonl` |
| First dataset attempt | rejected for scientific freeze | retained Wave 1 surface-audit artifacts |

The checkout used for unrelated local work is not an authoritative integration
base. Delivery uses an isolated worktree created from an exact verified commit.

## Evidence boundary

The following may qualify engineering, documentation, or readiness, but never
count as evidence for the hypothesis:

- smoke tests and synthetic fixtures;
- dashboards and visualizations;
- source inspection without a completed run;
- generator intent labels;
- incomplete or unblinded human judgments;
- model-backed instrumentation without the experimental controls;
- exploratory results presented outside their registered evidence class.

A scientific result requires frozen inputs, canonical labels, an exact model
revision, an immutable run record, the applicable controls, a terminal artifact
audit, and an explicit link to the claim registry. Null and failed results are
published under the same standard.

## Evolution ledger

### Phase A — hypothesis, governance, and public laboratory foundation

| Delivery | What became usable | Scientific boundary |
|---|---|---|
| PRs [#1](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/1)–[#3](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/3) | article framing, research protocol, official repository structure, Apache-2.0 governance, E0–E6 evidence discipline, Matryca-Knowledge documentation bundle | hypothesis registered; no empirical support |
| PR [#11](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/11) | one-command Lab 00 visual process smoke | synthetic and presentation-only |
| PRs [#12](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/12)–[#13](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/13) | provisional model strategy, offline model and dataset preflight, stronger evidence integrity | selection remained provisional and no-download |

### Phase B — runnable Lab 01–05 instrumentation

| Delivery | What became usable | Scientific boundary |
|---|---|---|
| PR [#14](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/14) | exact-revision real-model Lab 01 anatomy and numerical parity | instrumentation evidence only |
| PRs [#15](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/15)–[#19](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/19) | Lab 02 dataset anatomy, Lab 03 surface controls, Lab 04 decodability fixture, Lab 05 candidate directions, and the one-command Lab Suite | maintained fixtures and readiness gates, not TRIZ evidence |
| PR [#24](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/24) | domain-blocked max-statistic inference, nested alpha reselection, p-resolution refusal, and NumPy backend | empirical-scale method enabled; tracked fixture remained non-empirical |
| PR [#25](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/25) | hash-verified Safetensors bridge from real residual activations to Lab 04 | two-case Pythia smoke remained engineering-only |

### Phase C — annotation and the first dataset falsification gate

| Delivery | What became usable | Scientific boundary |
|---|---|---|
| PRs [#21](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/21)–[#23](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/23) | blinded workbench, balanced Wave 1 candidate batch, and retained multi-rater audit | candidate and collection infrastructure only |
| PR [#26](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/26) | annotation ontology v1.1 with cryptographic case, batch, guide, and session binding | independent collection had not started |
| PR [#27](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/27) | field-specific lexical and provenance surface audit | Wave 1 correctly rejected; negative readiness result, not hypothesis evidence |

Wave 1 exposed strong superficial shortcuts, including label prediction from the
problem alone and perfect prediction from some solution views. It must not be
edited until it passes the audit. Its permanent role is a known-leaky
calibration corpus and regression fixture.

### Phase D — fail-closed integrity and stable cost-aware governance

| Delivery | What became usable | Scientific boundary |
|---|---|---|
| PR [#28](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/28) | local `$ref` / `$defs`, `allOf`, exclusive bounds, unsupported-keyword failure, Draft 2020-12 cross-validation, mutation tests, disagreement-safe freeze, and `constraints` cue scanning | closed the two reported P0 fail-open paths; did not change a claim |
| PR [#29](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/29) | one stable path- and risk-aware `merge-policy/gate`, pre-merge Python 3.11/3.12 where applicable, exact-head CCP and artifact audit for scientific/governance changes, scheduled ruleset drift audit | qualification policy only |

### Phase E — human-label route in delivery

PR 30 is **in delivery**, not merged. The saved checkpoint contains the v1.2
decision record, documentation amendment, and a ready-to-run three-expert,
six-case cognitive-pilot protocol. The schemas, workbench, audit, synthetic
fixture migration, full tests, exact-commit CCP receipt, pull request, and human
pilot result are not yet complete. Its recorded base predates the merged A0
work, so every implementation and receipt must be re-verified rather than
carried forward by assumption.

### Phase F — completed automated A0 exploration

| Delivery | What became usable | Scientific boundary |
|---|---|---|
| PR [#31](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/31) | pre-sealed deterministic corpus foundation | procedural targets only; no model result |
| PR [#38](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/38) | A0-R R1.3 calibration and protocol freeze | exact power receipt, freeze manifest, and protocol lock; no model or sealed-output access |
| PR [#32](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/32) | calibrated and frozen A0 protocol `v1.0.3` | freeze and controls, not evidence by themselves |
| PR [#33](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/33) | hosted repository lane allowed to complete | CI policy correction only |
| PR [#34](https://github.com/MarcoPorcellato/Latent-TRIZ/pull/34) | exact-model activations, sealed analysis, immutable result package, `make a0`, HTML report, schemas, and receipts | positive exploratory proxy result; not expert-validated TRIZ evidence and not claim-eligible |

The sealed A0 result is `positive` under its frozen automated-proxy rule:
maximum statistic p = 0.005, 24/24 paired-family successes, maximum primary
macro-F1 = 0.687364, problem-only surface macro-F1 = 0.499130, and margin =
0.188234. The strongest preregistered combination was layer 6 at the mean
transformation span. Energy and transport remained at 0.5 accuracy in that
combination, the corpus is procedural, and only one small model revision was
tested. Those limits are part of the result, not optional caveats.

## Current bottlenecks

The laboratory now has one empirical automated-proxy result, while the authentic
TRIZ route still lacks expert-validated constructs and canonical labels. The
two routes must remain separate:

```text
annotation contract integrity
        -> permanent Wave 1 negative control
        -> label-free paired Wave 2
        -> independent canonical labels
        -> empirical artifact contract
        -> real multi-view activations
        -> held-out-domain EXP-001-R
```

The automated route may challenge A0 through a new preregistered replication,
but it cannot unblock or replace any node in the authentic route:

```text
A0 published result
        -> independent procedural-corpus replication
        -> independent model-family replication
        -> robustness conclusion for automated proxies only
```

## Ordered delivery plan

### Parallel Phase A0 — automated weak-hypothesis exploration

A0 may run before the human H1 gate because its targets are assigned by frozen
procedural transformations rather than expert judgment. It remains independent
from Wave 2 and cannot validate the TRIZ construct or promote a claim. Its
complete freeze, corpus, controls, activation, analysis, publication, and
completion contract is defined in
[A0 Automated Weak Hypothesis Exploration](./A0_AUTOMATED_WEAK_HYPOTHESIS.md).

The A0 protocol was merged and frozen before model output. PR 34 then passed the
scientific artifact audit, exact-head CCP receipt verification, Python 3.11 and
3.12 repository checks, the trusted aggregate gate, and exact-head squash merge.
The tracked package includes the exact-revision activation receipt, statistical
result, representation index, publication manifest, and HTML report. Dense
vectors remain external and hash-addressed.

**Current status — verified complete:** protocol `v1.0.3` is immutable and run
`a0-v1.0.3-e93a9faa` is published on `main` at PR 34's merge commit.

- deterministic design selected by power calibration:
  4 problem families/domain, 24 problem families total (48 paired cases), 199 permutations, critical=19,
  MDE 0.333212784429589
- v1.0.1 pre-freeze prototype was rejected and redesigned pre-freeze as token-matched
  unique role pairs
- exact Pythia activations and the sealed automated-proxy result are published
- all registered claims remain E0 and H1/Wave 2 remain independent

### Parallel Phase A0-R — automated replication and robustness

A0-R is the next fully automated milestone. It is a new preregistered experiment,
not a mutable continuation of the observed A0 protocol. Its canonical contract
is [A0 Replication and Robustness](./A0_REPLICATION_AND_ROBUSTNESS.md).

**Dependency:** A0 is terminally published and its inputs and results remain
byte-stable.

**Outcome:** challenge the A0 signal on an independently generated procedural
corpus, first with the already cached exact model revision and then, only with
explicit acquisition approval, with an independent model family.

**Exit evidence:** pre-output protocol freeze, independent case/template hashes,
the full shortcut suite, exact-model receipts, a terminal positive/null/failed/
non-interpretable result, one-command verification, artifact audit, exact-head
qualification, and immutable publication.

**Claim impact:** none. A successful A0-R strengthens only the robustness of the
automated proxy observation; it does not validate Segmentation or Inversion as
TRIZ constructs.

**Current status — verified complete:** R1.2 now has a deterministic
independent 48-family / 96-case corpus, physically separate calibration and
sealed targets, a zero-violation comparison against the published A0 corpus,
14/14 passing shortcut controls, strict schemas, and byte-for-byte one-command
verification. R1.3 has frozen the protocol with a separately hashed power
receipt and freeze manifest. No model output or A0-R result exists yet. The
next exit evidence is the R1.4a implementation binding and deterministic
pre-output tests. R1.4a is now the live implementation checkpoint, with fixed
runtime/input/code hash binding, fixed classifier/permutation/baseline/domain-
statistic specification, and synthetic-adapter / synthetic-vector coverage
only. Exact-model activation and sealed inference remain blocked until R1.4a is
reviewed and qualified under the guarded resource contract.

### PR 30 — annotation ontology v1.2 implementation

**Outcome**

- independent Segmentation and Inversion presence/essentiality scores;
- global contradiction-resolution and feasibility scores;
- mandatory named alternative for `Other`;
- null scores for `Cannot determine`;
- visible definitions, positive examples, near misses, adjacent-principle
  confusions, and decision rule;
- complete form reset after every successful save;
- a versioned cognitive-pilot protocol, without fabricated human results.

**Exit evidence**

- guide, annotation, audit-result, and cognitive-pilot schemas validate with the
  local validator and pinned `jsonschema`;
- focused workbench and audit tests cover every v1.2 branch;
- synthetic v1.1 fixtures are explicitly migrated without being reclassified as
  empirical;
- full repository, docs, Python 3.11, and schema cross-validation gates pass;
- exact-head CCP receipt, `merge-policy/gate`, ruleset re-read, and zero unresolved
  review threads are terminally green.

**Claim impact:** none; all claims stay E0.

**Residual risk:** a software-complete protocol is not a validated human guide.

### Human gate H1 — three-expert cognitive pilot

This is **blocked by real human work**, not by code. Three independent TRIZ
experts must evaluate the six frozen pilot cases, explain ambiguities, and
produce a versioned keep-or-amend decision. Synthetic or model-generated
responses cannot substitute for this gate. Wave 2 collection cannot start until
H1 closes, although software and archival work may continue.

### Milestone W1 — preserve Wave 1 as a permanent calibration corpus

**Outcome**

- no case text is changed;
- machine-readable `calibration_only`, `freeze_eligible: false`, and
  `known_shortcut_corpus: true` status;
- retained negative report and regression tests that must continue detecting
  the known shortcuts;
- a pre-freeze Candidate Surface Audit contract separated from post-freeze
  Lab 03 so no frozen Lab 02 snapshot is required circularly.

**Exit evidence:** artifact hashes remain stable, the expected-negative audit
passes as a regression, and no EXP-001 manifest can select Wave 1.

**Claim impact:** none; the negative result qualifies the method, not the
hypothesis.

### Milestone W2 — label-free paired Wave 2 contract

**Outcome**

- same base problem, constraints, improvement, and worsening consequence with
  counterfactual Segmentation and Inversion solution variants;
- label-free cases with separate generator draft targets;
- `problem_family_id`, solution-variant, source, generator, template, license,
  and relationship provenance;
- grouped splits that keep every problem family together;
- a sealed later set that is not used to tune Wave 2 or the audits.

**Exit evidence:** problem-only baselines remain near chance; no family crosses
split boundaries; provenance diversity, duplicate, cue, pair, and surface gates
pass under rules fixed before generation.

**Claim impact:** none; a valid candidate corpus is not a result.

### Milestone C1 — canonical human-label pipeline

**Dependency:** H1 closed and Wave 2 contract frozen.

**Outcome**

- immutable raw per-rater files;
- additive adjudication and exclusion ledgers;
- separate canonical labels and a Both/Other/Cannot-determine challenge set;
- Labs 03–05 consume explicit canonical labels and never generator intent;
- case content, targets, labels, relationships, splits, and representations are
  physically separate.

**Exit evidence:** blinded coverage and agreement gates pass; every canonical
label is traceable to raw ratings and adjudication; no mixed ontology revision
or hidden label fallback is possible.

**Claim impact:** none; independently labelled data becomes eligible for a
future frozen study.

### Milestone E1 — empirical envelope v2 and immutable run substrate

**Outcome**

- typed `fixture`, `instrumentation`, `exploratory`, `confirmatory`, and
  `replication` modes without rewriting historical v1 fixtures;
- fail-closed prohibition on empirical input being downgraded to non-empirical
  output;
- planning artifacts separated from evidence artifacts so an E0 claim may have
  a preregistration without pretending to have a result;
- separate recognition, pre-output selection, and causal-control claim branches;
- immutable run directories, atomic publication, real execution receipts, and
  compact summaries pointing to detailed results;
- one shared verified representation store for later Lab 04–06 consumers.

**Exit evidence:** schema mutations reject epistemic downgrades and overwrites;
interrupted writes cannot create valid partial runs; legacy fixtures remain
byte-stable.

**Claim impact:** claim structure becomes more precise; evidence levels do not
change.

### Milestone I1 — published multi-view Pythia instrumentation bundle

**Outcome**

- `problem_only`, transformation, and completed-solution views;
- stable sentinel, span-mean, and boundary token sites;
- complete tokenizer, model, case, license, and execution provenance;
- versioned index and summary in Git, with the verified Safetensors container as
  a release or archival asset rather than a dense Git payload.

**Exit evidence:** hashes, shapes, dtypes, token sites, residual parity, atomic
publish, and fresh-clone verification pass.

**Claim impact:** none; this remains a published engineering smoke.

### Milestone F1 — current model feasibility and statistical calibration

**Outcome**

- live verification of model terms, availability, exact revisions, disk, RAM,
  latency, tokenizer behavior, interpretability resources, and redistribution
  constraints before selecting a primary and replication model;
- simulation calibration for false-positive rate, known signal, domain-only
  confounding, lexical-only confounding, and minimum detectable effect;
- a sample size and permutation budget justified by the calibration rather than
  inherited from a smoke fixture;
- operator-signature and competing-taxonomy controls that distinguish TRIZ
  alignment from generic action or lexical categories.

**Exit evidence:** receipted no-download preflight precedes any authorized
acquisition; any download or material hardware use receives explicit approval;
the preregistration records the chosen model, dataset, views, sites, groups,
controls, sample size, and stopping rules.

**Claim impact:** none; feasibility and preregistration are planning artifacts.

### Milestone R1 — first authentic EXP-001-R exploratory recognition run

**Dependencies:** PR 30, milestones W1–F1, and H1 are closed; Wave 2 and canonical labels are
frozen; Candidate Surface Audit passes.

**Outcome**

- real exact-revision activations;
- multi-view and multi-site recognition analysis;
- grouped leave-one-domain-out evaluation;
- shared grouped permutations with nested selection and the calibrated budget;
- lexical, provenance, matched-negative, random-partition, adjacent-principle,
  and generic-transformation controls;
- a reproducible public bundle whether the result is positive, null, or failed.

**Exit evidence:** immutable dataset, canonical-label, model, environment, code,
run, and result receipts link end to end; rerun instructions work from a fresh
clone plus declared external assets; the result is marked `empirical: true`,
`scientific_status: exploratory`, and `evidence_eligible: false` unless a later
confirmatory contract explicitly changes that boundary.

**Claim impact:** the run may inform a future recognition-specific claim, but it
does not by itself establish pre-output selection, causal use, or the Strong
Latent TRIZ Hypothesis. Null results are published without reinterpretation.

## Work after the first authentic recognition run

Proceed only when the predecessor result justifies the next cost:

1. construct Lab 05 directions on training domains and evaluate them on held-out
   domains with split-half, bootstrap, permutation, orthogonal, random, and
   opposite-sign controls;
2. start Lab 06 only after an out-of-sample direction exists, then test dose
   response, ablation, bidirectionality, and capability preservation;
3. separate pre-output selection from recognition by annotating what the model
   actually generates after problem-only activations are captured;
4. replicate across an independent model family, dataset, implementation, or
   team before E5;
5. examine intermediate training checkpoints only after the primary recognition
   contract is stable;
6. reserve controlled training and E6 for a separately preregistered Track B;
7. publish versioned releases, tutorials, role-specific onboarding, issue
   milestones, Discussions, and archival assets as first-class reproducibility
   surfaces.

## Deferred until justified

- empirical Lab 05 before held-out-domain recognition;
- Lab 06 steering or causal claims before an out-of-sample direction;
- SAE, Jacobian, sparse-feature, or broad localization work before a stable
  target effect exists;
- expanding beyond Segmentation and Inversion before the two-operator contract
  works;
- using Wave 2 to redesign its own audits;
- promoting a claim from a smoke, dashboard, plot, source check, or partial run.

## Cost- and token-aware execution policy

1. Use deterministic discovery, parsers, targeted tests, and exact Git evidence
   before any LLM task.
2. Give documentation, mechanical migrations, bounded tests, and isolated audits
   to the cheapest suitable worker; provide only the necessary excerpts.
3. Reserve the primary model for architecture, integration, scientific and
   statistical judgment, security, release qualification, and merge decisions.
4. Never depend on an interactive local model-serving application. Do not repeat broad repository discovery when the master
   plan, exact checkpoint, or a recent receipt already answers the question.
5. Run the narrowest relevant validation first. Use the path-aware remote gate,
   and require exact-head CCP for scientific, governance, workflow, dependency,
   or otherwise high-risk changes.
6. Keep one isolated worktree and one owner per file group. Workers do not commit,
   push, merge, or revert other work.
7. At each milestone report: result, terminal validation evidence, claim changes,
   residual risks, and the next dependency.

Cost reduction never weakens an evidence gate. `RUNNING`, partial tests, source
inspection, or a receipt for another commit are not a pass.

## Release and completion definition

The laboratory is not complete merely because all modules exist. Completion
requires a new contributor to be able to:

- clone the public Apache-2.0 repository;
- launch the visual laboratory with one command;
- reproduce at least one complete empirical path using declared assets;
- inspect its frozen inputs, controls, receipts, result, and limitations;
- understand the E0–E6 claim boundary and find published null results;
- contribute through documented researcher, developer, statistician, or TRIZ
  specialist paths without private assistance.

Update this file whenever a milestone status, exact anchor, dependency, or exit
gate changes. Never rewrite a delivered negative result into a success.
