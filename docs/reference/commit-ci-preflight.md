---
type: Reference
title: Stable merge policy and Commit CI Preflight
description: Path-aware GitHub qualification with exact-head CCP evidence for scientific changes.
status: active
last_verified: 2026-08-13
---

# Stable merge policy and Commit CI Preflight

The protected branch uses one stable required context, `merge-policy/gate`.
A base-branch `pull_request_target` workflow defines separate, least-privilege
jobs. The trusted classifier reads its policy from the base commit. Candidate
checks receive only `contents: read`; the aggregate job receives only
`statuses: write`, performs no checkout, and executes no candidate code.
Unknown surfaces fail closed. Documentation-only pull requests stay
lightweight. Code changes run the repository and schema checks on Python 3.11
and 3.12.
Scientific and governance changes additionally require an exact-head Commit CI
Preflight (CCP) receipt. Scientific artifacts are parsed and dense model files
are rejected: they must remain external and be referenced by a retained hash.

## Local CCP contract

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
runtime, and a maximum receipt age of 24 hours. When the classifier requires
CCP, publish the receipt on the commit-bound
`ccp-evidence/<40-character-head-SHA>` branch. The trusted workflow verifies
it against the base-branch policy.

## Stable path and risk contract

| Changed surface | Required qualification |
|---|---|
| `docs/**` and public root documents only | documentation audit |
| `src/**`, `schemas/**`, `scripts/**`, `tests/**`, dependencies | repository and schema checks on Python 3.11 and 3.12 |
| `data/**`, `experiments/**`, `preregistrations/**`, `results/**` | repository check, scientific artifact audit, exact-head CCP |
| model-backed result or dense artifact suffix | scientific gates plus external-artifact/hash policy |
| workflow, policy, or unknown path | Python 3.11 and 3.12 plus exact-head CCP; unknown paths also receive the artifact audit |

Candidate test jobs use only `contents: read`. The artifact-audit job also
uses only `contents: read` and parses candidate files with trusted base-branch
code. The aggregate job has only `statuses: write`; it does not check out or
execute the candidate. No job uses repository secrets or persists checkout
credentials. The aggregator publishes only the required exact-head commit
status. CCP verification runs only in the higher-risk lanes. Post-merge
validation remains on both supported Python versions as defense in depth.

The active `main-protection` ruleset requires pull requests, linear squash
history, resolved review threads, and `merge-policy/gate`. Review, protected
secrets, deployment, release signing, external-service integration tests, and
native-platform evidence remain separate concerns.
