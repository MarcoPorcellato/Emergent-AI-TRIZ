---
type: Reference
title: Stable merge policy and Commit CI Preflight
description: Path-aware GitHub qualification with exact-head CCP evidence for scientific changes.
status: active
last_verified: 2026-08-16
---

# Stable merge policy and Commit CI Preflight

The protected branch uses one stable required context, `merge-policy/gate`.
A base-branch `pull_request_target` workflow defines separate, least-privilege
jobs. The trusted classifier reads its policy from the base commit. Candidate
checks receive only `contents: read`; the aggregate job receives only
`statuses: write`, performs no checkout, and executes no candidate code.
Unknown surfaces fail closed. Documentation-only pull requests stay
lightweight. Code changes require an exact-head Commit CI Preflight (CCP) v2
receipt for repository and schema checks on Python 3.11 and 3.12; those checks
run in the locally admitted, immutable verification images rather than on
GitHub-hosted candidate runners. Scientific artifacts remain parsed with
trusted base-branch code and dense model files remain external, referenced by a
retained hash.

## Local CCP contract

CCP PR 37 merged at `044697dee9a0d678d30a4847d62ddf9b4970505b` adds the v2
multi-runtime receipt contract. One exact-head local qualification can attest
Python 3.11 and 3.12 coverage with independent runtime identity,
configuration digests, image digests, freshness, check results, and receipt
verification. V1 receipts remain valid historical evidence.

The tracked `.commit-ci-preflight.toml` declares public GHCR Python 3.11 and
3.12 images by immutable digest, with no network, one CPU, 1 GiB of memory,
and 256 PIDs per runtime. It binds `repository_check.py` and
`schema_cross_validate.py` to each runtime. The repository is mounted
read-only. A successful matrix run writes the ignored local receipt
`.ccp/receipt.json`.

Run CCP only from an exact clean commit:

```text
make preflight-plan
make preflight-run
make preflight-verify
```

The acceptance policy pins the project identity, outer and per-runtime
configuration digests, required check-to-runtime assignments, image digests,
Apple Silicon macOS host, Docker-compatible runtime, and a maximum receipt age
of one hour. When the classifier requires CCP, publish the receipt on the commit-bound
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

Latent-TRIZ PR 51 merged the trusted-base runtime classification at
`39ad1965e82f5aa2f4671e38708e401774f176ec`. Its exact source head
`e249c4b42795b27d27d78a0b5c3526a38e7809de` was qualified with receipt branch
`ccp-evidence/e249c4b42795b27d27d78a0b5c3526a38e7809de` (evidence commit
`e4fb6c183483cedd12d9306c29938d1bdedae966`) and terminal run `31934684914`; observed Python 3.11 and CCP
times were 2m44 and 42s. PR 50 then merged at
`e6a634d52fcd153d6c78224fabb8df4713b18415`, publishing the immutable public
GHCR verification images. PR 53 merged at
`64892dd227f7256fe0dae204e501b2867ef4f905`, bridging the trusted verifier to
CCP v2. This remains a routing implementation record, not a cost result: the
matrix/workflow migration is staged until its own exact-head evidence is
qualified and merged.

| Changed surface | Required qualification |
|---|---|
| `docs/**` and public root documents only | documentation audit |
| `src/**`, `schemas/**`, `scripts/**`, `tests/**`, dependencies | exact-head CCP v2 receipt: repository and schema checks on Python 3.11 and 3.12 |
| `data/**`, `experiments/**`, `preregistrations/**`, `results/**` | CCP v2 matrix receipt plus trusted scientific artifact audit |
| model-backed result or dense artifact suffix | scientific gates plus external-artifact/hash policy |
| workflow, policy, or unknown path | CCP v2 matrix receipt; unknown paths also receive the trusted artifact audit |

GitHub runs only the trusted path classifier, the receipt verifier, the
aggregate status, documentation audit for documentation-only changes, and the
trusted scientific artifact audit where required. The receipt verifier does not
check out, build, or execute candidate project code. The artifact-audit job
uses only `contents: read` and parses candidate files with trusted base-branch
code. No job uses repository secrets or persists checkout credentials. The
aggregator publishes only the required exact-head commit status. The v2 matrix
is the code-qualification path; hosted cost is measured only after the
migration's terminal evidence exists.

The active `main-protection` ruleset requires pull requests, linear squash
history, resolved review threads, and `merge-policy/gate`. Review, protected
secrets, deployment, release signing, external-service integration tests, and
native-platform evidence remain separate concerns.
