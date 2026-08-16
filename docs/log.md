---
type: chronology-log
title: Documentation Chronology
description: Time-ordered notes for maintained documentation and governance updates.
status: canonical
last_verified: 2026-08-16
---

# Documentation Chronology

## 2026-08-16

- Closed the CCP multi-runtime v2 prerequisite at PR 37 merge commit
  `044697dee9a0d678d30a4847d62ddf9b4970505b`. The contract supports exact-head
  Python 3.11/3.12 local coverage with independently bound runtime and image
  digests; historical v1 receipts remain preserved.
- Merged Latent-TRIZ PR 51 at `39ad1965e82f5aa2f4671e38708e401774f176ec`.
  Its exact source head `e249c4b42795b27d27d78a0b5c3526a38e7809de` was qualified by receipt branch
  `ccp-evidence/e249c4b42795b27d27d78a0b5c3526a38e7809de` (evidence commit `e4fb6c183483cedd12d9306c29938d1bdedae966`) and terminal run
  `31934684914`; Python 3.11 took 2m44 and CCP 42s.
- Merged PR 50 at `e6a634d52fcd153d6c78224fabb8df4713b18415`, publishing the
  immutable public GHCR Python 3.11 and 3.12 verification images by digest.
  Merged PR 53 at `64892dd227f7256fe0dae204e501b2867ef4f905`, bridging the
  trusted CCP verifier to v2. The matrix/workflow migration remains staged, so
  hosted candidate checks are still active and no cost saving is claimed yet.

- Merged the trusted CCP timeout migration in two fail-closed steps. PR 48
  changed only the accepted configuration digest and merged at
  `afd4b56ae84a944dc4cd60486caabce9b9452f75` after a receipt produced by the
  existing 120-second plan passed the base policy. PR 49 then changed only the
  repository-check timeout to 180 seconds and merged at
  `85180041717f336de554300dda109731b48c6b95` after its new-plan receipt passed
  the already public policy. Both PRs passed Python 3.11, Python 3.12, exact-head
  CCP, aggregate, and review-thread gates. No candidate policy authorized its
  own receipt, and no model or sealed target was accessed.
- Rebased PR 47 onto the migrated public CCP contract. The R2.2 implementation
  remains pre-output and requires a fresh exact-head receipt plus terminal
  hosted gates before merge. R2.3 remains separately approval-gated.

## 2026-08-15

- Qualified the complete R2.2 implementation locally at exact head
  `e9df61830611cff2c3acf60ea1382cdf9968e1b8`. The full repository suite and
  exact-head CCP repository check pass, and the clean receipt matches that
  head. No model or sealed target was accessed. The branch and receipt remain
  unpublished, so this is a resumable local checkpoint rather than merged
  evidence; R2.3 remains approval-gated.
- Merged the R2.1 publication and receipt branch through PR 46 at
  `1f35ba353e792aa263db7449216e3172d0306798` after exact head
  `5f9c21db944f25fd1dac4a550911c85e86471e35` and public receipt publication.
  R2.1 is now verified complete. R2.2 is in delivery as the local/offline
  SmolLM2 tranche with 192 forwards, 1920 vectors, the final-block primary,
  descriptive layers, views, and sites, fixed primary thresholds, strict
  single target read, failure publication, and descriptive-only cross-model
  concordance and resource-envelope refusal. Fifty-five focused synthetic tests currently pass, the
  execution contract verifies 11 code files and 9 runtime files without model
  load, and no real model load or sealed-target access occurred. R2.3 remains
  explicitly approval-gated.
- Began the no-human-review A0-R2 study preregistration from public main
  `25c978d89a07fcd66194f8e0e333ebdae2f6bc08`. The planned study keeps one fixed
  cross-model primary, freezes broad descriptive sensitivities and negative
  controls before output, forbids sensitivity rescue and claim promotion, and
  retains a separate explicit gate for one sealed/material execution.
