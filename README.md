# Emergent AI TRIZ

**Project Latent TRIZ** is an open research initiative testing whether neural sequence models learn domain-general, causally active representations that are functionally equivalent to TRIZ inventive principles.

The project starts from a falsifiable question:

> When a model learns from enough examples of human problem solving, do recurring contradiction-resolution strategies emerge as reusable internal representations even when TRIZ names, definitions, and canonical examples are absent?

This repository is the public laboratory for the hypothesis, datasets, preregistrations, experiments, evaluation protocols, code, results, and negative findings.

## Hypotheses

### Weak Latent TRIZ Hypothesis

Pretrained language models contain internal representations corresponding to at least some TRIZ inventive principles, and those representations generalize across domains.

### Strong Latent TRIZ Hypothesis

A neural sequence model can develop representations functionally equivalent to TRIZ inventive principles from unlabeled problem-solution examples, without receiving TRIZ terminology, principle labels, definitions, or canonical examples.

The controlled-emergence track is essential because pretrained models may have encountered TRIZ material during training.

## Initial research program

1. Build a cross-domain, multi-label dataset for a small set of distinguishable inventive transformations.
2. Separate recognition in pretrained open models from emergence in models trained on controlled corpora.
3. Map candidate representations with probes, similarity analysis, sparse features, and causal tracing.
4. Test causal specificity through steering, ablation, random-vector controls, and unrelated-principle controls.
5. Test whether candidate operators compose predictably.
6. Replicate across domains, model sizes, model families, prompts, cases, and blinded expert evaluators.

The proposed starting principles are Segmentation, Taking Out, Local Quality, Inversion, Dynamics, Another Dimension, Feedback, and Intermediary. This list is provisional and must be justified before data collection.

## Evidence standard

A probe score or visually attractive cluster is not sufficient. Strong evidence requires a combination of:

- cross-domain decodability;
- lexical independence;
- causal specificity;
- bidirectional control through steering and ablation;
- generalization to cases created after discovery data are frozen;
- recurrence across independently trained model families; and
- controlled emergence without explicit TRIZ material.

The hypothesis is weakened when effects disappear under lexical controls, fail on held-out domains, change terminology without changing solution strategy, reduce to generic creativity, damage fluency, require explicit TRIZ prompts, resist ablation, or fail independent replication.

## Repository map

- [`docs/SOURCE_ARTICLE.txt`](docs/SOURCE_ARTICLE.txt) — the source article that motivates the project, preserved as supplied.
- [`docs/RESEARCH_PROTOCOL.md`](docs/RESEARCH_PROTOCOL.md) — experimental design, controls, metrics, and decision criteria.
- [`docs/ARTICLE_STATUS.md`](docs/ARTICLE_STATUS.md) — provenance and bibliography-cleanup status for the supplied article.
- [`data/README.md`](data/README.md) — dataset design and leakage constraints.
- [`schemas/case.schema.json`](schemas/case.schema.json) — draft machine-readable case format.
- [`experiments/README.md`](experiments/README.md) — experiment packaging requirements.
- [`preregistrations/README.md`](preregistrations/README.md) — frozen hypotheses and analysis plans.
- [`results/README.md`](results/README.md) — result and negative-result reporting contract.

## Current status

The repository is at **protocol-design stage**. No dataset, model experiment, or empirical result is claimed yet. The source article contains imported citation placeholders; they are preserved for provenance and must be replaced with stable references before the article is treated as publication-ready.

## Contributing

Contributions are welcome from TRIZ practitioners, mechanistic interpretability researchers, open-model developers, patent and innovation specialists, cognitive scientists, and philosophers of AI. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License and attribution

Copyright 2026 Marco Porcellato ([`MarcoPorcellato`](https://github.com/MarcoPorcellato)).

Licensed under the [Apache License 2.0](LICENSE). Attribution information is recorded in [NOTICE](NOTICE).

