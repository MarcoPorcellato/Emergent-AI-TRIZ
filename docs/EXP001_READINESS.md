---
type: Runbook
title: EXP-001 Readiness Gates
description: Fail-closed boundary between a recorded study decision and permission to freeze or execute EXP-001.
status: canonical
last_verified: 2026-08-13
---

# EXP-001 readiness gates

EXP-001 is not preregistered, frozen, acquired, or executed. The offline gates introduced here make that boundary observable without downloading model weights.

## One-command report

```bash
make readiness
```

This runs:

- `model-preflight`: validates the three recorded model roles, exact revisions, license/terms provenance, and the explicit `not_acquired` state;
- `dataset-audit`: validates record references, matched-control symmetry, lexical exclusions, duplicates, split leakage, source policy, and development target gaps.

A valid model manifest means only that the decision record is internally consistent. `acquisition_ready` and `experiment_ready` remain false until an operator records the required external receipts and local feasibility evidence. A development dataset may pass structural checks while `freeze_ready` remains false.

## Scientific claim separation

EXP-001 will not use a single result to stand for three different mechanisms:

| Claim path | Input state | Permitted interpretation |
|---|---|---|
| Recognition | Problem plus completed solution | Cross-domain semantic decodability |
| Pre-output selection | Problem and contradiction before generation | Prediction of the later operator choice |
| Causal control | Frozen intervention and controls | Controlled change in operator-consistent generation |

Recognition cannot promote selection or causal-control claims.

## Remaining blockers

- acquire no model until current terms, revision availability, disk/memory requirements, and interpretability access are receipted;
- expand and annotate the development corpus before any freeze-mode audit can pass;
- freeze two independent raters per response and a preregistered agreement statistic for empirical runs;
- keep evaluator packets physically separate from the sealed allocation key;
- freeze lexical, domain-transfer, random-direction, label-permutation, dose-response, and capability-preservation controls;
- protect `main` with a commit-pinned ruleset after the required check names are verified.

Lab 00 remains infrastructure-only. Lab 01 will use a separate didactic model role and will not by itself promote a TRIZ claim.