- Merged the A0-R2 feasibility contract through PR 44 at
  `da8f4bb0c07fe32ede438b13da80b89019cfb812`, then executed the one authorized
  CPU-only probe. The schema-valid receipt reports `compatible`, 33 hidden-state
  entries, repeatability difference 0.0, 2,540,519,424 bytes peak RSS, and
  3.813451875 seconds total time. The outer CCP guard exited 70 with cleanup
  uncertain at `completed descendant seal`; a separate post-run observation
  records an inactive admission gate, empty queue, no matching processes, and
  no retroactive guarded PASS. The model was not rerun, no output content was
  retained, and sealed targets remained untouched.
- Merged the A0-R2 acquisition checkpoint through PR 43 at
  `5d4d96c16b56715203aa8a077b13d3b6cc550fc9` after publishing the exact-head
  CCP receipt and obtaining a green trusted aggregate. The external nine-file
  snapshot remains integrity-verified and ignored by Git.
- Started the separately authorized A0-R2 bounded feasibility tranche by
  freezing a pre-load CPU float32 contract. The tranche allows only a fixed
  synthetic probe, two non-generative forward passes, compatibility, timing,
  repeatability, and memory measurements. It remains instrumentation-only;
  sealed targets, sealed R2 execution, and scientific inference stay blocked.
- Published the terminal A0-R R1 package through PR 41 at merge commit
  `05ba15a28442260c32951413c9128f0179573198`. The immutable package retains
  the raw output, deterministic 54-label clerical recovery, recovery receipt,
  activation receipt, 96-record representation index, report, manifest, and
  external dense-asset locator. The fixed primary remains positive exploratory
  E0 evidence: 23/24 family successes, macro-F1 0.624348 versus 0.499130,
  margin 0.125217, six domain-direction successes, and permutation p = 0.002.
  Exact-head repository qualification and all seven hosted checks passed; A0
  stayed byte-stable, claim IDs stayed empty, and H1/Wave 2 were untouched.
  At that closeout, R2 model acquisition and material execution remained
  explicitly approval-gated.
- Recorded the authorized SmolLM2 runtime acquisition: nine files at revision
  `f8027fd0eaeea54caa13c31d31b9fdc459c38b49`, 727,058,433 bytes total, receipt
  status `integrity_verified`, weights SHA-256
  `7aaff6661428bed033abba9522bec81938678642cca3181fe752b6ca9e1e540f`, all
  access flags false. This is instrumentation-only and evidence-ineligible.
  Model load, feasibility, output generation, sealed targets, and any sealed R2
  run were not authorized and were not performed.
- Merged the A0-R R1.4b harness in PR 40 at
  `c5b28cd3ffca38a4bbdca076ba4bff306e653aa6`, then executed the frozen R1
  endpoint once. The exploratory result is positive: 23/24 family successes,
  macro-F1 0.624348 versus 0.499130 for the surface baseline, margin 0.125217,
  six domain-direction successes, and permutation p = 0.002. The raw output's
  clerical `r1_` prefix failed schema validation; R1.5 preserves it and records
  a deterministic 54-label recovery with no metric changes and no additional
  model or sealed-target access.
- Merged A0-R R1.4a at `73d5e1cad5422d24209252257b54a46c24f8ee16`
  after exact-head qualification and hosted gates. The checkpoint binds the
  runtime, inputs, code, classifier, permutation, baseline, and domain rule;
  it accessed neither model output nor sealed targets. R1.4b is now preparing
  a separately bound runner and remains pre-output until that harness is
  reviewed, qualified, and merged. The harness records operational exceptions
  in a separate immutable receipt with tri-state access evidence; it does not
  fabricate a statistical outcome or treat uncertain access as non-access.
