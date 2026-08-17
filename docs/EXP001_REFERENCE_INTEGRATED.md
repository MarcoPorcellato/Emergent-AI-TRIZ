---
type: research-specification
title: EXP-001 Reference-Integrated TRIZ Study
description: Durable preregistration for a source-aware, source-blinded, label-safe study using the public TRIZ reference layer.
status: draft_preregistration
version: 0.1.0
last_verified: 2026-08-17
---

# EXP-001 — reference-integrated TRIZ study

This specification is the canonical execution contract for the next Latent-TRIZ
milestone. It is deliberately separate from the frozen A0-R2 protocol and does
not amend, rerun, or reinterpret any A0-R2 artifact.

## 1. Purpose and falsifiable outcome

Measure whether the already acquired SmolLM2 model can perform narrowly defined
TRIZ reference tasks under two non-poolable conditions:

1. `TRIZ-blinded-transfer`: independently authored problems contain no TRIZ
   names, source wording, canonical examples, matrix cells, or tool-map edges.
   This is the only arm that can test a rediscovery-like transfer signal.
2. `source-exposed-competence`: the same task families are paired with a cited,
   bounded reference context. This measures retrieval, interpretation, and use,
   never rediscovery.

The primary falsifiable outcome is a preregistered held-out-domain transfer
score in the blinded arm against a lexical-matched non-TRIZ control. Secondary
outcomes are source-exposed principle retrieval, direction-aware Matrix 2003
cell agreement, and supported-versus-unsupported tool-transition selection.
Every outcome is exploratory E0 until independent human labels and a later
confirmatory protocol exist.

A positive result may state only that the corresponding automated reference-task
signal exceeded its frozen control. It may not be called TRIZ rediscovery,
inventiveness, novelty, expert competence, causal reasoning, or expert-validated
TRIZ.

## 2. Verified anchors

The live starting anchor is public `main` commit
`f60afc8d9f2803a6a988f26f6c520dd72659080a` (verify `origin/main` before every
mutation). The current reference layer is:

| Artifact | SHA-256 | Scientific status |
|---|---|---|
| `data/triz-reference-sources.json` | `a3bd9283b7e73ebd723bcfab8edb9599161e37a47686b6c25e652158d2158273` | metadata/provenance only |
| `data/triz-reference/principles.jsonl` | `7baa3b74f7a5ee7ca5fe9303baf64361a5cbcdfea0cb0c539e00bb74db764249` | 40 independently worded summaries, not labels |
| `data/triz-consulting-web-corpus.json` | `e397160adfc60c534d16b5cd934deddb3e3500bb8f99f7fef26a2b6d4c2eff46` | metadata-only site catalogue |
| `docs/reference/triz-reference-corpus.md` | `92429183119e463090df170f4ec29bf0f0e43ee531f47898c8071325a3b7435f` | canonical rights and epistemic boundary |

The three supplied public references remain external copyrighted material. No
PDF, screenshot, bulk matrix table, or verbatim extract may be vendored under
the repository Apache-2.0 licence. The Panitz map remains user-attributed and
not independently verified as a canonical ontology.

The SmolLM2 model identity, runtime-file receipt, feasibility receipt, and prior
C3 activation bundle remain immutable inputs. Their exact hashes must be copied
into the new protocol and execution receipt; no new model download is planned.

## 3. Status vocabulary and epistemic envelope

Use these machine-readable states: `draft`, `ready_for_review`, `frozen`,
`approval_requested`, `authorized`, `running`, `positive`, `null`, `failed`,
`non_interpretable`, `incompatible`, and `published`.

`source_exposed` means a bounded source-derived context is intentionally shown.
`TRIZ_blinded` means no source-derived lexical or structural cue is shown.
`reference_task` means agreement with a recorded source recommendation; it is
not a ground-truth claim about the quality of a proposed solution.

