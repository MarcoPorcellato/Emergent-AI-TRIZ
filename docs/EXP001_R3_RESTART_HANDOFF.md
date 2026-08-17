# EXP-001 R3 restart handoff

## Checkpoint

- Recorded: 2026-08-18, before operator-requested macOS restart.
- Branch: `agent/exp001-r3-reference-freeze`.
- Exact local checkpoint: `60c39e12503f01f2e60a5864dbf6881a333d112c`.
- Verified public delivery base: `db4cf6d32d263f1df059f6fd376d4cb2bfd38a9c`.
- Worktree at recording: clean; the four pre-existing stashes remain untouched.
- Remote/ruleset/PR state has not been re-verified at this checkpoint and must
  be checked live before publication or qualification.

## Completed no-model work

- R3 source and schema foundation is committed through `60c39e1`.
- `87a54f7` adds a target-free builder that deterministically derives 20
  non-poolable public record stubs from the ten-pair control plan and opaque
  option-set inventory.
- `60c39e1` makes the no-model contract fail closed if the option inventory,
  split bindings, or non-pooling guarantee diverge from the control plan.
- Targeted synthetic validation passed: 14 R3 builder/split/contract tests.
- Schema parity validation passed: 80 tracked schema pairs agree and all four
  required mutations are rejected.

## Deliberately unfinished boundary

The study is not frozen and no model, sealed target, CCP workload, or network
operation has been started for R3. A review found that the present ten-pair
inventory cannot support the declared held-out-domain primary: it has only four
primary domains, a lexical control only for one domain, and placeholder options.
It therefore cannot yield a valid alpha .05 cluster-permutation primary result.

The next milestone is to revise the public, target-free fixture design before
freezing: add at least six independent domains, two problem families per domain,
two task pairs per family, a lexical-matched control for every family/domain,
and semantic public option text with sealed labels. Then freeze the scoring,
cluster permutation, confidence interval, multiplicity, and abstention rules;
only after no-model qualification may an exact authorization dossier be
requested.

## Resume sequence

1. Verify `git status`, branch/HEAD, `origin/main`, worktree inventory,
   stashes, GitHub ruleset/open PRs, and the immutable source/SmolLM2 receipts.
2. Re-run the listed targeted R3 tests and schema cross-validation.
3. Complete the public fixture/statistical design without accessing model or
   sealed targets; update the canonical specification and persistent goal.
4. Qualify the frozen no-model package before requesting any new operator
   authorization. CCP resource/admission checks apply only before a later
   material qualification or model run.

No existing A0-R2/C3 artifact may be modified. No prior execution approval
authorizes the eventual R3 model run.