- Froze the A0-R R1.3 calibration and protocol state: exact-binomial power
  receipt now records false-positive rate `0.03195732831954956`, power
  `0.9108287412264922` under family-success probability `0.8`, minimum
  detectable effect `0.2597184664182352`, `100000` deterministic simulations,
  and minimum permutation p-value resolution `.001`. R1.3 merged to `main` and
  the protocol is frozen before model output, with no model or sealed output
  accessed. R1.4a subsequently merged with fixed runtime/input/code hash binding,
  fixed classifier/permutation/baseline/domain-statistic specification, and
  synthetic-adapter / synthetic-vector tests only. Model activation and sealed
  inference remain blocked behind the R1.4b pre-run harness gate.
- Completed the pre-freeze A0-R R1.2 corpus substrate: 48 independent families,
  96 paired cases, physically separate 48-case calibration and sealed target
  files, zero independence-audit violations against the 192-case A0 source,
  and 14/14 passing shortcut controls. Added strict artifact schemas and
  `make a0r1-verify` for byte-for-byte regeneration. No model output was
  accessed and the protocol remains planned pending the R1.3 power freeze.
- Started A0-R R1.1 with a planned protocol and strict schema fixing the
  same-model primary endpoint, power thresholds, E0 envelope, and immutable A0
  source anchors. Added a fail-closed independence auditor whose API keeps
  calibration and sealed targets physically separate. This is implementation
  substrate, not a freeze or empirical result.
- Published the complete A0 sealed exploration through PR 34 at merge commit
  `fc80976d3a256ed88e2d59f1a6f893e15154e3a0`. The frozen automated-proxy
  result is positive with maximum-statistic p = 0.005, 24/24 paired-family
  successes, and macro-F1 margin 0.188234 over the problem-only baseline.
- Preserved the result boundary: exploratory, evidence-ineligible, not
  expert-validated, empty claim links, and no promotion from E0.
- Closed the stale A0 delivery notes, added the separate A0-R independent-corpus
  and cross-model replication contract, and added a concise persistent goal
  pointing to the canonical Laboratory Master Plan.
- A0 protocol checkpoint `v1.0.3` was frozen before any model-backed or sealed
  execution. The deterministic label-free corpus is 96 families / 192 cases.
- Calibration and sealed evaluation files were separated at manifest level, with
  `sealed_targets_accessed: false`.
- Initial v1.0.1 corpus setup was rejected for shortcut calibration and replaced
  pre-freeze with token-matched unique role-pair redesign.
- All 14 shortcut controls passed on the 96 calibration cases.
- Power-calibration parameters fixed as 4 problem families/domain, 24 problem
  families total (48 paired cases), 199 permutations, critical threshold 19,
  MDE 0.333212784429589.
- The later exact-model sealed run and publication are recorded above; no TRIZ
  validation claim is made.
- The next automated milestone is a separately frozen A0-R replication, not a
  mutation or rerun-in-place of the published A0 result.

## 2026-08-14

- Added the canonical Phase A0 specification for a fully automated,
  exact-revision, counterfactual proxy exploration of the Weak Latent TRIZ
  Hypothesis. A0 freezes its design before sealed evaluation, publishes null and
  failed outcomes, remains independent from H1 and Wave 2, and cannot promote an
  expert-validated TRIZ claim.
- Added the canonical Laboratory Master Plan: an evidence-bounded evolution
  ledger from the verified PR 1–29 foundation through annotation v1.2, the
  permanent Wave 1 negative control, paired label-free Wave 2, canonical human
  labels, empirical envelope v2, multi-view model artifacts, and the first
  authentic EXP-001-R path. The plan records exact exit evidence, claim impact,
  residual risk, deferred work, and the cost-aware delegation policy.

## 2026-08-13

