# EXP-002 restart handoff

## Current checkpoint

- Branch: `exp002-qwen3-followup`
- Last implementation checkpoint: `8dd287f`
- Scientific state: exploratory, no claim IDs, no evidence promotion
- Model/tokenizer access: not performed by the EXP-002 tranche
- Generation/network/CCP material run: not performed
- Sealed-target access: zero

## Implemented no-model surface

- `docs/EXP002_QWEN3_FOLLOWUP_RESEARCH_PLAN.md`
- frozen seven-model protocol and exact revisions;
- tokenizer audit plan and `not_started` receipt;
- 351-record direct TRIZ question bank with eight balanced task types per principle and sealed answer locators;
- response-surface permutations and label-prior utilities;
- transfer-corpus and statistical contracts;
- fail-closed terminal-result and execution/CCP gates;
- approval dossier in `authorized` state, bound to operator approval hash
  `0c5943ad5a7bf2c598511b8c3ecc29bd566f33140af59c8c6d788f2423483d67`;
- empty preexecution publication manifest;
- deterministic contract target: `make exp002-question-bank-audit`.

## Safe resume commands

```sh
make exp002-question-bank-audit
PYTHONPATH=src .venv/bin/python -m unittest \
  tests.test_exp002_followup \
  tests.test_exp002_surface_and_terminal \
  tests.test_exp002_analysis \
  tests.test_exp002_execution
```

These commands remain model-free. The dossier is now approved, but do not run
a tokenizer, load a model, generate, or open a sealed key until the live CCP
resource/admission gate is rechecked and reports Admit with an inactive empty
queue. A coordinator-layout error is a hard stop; do not bypass it.

## Next material gate

The operator approval is recorded. The remaining external gate is the live CCP
coordinator: `resource status --json` must be Admit and `admission status --json`
must be inactive with an empty queue. After that gate, execute each exact model
once, publish every terminal state, and stop permanently after any model or
target access failure.

## CCP coordination diagnosis (2026-08-20)

The current CCP `origin/main` runbook is pinned to commit `104d48d` in the
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
