# A0-R2-C2 Llama hidden-state shape correction

Status: pre-output contract prepared; material execution is not authorized.

## Predecessor and root cause

The only A0-R2-C1 execution loaded the exact local SmolLM2 snapshot and failed
before sealed-target analysis. The adapter accepted the tokenizer container,
but the shared extraction path expected each hidden-state layer to have shape
`[token, hidden]`. Llama returned `[batch, token, hidden]` with a singleton
batch axis. The old normalizer therefore attempted to convert a token vector to
a scalar. C1 remains an immutable terminal `failed` package.

## C2 change

C2 introduces new namespaced adapter and runner code. For every hidden-state
layer it removes only a singleton leading batch dimension, validates exact token
count and hidden size, converts every scalar to finite float, and rejects batch
sizes other than one and every malformed or drifted shape. The frozen shared
R2/C1 code and packages are unchanged.

## Frozen scientific boundary

The exact SmolLM2 revision, nine runtime files, frozen corpus and targets,
prompts, final-block endpoint, baseline, descriptive sites, statistical rules,
thresholds, resource limits, no-network/no-generation policy, no-tuning rule,
and terminal-publication policy are unchanged. C2 permits one material attempt
and one analysis-boundary target read only after a new explicit authorization.

## Qualification and remaining gate

Synthetic C2 tests cover valid rank-two and singleton-batch rank-three states,
and refuse non-singleton batches, token mismatch, hidden-size mismatch, and
malformed nesting. The C2 contract binds the C1 terminal failure and manifest
by hash. It must be merged and exact-head qualified before an operator can
authorize one C2 run. A new authorization is mandatory because C1 already
loaded the model.
