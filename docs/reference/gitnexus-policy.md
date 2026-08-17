---
type: operational-policy
title: GitNexus code-intelligence policy
description: Rules for using the local GitNexus graph without treating generated structure as source truth.
status: canonical
last_verified: 2026-08-17
---

# GitNexus code-intelligence policy

Latent-TRIZ follows the GitNexus operating convention used by the Matryca
repositories. GitNexus is a local structural map for navigation, process
discovery, and impact evidence. Source files, tracked protocols, receipts, and
runtime tests remain authoritative.

## Routing and evidence

- Use deterministic repository tools first. Use GitNexus for graph, process,
  dependency, and blast-radius questions; use live source inspection and tests
  to confirm the result.
- When the language and worktree are supported, use precise live symbol tools
  after GitNexus for bodies, references, and edits.
- A stale or missing index, unsupported language, empty PDG layer, or degraded
  graph is not evidence of safety. Report the limitation and fall back to
  bounded live reads and tests.
- Never treat generated graph descriptions, clusters, or inferred relationships
  as scientific, security, or release evidence by themselves.

## Required change gates

- Before changing a function, class, or method, run GitNexus `impact` upstream
  for the symbol and record direct callers, affected processes, risk, and
  limits. Warn before proceeding when the risk is `HIGH` or `CRITICAL`.
- Before committing, run `detect_changes` against the intended scope. For a
  branch review, compare with the default branch and confirm that affected
  symbols and processes match the change.
- Do not rename symbols with find-and-replace. Use semantic rename support or
  an equivalent reference-aware edit, then rerun the affected checks.
- GitNexus output never replaces runtime verification, schema validation, or
  exact-head qualification.

## Index lifecycle

- The index is local, regenerable state under `.gitnexus/`; it is ignored and
  must not contain public study data, model weights, secrets, or receipts.
- Do not rebuild, clean, or mutate the index during a read-only review or merely
  because it is stale. Reindex only when the task explicitly authorizes index
  maintenance.
- After an authorized material repository change, run:

  ```text
  node .gitnexus/run.cjs status
  node .gitnexus/run.cjs analyze
  node .gitnexus/run.cjs status
  ```

- Record the indexed commit, branch, timestamp, and graph counts in the
  handoff or audit that requested the reindex. Do not commit GitNexus-generated
  root `AGENTS.md` or `CLAUDE.md` files; repository policy belongs here.

## MCP and CLI references

- Context and process resources use `gitnexus://repo/Latent-TRIZ/...`.
- Read-only orientation uses `query`, `context`, and process resources.
- Change review uses `impact` and `detect_changes`.
- Index maintenance uses the repository-local GitNexus CLI skill and remains a
  separately authorized operation.
