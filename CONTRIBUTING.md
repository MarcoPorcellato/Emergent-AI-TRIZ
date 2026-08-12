# Contributing

Project Latent TRIZ is an official-lab foundation. Contributions should strengthen the audit trail from hypothesis to versioned result, not blur the line between planning and evidence.

## Before contributing

Open an issue that states:

- the research question or maintenance task;
- the artifact you want to add or change;
- whether the work is exploratory or confirmatory;
- the provenance and licensing of any external material; and
- the exact files or directories that should change.

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

See the [Commit CI Preflight reference](docs/reference/commit-ci-preflight.md)
for the evidence publication and GitHub cost boundary.

## Licensing

By contributing, you agree that your contribution is licensed under the Apache License 2.0. Do not submit material that you do not have the right to redistribute.