- Added the stable path- and risk-aware merge policy contract: lightweight docs qualification, dual-version Python checks for code, exact-head CCP plus artifact auditing for scientific changes, and scheduled live ruleset drift detection.
- Reordered the research program after the retained Wave 1 negative surface result: integrity hotfixes and stable governance now precede annotation v1.2, immutable calibration-only Wave 1, label-free counterfactual Wave 2, canonical human labels, and the first empirical recognition run. Empirical direction and causal work remain deferred until held-out-domain generalization is demonstrated.
- Replaced Lab 04 all-layer Holm gating with shared, domain-blocked max-statistic control, nested alpha reselection within every permutation, explicit p-resolution refusal, typed public receipts, and regenerated fail-closed Lab 04–05 fixture artifacts.
- Updated the v1.1 annotation ontology workflow: four primary ontology labels plus
  abstain, canonical case and batch hashes in annotation records, v1.1.0 display
  version, nominal Krippendorff alpha in blinded-audit output, and explicit
  frozen agreement policy in the stage-1 guide and audit schema.
- Added deterministic, case-clustered 95% bootstrap intervals for raw agreement
  and nominal alpha as descriptive calibration metadata under a frozen seed and
  resample count.
- Added the Wave 1 retained audit command for per-rater files, including
  exact guide digest checks, full coverage, pairwise agreement and abstention
  thresholds, consensus and disagreement retention, and a non-evidence
  boundary for `artifacts/annotations/wave1-audit.json`.
- Documented the Wave 1 candidate batch as discovery-only: 24 model-generated Segmentation/Inversion cases across four domains, reciprocal opposite-label pairs, lexical-cue exclusions, non-frozen status, and evidence ineligibility.
- Added the acceptance path for Wave 1 to the protocol: two independent raters, abstentions, agreement checks, provenance expansion, split freeze, and leakage audit before confirmatory use.
- Added the blinded localhost annotation workbench documentation path, with
  sanitized case views, Segmentation/Inversion-only labeling, local append-only
  outputs, and an explicit non-evidence boundary.
- Promoted the commit-bound CCP receipt to the primary pull-request gate after repeated exact-head end-to-end trials; retained the Python matrix on `main` and manual dispatch to reduce duplicate GitHub Actions execution.
- Added Lab 05 candidate-direction instrumentation with D1-D8 gates, seeded and unrelated-label controls, sparse public artifacts, and an explicit no-steering/no-causality boundary.
- Added the one-command local visual laboratory suite for navigating the maintained Lab 00 through Lab 05 artifacts with explicit readiness, provenance, and no-claim boundaries.
- Added Lab 03 behavioral-baseline contracts, deterministic local diagnostics, leave-one-domain-out and random-label gates, and an explicit no-claim visual report.
- Added Lab 02 dataset anatomy with immutable split membership, provenance/license checks, source/template leakage fingerprints, balance gates, annotation reliability, and a one-command visual readiness report.
- Added Lab 01 as the first exact-revision, real-model instrumentation laboratory with receipt-derived readiness, residual-stream capture, final-logit parity, repeatability, sparse public artifacts, and an explicit no-TRIZ-claim boundary.
- Added fail-closed evidence-profile obligations to claim-level promotion and target-specific readiness for the foundation, Lab 01, and EXP-001.
- Added offline model-preflight and dataset-audit gates for EXP-001 readiness, with deterministic JSON reports and no-download enforcement.
- Renamed the public laboratory to Latent TRIZ and updated repository identity references.
- Added the canonical E0-E6 Evidence Ladder, strict claim schema, and three explicit E0 hypotheses.
- Reframed the public entrance around the runnable Stage 1 process smoke and its non-empirical boundary.
- Added four contribution lanes and a staged visual/mechanistic-interpretability roadmap.
- Added the one-command, dependency-free Lab 00 visual smoke, explicitly infrastructure-only and not claim-attached.
- Recorded the provisional EXP-001 model roles and synthetic-first dataset strategy in ADR 0003 without promoting claims or freezing a preregistration.

- Initialized the Matryca Knowledge OKF maintained-bundle documentation structure.
- Added documentation portal pages and ADR 0001 for the dependency-free official-lab foundation.
- Wired root README, CONTRIBUTING, and PR template to require documentation checks and timestamp updates.
- Added a deterministic zero-LLM OKF gate for metadata, lifecycle, safe entry points, links, anchors, and unique canonical roles.
