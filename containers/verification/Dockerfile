# Build this image only from an immutable Python base reference. The published
# resulting digest, not a mutable tag, is what CCP policies accept at runtime.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG PYTHON_SERIES
ARG SOURCE_REVISION

LABEL org.opencontainers.image.title="Latent-TRIZ verification runtime"
LABEL org.opencontainers.image.description="Offline runtime for the repository and JSON Schema cross-validation gates."
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.revision="${SOURCE_REVISION}"
LABEL org.opencontainers.image.source="https://github.com/MarcoPorcellato/Latent-TRIZ"

COPY requirements-schema.lock /opt/latent-triz/requirements-schema.lock

RUN test -n "${PYTHON_SERIES}" \
    && python -c "import sys; expected='${PYTHON_SERIES}'; actual=f'{sys.version_info.major}.{sys.version_info.minor}'; assert actual == expected, (actual, expected)" \
    && python -m pip install --disable-pip-version-check --no-cache-dir --requirement /opt/latent-triz/requirements-schema.lock \
    && python -c "import jsonschema; assert jsonschema.__version__ == '4.26.0'"

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1
