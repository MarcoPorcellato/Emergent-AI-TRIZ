---
type: expert-reference-corpus
title: TRIZ Expert Reference Corpus
description: Provenance, rights, scientific role, and evaluation use of expert-authored TRIZ reference sources.
status: canonical
last_verified: 2026-08-16
---

# TRIZ expert reference corpus

This collection registers expert-authored TRIZ material that can improve
construct definition and future test design. It is a **reference corpus**, not
an empirical dataset, a source of automatic labels, or evidence for the Latent
TRIZ Hypothesis.

The machine-readable source of truth is
[`data/triz-reference-sources.json`](../../data/triz-reference-sources.json),
validated by
[`schemas/triz-reference-registry.schema.json`](../../schemas/triz-reference-registry.schema.json).
The independently worded, page-bound principle summaries are in
[`data/triz-reference/principles.jsonl`](../../data/triz-reference/principles.jsonl).
The curated discovery layer for the provider's wider public site is
[`data/triz-consulting-web-corpus.json`](../../data/triz-consulting-web-corpus.json),
validated by
[`schemas/triz-web-corpus.schema.json`](../../schemas/triz-web-corpus.schema.json).
It records 18 official landing pages, tools, direct references, and interactive
resources without copying their content into this repository.

## Source and rights status

| Source | Verified contribution | Authority status | Public-repository treatment |
|---|---|---|---|
| Robert Adunka, *40 Inventive Principles with 132 illustrated examples* (2023) | forty principle definitions and examples; physical-contradiction workflow; separation crosswalk; Fayer grouping | exact artifact and author-hosted public download verified | copyrighted reference; link, hash, citation, and independently written summaries tracked; PDF and images not vendored |
| Mann, Dewulf, Zlotin, and Zusman, *Matrix 2003* | updated 48 by 48 contradiction matrix and principle recommendations | authorship and provider permission statement verified | no general open license established; link, hash, and metadata tracked; matrix binary and cell table not vendored |
| Gregor Panitz, *TRIZ Tools Overview with main interactions* | expert conceptual map of tools, analysis stages, databases, and main interactions | user attribution; author expertise corroborated, but canonical artifact URL and publication date unverified | metadata and independent summary only; no image or full edge-list reproduction |

“Publicly downloadable” is not the same as “openly licensed.” The repository's
Apache-2.0 license does not relicense third-party material. Until a compatible
redistribution grant is documented, the three PDF binaries, screenshots, and
bulk verbatim extracts remain external.

The provider's tools pages explicitly permit training use subject to copyright
attribution. That statement is recorded per applicable resource and is not
generalized into a site-wide redistribution licence.

## What the sources add

### Forty Inventive Principles

Pages 1–40 of Adunka's slide set provide one principle per page with aliases,
operational interpretations, and multiple illustrated examples. Pages 41–42
connect physical-contradiction resolution to separation methods and suggested
principles; pages 43–44 give a Fayer grouping; pages 45–46 document the related
application and publication context.

The repository records one short, independently phrased operator description
and one independently phrased example for each principle. These records improve
terminology coverage and authoring consistency without reproducing the slide
set. They are suitable for reference-informed question construction, not for
automatic truth labels.

### Matrix 2003

The supplied matrix expands the classical 39 by 39 parameter scheme to a 48 by
48 artifact and groups parameters into physical, performance, efficiency,
reliability, manufacturing/cost, and measurement families. Its cells recommend
Inventive Principles for ordered improving/worsening parameter pairs.

Matrix 2003 is an updated and more extensive alternative to the classical
matrix, but it is not the latest matrix publication: Matrix 2010 is a later
50 by 50 work. Matrix recommendations are expert-curated heuristics derived
from the authors' research programme, not validated ground-truth labels for
every concrete problem.

### TRIZ tools relationship map

The Panitz diagram links project framing, ideality, functional and flow
analysis, resources, contradictions, the matrix, separation principles,
Inventive Principles, substance-field analysis, standard solutions, ARIZ,
evolution trends, effects databases, patent strategy, and other tools.

It broadens the laboratory from principle recognition to process questions:
which tool fits a problem state, which transitions are plausible, which tools
are alternatives, and which sequence omits necessary problem formulation. The
map remains one expert's conceptual organization, not a canonical or causal
TRIZ ontology.

## Scientific integration boundary

The frozen A0-R2 protocol, corpus, targets, primary endpoint, thresholds,
controls, and stopping rules remain unchanged. These references are explicitly
ineligible for R2.3. Using their wording, examples, matrix cells, or tool graph
to revise R2 cases after preregistration would introduce post-freeze
contamination and reduce reliability.

The sources instead define a future `R3/EXP-001` reference layer with two
strictly separated evaluation strata:

1. **TRIZ-blinded:** no source text, principle name, canonical example, matrix
   lookup, or tool-map edge is exposed. This stratum tests transfer and
   rediscovery-like behaviour.
2. **Source-exposed:** the relevant reference or lookup context is provided.
   This stratum tests retrieval, interpretation, and competent use of TRIZ.

The strata must never be pooled into one score or one claim.

## Future test families

### Principle coverage

- recognize a principle across independent paraphrases;
- classify independently authored examples and near misses;
- distinguish neighbouring operators such as Segmentation, Taking Away,
  Merging, Nesting, Local Conditions, and The Other Way Round;
- support multi-label and abstention outcomes;
- separate canonical-example recall from transfer to held-out domains.

### Contradiction-matrix use

- map concrete improving and worsening features to abstract parameters;
- retrieve the ordered parameter-pair recommendations in source-exposed tests;
- test robustness to parameter synonyms and swapped direction;
- include plausible but non-recommended principles as negative controls;
- report exact-cell agreement separately from solution quality.

Matrix agreement alone is not proof of inventiveness. A good solution may use
a principle absent from a recommended cell, and a recommended principle may be
poorly instantiated.

### Tool-workflow understanding

- select the next useful tool from a stated problem-analysis state;
- distinguish analysis, contradiction formulation, idea generation, and
  evaluation stages;
- detect invalid, reversed, or unsupported transitions;
- compare source-exposed path following with blinded procedural transfer;
- require abstention when the map does not establish a relationship.

## Reliability improvements and limits

The reference corpus improves:

- **content coverage:** all forty principles rather than an initial two;
- **construct clarity:** page-bound definitions, examples, and crosswalks;
- **reproducibility:** exact hashes, sizes, provenance, and rights status;
- **negative-control design:** neighbouring principles, direction reversals,
  unsupported matrix choices, and invalid workflow edges;
- **auditability:** every future item can record source, page, transformation,
  and lexical exposure.

It does not by itself improve evidence for the Latent TRIZ Hypothesis. The
documents may already occur in model training data, expert mappings may be
contestable, and source-derived cases can reward memorization. Reliability
improves only when blinded generalization, source-exposed competence, lexical
controls, source-family splits, and independent expert judgments remain
separate.

## Requirements for an R3/EXP-001 freeze

- define a schema for source exposure, page/table locator, derivation method,
  and canonical-example proximity;
- validate any encoded matrix cell twice against the visual source;
- obtain or document redistribution rights before tracking third-party binary
  or bulk extracted content;
- split by source and example family before model output;
- keep reference recommendations separate from independent human labels;
- preregister scoring, abstention, negative controls, and claim language;
- publish positive, null, failed, and non-interpretable outcomes equally.
