---
type: readiness-contract
title: CV2 — strengthened negative controls
description: No-model protocol for challenging lexical, source, domain, and taxonomy shortcuts before any new recognition output.
status: no_model_ready
last_verified: 2026-08-18
---

# CV2 — strengthened negative controls

CV2 is a no-model readiness contract. It does not create labels, load a model,
open sealed targets, or qualify evidence. Its machine-readable contract is
`experiments/cv2-negative-controls/protocol.json` and its strict schema is
`schemas/cv2-negative-control.schema.json`.

The control plan is intentionally broader than the historical Lab 05 fixture.
It includes lexical and length matching, template swaps, near-neighbour
principles, cosmetic counterfactuals, generic transformations, Matrix
direction swaps, unsupported Panitz edges, explicit abstention, random labels,
random directions, and extreme cross-domain shifts. Each family is scored
separately; no secondary or source-exposed result can rescue a failed blinded
primary.

## Freeze gate

Before any model output, the future implementation must produce contamination,
lexical-shortcut, template-shortcut, grouped-split, source-family-split,
power-calibration, and abstention-policy receipts. Every problem family stays
within one split, and blinded/source-exposed strata remain physically separate.
Unknown, missing, or contradictory receipt data is `non_interpretable`.

The protocol publishes all terminal classes (`positive`, `null`, `failed`, and
`non_interpretable`) and forbids post-hoc tuning, pooling, or claim promotion.

Run the deterministic readiness surface with:

```text
make no-model-quickstart
```

This renders the synthetic dashboard, validates all tracked schema pairs,
audits the H1 collection packet, and validates the CV2/Lab06 contracts without
model libraries, network access, generation, or sealed-target reads.
