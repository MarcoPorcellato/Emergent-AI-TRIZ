# EXP-002-AUTO Implementation Plan

> **For agentic workers:** Execute this plan task-by-task. Keep model access,
> tokenizer construction, network access, generation, and sealed-key access
> disabled until the explicit approval stage described in the specification.

**Goal:** Deliver a separately frozen, fully automated EXP-002-AUTO programme
with deterministic no-model fixtures, fail-closed execution gates, and a
hash-bound dossier for later seven-model material work.

**Architecture:** New AUTO modules own all protocol IDs, schemas, fixtures,
stage gates, analysis envelopes, and publication verification. Existing
EXP-002 modules may be imported only through narrow pure functions; their
frozen artefacts and code paths are never modified. The executable material
adapter is intentionally represented by a gate and an injected scorer until a
fresh authorization exists.

**Tech Stack:** Python 3 standard library, existing JSON Schema 2020-12,
existing `jsonschema` validation, `unittest`, repository cross-validator, and
`commit-ci-preflight` only at the later exact-head material gate.

**Spec:** `docs/EXP002_AUTO_PREEXPERT_CAMPAIGN.md`

## Global Constraints

- Keep all A0, R3, EXP-002A/B/C/D paths byte-stable.
- Use the exact seven-model registry imported from `exp002_followup`.
- No model library import or tokenizer construction in contract, fixture,
  schema, unit-test, documentation, or verifier paths.
- AUTO-2 and AUTO-4 target content is generated before access, stored under
  one combined sealed key, and opened exactly once only in a future analysis
  process.
- Per-model results are never pooled and every outcome is exploratory,
  `expert_validated: false`, and claim-free.
- A missing hash, changed shard, bad score, unknown status, or unsafe CCP
  state must fail closed.

---

### Task 1: Define the immutable AUTO contract and schemas

**Files:**
- Create: `src/latent_triz/exp002_auto_contract.py`
- Create: `schemas/exp002-auto-protocol.schema.json`
- Create: `schemas/exp002-auto-schedule.schema.json`
- Create: `schemas/exp002-auto-approval-dossier.schema.json`
- Create: `experiments/exp002-auto/protocol.json`
- Create: `experiments/exp002-auto/model-registry.json`
- Test: `tests/test_exp002_auto_contract.py`

**Produces:** `validate_auto_protocol(protocol)`,
`validate_auto_schedule(schedule)`, and `validate_auto_dossier(dossier)`.

- [ ] Write failing tests that accept exactly seven `EXPECTED_MODELS`, the five
  AUTO stage IDs, all false no-model access flags, and reject a changed revision,
  missing stage, claim ID, or an authorized dossier without the exact protocol
  hash.
- [ ] Run `PYTHONPATH=src python3 -m unittest tests.test_exp002_auto_contract`
  and confirm the missing module failure.
- [ ] Implement only strict mapping/type/hash validators, copied model identity
  from `EXPECTED_MODELS`, and explicit statuses `draft`, `frozen_no_model`,
  `approval_requested`, and `authorized`.
- [ ] Add schemas that reject extra capability flags, unknown terminal states,
  invalid SHA-256 values, and model registry drift.
- [ ] Re-run the focused suite and commit the contract unit.

### Task 2: Build deterministic public and sealed fixture inventories

**Files:**
- Create: `src/latent_triz/exp002_auto_fixtures.py`
- Create: `experiments/exp002-auto/factual-public.jsonl`
- Create: `experiments/exp002-auto/formulation-public.jsonl`
- Create: `experiments/exp002-auto/procedural-public.jsonl`
- Create: `experiments/exp002-auto/combined-target-key-template.json`
- Create: `schemas/exp002-auto-public-record.schema.json`
- Create: `schemas/exp002-auto-combined-target-key.schema.json`
- Test: `tests/test_exp002_auto_fixtures.py`

**Produces:** `build_factual_records`, `build_formulation_records`,
`build_procedural_records`, `build_combined_key`, and `validate_public_records`.

- [ ] Write failing tests proving exact counts `178`, `160`, and `48`; the
  factual family split `40/40/40/40/8/6/4`; exactly eight named domains with
  six procedural records each; no expected answer in a public record; and no
  TRIZ token, principle number, or canonical example in procedural prompts.
- [ ] Run the focused suite and confirm the fixture builder is absent.
- [ ] Implement deterministic builders from the registered principle, Matrix,
  and Panitz fixtures. Use deterministic text templates and local IDs; never
  copy source paragraphs or invoke a model.
- [ ] Implement a combined-key object with automatic provenance,
  `sealed_target_accessed: false`, and no public target content. Its emitted
  template remains `not_ready` until a later approval flow writes the sealed
  materialization outside the public tree.
- [ ] Generate and validate public JSONL manifests; re-run the focused suite
  and commit the fixture unit.

### Task 3: Freeze schedules and shard boundaries

**Files:**
- Create: `src/latent_triz/exp002_auto_schedule.py`
- Create: `experiments/exp002-auto/schedule.json`
- Create: `experiments/exp002-auto/input-manifest.json`
- Test: `tests/test_exp002_auto_schedule.py`

**Produces:** `build_auto_schedule` and `validate_auto_schedule`.

- [ ] Write failing tests that require: AUTO-1 exactly four cyclic plus one
  label-free condition over 24 IDs; AUTO-2 shard sizes `[45,45,44,44]`; AUTO-3
  four formulations for 40 facts; AUTO-4 eight domains; AUTO-5 lexicographic
  24 permutations in six shards of four; no duplicated record-condition pair.
