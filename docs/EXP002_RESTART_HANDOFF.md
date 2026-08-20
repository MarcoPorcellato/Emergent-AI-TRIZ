# EXP-002 restart handoff

## Current checkpoint

- Branch: `exp002-qwen3-followup`
- Last implementation checkpoint: `e47937c` (EXP-002 no-model gates, direct-question and label-free runner paths, sealed target-key contract, source-familiarity boundary, power calibration, review handoff, package-binding verifier, and canonical question-inventory preflight published)
- Scientific state: exploratory, no claim IDs, no evidence promotion
- Model access: one local CPU float32 pass per exact model, all terminal `null`
- Generation/network: disabled for every pass
- Sealed-target access: exactly one analysis-boundary read per model

## Implemented no-model surface

- `docs/EXP002_QWEN3_FOLLOWUP_RESEARCH_PLAN.md`
- frozen seven-model protocol and exact revisions;
- tokenizer audit plan and `not_started` receipt;
- 351-record direct TRIZ question bank with eight balanced task types per principle and sealed answer locators;
- response-surface permutations and label-prior utilities;
- transfer-corpus and statistical contracts;
- EXP-002C target-free corpus template plus validator that rejects source/TRIZ
  leakage, EXP-001 reuse, duplicate fingerprints, and merged expert/generator
  locators;
- direct-answer key gate requiring three pseudonymous reviewers and a frozen
  disagreement policy; the answer-key schema now binds conditional expected
  answers and frozen-review cardinality;
- empty independent-review collection with a question-bank hash and a
  fail-closed packet validator; its JSON schema now binds packet identity,
  independence/access attestations, decision enums, rationale hashes, and
  conditional packet-count/answer requirements;
  no reviewer packet is present yet;
- empty locator-only source-familiarity fixture with a fail-closed provenance
  validator; no canonical excerpt is stored;
- deterministic EXP-002C power calibration receipt selecting eight domains
  before model access; the transfer corpus itself remains pending;
- separate unapproved `EXP-002B` and `EXP-002C` dossiers with exact model
  identities, fixed limits, and a fresh-CCP stage gate;
- injected direct-question scoring boundary and stage-aware runner dispatch;
- fail-closed terminal-result and execution/CCP gates;
- approval dossier in `authorized` state, bound to operator approval hash
  `0c5943ad5a7bf2c598511b8c3ecc29bd566f33140af59c8c6d788f2423483d67`;
- seven immutable EXP-002A baseline packages and aggregate publication manifest;
- deterministic contract target: `make exp002-question-bank-audit`;
- material entry point: `scripts/run_exp002_stage.py` (EXP-002A only); it
  verifies the exact runtime receipt, sets the offline Transformers switches,
  and delegates the one-shot target boundary to the injected runner.

## Safe resume commands

```sh
make exp002-question-bank-audit
PYTHONPATH=src .venv/bin/python -m unittest tests.test_exp002_stage_cli
PYTHONPATH=src .venv/bin/python -m unittest \
  tests.test_exp002_followup \
  tests.test_exp002_surface_and_terminal \
  tests.test_exp002_analysis \
  tests.test_exp002_execution
```

These commands remain model-free. The EXP-002A baseline is complete, but do not
rerun any model or reopen the target key. The next work is to obtain three
independent review packets, freeze the answer key only after their full
coverage and disagreement policy pass, and complete independent EXP-002C
authoring. Do not add placeholder decisions to the collection.

After the live gate is available, provide a fresh JSON snapshot containing
`decision: "admit"`, `active: false`, and `queue_count: 0` to the material
entry point, for example:

```sh
PYTHONPATH=src .venv/bin/python scripts/run_exp002_stage.py \
  --model-id 'Qwen/Qwen3-0.6B-Base' \
  --run-id exp002-qwen3-0-6b-exp002a-1 \
  --ccp-gate /path/to/fresh-ccp-gate.json
```

The command is one model per process and refuses to overwrite a package; the
seven-model loop must invoke it once per exact identity only after the
coordinator gate is independently rechecked.

