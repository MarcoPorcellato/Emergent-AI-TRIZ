# EXP-001 R3 restart handoff

## Checkpoint

- Recorded: 2026-08-18, before operator-requested macOS restart.
- Branch: `agent/exp001-r3-reference-freeze`.
- Exact local checkpoint before this handoff commit: `fd7d3411abfc88dd7cbc36100544227e6667bf35`.
- Verified public delivery base: `db4cf6d32d263f1df059f6fd376d4cb2bfd38a9c`.
- Worktree at recording: clean; the four pre-existing stashes remain untouched.
- Remote/ruleset/PR state has not been re-verified at this checkpoint and must
  be checked live before publication or qualification.

## 2026-08-18 continuation checkpoint

- `b1ab0d6` replaces the unbalanced draft with 24 public, target-free primary
  units across six domains, two families per domain, and two replicates per
  family. The semantic intended positions are rotated six times each over
  `A`–`D`; no answer mapping is stored in the public fixture.
- `e91e420` defines teacher-forced four-option scoring; `5ac2f89` adds the
  fail-closed no-model execution preflight; `bd016be` adds a local-only
  SmolLM2 adapter; and `a216eeb` adds the target-free response-execution
  layer. All are synthetic-tested only: no R3 model load, target read, output,
  CCP workload, or network operation has occurred.
- `2e7c510` hardens teacher-forced scoring for tensor-backed tokenizer output,
  causal continuation positions and token-prefix drift; `fd7d341` adds the
  terminal package schemas. Both are synthetic-only checkpoints.
- `stash@{0}` and `stash@{1}` preserve rejected pre-balance fixture drafts as
  historical recovery evidence. They must remain untouched and must not be
  applied over the corrected committed fixture.

## Completed no-model work

- R3 source and schema foundation is committed through `a216eeb`.
- `87a54f7` adds a target-free builder that deterministically derives 20
  non-poolable public record stubs from the ten-pair control plan and opaque
  option-set inventory.
- `60c39e1` makes the no-model contract fail closed if the option inventory,
  split bindings, or non-pooling guarantee diverge from the control plan.
- Targeted synthetic validations passed for the fixture, analysis, execution,
  adapter, response-execution, and analysis-boundary modules. A full no-model
  suite and schema parity check remain required before freezing.

## Deliberately unfinished boundary

The study is not frozen and no model, sealed target, CCP workload, or network
operation has been started for R3. The public fixture is now structurally
adequate for the declared six-domain exact primary, but it still lacks the
frozen implementation binding, terminal-package schemas and writers, a
human-independent/source-derived sealed-key procedure, and full exact-head
no-model qualification.

The next milestone is to complete the R3-specific model scoring integration and
immutable package/verification path, then freeze the implementation and
statistical bindings. Only after exact-head no-model qualification may an exact
authorization dossier be requested and the sealed key created at the authorized
analysis boundary.

## Resume sequence

1. Verify `git status`, branch/HEAD, `origin/main`, worktree inventory,
   stashes, GitHub ruleset/open PRs, and the immutable source/SmolLM2 receipts.
2. Re-run the listed targeted R3 tests and schema cross-validation.
3. Finish and synthetic-test the real local teacher-forced option-scoring
   adapter. In particular, validate tensor normalization, prompt/continuation
   prefix stability, continuation log-probability positions, offline-only
   loading, and absence of generation.
4. Add and test immutable R3 execution, result, report, and publication
   manifests; then freeze implementation hashes and update the canonical
   specification and persistent goal.
5. Qualify the frozen no-model package before requesting any new operator
   authorization. CCP resource/admission checks apply only before a later
   material qualification or model run.

No existing A0-R2/C3 artifact may be modified. No prior execution approval
authorizes the eventual R3 model run.
