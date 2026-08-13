# Latent TRIZ

**Do language models rediscover general operators of invention?**

Latent TRIZ is an open laboratory for testing whether language models learn internal, cross-domain, and causally active transformations that resemble TRIZ Inventive Principles. The project combines reproducible experiments, mechanistic interpretability, blinded evaluation, and explicit falsification criteria.

> **Current evidence boundary:** the repository contains a functioning, deterministic Stage 1 protocol smoke test and research-governance infrastructure. It does **not** yet contain evidence that a TRIZ-like representation exists in any model. Every scientific claim starts at E0: hypothesis.

## Run the laboratory foundation

```bash
git clone https://github.com/MarcoPorcellato/Latent-TRIZ.git
cd Latent-TRIZ
make check
make stage1-pilot-smoke
```

The smoke command builds a blinded packet allocation, scores fixture annotations, validates every artifact, and compares the result with a frozen expected output. Its data are synthetic and marked `non_empirical`; passing it demonstrates process integrity, not the hypothesis.

## The hypothesis

The **Weak Latent TRIZ Hypothesis** predicts that pretrained language models contain representations corresponding to at least some TRIZ Inventive Principles and that those representations generalize across substantially different domains.

The **Strong Latent TRIZ Hypothesis** predicts that a neural sequence model can develop functionally equivalent representations from unlabelled problem-solution examples without receiving TRIZ terminology, definitions, principle labels, or canonical examples.

- **Track A — pretrained models:** inspect openly available base and instruction-tuned checkpoints for cross-domain, causally active TRIZ-like representations.
- **Track B — controlled emergence:** train small Transformers on fully inspectable corpora that exclude explicit TRIZ material.

A probe score, attractive cluster, or behavioral anecdote is insufficient. Strong evidence must converge across lexical controls, cross-domain transfer, causal intervention, bidirectionality, novel cases, composition, model families, and controlled emergence.

## Evidence Ladder

| Level | Meaning | Minimum interpretation |
|---|---|---|
| E0 | Hypothesis | Registered, falsifiable, no empirical support claimed |
| E1 | Behavioral observation | Effect observed under documented behavioral controls |
| E2 | Cross-domain decodability | Representation decodes beyond lexical and domain shortcuts |
| E3 | Causal steering | Intervention changes behavior in the predicted direction |
| E4 | Bidirectional causality | Opposing interventions produce opposing, controlled effects |
| E5 | Cross-model replication | Result reproduces across independent model families or teams |
| E6 | Controlled emergence | Equivalent operators emerge in a controlled training setting |

Promotion is evidence-bound: a claim may advance only when its preregistration, immutable dataset snapshot, run records, results, and replication links satisfy the level's proof obligations. See the [Evidence Ladder](docs/EVIDENCE_LADDER.md) and machine-readable [claim registry](data/claims.jsonl). The initial claims are all E0 and untested.

## From visible behavior to mechanism

The planned experimental route deliberately grows in complexity:

```mermaid
flowchart LR
    A["Behavioral controls"] --> B["Activations"]
    B --> C["Logit lens"]
    C --> D["Linear probes"]
    D --> E["Contrastive directions"]
    E --> F["Steering"]
    F --> G["Sparse features"]
    G --> H["Activation patching"]
    H --> I["Jacobian analysis"]
```

Each step must earn the next. The near-term target is a local, visual, one-command exploration lab; the current Stage 1 smoke establishes the artifact and evaluation path that this empirical work will use.

## Public artifact chain

```text
hypothesis -> preregistration -> dataset snapshot -> study manifest
           -> immutable run records -> blinded evaluation -> versioned results
```

Exploratory work may happen earlier, but it remains visibly separate from confirmatory records. Results are versioned rather than overwritten, and model, prompt, seed, environment, schema, and output hashes travel with every run.

## Start here

- [Documentation portal](docs/index.md) — maintained documentation map
- [Evidence Ladder](docs/EVIDENCE_LADDER.md) — claim promotion rules E0–E6
- [Stage 1 blinded pilot](docs/STAGE1_PILOT.md) — runnable packet, response, annotation, and summary contracts
- [Research protocol](docs/RESEARCH_PROTOCOL.md) — controls, metrics, and decision criteria
- [Roadmap](docs/ROADMAP.md) — visual labs, EXP-001, and the replication program
- [Article](docs/ARTICLE.md) and [article status](docs/ARTICLE_STATUS.md) — hypothesis framing and provenance
- [Claim registry](data/claims.jsonl) and [claim schema](schemas/claim.schema.json) — falsifiable public claims
- [Discussions](https://github.com/MarcoPorcellato/Latent-TRIZ/discussions) — research questions and collaboration

## Four contribution lanes

- **Lane 0 — Learning:** reproduce a tutorial or smoke path; no scientific claim is promoted.
- **Lane 1 — Exploratory:** add a clearly labeled probe, visualization, dataset audit, or candidate mechanism.
- **Lane 2 — Confirmatory:** execute a frozen preregistration against a sealed dataset and immutable run contract.
- **Lane 3 — Independent replication:** reproduce a result with an independent model family, dataset, implementation, or team.

TRIZ practitioners can help operationalize principles and design negative cases. Interpretability researchers can build probes and interventions. Python contributors can improve the lab and visual tooling. Statisticians can review power, multiplicity, and decision rules. Contributors with limited hardware can work on schemas, fixtures, annotation, documentation, or small-model experiments.

Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing a claim-level change.

## Repository status

- Foundation governance and schemas: implemented
- Matryca-Knowledge-style maintained documentation bundle: implemented
- Commit CI Preflight: configured with a dependency-free container runner to reduce unnecessary GitHub Actions usage
- Stage 1 deterministic blinded-pilot smoke: implemented, synthetic, non-empirical
- First model-backed visual experiment: planned, not yet implemented
- Empirical support for the Latent TRIZ hypothesis: none claimed

## License and attribution

Copyright 2026 Marco Porcellato ([`MarcoPorcellato`](https://github.com/MarcoPorcellato)).

Licensed under the [Apache License 2.0](LICENSE). Attribution information is recorded in [NOTICE](NOTICE).