## Next material gate

The seven-model baseline is published. Before any additional material work,
freeze the label-permutation/tokenizer and direct-knowledge contracts, obtain
any required new approval, then independently recheck the live CCP coordinator:
`resource status --json` must be Admit and `admission status --json` must be
inactive with an empty queue. No baseline model may be rerun.

## CCP coordination diagnosis (2026-08-20)

The current CCP `origin/main` runbook is pinned to commit `5f2ef66` in the
separate `commit-ci-preflight` repository. It makes the admission root and OS
locks host-wide, requires a fresh resource/admission/runtime preflight, and
explicitly forbids manual quarantine or deletion of locks, leases, ticket
files, counters, ownership markers, or the admission root. The installed
`commit-ci-preflight 0.1.0` currently returns `decision=unknown` and
`unsafe admission coordinator layout .../quarantine`; Docker context is
`orbstack` but its API is not readable from this activity. This is an external
CCP/runtime gate, not evidence that the slot is idle. Preserve the state and
do not start a material model run until an exact current CCP installation or
maintainer-approved repair yields a readable Admit/inactive/queue-0 snapshot.

## Independent review handoff

The next human contribution is three independent packets for
`experiments/exp002-qwen3-followup/expert-review-collection.json`. Each packet
must use a distinct pseudonymous reviewer identifier, bind the exact
question-bank SHA-256, cover all `351` question IDs exactly once, and provide a
SHA-256 for each rationale. Reviewers may classify a question as `exact`,
`abstention`, `rubric_required`, or `non_evidential`, but must not see model
outputs or sealed targets. Each packet must attest
`model_access=false`, `sealed_target_access=false`, and independent review.

Do not fill the empty collection with guessed answers, synthetic reviewer
names, or copied source text. Once all three real packets are supplied, run
the expert-review validator, resolve disagreements under the frozen policy,
then replace the answer-key dossier status with a separately hashed frozen
artifact. Only that reviewed artifact can advance EXP-002B authorization.
The repository now provides `freeze_answer_key_from_packets` for this step;
its output remains exploratory and claim-free.

Once the three packets are available, the file-level entry point is:

```sh
PYTHONPATH=src .venv/bin/python scripts/exp002_freeze_answer_key.py \
  --packets /path/to/three-review-packets.json \
  --output results/exp002/preexecution/direct-answer-key.json
```

The command recomputes the canonical question inventory and hash, refuses an
existing output, and performs no model or target access.

For independent EXP-002C authors, audit a public corpus before submitting it:

```sh
PYTHONPATH=src .venv/bin/python scripts/exp002_validate_transfer_corpus.py \
  --corpus /path/to/transfer-corpus.json
```

An empty design template is reported as pending; a frozen corpus must meet the
domain, split, independence, source-proximity, and power-calibration gates;
the corpus schema also rejects an empty `frozen_no_model` record set.
The separate transfer-target-key template is likewise `not_ready`: it carries
no answer records or sealed-file hash until the independently authored corpus
and expert labels are frozen.

The response-surface evaluator is likewise target-free: it requires complete
per-record cyclic/permutation coverage and reports agreement/invariance rates
before assigning `measurement_robust` or `measurement_artifact_supported`.
The direct-question scorer treats `bounded_completion` as a separate generation
capability and rejects it unless an explicit generation authorization is passed;
structured/abstention probes remain the no-generation path.
The injected runner now dispatches EXP-002B through this direct-question path;
EXP-002A and EXP-002C retain the response-surface path.
Source-familiarity metrics use the same injected-observation boundary and are
descriptive only; they never become a provenance claim.

Before requesting a material run, execute the stage preflight:

```sh
PYTHONPATH=src .venv/bin/python scripts/exp002_stage_preflight.py --stage EXP-002B
PYTHONPATH=src .venv/bin/python scripts/exp002_stage_preflight.py --stage EXP-002C
```

The current dossiers intentionally return `approval_required`; no CCP or
model capability is consulted until the relevant answer key/corpus and
operator authorization exist.
