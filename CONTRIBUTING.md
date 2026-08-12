# Contributing

Project Latent TRIZ is designed for adversarially useful, reproducible research. Contributions that challenge the hypothesis are as valuable as contributions that support it.

## Before contributing

Open an issue describing the research question, proposed evidence, relevant expertise, and expected artifact. Dataset contributions should explain provenance, licensing, labeling procedure, and leakage controls. Experiment contributions should identify the preregistration or clearly label the work as exploratory.

## Research requirements

Contributions must:

- distinguish observation, interpretation, and speculation;
- report negative and null results;
- preserve model identifiers, revisions, prompts, seeds, code versions, and environment details;
- separate discovery data from frozen evaluation data;
- test lexical and domain confounds;
- include norm-matched random and unrelated-principle controls for interventions;
- avoid claims about consciousness or human-equivalent understanding that the measurements do not establish; and
- respect dataset, model, and source licenses.

## Dataset changes

Each case should conform to [`schemas/case.schema.json`](schemas/case.schema.json). Labels should be multi-label and independently reviewed when possible. Disagreements must be retained rather than silently collapsed.

## Experiment changes

Place each study in its own directory under `experiments/`. Include a README containing the hypothesis, model revision, data snapshot, intervention point, controls, metrics, compute requirements, exact commands, and expected outputs.

## Results

Results belong under `results/` and should link to immutable code, data, and preregistration revisions. Do not overwrite earlier reports when analyses change; add a versioned report and explain the change.

## Licensing

By contributing, you agree that your contribution is licensed under the Apache License 2.0. Do not submit material that you do not have the right to redistribute.

