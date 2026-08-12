# Experiment template 000

This directory contains a skeleton study manifest for protocol-aligned preregistered runs.

Use this template as a non-empirical starting point before data collection and execution.
Populate immutable revision fields only after artifacts are finalized.

- `manifest.json`: concrete study manifest matching [`../../schemas/study.schema.json`](schemas/study.schema.json).
- `run_000_manifest.json`: optional per-run companion matching [`../../schemas/run.schema.json`](schemas/run.schema.json).

## Rules

- Keep every reference immutable (commit hash, dataset snapshot, model revision).
- Treat all timestamps as UTC ISO-8601.
- Use full hashes (sha-256) where hashes are required.
- Placeholder values such as `1970-01-01T00:00:00Z` and `unreleased` are for template scaffolding only and must be replaced before real execution.
- Use `environment.container_image = "none"` only for non-container execution paths.
- Do not add experiment results here; store reports under `results/`.
