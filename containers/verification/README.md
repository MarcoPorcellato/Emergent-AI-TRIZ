# Latent-TRIZ verification runtime

This Dockerfile produces the offline dependency layer used by the local
Python 3.11 and 3.12 compatibility receipt. It contains only the locked JSON
Schema validation dependencies; it does not copy the repository, a model,
scientific data, credentials, or a receipt.

Builds must set both arguments to immutable values:

```text
BASE_IMAGE=docker.io/library/python@sha256:<platform-specific-base-digest>
PYTHON_SERIES=3.11 | 3.12
SOURCE_REVISION=<exact-source-commit>
```

The Dockerfile default is a pinned Python 3.11 base solely so static Docker
parsers have a valid `FROM`; a release build must still pass all three values.

Before an image can be used by CCP, publish its immutable arm64 manifest
digest, record the exact base digest and lockfile hash in the image publication
receipt, and bind the resulting image reference in both the v2 CCP
configuration and policy. Mutable tags are discovery aids only and must never
appear in either contract.

At receipt time, CCP mounts the candidate repository read-only and runs with
network disabled. The image is a reproducibility dependency, not scientific
evidence and not an authorization to access the SmolLM2 model or sealed R2
targets.

## Published CCP v2 runtime contract

The public arm64 images built from the PR 50 source definition are bound by
digest in `.commit-ci-preflight.toml` and `.commit-ci-policy-v2.toml`:

- Python 3.11: `ghcr.io/marcoporcellato/latent-triz-verify@sha256:25de19baba5938c80de18c930342ccdcdf3c6759051196c3c713bd3e434d2f0e`
- Python 3.12: `ghcr.io/marcoporcellato/latent-triz-verify@sha256:e984457d591121c52517027f49bb55371f68075caace763b8859db136e434dd0`

These immutable references are the executable compatibility contract. Package
visibility or a mutable discovery tag never substitutes for either digest.
