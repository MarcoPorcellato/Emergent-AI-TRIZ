# Wave 1 candidate batch

This directory is the staging area for Wave 1 discovery material.

Current batch status:

- 24 candidate cases;
- 12 Segmentation and 12 Inversion cases;
- 4 domains: manufacturing, packaging, software operations, and healthcare devices;
- 3 or more cases per principle per domain;
- reciprocal opposite-label pairs are required;
- target lexical cues are forbidden in the surface text;
- the batch is model-generated, non-empirical, non-frozen, and not evidence-eligible; its audit only qualifies it for blinded review.
- deterministic field-only word/character n-gram overlap diagnostics are now retained;
- domain diagnostics are evaluable, while source and template shortcut classifiers are
  explicitly non-evaluable for the single-source batch without a structured template ID;
- sentence embeddings remain optional and are explicitly marked `not_run` in semantic leakage output unless a backend is added.

Limitations:

- the batch is 100% model-generated, which exceeds the final source-policy ratio of 0.35;
- it is discovery-only and not independently annotated yet;
- it is not frozen (freeze is currently blocked by missing semantic pair-review metadata);
- it cannot support claims about the Latent TRIZ Hypothesis;
- it must not be presented as empirical evidence.

Path to acceptance:

1. obtain two independent blinded raters;
2. retain abstentions;
3. check agreement against the versioned guide;
4. add human-authored, adapted, and historical provenance so the source mix can satisfy the final policy;
5. freeze discovery and holdout splits separately;
6. run a leakage audit before any confirmatory use;
7. populate `pair_semantic_review` in `wave1-manifest.json` (`pair_id`, `status`, `reviewer_id`, `reviewed_at`, optional `notes`) before `ready_for_freeze` can become true.

Run `make dataset-wave1-audit` before every review session. Start a local
blinded session with `make annotate-wave1 ANNOTATION_RATER_ID=rater_01`.
After collecting at least two retained rater files, run
`make wave1-annotation-audit ANNOTATION_FILES="path/rater1.jsonl path/rater2.jsonl"`
to produce the retained batch summary at `artifacts/annotations/wave1-audit.json`.
The batch manifest in this directory defines its exact counts and candidate
constraints; the final dataset plan remains under `experiments/001-stage1-pilot/`.
