# EXP-002 restart handoff

## Current checkpoint

- Branch: `exp002-qwen3-followup`
- Last implementation checkpoint: `51ba0ac`
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
- approval dossier in `approval_requested` state;
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

These commands must remain model-free. Do not run a tokenizer, load a model,
generate, invoke CCP, or open a sealed key until a new operator approval is
recorded in `experiments/exp002-qwen3-followup/approval-dossier.json` with an
exact dossier hash and the current CCP resource/admission gate.

## Next material gate

The operator must explicitly authorize the exact seven-model dossier, CPU
float32/local-only limits, one run per model, one sealed-target read at the
analysis boundary, publication of every terminal state, and no retry or
substitution. If approval is not granted, continue only with synthetic tests,
schema/hash audits, and documentation.
