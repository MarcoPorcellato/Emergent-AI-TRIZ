# Data

This directory will contain redistributable Latent TRIZ datasets. No empirical dataset has been released yet.

## Candidate batches

`data/candidates/` is the staging area for discovery-only candidate material. It may contain model-generated or other pre-freeze artifacts that help establish the annotation workflow, leakage checks, and split design, but it is not itself a released dataset.

[`registry.json`](registry.json) is the machine-readable index of dataset snapshots and must conform to [`../schemas/dataset-registry.schema.json`](../schemas/dataset-registry.schema.json). An empty registry means that no dataset has been released; it is not evidence of a completed data stage.

## Expert reference corpus

[`triz-reference-sources.json`](triz-reference-sources.json) registers external
expert-authored TRIZ sources by exact hash, provenance, rights status, and
scientific role. [`triz-reference/principles.jsonl`](triz-reference/principles.jsonl)
contains independently written, page-bound summaries of the forty Inventive
Principles. [`triz-consulting-web-corpus.json`](triz-consulting-web-corpus.json)
catalogs a curated set of official public pages and tools from TRIZ Consulting
Group. These artifacts are reference-only and evidence-ineligible: they are not
released empirical datasets and cannot provide automatic ground-truth labels.

Third-party PDFs are not tracked merely because they are publicly downloadable.
The repository records links, hashes, citations, and permitted derivatives
until an explicit compatible redistribution grant is documented.

## Design requirements

Cases must span domains, avoid repetitive TRIZ vocabulary, support multiple labels, include near misses and alternative-principle controls, and preserve independent annotator decisions. The draft record format is defined in [`../schemas/case.schema.json`](../schemas/case.schema.json).

Do not commit private, licensed, personally identifying, or model-generated data without documented rights and provenance. Large raw corpora belong in an external versioned data release, referenced by checksums and immutable identifiers.