All results are `scientific_status: exploratory`, `expert_validated: false`,
`claim_ids: []`, and `evidence_eligible: false` unless a later human-governed
protocol explicitly changes those fields.

## 4. Scope, non-goals, and invariants

In scope:

- all 40 principle records as authoring references;
- a small, double-checked Matrix 2003 cell fixture with page/table locators;
- a small, independently transcribed Panitz tool-edge fixture with edge status;
- paired blinded/exposed variants, lexical controls, held-out domains, and
  source-family splits;
- one bounded SmolLM2 run that processes both strata in one guarded invocation;
- immutable receipts, statistics, reports, limitations, and public publication.

Out of scope:

- changing A0-R2 prompts, targets, thresholds, model identity, or claims;
- treating a principle, matrix recommendation, or Panitz edge as universal
  ground truth;
- claiming that source exposure demonstrates latent rediscovery;
- human or LLM judging in the automated run;
- downloading a new model, accepting new terms, or publishing third-party PDFs;
- pooling blinded transfer with source-exposed retrieval in one score.

Invariants:

- source registry and existing A0-R2 bytes remain byte-for-byte unchanged;
- every item has source ID, locator, derivation method, exposure mode, domain,
  family, lexical-overlap score, canonical-example proximity, and rights state;
- source-derived recommendations and independent human labels are separate
  fields and are never silently substituted;
- the primary endpoint, controls, stopping rule, and multiplicity are frozen
  before any model output;
- sensitivity analyses cannot rescue a failed primary;
- missing, stale, mismatched, or uncertain receipts fail closed;
- positive, null, failed, non-interpretable, and incompatible packages are all
  published.

## 5. Ordered milestones

### R3.0 — no-model source and protocol readiness

Create `experiments/exp001-reference-integrated/` with a strict protocol,
item, source-exposure, matrix-cell, tool-edge, and publication schema. Validate
the existing registry, exactly 40 principles, exactly 18 web resources, rights
flags, hashes, and no-local-path policy. Do not download sources, load a model,
open sealed targets, or alter A0-R2.

**Exit evidence:** schema cross-validation, source/hash audit, rights audit,
clean worktree, and a reviewable protocol diff.

### R3.1 — independent fixture construction and contamination audit

Build independent paraphrases and domains from the reference summaries without
copying canonical examples. Encode a sparse matrix fixture only after two
independent visual checks against Matrix 2003. Encode only clearly supported
Panitz edges and mark uncertain or unsupported transitions explicitly. Add
near-neighbour principles, swapped matrix directions, unsupported edges,
abstentions, lexical-matched non-TRIZ controls, and canonical-example proximity
audits.

The fixture must be split by source family, problem family, and held-out domain
before any model output. The blinded and exposed variants must share the same
underlying task identity but remain separately addressable and separately
scored.

**Exit evidence:** frozen fixture manifest, independent derivation receipts,
lexical-overlap report, source-family/domain split report, matrix double-check
receipt, tool-edge status receipt, and synthetic power/permutation calibration.

### R3.2 — statistical and implementation freeze

Freeze one primary: blinded held-out-domain transfer versus the lexical-matched
control, using family-grouped leave-one-domain-out evaluation. Freeze distinct
secondary endpoints for exposed principle retrieval, Matrix 2003 exact-cell
agreement, and tool-edge selection/abstention. Declare the exact score,
permutation/bootstrap scheme, seed, multiplicity correction, confidence
intervals, minimum family/domain support, and terminal classification before
model access. Reuse existing kernels only after a compatibility review; do not
inherit A0 thresholds by assumption.

Bind the exact SmolLM2 revision, prior integrity/feasibility receipts, code
hashes, fixture hashes, runtime limits, and no-claim envelope. Synthetic
adapters/vectors must cover both strata and every terminal class.

**Exit evidence:** frozen protocol, code/fixture hash manifest, mutation tests,
synthetic statistics tests, exact-head CCP qualification, and a separate
operator approval dossier.

