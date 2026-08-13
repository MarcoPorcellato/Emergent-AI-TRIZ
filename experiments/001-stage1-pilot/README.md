# Stage 1 Pilot Smoke Experiment

This directory contains a synthetic, non-empirical smoke bundle for the Stage 1 preregistered pipeline test.

Contents:

- `experiments/001-stage1-pilot/manifest.json`
- `data/pilot/packets.jsonl`
- `data/pilot/cases.jsonl`
- `data/pilot/responses.jsonl`
- `data/pilot/annotations.jsonl`
- `data/pilot/summary.json`

Purpose:

- exercise JSONL ingestion;
- verify case/response/annotation pairing;
- confirm the control versus TRIZ-name-free treatment labels remain stable;
- provide a non-confirmatory example bundle for the preregistration.

Non-goals:

- no model training;
- no empirical evaluation claim;
- no scientific interpretation;
- no external provenance.

The records are synthetic placeholders only.

The arm names are stable protocol identifiers:

- `control`: generic constraint-respecting problem solving;
- `treatment`: contradiction-focused elicitation without TRIZ names or examples.

The tracked packet contains the arm key for reproducibility. Evaluator-facing
exports must withhold `arms_by_blind` until ratings and exclusions are frozen.

## Runner commands

Prepare packets:

```bash
rtk env PYTHONPATH=src python3 -m latent_triz.cli pilot-prepare --seed 20260812 --arms control treatment --cases data/pilot/cases.jsonl --output data/pilot/packets.jsonl
```

Score the smoke bundle:

```bash
rtk env PYTHONPATH=src python3 -m latent_triz.cli pilot-score --packets data/pilot/packets.jsonl --responses data/pilot/responses.jsonl --annotations data/pilot/annotations.jsonl --output data/pilot/summary.json
```

Run `make stage1-pilot-smoke` to reproduce and validate the complete tracked
bundle without contacting a model provider.