- [ ] Run the test and observe the missing schedule module.
- [ ] Implement schedule generation using existing pure
  `cyclic_permutations` and `all_label_permutations`, then bind every public
  input by SHA-256 in the manifest.
- [ ] Reject missing, reordered, extra, duplicate, or changed mappings before
  writing a schedule.
- [ ] Re-run the test and commit the schedule unit.

### Task 4: Add target-free execution and authorization gates

**Files:**
- Create: `src/latent_triz/exp002_auto_execution.py`
- Create: `src/latent_triz/exp002_auto_stage_gate.py`
- Create: `experiments/exp002-auto/approval-dossier.json`
- Create: `results/exp002-auto/preexecution/execution-receipt-template.json`
- Test: `tests/test_exp002_auto_execution.py`

**Produces:** `score_auto_surface`, `score_auto_candidates`,
`authorize_auto_shard`, and `build_preexecution_receipt`.

- [ ] Write failing injected-scorer tests showing public score records preserve
  identity, condition, finite score vectors, and no target field; all unsafe
  conditions (network, generation, wrong CPU dtype, over-limit, retry count,
  non-Admit CCP, active admission, queue) raise before scorer invocation.
- [ ] Run the focused suite and confirm the new gate is absent.
- [ ] Implement pure injected scoring only; do not import transformers, torch,
  or tokenizers. Dossier state must default to `approval_requested` with an
  ungranted operator approval and empty material receipt.
- [ ] Bind all shard IDs, public-input hashes, combined-key hash placeholder,
  code hashes, seven model identities, and resource ceilings in the dossier.
- [ ] Re-run the focused suite and commit the gate unit.

### Task 5: Build one-read analysis, result envelopes, and publication verifier

**Files:**
- Create: `src/latent_triz/exp002_auto_analysis.py`
- Create: `src/latent_triz/exp002_auto_report.py`
- Create: `schemas/exp002-auto-result.schema.json`
- Create: `schemas/exp002-auto-publication-manifest.schema.json`
- Create: `results/exp002-auto/preexecution/statistical-result-template.json`
- Create: `results/exp002-auto/preexecution/publication-manifest.json`
- Test: `tests/test_exp002_auto_analysis.py`
- Test: `tests/test_exp002_auto_report.py`

**Produces:** `analyze_auto_results`, `verify_auto_publication`, and one
claim-free terminal package per model/stage.

- [ ] Write failing tests for: one combined-key reader call after all score
  asset/hash checks; refusal on a missing or one-byte-mutated score asset;
  no key reader for AUTO-1/3/5; eight-domain AUTO-4 signal/null boundary;
  separated model summaries; and publication rejection if a result has a
  general TRIZ claim or `expert_validated: true`.
- [ ] Run the focused suites and confirm the missing modules fail.
- [ ] Implement fixed AUTO-4 sign-flip analysis through the existing pure
  `evaluate_transfer`, translating `positive` only to `auto_proxy_signal` in
  public wording. Preserve `null`, `failed`, and `non_interpretable`.
- [ ] Implement immutable hash bindings for receipt, result, response index,
  report, recovery observation, and external score asset; never copy dense
  bytes into Git.
- [ ] Re-run focused suites and commit the analysis/publication unit.

### Task 6: Register repository integration and documentation

**Files:**
- Modify: `scripts/schema_cross_validate.py`
- Modify: `scripts/repository_check.py`
- Modify: `Makefile`
- Modify: `docs/EXP002_QWEN3_FOLLOWUP_RESEARCH_PLAN.md`
- Modify: `docs/PERSISTENT_GOAL.txt`
- Modify: `docs/ROADMAP.md`
- Test: `tests/test_exp002_auto_cli.py`

**Produces:** `make exp002-auto-verify`,
`make exp002-auto-stage-preflight`, and a no-model handoff checkpoint.

- [ ] Write failing CLI tests proving no-model verification never imports a
  model library or opens the combined key, while stage preflight returns
  `approval_required` for every AUTO material shard.
- [ ] Run the test and confirm targets do not exist.
- [ ] Add Make targets that run contract/schema/fixture/schedule/analysis
  checks locally; do not add a material run target until the dossier is
  frozen and explicitly authorized.
- [ ] Register every tracked instance/schema pair and mutation rejection in
  both repository validators.
- [ ] Update canonical documentation and persistent goal to state that AUTO is
  an independent, pre-expert exploratory path and record its exact checkpoint.
- [ ] Re-run focused tests, `make docs-audit`, and commit the integration unit.

### Task 7: Qualify and publish the no-model checkpoint

**Files:**
- Create: `docs/EXP002_AUTO_RESTART_HANDOFF.md`
- Modify: `docs/EXP002_AUTO_PREEXPERT_CAMPAIGN.md`
- Modify: `docs/PERSISTENT_GOAL.txt`

- [ ] Run `make exp002-auto-verify`, `make exp002-runner-test`,
  `make schema-cross-validate`, `make docs-audit`, and the repository check.
- [ ] Record exact HEAD, branch, clean status, all passing commands, absent
  model/target access, and the next authorization gate in the handoff.
- [ ] Run one exact-head CCP qualification only after current CCP reports
  Admit/inactive/queue-zero; retain its receipt under the exact evidence branch
  only when the operator separately authorizes publication.
- [ ] Commit the final no-model checkpoint. Push, PR, GitHub checks, and merge
  are separate operator-authorized publication gates.

## Completion audit

The no-model tranche is complete when every task above has code and tests,
tracked schemas validate, no-model commands prove zero model/target access,
and the dossier remains unapproved. The material campaign cannot begin until
the exact resulting dossier hash receives a new explicit operator authorization.
