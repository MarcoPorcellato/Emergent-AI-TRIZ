# A0-R2-C3 analysis-only metadata recovery

Status: pre-output corrective specification. No C3 target access or statistical
result is authorized yet.

## Purpose

C3 is the narrowest recovery from the published C2 terminal failure. It reuses
the immutable C2 activation bundle and must not load, import, query, or
substitute a model. Its sole prospective material action is one newly
authorized read of the exact-hash sealed targets at the analysis boundary.

## Deterministic diagnosis

The C2 failure receipt records digest
`e42a209ddb9d3e2017d68f5b56ec609986b280e9890dace37a8152fd6f4a9e0a`.
The runner hashes the exception text, and that digest resolves to
`activation dtype drift`.

The C2 activation receipt declares CPU `float32`, but every one of the 1,920
rows in the immutable representation index omitted the required `dtype` field.
The frozen analyzer rejects such a row before it opens sealed targets. This is
an index-metadata omission, not a model, tokenizer, tensor, target, or
statistical-kernel result.

## C3 recovery rule

The C3 analysis adapter may add `dtype: float32` only in memory, and only when:

- the source index hash is exactly
  `baa78647fcc01c1d71cf27ef1c1fd83c6e38feb2a9a54a58fab87f245c63fc58`;
- the source activation receipt declares `runtime.torch_dtype` as `float32`;
- the source has exactly 1,920 index rows; and
- every source row omits, rather than contradicts, `dtype`.

The source index bytes, activation receipt, dense asset, model output, frozen
protocol, prompts, cases, targets, endpoint, statistics, thresholds, and
interpretation rules remain unchanged. Any mismatch is terminally refused.

The frozen R2 activation writer, analyzer, and reporter remain byte-identical
to the code bound by the consumed R2 dossier. C3 instead carries its recovery,
source-dense-asset publication, and verification behavior in C3-named modules.
It does not retrofit the historical writer. Any future model activation must
use a separately preregistered, versioned writer that enforces the published
index-record contract before analysis. The broader guardrails are in the
[SmolLM2 runtime contract](./reference/smollm2-runtime-contract.md). None of
this alters the historical C2 index or authorizes a further model run.

## Ordered milestones

1. **C3.0 — diagnosis and synthetic qualification.** Prove the digest-to-error
   mapping, exact immutable-index omission, and fail-closed recovery rule with
   synthetic rows only. Exit: no model or target access; all regression and
   mutation tests pass.
2. **C3.1 — reviewable pre-output contract.** Bind the C2 receipts, source
   activation/index/dense hashes, C3-namespaced recovery and publication code,
   analysis-only boundary, terminal publication rules, and fresh authorization
   schema. The byte-bound historical R2 modules must remain unchanged. Exit:
   exact-head local and hosted qualification after publication.
3. **C3.2 — explicit operator authorization.** Request one analysis-only run:
   no model load, no network, no generation, no new dense output, and exactly
   one sealed-target read. The authorization must bind the final C3 contract
   hash and cannot reuse C2 authorization.
4. **C3.3 — guarded analysis and immutable publication.** Only after CCP
   resource `Admit`, inactive admission, and an empty queue, perform one
analysis of the existing C2 asset. Publish positive, null, failed, or
non-interpretable output with the C2 source hashes and C3 recovery receipt.
For every C3 terminal package after source synchronization, preserve the
copied immutable C2 receipt and representation index plus the external dense
locator/hash. These identify predecessor evidence only; they never imply that
C3 loaded a model or created fresh activations.

## Epistemic boundary

Even a positive C3 result would say only that the frozen automated-proxy signal
persisted across the two exact model families tested. It remains exploratory
E0, evidence-ineligible, not expert-validated, and cannot establish general
TRIZ rediscovery.
