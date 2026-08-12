# Data

This directory will contain redistributable Project Latent TRIZ datasets. No empirical dataset has been released yet.

[`registry.json`](registry.json) is the machine-readable index of dataset snapshots and must conform to [`../schemas/dataset-registry.schema.json`](../schemas/dataset-registry.schema.json). An empty registry means that no dataset has been released; it is not evidence of a completed data stage.

## Design requirements

Cases must span domains, avoid repetitive TRIZ vocabulary, support multiple labels, include near misses and alternative-principle controls, and preserve independent annotator decisions. The draft record format is defined in [`../schemas/case.schema.json`](../schemas/case.schema.json).

Do not commit private, licensed, personally identifying, or model-generated data without documented rights and provenance. Large raw corpora belong in an external versioned data release, referenced by checksums and immutable identifiers.
