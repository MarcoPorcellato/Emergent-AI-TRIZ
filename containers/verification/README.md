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

Before an image can be used by CCP, publish its immutable arm64 manifest
digest, record the exact base digest and lockfile hash in the image publication
receipt, and bind the resulting image reference in both the v2 CCP
configuration and policy. Mutable tags are discovery aids only and must never
appear in either contract.

At receipt time, CCP mounts the candidate repository read-only and runs with
network disabled. The image is a reproducibility dependency, not scientific
evidence and not an authorization to access the SmolLM2 model or sealed R2
targets.
