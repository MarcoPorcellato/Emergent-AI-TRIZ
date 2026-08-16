# A0-R2-C1 tokenizer correction and approval request

Status: pre-output contract prepared; material execution is not authorized.

## What failed

The published A0-R2 attempt did not produce an activation or statistical
result. Transformers 5.15.0 returned a valid
`transformers.tokenization_utils_base.BatchEncoding`, while the adapter
accepted only a concrete Python `dict`. `BatchEncoding` implements
`collections.abc.Mapping` but is not a `dict`, so the adapter stopped before
the first forward pass and before sealed-target analysis.

This was predictable. The feasibility path used the mapping interface without
the adapter's concrete-type check, and the synthetic adapter tokenizer returned
a plain `dict`. Neither test exercised the real tokenizer container contract.

## Evidence and correction

The tracked tokenizer-only compatibility receipt binds the exact local
SmolLM2 snapshot and installed runtime. It records aligned token, attention,
and offset counts and proves `is_mapping=true`, `is_dict=false`. The probe used
no network, loaded no model weights, and accessed no sealed target.

A0-R2-C1 introduces an isolated adapter and runner. The only semantic change is
the accepted tokenizer container interface:

```text
isinstance(encoded, dict)
    ->
isinstance(encoded, collections.abc.Mapping)
```

The original R2 implementation and terminal failure package remain unchanged.
The C1 contract binds the new files, the tokenizer receipt, and the historical
failure package by SHA-256.

## Frozen scientific boundary

The model and revision, corpus, cases, sealed targets, prompts, architecture
mapping, primary endpoint, descriptive sensitivities, statistics, thresholds,
and terminal interpretation rules are unchanged. Tuning, model substitution,
claim promotion, and post-access retry remain prohibited.

The proposed corrective attempt is exactly one local-only CPU float32 run of
`HuggingFaceTB/SmolLM2-360M` revision
`f8027fd0eaeea54caa13c31d31b9fdc459c38b49`, with no network or generation,
at most 1,800 seconds, 8,589,934,592 bytes peak RSS, and 67,108,864 bytes of new
dense output. It permits exactly one sealed-target content read at the analysis
boundary and requires publication of every terminal outcome.

## Remaining gate

The contract deliberately records `operator_approval_granted=false`. Before
any new model load or target access, the contract and implementation must be
merged and exact-head qualified. A separate operator authorization must then
name that merged contract and authorize the single C1 attempt. A new receipt
will bind that authorization before the runner can proceed.
