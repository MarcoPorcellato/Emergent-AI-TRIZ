# Contributing

Latent TRIZ is an open research laboratory. Contributions should strengthen the audit trail from hypothesis to versioned result, not blur the line between planning and evidence.

## Choose a contribution lane

Every issue and pull request must identify one lane:

1. **Lane 0 — Learning:** reproduce or improve a tutorial, fixture, documentation path, or process smoke. It cannot promote a scientific claim.
2. **Lane 1 — Exploratory:** add a labeled probe, visualization, dataset audit, candidate direction, or methodological investigation. Outputs remain exploratory.
3. **Lane 2 — Confirmatory:** execute a frozen preregistration against a sealed dataset snapshot and immutable run contract.
4. **Lane 3 — Independent replication:** reproduce a prior result with an independent model family, dataset, implementation, or team.

A change to [`data/claims.jsonl`](data/claims.jsonl) must name the `claim_id`, explain any E0-E6 transition, link the required evidence artifacts, and state which falsification condition was evaluated. No claim may advance beyond E0 because repository tests or synthetic smoke fixtures pass.

## Before contributing

Open an issue that states:

- the research question or maintenance task;
- the artifact you want to add or change;
- whether the work is exploratory or confirmatory;
- the provenance and licensing of any external material; and
- the exact files or directories that should change.
- the contribution lane and any intended Evidence Ladder transition.

## Required research discipline

Contributions must:

- distinguish observation, interpretation, and speculation;
- report negative and null results;
- preserve model identifiers, revisions, prompts, seeds, code versions, and environment details;
- keep discovery data separate from sealed evaluation data;
- document lexical, domain, and near-miss controls;
- keep blinded evaluation separate from discovery analysis;
- avoid claims that exceed the available evidence; and
- respect dataset, model, and source licenses.

The canonical promotion rules are in the [Evidence Ladder](docs/EVIDENCE_LADDER.md). New empirical claims start as `E0`, `untested`, and `non_empirical: true`.

## Documentation maintenance gate (OKF)

For any change to maintained documentation:

- run and record a documentation audit against [`docs/index.md`](docs/index.md);
- update `last_verified` in every changed maintained doc frontmatter;
- update related entry points (`docs/index.md`, `docs/README.md`, `docs/reference/index.md`,
  `docs/log.md`, `docs/decisions/index.md`) when navigation, process, or governance scope changes;
- add or update an ADR when interpretation scope or evidence boundary changes.

## Dataset changes

Each case must conform to [`schemas/case.schema.json`](schemas/case.schema.json). Labels should remain multi-label, and disagreements should be preserved rather than collapsed away.

## Preregistrations

Store frozen analysis plans in [`preregistrations/`](preregistrations/). A preregistration should specify hypotheses, data splits, exclusions, metrics, controls, and success thresholds. Amendments must be added as new files.

## Experiments

Place each study in its own directory under [`experiments/`](experiments/). Include the hypothesis, model revision, data snapshot, intervention point, controls, metrics, compute requirements, exact commands, and expected outputs.

## Results

Results belong under [`results/`](results/) and should link to immutable code, data, and preregistration revisions. Do not overwrite earlier reports when analyses change; add a versioned report and explain the delta.

## Quick validation

Repository-level changes should remain compatible with the dependency-free checks used by CI:

```bash
make check
```

For an exact clean commit, produce and verify the local commit-bound receipt:

```text
make preflight-plan
make preflight-run
make preflight-verify
```

For Stage 1 dry-runs and schema checks:

```text
make stage1-pilot-validate
make stage1-pilot-smoke
```
`make stage1-pilot-smoke` prepares Stage 1 packets from `data/pilot/cases.jsonl` with fixed seed `20260812`, compares byte-for-byte against tracked `data/pilot/packets.jsonl`, regenerates `data/pilot/summary.json`, and validates all tracked pilot artifacts against Stage 1 schemas. This is a deterministic process boundary check, not a confirmation step.

See the [Commit CI Preflight reference](docs/reference/commit-ci-preflight.md)
for the evidence publication and GitHub cost boundary.

## Licensing

By contributing, you agree that your contribution is licensed under the Apache License 2.0. Do not submit material that you do not have the right to redistribute.