### R3.3 — one guarded model run

After explicit approval of the frozen dossier, check CCP `resource status
--json` and `admission status --json`; proceed only with `decision=admit`,
`active=false`, and `queue_count=0`. Run SmolLM2 locally in one CPU float32
invocation, offline and without generation unless the frozen protocol requires
structured output. Use the already acquired snapshot only. Apply a conservative
30-minute wall-time, 8 GiB peak-RSS, and 128 MiB new-dense-output ceiling unless
the approved dossier freezes stricter limits.

No tuning, model substitution, protocol change, post-output retry, or sealed
target access outside the declared analysis boundary is permitted. If any
runtime or tokenizer mismatch occurs, publish `incompatible` or `failed` and
stop.

**Exit evidence:** exact runtime receipt, access receipt, activation/response
index, terminal statistical result, recovery observation, and immutable logs.

### R3.4 — publication and fresh-clone verification

Publish the package on a dedicated branch and PR, publish the exact-head CCP
receipt on `ccp-evidence/<exact-head>`, and merge only after hosted CCP,
scientific-artifact, trusted-path, documentation, and aggregate gates are
terminally green. The manifest must name the external dense asset and SHA-256;
the fresh-clone verifier must pass with that asset and fail closed when it is
missing or mutated.

**Exit evidence:** merged main commit, PR and receipt links, fresh-clone pass,
fresh-clone missing/mutation rejection, final report, and updated chronology.

## 6. Required deliverables

- `experiments/exp001-reference-integrated/protocol.json` and freeze manifest;
- strict schemas for items, exposure, matrix cells, tool edges, execution,
  statistical result, and publication manifest;
- principle, matrix, and tool fixtures with source locators and rights flags;
- lexical/split/contamination/power receipts;
- SmolLM2 execution, access, response/activation, statistical, report, and
  recovery receipts;
- external dense locator and hash, immutable publication manifest, limitations,
  and fresh-clone verifier evidence;
- public PR, exact-head CCP evidence branch, merge commit, and chronology entry.

## 7. Delegation and cost policy

Use deterministic tools first. Delegate the largest independent safe share to
GPT-5.6 Luna: source inventory, hash/schema audits, mechanical fixture checks,
synthetic test execution, and log distillation. GPT-5.6 Terra should orchestrate
milestones, integrate Luna outputs, and own protocol architecture, scientific
interpretation, security, CCP qualification, release, and merge decisions.
Do not delegate sealed-target access, model selection, statistical endpoints,
approval boundaries, or claim language.

## 8. Approval and recovery boundaries

No-model preparation needs no new external approval beyond normal repository
delivery. Before any model load, generation, material hardware use, or sealed
target read, request one explicit approval bound to the exact frozen protocol,
model revision, files, resource ceiling, one-run rule, access mode, and
publication duties. Preserve all prior A0-R2/C3 receipts and do not retry a
consumed run under this specification.

At interruption, record branch, exact HEAD, base, dirty state, worker status,
CCP resource/admission, completed gates, unproven gates, external hashes, and
the exact resume command in a restart handoff. Never treat a temporary path as
the checkpoint.

## 9. Completion checklist

- [ ] R3.0 schemas and no-model source audit pass.
- [ ] R3.1 fixtures, rights, contamination, source-family, and domain audits pass.
- [ ] R3.2 primary/statistics/code hashes are frozen before model output.
- [ ] Exact model/runtime/CCP approval dossier is recorded.
- [ ] Exactly one guarded run completes or publishes a terminal failure.
- [ ] Blinded, exposed, matrix, and tool endpoints remain non-pooled.
- [ ] Every terminal class and limitation is published with claim IDs empty.
- [ ] Exact-head receipt and hosted gates are terminally green.
- [ ] Fresh clone passes with the declared external asset and rejects missing or mutated assets.
- [ ] Main, chronology, persistent goal, and this specification agree on status.

