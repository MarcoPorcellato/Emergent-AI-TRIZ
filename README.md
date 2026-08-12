# Emergent AI TRIZ

Project Latent TRIZ is an official-lab foundation for studying whether models can represent TRIZ-like inventive transformations in a way that is measurable, reproducible, and falsifiable.

This repository does not claim that the experiments already exist. It defines the public artifact flow, governance boundaries, and the minimum foundation needed to run them later.

## Repository status

- Phase: `0` foundation
- Claim level: protocol and infrastructure only
- Evidence state: no dataset, preregistered study, or empirical result is claimed here
- Runtime: dependency-free Python 3.11+ lab core included in this repository

## Hypotheses and tracks

The **Weak Latent TRIZ Hypothesis** predicts that pretrained language models contain representations corresponding to at least some TRIZ Inventive Principles and that those representations generalize across substantially different domains.

The **Strong Latent TRIZ Hypothesis** predicts that a neural sequence model can develop functionally equivalent representations from unlabelled problem-solution examples without receiving TRIZ terminology, definitions, principle labels, or canonical examples.

- **Track A — Existing open models:** inspect pretrained base and instruction-tuned checkpoints for cross-domain, causally active TRIZ-like representations.
- **Track B — Controlled emergence:** train small Transformers on fully inspectable corpora that exclude explicit TRIZ material.

Strong evidence requires converging lexical-control, cross-domain, causal, bidirectional, novel-case, compositional, cross-model, and controlled-emergence results. A probe score or visual cluster alone is not sufficient.

## Public artifact flow

The intended research flow is:

1. hypothesis
2. preregistration
3. dataset snapshot
4. study manifest
5. run records
6. blinded evaluation
7. versioned results

Each step should be frozen before the next confirmatory step starts. Exploratory work may happen earlier, but it must be labeled and kept separate from confirmatory records.

## Governance boundaries

- Hypotheses and analytical plans belong in preregistrations, not in results reports.
- Dataset snapshots must be immutable, versioned, and provenance-backed.
- Run records must preserve exact code revision, schema revision, model revision, prompt text, seed, environment, and output hashes.
- Blinded evaluation must be separated from discovery data and from any unblinded analysis.
- Versioned results must never overwrite earlier reports when the analysis changes.

The repository is a public lab scaffold, not a claim of successful discovery.

## Phase 0 foundation

Phase 0 establishes the working contract for the future lab:

- define the case schema and leakage controls;
- define preregistration and result file formats;
- keep the artifact chain explicit from hypothesis to versioned result;
- keep claims bounded to what the available evidence supports;
- make validation possible with dependency-free checks.

## Future stages

The intended research program is staged, but only the foundation is present here.

### Stage 1 - Dataset assembly

Build a cross-domain case corpus with provenance, leakage controls, and balanced labels.

### Stage 2 - Surface baselines

Measure what can be learned from lexical and shallow signals before representation analysis.

### Stage 3 - Representation mapping

Inspect candidate internal operators with probes, similarity methods, and readout analyses.

### Stage 4 - Causal intervention

Test whether candidate directions change solution strategy under controlled steering.

### Stage 5 - Composition

Test whether multiple candidate operators combine predictably.

### Stage 6 - Replication

Replicate across domains, model families, and independent evaluation sets.

## Quickstart

Run the repository directly from a checkout:

```bash
make check
make preflight-plan
PYTHONPATH=src python -m latent_triz.cli validate --schema schemas/case.schema.json tests/fixtures/case_valid.json
PYTHONPATH=src python -m latent_triz.cli fingerprint schemas/case.schema.json
```

## Repository map

- [Documentation portal](docs/index.md) - OKF maintained-bundle entry point and map
- [Documentation log](docs/log.md) - chronology and updates for the maintained bundle
- [Documentation reference index](docs/reference/index.md) - schema and artifact references
- [Commit CI Preflight](docs/reference/commit-ci-preflight.md) - local receipts and lightweight GitHub verification
- [Decision index](docs/decisions/index.md) - ADR ledger and governance boundaries
- [Lab architecture](docs/LAB_ARCHITECTURE.md) - artifact flow, governance boundaries, and staged lab structure
- [Roadmap](docs/ROADMAP.md) - Phase 0 foundation and future Stages 1-6
- [Article](docs/ARTICLE.md) - research proposal and hypothesis framing
- [Research protocol](docs/RESEARCH_PROTOCOL.md) - experimental design, controls, metrics, and decision criteria
- [Article status](docs/ARTICLE_STATUS.md) - provenance and editorial status for the supplied article
- [Data](data/README.md) - dataset design and leakage constraints
- [`schemas/case.schema.json`](schemas/case.schema.json) - machine-readable case format
- [`schemas/dataset-registry.schema.json`](schemas/dataset-registry.schema.json) - dataset snapshot registry contract
- [`schemas/study.schema.json`](schemas/study.schema.json) - study manifest contract
- [`schemas/run.schema.json`](schemas/run.schema.json) - immutable run record contract
- [`src/latent_triz/`](src/latent_triz/) - dependency-free validation and fingerprinting CLI
- [`experiments/000-template/`](experiments/000-template/) - non-empirical study and run templates
- [`experiments/README.md`](experiments/README.md) - experiment packaging requirements
- [`preregistrations/README.md`](preregistrations/README.md) - frozen hypotheses and analysis plans
- [`results/README.md`](results/README.md) - versioned reporting contract

## OKF gate

Repository changes to maintained documentation are required to pass the OKF gate:

- use the maintained bundle index at [`docs/index.md`](docs/index.md)
- ensure every maintained doc includes `frontmatter` with `type`, `title`, `description`, `status`, and `last_verified`
- keep `status` canonical on primary maintained entry points and update `last_verified` on edits

## Contributing

Contributions should preserve the foundation contract: separate exploratory from confirmatory work, keep provenance explicit, and avoid claiming empirical success until the supporting artifacts exist.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for submission requirements.

## License and attribution

Copyright 2026 Marco Porcellato ([`MarcoPorcellato`](https://github.com/MarcoPorcellato)).

Licensed under the [Apache License 2.0](LICENSE). Attribution information is recorded in [NOTICE](NOTICE).
