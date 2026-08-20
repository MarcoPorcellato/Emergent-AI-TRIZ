---
type: restart-handoff
title: EXP-002-AUTO no-model checkpoint
status: awaiting-local-commit
---

# EXP-002-AUTO restart handoff

## Completed in the current working tree

- The public protocol, exact seven-model registry, 178 factual records, 160
  source-familiarity formulations, and 48 eight-domain procedural records are
  generated deterministically from registered public sources.
- AUTO-0 through AUTO-5 are fully scheduled. AUTO-5 contains all 24 lexical
  label permutations as six four-permutation shards for each exact model.
- Input hashes are frozen in `experiments/exp002-auto/input-manifest.json` and
  the material dossier binds the protocol, schedule, and input-manifest hashes.
- The public combined-key template is `not_ready` and empty. No answer key,
  model, tokenizer, network, CCP material job, or sealed target has been
  accessed in this checkpoint.
- The new no-model gate checks the contracts, public fixture shape and hash
  bindings, rejects ML-runtime imports in AUTO modules, and fails closed for an
  unapproved dossier. It also has an external-score publication verifier that
  rejects missing/mutated assets and any claim promotion.

## Verification already completed

```text
make exp002-auto-verify                 PASS (25 focused tests)
make schema-cross-validate              PASS (155 tracked pairs)
.venv/bin/python scripts/repository_check.py  PASS (823 tests, 1 expected skip)
make docs-audit                         PASS
git diff --check                        PASS
```

The repository-wide output includes existing intentional failure-path messages
from historical A0/EXP tests; its terminal status is `repository-check: PASS`.

## Required next gates

1. Create a local Git commit for the no-model checkpoint, then rerun exact-head
   no-model qualification and obtain a CCP receipt only after a fresh
   `Admit`/inactive/queue-zero observation.
2. Publish and review the no-model checkpoint before material work.
3. Produce an exact private combined-key receipt and update the dossier with
   its locator, hash, code hashes, and authorization text hash.
4. Obtain a new explicit operator authorization bound to that exact dossier.
   Only then can one authorized local CPU float32 run be considered; no retry,
   tuning, model substitution, or target read is authorized by this handoff.

## Scientific boundary

AUTO can measure response-surface robustness, factual/source familiarity, and
an automated eight-domain procedural proxy. It does **not** validate TRIZ
constructs, replace the H1 expert gate, pool the seven model results, or
support a general TRIZ claim. Every terminal outcome remains exploratory and
claim-free.
