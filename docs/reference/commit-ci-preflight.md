---
type: Reference
title: Commit CI Preflight adoption
description: Local preflight, receipt, and lightweight GitHub verification contract.
status: active
last_verified: 2026-08-12
---

# Commit CI Preflight adoption

The laboratory uses Commit CI Preflight (CCP) to execute repository checks on
reviewed local hardware and to publish a commit-bound receipt. GitHub retains a
small trusted gate that verifies the receipt as data; it does not execute pull
request code.

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
runtime, and a maximum receipt age of 24 hours.

## Remote cost boundary

The receipt gate builds only the verifier pinned to CCP commit
`17737e002a079124d9ce1cb458bd64ab229aa9d8`. It reads the target repository's
trusted base policy and the exact `ccp-evidence/<source-sha>` branch. It never
builds or imports pull request code.

The existing Python validation workflow remains active during bootstrap. It
may be removed only after the receipt workflow has been merged into the trusted
base and one exact-head end-to-end trial is green. Review, protected secrets,
deployment, and native-platform evidence remain separate concerns.
