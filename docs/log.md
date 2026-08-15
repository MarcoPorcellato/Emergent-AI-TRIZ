---
type: chronology-log
title: Documentation Chronology
description: Time-ordered notes for maintained documentation and governance updates.
status: canonical
last_verified: 2026-08-15
---

# Documentation Chronology

## 2026-08-15

- Merged A0-R R1.4a at `73d5e1cad5422d24209252257b54a46c24f8ee16`
  after exact-head qualification and hosted gates. The checkpoint binds the
  runtime, inputs, code, classifier, permutation, baseline, and domain rule;
  it accessed neither model output nor sealed targets. R1.4b is now preparing
  a separately bound runner and remains pre-output until that harness is
  reviewed, qualified, and merged.
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
