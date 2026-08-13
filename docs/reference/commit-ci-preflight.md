---
type: Reference
title: Commit CI Preflight adoption
description: Optional local qualification and bounded direct GitHub validation contract.
status: active
last_verified: 2026-08-13
---

# Commit CI Preflight adoption

The laboratory retains Commit CI Preflight (CCP) as an optional local
qualification path for larger or resource-sensitive changes. Small pull
requests run the dependency-free repository check directly on GitHub-hosted
runners so contributors do not need Docker or OrbStack.

## Local contract

The tracked `.commit-ci-preflight.toml` runs `make check` inside an immutable
Python image with no network, one CPU, 256 MiB of memory, and 64 PIDs. The
repository is mounted read-only. A successful run writes the ignored local
receipt `.ccp/receipt.json`.

Run CCP only from an exact clean commit:

```text
make preflight-plan
make preflight-run
make preflight-verify
```

The acceptance policy pins the project identity, configuration digest,
required check, image digest, Apple Silicon macOS host, Docker-compatible
runtime, and a maximum receipt age of 24 hours. The receipt remains useful as
local qualification evidence, but it is not published or required for the
small-pull-request path.

## Remote cost boundary

Pull requests run one `Repository check` job on Python 3.12 with
`contents: read`, no repository secrets, and a three-minute timeout. The job
runs `make check` and the dependency-free schema fingerprint command. Python
3.11 compatibility runs only after a push to `main` or a manual dispatch, so a
small pull request consumes one bounded job rather than a two-version matrix.

The active `main-protection` ruleset requires pull requests, linear squash
history, resolved review threads, and `Repository check`. The automatic CCP
receipt workflow is retired. Review, protected secrets, deployment, release
signing, external-service integration tests, and native-platform evidence
remain separate concerns.
