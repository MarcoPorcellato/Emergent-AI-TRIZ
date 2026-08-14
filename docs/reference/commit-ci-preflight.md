---
type: Reference
title: Stable merge policy and Commit CI Preflight
description: Path-aware GitHub qualification with exact-head CCP evidence for scientific changes.
status: active
last_verified: 2026-08-14
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

### Installed macOS v3 resource admission

The locally installed CCP binary was rebuilt from the commit-ci-preflight PR 35
merge at exact upstream commit
`9c506890880b89747462c0d21087e49abe78b8ee`. Its active host policy is
`macos-v3`:

- available RAM must be at least 20%;
- swap must remain below the smaller of 8 GiB or 30% of physical RAM;
- pre-start compressor use must remain below 40%;
- runtime compressor use above 40% is a soft-pressure signal only after three
  consecutive samples;
- runtime compressor use above 45% is immediate hard pressure.

Before an official guarded runner, execute:

```text
commit-ci-preflight resource status --json
commit-ci-preflight admission status --json
```

Proceed only when admission returns `Admit` and there is no active or queued
run. `Unknown` and `Deny` remain fail-closed and must not authorize a retry or
runner start.

The Rust 1.96 Bookworm runner image is pinned to
`sha256:5e2214abe154fe26e39f64488952e5c991eeed1d6d6da7cc8381ae83927f0cfc`
and cached persistently in OrbStack. Preserve `macos-v2` receipts as historical
evidence; never relabel them as `macos-v3`. The still-draft upstream CCP PR 34
is not part of the installed contract.

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
