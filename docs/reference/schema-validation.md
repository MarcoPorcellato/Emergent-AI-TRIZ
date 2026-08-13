---
type: Reference
title: Fail-closed schema validation
description: Supported Draft 2020-12 subset, reference cross-validation, and mutation-test contract.
status: active
last_verified: 2026-08-13
---

# Fail-closed schema validation

Latent TRIZ keeps a dependency-free validator for local runtime paths and uses
the pinned `jsonschema` Draft 2020-12 validator as an independent CI oracle.
The minimal validator rejects unsupported keywords and formats instead of
silently treating unimplemented constraints as successful validation.

## Enforced subset

The runtime validator enforces every keyword currently used by tracked
schemas, including local JSON Pointer `$ref` and `$defs`, `allOf`, conditional
branches, `contains`, schema-valued `additionalProperties`, `minProperties`,
and inclusive and exclusive numeric bounds. Local references that are cyclic
or cannot be resolved fail validation.

Metadata-only keywords such as `title`, `description`, and `examples` are
explicitly allow-listed. Adding a new assertion keyword requires an
implementation and tests in the same change.

## Independent cross-check

Install the pinned reference environment and run:

```text
python -m pip install -r requirements-schema.lock
make schema-cross-validate
```

The cross-check validates every tracked schema with
`Draft202012Validator.check_schema`, requires both validators to accept the
tracked schema-instance matrix, and mutates the Lab 04 result to prove both
validators reject:

- a 63-character SHA-256;
- a predecessor without `summary_sha256`;
- a zero value guarded by `exclusiveMinimum`;
- a NumPy backend paired with the pure-Python solver.

The reference dependency is intentionally separated from the runtime package.
Normal local commands remain dependency-free; protected CI installs only the
pinned schema-validation set before running the repository gate.
